from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from accounting import test_budget_attribution_concurrency as races
from . import test_actuals_selection as fixtures
from .services import transition_version
from .models import BudgetVersion, BudgetAuditEvent


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native proposal and Fund locks')
class ActualsSelectionConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(fixtures.ActualsSelectionTests.employee.__func__)
    make_call = fixtures.ActualsSelectionTests.make_call
    make_version = fixtures.ActualsSelectionTests.make_version
    add_line = fixtures.ActualsSelectionTests.add_line
    add_ceiling = fixtures.ActualsSelectionTests.add_ceiling
    grant = fixtures.ActualsSelectionTests.grant
    attribute_grant = fixtures.ActualsSelectionTests.attribute_grant
    journal = fixtures.ActualsSelectionTests.journal
    capture = fixtures.ActualsSelectionTests.capture
    rows = fixtures.ActualsSelectionTests.rows
    propose = fixtures.ActualsSelectionTests.propose
    review = fixtures.ActualsSelectionTests.review
    native_grant = fixtures.ActualsSelectionTests.native_grant
    native_propose = fixtures.ActualsSelectionTests.native_propose
    decide = fixtures.ActualsSelectionTests.decide
    race = races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.ActualsSelectionTests.setUpTestData.__func__(type(self))
        fixtures.ActualsSelectionTests.setUp(self)

    def test_competing_selection_and_submission_preserve_one_captured_choice(self):
        from .actuals_selection import select_source
        args = dict(version=self.version, actor=self.preparer, fund_id=self.fund.pk,
            center_id=self.center.pk, prefix='half', kind='native', source_id=self.native.public_id,
            expected_state_version=self.version.state_version, reason='Native race source selection')
        result = self.race(lambda _: 'selected' if select_source(**args) else 'missing')
        self.assertEqual(result.count('selected'), 1, result)
        self.assertEqual(BudgetAuditEvent.objects.filter(action='actuals_source_selected').count(), 1)
        self.version.refresh_from_db()
        args.update(kind='clear', source_id='', expected_state_version=self.version.state_version)
        def action(number):
            if number == 1:
                transition_version(self.version, 'submit', self.preparer)
                return 'submitted'
            select_source(**args)
            return 'cleared'
        result = self.race(action)
        self.assertIn('submitted', result)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, BudgetVersion.FOR_REVIEW)
        selected = bool(self.version.actuals_source_selection)
        retained = self.version.planning_context_snapshot['rows'][0]['half_certified']
        self.assertEqual(bool(retained), selected)
