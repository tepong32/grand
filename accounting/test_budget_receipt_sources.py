from copy import deepcopy
from datetime import date
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test.utils import CaptureQueriesContext
from vouchers import test_collection_workflow as fixtures
from vouchers.collection_corrections import propose as propose_correction
from . import budget_receipt_sources as service, budget_native_cash
from .models import Fund, JournalEntry
from reporting.models import FinanceStatementMapping as Mapping, FinanceStatementLine as MappingLine
from reporting.statement_services import submit_statement_mapping, review_statement_mapping
from .cash_classifications import checksum


class ReceiptSourceInventoryTests(fixtures.CollectionWorkflowTests):
    def setUp(self):
        super().setUp()
        self.configure_mapping()

    def configure_mapping(self):
        for actor, codes in ((self.preparer, ('view_budget_summary_actuals',)),
                             (self.validator, ('view_budget_summary_actuals',))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting', codename__in=codes))
        for actor, code in ((self.preparer, 'manage_report_definitions'), (self.validator, 'approve_reports')):
            actor.user_permissions.add(Permission.objects.get(content_type__app_label='reporting', codename=code))
        self.cash_mapping = Mapping.objects.create(department=self.accounting, statement_type=Mapping.CASH_FLOW,
            version=1, title='Synthetic explicit receipt cash inventory', authority_reference='Synthetic inventory authority',
            local_acceptance_note='Synthetic source coverage only', created_by=self.preparer)
        MappingLine.objects.create(mapping=self.cash_mapping, position=1, section_code='cash', section_title='Cash',
            line_code='cash', line_title='Cash inventory', selector_type=MappingLine.ACCOUNT_CODES,
            account_codes=[self.collection_cash.code, self.deposit_bank.code])
        submit_statement_mapping(self.cash_mapping, self.preparer)
        review_statement_mapping(self.cash_mapping, self.validator, approve=True, note='Independent explicit cash inventory review')
        self.receipt_fund = Fund.objects.get(department_id=self.accounting.pk, code='general-fund')

    def inventory(self, **changes):
        args = dict(actor=self.preparer, fund_id=self.receipt_fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
        args.update(changes); return service.capture(**args)

    def test_actual_receipt_and_deposit_retain_full_unresolved_sources_without_double_count(self):
        receipt = self.capture()
        first = self.post_source(receipt)
        deposit = self.deposit(receipt, '100', 'RECEIPT-INVENTORY-DEPOSIT')
        second = self.post_source(deposit)
        with CaptureQueriesContext(connections['finance']) as queries:
            artifact = self.inventory()
        # Mapping/account/bank reads are distinct evidence; the complete journal
        # cohort itself is the single existing Fund/posted-line SELECT.
        cohort_queries = [q for q in queries if 'posting_evidence' in q['sql'] and 'accounting_fund' in q['sql']]
        self.assertEqual(len(cohort_queries), 1)
        payload = service.verify(artifact)
        self.assertEqual(payload['controls'], dict(journals=2, lines=4,
            cash_debit='200.00', cash_credit='100.00', cash_movement='100.00', unresolved_lines=4))
        self.assertIsNone(payload['receipt_total'])
        self.assertEqual(payload['certification_status'], 'not_certified')
        self.assertEqual([r['collection']['kind'] for r in payload['journals']], ['receipt', 'deposit'])
        self.assertEqual(payload['journals'][1]['collection']['deposit_allocations'][0]['entry'], str(first.public_id))
        self.assertEqual([r['entry_id'] for r in payload['journals']], [first.pk, second.pk])
        self.assertTrue(all(r['classification_status'] == 'unresolved' for r in payload['lines']))
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            self.assertEqual(service.verify(artifact), payload)
        self.assertTrue(service.is_current(artifact, self.preparer))
        self.assertEqual(JournalEntry.objects.count(), 2)
        for original in (deposit, receipt):
            correction = propose_correction(original=original, actor=self.treasury_user,
                corrected_on=date(2026, 9, 13), reason='Synthetic exact source error correction')
            self.post_source(correction)
        corrected = service.verify(self.inventory())
        self.assertEqual(corrected['controls']['journals'], 4)
        self.assertEqual(corrected['controls']['cash_movement'], '0.00')
        self.assertIsNone(corrected['receipt_total'])
        self.assertEqual([r['collection']['kind'] for r in corrected['journals']],
            ['receipt', 'deposit', 'correction', 'correction'])
        self.assertTrue(all(r['lineage']['ancestor_ids'] for r in corrected['journals'][2:]))
        self.assertFalse(service.is_current(artifact, self.preparer))
        self.assertEqual(service.verify(artifact), payload)

    def test_missing_scope_empty_period_permission_and_tamper_never_establish_receipt_zero(self):
        empty = self.inventory()
        self.assertEqual(empty['payload']['controls']['lines'], 0)
        self.assertIsNone(empty['payload']['receipt_total'])
        with self.assertRaises(PermissionDenied):
            self.inventory(actor=self.treasury_user)
        wrong = Fund.objects.create(department_id=self.treasury.pk, department_label=self.treasury.name,
            code='FOREIGN', name='Foreign scope')
        with self.assertRaises(PermissionDenied):
            self.inventory(fund_id=wrong.pk)
        self.post_source(self.capture())
        artifact = self.inventory()
        damaged = deepcopy(artifact)
        damaged['payload']['receipt_total'] = '100.00'
        damaged['checksum'] = checksum(damaged['payload'])
        with self.assertRaises(ValidationError): service.verify(damaged)
        mapping = deepcopy(artifact['payload']['mapping']); mapping['accounts'] = mapping['accounts'][:1]
        with self.assertRaises(ValidationError):
            service.project(artifact['payload']['ledger'], mapping,
                period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
        ledger = deepcopy(artifact['payload']['ledger'])
        ledger['payload']['journals'][0]['source_snapshot']['collection_payload']['proposal']['financial_rows'][0]['debit'] = '101.00'
        ledger['checksum'] = checksum(ledger['payload'])
        ledger['evidence_checksum'] = checksum({'source_checksum': ledger['checksum'], 'captured_at': ledger['captured_at']})
        with self.assertRaisesMessage(ValidationError, 'approved collection rows'):
            service.project(ledger, artifact['payload']['mapping'],
                period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))

    def test_mapping_change_and_later_post_preserve_old_inventory(self):
        receipt = self.capture()
        self.post_source(receipt)
        artifact = self.inventory(); frozen = deepcopy(artifact)
        changed = deepcopy(artifact['payload']['mapping']); changed['reviewed_by'] += 1
        with patch.object(budget_native_cash, 'mapping_evidence', side_effect=[artifact['payload']['mapping'], changed]):
            with self.assertRaisesMessage(ValidationError, 'changed during receipt capture'):
                self.inventory()
        self.post_source(self.deposit(receipt, '100', 'SOURCE-LATER-DEPOSIT'))
        self.assertFalse(service.is_current(artifact, self.preparer))
        self.assertEqual(service.verify(artifact)['controls']['journals'], 1)
        self.assertEqual(artifact, frozen)
