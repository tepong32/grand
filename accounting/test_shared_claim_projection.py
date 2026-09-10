"""Independent shared approval through native correction and report services."""
import csv
import io
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.db import connections
from unittest import skipUnless
from django.urls import reverse

from . import test_shared_claim_proposals as fixture_module
from . import claim_attributions as history
from .models import PayableClaimAttribution as Attribution, PayableClaimAttributionHead as Head, JournalEntry, PostingMapping
from .payables import claim_rows, _capacity
from .shared_claim_proposals import propose


class SharedClaimProjectionTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixture_module.SharedClaimProposalTests.setUp
    entry = fixture_module.SharedClaimProposalTests.entry
    post = fixture_module.SharedClaimProposalTests.post
    legacy = fixture_module.SharedClaimProposalTests.legacy
    detail = fixture_module.SharedClaimProposalTests.detail
    proposal = fixture_module.SharedClaimProposalTests.proposal
    sources_and_payment = fixture_module.SharedClaimProposalTests.sources_and_payment
    schedule = fixture_module.SharedClaimProposalTests.schedule

    def reviewed_fixture(self):
        first, second, payment, args = self.schedule()
        proposal = propose(**args)
        from .shared_claim_proposals import review
        records = review(proposal, self.poster, approve=True, note='Reconciled both original credits and payment')
        for record in records:
            self.assertGreaterEqual(record.reviewed_at, record.proposed_at)
        return first, second, payment, records

    def test_claim_capacity_csv_and_subsidiary_keep_both_payment_shares(self):
        from reporting.datasets import PostedPayableScheduleDataset
        first, second, payment, records = self.reviewed_fixture()
        before = history.serial_snapshot(first, [payment.pk])
        rows = claim_rows(self.department.pk, date(2026, 9, 5))
        self.assertEqual([row['outstanding'] for row in rows], [Decimal('700'), Decimal('600')])
        self.assertEqual([_capacity(source) for source in [first, second]], [Decimal('700'), Decimal('600')])
        details = history.projected_details(self.department.pk, date(2026, 9, 5))
        shares = [row for row in details if row.journal_line_id == payment.pk]
        self.assertEqual(sorted(row.debit for row in shares), [Decimal('200'), Decimal('300')])
        self.assertEqual({row.source_snapshot['claim_line'] for row in shares}, {first.pk, second.pk})
        PostingMapping.objects.create(**self.owner, category=PostingMapping.PAYABLE, source_code='*',
            label='Payable control', account=self.accounts['payable'])
        payload = PostedPayableScheduleDataset().payload(self.department, date(2026, 9, 1), date(2026, 9, 5), {})
        self.assertEqual(payload.control_status, 'reconciled')
        self.assertEqual(payload.control_totals['subsidiary_balance'], Decimal('1300'))
        self.assertEqual(payload.control_totals['source_line_count'], 3)
        self.assertEqual(payload.control_totals['allocation_row_count'], 4)
        self.client.force_login(self.poster)
        response = self.client.get(reverse('accounting:payable_claim_export'), {'as_of': '2026-09-05'})
        self.assertEqual(response.status_code, 200)
        exported = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual([row['outstanding'] for row in exported], ['700.00', '600.00'])
        self.assertEqual(history.serial_snapshot(first, [payment.pk]), before)

    def test_compatible_successor_retains_original_native_reversal_approval(self):
        from .shared_claim_proposals import review
        from .services import create_reversal
        first, second, payment, old = self.reviewed_fixture()
        returned = create_reversal(payment.entry, self.maker, reference='SHARED-SUCCESSOR-RETURN',
            entry_date=date(2026, 9, 6), period=self.period, reason='Actual bank return')
        self.post(returned)
        evidence = returned.lines.get(sequence=payment.sequence).payable_allocation
        args = dict(actor=self.maker, source_ids=[first.pk, second.pk], application_ids=[payment.pk],
            rows=[{'source_id': record.source_id, 'invoices': history.allocation_rows(record)} for record in old],
            expected_approvals={str(record.source_id): record.version for record in old}, expected_version=1,
            evidence_reference='Rechecked same original invoice schedule', reason='Add documentary explanation')
        newer = review(propose(**args), self.poster, approve=True, note='Same financial allocations confirmed')
        self.assertNotEqual(newer[0].pk, old[0].pk)
        self.assertEqual(history.verify(old[0]).pk, old[0].pk)
        self.assertEqual([_capacity(source) for source in [first, second]], [Decimal('1000'), Decimal('800')])
        self.assertEqual(returned.lines.get(sequence=payment.sequence).payable_allocation, evidence)
        reapplied = create_reversal(returned, self.maker, reference='SHARED-SUCCESSOR-REAPPLY',
            entry_date=date(2026, 9, 7), period=self.period, reason='Correct mistaken bank return')
        self.post(reapplied)
        self.assertEqual(reapplied.lines.get(sequence=payment.sequence).payable_allocation, evidence)
        self.assertEqual([_capacity(source) for source in [first, second]], [Decimal('700'), Decimal('600')])

    def test_incomplete_or_changed_peer_cannot_produce_a_partial_balance(self):
        first, second, payment, records = self.reviewed_fixture()
        Attribution.objects.filter(pk=records[1].pk).update(application_amounts={str(payment.pk): '199.99'})
        with self.assertRaisesMessage(ValidationError, 'complete approved schedule'):
            history.current(first)
        with self.assertRaises(ValidationError):
            history.projected_details(self.department.pk, date(2026, 9, 5))

    def test_missing_current_peer_blocks_balances_but_retains_historical_decision(self):
        first, second, payment, records = self.reviewed_fixture()
        Head.objects.filter(source=second).delete()
        self.assertEqual(history.verify(records[0]).pk, records[0].pk)
        with self.assertRaisesMessage(ValidationError, 'current shared attribution is incomplete'):
            claim_rows(self.department.pk, date(2026, 9, 5))
        with self.assertRaises(ValidationError):
            history.current(first)

    def test_standalone_review_replacement_and_first_source_lookup_are_blocked(self):
        first, second, payment, records = self.reviewed_fixture()
        with self.assertRaisesMessage(ValidationError, 'complete shared proposal'):
            history.review(records[0], self.poster, approve=True, note='One member only')
        with self.assertRaisesMessage(ValidationError, 'all members'):
            self.proposal(first, [payment], expected_version=1)
        with self.assertRaisesMessage(ValidationError, 'complete shared-source allocation'):
            history.application_origin(payment)

    def test_exact_shared_reversal_and_reversal_of_reversal_reach_all_claims_and_output(self):
        from .services import create_reversal
        from reporting.datasets import PostedPayableScheduleDataset
        first, second, payment, records = self.reviewed_fixture()
        before = history.serial_snapshot(first, [payment.pk])
        restored = create_reversal(payment.entry, self.maker, reference='SHARED-RETURN',
            entry_date=date(2026, 9, 6), period=self.period, reason='Bank returned the historical payment')
        returned_line = restored.lines.get(sequence=payment.sequence)
        self.assertEqual(restored.lines.count(), payment.entry.lines.count())
        self.assertIsNone(returned_line.payable_origin_id)
        self.assertEqual(returned_line.credit, Decimal('500'))
        self.assertEqual(set(returned_line.payable_allocation['sources']), {str(first.pk), str(second.pk)})
        self.post(restored)
        self.assertEqual([_capacity(source) for source in [first, second]], [Decimal('1000'), Decimal('800')])
        self.assertEqual([row['outstanding'] for row in claim_rows(self.department.pk, date(2026, 9, 6))],
            [Decimal('1000'), Decimal('800')])
        self.assertEqual([row['outstanding'] for row in claim_rows(self.department.pk, date(2026, 9, 5))],
            [Decimal('700'), Decimal('600')])
        PostingMapping.objects.create(**self.owner, category=PostingMapping.PAYABLE, source_code='*',
            label='Payable control', account=self.accounts['payable'])
        report = PostedPayableScheduleDataset().payload(self.department, date(2026, 9, 1), date(2026, 9, 6), {})
        self.assertEqual(report.control_status, 'reconciled')
        self.assertEqual(report.control_totals['subsidiary_balance'], Decimal('1800'))
        reapplied = create_reversal(restored, self.maker, reference='SHARED-RETURN-CORRECTED',
            entry_date=date(2026, 9, 7), period=self.period, reason='Correct the mistaken return')
        self.post(reapplied)
        self.assertEqual(reapplied.lines.get(sequence=payment.sequence).payable_allocation, returned_line.payable_allocation)
        self.assertEqual([_capacity(source) for source in [first, second]], [Decimal('700'), Decimal('600')])
        self.assertEqual(history.serial_snapshot(first, [payment.pk]), before)
        self.client.force_login(self.poster)
        response = self.client.get(reverse('accounting:payable_claim_export'), {'as_of': '2026-09-07'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['outstanding'] for row in csv.DictReader(io.StringIO(response.content.decode()))],
            ['700.00', '600.00'])
        event = restored.audit_events.get(action='posted')
        event.snapshot['invoice_allocations'] = {}
        type(event).objects.filter(pk=event.pk).update(snapshot=event.snapshot)
        with self.assertRaisesMessage(ValidationError, 'independent posting evidence'):
            _capacity(first)

    def test_shared_reversal_rejects_changed_shares_even_when_total_still_balances(self):
        from .services import create_reversal, submit_entry
        from .models import JournalLine
        first, second, payment, records = self.reviewed_fixture()
        restored = create_reversal(payment.entry, self.maker, reference='SHARED-TAMPER',
            entry_date=date(2026, 9, 6), period=self.period, reason='Return with retained sources')
        line = restored.lines.get(sequence=payment.sequence)
        sources = line.payable_allocation['sources']
        first_key = next(iter(sources[str(first.pk)]['shares']))
        second_key = next(iter(sources[str(second.pk)]['shares']))
        sources[str(first.pk)]['shares'][first_key] = '299.99'
        sources[str(second.pk)]['shares'][second_key] = '200.01'
        JournalLine.objects.filter(pk=line.pk).update(payable_allocation=line.payable_allocation)
        with self.assertRaisesMessage(ValidationError, 'exact original financial reversal'):
            submit_entry(restored, self.maker)
        restored.refresh_from_db()
        self.assertEqual(restored.status, JournalEntry.DRAFT)

    def test_reapplying_shared_payment_cannot_overdraw_one_credit_after_new_invoice_payment(self):
        from .services import create_reversal, submit_entry, post_entry
        from .claim_splits import bind_allocation
        first, second, payment, records = self.reviewed_fixture()
        returned = create_reversal(payment.entry, self.maker, reference='SHARED-RESTORE-CAPACITY',
            entry_date=date(2026, 9, 6), period=self.period, reason='Actual returned payment')
        self.post(returned)
        replacement = self.entry('NEW-INVOICE-PAYMENT', Decimal('800'), source=first, day=7)
        line = replacement.lines.get(sequence=1)
        invoice = history.allocation_rows(records[0])[0]['key']
        line.payable_allocation = bind_allocation(first, {invoice: '800.00'})
        line.save()
        self.post(replacement)
        self.assertEqual(_capacity(first), Decimal('200'))
        reapplied = create_reversal(returned, self.maker, reference='SHARED-OVERDRAW',
            entry_date=date(2026, 9, 8), period=self.period, reason='Attempt to reapply historical payment')
        submit_entry(reapplied, self.maker)
        with self.assertRaisesMessage(ValidationError, 'applications through'):
            post_entry(reapplied, self.poster)
        reapplied.refresh_from_db()
        self.assertEqual(reapplied.status, JournalEntry.SUBMITTED)
        self.assertEqual(_capacity(second), Decimal('800'))


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native MySQL row locks')
class SharedReversalConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    setUp = SharedClaimProjectionTests.setUp
    entry = SharedClaimProjectionTests.entry
    post = SharedClaimProjectionTests.post
    legacy = SharedClaimProjectionTests.legacy
    detail = SharedClaimProjectionTests.detail
    proposal = SharedClaimProjectionTests.proposal
    sources_and_payment = SharedClaimProjectionTests.sources_and_payment
    schedule = SharedClaimProjectionTests.schedule
    reviewed_fixture = SharedClaimProjectionTests.reviewed_fixture

    def test_shared_reapplication_and_new_invoice_payment_serialize_on_original_credit(self):
        from .test_claim_attribution_concurrency import ClaimAttributionConcurrencyTests
        from .services import create_reversal, submit_entry, post_entry
        from .claim_splits import bind_allocation
        first, second, payment, records = self.reviewed_fixture()
        returned = create_reversal(payment.entry, self.maker, reference='SHARED-RACE-RETURN',
            entry_date=date(2026, 9, 6), period=self.period, reason='Restore actual returned payment')
        self.post(returned)
        reapplied = create_reversal(returned, self.maker, reference='SHARED-RACE-REAPPLY',
            entry_date=date(2026, 9, 8), period=self.period, reason='Correct return')
        submit_entry(reapplied, self.maker)
        other = self.entry('SHARED-RACE-INVOICE', Decimal('800'), source=first, day=8)
        line = other.lines.get(sequence=1)
        line.payable_allocation = bind_allocation(first, {history.allocation_rows(records[0])[0]['key']: '800.00'})
        line.save()
        submit_entry(other, self.maker)
        results = ClaimAttributionConcurrencyTests.race(self, [
            lambda actor: post_entry(JournalEntry.objects.get(pk=reapplied.pk), actor),
            lambda actor: post_entry(JournalEntry.objects.get(pk=other.pk), actor)])
        self.assertTrue(any('applications through' in result for result in results), results)
        self.assertIn(_capacity(first), [Decimal('200'), Decimal('700')])
        self.assertIn(_capacity(second), [Decimal('600'), Decimal('800')])
