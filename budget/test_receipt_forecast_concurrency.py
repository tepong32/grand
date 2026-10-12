"""Native forecast version/source boundaries; no inherited unit test methods."""
from .test_office_form_concurrency import OfficeFormConcurrencyFixture
from . import test_actuals_selection as selection
from .test_native_summary_reconciliation import NativeSummaryReconciliationFixture as Native
from .test_receipt_forecast_reviews import ReceiptForecastReviewFixture as Forecast
from .models import BudgetReceiptForecast as Record
from . import receipt_forecast_reviews as service, office_forms, summary_reconciliations


class ReceiptForecastConcurrencyFixture(OfficeFormConcurrencyFixture):
    prepare_resources = Forecast.prepare_resources
    component = Forecast.component
    coverage = Forecast.coverage
    inputs = Forecast.inputs
    setup_forecast = Forecast.setup_forecast
    prepare_forecast = Forecast.prepare_forecast
    review_forecast = Forecast.review_forecast
    configure_sources = Native.configure_sources
    make_actuals = Native.make_actuals
    args = Native.args
    accept = Native.accept

    def setUp(self):
        selection.ActualsSelectionTests.setUpTestData.__func__(type(self))
        selection.ActualsSelectionTests.setUp(self)
        self.prepare_resources()
        self.version.refresh_from_db()
        self.complete_proposal()
        self.form = office_forms.decide(item=office_forms.prepare(**self.form_args()), actor=self.reviewer,
            issue=True, note='Independent complete synthetic office issuance')
        self.configure_sources()
        self.setup_forecast()


class ReceiptForecastConcurrencyTests(ReceiptForecastConcurrencyFixture):
    def test_competing_versions_and_conflicting_decisions_serialize(self):
        results = self.race(lambda _: 'prepared' if self.prepare_forecast() else 'missing')
        self.assertEqual(results.count('prepared'), 1, results)
        record = Record.objects.get()
        results = self.race(lambda n: self.review_forecast(record, approve=n==1).status)
        self.assertEqual(sum(result in ('approved', 'returned') for result in results), 1, results)
        record.refresh_from_db(); service.verify(record)

    def assert_source_race(self, successor):
        record = self.prepare_forecast()
        def action(number):
            if number == 1:
                successor()
                return 'successor'
            return self.review_forecast(record).status
        results = self.race(action)
        self.assertIn('successor', results)
        record.refresh_from_db(); service.verify(record)
        self.assertFalse(service.is_current(record, self.preparer))
        self.assertEqual(record.status, 'approved' if 'approved' in results else 'prepared')

    def test_forecast_successor_and_approval_share_proposal_lock(self):
        self.assert_source_race(lambda: self.prepare_forecast(expected_latest=1))

    def test_native_successor_and_approval_share_fund_lock(self):
        self.assert_source_race(lambda: self.make_actuals(2026, 6, certify=False, expected_latest=1))

    def test_reconciliation_successor_and_approval_share_proposal_lock(self):
        self.assert_source_race(lambda: summary_reconciliations.prepare(**self.args(expected_latest=1)))

    def test_office_successor_and_approval_share_proposal_lock(self):
        self.assert_source_race(lambda: office_forms.prepare(**self.form_args(expected_latest=1)))
