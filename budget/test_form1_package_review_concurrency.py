from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone
from accounting import test_budget_attribution_concurrency as race_fixtures
from . import test_form1_package_reviews as fixtures,form1_package_reviews as service
from .models import Form1PackageDecision


@skipUnless(connections['finance'].vendor=='mysql','Requires native proposal/Fund/package decision locks')
class Form1PackageReviewConcurrencyTests(TransactionTestCase):
    databases={'default','finance'}
    race=race_fixtures.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.Form1PackageReviewFixture.setUpTestData.__func__(fixtures.Form1PackageReviewFixture)
        self.factory=fixtures.Form1PackageReviewFixture(methodName='runTest')
        original_localdate=timezone.localdate
        def restore_factory():
            self.assertTrue(self.factory.doCleanups())
            self.assertIs(timezone.localdate,original_localdate)
        self.addCleanup(restore_factory)
        self.factory.setUp()

    def test_same_role_return_and_source_successor_decisions_are_serialized(self):
        factory=self.factory;record=factory.retain()
        result=self.race(lambda _: 'decided' if factory.decide_package(record) else 'missing')
        self.assertEqual(result.count('decided'),1,result)
        self.assertEqual(Form1PackageDecision.objects.filter(package=record).count(),1)
        def close(number):
            if number==1:return 'approved' if factory.decide_package(record,'accounting') else 'missing'
            return 'returned' if factory.decide_package(record,'treasury',approve=False) else 'missing'
        result=self.race(close)
        self.assertEqual(result.count('returned'),1,result)
        self.assertEqual(Form1PackageDecision.objects.filter(package=record).count(),2+result.count('approved'))
        original=service.snapshot(record,factory.treasurer)
        self.assertEqual(original['status'],'returned')
        successor=factory.retain(expected_latest=1)
        def change_source(number):
            if number==1:
                factory.prepare_forecast(expected_latest=1)
                return 'source_successor'
            return 'approved' if factory.decide_package(successor) else 'missing'
        result=self.race(change_source)
        self.assertIn('source_successor',result)
        self.assertEqual(Form1PackageDecision.objects.filter(package=successor).count(),result.count('approved'))
        self.assertEqual(service.snapshot(record,factory.treasurer),original)
