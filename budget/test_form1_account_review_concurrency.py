from . import test_receipt_forecast_concurrency as forecasts
from . import test_form1_account_proposals as proposals, test_form1_account_reviews as reviews
from . import form1_flows, form1_components, form1_account_reviews as service
from .models import Form1AccountReview as Record


class Form1AccountReviewConcurrencyTests(forecasts.ReceiptForecastConcurrencyFixture):
    prepare_resources = proposals.Form1AccountProposalFixture.prepare_resources
    account_allocations = proposals.Form1AccountProposalFixture.account_allocations
    setup_account_review = reviews.Form1AccountReviewFixture.setup_account_review
    code_document = reviews.Form1AccountReviewFixture.code_document
    prepare_accounts = reviews.Form1AccountReviewFixture.prepare_accounts
    review_accounts = reviews.Form1AccountReviewFixture.review_accounts

    def setUp(self):
        super().setUp()
        approved=self.review_forecast(self.prepare_forecast())
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=approved,actor=self.preparer))
        self.setup_account_review()

    def test_competing_versions_and_conflicting_accounting_decisions_serialize(self):
        result=self.race(lambda _: 'prepared' if self.prepare_accounts() else 'missing')
        self.assertEqual(result.count('prepared'),1,result)
        record=Record.objects.get()
        result=self.race(lambda number: self.review_accounts(record,approve=number==1).status)
        self.assertEqual(sum(row in ('approved','returned') for row in result),1,result)
        record.refresh_from_db(); service.verify(record)

    def assert_review_race(self, successor):
        record=self.prepare_accounts()
        def action(number):
            if number==1:
                successor()
                return 'successor'
            return self.review_accounts(record).status
        result=self.race(action)
        self.assertIn('successor',result)
        record.refresh_from_db(); service.verify(record)
        self.assertEqual(record.status,'approved' if 'approved' in result else 'prepared')
        self.assertFalse(service.is_current(record,self.checker))

    def test_pending_account_successor_and_approval_share_proposal_lock(self):
        self.assert_review_race(lambda:self.prepare_accounts(expected_latest=1))

    def test_forecast_successor_and_account_approval_share_proposal_lock(self):
        self.assert_review_race(lambda:self.prepare_forecast(expected_latest=1))

    def test_native_successor_and_account_approval_share_fund_lock(self):
        self.assert_review_race(lambda:self.make_actuals(2026,6,certify=False,expected_latest=1))
