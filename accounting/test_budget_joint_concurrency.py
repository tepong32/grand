from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from . import test_budget_joint_attributions as fixtures
from . import test_budget_attribution_concurrency as race_fixtures
from .budget_component_usage import component_usage
from .models import BudgetExpenditureAttribution as Attribution


@skipUnless(connections["finance"].vendor == "mysql", "Requires native Fund row locks")
class JointReviewConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = fixtures.JointAttributionTests.setUp
    entry = fixtures.JointAttributionTests.entry
    post = fixtures.JointAttributionTests.post
    rows = fixtures.JointAttributionTests.rows
    approve = fixtures.JointAttributionTests.approve
    reference = fixtures.JointAttributionTests.reference
    payment_rows = fixtures.JointAttributionTests.payment_rows
    capture = fixtures.JointAttributionTests.capture
    propose = fixtures.JointAttributionTests.propose
    reverse_and_review = fixtures.JointAttributionTests.reverse_and_review
    stale_pair = fixtures.JointAttributionTests.stale_pair
    joint = fixtures.JointAttributionTests.joint
    race = race_fixtures.BudgetAttributionConcurrencyTests.race

    def test_competing_joint_reviews_make_one_complete_decision(self):
        returned, _ = self.stale_pair()
        records = self.joint(returned)
        results = self.race(lambda _: "approved" if self.approve(records) else "missing")
        self.assertEqual(results.count("approved"), 1, results)
        self.assertTrue(any("complete pending batch" in result for result in results), results)
        decided = list(Attribution.objects.filter(batch_id=records[0].batch_id))
        self.assertEqual(len(decided), 2)
        self.assertTrue(all(record.status == "approved" for record in decided))
        self.assertEqual(len({record.reviewed_at for record in decided}), 1)
        self.assertTrue(component_usage(self.capture(), require_complete=True)["complete"])
