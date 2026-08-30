import json

from django import forms

from .models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceDocumentRule, FinanceNumberingSequence,
    FinanceParty, FinancePartyClaimant, FinanceSignatory, FinanceTemplateVersion,
    FinanceTransactionVariant,
)


class DateInput(forms.DateInput):
    input_type = "date"


class FinanceReleaseForm(forms.ModelForm):
    class Meta:
        model = FinanceConfigurationRelease
        fields = ("code", "version", "title", "fiscal_year", "effective_from", "effective_to")
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}


class FinanceItemForm(forms.ModelForm):
    configuration_json = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 7}),
        help_text='JSON object with reviewed, category-specific values. Example: {"requires_obr": true}.',
    )

    class Meta:
        model = FinanceConfigurationItem
        fields = ("release", "category", "code", "version", "label", "description", "effective_from", "effective_to", "supersedes")
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")
            self.fields["supersedes"].queryset = FinanceConfigurationItem.objects.filter(department=department).exclude(status="draft")
        if self.instance.pk:
            self.fields["configuration_json"].initial = json.dumps(self.instance.configuration, indent=2, sort_keys=True)

    def clean_configuration_json(self):
        raw = self.cleaned_data["configuration_json"] or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Enter valid JSON: {exc.msg}.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("Configuration must be a JSON object.")
        return value

    def save(self, commit=True):
        instance = super().save(False)
        instance.configuration = self.cleaned_data["configuration_json"]
        if commit:
            instance.save()
        return instance


class FinanceTransactionVariantForm(forms.ModelForm):
    class Meta:
        model = FinanceTransactionVariant
        fields = (
            "release", "code", "label", "kind", "description", "authority_reference",
            "effective_from", "effective_to",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "effective_from": DateInput(), "effective_to": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(
                department=department, status="draft",
            )


class FinanceDocumentRuleForm(forms.ModelForm):
    class Meta:
        model = FinanceDocumentRule
        fields = (
            "variant", "code", "label", "evidence_kind", "required", "waiver_allowed",
            "condition_description", "authority_reference", "display_order",
        )
        widgets = {
            "condition_description": forms.Textarea(attrs={"rows": 2}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.fields["variant"].queryset = FinanceTransactionVariant.objects.filter(
                department=department, release__status="draft",
            ).select_related("release").order_by("release", "label")


class FinanceTemplateForm(forms.ModelForm):
    class Meta:
        model = FinanceTemplateVersion
        fields = (
            "release", "document_type", "version", "title", "form_reference",
            "authority_reference", "comparison_reference", "form_status",
            "paper_size", "orientation", "default_copy_count", "printer_instructions",
            "controlled_print_required", "workbook", "effective_from", "effective_to",
        )
        widgets = {
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "comparison_reference": forms.Textarea(attrs={"rows": 3}),
            "printer_instructions": forms.Textarea(attrs={"rows": 3}),
            "effective_from": DateInput(), "effective_to": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        if not workbook.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Upload a macro-free .xlsx workbook only.")
        return workbook


class FinanceSignatoryForm(forms.ModelForm):
    class Meta:
        model = FinanceSignatory
        fields = (
            "release", "role_code", "display_name", "position_title", "acting",
            "custody_department", "custody_instructions", "valid_from", "valid_to",
        )
        widgets = {
            "custody_instructions": forms.Textarea(attrs={"rows": 2}),
            "valid_from": DateInput(), "valid_to": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")


class FinanceStarterTemplateForm(forms.Form):
    lgu_name = forms.CharField(
        max_length=180,
        label="Local government name",
        help_text="Example: Municipality of Sample. This remains editable in Excel.",
    )
    finance_office_name = forms.CharField(max_length=180, initial="Accounting Office")
    form_title = forms.CharField(max_length=180, initial="DISBURSEMENT VOUCHER")
    form_reference = forms.CharField(
        max_length=180,
        initial="Editable starter — verify current local form",
        help_text="Enter a form number only after the municipality confirms it.",
    )
    paper_size = forms.ChoiceField(choices=FinanceTemplateVersion.PAPER_SIZE_CHOICES, initial="a4")
    orientation = forms.ChoiceField(choices=FinanceTemplateVersion.ORIENTATION_CHOICES, initial="portrait")
    particulars_rows = forms.IntegerField(
        min_value=4, max_value=24, initial=8,
        label="Rows for particulars",
        help_text="More rows make the form longer; the uploaded version will be checked before use.",
    )
    default_copy_count = forms.IntegerField(min_value=1, max_value=10, initial=2, label="Usual number of copies")
    prepared_label = forms.CharField(max_length=120, initial="Prepared by")
    certified_label = forms.CharField(max_length=120, initial="Certified / reviewed by")
    approved_label = forms.CharField(max_length=120, initial="Approved for payment by")
    footer_note = forms.CharField(
        required=False,
        initial="STARTER FOR LOCAL REVIEW — compare with the current approved blank form before official use.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class FinanceNumberingSequenceForm(forms.ModelForm):
    class Meta:
        model = FinanceNumberingSequence
        fields = ("release", "fiscal_year", "document_type", "prefix", "padding", "next_number")

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")


class FinancePartyForm(forms.ModelForm):
    class Meta:
        model = FinanceParty
        fields = (
            "release", "code", "version", "display_name", "party_type", "address",
            "tax_identifier", "effective_from", "effective_to", "supersedes",
        )
        widgets = {"effective_from": DateInput(), "effective_to": DateInput(), "address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")
            self.fields["supersedes"].queryset = FinanceParty.objects.filter(department=department).exclude(status="draft")


class FinancePartyClaimantForm(forms.ModelForm):
    class Meta:
        model = FinancePartyClaimant
        fields = ("display_name", "relationship", "valid_from", "valid_to")
        widgets = {"valid_from": DateInput(), "valid_to": DateInput()}
