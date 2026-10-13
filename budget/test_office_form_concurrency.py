from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from accounting import test_budget_attribution_concurrency as races
from . import test_office_forms as fixtures
from . import test_actuals_selection as selection
from . import office_forms as service
from .models import BudgetOfficeForm


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal/office-form locks')
class OfficeFormConcurrencyFixture(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(selection.ActualsSelectionTests.employee.__func__)
    for name in ('make_call', 'make_version', 'add_line', 'add_ceiling', 'grant', 'attribute_grant',
                 'journal', 'capture', 'rows', 'propose', 'review', 'native_grant', 'native_propose',
                 'decide', 'choose', 'document', 'arguments', 'adopt'):
        locals()[name] = getattr(selection.ActualsSelectionTests, name)
    complete_proposal = fixtures.OfficeFormTests.complete_proposal
    form_args = fixtures.OfficeFormTests.form_args
    race = races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        selection.ActualsSelectionTests.setUpTestData.__func__(type(self))
        selection.ActualsSelectionTests.setUp(self)
        self.complete_proposal()


class OfficeFormConcurrencyTests(OfficeFormConcurrencyFixture):
    def test_competing_preparation_and_decision_retain_one_version_and_copy(self):
        args = self.form_args()
        result = self.race(lambda _: 'prepared' if service.prepare(**args) else 'missing')
        self.assertEqual(result.count('prepared'), 1, result)
        self.assertEqual(BudgetOfficeForm.objects.count(), 1)
        item = BudgetOfficeForm.objects.get()
        result = self.race(lambda _: 'issued' if service.decide(item=item, actor=self.reviewer,
            issue=True, note='Independent concurrent issuance review') else 'missing')
        self.assertEqual(result.count('issued'), 1, result)
        item.refresh_from_db()
        self.assertEqual(item.status, BudgetOfficeForm.ISSUED)
        service.verify(item)

    def test_successor_preparation_and_issuance_share_proposal_lock(self):
        item = service.prepare(**self.form_args())
        def action(number):
            if number == 1:
                service.prepare(**self.form_args(expected_latest=1))
                return 'successor'
            service.decide(item=item, actor=self.reviewer, issue=True, note='Review before a possible successor')
            return 'issued'
        result = self.race(action)
        self.assertIn('successor', result)
        item.refresh_from_db()
        if 'issued' in result:
            self.assertEqual(item.status, BudgetOfficeForm.ISSUED)
            service.verify(item)
        else:
            self.assertEqual(item.status, BudgetOfficeForm.PREPARED)
            self.assertTrue(any('newer preparation' in text for text in result), result)
