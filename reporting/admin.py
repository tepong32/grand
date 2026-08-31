from django.contrib import admin

from .models import (
    FinanceStatementLine, FinanceStatementMapping, FinanceStatementMappingEvent,
    FinanceStatementNote, FinanceStatementNoteEvent, FinanceStatementNoteSet,
    ReportDefinition, ReportReferenceComparison, ReportReferenceComparisonEvent,
    ReportRun, ReportRunEvent, ReportRunSource, ReportSchedule, ReportTemplateMappingField,
    ReportTemplatePromotion, ReportTemplatePromotionEvent, ReportTemplateVersion,
)


class FinanceStatementLineInline(admin.TabularInline):
    model = FinanceStatementLine
    extra = 0
    readonly_fields = ("position", "section_code", "section_title", "line_code", "line_title", "selector_type", "account_type", "account_codes")
    can_delete = False


@admin.register(FinanceStatementMapping)
class FinanceStatementMappingAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "statement_type", "version", "status", "reviewed_at")
    list_filter = ("department", "statement_type", "status")
    readonly_fields = ("public_id", "snapshot_checksum", "created_at", "submitted_at", "reviewed_at", "updated_at")
    inlines = (FinanceStatementLineInline,)


@admin.register(FinanceStatementMappingEvent)
class FinanceStatementMappingEventAdmin(admin.ModelAdmin):
    list_display = ("mapping", "action", "actor", "created_at")
    readonly_fields = ("mapping", "actor", "action", "reason", "snapshot", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FinanceStatementNoteInline(admin.TabularInline):
    model = FinanceStatementNote
    extra = 0
    readonly_fields = (
        "position", "topic_code", "title", "related_statement", "related_line_codes",
        "disclosure_text", "source_reference", "authority_basis", "is_not_applicable",
        "not_applicable_reason",
    )
    can_delete = False


@admin.register(FinanceStatementNoteSet)
class FinanceStatementNoteSetAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "period_end", "version", "applicability_status", "status")
    list_filter = ("department", "applicability_status", "status")
    readonly_fields = (
        "public_id", "source_snapshot", "snapshot_checksum", "created_at", "submitted_at",
        "reviewed_at", "updated_at",
    )
    inlines = (FinanceStatementNoteInline,)


@admin.register(FinanceStatementNoteEvent)
class FinanceStatementNoteEventAdmin(admin.ModelAdmin):
    list_display = ("note_set", "action", "actor", "created_at")
    readonly_fields = ("note_set", "actor", "action", "reason", "snapshot", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportReferenceComparison)
class ReportReferenceComparisonAdmin(admin.ModelAdmin):
    list_display = ("reference_label", "run", "version", "comparison_result", "status", "reviewed_at")
    list_filter = ("run__definition__department", "comparison_result", "status")
    readonly_fields = (
        "public_id", "reference_values", "generated_values_snapshot", "differences",
        "run_evidence_snapshot", "reference_file_checksum", "snapshot_checksum",
        "created_at", "submitted_at", "reviewed_at", "updated_at",
    )


@admin.register(ReportReferenceComparisonEvent)
class ReportReferenceComparisonEventAdmin(admin.ModelAdmin):
    list_display = ("comparison", "action", "actor", "created_at")
    readonly_fields = ("comparison", "actor", "action", "reason", "snapshot", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReportTemplateInline(admin.TabularInline):
    model = ReportTemplateVersion
    extra = 0
    fields = ("version", "title", "reference_kind", "fidelity_status", "is_active", "approved_at", "fidelity_validated_at")
    readonly_fields = ("is_active", "approved_at", "fidelity_validated_at")


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "dataset_key", "applicability_status", "default_format", "is_active", "updated_at")
    list_filter = ("department", "applicability_status", "is_active", "default_format")
    search_fields = ("name", "description", "slug")
    inlines = (ReportTemplateInline,)


@admin.register(ReportTemplateVersion)
class ReportTemplateVersionAdmin(admin.ModelAdmin):
    list_display = ("definition", "version", "render_mode", "reference_kind", "fidelity_status", "mapping_validated_at", "is_active", "approved_at")
    list_filter = ("definition__department", "render_mode", "reference_kind", "fidelity_status", "is_active")
    readonly_fields = (
        "is_active", "approved_by", "approved_at", "fidelity_status", "fidelity_notes",
        "fidelity_validated_by", "fidelity_validated_at", "mapping_checksum", "mapping_summary",
        "mapping_validated_by", "mapping_validated_at",
    )


@admin.register(ReportTemplateMappingField)
class ReportTemplateMappingFieldAdmin(admin.ModelAdmin):
    list_display = ("template_version", "source_key", "page_number", "x_mm", "y_mm", "repeat_for_rows", "max_rows")
    list_filter = ("template_version__definition__department", "repeat_for_rows", "alignment")


@admin.register(ReportTemplatePromotion)
class ReportTemplatePromotionAdmin(admin.ModelAdmin):
    list_display = (
        "candidate_template", "baseline_template", "status", "golden_result",
        "created_by", "reviewed_by", "activated_at",
    )
    list_filter = (
        "candidate_template__definition__department", "status", "golden_result",
        "update_compatible_schedules",
    )
    readonly_fields = (
        "public_id", "template_snapshot", "template_checksum", "mapping_diff",
        "impact_snapshot", "golden_result", "golden_snapshot", "submission_checksum",
        "created_at", "submitted_at", "reviewed_at", "activated_at", "rolled_back_at", "updated_at",
    )


@admin.register(ReportTemplatePromotionEvent)
class ReportTemplatePromotionEventAdmin(admin.ModelAdmin):
    list_display = ("promotion", "action", "actor", "created_at")
    readonly_fields = ("promotion", "actor", "action", "reason", "snapshot", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "definition", "frequency", "next_run_at", "is_active")
    list_filter = ("definition__department", "frequency", "is_active")


class ReportRunEventInline(admin.TabularInline):
    model = ReportRunEvent
    extra = 0
    readonly_fields = ("actor", "action", "from_status", "to_status", "note", "created_at")
    can_delete = False


class ReportRunSourceInline(admin.TabularInline):
    model = ReportRunSource
    extra = 0
    fields = ("source_date", "source_app", "source_model", "source_reference", "control_group", "amount")
    readonly_fields = fields
    can_delete = False
    max_num = 0


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("definition", "period_start", "period_end", "output_format", "status", "control_status", "generated_at")
    list_filter = ("definition__department", "status", "control_status", "output_format")
    search_fields = ("idempotency_key", "checksum", "dataset_checksum", "control_checksum", "reproduction_key", "public_id")
    readonly_fields = (
        "public_id", "idempotency_key", "checksum", "row_count", "dataset_snapshot",
        "dataset_checksum", "control_totals", "control_checksum", "control_status",
        "control_message", "control_gate_required", "source_record_count", "source_freshness_at",
        "reproduction_key", "generated_at", "created_at", "updated_at",
    )
    inlines = (ReportRunEventInline, ReportRunSourceInline)


@admin.register(ReportRunEvent)
class ReportRunEventAdmin(admin.ModelAdmin):
    list_display = ("run", "action", "actor", "from_status", "to_status", "created_at")
    readonly_fields = ("run", "actor", "action", "from_status", "to_status", "note", "created_at")


@admin.register(ReportRunSource)
class ReportRunSourceAdmin(admin.ModelAdmin):
    list_display = ("run", "source_date", "source_app", "source_model", "source_reference", "control_group", "amount")
    list_filter = ("run__definition__department", "source_app", "source_model", "control_group")
    search_fields = ("source_reference", "source_public_id", "source_checksum")
    readonly_fields = (
        "run", "source_app", "source_model", "source_pk", "source_public_id",
        "source_reference", "source_date", "control_group", "amount", "source_checksum",
        "source_url", "snapshot", "created_at",
    )
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
