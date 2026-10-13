from copy import deepcopy
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from .summary_comparison import compare, compare_cohort


class SummaryComparisonTests(SimpleTestCase):
    def setUp(self):
        self.actual = {'scope': {'fund_id': 1, 'period_start': '2026-01-01', 'period_end': '2026-06-30'},
            'rows': [{'kind': 'expenditure', 'category': 'mooe', 'amount': '140.00'},
                     {'kind': 'receipt', 'category': 'service', 'amount': '1000.00'}],
            'totals': {'expenditure': '140.00'}}
        self.schedule = {'fund_id': 1, 'prior_year': 2025, 'current_year': 2026, 'budget_year': 2027,
            'rows': [{'category': 'mooe', 'half_amount': '100.00', 'prior_amount': '0.00', 'current_total': '140.00'}],
            'totals': {'half_amount': '100.00', 'prior_amount': '0.00', 'current_total': '140.00'}}

    def test_exact_half_period_exposes_false_full_year_match(self):
        before = deepcopy((self.actual, self.schedule))
        result = compare(self.actual, self.schedule)
        self.assertEqual(result['difference'], '40.00')
        self.assertEqual(result['column'], 'half_amount')
        self.assertEqual((self.actual, self.schedule), before)

    def test_prior_year_and_negative_components(self):
        self.actual['scope'].update(period_start='2025-01-01', period_end='2025-12-31')
        self.actual['rows'][0]['amount'] = '-20.00'
        self.actual['totals']['expenditure'] = '-20.00'
        result = compare(self.actual, self.schedule)
        self.assertEqual(result['column'], 'prior_amount')
        self.assertEqual(result['difference'], '-20.00')

    def test_wrong_fund_period_or_inconsistent_control_rejects(self):
        for changed in ({'fund_id': 2}, {'period_end': '2026-12-31'}, {'period_start': '2026-02-01'}):
            actual = deepcopy(self.actual); actual['scope'].update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValidationError): compare(actual, self.schedule)
        for source in (self.actual, self.schedule):
            key = 'expenditure' if source is self.actual else 'half_amount'
            source['totals'][key] = '999.00'
            with self.assertRaisesMessage(ValidationError, 'controls'): compare(self.actual, self.schedule)
            source['totals'][key] = '140.00' if source is self.actual else '100.00'

    def cohort(self):
        self.actual['scope'].update(entity_key='general', budget_department_id=10)
        first = deepcopy(self.schedule); first['office_id'] = 1
        second = deepcopy(first); second['office_id'] = 2
        second['rows'][0]['half_amount'] = second['totals']['half_amount'] = '40.00'
        return [{'proposal': 'same-proposal', 'department_id': 10, 'schedule': item} for item in (first, second)]

    def test_complete_cohort_sums_exact_period_once(self):
        forms = self.cohort(); before = deepcopy(forms)
        result = compare_cohort(self.actual, forms, expected_offices=[2,1], entity_key='general', coverage_reference='Explicit synthetic entity/office designation')
        self.assertEqual(result['difference'], '0.00')
        self.assertEqual(result['office_total'], '140.00')
        self.assertEqual(forms, before)

    def test_cohort_coverage_and_identity_failures(self):
        forms = self.cohort()
        args = dict(expected_offices=[1,2], entity_key='general', coverage_reference='Synthetic designation')
        for changes in ({'expected_offices': []}, {'expected_offices': [1,1]}, {'expected_offices': [1,2,3]},
                        {'entity_key': 'enterprise:other'}, {'coverage_reference': ''}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                compare_cohort(self.actual, forms, **(args | changes))
        with self.assertRaisesMessage(ValidationError, 'one issued version'):
            compare_cohort(self.actual, forms + [forms[0]], **args)
        for key, value in (('proposal', 'other'), ('department_id', 99)):
            changed = deepcopy(forms); changed[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError): compare_cohort(self.actual, changed, **args)
