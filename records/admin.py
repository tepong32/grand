from django.contrib import admin

from .models import DepartmentRecord, RecordAssociation, RecordEvent, RecordFile


class RecordAssociationInline(admin.TabularInline):
    model = RecordAssociation
    extra = 0
    readonly_fields = ("content_type", "object_id", "role", "created_by", "created_at")
    can_delete = False


class RecordFileInline(admin.TabularInline):
    model = RecordFile
    extra = 0
    readonly_fields = ("display_name", "content_type", "size_bytes", "checksum", "uploaded_by", "created_at")
    can_delete = False


class RecordEventInline(admin.TabularInline):
    model = RecordEvent
    extra = 0
    readonly_fields = ("actor", "action", "from_status", "to_status", "note", "metadata", "created_at")
    can_delete = False


@admin.register(DepartmentRecord)
class DepartmentRecordAdmin(admin.ModelAdmin):
    list_display = ("record_number", "title", "department", "classification", "confidentiality", "status", "disposition_due_date", "updated_at")
    list_filter = ("department", "classification", "confidentiality", "status", "legal_hold")
    search_fields = ("record_number", "title", "description")
    readonly_fields = tuple(field.name for field in DepartmentRecord._meta.fields)
    inlines = (RecordAssociationInline, RecordFileInline, RecordEventInline)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RecordAssociation)
class RecordAssociationAdmin(admin.ModelAdmin):
    list_display = ("record", "content_type", "object_id", "role", "created_at")
    readonly_fields = ("record", "content_type", "object_id", "role", "created_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RecordFile)
class RecordFileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "record", "size_bytes", "checksum", "uploaded_by", "created_at")
    readonly_fields = ("record", "file", "display_name", "description", "content_type", "size_bytes", "checksum", "uploaded_by", "created_at", "is_active", "superseded_by")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RecordEvent)
class RecordEventAdmin(admin.ModelAdmin):
    list_display = ("record", "action", "actor", "from_status", "to_status", "created_at")
    readonly_fields = ("record", "actor", "action", "from_status", "to_status", "note", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD") and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
