from django.contrib import admin

from .models import PacketEvent, TrackedPacket


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
