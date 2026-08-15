from django.contrib import admin

from .models import ReportDefinition, ReportRun, ReportRunEvent, ReportSchedule, ReportTemplateMappingField, ReportTemplateVersion


class ReportTemplateInline(admin.TabularInline):
    model = ReportTemplateVersion
    extra = 0
    fields = ("version", "title", "reference_kind", "fidelity_status", "is_active", "approved_at", "fidelity_validated_at")
    readonly_fields = ("approved_at", "fidelity_validated_at")


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "dataset_key", "default_format", "is_active", "updated_at")
    list_filter = ("department", "is_active", "default_format")
    search_fields = ("name", "description", "slug")
    inlines = (ReportTemplateInline,)


@admin.register(ReportTemplateVersion)
class ReportTemplateVersionAdmin(admin.ModelAdmin):
    list_display = ("definition", "version", "render_mode", "reference_kind", "fidelity_status", "mapping_validated_at", "is_active", "approved_at")
    list_filter = ("definition__department", "render_mode", "reference_kind", "fidelity_status", "is_active")


@admin.register(ReportTemplateMappingField)
class ReportTemplateMappingFieldAdmin(admin.ModelAdmin):
    list_display = ("template_version", "source_key", "page_number", "x_mm", "y_mm", "repeat_for_rows", "max_rows")
    list_filter = ("template_version__definition__department", "repeat_for_rows", "alignment")


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "definition", "frequency", "next_run_at", "is_active")
    list_filter = ("definition__department", "frequency", "is_active")


class ReportRunEventInline(admin.TabularInline):
    model = ReportRunEvent
    extra = 0
    readonly_fields = ("actor", "action", "from_status", "to_status", "note", "created_at")
    can_delete = False


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("definition", "period_start", "period_end", "output_format", "status", "generated_at")
    list_filter = ("definition__department", "status", "output_format")
    search_fields = ("idempotency_key", "checksum", "public_id")
    readonly_fields = ("public_id", "idempotency_key", "checksum", "row_count", "generated_at", "created_at", "updated_at")
    inlines = (ReportRunEventInline,)


@admin.register(ReportRunEvent)
class ReportRunEventAdmin(admin.ModelAdmin):
    list_display = ("run", "action", "actor", "from_status", "to_status", "created_at")
    readonly_fields = ("run", "actor", "action", "from_status", "to_status", "note", "created_at")
