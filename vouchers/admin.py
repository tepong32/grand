from django.contrib import admin

from .models import VoucherCase, VoucherEvent, VoucherNonFinancialAmendment


class ReadOnlyWorkflowAdmin(admin.ModelAdmin):
    """Keep support evidence inspectable without exposing workflow CRUD."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VoucherCase)
class VoucherCaseAdmin(ReadOnlyWorkflowAdmin):
    list_display = (
        "reference_code", "payee_name", "current_stage", "current_department",
        "shadow_mode", "updated_at",
    )
    list_filter = ("current_stage", "current_department", "shadow_mode")
    search_fields = ("reference_code", "payee_name", "particulars")


@admin.register(VoucherEvent)
class VoucherEventAdmin(ReadOnlyWorkflowAdmin):
    list_display = (
        "created_at", "case", "action", "actor", "from_stage", "to_stage", "state_version",
    )
    list_filter = ("action", "from_stage", "to_stage")
    search_fields = ("case__reference_code", "actor__username", "reason")


@admin.register(VoucherNonFinancialAmendment)
class VoucherNonFinancialAmendmentAdmin(ReadOnlyWorkflowAdmin):
    list_display = (
        "case", "version", "old_voucher_date", "new_voucher_date",
        "status", "amended_by", "amended_at",
    )
    list_filter = ("status",)
    search_fields = ("case__reference_code", "reason")
