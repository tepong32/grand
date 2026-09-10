"""Real shared historical review through ordinary DV and Treasury services."""
import csv
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
import uuid
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting import claim_attributions as history
from accounting.models import JournalEntry, JournalLine, PostingMapping, PayableClaimReservation, PayableClaimRetirement, SharedPayableClaimProposal
from accounting.payables import _capacity
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule
from . import test_consolidated_payables as fixtures
from .models import ReturnedInstrumentReview
from .prior_payables import current_evidence
from .services import issue_check
from .deduction_corrections import request_correction
from .posting import reconcile_posted_voucher_entry


class SharedHistoricalDVTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.ConsolidatedPayableTests.setUpTestData.__func__)
    employee = classmethod(fixtures.ConsolidatedPayableTests.employee.__func__)
    create_case = fixtures.ConsolidatedPayableTests.create_case
    budget_certify = fixtures.ConsolidatedPayableTests.budget_certify
    return_signatures = fixtures.ConsolidatedPayableTests.return_signatures
    acknowledge_advice = fixtures.ConsolidatedPayableTests.acknowledge_advice
    enable_payment_event_rules = fixtures.ConsolidatedPayableTests.enable_payment_event_rules
    case_for_validation = fixtures.ConsolidatedPayableTests.case_for_validation
    post_request = fixtures.ConsolidatedPayableTests.post_request
    pay = fixtures.ConsolidatedPayableTests.pay
    validate_group = fixtures.ConsolidatedPayableTests.validate_group
    release_issued = fixtures.ConsolidatedPayableTests.release_issued
    return_review = fixtures.ConsolidatedPayableTests.return_review

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='grand-shared-dv-')
        cls.override = override_settings(MEDIA_ROOT=cls.temp, GRAND_EXPORT_ROOT=cls.temp)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.temp, ignore_errors=True)

    def setUp(self):
        fixtures.ConsolidatedPayableTests.setUp(self)
        owner = dict(department_id=self.accounting.pk, department_label=self.accounting.name,
            period=self.accounting_period, fund=self.accounting_fund,
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        self.shared_sources = []
        for index, amount in enumerate((1800, 1200), 1):
            entry = JournalEntry.objects.create(**owner, reference=f'SHARED-OLD-CREDIT-{index}',
                entry_date=date(2026, 8, 20), description='Original historical invoice')
            JournalLine.objects.create(entry=entry, sequence=1, account=self.expense_account, debit=amount)
            source = JournalLine.objects.create(entry=entry, sequence=2, account=self.payable_account, credit=amount)
            submit_entry(entry, self.preparer)
            post_entry(entry, self.validator)
            self.shared_sources.append(source)
        entry = JournalEntry.objects.create(**owner, reference='SHARED-OLD-PAYMENT',
            entry_date=date(2026, 8, 21), description='One historical payment for both invoices')
        self.old_payment = JournalLine.objects.create(entry=entry, sequence=1, account=self.payable_account, debit=500)
        bank = PostingMapping.objects.get(department_id=self.accounting.pk, category=PostingMapping.BANK, source_code='gf-lbp').account
        JournalLine.objects.create(entry=entry, sequence=2, account=bank, credit=500, cash_flow_category='op_suppliers')
        submit_entry(entry, self.preparer)
        post_entry(entry, self.validator)
        self.invoice_keys = [str(uuid.UUID(int=101)), str(uuid.UUID(int=102))]
        rows = [{'source_id': source.pk, 'invoices': [{'key': key, 'party_key': f'finance-party:{self.party.code}',
            'claim_reference': f'SHARED-INVOICE-{index}', 'recognized': str(source.credit),
            'applications': {str(self.old_payment.pk): paid}}]}
            for index, (source, key, paid) in enumerate(zip(self.shared_sources, self.invoice_keys, ('300', '200')), 1)]
        self.schedule_url = reverse('accounting:shared_claim_schedule', args=[self.shared_sources[0].pk])
        self.schedule_data = {'sources': [str(s.pk) for s in self.shared_sources], 'applications': [str(self.old_payment.pk)],
            'expected_approvals': json.dumps({str(s.pk): 0 for s in self.shared_sources}), 'expected_version': '0',
            'evidence_reference': 'Synthetic reconciled original invoices and shared bank payment',
            'reason': 'Identify both original invoice credits without rewriting their shared payment', 'complete_history': 'on',
            'invoices-TOTAL_FORMS': '2', 'invoices-INITIAL_FORMS': '0'}
        for index, member in enumerate(rows):
            self.schedule_data[f'invoices-{index}-source'] = str(member['source_id'])
            invoice = member['invoices'][0]
            self.schedule_data.update({f'invoices-{index}-{field}': invoice[field]
                for field in ('key', 'party_key', 'claim_reference', 'recognized')})
            self.schedule_data[f'invoices-{index}-share_{self.old_payment.pk}'] = invoice['applications'][str(self.old_payment.pk)]
        self.client.force_login(self.preparer)
        response = self.client.post(self.schedule_url, self.schedule_data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        proposal = SharedPayableClaimProposal.objects.get()
        self.client.force_login(self.validator)
        response = self.client.post(reverse('accounting:shared_claim_review', args=[self.shared_sources[0].pk, proposal.public_id, 'approve']),
            {'note': 'Independently checked complete shared schedule'})
        self.assertEqual(response.status_code, 302)
        self.approvals = [history.current(s) for s in self.shared_sources]
        self.assertEqual({record.shared_proposal_id for record in self.approvals}, {proposal.pk})

    def rows(self, case):
        deduction = case.disbursement_voucher.deductions.first()
        return [{'source_id': source.pk, 'invoice_key': key, 'gross': gross,
            'deductions': {str(deduction.pk): withheld} if deduction else {}}
            for source, key, gross, withheld in zip(self.shared_sources, self.invoice_keys, ('600', '400'), ('40', '60'))]

    def capacities(self, **kwargs):
        return [_capacity(source, invoice_key=key, **kwargs) for source, key in zip(self.shared_sources, self.invoice_keys)]

    def test_http_selection_deductions_payment_return_reissue_and_retained_csv(self):
        case = self.case_for_validation(deductions=True)
        before = [history.serial_snapshot(s, [self.old_payment.pk]) for s in self.shared_sources]
        deduction = case.disbursement_voucher.deductions.get()
        self.client.force_login(self.validator)
        data = {'state_version': case.state_version, 'idempotency_key': 'shared-http-invoices',
            'jev_number': 'SHARED-DEDUCTIONS', 'jev_date': '2026-08-25', 'consolidated': 'on',
            'claims-TOTAL_FORMS': '2', 'claims-INITIAL_FORMS': '0'}
        for index, row in enumerate(self.rows(case)):
            data.update({f'claims-{index}-source': f"{row['source_id']}:{row['invoice_key']}",
                f'claims-{index}-gross': row['gross'], f'claims-{index}-deduction_{deduction.pk}': row['deductions'][str(deduction.pk)]})
        response = self.client.post(reverse('vouchers:case_action', args=[case.public_id, 'validate-accounting']), data)
        self.assertEqual(response.status_code, 302)
        holds = list(PayableClaimReservation.objects.filter(source__in=self.shared_sources).order_by('source_id'))
        self.assertEqual([str(hold.invoice_key) for hold in holds], self.invoice_keys)
        self.assertEqual(len(current_evidence(case)['claims']), 2)
        self.assertEqual(self.capacities(), [Decimal('900'), Decimal('600')])
        adjustment = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        self.assertEqual([line.payable_allocation['shares'] for line in adjustment.lines.filter(
            payable_origin__in=self.shared_sources).order_by('payable_origin_id')],
            [{self.invoice_keys[0]: '40.00'}, {self.invoice_keys[1]: '60.00'}])
        instrument, payment = self.pay(case)
        self.assertFalse(payment.lines.filter(account=self.expense_account).exists())
        self.assertEqual(self.capacities(), [Decimal('900'), Decimal('600')])
        first_export = self.client.get(reverse('accounting:payable_claim_export'), {'as_of': timezone.localdate().isoformat()})
        self.assertEqual(first_export.status_code, 200)
        retained = Path(self.temp) / first_export['X-GRAND-Export-Relative-Path']
        original_bytes = retained.read_bytes()
        returned = self.return_review(instrument, ReturnedInstrumentReview.REISSUE)
        reversal = self.post_request(returned.posting_request)
        self.assertEqual([line.payable_allocation for line in reversal.lines.order_by('sequence')],
            [line.payable_allocation for line in payment.lines.order_by('sequence')])
        self.pay(case, suffix='-shared-reissue', replaces=instrument)
        self.assertEqual(self.capacities(), [Decimal('900'), Decimal('600')])
        export = self.client.get(reverse('accounting:payable_claim_export'), {'as_of': timezone.localdate().isoformat()})
        selected = [row for row in csv.DictReader(io.StringIO(export.content.decode()))
            if row['claim'].startswith('SHARED-INVOICE-')]
        self.assertEqual([row['outstanding'] for row in selected], ['900.00', '600.00'])
        self.assertEqual(retained.read_bytes(), original_bytes)
        self.assertEqual([history.serial_snapshot(s, [self.old_payment.pk]) for s in self.shared_sources], before)

    def test_interrupted_validation_recovers_exact_group_without_duplicate_holds(self):
        case = self.case_for_validation()
        with patch('vouchers.services._advance', side_effect=RuntimeError('Interrupted shared handoff')):
            with self.assertRaises(RuntimeError):
                self.validate_group(case)
        before = set(PayableClaimReservation.objects.filter(source__in=self.shared_sources).values_list('public_id', flat=True))
        self.assertEqual(len(before), 2)
        self.validate_group(case)
        self.assertEqual(set(PayableClaimReservation.objects.filter(source__in=self.shared_sources).values_list('public_id', flat=True)), before)
        self.pay(case)
        self.assertEqual(self.capacities(), [Decimal('900'), Decimal('600')])

    def test_posted_deduction_correction_retains_shared_originals_and_releases_holds(self):
        case = self.case_for_validation(deductions=True)
        self.validate_group(case)
        original = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        case.refresh_from_db()
        request_correction(case=case, actor=self.preparer, correction_date=date(2026, 8, 26),
            reason='Correct shared invoice deduction amounts', expected_version=case.state_version, idempotency_key='shared-correction')
        corrected = self.post_request(case.posting_requests.get(kind=Rule.REVERSAL))
        self.assertEqual([line.payable_allocation for line in corrected.lines.order_by('sequence')],
            [line.payable_allocation for line in original.lines.order_by('sequence')])
        self.assertEqual(self.capacities(), [Decimal('1500'), Decimal('1000')])
        self.assertEqual(PayableClaimReservation.objects.filter(source__in=self.shared_sources, released_at__isnull=False).count(), 2)

    def test_partial_closing_return_retires_only_its_shares_with_recovery(self):
        case = self.case_for_validation()
        self.validate_group(case)
        keys = [row['reservation'] for row in current_evidence(case)['claims']]
        for index in (1, 2):
            case.refresh_from_db()
            issue_check(case=case, actor=self.treasury_user, bank_account_code='gf-lbp', fund_code='general-fund',
                check_number=f'SHARED-PARTIAL-{index}', amount='500', expected_version=case.state_version,
                idempotency_key=f'shared-partial-{index}', claim_payment_amounts={keys[0]: '300', keys[1]: '200'})
        paid = self.release_issued(case, 'shared')
        closing = self.return_review(paid[0][0], ReturnedInstrumentReview.CLOSE_WITHOUT_REISSUE)
        with patch('vouchers.cash_positions.resolve_instrument_exception', side_effect=RuntimeError('Interrupted shared close')):
            with self.assertRaises(RuntimeError):
                self.post_request(closing.posting_request)
        reversal = JournalEntry.objects.get(source_reference=str(closing.posting_request.public_id))
        reconcile_posted_voucher_entry(reversal, self.validator)
        self.assertEqual(PayableClaimRetirement.objects.count(), 2)
        self.assertEqual(self.capacities(), [Decimal('1200'), Decimal('800')])
        self.assertEqual(self.capacities(as_of=date(2026, 8, 25)), [Decimal('900'), Decimal('600')])

    def test_shared_entry_refresh_invalid_totals_return_and_successor_preserve_rows(self):
        self.client.force_login(self.preparer)
        response = self.client.get(reverse('accounting:claim_attribution', args=[self.shared_sources[1].pk]))
        self.assertRedirects(response, reverse('accounting:shared_claim_schedule', args=[self.shared_sources[1].pk]))
        data = dict(self.schedule_data, expected_version='1',
            expected_approvals=json.dumps({str(record.source_id): record.version for record in self.approvals}), action='refresh')
        response = self.client.post(self.schedule_url, data)
        self.assertContains(response, 'SHARED-OLD-PAYMENT')
        self.assertEqual(SharedPayableClaimProposal.objects.count(), 1)
        data['action'] = 'add_invoice'
        response = self.client.post(self.schedule_url, data)
        self.assertEqual(len(response.context['invoices'].forms), 3)
        self.assertEqual(SharedPayableClaimProposal.objects.count(), 1)
        unfinished = dict(data, complete_history='', evidence_reference='', reason='')
        response = self.client.post(self.schedule_url, unfinished)
        self.assertNotContains(response, 'This field is required.')
        response = self.client.post(self.schedule_url, dict(unfinished, action='submit'))
        self.assertContains(response, 'This field is required.')
        self.assertEqual(SharedPayableClaimProposal.objects.count(), 1)
        data.update(action='submit', **{f'invoices-0-share_{self.old_payment.pk}': '299.99'})
        response = self.client.post(self.schedule_url, data)
        self.assertContains(response, 'application in full')
        self.assertEqual(SharedPayableClaimProposal.objects.count(), 1)
        data[f'invoices-0-share_{self.old_payment.pk}'] = '300'
        self.assertEqual(self.client.post(self.schedule_url, data).status_code, 302)
        record = SharedPayableClaimProposal.objects.order_by('-pk').first()
        review_url = reverse('accounting:shared_claim_review', args=[self.shared_sources[0].pk, record.public_id, 'approve'])
        self.client.post(review_url, {'note': 'Own approval rejected'})
        self.assertFalse(record.attributions.exists())
        self.client.force_login(self.validator)
        self.client.post(reverse('accounting:shared_claim_review', args=[self.shared_sources[0].pk, record.public_id, 'return']),
            {'note': 'Check supporting document reference'})
        self.client.force_login(self.preparer)
        response = self.client.get(self.schedule_url)
        self.assertEqual(str(response.context['invoices'].forms[0]['key'].value()), self.invoice_keys[0])
        data['expected_version'] = '2'
        self.assertEqual(self.client.post(self.schedule_url, data).status_code, 302)
        self.assertEqual(SharedPayableClaimProposal.objects.order_by('-pk').first().version, 3)

    def test_shared_pages_preserve_uat_denial_and_department_boundaries(self):
        proposal = SharedPayableClaimProposal.objects.get()
        self.validator.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        self.client.force_login(self.validator)
        page = self.client.get(self.schedule_url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'Submit complete schedule for review')
        self.assertEqual(self.client.post(self.schedule_url, self.schedule_data).status_code, 403)
        self.assertEqual(self.client.post(reverse('accounting:shared_claim_review',
            args=[self.shared_sources[0].pk, proposal.public_id, 'approve']), {'note': 'Viewer cannot review'}).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.schedule_url).status_code, 403)
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='view_accounting_workspace'))
        self.assertEqual(self.client.get(self.schedule_url).status_code, 404)
