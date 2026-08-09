from django.contrib import admin

from .models import Department, Plantilla


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "email", "phone", "deptHead_or_oic", "dashboard_template"]
    search_fields = ["name", "slug", "email", "phone"]
    list_filter = ["deptHead_or_oic", "slug"]
    ordering = ["name"]


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ["title", "item_number", "salary_grade", "department"]
    search_fields = ["title", "item_number", "department__name"]
    list_filter = ["department"]
    ordering = ["title"]
