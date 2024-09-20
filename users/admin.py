from django.contrib import admin
from django.db import models

from .models import User, Department, Manager, Profile, Salary



class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'is_active', 'is_staff', 'is_superuser','last_login', 'date_joined')
    fieldsets = (
        (None, {'fields': ('username', 'password', 'department', 'groups')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'middle_name', 'ext_name', 'email', )}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',)}),
    )


@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ('grade', 'amount')
    search_fields = ('grade',)
# Alternatively, you can use the simpler registration method:
# admin.site.register(Salary, SalaryAdmin)


admin.site.register(User, CustomUserAdmin)
admin.site.register(Department)
admin.site.register(Manager)
admin.site.register(Profile)

