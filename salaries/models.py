from django.db import models
from profiles.models import EmployeeProfile

from decimal import Decimal

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
        emp = self.employee
        if emp.employment_type in [emp.REG, emp.CT] and emp.reg_or_ct_salary:
            return emp.reg_or_ct_salary.amount
        elif emp.employment_type == emp.JO and emp.jo_salary:
            return emp.jo_salary.daily_rate * Decimal(self.working_days_this_month())
        return Decimal('0.00')

    def working_days_this_month(self):
        # Temporary hardcoded fallback
        return 22  # common LGU assumption; replace with actual computation later

    def compute_sss(self):
        salary = self.get_base_salary()
        if salary < 3250:
            return Decimal('135.00')
        elif salary >= 24750:
            return Decimal('1125.00')
        else:
            return round(salary * Decimal('0.045'), 2)

    def compute_philhealth(self):
        salary = self.get_base_salary()
        base = max(min(salary, Decimal('100000')), Decimal('10000'))
        return round(base * Decimal('0.025'), 2)

    def compute_pagibig(self):
        salary = self.get_base_salary()
        contribution = salary * Decimal('0.02')
        return min(Decimal('100.00'), round(contribution, 2))

    def compute_tax(self):
        salary = self.get_base_salary()
        if salary <= 20833:
            return Decimal('0.00')
        elif salary <= 33332:
            return round((salary - 20833) * Decimal('0.20'), 2)
        elif salary <= 66666:
            return round(2500 + (salary - 33333) * Decimal('0.25'), 2)
        elif salary <= 166666:
            return round(10833 + (salary - 66667) * Decimal('0.30'), 2)
        else:
            return round(40833 + (salary - 166667) * Decimal('0.32'), 2)

    def compute_total_deductions(self):
        return sum([
            self.compute_sss(),
            self.compute_philhealth(),
            self.compute_pagibig(),
            self.compute_tax(),
            self.other_deductions
        ])

    def compute_gross(self):
        return self.get_base_salary() + self.rice_allowance + self.hazard_pay + self.other_allowances

    def compute_net_pay(self):
        return self.compute_gross() - self.compute_total_deductions()

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