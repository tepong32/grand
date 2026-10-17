from django import forms
from django.utils import timezone


class EmployeeHandoffForm(forms.Form):
    query = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput)
    employee_id = forms.TypedChoiceField(choices=(), coerce=int, label="Receiving employee")
    transfer_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    reference = forms.CharField(max_length=120, label="PAR / ICS / documented handoff reference")
    reason = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 3}), label="Reason for handoff")

    def __init__(self, *args, employees=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee_id"].choices = [("", "Select a matching employee")] + [
            (row.pk, f"{row.get_full_name() or row.username} ({row.username}) — {row.employeeprofile.assigned_department.name}")
            for row in employees]


class ConfirmEmployeeHandoffForm(forms.Form):
    handoff_token = forms.CharField(widget=forms.HiddenInput)
