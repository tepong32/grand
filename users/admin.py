from django.contrib import admin
from django.db import models

from .models import User



class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'is_active', 'is_staff', 'is_superuser','last_login', 'date_joined')
    fieldsets = (
        (None, {'fields': ('username', 'password', 'groups')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'middle_name', 'ext_name', 'email', )}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',)}),
    )





admin.site.register(User, CustomUserAdmin)