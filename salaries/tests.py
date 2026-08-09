from decimal import Decimal

from django.test import SimpleTestCase

from .services.payroll_service import PayrollCalculator, PayrollComputationError


class PayrollServiceTests(SimpleTestCase):
    def test_sss_minimum_tier(self):
        self.assertEqual(PayrollCalculator.resolve_sss(Decimal("3200.00")), Decimal("135.00"))

    def test_sss_mid_tier(self):
        self.assertEqual(PayrollCalculator.resolve_sss(Decimal("10000.00")), Decimal("450.00"))

    def test_sss_max_tier(self):
        self.assertEqual(PayrollCalculator.resolve_sss(Decimal("30000.00")), Decimal("1125.00"))

    def test_pagibig_caps(self):
        self.assertEqual(PayrollCalculator.resolve_pagibig(Decimal("10000.00")), Decimal("100.00"))
        self.assertEqual(PayrollCalculator.resolve_pagibig(Decimal("1000.00")), Decimal("20.00"))

    def test_tax_banding(self):
        self.assertEqual(PayrollCalculator.resolve_tax(Decimal("20000.00")), Decimal("1833.40"))


class PayrollWorkingDaysTests(SimpleTestCase):
    def test_working_days_for_feb_2024(self):
        self.assertEqual(PayrollCalculator.working_days_this_month(2024, 2), 21)


class PayrollBuildBreakdownGuardTests(SimpleTestCase):
    def test_build_breakdown_empty_salary_raises(self):
        class DummySalaryDetails:
            other_deductions = Decimal("0.00")
            rice_allowance = Decimal("0.00")
            hazard_pay = Decimal("0.00")
            other_allowances = Decimal("0.00")

            def get_base_salary(self):
                return None

        with self.assertRaises(PayrollComputationError):
            PayrollCalculator.build_breakdown(DummySalaryDetails())
