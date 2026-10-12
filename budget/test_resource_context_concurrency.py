from datetime import date
from decimal import Decimal
from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from accounting.models import FundingSource
from accounting import test_budget_attribution_concurrency as races
from . import test_planning_context as fixtures
from .resource_context import save_estimate
from .services import transition_version


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal locks')
class ResourceContextConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(fixtures.PlanningContextTests.employee.__func__)
    make_call = fixtures.PlanningContextTests.make_call
    make_version = fixtures.PlanningContextTests.make_version
    add_line = fixtures.PlanningContextTests.add_line
    add_ceiling = fixtures.PlanningContextTests.add_ceiling
    race = races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.PlanningContextTests.setUpTestData.__func__(type(self))
        fixtures.PlanningContextTests.setUp(self)
        self.source = FundingSource.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, fiscal_year=self.fiscal_year, fund=self.fund,
            code='RACE-SOURCE', name='Synthetic proposed financing', effective_from=date(2027, 1, 1))

    def args(self):
        return dict(version=self.version, actor=self.preparer, funding_source=self.source,
            description='Synthetic proposed financing', amount=Decimal('50'), basis='Synthetic resource worksheet',
            expected_state_version=self.version.state_version, reason='Retain exact submitted financing')

    def test_creation_and_submission_retain_exactly_the_committed_resource_set(self):
        args = self.args()
        def action(number):
            if number == 1:
                save_estimate(**args)
                return 'saved'
            transition_version(self.version, 'submit', self.preparer)
            return 'submitted'
        result = self.race(action)
        self.assertIn('submitted', result)
        self.version.refresh_from_db()
        rows = self.version.planning_context_snapshot['resources']['rows']
        self.assertEqual(len(rows), self.version.resource_estimates.count())
        if 'saved' in result:
            self.assertEqual(rows[0]['amount'], '50.00')
        else:
            self.assertEqual(rows, [])

    def test_competing_revisions_and_submission_preserve_one_amount(self):
        item = save_estimate(**self.args())
        self.version.refresh_from_db()
        args = self.args() | {'item_id': item.pk, 'amount': Decimal('80')}
        result = self.race(lambda _: 'saved' if save_estimate(**args) else 'missing')
        self.assertEqual(result.count('saved'), 1, result)
        self.version.refresh_from_db()
        args.update(expected_state_version=self.version.state_version, amount=Decimal('90'))
        def action(number):
            if number == 1:
                save_estimate(**args)
                return 'saved'
            transition_version(self.version, 'submit', self.preparer)
            return 'submitted'
        self.assertIn('submitted', self.race(action))
        self.version.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(self.version.planning_context_snapshot['resources']['rows'][0]['amount'], str(item.amount))
