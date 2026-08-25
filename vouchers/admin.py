from django.contrib import admin

from .models import (
    AccountingValidation, BankAdviceBatch, BankAdviceItem, BudgetAllocationLine,
    BudgetObligation, ControlOverride, DisbursementVoucher, PaymentInstrument,
    VoucherCase, VoucherDeduction, VoucherDocumentCheck, VoucherEvent,
    VoucherLineItem, VoucherNumberIssue, VoucherOutput, VoucherTask, WetSignatureTask,
)


class BudgetAllocationInline(admin.TabularInline):
    model = BudgetAllocationLine
    extra = 0


@admin.register(BudgetObligation)
class BudgetObligationAdmin(admin.ModelAdmin):
    list_display = ("obr_number", "case", "certified_amount", "certified_by", "certified_at")
    inlines = (BudgetAllocationInline,)


@admin.register(VoucherCase)
class VoucherCaseAdmin(admin.ModelAdmin):
    list_display = ("reference_code", "payee_name", "current_stage", "current_department", "shadow_mode", "updated_at")
    list_filter = ("current_stage", "current_department", "shadow_mode")
    search_fields = ("reference_code", "payee_name", "particulars")
    readonly_fields = ("public_id", "reference_code", "state_version", "created_at", "updated_at", "completed_at", "cancelled_at")


@admin.register(VoucherEvent)
class VoucherEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "case", "action", "actor", "from_stage", "to_stage", "state_version")
    readonly_fields = tuple(field.name for field in VoucherEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (
    AccountingValidation, BankAdviceBatch, BankAdviceItem, ControlOverride,
    DisbursementVoucher, PaymentInstrument, VoucherDeduction, VoucherDocumentCheck,
    VoucherLineItem, VoucherNumberIssue, VoucherOutput, VoucherTask, WetSignatureTask,
):
    admin.site.register(model)
