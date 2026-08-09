from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal as D
from typing import Optional

from calendar import monthrange

from profiles.models import EmployeeProfile


class PayrollComputationError(ValueError):
    """Raised when payroll inputs are invalid or incomplete."""


class PayrollConstants:
    REGULAR_EMPLOYEE = "REG"
    CO_TERMINUS_EMPLOYEE = "CT"
    JOB_ORDER = "JO"

    SSS_RATE = D("0.045")
    PHILHEALTH_RATE = D("0.025")
    PAGIBIG_RATE = D("0.02")
    SSS_MINIMUM_WAGE = D("3250.00")
    SSS_MAXIMUM_WAGE = D("24750.00")
    PAGIBIG_MAXIMUM = D("100.00")

    DEFAULT_WORKING_DAYS = 22


@dataclass(frozen=True)
class PayrollAmounts:
    gross: D
    sss: D
    philhealth: D
    pagibig: D
    tax: D
    total_deductions: D
    net: D


class PayrollCalculator:
    @staticmethod
    def _to_decimal(value) -> D:
        if value is None:
            return D("0.00")
        if isinstance(value, D):
            return value
        return D(str(value))

    @staticmethod
    def working_days_this_month(year: Optional[int] = None, month: Optional[int] = None) -> int:
        """
        Return weekday-count-based business days for the current month.
        """
        today = date.today()
        year = year or today.year
        month = month or today.month
        _, num_days = monthrange(year, month)

        working_days = 0
        for day in range(1, num_days + 1):
            weekday = date(year, month, day).weekday()  # Monday=0..Sunday=6
            if weekday < 5:
                working_days += 1

        return working_days or PayrollConstants.DEFAULT_WORKING_DAYS

    @staticmethod
    def resolve_base_salary(employee: EmployeeProfile) -> D:
        if employee.employment_type in {
            PayrollConstants.REGULAR_EMPLOYEE,
            PayrollConstants.CO_TERMINUS_EMPLOYEE,
        }:
            if not employee.reg_or_ct_salary:
                return D("0.00")
            return PayrollCalculator._to_decimal(employee.reg_or_ct_salary.amount)

        if employee.employment_type == PayrollConstants.JOB_ORDER:
            if not employee.jo_salary:
                return D("0.00")
            daily_rate = PayrollCalculator._to_decimal(employee.jo_salary.daily_rate)
            return daily_rate * D(str(PayrollConstants.DEFAULT_WORKING_DAYS))

        return D("0.00")

    @staticmethod
    def resolve_sss(base_salary: D) -> D:
        base_salary = PayrollCalculator._to_decimal(base_salary)
        if base_salary < PayrollConstants.SSS_MINIMUM_WAGE:
            return D("135.00")
        if base_salary >= PayrollConstants.SSS_MAXIMUM_WAGE:
            return D("1125.00")
        return (base_salary * PayrollConstants.SSS_RATE).quantize(D("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def resolve_philhealth(base_salary: D) -> D:
        base_salary = PayrollCalculator._to_decimal(base_salary)
        bounded = max(min(base_salary, D("100000.00")), D("10000.00"))
        return (bounded * PayrollConstants.PHILHEALTH_RATE).quantize(D("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def resolve_pagibig(base_salary: D) -> D:
        base_salary = PayrollCalculator._to_decimal(base_salary)
        computed = (base_salary * PayrollConstants.PAGIBIG_RATE).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        return min(PayrollConstants.PAGIBIG_MAXIMUM, computed)

    @staticmethod
    def resolve_tax(base_salary: D) -> D:
        salary = PayrollCalculator._to_decimal(base_salary)
        if salary <= 20833:
            return D("0.00")
        if salary <= 33332:
            return ((salary - 20833) * D("0.20")).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        if salary <= 66666:
            return (D("2500") + (salary - 33333) * D("0.25")).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        if salary <= 166666:
            return (D("10833") + (salary - 66667) * D("0.30")).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        return (D("40833") + (salary - 166667) * D("0.32")).quantize(D("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def build_breakdown(employee_salary_details, working_days: Optional[int] = None) -> PayrollAmounts:
        base_salary = employee_salary_details.get_base_salary()
        if base_salary is None:
            raise PayrollComputationError("Cannot compute payroll without salary")

        other_deductions = PayrollCalculator._to_decimal(getattr(employee_salary_details, "other_deductions", D("0.00")))
        rice_allowance = PayrollCalculator._to_decimal(getattr(employee_salary_details, "rice_allowance", D("0.00")))
        hazard_pay = PayrollCalculator._to_decimal(getattr(employee_salary_details, "hazard_pay", D("0.00")))
        other_allowances = PayrollCalculator._to_decimal(getattr(employee_salary_details, "other_allowances", D("0.00")))

        gross = base_salary + rice_allowance + hazard_pay + other_allowances
        sss = PayrollCalculator.resolve_sss(base_salary)
        philhealth = PayrollCalculator.resolve_philhealth(base_salary)
        pagibig = PayrollCalculator.resolve_pagibig(base_salary)
        tax = PayrollCalculator.resolve_tax(base_salary)
        total_deductions = sss + philhealth + pagibig + tax + other_deductions
        net = gross - total_deductions

        return PayrollAmounts(
            gross=gross.quantize(D("0.01"), rounding=ROUND_HALF_UP),
            sss=sss,
            philhealth=philhealth,
            pagibig=pagibig,
            tax=tax,
            total_deductions=total_deductions.quantize(D("0.01"), rounding=ROUND_HALF_UP),
            net=net.quantize(D("0.01"), rounding=ROUND_HALF_UP),
        )
