from django import forms
from django.contrib.auth import get_user_model

from .models import DepartmentRecord


class DepartmentRecordForm(forms.ModelForm):
    source_type = forms.CharField(required=False, widget=forms.HiddenInput)
    source_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    initial_file = forms.FileField(required=False, help_text="Optional supporting file. Approved operational files can instead be linked without duplication.")
    file_description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = DepartmentRecord
        fields = ("title", "description", "classification", "confidentiality", "custodian", "retention_years", "retention_notes")
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "retention_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["custodian"].queryset = get_user_model().objects.filter(employeeprofile__assigned_department=department, is_active=True).order_by("last_name", "first_name", "username")
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs["class"] = "form-control"


class RecordFileForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={"class": "form-control"}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))


class RetentionForm(forms.ModelForm):
    class Meta:
        model = DepartmentRecord
        fields = ("retention_years", "retention_notes", "retention_start_date", "disposition_due_date", "legal_hold")
        widgets = {
            "retention_notes": forms.Textarea(attrs={"rows": 3}),
            "retention_start_date": forms.DateInput(attrs={"type": "date"}),
            "disposition_due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
