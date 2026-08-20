from django.contrib import admin

from .models import (
    FinanceAuditEvent, FinanceConfigurationItem, FinanceConfigurationRelease,
    FinanceNumberingSequence, FinanceSignatory, FinanceTemplateVersion,
)


@admin.register(FinanceConfigurationRelease)
class FinanceConfigurationReleaseAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "department", "fiscal_year", "status", "effective_from")
    list_filter = ("department", "status", "fiscal_year")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "approved_at", "activated_at")


@admin.register(FinanceConfigurationItem)
class FinanceConfigurationItemAdmin(admin.ModelAdmin):
    list_display = ("label", "category", "code", "version", "department", "status")
    list_filter = ("department", "category", "status")


admin.site.register(FinanceSignatory)
admin.site.register(FinanceNumberingSequence)
admin.site.register(FinanceTemplateVersion)


@admin.register(FinanceAuditEvent)
class FinanceAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "department", "target_type", "action", "actor")
    readonly_fields = tuple(field.name for field in FinanceAuditEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
