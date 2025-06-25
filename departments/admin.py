from django.contrib import admin
from .models import Department, Plantilla
# Register your models here.

from django.contrib import admin
from .models import Department

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'deptHead_or_oic']
    ordering = ['name']  # ✅ alphabetical by department name

@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    # list_display = ['title', 'item_number', 'salary_grade', 'department']
    ordering = ['title']  # ✅ alphabetical by department name

# admin.site.register(Department)
# admin.site.register(Plantilla)
