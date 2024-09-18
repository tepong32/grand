# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin
# from .models import User

from django.contrib import admin
from django.db import models

from .models import User, Department, Manager



class BooleanListFilter(admin.SimpleListFilter):
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'is_active', 'is_staff', 'is_superuser','last_login', 'date_joined')
    fieldsets = (
        (None, {'fields': ('username', 'password', 'department', 'groups')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'middle_name', 'ext_name', 'email', )}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',)}),
    )


admin.site.register(User, CustomUserAdmin)
admin.site.register(Department)
admin.site.register(Manager)

