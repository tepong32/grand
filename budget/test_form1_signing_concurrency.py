from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounting import test_budget_attribution_concurrency as race_fixtures
from . import test_form1_signing as fixtures, form1_signing as service
from .models import Form1SigningPreparation as Preparation, Form1SigningEvidence as Evidence, Form1SigningReview as Review


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal/Fund/package signing locks')
class Form1SigningConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    race = race_fixtures.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.Form1SigningFixture.setUpTestData.__func__(fixtures.Form1SigningFixture)
        self.factory = fixtures.Form1SigningFixture(methodName='runTest')
        original_localdate = timezone.localdate

        def restore_factory():
            self.assertTrue(self.factory.doCleanups())
            self.assertIs(timezone.localdate, original_localdate)

        self.addCleanup(restore_factory)
        self.factory.setUp()

    def test_preparation_review_and_source_successors_serialize_without_rewriting_history(self):
        factory = self.factory
        package = factory.reviewed_package()
        # Each call constructs separate upload streams, including across threads.
        result = self.race(lambda _: 'prepared' if factory.signing(package) else 'missing')
        self.assertEqual(result.count('prepared'), 1, result)
        self.assertEqual(Preparation.objects.count(), 1)
        self.assertEqual(Evidence.objects.count(), 5)
        first = Preparation.objects.get()
        result = self.race(lambda _: 'reviewed' if factory.decide_signing(first) else 'missing')
        self.assertEqual(result.count('reviewed'), 1, result)
        self.assertEqual(Review.objects.count(), 1)
        original = service.snapshot(first, factory.reviewer)

        second = factory.signing(package, expected_latest=1)

        def advance(number):
            if number == 1:
                factory.signing(package, expected_latest=2)
                return 'successor'
            factory.decide_signing(second)
            return 'reviewed'

        result = self.race(advance)
        self.assertIn('successor', result)
        self.assertEqual(Preparation.objects.count(), 3)
        self.assertEqual(Review.objects.filter(preparation=second).count(), result.count('reviewed'))
        self.assertTrue(all(value in ('successor', 'reviewed') or 'latest' in value.lower()
                            for value in result), result)
        self.assertEqual(service.snapshot(first, factory.reviewer), original)

        third = Preparation.objects.get(version=3)

        def change_source(number):
            if number == 1:
                factory.prepare_forecast(expected_latest=1)
                return 'source_successor'
            factory.decide_signing(third)
            return 'reviewed'

        result = self.race(change_source)
        self.assertIn('source_successor', result)
        self.assertEqual(Review.objects.filter(preparation=third).count(), result.count('reviewed'))
        self.assertTrue(all(value in ('source_successor', 'reviewed') or 'current' in value.lower()
                            for value in result), result)
        self.assertEqual(service.snapshot(first, factory.reviewer), original)
        self.assertEqual(Evidence.objects.count(), 15)
