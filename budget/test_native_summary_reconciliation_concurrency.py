"""Native locks serialize reconciliation and selected source successors."""
from .test_office_form_concurrency import OfficeFormConcurrencyFixture
from .test_native_summary_reconciliation import NativeSummaryReconciliationTests as Fixtures
from . import office_forms, summary_reconciliations as service
from .models import BudgetSummaryReconciliation as Record


class NativeSummaryReconciliationConcurrencyTests(OfficeFormConcurrencyFixture):
    configure_sources = Fixtures.configure_sources
    make_actuals = Fixtures.make_actuals
    args = Fixtures.args
    accept = Fixtures.accept

    def setUp(self):
        super().setUp()
        self.form = office_forms.decide(item=office_forms.prepare(**self.form_args()),
            actor=self.reviewer, issue=True, note='Independent complete synthetic office issue')
        self.configure_sources()

    def test_native_preparation_and_conflicting_decisions_serialize(self):
        result = self.race(lambda _: 'prepared' if service.prepare(**self.args()) else 'missing')
        self.assertEqual(result.count('prepared'), 1, result)
        record = Record.objects.get()
        result = self.race(lambda number: 'accepted' if self.accept(record, accept=number==1).status=='accepted' else 'returned')
        self.assertEqual(sum(value in ('accepted', 'returned') for value in result), 1, result)
        record.refresh_from_db(); service.verify(record)

    def test_native_successor_and_acceptance_share_fund_lock(self):
        record = service.prepare(**self.args())
        def action(number):
            if number==1:
                self.make_actuals(2026,6,certify=False,expected_latest=1)
                return 'successor'
            self.accept(record)
            return 'accepted'
        result = self.race(action)
        self.assertIn('successor', result)
        record.refresh_from_db()
        if 'accepted' in result:
            self.assertEqual(record.status, 'accepted')
        else:
            self.assertEqual(record.status, 'prepared')
            self.assertTrue(any('stale' in value for value in result), result)
        service.verify(record)

    def test_office_successor_and_acceptance_share_proposal_lock(self):
        record = service.prepare(**self.args())
        def action(number):
            if number==1:
                office_forms.prepare(**self.form_args(expected_latest=1))
                return 'successor'
            self.accept(record)
            return 'accepted'
        result = self.race(action)
        self.assertIn('successor', result)
        record.refresh_from_db()
        if 'accepted' in result:
            self.assertEqual(record.status, 'accepted')
        else:
            self.assertEqual(record.status, 'prepared')
            self.assertTrue(any('newer office' in value for value in result), result)
        service.verify(record)
