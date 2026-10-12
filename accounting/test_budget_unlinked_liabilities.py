from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import test_budget_reviewed_components as sources
from . import test_budget_component_usage as fixtures
from .budget_reviewed_components import source_components
from . import budget_attributions as service, budget_native_sources, claim_attributions as history
from .budget_component_usage import component_usage
from .cash_classifications import checksum
from .models import ResponsibilityCenter


class UnlinkedLiabilityTests(TestCase):
    databases = {'default', 'finance'}
    entry = fixtures.ComponentUsageTests.entry
    post = fixtures.ComponentUsageTests.post
    rows = fixtures.ComponentUsageTests.rows
    approve = fixtures.ComponentUsageTests.approve
    reference = fixtures.ComponentUsageTests.reference
    capture = fixtures.ComponentUsageTests.capture
    propose = fixtures.ComponentUsageTests.propose
    principal_rows = fixtures.ComponentUsageTests.principal_rows
    reverse_and_review = fixtures.ComponentUsageTests.reverse_and_review

    def setUp(self):
        sources.ReviewedComponentTests.setUp(self)
        self.approve(self.propose())
        self.bound = source_components(self.capture(), self.source.pk)
        self.center = ResponsibilityCenter.objects.create(**self.owner, code='OFFICE', name='Synthetic office',
                                                         office_id=self.department.pk)
        self.payment = self.entry('UNLINKED-PAYMENT', Decimal('200'), source=self.source, day=4)
        line = self.payment.lines.get(sequence=1)
        line.payable_origin = None
        line.save()
        self.payment = self.post(self.payment)

    def test_unlinked_liability_cannot_claim_principal_without_source(self):
        for purpose in ('debt_principal', 'other_expenditure'):
            with self.subTest(purpose=purpose):
                rows = self.principal_rows(self.payment, '200')
                del rows[0]['claim_component']
                rows[0]['purpose'] = purpose
                with self.assertRaisesMessage(ValidationError, 'exact original liability'):
                    self.propose(rows, entry=self.payment)

    def test_historical_review_resolves_payment_without_rewriting_financial_lines(self):
        before = list(self.payment.lines.values('id', 'account_id', 'debit', 'credit', 'payable_origin_id'))
        proposal = history.propose(self.source, self.maker,
            applications=[self.payment.lines.get(sequence=1).pk],
            party_key=self.source.payable_party_key, claim_reference=self.source.payable_claim_reference,
            evidence_reference='SYN-EXACT-HISTORICAL-PAYMENT', reason='Reviewed actual original and payment',
            expected_version=0)
        history.review(proposal, self.poster, approve=True, note='Reconciled original liability and payment')
        self.approve(self.propose(version=1))
        self.bound = source_components(self.capture(), self.source.pk)
        self.approve(self.propose(self.principal_rows(self.payment, '200'), entry=self.payment))
        with CaptureQueriesContext(connections['finance']) as queries:
            retained = self.capture()
            projected = service.reviewed_allocations(retained)
            usage = component_usage(retained, require_complete=True)
        self.assertEqual(len(queries), 1)
        self.assertTrue(usage['complete'])
        self.assertEqual(before, list(self.payment.lines.values('id', 'account_id', 'debit', 'credit', 'payable_origin_id')))
        payment = next(item for item in projected if item['entry_id'] == self.payment.pk)
        self.assertEqual(sum(Decimal(row['signed_amount']) for row in payment['allocations']
                             if row['disposition'] == 'include'), Decimal('200'))
        self.reverse_and_review(self.payment, 'HISTORICAL-RETURN', 5)
        self.assertEqual(service.reviewed_allocations(retained), projected)
        current = service.reviewed_allocations(self.capture())
        self.assertEqual(sum(Decimal(row['signed_amount']) for item in current for row in item['allocations']
                             if row['disposition'] == 'include'), Decimal('0'))

    def test_unlinked_original_credit_cannot_reduce_expenditure(self):
        rows = self.rows()
        for row in rows[1:]:
            del row['claim_component_basis']
            row.update(disposition='include', purpose='debt_principal', center_id=self.center.pk, expense_class='DEBT')
        with self.assertRaisesMessage(ValidationError, 'exact original liability'):
            self.propose(rows, version=1)

    def test_explicit_exclusion_and_unresolved_review_remain_available(self):
        rows = self.principal_rows(self.payment, '200')
        del rows[0]['claim_component']
        rows[0].update(disposition='exclude', purpose='transfer', center_id=None, expense_class='',
                       basis='Explicit synthetic non-expenditure treatment for independent review')
        self.approve(self.propose(rows, entry=self.payment))
        self.assertTrue(component_usage(self.capture(), require_complete=True)['complete'])
        rows[0].update(disposition='unresolved', purpose='unresolved', basis='Awaiting exact source evidence')
        self.approve(self.propose(rows, entry=self.payment, version=1))
        self.assertFalse(component_usage(self.capture())['complete'])
        with self.assertRaises(ValidationError):
            component_usage(self.capture(), require_complete=True)

    def test_legacy_capture_remains_readable_without_authorizing_new_unlinked_expenditure(self):
        def legacy(captured):
            result = deepcopy(captured)
            result['payload']['schema'] = 6
            result['checksum'] = checksum(result['payload'])
            result['evidence_checksum'] = checksum(dict(source_checksum=result['checksum'], captured_at=result['captured_at']))
            return result
        before = legacy(self.capture())
        rows = self.principal_rows(self.payment, '200')
        del rows[0]['claim_component']
        with patch.object(budget_native_sources, 'capture', return_value=before):
            self.approve(self.propose(rows, entry=self.payment))
        current = self.capture()
        retained = legacy(current)
        frozen = deepcopy(retained)
        self.assertTrue(all(row['status'] == 'reviewed' for row in service.reviewed_allocations(retained)))
        with self.assertRaisesMessage(ValidationError, 'exact original liability'):
            service.reviewed_allocations(current)
        self.assertEqual(retained, frozen)
