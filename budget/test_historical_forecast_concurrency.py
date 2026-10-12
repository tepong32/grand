from datetime import date

from .test_actuals_selection_concurrency import ActualsSelectionConcurrencyTests
from .test_actuals_complete_scope import CompleteScopeSelectionTests
from .actuals_selection import select_source
from .historical_forecasts import row_key, source_digest, save_forecast
from .planning_context import build_context
from .services import transition_version
from .models import BudgetAuditEvent


class HistoricalForecastConcurrencyTests(ActualsSelectionConcurrencyTests):
    new_proposal_account = CompleteScopeSelectionTests.new_proposal_account

    def test_competing_forecasts_and_submission_preserve_one_retained_amount(self):
        self.new_proposal_account()
        self.version = select_source(version=self.version, actor=self.preparer, fund_id=self.fund.pk,
            center_id=self.center.pk, prefix='half', kind='native', source_id=self.native.public_id,
            expected_state_version=self.version.state_version, reason='Native forecast fixture')
        row = next(item for item in build_context(self.version, self.preparer)['certified_schedule'] if not item['has_proposal'])
        args = dict(version=self.version, actor=self.preparer, key=row_key(row),
            expected_state_version=self.version.state_version, expected_source_digest=source_digest(row),
            amount='40', as_of=date(2026, 8, 1), basis='Synthetic forecast race', reason='Reviewed expectation')
        result = self.race(lambda _: 'saved' if save_forecast(**args) else 'missing')
        self.assertEqual(result.count('saved'), 1, result)
        self.assertEqual(BudgetAuditEvent.objects.filter(action='historical_forecast_saved').count(), 1)
        self.version.refresh_from_db()
        args.update(version=self.version, expected_state_version=self.version.state_version, clear=True)
        def action(number):
            if number == 1:
                transition_version(self.version, 'submit', self.preparer)
                return 'submitted'
            save_forecast(**args)
            return 'cleared'
        result = self.race(action)
        self.assertIn('submitted', result)
        self.version.refresh_from_db()
        self.assertEqual(self.version.planning_context_snapshot['historical_forecasts'], self.version.historical_forecasts)
