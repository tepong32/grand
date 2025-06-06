from django.contrib import admin
from .models import EmployeeSalaryDetails, RegOrCT_Salary, JO_Salary
# Register your models here.
admin.site.register(EmployeeSalaryDetails)
admin.site.register(RegOrCT_Salary)
admin.site.register(JO_Salary)




# Uncomment the following lines to register the models with custom admin classes
# @admin.register(RegOrCT_Salary)
# class RegOrCT_SalarySalaryAdmin(admin.ModelAdmin):
#     list_display = ('grade', 'step', 'amount')
#     search_fields = ('grade', 'step')
# Alternatively, you can use the simpler registration method:
# admin.site.register(RegOrCT_Salary, RegOrCT_SalaryAdmin)