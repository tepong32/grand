from django.contrib import admin

from .models import FinanceAuditEvent, FinanceConfigurationRelease, FinanceWorkflowExemption


class ReadOnlyFinanceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinanceConfigurationRelease)
class FinanceConfigurationReleaseAdmin(ReadOnlyFinanceAdmin):
    list_display = ("title", "version", "department", "fiscal_year", "status", "effective_from")
    list_filter = ("department", "status", "fiscal_year")
    search_fields = ("title", "code")


@admin.register(FinanceWorkflowExemption)
class FinanceWorkflowExemptionAdmin(admin.ModelAdmin):
    list_display = (
        "control_code", "department", "subject", "effective_from", "effective_to", "is_active", "created_by",
    )
    list_filter = ("control_code", "department", "is_active", "effective_from", "effective_to")
    search_fields = (
        "subject_user__username", "subject_user__first_name", "subject_user__last_name",
        "subject_group__name", "rationale",
    )
    readonly_fields = ("created_by", "created_at", "updated_at")
    fieldsets = (
        ("Control", {"fields": ("department", "control_code", "subject_user", "subject_group")}),
        ("Approval basis", {"fields": ("rationale", "effective_from", "effective_to", "is_active")}),
        ("Audit", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Exempt user / role")
    def subject(self, obj):
        return obj.subject_user or obj.subject_group

    def _can_manage(self, request):
        return request.user.is_superuser or request.user.has_perm("finance.manage_workflow_exemptions")

    def has_module_permission(self, request):
        return self._can_manage(request)

    def has_view_permission(self, request, obj=None):
        return self._can_manage(request)

    def has_add_permission(self, request):
        return self._can_manage(request)

    def has_change_permission(self, request, obj=None):
        return self._can_manage(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(FinanceAuditEvent)
class FinanceAuditEventAdmin(ReadOnlyFinanceAdmin):
    list_display = ("created_at", "department", "target_type", "action", "actor")
    list_filter = ("department", "target_type", "action")
    search_fields = ("target_id", "actor__username", "reason")
