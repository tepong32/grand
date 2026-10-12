from . import test_form1_account_review_concurrency as account_races
from . import test_form1_spa_reviews as fixtures
from . import form1_spa_reviews as service
from .models import Form1SPAReview as Record
from . import test_receipt_forecast_concurrency as forecasts,form1_flows,form1_components


class Form1SPAReviewConcurrencyFixture(forecasts.ReceiptForecastConcurrencyFixture):
    prepare_resources=account_races.Form1AccountReviewConcurrencyTests.prepare_resources
    account_allocations=account_races.Form1AccountReviewConcurrencyTests.account_allocations
    setup_account_review=account_races.Form1AccountReviewConcurrencyTests.setup_account_review
    code_document=account_races.Form1AccountReviewConcurrencyTests.code_document
    prepare_accounts=account_races.Form1AccountReviewConcurrencyTests.prepare_accounts
    review_accounts=account_races.Form1AccountReviewConcurrencyTests.review_accounts
    setup_spa=fixtures.Form1SPAReviewFixture.setup_spa
    spa_inputs=fixtures.Form1SPAReviewFixture.spa_inputs
    propose_accounts=fixtures.Form1SPAReviewFixture.propose_accounts
    spa_document=fixtures.Form1SPAReviewFixture.spa_document
    prepare_spa=fixtures.Form1SPAReviewFixture.prepare_spa
    decide_spa=fixtures.Form1SPAReviewFixture.decide_spa

    def setUp(self):
        super().setUp()
        approved=self.review_forecast(self.prepare_forecast())
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=approved,actor=self.preparer))
        self.setup_account_review(); self.setup_spa()


class Form1SPAReviewConcurrencyTests(Form1SPAReviewConcurrencyFixture):

    def test_competing_spa_versions_and_conflicting_same_role_decisions_serialize(self):
        result=self.race(lambda _: 'prepared' if self.prepare_spa() else 'missing')
        self.assertEqual(result.count('prepared'),1,result)
        record=Record.objects.get()
        result=self.race(lambda number:self.decide_spa(record,approve=number==1).status)
        self.assertEqual(sum(row in ('partially_approved','returned') for row in result),1,result)
        record.refresh_from_db(); service.verify(record)
        self.assertEqual(record.decisions.count(),1)

    def test_independent_budget_and_accounting_decisions_both_survive(self):
        record=self.prepare_spa()
        result=self.race(lambda number:self.decide_spa(record,role='budget' if number==1 else 'accounting').status)
        self.assertEqual(set(result),{'partially_approved','approved'},result)
        record.refresh_from_db(); service.verify(record)
        self.assertEqual(record.decisions.count(),2)
        self.assertTrue(service.is_current(record,self.checker))

    def assert_spa_successor_race(self,successor):
        record=self.decide_spa(self.prepare_spa())
        def action(number):
            if number==1: successor(); return 'successor'
            return self.decide_spa(record,role='accounting').status
        result=self.race(action); self.assertIn('successor',result)
        record.refresh_from_db(); service.verify(record)
        self.assertEqual(record.status,'approved' if 'approved' in result else 'partially_approved')
        self.assertFalse(service.is_current(record,self.checker))

    def test_spa_successor_and_final_approval_share_proposal_lock(self):
        self.assert_spa_successor_race(lambda:self.prepare_spa(expected_latest=1))

    def test_account_successor_and_final_spa_approval_share_proposal_lock(self):
        self.assert_spa_successor_race(lambda:self.prepare_accounts(expected_latest=1))
