from django.contrib import admin
from .models import EmployeeSalaryDetails, RegOrCT_Salary, JO_Salary
# Register your models here.
admin.site.register(EmployeeSalaryDetails)
admin.site.register(RegOrCT_Salary)
admin.site.register(JO_Salary)