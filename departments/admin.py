from django.contrib import admin

from .models import Department, InternalHowTo, InternalHowToStep, InternalHowToStepCompletion, Plantilla


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


class InternalHowToStepInline(admin.StackedInline):
    model = InternalHowToStep
    extra = 0
    ordering = ("position",)


@admin.register(InternalHowTo)
class InternalHowToAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "version", "required_permission", "status", "sort_order", "updated_at")
    list_filter = ("department", "status", "required_permission")
    search_fields = ("title", "summary", "slug")
    ordering = ("department", "sort_order", "title", "-version")
    inlines = (InternalHowToStepInline,)

    def _department(self, request):
        profile = getattr(request.user, "employeeprofile", None)
        return getattr(profile, "assigned_department", None)

    def _can_manage(self, request, obj=None):
        if not request.user.has_perm("departments.manage_internal_how_tos"):
            return False
        return obj is None or obj.department_id == getattr(self._department(request), "pk", None) or request.user.is_superuser

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        department = self._department(request)
        return queryset.filter(department=department) if department else queryset.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "department" and not request.user.is_superuser:
            department = self._department(request)
            kwargs["queryset"] = Department.objects.filter(pk=getattr(department, "pk", None))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_module_permission(self, request):
        return self._can_manage(request)

    def has_view_permission(self, request, obj=None):
        return self._can_manage(request, obj)

    def has_add_permission(self, request):
        return self._can_manage(request) and bool(self._department(request) or request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return self._can_manage(request, obj)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.department = self._department(request)
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InternalHowToStepCompletion)
class InternalHowToStepCompletionAdmin(admin.ModelAdmin):
    list_display = ("user", "step", "department", "completed_at")
    list_filter = ("department", "completed_at")
    search_fields = ("user__username", "step__how_to__title", "step__title")
    readonly_fields = ("user", "step", "department", "completed_at")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        profile = getattr(request.user, "employeeprofile", None)
        return queryset.filter(department=getattr(profile, "assigned_department", None))

    def has_module_permission(self, request):
        return request.user.has_perm("departments.manage_internal_how_tos")

    def has_view_permission(self, request, obj=None):
        if not request.user.has_perm("departments.manage_internal_how_tos"):
            return False
        if obj is None or request.user.is_superuser:
            return True
        profile = getattr(request.user, "employeeprofile", None)
        return obj.department_id == getattr(profile, "assigned_department_id", None)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
