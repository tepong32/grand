from django import forms

from .models import ProgramActivity, SocialWelfareProgram


class DateInput(forms.DateInput):
    input_type = "date"


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class SocialWelfareProgramForm(forms.ModelForm):
    class Meta:
        model = SocialWelfareProgram
        fields = (
            "name",
            "code",
            "program_type",
            "description",
            "status",
            "coordinator",
            "start_date",
            "end_date",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": DateInput(),
            "end_date": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.department = department
        self.fields["coordinator"].queryset = self.fields["coordinator"].queryset.filter(
            employeeprofile__assigned_department=department
        ).order_by("last_name", "first_name", "username")

    def validate_unique(self):
        if self.department:
            self.instance.department = self.department
        super().validate_unique()


class ProgramActivityForm(forms.ModelForm):
    class Meta:
        model = ProgramActivity
        fields = (
            "title",
            "activity_type",
            "starts_at",
            "ends_at",
            "venue",
            "status",
            "expected_attendance",
            "actual_attendance",
            "outcome_notes",
        )
        widgets = {
            "starts_at": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "ends_at": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "outcome_notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ("%Y-%m-%dT%H:%M",)
        self.fields["ends_at"].input_formats = ("%Y-%m-%dT%H:%M",)
