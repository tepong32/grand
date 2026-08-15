from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from departments.models import Department


REFERENCE_EXTENSIONS = ("pdf", "xlsx", "xls", "docx", "png", "jpg", "jpeg")
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg")


def report_reference_path(instance, filename):
    return f"reporting/references/{instance.definition.department.slug}/{instance.definition.slug}/v{instance.version}/{filename}"


def report_output_path(instance, filename):
    return f"reporting/outputs/{instance.definition.department.slug}/{instance.definition.slug}/{filename}"


def report_identity_path(instance, filename):
    return f"reporting/identity/{instance.definition.department.slug}/{instance.definition.slug}/v{instance.version}/{filename}"


class ReportDefinition(models.Model):
    FORMAT_PDF = "pdf"
    FORMAT_XLSX = "xlsx"
    FORMAT_CSV = "csv"
    FORMAT_CHOICES = ((FORMAT_PDF, "PDF"), (FORMAT_XLSX, "Excel workbook"), (FORMAT_CSV, "CSV"))

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="report_definitions")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True)
    dataset_key = models.CharField(max_length=80)
    selected_fields = models.JSONField(default=list)
    filters = models.JSONField(default=dict, blank=True)
    group_by = models.JSONField(default=list, blank=True)
    totals = models.JSONField(default=list, blank=True)
    sort_by = models.JSONField(default=list, blank=True)
    default_format = models.CharField(max_length=8, choices=FORMAT_CHOICES, default=FORMAT_PDF)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_report_definitions")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_report_definitions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(fields=("department", "slug"), name="unique_report_slug_per_department"),
        )
        permissions = (
            ("view_reporting_workspace", "Can access the department reporting workspace"),
            ("manage_report_definitions", "Can configure report definitions"),
            ("manage_report_templates", "Can manage official report templates"),
            ("schedule_reports", "Can schedule recurring reports"),
            ("generate_reports", "Can generate department reports"),
            ("review_reports", "Can review generated reports"),
            ("approve_reports", "Can approve official reports"),
            ("download_reports", "Can download generated reports"),
            ("view_department_reports", "Can view all reports in the assigned department"),
        )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("reporting:definition_detail", kwargs={"pk": self.pk})

    @property
    def current_template(self):
        return self.template_versions.filter(is_active=True, approved_at__isnull=False).order_by("-version").first()

    @property
    def dataset_label(self):
        from .datasets import dataset_registry
        adapter = dataset_registry.get(self.dataset_key)
        return adapter.label if adapter else self.dataset_key

    def clean(self):
        from .datasets import dataset_registry

        adapter = dataset_registry.get(self.dataset_key)
        if not adapter:
            raise ValidationError({"dataset_key": "Select an approved application dataset."})
        if not adapter.supports_department(self.department):
            raise ValidationError({"dataset_key": "This approved dataset is not available to the selected department."})
        allowed = set(adapter.column_keys)
        selected = self.selected_fields or []
        json_lists = {"selected_fields": selected, "group_by": self.group_by or [], "totals": self.totals or [], "sort_by": self.sort_by or []}
        for field_name, values in json_lists.items():
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ValidationError({field_name: "Choose fields from the approved dataset list."})
        invalid = set(selected) - allowed
        if not selected:
            raise ValidationError({"selected_fields": "Select at least one approved field."})
        if invalid:
            raise ValidationError({"selected_fields": f"Unsupported fields: {', '.join(sorted(invalid))}."})
        for field_name in ("group_by", "totals", "sort_by"):
            values = getattr(self, field_name) or []
            if set(value.lstrip("-") for value in values) - allowed:
                raise ValidationError({field_name: "Only approved dataset fields may be used."})
        if not isinstance(self.filters, dict):
            raise ValidationError({"filters": "Filters must be a controlled key/value mapping."})
        for filter_key, value in self.filters.items():
            parts = filter_key.split("__", 1)
            if parts[0] not in allowed or (len(parts) == 2 and parts[1] not in ("exact", "contains", "in")):
                raise ValidationError({"filters": f"Unsupported filter: {filter_key}."})
            if isinstance(value, (dict, list)) and not (filter_key.endswith("__in") and isinstance(value, list)):
                raise ValidationError({"filters": "Filter values must be text, numbers, or a list used with the 'in' operator."})
        if self.group_by and set(self.group_by) - set(selected):
            raise ValidationError({"group_by": "Grouped fields must also be included in the report."})
        if self.totals and set(self.totals) - set(selected):
            raise ValidationError({"totals": "Totaled fields must also be included in the report."})
        if self.group_by and set(selected) - set(self.group_by) - set(self.totals):
            raise ValidationError({"group_by": "When grouping is enabled, every included field must be either a grouping field or a numeric total."})


class ReportTemplateVersion(models.Model):
    REFERENCE_NONE = "none"
    REFERENCE_PDF = "pdf"
    REFERENCE_XLSX = "xlsx"
    REFERENCE_DOCX = "docx"
    REFERENCE_IMAGE = "image"
    REFERENCE_CHOICES = (
        (REFERENCE_NONE, "No uploaded reference"),
        (REFERENCE_PDF, "PDF form or layout"),
        (REFERENCE_XLSX, "Spreadsheet layout"),
        (REFERENCE_DOCX, "Word document layout"),
        (REFERENCE_IMAGE, "Scanned or image reference"),
    )

    PILOT = "pilot"
    OFFICIAL = "official"
    FIDELITY_CHOICES = (
        (PILOT, "Pilot - internal comparison only"),
        (OFFICIAL, "Department-validated official layout"),
    )
    PAGE_A4 = "a4"
    PAGE_LETTER = "letter"
    PAGE_LEGAL = "legal"
    PAGE_SIZE_CHOICES = ((PAGE_A4, "A4"), (PAGE_LETTER, "Letter"), (PAGE_LEGAL, "Legal"))
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    ORIENTATION_CHOICES = ((PORTRAIT, "Portrait"), (LANDSCAPE, "Landscape"))
    BORDER_NONE = "none"
    BORDER_SINGLE = "single"
    BORDER_CHOICES = ((BORDER_NONE, "No page border"), (BORDER_SINGLE, "Single page border"))
    RENDER_NATIVE = "native"
    RENDER_XLSX_TEMPLATE = "xlsx_template"
    RENDER_PDF_OVERLAY = "pdf_overlay"
    RENDER_MODE_CHOICES = (
        (RENDER_NATIVE, "Native GRAND layout"),
        (RENDER_XLSX_TEMPLATE, "Mapped Excel workbook"),
        (RENDER_PDF_OVERLAY, "Exact PDF overlay"),
    )

    definition = models.ForeignKey(ReportDefinition, on_delete=models.CASCADE, related_name="template_versions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=180)
    header_text = models.CharField(max_length=255, blank=True)
    certification_text = models.TextField(blank=True)
    footer_text = models.CharField(max_length=255, blank=True)
    document_control_prefix = models.CharField(max_length=30, blank=True)
    signatories = models.JSONField(default=list, blank=True)
    layout_config = models.JSONField(default=dict, blank=True)
    reference_kind = models.CharField(max_length=12, choices=REFERENCE_CHOICES, default=REFERENCE_NONE)
    reference_file = models.FileField(
        upload_to=report_reference_path,
        max_length=500,
        blank=True,
        validators=[FileExtensionValidator(REFERENCE_EXTENSIONS)],
        help_text="Stored as a non-executable reference. Mapping and approval are required before official use.",
    )
    mapping_notes = models.TextField(blank=True)
    render_mode = models.CharField(max_length=20, choices=RENDER_MODE_CHOICES, default=RENDER_NATIVE)
    mapping_checksum = models.CharField(max_length=64, blank=True)
    mapping_summary = models.JSONField(default=dict, blank=True)
    mapping_validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="preflighted_report_templates")
    mapping_validated_at = models.DateTimeField(null=True, blank=True)
    fidelity_status = models.CharField(max_length=12, choices=FIDELITY_CHOICES, default=PILOT)
    fidelity_notes = models.TextField(blank=True, help_text="Record the department comparison, governing form, and sign-off basis.")
    page_size = models.CharField(max_length=10, choices=PAGE_SIZE_CHOICES, default=PAGE_A4)
    orientation = models.CharField(max_length=10, choices=ORIENTATION_CHOICES, default=LANDSCAPE)
    margin_mm = models.PositiveSmallIntegerField(default=14, validators=[MinValueValidator(5), MaxValueValidator(30)])
    page_border = models.CharField(max_length=10, choices=BORDER_CHOICES, default=BORDER_SINGLE)
    repeat_header = models.BooleanField(default=True)
    show_footer = models.BooleanField(default=True)
    show_page_numbers = models.BooleanField(default=True)
    show_document_control = models.BooleanField(default=True)
    primary_logo = models.ImageField(upload_to=report_identity_path, max_length=500, blank=True, validators=[FileExtensionValidator(IMAGE_EXTENSIONS)])
    secondary_logo = models.ImageField(upload_to=report_identity_path, max_length=500, blank=True, validators=[FileExtensionValidator(IMAGE_EXTENSIONS)])
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_report_templates")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_report_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    fidelity_validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="validated_report_templates")
    fidelity_validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("definition", "-version")
        constraints = (
            models.UniqueConstraint(fields=("definition", "version"), name="unique_report_template_version"),
        )

    def __str__(self):
        return f"{self.definition.name} v{self.version}"

    @property
    def is_official_ready(self):
        return self.is_mapping_ready and self.fidelity_status == self.OFFICIAL and bool(self.fidelity_validated_at and self.approved_at)

    @property
    def is_mapping_ready(self):
        return self.render_mode == self.RENDER_NATIVE or bool(self.mapping_checksum and self.mapping_validated_at)

    @property
    def supported_formats(self):
        if self.render_mode == self.RENDER_XLSX_TEMPLATE:
            return (ReportDefinition.FORMAT_XLSX,)
        if self.render_mode == self.RENDER_PDF_OVERLAY:
            return (ReportDefinition.FORMAT_PDF,)
        return tuple(value for value, _label in ReportDefinition.FORMAT_CHOICES)

    def supports_format(self, output_format):
        return output_format in self.supported_formats

    def clean(self):
        if self.reference_file and getattr(self.reference_file, "size", 0) > 10 * 1024 * 1024:
            raise ValidationError({"reference_file": "Report template references must be 10 MB or smaller."})
        if self.reference_kind == self.REFERENCE_NONE and self.reference_file:
            raise ValidationError({"reference_kind": "Identify the uploaded reference format."})
        if self.reference_kind != self.REFERENCE_NONE and not self.reference_file and self.pk is None:
            raise ValidationError({"reference_file": "Upload the referenced departmental form."})
        if not isinstance(self.signatories, list) or any(not isinstance(item, dict) for item in self.signatories):
            raise ValidationError({"signatories": "Signatories must be a list of role and name mappings."})
        if not isinstance(self.layout_config, dict):
            raise ValidationError({"layout_config": "Layout configuration must be a controlled mapping."})
        if not isinstance(self.mapping_summary, dict):
            raise ValidationError({"mapping_summary": "Mapping validation must be a controlled summary."})
        if self.render_mode == self.RENDER_XLSX_TEMPLATE and self.reference_kind != self.REFERENCE_XLSX:
            raise ValidationError({"reference_kind": "Mapped Excel layouts require an XLSX workbook reference."})
        if self.render_mode == self.RENDER_PDF_OVERLAY and self.reference_kind != self.REFERENCE_PDF:
            raise ValidationError({"reference_kind": "Exact PDF overlays require a PDF reference."})
        if self.render_mode == self.RENDER_XLSX_TEMPLATE and self.reference_file and not self.reference_file.name.lower().endswith(".xlsx"):
            raise ValidationError({"reference_file": "Mapped workbooks must use the macro-free XLSX format."})
        if self.approved_at and not self.is_mapping_ready:
            raise ValidationError({"approved_at": "Mapped templates must pass preflight before approval."})
        if self.fidelity_status == self.OFFICIAL and not self.fidelity_validated_at:
            raise ValidationError({"fidelity_status": "Official layouts require recorded department validation."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.approved_at:
                immutable_fields = ("title", "header_text", "certification_text", "footer_text", "document_control_prefix", "signatories", "layout_config", "reference_kind", "mapping_notes", "render_mode", "mapping_checksum", "mapping_summary", "page_size", "orientation", "margin_mm", "page_border", "repeat_header", "show_footer", "show_page_numbers", "show_document_control")
                changed = any(getattr(prior, field) != getattr(self, field) for field in immutable_fields)
                changed = changed or prior.reference_file.name != self.reference_file.name or prior.primary_logo.name != self.primary_logo.name or prior.secondary_logo.name != self.secondary_logo.name
                if changed:
                    raise ValidationError("Approved template versions are immutable. Create a new version instead.")
            if prior and prior.fidelity_validated_at:
                fidelity_fields = ("fidelity_status", "fidelity_notes", "fidelity_validated_by_id", "fidelity_validated_at")
                if any(getattr(prior, field) != getattr(self, field) for field in fidelity_fields):
                    raise ValidationError("Department fidelity evidence is immutable. Create a new template version for a different validation.")


class ReportTemplateMappingField(models.Model):
    ALIGN_LEFT = "left"
    ALIGN_CENTER = "center"
    ALIGN_RIGHT = "right"
    ALIGNMENT_CHOICES = ((ALIGN_LEFT, "Left"), (ALIGN_CENTER, "Center"), (ALIGN_RIGHT, "Right"))

    template_version = models.ForeignKey(ReportTemplateVersion, on_delete=models.CASCADE, related_name="overlay_fields")
    source_key = models.CharField(max_length=100)
    page_number = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    x_mm = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(500)])
    y_mm = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(500)], help_text="Distance from the top edge of the page.")
    width_mm = models.DecimalField(max_digits=6, decimal_places=2, default=60, validators=[MinValueValidator(5), MaxValueValidator(500)])
    font_size = models.DecimalField(max_digits=4, decimal_places=1, default=9, validators=[MinValueValidator(5), MaxValueValidator(24)])
    alignment = models.CharField(max_length=8, choices=ALIGNMENT_CHOICES, default=ALIGN_LEFT)
    repeat_for_rows = models.BooleanField(default=False)
    row_height_mm = models.DecimalField(max_digits=5, decimal_places=2, default=5, validators=[MinValueValidator(2), MaxValueValidator(30)])
    max_rows = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(500)])
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("page_number", "display_order", "pk")

    def __str__(self):
        return f"{self.template_version}: {self.source_key}"

    @property
    def is_dataset_field(self):
        return self.source_key in (self.template_version.definition.selected_fields or [])

    def clean(self):
        if self.template_version_id and self.template_version.render_mode != ReportTemplateVersion.RENDER_PDF_OVERLAY:
            raise ValidationError({"template_version": "Coordinate mappings belong only to exact PDF overlay templates."})
        metadata_keys = {"header", "title", "period", "period_start", "period_end", "control_id", "row_count"}
        selected = set(self.template_version.definition.selected_fields or []) if self.template_version_id else set()
        total_keys = {f"total:{key}" for key in self.template_version.definition.totals or []} if self.template_version_id else set()
        if self.source_key not in metadata_keys | selected | total_keys:
            raise ValidationError({"source_key": "Choose document metadata or a field exposed by this report definition."})
        if self.repeat_for_rows and self.source_key not in selected:
            raise ValidationError({"repeat_for_rows": "Only dataset fields may repeat down a PDF table area."})
        if not self.repeat_for_rows and self.max_rows != 1:
            raise ValidationError({"max_rows": "Non-repeating mappings must use one row."})

    def _assert_editable(self):
        if self.template_version_id and self.template_version.approved_at:
            raise ValidationError("Approved template mappings are immutable. Create a new template version instead.")

    def _invalidate_preflight(self):
        ReportTemplateVersion.objects.filter(pk=self.template_version_id).update(
            mapping_checksum="", mapping_summary={}, mapping_validated_by=None, mapping_validated_at=None,
        )

    def save(self, *args, **kwargs):
        self._assert_editable()
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._invalidate_preflight()
        return result

    def delete(self, *args, **kwargs):
        self._assert_editable()
        template_id = self.template_version_id
        result = super().delete(*args, **kwargs)
        ReportTemplateVersion.objects.filter(pk=template_id).update(
            mapping_checksum="", mapping_summary={}, mapping_validated_by=None, mapping_validated_at=None,
        )
        return result


class ReportSchedule(models.Model):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    FREQUENCY_CHOICES = ((DAILY, "Daily"), (WEEKLY, "Weekly"), (MONTHLY, "Monthly"), (QUARTERLY, "Quarterly"), (ANNUAL, "Annual"))

    definition = models.ForeignKey(ReportDefinition, on_delete=models.CASCADE, related_name="schedules")
    template_version = models.ForeignKey(ReportTemplateVersion, on_delete=models.PROTECT, related_name="schedules")
    name = models.CharField(max_length=180)
    frequency = models.CharField(max_length=12, choices=FREQUENCY_CHOICES)
    output_format = models.CharField(max_length=8, choices=ReportDefinition.FORMAT_CHOICES)
    parameters = models.JSONField(default=dict, blank=True)
    next_run_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_report_schedules")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("next_run_at", "name")

    def __str__(self):
        return self.name

    def clean(self):
        if self.template_version_id and self.definition_id and self.template_version.definition_id != self.definition_id:
            raise ValidationError({"template_version": "The template must belong to this report definition."})
        if self.template_version_id and not self.template_version.supports_format(self.output_format):
            raise ValidationError({"output_format": "This output format is not supported by the selected template mapper."})
        if self.template_version_id and not self.template_version.approved_at:
            raise ValidationError({"template_version": "Scheduled reports require an approved template version."})


class ReportRun(models.Model):
    DRAFT = "draft"
    GENERATED = "generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = ((DRAFT, "Draft"), (GENERATED, "Generated"), (REVIEWED, "Reviewed"), (APPROVED, "Approved"), (FAILED, "Failed"), (SUPERSEDED, "Superseded"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    definition = models.ForeignKey(ReportDefinition, on_delete=models.PROTECT, related_name="runs")
    template_version = models.ForeignKey(ReportTemplateVersion, on_delete=models.PROTECT, related_name="runs")
    schedule = models.ForeignKey(ReportSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs")
    idempotency_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    output_format = models.CharField(max_length=8, choices=ReportDefinition.FORMAT_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    parameters = models.JSONField(default=dict, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    output_file = models.FileField(upload_to=report_output_path, max_length=500, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_report_runs")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_report_runs")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="official_report_runs")
    generated_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.definition.name}: {self.period_start} to {self.period_end}"

    def get_absolute_url(self):
        return reverse("reporting:run_detail", kwargs={"public_id": self.public_id})

    @property
    def is_printable(self):
        return self.output_format == ReportDefinition.FORMAT_PDF and bool(self.output_file)

    @property
    def is_official_output(self):
        return self.status == self.APPROVED and self.template_version.is_official_ready

    def clean(self):
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "The reporting period cannot end before it starts."})
        if self.template_version_id and self.definition_id and self.template_version.definition_id != self.definition_id:
            raise ValidationError({"template_version": "The template must belong to this report definition."})
        if self.template_version_id and not self.template_version.supports_format(self.output_format):
            raise ValidationError({"output_format": "This output format is not supported by the selected template mapper."})


class ReportRunEvent(models.Model):
    run = models.ForeignKey(ReportRun, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="report_run_events")
    action = models.CharField(max_length=40)
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.run_id}: {self.action}"
