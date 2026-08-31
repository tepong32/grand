from django import forms
from django.utils import timezone
from django.utils.text import slugify

from accounting.models import LedgerAccount

from .datasets import DATASETS, available_datasets, dataset_registry
from .models import (
    FinanceStatementLine, FinanceStatementMapping, FinanceStatementNote,
    FinanceStatementNoteSet, ReportDefinition, ReportReferenceComparison, ReportRun,
    ReportSchedule, ReportTemplateMappingField, ReportTemplatePromotion, ReportTemplateVersion,
)
from .statement_services import comparison_controls, create_note_set


class FinanceStatementMappingForm(forms.ModelForm):
    class Meta:
        model = FinanceStatementMapping
        fields = (
            "statement_type", "title", "description", "authority_reference", "local_acceptance_note",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department=None, user=None, **kwargs):
        self.department, self.user = department, user
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["statement_type"].disabled = True

    def save(self, commit=True):
        mapping = super().save(commit=False)
        if not mapping.pk:
            mapping.department = self.department
            mapping.created_by = self.user
            mapping.version = (
                FinanceStatementMapping.objects.filter(
                    department=self.department, statement_type=mapping.statement_type,
                ).order_by("-version").values_list("version", flat=True).first() or 0
            ) + 1
            mapping.supersedes = FinanceStatementMapping.objects.filter(
                department=self.department, statement_type=mapping.statement_type,
                status__in=(FinanceStatementMapping.ACTIVE, FinanceStatementMapping.STARTER),
            ).order_by("-version").first()
        if commit:
            mapping.full_clean()
            mapping.save()
        return mapping


class FinanceStatementLineForm(forms.ModelForm):
    account_codes = forms.MultipleChoiceField(
        choices=(), required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Used only when ‘Selected account codes’ is chosen.",
    )

    class Meta:
        model = FinanceStatementLine
        fields = (
            "position", "section_code", "section_title", "line_code", "line_title",
            "selector_type", "account_type", "account_codes",
        )

    def __init__(self, *args, mapping=None, **kwargs):
        self.mapping = mapping
        super().__init__(*args, **kwargs)
        accounts = LedgerAccount.objects.filter(
            department_id=mapping.department_id, is_active=True, allow_posting=True,
        ).order_by("code")
        self.fields["account_codes"].choices = [
            (account.code, f"{account.code} — {account.title}") for account in accounts
        ]

    def save(self, commit=True):
        line = super().save(commit=False)
        line.mapping = self.mapping
        line.account_codes = list(self.cleaned_data.get("account_codes") or [])
        if commit:
            line.save()
        return line


class FinanceStatementNoteSetForm(forms.ModelForm):
    class Meta:
        model = FinanceStatementNoteSet
        fields = (
            "title", "position_run", "performance_run", "applicability_status",
            "preparation_note", "authority_reference", "local_acceptance_note",
        )
        widgets = {
            "preparation_note": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department=None, user=None, **kwargs):
        self.department, self.user = department, user
        super().__init__(*args, **kwargs)
        base = ReportRun.objects.filter(
            definition__department=department,
            status__in=(ReportRun.GENERATED, ReportRun.REVIEWED, ReportRun.APPROVED),
            control_status=ReportRun.CONTROL_RECONCILED,
        ).select_related("definition").order_by("-period_end", "-created_at")
        self.fields["position_run"].queryset = base.filter(
            definition__dataset_key="finance_statement_position",
        )
        self.fields["performance_run"].queryset = base.filter(
            definition__dataset_key="finance_statement_performance",
        )
        self.fields["position_run"].label_from_instance = lambda run: (
            f"{run.period_start:%b %d, %Y} to {run.period_end:%b %d, %Y} · "
            f"{run.get_status_display()} · {str(run.public_id)[:8]}"
        )
        self.fields["performance_run"].label_from_instance = self.fields["position_run"].label_from_instance
        self.fields["applicability_status"].help_text = (
            "Keep Candidate until the current authority, exact local note package, and retained acceptance evidence are confirmed."
        )
        if self.instance.pk and not self.instance.is_editable:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        cleaned = super().clean()
        position = cleaned.get("position_run")
        performance = cleaned.get("performance_run")
        if position and performance and (
            position.period_start != performance.period_start or position.period_end != performance.period_end
        ):
            raise forms.ValidationError("Choose position and performance runs for the exact same period.")
        if cleaned.get("applicability_status") == FinanceStatementNoteSet.CONFIRMED:
            if not (cleaned.get("authority_reference") or "").strip():
                self.add_error("authority_reference", "Record the reviewed current authority before local confirmation.")
            if not (cleaned.get("local_acceptance_note") or "").strip():
                self.add_error("local_acceptance_note", "Record who accepted the local note package and where evidence is retained.")
        return cleaned

    def save(self, commit=True):
        if self.instance.pk:
            note_set = super().save(commit=False)
            if commit:
                note_set.full_clean()
                note_set.save()
            return note_set
        if not commit:
            raise ValueError("New statement-note packages must be created atomically.")
        return create_note_set(
            department=self.department,
            position_run=self.cleaned_data["position_run"],
            performance_run=self.cleaned_data["performance_run"],
            actor=self.user,
            data=self.cleaned_data,
        )


class FinanceStatementNoteForm(forms.ModelForm):
    related_line_codes = forms.MultipleChoiceField(
        choices=(), required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Optionally link this disclosure to the exact lines pinned in the two statement runs.",
    )

    class Meta:
        model = FinanceStatementNote
        fields = (
            "position", "topic_code", "title", "related_statement", "related_line_codes",
            "disclosure_text", "source_reference", "authority_basis",
            "is_not_applicable", "not_applicable_reason",
        )
        widgets = {
            "disclosure_text": forms.Textarea(attrs={"rows": 7}),
            "source_reference": forms.Textarea(attrs={"rows": 2}),
            "authority_basis": forms.Textarea(attrs={"rows": 2}),
            "not_applicable_reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, note_set=None, **kwargs):
        self.note_set = note_set
        super().__init__(*args, **kwargs)
        choices = []
        seen = set()
        for label, run in (("Position", note_set.position_run), ("Performance", note_set.performance_run)):
            snapshot = run.parameters.get("_statement_mapping_snapshot", {})
            for item in snapshot.get("lines", []):
                code = item.get("line_code")
                if code and code not in seen:
                    seen.add(code)
                    choices.append((code, f"{label} · {item.get('line_title') or code}"))
        self.fields["related_line_codes"].choices = choices
        if self.instance.pk:
            self.initial["related_line_codes"] = list(self.instance.related_line_codes or [])

    def save(self, commit=True):
        item = super().save(commit=False)
        item.note_set = self.note_set
        item.related_line_codes = list(self.cleaned_data.get("related_line_codes") or [])
        if commit:
            item.save()
        return item


class ReportReferenceComparisonForm(forms.ModelForm):
    class Meta:
        model = ReportReferenceComparison
        fields = (
            "reference_label", "reference_kind", "reference_file", "signed_copy",
            "redaction_confirmed", "authority_reference", "local_acceptance_note",
        )
        widgets = {
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, run=None, user=None, **kwargs):
        self.run, self.user = run, user
        super().__init__(*args, **kwargs)
        self.fields["signed_copy"].help_text = "Confirm this is the signed copy used by the office for comparison."
        self.fields["redaction_confirmed"].help_text = (
            "Confirm confidential taxpayer, payee, employee, bank, and signature-image details were removed before upload."
        )
        if self.instance.pk:
            self.fields["reference_file"].required = False
        for key, label in comparison_controls(run):
            self.fields[f"control_{key}"] = forms.DecimalField(
                label=f"Reference total — {label}", max_digits=18, decimal_places=2,
                initial=(self.instance.reference_values or {}).get(key) if self.instance.pk else None,
                help_text="Enter the amount shown on the retained reference copy.",
            )

    def clean(self):
        cleaned = super().clean()
        cleaned["reference_values"] = {
            key: str(cleaned[f"control_{key}"]) for key, _label in comparison_controls(self.run)
            if cleaned.get(f"control_{key}") is not None
        }
        return cleaned

    def save(self, commit=True):
        comparison = super().save(commit=False)
        comparison.run = self.run
        comparison.reference_values = self.cleaned_data["reference_values"]
        if not comparison.pk:
            comparison.created_by = self.user
            comparison.version = (
                ReportReferenceComparison.objects.filter(run=self.run).order_by("-version")
                .values_list("version", flat=True).first() or 0
            ) + 1
        if commit:
            comparison.full_clean()
            comparison.save()
        return comparison


class ReportDefinitionForm(forms.ModelForm):
    dataset_key = forms.ChoiceField(choices=[])
    selected_fields = forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple)
    group_by = forms.MultipleChoiceField(choices=[], required=False, widget=forms.CheckboxSelectMultiple, help_text="Combine rows that share these values.")
    totals = forms.MultipleChoiceField(choices=[], required=False, widget=forms.CheckboxSelectMultiple, help_text="Add numeric values when rows are grouped and show a final total.")
    sort_by = forms.MultipleChoiceField(choices=[], required=False, help_text="Apply selected ordering from top to bottom.")
    filter_field = forms.ChoiceField(choices=[], required=False)
    filter_operator = forms.ChoiceField(choices=(("exact", "Equals"), ("contains", "Contains"), ("in", "Is one of (comma-separated)")), required=False)
    filter_value = forms.CharField(required=False, help_text="Leave blank for no additional filter.")

    class Meta:
        model = ReportDefinition
        fields = (
            "name", "description", "dataset_key", "selected_fields", "group_by", "totals",
            "sort_by", "default_format", "applicability_status", "authority_reference",
            "local_acceptance_note", "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department=None, user=None, **kwargs):
        self.department = department
        self.user = user
        super().__init__(*args, **kwargs)
        datasets = available_datasets(department)
        self.fields["dataset_key"].choices = [(dataset.key, dataset.label) for dataset in datasets]
        requested_dataset = self.data.get("dataset_key") or getattr(self.instance, "dataset_key", "") or (datasets[0].key if datasets else "")
        adapter = dataset_registry.get(requested_dataset)
        if not adapter or not adapter.supports_department(department):
            adapter = datasets[0] if datasets else None
        columns = adapter.columns if adapter else ()
        field_choices = [(column.key, column.label) for column in columns]
        self.fields["selected_fields"].choices = field_choices
        self.fields["group_by"].choices = field_choices
        self.fields["totals"].choices = [
            (column.key, column.label) for column in columns if column.kind in ("integer", "decimal")
        ]
        self.fields["sort_by"].choices = [(column.key, f"{column.label} - ascending") for column in columns] + [(f"-{column.key}", f"{column.label} - descending") for column in columns]
        self.fields["filter_field"].choices = [("", "No additional filter")] + field_choices
        if self.instance.pk and self.instance.filters:
            key, value = next(iter(self.instance.filters.items()))
            field, _, operator = key.partition("__")
            self.fields["filter_field"].initial = field
            self.fields["filter_operator"].initial = operator or "exact"
            self.fields["filter_value"].initial = ", ".join(map(str, value)) if isinstance(value, list) else value

    def clean_selected_fields(self):
        selected = self.cleaned_data["selected_fields"]
        adapter = dataset_registry[self.cleaned_data.get("dataset_key", DATASETS[0].key)]
        if set(selected) - set(adapter.column_keys):
            raise forms.ValidationError("Select only fields exposed by the approved dataset.")
        return selected

    def _configured_filters(self):
        filter_field = self.cleaned_data.get("filter_field")
        filter_value = self.cleaned_data.get("filter_value", "").strip()
        operator = self.cleaned_data.get("filter_operator") or "exact"
        if not filter_field or not filter_value:
            return {}
        value = [item.strip() for item in filter_value.split(",") if item.strip()] if operator == "in" else filter_value
        return {f"{filter_field}__{operator}": value}

    def clean(self):
        cleaned = super().clean()
        self.instance.filters = self._configured_filters()
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.department = self.department
        instance.slug = slugify(instance.name)
        if not instance.pk:
            instance.created_by = self.user
        instance.updated_by = self.user
        instance.filters = self._configured_filters()
        if commit:
            instance.full_clean()
            instance.save()
        return instance


class ReportTemplateVersionForm(forms.ModelForm):
    prepared_by = forms.CharField(required=False, help_text="Name or office title shown in the prepared-by line.")
    reviewed_by = forms.CharField(required=False, help_text="Name or office title shown in the reviewed-by line.")
    approved_by = forms.CharField(required=False, help_text="Name or office title shown in the approved-by line.")

    class Meta:
        model = ReportTemplateVersion
        fields = (
            "title", "header_text", "certification_text", "footer_text", "document_control_prefix",
            "page_size", "orientation", "margin_mm", "page_border", "repeat_header", "show_footer",
            "show_page_numbers", "show_document_control", "primary_logo", "secondary_logo",
            "render_mode", "reference_kind", "reference_file", "mapping_notes",
        )
        widgets = {
            "certification_text": forms.Textarea(attrs={"rows": 3}),
            "mapping_notes": forms.Textarea(attrs={"rows": 4}),
            "primary_logo": forms.ClearableFileInput(attrs={"accept": ".png,.jpg,.jpeg"}),
            "secondary_logo": forms.ClearableFileInput(attrs={"accept": ".png,.jpg,.jpeg"}),
            "reference_file": forms.ClearableFileInput(attrs={"accept": ".pdf,.xlsx,.xls,.docx,.png,.jpg,.jpeg"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.signatories = [
            {"role": label, "name": self.cleaned_data[field]}
            for field, label in (("prepared_by", "Prepared by"), ("reviewed_by", "Reviewed by"), ("approved_by", "Approved by"))
            if self.cleaned_data.get(field)
        ]
        if commit:
            instance.save()
        return instance


class ReportTemplatePromotionForm(forms.Form):
    period_start = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Use the exact period covered by the signed sample or accepted golden output.",
    )
    period_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    output_format = forms.ChoiceField(choices=ReportDefinition.FORMAT_CHOICES)
    baseline_run = forms.ModelChoiceField(
        queryset=ReportRun.objects.none(), required=False,
        label="Accepted prior output for automatic comparison",
        help_text="Required when this report already has an active official template. Choose the same period and file format.",
    )
    change_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Why this layout version is needed",
    )
    comparison_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Department comparison and practical checks",
        help_text=(
            "Describe the blank/redacted form used, side-by-side fields and totals, signatories, page count, "
            "overflow, form stock or printer alignment, and who can inspect the retained evidence."
        ),
    )
    update_compatible_schedules = forms.BooleanField(
        required=False,
        label="Move compatible active schedules to this version when it is activated",
    )

    def __init__(self, *args, template=None, **kwargs):
        self.template = template
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["period_start"].initial = today.replace(day=1)
        self.fields["period_end"].initial = today
        self.fields["output_format"].choices = [
            choice for choice in ReportDefinition.FORMAT_CHOICES
            if template.supports_format(choice[0])
        ]
        self.fields["output_format"].initial = template.definition.default_format
        self.fields["baseline_run"].queryset = ReportRun.objects.filter(
            definition=template.definition,
            status=ReportRun.APPROVED,
            template_version__is_active=True,
            template_version__fidelity_status=ReportTemplateVersion.OFFICIAL,
            template_version__fidelity_validated_at__isnull=False,
        ).exclude(template_version=template).select_related("template_version")
        self.fields["baseline_run"].label_from_instance = lambda run: (
            f"{run.period_start} to {run.period_end} · {run.output_format.upper()} · "
            f"template v{run.template_version.version} · {str(run.public_id)[:8]}"
        )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "The comparison period cannot end before it starts.")
        baseline = cleaned.get("baseline_run")
        if baseline and start and end:
            if (baseline.period_start, baseline.period_end, baseline.output_format) != (
                start, end, cleaned.get("output_format"),
            ):
                self.add_error(
                    "baseline_run",
                    "Choose an accepted output with the same period and file format as this preview.",
                )
        active = self.template.definition.template_versions.filter(
            is_active=True,
            approved_at__isnull=False,
            fidelity_status=ReportTemplateVersion.OFFICIAL,
            fidelity_validated_at__isnull=False,
        ).exclude(pk=self.template.pk).first()
        if active and not baseline:
            self.add_error(
                "baseline_run",
                "This report already has an active official layout. Choose its accepted output for the golden comparison.",
            )
        return cleaned


class ManualReportForm(forms.Form):
    period_start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    output_format = forms.ChoiceField(choices=ReportDefinition.FORMAT_CHOICES)
    template_version = forms.ModelChoiceField(queryset=ReportTemplateVersion.objects.none())

    def __init__(self, *args, definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["period_start"].initial = today.replace(day=1)
        self.fields["period_end"].initial = today
        self.fields["output_format"].initial = definition.default_format
        self.fields["template_version"].queryset = definition.template_versions.filter(is_active=True, approved_at__isnull=False)
        self.fields["template_version"].initial = definition.current_template

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("period_start") and cleaned.get("period_end") and cleaned["period_end"] < cleaned["period_start"]:
            self.add_error("period_end", "The reporting period cannot end before it starts.")
        template = cleaned.get("template_version")
        output_format = cleaned.get("output_format")
        if template and output_format and not template.supports_format(output_format):
            self.add_error("output_format", "Choose the output format supported by this template.")
        if template and not template.is_mapping_ready:
            self.add_error("template_version", "This mapped template must pass preflight before it can generate reports.")
        return cleaned


class ReportTemplateMappingFieldForm(forms.ModelForm):
    class Meta:
        model = ReportTemplateMappingField
        fields = ("source_key", "page_number", "x_mm", "y_mm", "width_mm", "font_size", "alignment", "repeat_for_rows", "row_height_mm", "max_rows", "display_order")

    def __init__(self, *args, template_version=None, **kwargs):
        self.template_version = template_version
        super().__init__(*args, **kwargs)
        metadata = (
            ("header", "Department header"), ("title", "Report title"), ("period", "Covered period"),
            ("period_start", "Period start"), ("period_end", "Period end"),
            ("control_id", "Document control ID"), ("row_count", "Row count"),
        )
        adapter = dataset_registry[template_version.definition.dataset_key]
        column_labels = {column.key: column.label for column in adapter.columns}
        dataset = [(key, column_labels.get(key, key.replace("_", " ").title())) for key in template_version.definition.selected_fields]
        totals = [(f"total:{key}", f"Total: {column_labels.get(key, key)}") for key in template_version.definition.totals or []]
        self.fields["source_key"] = forms.ChoiceField(choices=list(metadata) + dataset + totals)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.template_version = self.template_version
        if commit:
            instance.save()
        return instance


class ReportScheduleForm(forms.ModelForm):
    class Meta:
        model = ReportSchedule
        fields = ("definition", "template_version", "name", "frequency", "output_format", "next_run_at", "is_active")
        widgets = {"next_run_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}

    def __init__(self, *args, department=None, user=None, **kwargs):
        self.department, self.user = department, user
        super().__init__(*args, **kwargs)
        self.fields["definition"].queryset = ReportDefinition.objects.filter(department=department, is_active=True)
        self.fields["template_version"].queryset = ReportTemplateVersion.objects.filter(definition__department=department, is_active=True, approved_at__isnull=False)

    def clean(self):
        cleaned = super().clean()
        template = cleaned.get("template_version")
        if template and not template.is_mapping_ready:
            self.add_error("template_version", "This mapped template must pass preflight before it can be scheduled.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        if commit:
            instance.full_clean()
            instance.save()
        return instance
