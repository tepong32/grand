from django.db import models
from profiles.models import EmployeeProfile

from decimal import Decimal

from .services.payroll_service import PayrollCalculator

class EmployeeSalaryDetails(models.Model):
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name="salary_details")

    # Optional overrides / additions
    rice_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    hazard_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    other_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Timestamping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_base_salary(self):
        return PayrollCalculator.resolve_base_salary(self.employee)

    def working_days_this_month(self):
        return PayrollCalculator.working_days_this_month()

    def compute_sss(self):
        breakdown = PayrollCalculator.build_breakdown(self)
        return breakdown.sss

    def compute_philhealth(self):
        breakdown = PayrollCalculator.build_breakdown(self)
        return breakdown.philhealth

    def compute_pagibig(self):
        breakdown = PayrollCalculator.build_breakdown(self)
        return breakdown.pagibig

    def compute_tax(self):
        breakdown = PayrollCalculator.build_breakdown(self)
        return breakdown.tax

    def compute_total_deductions(self):
        breakdown = PayrollCalculator.build_breakdown(self)
        return breakdown.total_deductions

    def compute_gross(self):
        return PayrollCalculator.build_breakdown(self).gross

    def compute_net_pay(self):
        return PayrollCalculator.build_breakdown(self).net

    def __str__(self):
        return f"Salary Details for {self.employee.user.get_full_name()}"
    
    
class RegOrCT_Salary(models.Model):
    """
    Salary Grade and Step mapping for Regular and Co-Terminus Employees.
    Based on DBM or Official Gazette tables.
    """
    grade = models.PositiveIntegerField()
    step = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_date = models.DateField(null=True, blank=True)  # For versioning salary tables

    class Meta:
        verbose_name = "RegOrCT Salary"
        verbose_name_plural = "RegOrCT Salaries"
        unique_together = ('grade', 'step')

    def __str__(self):
        return f"SG-{self.grade} Step-{self.step}: ₱{self.amount}"


class JO_Salary(models.Model):
    """
    Salary setup for Job Order Employees.
    Daily rate setup. Linked to EmployeeProfile.
    """
    position_title = models.CharField(max_length=100, null=True, blank=True)
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "JO Salary"
        verbose_name_plural = "JO Salaries"

    def __str__(self):
        return f"{self.position_title or 'JO'}: ₱{self.daily_rate}/day"
