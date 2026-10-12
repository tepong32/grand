from unittest import skipUnless
from django.db import connections
from django.test import TransactionTestCase

from .test_summary_actuals import SummaryActualTests
from .test_budget_attribution_concurrency import BudgetAttributionConcurrencyTests
from . import summary_actuals as services
from .models import BudgetSummaryActual as Actual, BudgetSummaryScope as Scope


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native summary locks')
class SummaryActualConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = SummaryActualTests.__dict__['employee']
    make_call = SummaryActualTests.make_call
    make_version = SummaryActualTests.make_version
    add_line = SummaryActualTests.add_line
    add_ceiling = SummaryActualTests.add_ceiling
    grant = SummaryActualTests.grant
    grant_summary = SummaryActualTests.grant_summary
    arguments = SummaryActualTests.arguments
    document = SummaryActualTests.document
    adopt = SummaryActualTests.adopt
    race = BudgetAttributionConcurrencyTests.race

    def setUp(self):
        SummaryActualTests.setUpTestData.__func__(type(self))
        SummaryActualTests.setUp(self)

    def test_competing_initial_creation_and_reviews(self):
        results = self.race(lambda _: 'created' if services.propose(**self.arguments()) else 'missing')
        self.assertEqual(results.count('created'), 1, results)
        self.assertEqual(Scope.objects.count(), 1)
        record = Actual.objects.get()
        results = self.race(lambda _: 'adopted' if self.adopt(record) else 'missing')
        self.assertEqual(results.count('adopted'), 1, results)
        record.refresh_from_db(); self.assertEqual(record.status, Actual.APPROVED)
        self.assertEqual(Scope.objects.get().current_version_id, record.pk)

    def test_successor_racing_approval_cannot_displace_newer_evidence(self):
        first = services.propose(**self.arguments())
        def action(number):
            if number == 1:
                services.propose(**self.arguments(expected_latest=1))
                return 'successor'
            self.adopt(first)
            return 'adopted'
        results = self.race(action)
        self.assertIn('successor', results)
        latest = Actual.objects.get(version=2)
        self.adopt(latest)
        self.assertEqual(Scope.objects.get().current_version_id, latest.pk)
