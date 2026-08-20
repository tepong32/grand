from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from records.models import DepartmentRecord
from reporting.models import ReportRun

from .models import PacketCheckpoint, PacketDiscrepancy, PacketItem, TrackedPacket


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


class PacketItemForm(forms.ModelForm):
    class Meta:
        model = PacketItem
        fields = ("title", "description", "expected_attachment_count", "expected_page_count")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class PacketCheckpointForm(forms.ModelForm):
    class Meta:
        model = PacketCheckpoint
        fields = ("department", "employee", "purpose", "label", "instructions", "required")
        widgets = {"instructions": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = get_user_model().objects.filter(
            is_active=True,
            employeeprofile__assigned_department__isnull=False,
        ).select_related("employeeprofile__assigned_department").order_by(
            "employeeprofile__assigned_department__name", "last_name", "first_name", "username",
        )
        self.fields["employee"].required = False
        self.fields["employee"].help_text = "Optional. Leave blank when any employee in the checkpoint office may receive it."
        for name, field in self.fields.items():
            if name != "required":
                field.widget.attrs["class"] = "form-control"


class PacketSplitForm(forms.Form):
    items = forms.ModelMultipleChoiceField(
        queryset=PacketItem.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Vouchers moving together",
    )
    title = forms.CharField(max_length=220, widget=forms.TextInput(attrs={"class": "form-control"}))
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Reason or physical split note"}),
    )

    def __init__(self, *args, packet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["items"].queryset = packet.voucher_items.all() if packet else PacketItem.objects.none()


class PacketRebundleForm(forms.Form):
    items = forms.ModelMultipleChoiceField(
        queryset=PacketItem.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Vouchers to move",
    )
    target_packet = forms.ModelChoiceField(
        queryset=TrackedPacket.objects.none(),
        label="Destination bundle",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Reason for rebundling"}),
    )

    def __init__(self, *args, packet=None, targets=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["items"].queryset = packet.voucher_items.all() if packet else PacketItem.objects.none()
        self.fields["target_packet"].queryset = targets if targets is not None else TrackedPacket.objects.none()


class ReceiptConfirmationForm(forms.Form):
    checkpoint = forms.ModelChoiceField(
        queryset=PacketCheckpoint.objects.none(),
        required=False,
        empty_label="No planned checkpoint completed at this receipt",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    terminal_delivery = forms.BooleanField(
        required=False,
        label="This is the final, terminal delivery",
        help_text="Use only when this office is keeping the packet as its declared final destination.",
        widget=forms.CheckboxInput(attrs={"class": "custom-control-input"}),
    )
    receipt_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Example: Counted 12 vouchers; sealed bundle received intact.",
        }),
    )

    def __init__(self, *args, scan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.scan = scan
        if not scan or not scan.recipient_id:
            return
        department = scan.recipient.employeeprofile.assigned_department
        if scan.packet.status == TrackedPacket.DRAFT:
            self.fields.pop("checkpoint")
            self.fields.pop("terminal_delivery")
            return
        self.fields["checkpoint"].queryset = scan.packet.checkpoints.filter(
            status=PacketCheckpoint.PENDING,
            department=department,
        ).filter(Q(employee__isnull=True) | Q(employee=scan.recipient))
        destination_matches = (
            scan.recipient_id == scan.packet.final_destination_employee_id
            if scan.packet.final_destination_employee_id
            else department.pk == scan.packet.final_destination_department_id
        )
        if not destination_matches:
            self.fields.pop("terminal_delivery")
