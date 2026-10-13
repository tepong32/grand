from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounting import test_budget_attribution_concurrency as race_fixtures
from . import test_form1_treatments as fixtures, form1_treatments as service
from .models import Form1TreatmentProposal, Form1TreatmentDecision


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal/Fund/treatment locks')
class Form1TreatmentConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    race = race_fixtures.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.Form1TreatmentTests.setUpTestData.__func__(fixtures.Form1TreatmentTests)
        self.factory = fixtures.Form1TreatmentTests(methodName='runTest')
        original_localdate = timezone.localdate

        def restore():
            self.assertTrue(self.factory.doCleanups())
            self.assertIs(timezone.localdate, original_localdate)

        self.addCleanup(restore)
        self.factory.setUp()

    def test_versions_roles_returns_and_source_successors_are_serialized(self):
        factory = self.factory
        package = factory.retain_original_package()
        result = self.race(lambda _: 'prepared' if factory.prepare_treatment(package) else 'missing')
        self.assertEqual(result.count('prepared'), 1, result)
        self.assertEqual(Form1TreatmentProposal.objects.filter(package=package).count(), 1)
        proposal = Form1TreatmentProposal.objects.get(package=package)
        result = self.race(lambda _: 'reviewed' if factory.decide_treatment(proposal) else 'missing')
        self.assertEqual(result.count('reviewed'), 1, result)
        self.assertEqual(Form1TreatmentDecision.objects.filter(proposal=proposal).count(), 1)

        def close(number):
            if number == 1:
                return 'approved' if factory.decide_treatment(proposal, 'accounting') else 'missing'
            return 'returned' if factory.decide_treatment(proposal, 'treasury', approve=False) else 'missing'

        result = self.race(close)
        self.assertEqual(result.count('returned'), 1, result)
        self.assertEqual(Form1TreatmentDecision.objects.filter(proposal=proposal).count(), 2+result.count('approved'))
        original = service.snapshot(proposal, factory.treasurer)
        self.assertEqual(original['review']['status'], 'returned')
        successor = factory.prepare_treatment(package, expected_latest=1)

        def change_source(number):
            if number == 1:
                factory.prepare_forecast(expected_latest=1)
                return 'source_successor'
            return 'reviewed' if factory.decide_treatment(successor) else 'missing'

        result = self.race(change_source)
        self.assertIn('source_successor', result)
        self.assertEqual(Form1TreatmentDecision.objects.filter(proposal=successor).count(), result.count('reviewed'))
        self.assertEqual(service.snapshot(proposal, factory.treasurer), original)
        self.assertFalse(original['review']['numeric_adjustment_approved'])
