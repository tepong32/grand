import json

from django import forms

from .models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceNumberingSequence,
    FinanceParty, FinancePartyClaimant, FinanceSignatory, FinanceTemplateVersion,
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


class FinanceTemplateForm(forms.ModelForm):
    class Meta:
        model = FinanceTemplateVersion
        fields = ("release", "document_type", "version", "title", "workbook", "effective_from", "effective_to")
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}

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
        fields = ("release", "role_code", "display_name", "position_title", "acting", "valid_from", "valid_to")
        widgets = {"valid_from": DateInput(), "valid_to": DateInput()}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")


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
