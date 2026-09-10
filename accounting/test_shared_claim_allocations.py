"""One unchanged historical payment allocated across real original credits."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .claim_splits import normalize_allocations


def ledger_line(pk, debit, credit, day=1, *, reversal_of=None):
    return SimpleNamespace(pk=pk, debit=Decimal(debit), credit=Decimal(credit),
        sequence=1, account_id=7, entry_id=pk,
        entry=SimpleNamespace(entry_date=date(2026, 9, day), reversal_of_id=reversal_of,
            department_id=2, fund_id=3))


class SharedHistoricalAllocationCalculations(SimpleTestCase):
    def setUp(self):
        self.sources = [ledger_line(1, '0', '600'), ledger_line(2, '0', '400')]
        self.payment = ledger_line(3, '500', '0', 2)
        self.rows = [
            {'source_id': 1, 'invoices': [self.invoice(1, '400', '200'), self.invoice(2, '200', '100')]},
            {'source_id': 2, 'invoices': [self.invoice(3, '400', '200')]},
        ]

    def invoice(self, number, recognized, paid):
        return {'key': str(UUID(int=number)), 'party_key': 'supplier-001',
            'claim_reference': f'INV-{number}', 'recognized': recognized,
            'applications': {'3': paid}}

    def calculate(self, *, applications=None, rows=None):
        from .shared_claim_allocations import normalize_shared_allocations
        return normalize_shared_allocations(self.sources,
            applications if applications is not None else [self.payment],
            rows if rows is not None else self.rows)

    def test_existing_single_credit_contract_rejects_a_partial_shared_payment(self):
        with self.assertRaisesMessage(ValidationError, 'application in full'):
            normalize_allocations(self.sources[0], [self.payment], self.rows[0]['invoices'])

    def test_shared_payment_and_single_invoice_credit_reconcile_without_mutation(self):
        before = deepcopy((self.sources, self.payment, self.rows))
        result = self.calculate(rows=list(reversed(self.rows)))
        self.assertEqual([r['source_id'] for r in result], [1, 2])
        self.assertEqual([r['applications']['3'] for r in result], ['300.00', '200.00'])
        self.assertEqual([Decimal(invoice['recognized']) - Decimal(invoice['applications']['3'])
            for row in result for invoice in row['invoices']], [Decimal('200'), Decimal('100'), Decimal('200')])
        self.assertEqual((self.sources, self.payment, self.rows), before)

    def test_every_credit_and_every_payment_must_reconcile_exactly(self):
        for member, field, value, message in [(0, 'recognized', '399.99', 'liability credit exactly'),
                (1, 'applications', {'3': '199.99'}, 'shared historical application in full')]:
            with self.subTest(field=field):
                rows = deepcopy(self.rows)
                rows[member]['invoices'][0][field] = value
                with self.assertRaisesMessage(ValidationError, message):
                    self.calculate(rows=rows)

    def test_invoice_capacity_cannot_be_borrowed_from_another_credit(self):
        self.rows[0]['invoices'][0]['applications']['3'] = '401'
        self.rows[0]['invoices'][1]['applications']['3'] = '1'
        self.rows[1]['invoices'][0]['applications']['3'] = '98'
        with self.assertRaisesMessage(ValidationError, 'dated capacity'):
            self.calculate()

    def test_later_return_cannot_repair_earlier_shortfall(self):
        self.rows[0]['invoices'][0]['applications']['3'] = '401'
        self.rows[0]['invoices'][1]['applications']['3'] = '1'
        self.rows[1]['invoices'][0]['applications']['3'] = '98'
        for row in self.rows:
            for invoice in row['invoices']:
                invoice['applications']['4'] = invoice['applications']['3']
        with self.assertRaisesMessage(ValidationError, '2026-09-02'):
            self.calculate(applications=[self.payment, ledger_line(4, '0', '500', 4, reversal_of=3)])

    def test_return_preserves_shares_across_sources_and_invoices(self):
        returned = ledger_line(4, '0', '500', 4, reversal_of=3)
        later_payment = ledger_line(6, '500', '0', 3)
        for row in self.rows:
            for invoice in row['invoices']:
                invoice['applications']['4'] = invoice['applications']['3']
                invoice['applications']['6'] = invoice['applications']['3']
        result = self.calculate(applications=[self.payment, later_payment, returned])
        self.assertEqual([row['applications']['4'] for row in result], ['300.00', '200.00'])
        self.rows[0]['invoices'][0]['applications']['4'] = '199'
        self.rows[1]['invoices'][0]['applications']['4'] = '201'
        with self.assertRaisesMessage(ValidationError, 'exact original line'):
            self.calculate(applications=[self.payment, later_payment, returned])

    def test_each_credit_must_precede_its_own_allocated_payment(self):
        self.sources[1].entry.entry_date = date(2026, 9, 3)
        with self.assertRaisesMessage(ValidationError, 'follow recognition'):
            self.calculate()

    def test_original_credit_cancellation_keeps_its_exact_invoice_shares(self):
        # Distinct original credit lines can belong to the same historical JEV.
        self.sources[1].entry_id = self.sources[0].entry_id
        self.sources[1].sequence = 2
        returned = ledger_line(4, '0', '500', 4, reversal_of=3)
        cancelled = ledger_line(5, '400', '0', 5, reversal_of=1)
        cancelled.sequence = 2
        for row in self.rows:
            for invoice in row['invoices']:
                invoice['applications']['4'] = invoice['applications']['3']
        self.rows[1]['invoices'][0]['applications']['5'] = '400'
        result = self.calculate(applications=[self.payment, returned, cancelled])
        self.assertNotIn('5', result[0]['applications'])
        self.assertEqual(result[1]['applications']['5'], '400.00')

    def test_missing_duplicate_sources_and_foreign_application_are_rejected(self):
        for rows in [self.rows[:1], [self.rows[0], self.rows[0]]]:
            with self.subTest(rows=rows), self.assertRaisesMessage(ValidationError, 'each selected original credit once'):
                self.calculate(rows=rows)
        self.rows[1]['invoices'][0]['applications']['99'] = '1'
        with self.assertRaisesMessage(ValidationError, 'selected historical applications'):
            self.calculate()

    def test_scope_and_duplicate_invoice_identity_are_rejected(self):
        self.sources[1].entry.fund_id = 9
        with self.assertRaisesMessage(ValidationError, 'same office, fund and liability account'):
            self.calculate()
        self.sources[1].entry.fund_id = 3
        self.rows[1]['invoices'][0]['claim_reference'] = 'INV-1'
        with self.assertRaisesMessage(ValidationError, 'invoice identity only once'):
            self.calculate()


class SharedHistoricalPostedSourceTests(TestCase):
    databases = {'default', 'finance'}
    from . import test_claim_attributions as fixture_module
    setUp = fixture_module.ClaimAttributionTests.setUp
    entry = fixture_module.ClaimAttributionTests.entry
    post = fixture_module.ClaimAttributionTests.post
    legacy = fixture_module.ClaimAttributionTests.legacy
    detail = fixture_module.ClaimAttributionTests.detail
    proposal = fixture_module.ClaimAttributionTests.proposal

    def sources_and_payment(self):
        first, payment = self.legacy(payment_amount='500')
        second_entry = self.entry('SECOND-HISTORICAL-CREDIT', Decimal('800'), day=3)
        second = second_entry.lines.get(sequence=2)
        second.payable_party_key = second.payable_claim_reference = ''
        second.save()
        self.detail(second)
        self.post(second_entry)
        return first, second, payment

    def test_current_independent_approvals_cannot_share_one_payment(self):
        from .claim_attributions import review, current
        first, second, payment = self.sources_and_payment()
        approved = self.proposal(first, [payment], claim_reference='FIRST-CREDIT')
        review(approved, self.poster, approve=True, note='The existing route owns the complete line')
        with self.assertRaisesMessage(ValidationError, 'already belongs to another approved claim'):
            self.proposal(second, [payment], claim_reference='SECOND-CREDIT')
        self.assertIsNone(current(second))
        self.assertEqual(current(first).pk, approved.pk)

    def test_shared_calculation_and_return_match_ledger_without_attribution_writes(self):
        from .claim_attributions import serial_snapshot
        from .models import JournalLine, PayableClaimAttribution, PayableClaimReservation
        from .services import create_reversal
        from .shared_claim_allocations import normalize_shared_allocations
        first, second, payment = self.sources_and_payment()
        sources = [first, second]
        rows = []
        for index, (source, recognized, applied) in enumerate([(first, '1000', '300'), (second, '800', '200')], 1):
            rows.append({'source_id': source.pk, 'invoices': [{'key': str(UUID(int=index)),
                'party_key': 'supplier-001', 'claim_reference': f'SHARED-{index}', 'recognized': recognized,
                'applications': {str(payment.pk): applied}}]})

        def balance(applications):
            before = [serial_snapshot(source, [line.pk for line in applications]) for source in sources]
            result = normalize_shared_allocations(sources, applications, rows)
            outstanding = sum((sum((Decimal(invoice['recognized']) for invoice in row['invoices']), Decimal('0'))
                - sum((Decimal(row['applications'].get(str(line.pk), '0')) * (1 if line.debit else -1)
                    for line in applications), Decimal('0')) for row in result), Decimal('0'))
            actual = sum((line.credit - line.debit for line in JournalLine.objects.filter(
                account=self.accounts['payable'], entry__status='posted')), Decimal('0'))
            self.assertEqual(outstanding, actual)
            self.assertEqual([serial_snapshot(source, [line.pk for line in applications]) for source in sources], before)
            self.assertFalse(PayableClaimAttribution.objects.exists())
            self.assertFalse(PayableClaimReservation.objects.exists())
            return outstanding

        self.assertEqual(balance([payment]), Decimal('1300'))
        returned = create_reversal(payment.entry, self.maker, reference='SHARED-HISTORICAL-RETURN',
            entry_date=date(2026, 9, 6), period=self.period, reason='Synthetic exact payment return')
        self.post(returned)
        credit = returned.lines.get(sequence=payment.sequence)
        for row in rows:
            row['invoices'][0]['applications'][str(credit.pk)] = row['invoices'][0]['applications'][str(payment.pk)]
        self.assertEqual(balance([payment, credit]), Decimal('1800'))
