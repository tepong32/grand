from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounting import test_budget_attribution_concurrency as races
from . import test_form1_signed_copies as fixtures, form1_signed_copies as signed, form1_final_issues as final
from .models import Form1SignedReceipt as Receipt, Form1SignedReview as Review, Form1FinalIssue as Issue


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal/Fund/return/issue locks')
class Form1SignedConcurrencyTests(TransactionTestCase):
    databases = {'default','finance'}
    race = races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.Form1SignedFixture.setUpTestData.__func__(fixtures.Form1SignedFixture)
        self.factory = fixtures.Form1SignedFixture(methodName='runTest')
        original_localdate = timezone.localdate

        def restore():
            self.assertTrue(self.factory.doCleanups())
            self.assertIs(timezone.localdate,original_localdate)

        self.addCleanup(restore)
        self.factory.setUp()

    def test_return_review_issue_and_successor_races_keep_one_governed_history(self):
        factory = self.factory
        copy = factory.release_copy(factory.unsigned_preparation())
        result = self.race(lambda _: 'recorded' if factory.capture_return(copy) else 'missing')
        self.assertEqual(result.count('recorded'),1,result)
        self.assertEqual(Receipt.objects.filter(copy=copy).count(),1)
        first = Receipt.objects.get(copy=copy)
        result = self.race(lambda _: 'reviewed' if factory.inspect_return(first) else 'missing')
        self.assertEqual(result.count('reviewed'),1,result)
        self.assertEqual(Review.objects.filter(receipt=first).count(),1)
        result = self.race(lambda _: 'issued' if factory.issue_return(first) else 'missing')
        self.assertEqual(result.count('issued'),1,result)
        self.assertEqual(Issue.objects.count(),1)
        issued = Issue.objects.get()
        original = final.document(issued,factory.checker)
        result = self.race(lambda _: 'successor' if factory.capture_return(copy,expected_latest=1,predecessor=issued) else 'missing')
        self.assertEqual(result.count('successor'),1,result)
        second = Receipt.objects.get(copy=copy,version=2)
        factory.inspect_return(second)

        def competing_head(number):
            if number == 1:
                factory.issue_return(second)
                return 'issued'
            factory.capture_return(copy,expected_latest=2,predecessor=issued)
            return 'receipt_successor'

        result = self.race(competing_head)
        self.assertEqual(result.count('issued')+result.count('receipt_successor'),1,result)
        self.assertEqual(Issue.objects.filter(predecessor=issued).count(),result.count('issued'))
        self.assertEqual(Receipt.objects.filter(copy=copy,version=3).count(),result.count('receipt_successor'))
        head = signed._head(copy)
        latest = Receipt.objects.filter(copy=copy).order_by('-version').first()
        # A source update and a verification share the original parent lock.
        pending = factory.capture_return(copy,expected_latest=latest.version,predecessor=head)

        def source_race(number):
            if number == 1:
                factory.prepare_forecast(expected_latest=1)
                return 'source_successor'
            factory.inspect_return(pending)
            return 'reviewed'

        result = self.race(source_race)
        self.assertIn('source_successor',result)
        self.assertTrue(all(value in ('source_successor','reviewed') or 'current' in value.lower()
                            for value in result),result)
        with self.assertRaises(ValidationError): factory.issue_return(pending)
        self.assertEqual(final.document(issued,factory.checker),original)
