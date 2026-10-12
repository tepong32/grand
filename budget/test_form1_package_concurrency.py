from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone
from accounting import test_budget_attribution_concurrency as race_fixtures
from . import test_form1_packages as fixtures,form1_packages as service
from .models import Form1Package


@skipUnless(connections['finance'].vendor=='mysql','Requires native proposal/Fund locks')
class Form1PackageConcurrencyTests(TransactionTestCase):
    databases={'default','finance'}
    race=race_fixtures.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        # Run the genuine source factory outside TestCase atomics so worker threads
        # can see committed original records. This runner has one fresh-store case.
        fixtures.Form1PackageFixture.setUpTestData.__func__(fixtures.Form1PackageFixture)
        self.factory=fixtures.Form1PackageFixture(methodName='runTest')
        original_localdate=timezone.localdate
        def restore_factory():
            self.assertTrue(self.factory.doCleanups())
            self.assertIs(timezone.localdate,original_localdate)
        # The manually owned TestCase has clock/settings cleanups of its own.
        # Register before setup so partial setup failure restores them as well.
        self.addCleanup(restore_factory)
        self.factory.setUp()

    def test_competing_versions_and_forecast_successor_share_original_locks(self):
        factory=self.factory
        result=self.race(lambda _: 'prepared' if factory.retain() else 'missing')
        self.assertEqual(result.count('prepared'),1,result)
        self.assertEqual(Form1Package.objects.count(),1)
        first=Form1Package.objects.get()
        original=service.snapshot(first,factory.preparer)
        def action(number):
            if number==1:
                factory.prepare_forecast(expected_latest=1)
                return 'successor'
            return 'prepared' if factory.retain(expected_latest=1) else 'missing'
        result=self.race(action)
        self.assertIn('successor',result)
        self.assertEqual(Form1Package.objects.count(),1+result.count('prepared'))
        self.assertEqual(service.snapshot(first,factory.treasurer),original)
        self.assertTrue(all(value=='prepared' or value=='successor' or 'source' in value.lower()
            or 'current' in value.lower() or 'successor' in value.lower() for value in result),result)
