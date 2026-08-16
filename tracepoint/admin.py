from django.contrib import admin

from .models import (
    DailyEmployeeCredential,
    EmployeeCredentialEvent,
    PacketEvent,
    PacketHandoff,
    PacketScanSession,
    TrackedPacket,
)


class PacketEventInline(admin.TabularInline):
    model = PacketEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "action", "from_status", "to_status", "note", "metadata", "created_at")


@admin.register(TrackedPacket)
class TrackedPacketAdmin(admin.ModelAdmin):
    list_display = ("tracking_number", "title", "origin_department", "final_destination_department", "status", "current_holder", "updated_at")
    list_filter = ("origin_department", "final_destination_department", "status", "confidentiality")
    search_fields = ("tracking_number", "title", "contents_manifest")
    readonly_fields = tuple(field.name for field in TrackedPacket._meta.fields)
    inlines = (PacketEventInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PacketEvent)
class PacketEventAdmin(admin.ModelAdmin):
    list_display = ("packet", "action", "actor", "from_status", "to_status", "created_at")
    readonly_fields = ("packet", "actor", "action", "from_status", "to_status", "note", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EmployeeCredentialEventInline(admin.TabularInline):
    model = EmployeeCredentialEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "action", "note", "metadata", "created_at")


@admin.register(DailyEmployeeCredential)
class DailyEmployeeCredentialAdmin(admin.ModelAdmin):
    list_display = ("employee", "valid_on", "issued_at", "expires_at", "revoked_at", "use_count")
    list_filter = ("valid_on", "revoked_at")
    search_fields = ("employee__username", "employee__email")
    readonly_fields = tuple(field.name for field in DailyEmployeeCredential._meta.fields)
    inlines = (EmployeeCredentialEventInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmployeeCredentialEvent)
class EmployeeCredentialEventAdmin(admin.ModelAdmin):
    list_display = ("credential", "action", "actor", "created_at")
    readonly_fields = ("credential", "actor", "action", "note", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PacketScanSession)
class PacketScanSessionAdmin(admin.ModelAdmin):
    list_display = ("packet", "status", "initiated_by", "recipient", "created_at", "expires_at", "confirmed_at")
    list_filter = ("status", "created_at")
    readonly_fields = tuple(field.name for field in PacketScanSession._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PacketHandoff)
class PacketHandoffAdmin(admin.ModelAdmin):
    list_display = ("packet", "sequence", "transfer_type", "from_holder", "to_holder", "confirmed_at")
    list_filter = ("transfer_type", "to_department", "confirmed_at")
    search_fields = ("packet__tracking_number", "from_employee_name", "to_employee_name")
    readonly_fields = tuple(field.name for field in PacketHandoff._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
