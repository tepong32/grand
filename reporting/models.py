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


def statement_reference_path(instance, filename):
    return (
        f"reporting/statement-references/{instance.run.definition.department.slug}/"
        f"{instance.run.definition.slug}/{instance.run.public_id}/v{instance.version}/{filename}"
    )


def local_form_reference_path(instance, filename):
    return (
        f"reporting/local-form-references/{instance.department.slug}/"
        f"{instance.code}/v{instance.version}/{filename}"
    )


class ReportDefinition(models.Model):
    FORMAT_PDF = "pdf"
    FORMAT_XLSX = "xlsx"
    FORMAT_CSV = "csv"
    FORMAT_CHOICES = ((FORMAT_PDF, "PDF"), (FORMAT_XLSX, "Excel workbook"), (FORMAT_CSV, "CSV"))
    APPLICABILITY_DEPARTMENTAL = "departmental"
    APPLICABILITY_CANDIDATE = "candidate"
    APPLICABILITY_CONFIRMED = "confirmed"
    APPLICABILITY_CHOICES = (
        (APPLICABILITY_DEPARTMENTAL, "Departmental / management output"),
        (APPLICABILITY_CANDIDATE, "Controlled official-form candidate — local confirmation pending"),
        (APPLICABILITY_CONFIRMED, "Locally confirmed official requirement"),
    )

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
    applicability_status = models.CharField(
        max_length=16, choices=APPLICABILITY_CHOICES, default=APPLICABILITY_DEPARTMENTAL,
    )
    authority_reference = models.TextField(
        blank=True,
        help_text="Plain-language COA, DBM, BIR, ordinance, memorandum, or local-procedure basis. Do not paste secrets or credentials.",
    )
    local_acceptance_note = models.TextField(
        blank=True,
        help_text="Record who confirmed local applicability, the accepted form/schedule, and where the retained evidence can be checked.",
    )
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
            ("prepare_template_promotions", "Can prepare report template promotion requests"),
            ("approve_template_promotions", "Can independently approve report template promotions"),
            ("activate_template_promotions", "Can activate or roll back approved report templates"),
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
        if self.applicability_status == self.APPLICABILITY_CONFIRMED:
            if not self.authority_reference.strip():
                raise ValidationError({"authority_reference": "A locally confirmed requirement needs its reviewed authority reference."})
            if not self.local_acceptance_note.strip():
                raise ValidationError({"local_acceptance_note": "Record the local acceptance and retained evidence before marking this requirement confirmed."})


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


class FinanceStatementMapping(models.Model):
    POSITION = "position"
    PERFORMANCE = "performance"
    STATEMENT_CHOICES = (
        (POSITION, "Management statement of financial position"),
        (PERFORMANCE, "Management statement of financial performance"),
    )
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    STARTER = "starter"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable draft"), (SUBMITTED, "For independent review"),
        (RETURNED, "Returned for correction"),
        (STARTER, "Controlled management starter"),
        (ACTIVE, "Locally accepted active mapping"),
        (SUPERSEDED, "Superseded mapping"),
    )
    LOCKED_STATUSES = {STARTER, ACTIVE, SUPERSEDED}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_statement_mappings",
    )
    statement_type = models.CharField(max_length=16, choices=STATEMENT_CHOICES)
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors",
    )
    authority_reference = models.TextField(blank=True)
    local_acceptance_note = models.TextField(blank=True)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_statement_mappings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_statement_mappings",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_statement_mappings",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("statement_type", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("department", "statement_type", "version"),
                name="unique_finance_statement_mapping_version",
            ),
            models.UniqueConstraint(
                fields=("department", "statement_type"),
                condition=models.Q(status="active"),
                name="one_active_finance_statement_mapping",
            ),
        )

    def __str__(self):
        return f"{self.get_statement_type_display()} · v{self.version}"

    def get_absolute_url(self):
        return reverse("reporting:statement_mapping_detail", kwargs={"public_id": self.public_id})

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "A mapping cannot supersede itself."})
            if (
                self.supersedes.department_id != self.department_id
                or self.supersedes.statement_type != self.statement_type
                or self.version <= self.supersedes.version
            ):
                raise ValidationError({
                    "supersedes": "Choose an earlier version of the same department statement mapping.",
                })
        if self.status == self.ACTIVE:
            if not self.authority_reference.strip() or not self.local_acceptance_note.strip():
                raise ValidationError(
                    "An active statement mapping requires its reviewed authority and local acceptance evidence."
                )
            if not self.snapshot_checksum or not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("An active statement mapping requires immutable review evidence.")
            if self.created_by_id == self.reviewed_by_id:
                raise ValidationError("The statement mapping preparer cannot approve the same version.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "department_id", "statement_type", "version", "title", "description",
                "supersedes_id", "authority_reference", "local_acceptance_note", "created_by_id",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Locked statement mappings are immutable. Create a successor version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists():
            raise ValidationError("Statement mapping history cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceStatementLine(models.Model):
    ACCOUNT_TYPE = "account_type"
    ACCOUNT_CODES = "account_codes"
    SELECTOR_CHOICES = (
        (ACCOUNT_TYPE, "All accounts of one type"),
        (ACCOUNT_CODES, "Selected account codes"),
    )
    ACCOUNT_TYPE_CHOICES = (
        ("", "Choose when using account type"),
        ("asset", "Asset"), ("liability", "Liability"), ("equity", "Equity"),
        ("revenue", "Revenue"), ("expense", "Expense"),
    )

    mapping = models.ForeignKey(
        FinanceStatementMapping, on_delete=models.CASCADE, related_name="lines",
    )
    position = models.PositiveSmallIntegerField()
    section_code = models.SlugField(max_length=60)
    section_title = models.CharField(max_length=160)
    line_code = models.SlugField(max_length=60)
    line_title = models.CharField(max_length=180)
    selector_type = models.CharField(max_length=20, choices=SELECTOR_CHOICES)
    account_type = models.CharField(max_length=16, choices=ACCOUNT_TYPE_CHOICES, blank=True)
    account_codes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ("position", "pk")
        constraints = (
            models.UniqueConstraint(fields=("mapping", "position"), name="unique_statement_line_position"),
            models.UniqueConstraint(fields=("mapping", "line_code"), name="unique_statement_line_code"),
        )

    def __str__(self):
        return f"{self.mapping} · {self.line_title}"

    def clean(self):
        if self.selector_type == self.ACCOUNT_TYPE:
            if not self.account_type:
                raise ValidationError({"account_type": "Choose the account type for this statement line."})
            if self.account_codes:
                raise ValidationError({"account_codes": "Account-type lines cannot also select individual codes."})
        elif self.selector_type == self.ACCOUNT_CODES:
            if self.account_type:
                raise ValidationError({"account_type": "Selected-code lines do not also use an account type."})
            if not isinstance(self.account_codes, list) or not self.account_codes:
                raise ValidationError({"account_codes": "Choose at least one governed ledger account."})
            if any(not isinstance(code, str) or not code.strip() for code in self.account_codes):
                raise ValidationError({"account_codes": "Account codes must be a non-empty controlled list."})
        if self.mapping_id:
            allowed = (
                {"asset", "liability", "equity"}
                if self.mapping.statement_type == FinanceStatementMapping.POSITION
                else {"revenue", "expense"}
            )
            if self.account_type and self.account_type not in allowed:
                raise ValidationError({"account_type": "This account type does not belong in the selected statement."})

    def save(self, *args, **kwargs):
        if self.mapping_id and not self.mapping.is_editable:
            raise ValidationError("Locked statement mapping lines are immutable. Create a successor version.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.mapping.is_editable:
            raise ValidationError("Locked statement mapping lines cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceStatementMappingEvent(models.Model):
    mapping = models.ForeignKey(
        FinanceStatementMapping, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="finance_statement_mapping_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Statement mapping events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Statement mapping events cannot be deleted.")


class FinanceStatementNoteSet(models.Model):
    """Versioned explanatory notes pinned to one position/performance statement pair."""

    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    APPLICABILITY_CHOICES = (
        (CANDIDATE, "Controlled candidate — local acceptance pending"),
        (CONFIRMED, "Locally confirmed statement-note package"),
    )
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable draft"),
        (SUBMITTED, "For independent review"),
        (RETURNED, "Returned for correction"),
        (REVIEWED, "Controlled working notes"),
        (APPROVED, "Locally accepted notes"),
        (SUPERSEDED, "Superseded notes"),
    )
    LOCKED_STATUSES = {SUBMITTED, REVIEWED, APPROVED, SUPERSEDED}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_statement_note_sets",
    )
    title = models.CharField(max_length=200, default="Notes to the financial statements")
    period_start = models.DateField()
    period_end = models.DateField()
    version = models.PositiveIntegerField()
    applicability_status = models.CharField(
        max_length=12, choices=APPLICABILITY_CHOICES, default=CANDIDATE,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    position_run = models.ForeignKey(
        "ReportRun", on_delete=models.PROTECT, related_name="position_note_sets",
    )
    performance_run = models.ForeignKey(
        "ReportRun", on_delete=models.PROTECT, related_name="performance_note_sets",
    )
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors",
    )
    preparation_note = models.TextField(blank=True)
    authority_reference = models.TextField(blank=True)
    local_acceptance_note = models.TextField(blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_statement_note_sets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_statement_note_sets",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_statement_note_sets",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_end", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("department", "period_start", "period_end", "version"),
                name="unique_statement_note_set_version",
            ),
            models.UniqueConstraint(
                fields=("department", "period_start", "period_end"),
                condition=models.Q(status="approved"),
                name="one_approved_statement_note_set",
            ),
        )
        permissions = (
            ("prepare_statement_notes", "Can prepare financial statement notes"),
            ("review_statement_notes", "Can independently review financial statement notes"),
            ("export_statement_packages", "Can export statement notes and comparison evidence"),
        )

    def __str__(self):
        return f"{self.title} · {self.period_end:%Y-%m-%d} · v{self.version}"

    def get_absolute_url(self):
        return reverse("reporting:statement_note_set_detail", kwargs={"public_id": self.public_id})

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "The note period cannot end before it starts."})
        expected = (
            (self.position_run, "finance_statement_position", "position_run"),
            (self.performance_run, "finance_statement_performance", "performance_run"),
        )
        for run, dataset_key, field in expected:
            if run.definition.department_id != self.department_id:
                raise ValidationError({field: "Choose a statement run from this Accounting department."})
            actual_key = run.parameters.get("_definition_snapshot", {}).get(
                "dataset_key", run.definition.dataset_key,
            )
            if actual_key != dataset_key:
                raise ValidationError({field: "Choose the matching governed statement run."})
            if run.period_start != self.period_start or run.period_end != self.period_end:
                raise ValidationError({field: "Both statement runs must cover the note package period exactly."})
            if run.control_status != run.CONTROL_RECONCILED:
                raise ValidationError({field: "Only a control-reconciled statement run can support notes."})
        if self.position_run_id == self.performance_run_id:
            raise ValidationError("Use separate position and performance statement runs.")
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "A note package cannot supersede itself."})
            if (
                self.supersedes.department_id != self.department_id
                or self.supersedes.period_start != self.period_start
                or self.supersedes.period_end != self.period_end
                or self.version <= self.supersedes.version
            ):
                raise ValidationError({"supersedes": "Choose an earlier note package for the same department and period."})
        if self.status == self.APPROVED:
            if self.applicability_status != self.CONFIRMED:
                raise ValidationError("Only locally confirmed notes can be approved for official use.")
            if not self.authority_reference.strip() or not self.local_acceptance_note.strip():
                raise ValidationError("Approved notes require reviewed authority and local acceptance evidence.")
            if not self.snapshot_checksum or not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("Approved notes require immutable independent-review evidence.")
            if self.created_by_id == self.reviewed_by_id or self.submitted_by_id == self.reviewed_by_id:
                raise ValidationError("The note preparer or submitter cannot approve the same package.")
            if not self.position_run.is_official_output or not self.performance_run.is_official_output:
                raise ValidationError("Official notes require approved official position and performance runs.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "department_id", "title", "period_start", "period_end", "version",
                "applicability_status", "position_run_id", "performance_run_id", "supersedes_id",
                "preparation_note", "authority_reference", "local_acceptance_note", "created_by_id",
                "source_snapshot", "snapshot_checksum",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted statement notes are immutable. Return them or create a successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists():
            raise ValidationError("Statement-note history cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceStatementNote(models.Model):
    GENERAL = "general"
    POSITION = "position"
    PERFORMANCE = "performance"
    BOTH = "both"
    RELATED_CHOICES = (
        (GENERAL, "General disclosure"),
        (POSITION, "Statement of financial position"),
        (PERFORMANCE, "Statement of financial performance"),
        (BOTH, "Both statements"),
    )

    note_set = models.ForeignKey(
        FinanceStatementNoteSet, on_delete=models.CASCADE, related_name="notes",
    )
    position = models.PositiveSmallIntegerField()
    topic_code = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    related_statement = models.CharField(max_length=16, choices=RELATED_CHOICES, default=GENERAL)
    related_line_codes = models.JSONField(default=list, blank=True)
    disclosure_text = models.TextField(blank=True)
    source_reference = models.TextField(blank=True)
    authority_basis = models.TextField(blank=True)
    is_not_applicable = models.BooleanField(default=False)
    not_applicable_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("position", "pk")
        constraints = (
            models.UniqueConstraint(fields=("note_set", "position"), name="unique_statement_note_position"),
            models.UniqueConstraint(fields=("note_set", "topic_code"), name="unique_statement_note_topic"),
        )

    def __str__(self):
        return f"{self.note_set} · {self.title}"

    def clean(self):
        if not isinstance(self.related_line_codes, list) or any(
            not isinstance(value, str) or not value.strip() for value in self.related_line_codes
        ):
            raise ValidationError({"related_line_codes": "Related line codes must be a plain controlled list."})
        if self.is_not_applicable:
            if not self.not_applicable_reason.strip():
                raise ValidationError({"not_applicable_reason": "Explain why this candidate topic does not apply."})
            if self.disclosure_text.strip():
                raise ValidationError({"disclosure_text": "Remove disclosure text when the topic is marked not applicable."})
        else:
            if not self.disclosure_text.strip():
                raise ValidationError({"disclosure_text": "Write the disclosure or mark the topic not applicable with a reason."})
            if self.not_applicable_reason.strip():
                raise ValidationError({"not_applicable_reason": "Use this field only when the topic is not applicable."})

    def save(self, *args, **kwargs):
        if self.note_set_id and not self.note_set.is_editable:
            raise ValidationError("Locked statement-note topics are immutable. Create a successor package.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.note_set.is_editable:
            raise ValidationError("Locked statement-note topics cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceStatementNoteEvent(models.Model):
    note_set = models.ForeignKey(
        FinanceStatementNoteSet, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="finance_statement_note_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Statement-note events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Statement-note events cannot be deleted.")


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
    CONTROL_NOT_APPLICABLE = "not_applicable"
    CONTROL_RECONCILED = "reconciled"
    CONTROL_EXCEPTION = "exception"
    CONTROL_UNAVAILABLE = "unavailable"
    CONTROL_STATUS_CHOICES = (
        (CONTROL_NOT_APPLICABLE, "Not applicable"),
        (CONTROL_RECONCILED, "Control totals reconciled"),
        (CONTROL_EXCEPTION, "Control exception"),
        (CONTROL_UNAVAILABLE, "Control evidence unavailable"),
    )

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
    dataset_snapshot = models.JSONField(default=dict, blank=True)
    dataset_checksum = models.CharField(max_length=64, blank=True)
    control_totals = models.JSONField(default=dict, blank=True)
    control_checksum = models.CharField(max_length=64, blank=True)
    control_status = models.CharField(
        max_length=20, choices=CONTROL_STATUS_CHOICES, default=CONTROL_NOT_APPLICABLE,
    )
    control_message = models.TextField(blank=True)
    control_gate_required = models.BooleanField(default=False)
    source_record_count = models.PositiveIntegerField(default=0)
    source_freshness_at = models.DateTimeField(null=True, blank=True)
    reproduction_key = models.CharField(max_length=64, blank=True)
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
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.generated_at:
                evidence_fields = (
                    "dataset_snapshot", "dataset_checksum", "control_totals", "control_checksum",
                    "control_status", "control_message", "control_gate_required", "source_record_count",
                    "source_freshness_at", "reproduction_key", "checksum", "row_count", "output_file",
                    "definition_id", "template_version_id", "output_format", "period_start", "period_end",
                    "parameters", "generated_at",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in evidence_fields):
                    raise ValidationError("Generated report evidence is immutable. Generate a successor run instead.")


class ReportRunSource(models.Model):
    """Cross-database-safe source snapshot supporting report-total drill-through."""

    run = models.ForeignKey(ReportRun, on_delete=models.CASCADE, related_name="source_records")
    source_app = models.CharField(max_length=40)
    source_model = models.CharField(max_length=80)
    source_pk = models.CharField(max_length=80)
    source_public_id = models.CharField(max_length=80, blank=True)
    source_reference = models.CharField(max_length=180)
    source_date = models.DateField(null=True, blank=True)
    control_group = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    source_checksum = models.CharField(max_length=64, blank=True)
    source_url = models.CharField(max_length=500, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("source_date", "source_app", "source_model", "source_reference", "pk")
        indexes = (
            models.Index(fields=("run", "control_group"), name="report_source_control_idx"),
        )

    def __str__(self):
        return f"{self.run_id}: {self.source_reference}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Report source evidence is immutable. Generate a successor run instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Report source evidence cannot be deleted independently from its retained run.")


class ReportReferenceComparison(models.Model):
    """Independent exact-control comparison against a retained signed/redacted reference."""

    REFERENCE_PDF = "pdf"
    REFERENCE_XLSX = "xlsx"
    REFERENCE_IMAGE = "image"
    REFERENCE_CHOICES = (
        (REFERENCE_PDF, "PDF reference"),
        (REFERENCE_XLSX, "Excel reference"),
        (REFERENCE_IMAGE, "Scanned or image reference"),
    )
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    RECONCILED = "reconciled"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable comparison"),
        (SUBMITTED, "For independent review"),
        (RETURNED, "Returned for correction"),
        (RECONCILED, "Exact controls independently reconciled"),
        (SUPERSEDED, "Superseded comparison"),
    )
    RESULT_PENDING = "pending"
    RESULT_RECONCILED = "reconciled"
    RESULT_EXCEPTION = "exception"
    RESULT_CHOICES = (
        (RESULT_PENDING, "Not calculated"),
        (RESULT_RECONCILED, "Exact agreement"),
        (RESULT_EXCEPTION, "Difference requires resolution"),
    )
    LOCKED_STATUSES = {SUBMITTED, RECONCILED, SUPERSEDED}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    run = models.ForeignKey(ReportRun, on_delete=models.PROTECT, related_name="reference_comparisons")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    reference_label = models.CharField(max_length=200)
    reference_kind = models.CharField(max_length=12, choices=REFERENCE_CHOICES)
    reference_file = models.FileField(
        upload_to=statement_reference_path,
        max_length=500,
        validators=[FileExtensionValidator(("pdf", "xlsx", "png", "jpg", "jpeg"))],
        help_text="Upload only the approved redacted comparison copy; GRAND never executes its contents.",
    )
    signed_copy = models.BooleanField(default=False)
    redaction_confirmed = models.BooleanField(default=False)
    authority_reference = models.TextField(blank=True)
    local_acceptance_note = models.TextField(blank=True)
    reference_values = models.JSONField(default=dict, blank=True)
    generated_values_snapshot = models.JSONField(default=dict, blank=True)
    differences = models.JSONField(default=dict, blank=True)
    comparison_result = models.CharField(
        max_length=16, choices=RESULT_CHOICES, default=RESULT_PENDING,
    )
    run_evidence_snapshot = models.JSONField(default=dict, blank=True)
    reference_file_checksum = models.CharField(max_length=64, blank=True)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_report_reference_comparisons",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_report_reference_comparisons",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_report_reference_comparisons",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = (
            models.UniqueConstraint(fields=("run", "version"), name="unique_report_reference_comparison_version"),
        )
        permissions = (
            ("prepare_reference_comparisons", "Can prepare signed report reference comparisons"),
            ("review_reference_comparisons", "Can independently review signed report reference comparisons"),
        )

    def __str__(self):
        return f"{self.reference_label} · {self.run.definition.name} · v{self.version}"

    def get_absolute_url(self):
        return reverse("reporting:reference_comparison_detail", kwargs={"public_id": self.public_id})

    @property
    def department(self):
        return self.run.definition.department

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        actual_key = self.run.parameters.get("_definition_snapshot", {}).get(
            "dataset_key", self.run.definition.dataset_key,
        )
        if actual_key not in ("finance_statement_position", "finance_statement_performance"):
            raise ValidationError({"run": "Reference comparison is limited to governed financial statement runs."})
        if self.reference_file and getattr(self.reference_file, "size", 0) > 15 * 1024 * 1024:
            raise ValidationError({"reference_file": "Reference copies must be 15 MB or smaller."})
        if self.reference_kind == self.REFERENCE_PDF and self.reference_file and not self.reference_file.name.lower().endswith(".pdf"):
            raise ValidationError({"reference_file": "Choose a PDF file for a PDF reference."})
        if self.reference_kind == self.REFERENCE_XLSX and self.reference_file and not self.reference_file.name.lower().endswith(".xlsx"):
            raise ValidationError({"reference_file": "Choose a macro-free XLSX file for an Excel reference."})
        if self.reference_kind == self.REFERENCE_IMAGE and self.reference_file and not self.reference_file.name.lower().endswith((".png", ".jpg", ".jpeg")):
            raise ValidationError({"reference_file": "Choose a PNG or JPEG image reference."})
        for field in ("reference_values", "generated_values_snapshot", "differences", "run_evidence_snapshot"):
            if not isinstance(getattr(self, field), dict):
                raise ValidationError({field: "Comparison evidence must be a controlled key/value mapping."})
        if self.status == self.RECONCILED:
            if self.comparison_result != self.RESULT_RECONCILED:
                raise ValidationError("Only an exact zero-difference comparison can be reconciled.")
            if not self.signed_copy or not self.redaction_confirmed:
                raise ValidationError("Reconciled evidence must be a signed and confirmed-redacted comparison copy.")
            if not self.authority_reference.strip() or not self.local_acceptance_note.strip():
                raise ValidationError("Record the reviewed authority and local acceptance evidence.")
            if not self.snapshot_checksum or not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("Reconciled comparison requires immutable review evidence.")
            if self.created_by_id == self.reviewed_by_id or self.submitted_by_id == self.reviewed_by_id:
                raise ValidationError("The comparison preparer or submitter cannot review the same evidence.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "run_id", "version", "reference_label", "reference_kind", "reference_file",
                "signed_copy", "redaction_confirmed", "authority_reference", "local_acceptance_note",
                "reference_values", "generated_values_snapshot", "differences", "comparison_result",
                "run_evidence_snapshot", "reference_file_checksum", "snapshot_checksum", "created_by_id",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted reference evidence is immutable. Return it or create a successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists():
            raise ValidationError("Reference-comparison history cannot be deleted.")
        return super().delete(*args, **kwargs)


class ReportReferenceComparisonEvent(models.Model):
    comparison = models.ForeignKey(
        ReportReferenceComparison, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="report_reference_comparison_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Reference-comparison events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Reference-comparison events cannot be deleted.")


class FinanceAccountabilityPackageProfile(models.Model):
    """Locally accepted, human-editable recipe for a Finance accountability package."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable draft"),
        (SUBMITTED, "For independent review"),
        (RETURNED, "Returned for correction"),
        (ACTIVE, "Active package profile"),
        (SUPERSEDED, "Superseded profile"),
    )
    LOCKED_STATUSES = {SUBMITTED, ACTIVE, SUPERSEDED}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_accountability_package_profiles",
    )
    code = models.SlugField(max_length=80)
    version = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_profiles",
    )
    authority_reference = models.TextField(
        blank=True,
        help_text="Plain-language COA, DBM, BIR, ordinance, memorandum, or accepted local-procedure basis.",
    )
    local_acceptance_note = models.TextField(
        blank=True,
        help_text="Record the office and person who accepted this package recipe and where its evidence is retained.",
    )
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_accountability_package_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_accountability_package_profiles",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_accountability_package_profiles",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("department", "code", "version"), name="unique_accountability_profile_version",
            ),
            models.UniqueConstraint(
                fields=("department", "code"), condition=models.Q(status="active"),
                name="one_active_accountability_profile",
            ),
        )
        permissions = (
            ("manage_accountability_package_profiles", "Can prepare Finance accountability package profiles"),
            ("approve_accountability_package_profiles", "Can independently approve Finance accountability package profiles"),
            ("prepare_accountability_packages", "Can prepare Finance accountability packages"),
            ("review_accountability_packages", "Can independently review Finance accountability packages"),
            ("export_accountability_packages", "Can export approved Finance accountability packages"),
        )

    def __str__(self):
        return f"{self.name} v{self.version}"

    def get_absolute_url(self):
        return reverse("reporting:accountability_profile_detail", kwargs={"public_id": self.public_id})

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "A profile cannot supersede itself."})
            if (
                self.supersedes.department_id != self.department_id
                or self.supersedes.code != self.code
                or self.version <= self.supersedes.version
            ):
                raise ValidationError({"supersedes": "Choose an earlier version of this department package profile."})
        if self.status == self.ACTIVE:
            if not self.authority_reference.strip() or not self.local_acceptance_note.strip():
                raise ValidationError("An active package profile requires authority and local acceptance evidence.")
            if not self.snapshot_checksum or not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("An active package profile requires pinned independent-review evidence.")
            if self.reviewed_by_id in (self.created_by_id, self.submitted_by_id):
                raise ValidationError("The profile preparer or submitter cannot approve the same profile.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "department_id", "code", "version", "name", "description", "supersedes_id",
                "authority_reference", "local_acceptance_note", "snapshot_checksum", "created_by_id",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted package profiles are immutable. Return the profile or create a successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists() or self.packages.exists():
            raise ValidationError("Package-profile history cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceAccountabilityPackageRequirement(models.Model):
    REPORT_RUN = "report_run"
    STATEMENT_NOTES = "statement_notes"
    SIGNED_REFERENCE = "signed_reference"
    TAX_FILING = "tax_filing"
    EVIDENCE_CHOICES = (
        (REPORT_RUN, "Approved GRAND report"),
        (STATEMENT_NOTES, "Approved financial-statement notes"),
        (SIGNED_REFERENCE, "Reconciled signed-reference comparison"),
        (TAX_FILING, "Verified tax-filing evidence"),
    )

    profile = models.ForeignKey(
        FinanceAccountabilityPackageProfile, on_delete=models.PROTECT, related_name="requirements",
    )
    position = models.PositiveSmallIntegerField()
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    evidence_kind = models.CharField(max_length=24, choices=EVIDENCE_CHOICES)
    source_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_accountability_source_requirements",
        help_text="Office responsible for the approved source output.",
    )
    report_definition = models.ForeignKey(
        ReportDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="finance_accountability_requirements",
    )
    tax_form_code = models.CharField(max_length=40, blank=True)
    required = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)

    class Meta:
        ordering = ("position", "pk")
        constraints = (
            models.UniqueConstraint(fields=("profile", "position"), name="unique_accountability_requirement_position"),
            models.UniqueConstraint(fields=("profile", "code"), name="unique_accountability_requirement_code"),
        )

    def __str__(self):
        return f"{self.profile}: {self.label}"

    def clean(self):
        if self.report_definition_id:
            if self.report_definition.department_id != self.source_department_id:
                raise ValidationError({"report_definition": "Choose a report owned by the selected source office."})
        if self.evidence_kind in (self.REPORT_RUN, self.SIGNED_REFERENCE):
            if not self.report_definition_id:
                raise ValidationError({"report_definition": "Choose the exact governed report required for this slot."})
            if self.tax_form_code.strip():
                raise ValidationError({"tax_form_code": "Use a tax form code only for tax-filing evidence."})
        elif self.report_definition_id:
            raise ValidationError({"report_definition": "This evidence type does not use a report definition."})
        if self.evidence_kind == self.TAX_FILING:
            if not self.tax_form_code.strip():
                raise ValidationError({"tax_form_code": "Enter the locally confirmed return form code."})
        elif self.tax_form_code.strip():
            raise ValidationError({"tax_form_code": "This evidence type does not use a tax form code."})

    def save(self, *args, **kwargs):
        if self.profile_id and not self.profile.is_editable:
            raise ValidationError("Locked package requirements are immutable. Create a successor profile.")
        self.tax_form_code = self.tax_form_code.strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.profile.is_editable:
            raise ValidationError("Locked package requirements cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceAccountabilityPackage(models.Model):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable draft"),
        (SUBMITTED, "For independent review"),
        (RETURNED, "Returned for correction"),
        (APPROVED, "Approved accountability package"),
        (SUPERSEDED, "Superseded package"),
    )
    LOCKED_STATUSES = {SUBMITTED, APPROVED, SUPERSEDED}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_accountability_packages",
    )
    profile = models.ForeignKey(
        FinanceAccountabilityPackageProfile, on_delete=models.PROTECT, related_name="packages",
    )
    title = models.CharField(max_length=200)
    period_start = models.DateField()
    period_end = models.DateField()
    version = models.PositiveSmallIntegerField(default=1)
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_packages",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    preparation_note = models.TextField(blank=True)
    profile_snapshot = models.JSONField(default=dict)
    profile_checksum = models.CharField(max_length=64)
    package_snapshot = models.JSONField(default=dict, blank=True)
    package_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_accountability_packages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_accountability_packages",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_accountability_packages",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_end", "profile__code", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("department", "profile", "period_start", "period_end", "version"),
                name="unique_accountability_package_version",
            ),
            models.UniqueConstraint(
                fields=("department", "profile", "period_start", "period_end"),
                condition=models.Q(status="approved"), name="one_approved_accountability_package",
            ),
        )

    def __str__(self):
        return f"{self.title} · {self.period_end:%Y-%m-%d} · v{self.version}"

    def get_absolute_url(self):
        return reverse("reporting:accountability_package_detail", kwargs={"public_id": self.public_id})

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "The package period cannot end before it starts."})
        if self.profile_id and self.profile.department_id != self.department_id:
            raise ValidationError({"profile": "Choose a profile owned by this Accounting office."})
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "A package cannot supersede itself."})
            if (
                self.supersedes.department_id != self.department_id
                or self.supersedes.profile.code != self.profile.code
                or self.supersedes.period_start != self.period_start
                or self.supersedes.period_end != self.period_end
                or self.version <= self.supersedes.version
            ):
                raise ValidationError({"supersedes": "Choose an earlier package for the same profile and exact period."})
        if self.status == self.APPROVED:
            if not self.package_checksum or not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("Approved packages require pinned independent-review evidence.")
            if self.reviewed_by_id in (self.created_by_id, self.submitted_by_id):
                raise ValidationError("The package preparer or submitter cannot approve the same package.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "department_id", "profile_id", "title", "period_start", "period_end", "version",
                "supersedes_id", "preparation_note", "profile_snapshot", "profile_checksum",
                "package_snapshot", "package_checksum", "created_by_id",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted accountability packages are immutable. Return the package or create a successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists():
            raise ValidationError("Accountability-package history cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceAccountabilityPackageSlot(models.Model):
    package = models.ForeignKey(
        FinanceAccountabilityPackage, on_delete=models.PROTECT, related_name="slots",
    )
    position = models.PositiveSmallIntegerField()
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    evidence_kind = models.CharField(
        max_length=24, choices=FinanceAccountabilityPackageRequirement.EVIDENCE_CHOICES,
    )
    source_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_accountability_package_slots",
    )
    source_department_label = models.CharField(max_length=160)
    report_definition = models.ForeignKey(
        ReportDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="finance_accountability_package_slots",
    )
    report_definition_label = models.CharField(max_length=180, blank=True)
    tax_form_code = models.CharField(max_length=40, blank=True)
    required = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)

    class Meta:
        ordering = ("position", "pk")
        constraints = (
            models.UniqueConstraint(fields=("package", "position"), name="unique_accountability_slot_position"),
            models.UniqueConstraint(fields=("package", "code"), name="unique_accountability_slot_code"),
        )

    def __str__(self):
        return f"{self.package}: {self.label}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Package requirement snapshots are immutable. Create a successor package profile.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Package requirement snapshots cannot be deleted.")

    @property
    def current_selection(self):
        return self.selections.filter(status=FinanceAccountabilityPackageSelection.CURRENT).first()


class FinanceAccountabilityPackageSelection(models.Model):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = ((CURRENT, "Current selection"), (SUPERSEDED, "Superseded selection"))

    slot = models.ForeignKey(
        FinanceAccountabilityPackageSlot, on_delete=models.PROTECT, related_name="selections",
    )
    version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=CURRENT)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor",
    )
    source_public_id = models.UUIDField()
    source_label = models.CharField(max_length=240)
    source_snapshot = models.JSONField(default=dict)
    source_checksum = models.CharField(max_length=64)
    change_reason = models.TextField(blank=True)
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="finance_accountability_package_selections",
    )
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("slot", "-version")
        constraints = (
            models.UniqueConstraint(fields=("slot", "version"), name="unique_accountability_selection_version"),
            models.UniqueConstraint(
                fields=("slot",), condition=models.Q(status="current"),
                name="one_current_accountability_selection",
            ),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "slot_id", "version", "supersedes_id", "source_public_id", "source_label",
                "source_snapshot", "source_checksum", "change_reason", "selected_by_id", "selected_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Package evidence selections are immutable. Create a reasoned successor selection.")
            if prior.status != self.CURRENT or self.status != self.SUPERSEDED:
                raise ValidationError("A selection may only move once from current to superseded.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Package evidence-selection history cannot be deleted.")


class FinanceAccountabilityPackageEvent(models.Model):
    package = models.ForeignKey(
        FinanceAccountabilityPackage, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="finance_accountability_package_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Accountability-package events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Accountability-package events cannot be deleted.")


class FinanceAccountabilityPackageProfileEvent(models.Model):
    profile = models.ForeignKey(
        FinanceAccountabilityPackageProfile, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="finance_accountability_package_profile_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Accountability-profile events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Accountability-profile events cannot be deleted.")


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


class ReportTemplatePromotion(models.Model):
    """Deployment-independent evidence and approval for an official layout change."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    APPROVED = "approved"
    ACTIVATED = "activated"
    ROLLED_BACK = "rolled_back"
    STATUS_CHOICES = (
        (DRAFT, "Editable promotion request"),
        (SUBMITTED, "For independent approval"),
        (RETURNED, "Returned for correction"),
        (APPROVED, "Approved, awaiting activation"),
        (ACTIVATED, "Active official template"),
        (ROLLED_BACK, "Rolled back to prior template"),
    )
    GOLDEN_PENDING = "pending"
    GOLDEN_MATCHED = "matched"
    GOLDEN_REFERENCE = "reference_review"
    GOLDEN_EXCEPTION = "exception"
    GOLDEN_CHOICES = (
        (GOLDEN_PENDING, "Preview not compared"),
        (GOLDEN_MATCHED, "Golden run data and controls match"),
        (GOLDEN_REFERENCE, "First-layout reference review required"),
        (GOLDEN_EXCEPTION, "Preview comparison has differences"),
    )
    LOCKED_STATUSES = {SUBMITTED, APPROVED, ACTIVATED, ROLLED_BACK}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    candidate_template = models.OneToOneField(
        ReportTemplateVersion, on_delete=models.PROTECT, related_name="promotion_request",
    )
    baseline_template = models.ForeignKey(
        ReportTemplateVersion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="successor_promotion_requests",
    )
    preview_run = models.OneToOneField(
        ReportRun, on_delete=models.PROTECT, related_name="template_promotion_preview",
    )
    baseline_run = models.ForeignKey(
        ReportRun, on_delete=models.PROTECT, null=True, blank=True,
        related_name="template_promotion_baselines",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    change_reason = models.TextField()
    comparison_note = models.TextField(
        help_text="Plain-language side-by-side check, retained form, signatory, printer, and overflow evidence.",
    )
    update_compatible_schedules = models.BooleanField(default=False)
    template_snapshot = models.JSONField(default=dict)
    template_checksum = models.CharField(max_length=64)
    mapping_diff = models.JSONField(default=list)
    impact_snapshot = models.JSONField(default=dict)
    golden_result = models.CharField(max_length=20, choices=GOLDEN_CHOICES, default=GOLDEN_PENDING)
    golden_snapshot = models.JSONField(default=dict)
    submission_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_report_template_promotions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_report_template_promotions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_report_template_promotions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="activated_report_template_promotions",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="rolled_back_report_template_promotions",
    )
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rollback_reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.candidate_template} promotion"

    def get_absolute_url(self):
        return reverse("reporting:template_promotion_detail", kwargs={"public_id": self.public_id})

    @property
    def department(self):
        return self.candidate_template.definition.department

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        candidate = self.candidate_template
        if self.baseline_template_id and self.baseline_template.definition_id != candidate.definition_id:
            raise ValidationError({"baseline_template": "The prior template must belong to the same report."})
        if self.baseline_template_id and self.baseline_template_id == self.candidate_template_id:
            raise ValidationError({"baseline_template": "A candidate cannot be its own prior template."})
        if self.preview_run.definition_id != candidate.definition_id or self.preview_run.template_version_id != candidate.pk:
            raise ValidationError({"preview_run": "The preview must use this candidate template and report definition."})
        if self.baseline_run_id:
            baseline = self.baseline_run
            if not self.baseline_template_id or baseline.template_version_id != self.baseline_template_id:
                raise ValidationError({"baseline_run": "The golden run must use the selected prior template."})
            if baseline.definition_id != candidate.definition_id:
                raise ValidationError({"baseline_run": "The golden run must belong to the same report."})
            if (baseline.period_start, baseline.period_end, baseline.output_format) != (
                self.preview_run.period_start, self.preview_run.period_end, self.preview_run.output_format,
            ):
                raise ValidationError({"baseline_run": "The golden run and preview must cover the same period and format."})
        for field in ("template_snapshot", "impact_snapshot", "golden_snapshot"):
            if not isinstance(getattr(self, field), dict):
                raise ValidationError({field: "Promotion evidence must be a controlled key/value mapping."})
        if not isinstance(self.mapping_diff, list):
            raise ValidationError({"mapping_diff": "Template differences must be a controlled list."})
        if self.status in self.LOCKED_STATUSES:
            if not self.submission_checksum or not self.submitted_at or not self.submitted_by_id:
                raise ValidationError("Submitted promotion requests require immutable evidence and a checksum.")
            if self.golden_result not in (self.GOLDEN_MATCHED, self.GOLDEN_REFERENCE):
                raise ValidationError("Resolve preview comparison differences before submitting this promotion.")
        if self.status in (self.APPROVED, self.ACTIVATED, self.ROLLED_BACK):
            if not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("Approved promotions require independent review evidence.")
            if self.reviewed_by_id in (self.created_by_id, self.submitted_by_id):
                raise ValidationError("The preparer or submitter cannot approve the same template promotion.")
        if self.status == self.ACTIVATED and (not self.activated_at or not self.activated_by_id):
            raise ValidationError("Active promotions require recorded activation evidence.")
        if self.status == self.ACTIVATED and not candidate.is_active:
            raise ValidationError("The activated candidate must be the active report template.")
        if self.status == self.ROLLED_BACK:
            if not self.baseline_template_id:
                raise ValidationError("A first official template has no earlier version to restore.")
            if not self.rolled_back_at or not self.rolled_back_by_id or not self.rollback_reason.strip():
                raise ValidationError("Rollback requires an actor, time, and reason.")
            if candidate.is_active or not self.baseline_template.is_active:
                raise ValidationError("Rollback must restore the prior template and deactivate the candidate.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "candidate_template_id", "baseline_template_id", "preview_run_id", "baseline_run_id",
                "change_reason", "comparison_note", "update_compatible_schedules", "template_snapshot",
                "template_checksum", "mapping_diff", "impact_snapshot", "golden_result",
                "golden_snapshot", "submission_checksum", "created_by_id",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted promotion evidence is immutable. Return it or create a new template version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists():
            raise ValidationError("Template-promotion history cannot be deleted.")
        return super().delete(*args, **kwargs)


class ReportTemplatePromotionEvent(models.Model):
    promotion = models.ForeignKey(
        ReportTemplatePromotion, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="report_template_promotion_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Template-promotion events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Template-promotion events cannot be deleted.")


class FinanceLocalFormAcceptance(models.Model):
    """Human-readable, evidence-backed acceptance record for one exact local form version."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable local-form record"),
        (SUBMITTED, "For independent acceptance review"),
        (RETURNED, "Returned for correction"),
        (ACCEPTED, "Locally accepted form"),
        (SUPERSEDED, "Superseded local form"),
    )
    LOCKED_STATUSES = {SUBMITTED, ACCEPTED, SUPERSEDED}

    SOURCE_UNMAPPED = "unmapped"
    SOURCE_REPORT = "report_template"
    SOURCE_FINANCE = "finance_workbook"
    SOURCE_CHOICES = (
        (SOURCE_UNMAPPED, "Inventory only — GRAND mapping still required"),
        (SOURCE_REPORT, "Governed report template"),
        (SOURCE_FINANCE, "Governed Finance workbook"),
    )
    DELIVERY_DIGITAL = "digital"
    DELIVERY_PRINT = "print"
    DELIVERY_BOTH = "both"
    DELIVERY_UNCONFIRMED = "unconfirmed"
    DELIVERY_CHOICES = (
        (DELIVERY_UNCONFIRMED, "Candidate starter — confirm locally"),
        (DELIVERY_DIGITAL, "Digital file only"),
        (DELIVERY_PRINT, "Printed or pre-printed form"),
        (DELIVERY_BOTH, "Digital file and printed copy"),
    )
    REFERENCE_CHOICES = (
        ("pdf", "PDF blank or redacted sample"),
        ("xlsx", "Macro-free Excel blank or redacted sample"),
        ("docx", "Word blank or redacted sample"),
        ("image", "Scanned/image reference"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_local_form_acceptances",
    )
    code = models.SlugField(max_length=80)
    version = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=180)
    form_number = models.CharField(
        max_length=120, blank=True,
        help_text="Use the familiar official or local form number only when the office has verified it.",
    )
    purpose = models.TextField()
    source_type = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=SOURCE_UNMAPPED)
    report_template = models.ForeignKey(
        ReportTemplateVersion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="local_form_acceptance_records",
    )
    finance_template = models.ForeignKey(
        "finance.FinanceTemplateVersion", on_delete=models.PROTECT, null=True, blank=True,
        related_name="local_form_acceptance_records",
    )
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="successor_forms",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    authority_reference = models.TextField(
        blank=True,
        help_text="Current COA, DBM, BIR, bank, ordinance, memorandum, or accepted local-procedure basis.",
    )
    local_acceptance_note = models.TextField(
        blank=True,
        help_text="Name the accepting office/person and the retained decision or comparison record.",
    )
    reference_kind = models.CharField(max_length=12, choices=REFERENCE_CHOICES, default="pdf")
    reference_file = models.FileField(
        upload_to=local_form_reference_path, max_length=500, blank=True,
        validators=[FileExtensionValidator(REFERENCE_EXTENSIONS)],
        help_text=(
            "Upload only a blank or safely redacted reference up to 10 MB. "
            "A candidate starter may remain blank while the office collects the current local copy."
        ),
    )
    reference_checksum = models.CharField(max_length=64, blank=True)
    delivery_mode = models.CharField(max_length=12, choices=DELIVERY_CHOICES, default=DELIVERY_BOTH)
    signatory_instructions = models.TextField(
        help_text="List the required signatory roles, order, acting/delegation rule, and wet/digital signature treatment.",
    )
    default_copy_count = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(50)],
    )
    recipient_instructions = models.TextField(
        help_text="State who receives each copy or digital file and how acknowledgement is retained.",
    )
    deadline_instructions = models.TextField(
        help_text="State the locally confirmed preparation, submission, filing, or distribution deadline basis.",
    )
    retention_instructions = models.TextField(
        help_text="State the records folder, custodian, retention rule, and confidential-copy handling.",
    )
    paper_size = models.CharField(
        max_length=20, blank=True,
        help_text="For example A4, Letter, Legal, or the exact pre-printed stock description.",
    )
    orientation = models.CharField(
        max_length=20, blank=True,
        help_text="For example Portrait or Landscape.",
    )
    form_stock = models.TextField(blank=True)
    printer_instructions = models.TextField(blank=True)
    pagination_instructions = models.TextField(
        help_text="Describe page numbering, repeating headings, annexes, and continuation-page treatment.",
    )
    overflow_instructions = models.TextField(
        help_text="Describe what happens when rows, particulars, notes, or signatures do not fit.",
    )
    accessibility_instructions = models.TextField(
        help_text="Describe readable labels/order, download format, scaling, and any accessibility accommodation.",
    )
    source_snapshot = models.JSONField(default=dict, blank=True)
    source_checksum = models.CharField(max_length=64, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    submission_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_local_form_acceptances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_local_form_acceptances",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_local_form_acceptances",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("department", "code", "version"), name="unique_local_form_acceptance_version",
            ),
            models.UniqueConstraint(
                fields=("department", "code"), condition=models.Q(status="accepted"),
                name="one_accepted_local_form_version",
            ),
        )
        permissions = (
            ("manage_local_form_acceptance", "Can prepare local Finance form acceptance records"),
            ("witness_local_form_tests", "Can independently witness local Finance form tests"),
            ("review_local_form_acceptance", "Can independently accept local Finance forms"),
            ("export_local_form_acceptance", "Can export accepted local Finance form evidence"),
        )

    def __str__(self):
        return f"{self.name} v{self.version}"

    def get_absolute_url(self):
        return reverse("reporting:local_form_detail", kwargs={"public_id": self.public_id})

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.reference_file and getattr(self.reference_file, "size", 0) > 10 * 1024 * 1024:
            raise ValidationError({"reference_file": "Local-form references must be 10 MB or smaller."})
        if self.reference_file:
            extension = self.reference_file.name.rsplit(".", 1)[-1].lower()
            allowed_by_kind = {
                "pdf": {"pdf"},
                "xlsx": {"xlsx", "xls"},
                "docx": {"docx"},
                "image": set(IMAGE_EXTENSIONS),
            }
            if extension not in allowed_by_kind.get(self.reference_kind, set()):
                raise ValidationError({
                    "reference_file":
                        f"The uploaded file must match the selected {self.get_reference_kind_display()} type."
                })
        if self.source_type == self.SOURCE_REPORT:
            if not self.report_template_id or self.finance_template_id:
                raise ValidationError("A governed report form must link only its exact report template version.")
            if self.report_template.definition.department_id != self.department_id:
                raise ValidationError({"report_template": "Choose a report template owned by this office."})
        elif self.source_type == self.SOURCE_FINANCE:
            if not self.finance_template_id or self.report_template_id:
                raise ValidationError("A governed Finance workbook must link only its exact workbook version.")
            if self.finance_template.department_id != self.department_id:
                raise ValidationError({"finance_template": "Choose a Finance workbook owned by this office."})
        elif self.report_template_id or self.finance_template_id:
            raise ValidationError("An inventory-only form cannot point to a runtime template until its mapping type is chosen.")
        if self.delivery_mode in (self.DELIVERY_PRINT, self.DELIVERY_BOTH):
            if not self.paper_size.strip() or not self.form_stock.strip() or not self.printer_instructions.strip():
                raise ValidationError("Printed forms require paper/stock and printer instructions.")
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "A local form cannot supersede itself."})
            if (
                self.supersedes.department_id != self.department_id
                or self.supersedes.code != self.code
                or self.version <= self.supersedes.version
            ):
                raise ValidationError({"supersedes": "Choose an earlier version of this office's same local form."})
        if self.status == self.ACCEPTED:
            if not self.submission_checksum or not self.reviewed_by_id or not self.reviewed_at:
                raise ValidationError("Accepted forms require a pinned submission and independent review.")
            if self.reviewed_by_id in (self.created_by_id, self.submitted_by_id):
                raise ValidationError("The form preparer or submitter cannot accept the same form.")
        if self.status in (self.SUBMITTED, self.ACCEPTED, self.SUPERSEDED):
            if not self.submission_checksum or not self.submitted_by_id or not self.submitted_at:
                raise ValidationError("Locked local-form states require a pinned, attributable submission.")
        if self.status == self.SUPERSEDED and (
            not self.reviewed_by_id or not self.reviewed_at
        ):
            raise ValidationError("Superseded forms must retain their original independent acceptance.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            allowed_transitions = {
                self.DRAFT: {self.SUBMITTED},
                self.RETURNED: {self.SUBMITTED},
                self.SUBMITTED: {self.RETURNED, self.ACCEPTED},
                self.ACCEPTED: {self.SUPERSEDED},
                self.SUPERSEDED: set(),
            }
            if (
                prior.status != self.status
                and self.status not in allowed_transitions.get(prior.status, set())
            ):
                raise ValidationError(
                    f"Local-form status cannot move from {prior.status} to {self.status}; use the governed action."
                )
            governed = (
                "department_id", "code", "version", "name", "form_number", "purpose",
                "source_type", "report_template_id", "finance_template_id", "supersedes_id",
                "authority_reference", "local_acceptance_note", "reference_kind",
                "reference_checksum", "delivery_mode", "signatory_instructions",
                "default_copy_count", "recipient_instructions", "deadline_instructions",
                "retention_instructions", "paper_size", "orientation", "form_stock",
                "printer_instructions", "pagination_instructions", "overflow_instructions",
                "accessibility_instructions", "source_snapshot", "source_checksum",
                "submission_snapshot", "submission_checksum", "created_by_id",
            )
            changed = any(getattr(prior, field) != getattr(self, field) for field in governed)
            changed = changed or prior.reference_file.name != self.reference_file.name
            if prior.status in self.LOCKED_STATUSES and changed:
                raise ValidationError("Submitted local-form evidence is immutable. Return it or create a successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.events.exists() or self.test_attempts.exists():
            raise ValidationError("Local-form acceptance history cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceLocalFormSection(models.Model):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"
    REPEATING = "repeating"
    SECTION_CHOICES = (
        (REQUIRED, "Required section"),
        (OPTIONAL, "Optional section"),
        (CONDITIONAL, "Conditional section"),
        (REPEATING, "Repeating rows or continuation section"),
    )

    STARTER_CANDIDATE = "candidate"
    LOCAL_ENTRY = "local_entry"
    STARTER_CONFIRMED = "confirmed"
    STARTER_NOT_APPLICABLE = "not_applicable"
    CONFIRMATION_CHOICES = (
        (STARTER_CANDIDATE, "Candidate starter — confirm locally"),
        (LOCAL_ENTRY, "Entered from the current local form"),
        (STARTER_CONFIRMED, "Starter row matched to the current local form"),
        (STARTER_NOT_APPLICABLE, "Starter row documented as not applicable"),
    )

    form = models.ForeignKey(
        FinanceLocalFormAcceptance, on_delete=models.PROTECT, related_name="sections",
    )
    position = models.PositiveSmallIntegerField()
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    requirement_type = models.CharField(max_length=16, choices=SECTION_CHOICES, default=REQUIRED)
    applicability_instructions = models.TextField(
        blank=True,
        help_text="For optional or conditional sections, state who decides and what retained fact makes the section apply.",
    )
    row_instructions = models.TextField(
        blank=True,
        help_text="For repeating content, state the minimum/maximum rows and continuation-page behavior.",
    )
    field_instructions = models.TextField(
        blank=True,
        help_text="List the familiar fields or column group employees expect in this section.",
    )
    source_instructions = models.TextField(
        blank=True,
        help_text="Name the governed GRAND record or retained source that supplies this section.",
    )
    control_instructions = models.TextField(
        blank=True,
        help_text="Explain totals, cross-checks, limits, and other observable validation rules.",
    )
    owner_instructions = models.TextField(
        blank=True,
        help_text="Name the office/role that prepares, reviews, signs, or keeps this section.",
    )
    print_instructions = models.TextField(
        blank=True,
        help_text="Explain headings, page breaks, continuation, amount format, and signature space.",
    )
    starter_reference = models.CharField(
        max_length=120, blank=True,
        help_text="Official-source page anchor supplied by a built-in candidate starter.",
    )
    confirmation_status = models.CharField(
        max_length=20, choices=CONFIRMATION_CHOICES, default=LOCAL_ENTRY,
    )
    local_confirmation_reference = models.TextField(
        blank=True,
        help_text=(
            "For a built-in starter row, cite the current local form, page/section, comparison, "
            "or decision that confirms or excludes it."
        ),
    )

    class Meta:
        ordering = ("position", "pk")
        constraints = (
            models.UniqueConstraint(fields=("form", "position"), name="unique_local_form_section_position"),
            models.UniqueConstraint(fields=("form", "code"), name="unique_local_form_section_code"),
        )

    def __str__(self):
        return f"{self.form}: {self.label}"

    def clean(self):
        if self.requirement_type in (self.OPTIONAL, self.CONDITIONAL) and not self.applicability_instructions.strip():
            raise ValidationError({"applicability_instructions": "Explain when this non-required section applies and who decides."})
        if self.requirement_type == self.REPEATING and not self.row_instructions.strip():
            raise ValidationError({"row_instructions": "Explain the repeating-row and continuation-page behavior."})
        if (
            self.starter_reference
            and self.confirmation_status in (self.STARTER_CONFIRMED, self.STARTER_NOT_APPLICABLE)
            and not self.local_confirmation_reference.strip()
        ):
            raise ValidationError({
                "local_confirmation_reference":
                    "Cite the retained local form, comparison, or decision for this starter-row outcome."
            })

    def save(self, *args, **kwargs):
        if self.form_id and not self.form.is_editable:
            raise ValidationError("Locked local-form sections are immutable. Create a successor form.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.form.is_editable:
            raise ValidationError("Locked local-form sections cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceLocalFormTestAttempt(models.Model):
    DATA_CONTROL = "data_control"
    LAYOUT_FIELDS = "layout_fields"
    SIGNATORY_ROUTE = "signatory_route"
    OVERFLOW_PAGINATION = "overflow_pagination"
    ACCESS_DOWNLOAD = "access_download"
    PRINTER_STOCK = "printer_stock"
    ROLLBACK_RECOVERY = "rollback_recovery"
    CATEGORY_CHOICES = (
        (DATA_CONTROL, "Data and control totals"),
        (LAYOUT_FIELDS, "Labels, fields, and visual comparison"),
        (SIGNATORY_ROUTE, "Signatories, copies, recipients, and custody route"),
        (OVERFLOW_PAGINATION, "Overflow, pagination, and continuation pages"),
        (ACCESS_DOWNLOAD, "Accessibility, download, and readable output"),
        (PRINTER_STOCK, "Physical printer and form-stock trial"),
        (ROLLBACK_RECOVERY, "Rollback and recoverable prior-version drill"),
    )
    REQUIRED_CATEGORIES = tuple(value for value, _label in CATEGORY_CHOICES)

    SUBMITTED = "submitted"
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    STATUS_CHOICES = (
        (SUBMITTED, "Awaiting independent witness"),
        (PASSED, "Witnessed pass"),
        (FAILED, "Witnessed failure — new attempt required"),
        (NOT_APPLICABLE, "Witnessed not applicable"),
    )

    form = models.ForeignKey(
        FinanceLocalFormAcceptance, on_delete=models.PROTECT, related_name="test_attempts",
    )
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES)
    attempt = models.PositiveSmallIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="successor_attempt",
    )
    change_reason = models.TextField(blank=True)
    test_steps = models.TextField()
    expected_result = models.TextField()
    observed_result = models.TextField()
    environment = models.TextField(
        help_text="Name the browser/device, output format, printer/paper when applicable, and useful settings.",
    )
    evidence_reference = models.TextField(
        help_text="Reference the retained redacted output, comparison sheet, print sample, screenshot, or drill record.",
    )
    evidence_checksum = models.CharField(max_length=64)
    basis_snapshot = models.JSONField(default=dict)
    basis_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=SUBMITTED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_local_form_tests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_local_form_tests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ("category", "-attempt")
        constraints = (
            models.UniqueConstraint(fields=("form", "category", "attempt"), name="unique_local_form_test_attempt"),
        )

    def __str__(self):
        return f"{self.form}: {self.get_category_display()} attempt {self.attempt}"

    def clean(self):
        if self.supersedes_id:
            if (
                self.supersedes.form_id != self.form_id
                or self.supersedes.category != self.category
                or self.attempt <= self.supersedes.attempt
            ):
                raise ValidationError({"supersedes": "Choose an earlier attempt for this same form and test category."})
            if not self.change_reason.strip():
                raise ValidationError({"change_reason": "Explain why another test attempt is required."})
        if self.status != self.SUBMITTED:
            if not self.reviewed_by_id or not self.reviewed_at or not self.review_note.strip():
                raise ValidationError("A witnessed test result requires reviewer, time, and decision note.")
            if self.reviewed_by_id == self.created_by_id:
                raise ValidationError("The person who performed the test cannot witness the same attempt.")
        if self.status == self.NOT_APPLICABLE and (
            self.category != self.PRINTER_STOCK or self.form.delivery_mode != FinanceLocalFormAcceptance.DELIVERY_DIGITAL
        ):
            raise ValidationError("Only a printer/form-stock test for a digital-only form may be marked not applicable.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "form_id", "category", "attempt", "supersedes_id", "change_reason",
                "test_steps", "expected_result", "observed_result", "environment",
                "evidence_reference", "evidence_checksum", "basis_snapshot",
                "basis_checksum", "created_by_id", "created_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("Local-form test attempts are immutable. Record a reasoned successor attempt.")
            if prior.status != self.SUBMITTED or self.status not in (self.PASSED, self.FAILED, self.NOT_APPLICABLE):
                raise ValidationError("A test attempt may move only once from submitted to a witnessed result.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Local-form test-attempt history cannot be deleted.")


class FinanceLocalFormEvent(models.Model):
    form = models.ForeignKey(
        FinanceLocalFormAcceptance, on_delete=models.PROTECT, related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="finance_local_form_events",
    )
    action = models.CharField(max_length=60)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Local-form acceptance events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Local-form acceptance events cannot be deleted.")
