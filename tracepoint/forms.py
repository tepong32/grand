from django import forms
from django.contrib.auth import get_user_model

from records.models import DepartmentRecord
from reporting.models import ReportRun

from .models import PacketDiscrepancy, TrackedPacket


class TrackedPacketForm(forms.ModelForm):
    class Meta:
        model = TrackedPacket
        fields = (
            "title", "contents_manifest", "expected_document_count", "expected_page_count",
            "confidentiality", "final_destination_department", "final_destination_employee",
            "department_record", "report_run",
        )
        widgets = {"contents_manifest": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, origin_department=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).select_related("employeeprofile__assigned_department").order_by(
            "employeeprofile__assigned_department__name", "last_name", "first_name", "username",
        )
        self.fields["final_destination_employee"].queryset = users
        self.fields["final_destination_employee"].required = False
        self.fields["final_destination_employee"].help_text = "Optional. Leave blank when any authorized employee in the destination office may receive it."
        self.fields["department_record"].queryset = DepartmentRecord.objects.filter(
            department=origin_department,
        ).exclude(status=DepartmentRecord.DISPOSED).order_by("-updated_at")
        self.fields["report_run"].queryset = ReportRun.objects.filter(
            definition__department=origin_department,
            status=ReportRun.APPROVED,
            template_version__fidelity_status="official",
            template_version__fidelity_validated_at__isnull=False,
            template_version__approved_at__isnull=False,
        ).order_by("-created_at")
        self.fields["department_record"].required = False
        self.fields["report_run"].required = False
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class EmployeeCodeScanForm(forms.Form):
    employee_code = forms.CharField(
        max_length=500,
        label="Employee daily code",
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "autocomplete": "off",
            "autofocus": True,
            "placeholder": "Scan the employee QR or paste its code",
        }),
    )


class DiscrepancyForm(forms.Form):
    category = forms.ChoiceField(choices=PacketDiscrepancy.CATEGORY_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Describe what was observed."}))
    related_handoff = forms.IntegerField(required=False, widget=forms.HiddenInput)
