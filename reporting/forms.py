from django import forms
from django.utils import timezone
from django.utils.text import slugify

from .datasets import DATASETS, available_datasets, dataset_registry
from .models import ReportDefinition, ReportSchedule, ReportTemplateMappingField, ReportTemplateVersion


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
        fields = ("name", "description", "dataset_key", "selected_fields", "group_by", "totals", "sort_by", "default_format", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

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
        self.fields["totals"].choices = [(column.key, column.label) for column in columns if column.kind == "integer"]
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
