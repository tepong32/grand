from django.contrib import admin

from .models import EmployeeSalaryDetails, JO_Salary, RegOrCT_Salary


@admin.register(EmployeeSalaryDetails)
class EmployeeSalaryDetailsAdmin(admin.ModelAdmin):
    list_display = [
        "employee",
        "gross",
        "other_deductions",
        "created_at",
        "updated_at",
    ]
    readonly_fields = ["gross", "updated_at"]
    ordering = ["employee__user__username"]

    @admin.display(description="Gross Salary")
    def gross(self, obj):
        return obj.compute_gross()


@admin.register(RegOrCT_Salary)
class RegOrCTSalaryAdmin(admin.ModelAdmin):
    list_display = ("grade", "step", "amount", "effective_date")
    list_filter = ("grade", "step")
    search_fields = ("grade", "step")
    ordering = ("grade", "step")


@admin.register(JO_Salary)
class JO_SalaryAdmin(admin.ModelAdmin):
    list_display = ("position_title", "daily_rate", "remarks")
    list_filter = ("position_title",)
    search_fields = ("position_title",)
    ordering = ("position_title",)




# Uncomment the following lines to register the models with custom admin classes
# @admin.register(RegOrCT_Salary)
# class RegOrCT_SalarySalaryAdmin(admin.ModelAdmin):
#     list_display = ('grade', 'step', 'amount')
#     search_fields = ('grade', 'step')
# Alternatively, you can use the simpler registration method:
# admin.site.register(RegOrCT_Salary, RegOrCT_SalaryAdmin)
