from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone
from accounting import test_budget_attribution_concurrency as races
from . import test_form1_unsigned_copies as fixtures, form1_unsigned_copies as service
from .models import Form1UnsignedCopy as Copy


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal/Fund/package/copy release locks')
class Form1UnsignedConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    race = races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.Form1UnsignedFixture.setUpTestData.__func__(fixtures.Form1UnsignedFixture)
        self.factory = fixtures.Form1UnsignedFixture(methodName='runTest')
        original_localdate = timezone.localdate

        def restore():
            self.assertTrue(self.factory.doCleanups())
            self.assertIs(timezone.localdate, original_localdate)

        self.addCleanup(restore)
        self.factory.setUp()

    def test_duplicate_release_preparation_and_source_successors_preserve_original_bytes(self):
        factory = self.factory
        first = factory.unsigned_preparation()
        result = self.race(lambda _: 'released' if factory.release_copy(first) else 'missing')
        self.assertEqual(result.count('released'), 1, result)
        self.assertEqual(Copy.objects.count(), 1)
        original_copy = Copy.objects.get()
        original = service.document(original_copy, factory.checker)
        second = factory.signing(first.package, expected_latest=1)
        factory.decide_signing(second)

        def successor(number):
            if number == 1:
                factory.signing(first.package, expected_latest=2)
                return 'successor'
            factory.release_copy(second)
            return 'released'

        result = self.race(successor)
        self.assertIn('successor', result)
        self.assertEqual(Copy.objects.filter(preparation=second).count(), result.count('released'))
        self.assertTrue(all(value in ('successor','released') or 'latest' in value.lower() for value in result), result)
        third = first.package.signing_preparations.get(version=3)
        factory.decide_signing(third)

        def source(number):
            if number == 1:
                factory.prepare_forecast(expected_latest=1)
                return 'source_successor'
            factory.release_copy(third)
            return 'released'

        result = self.race(source)
        self.assertIn('source_successor', result)
        self.assertEqual(Copy.objects.filter(preparation=third).count(), result.count('released'))
        self.assertTrue(all(value in ('source_successor','released') or 'current' in value.lower() for value in result), result)
        self.assertEqual(service.document(original_copy, factory.checker), original)
