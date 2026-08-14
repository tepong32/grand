from django import forms
from .models import AssistanceRequest, CitizenProfile, RequestDocument
import datetime


def get_valid_school_years():
    current_year = datetime.date.today().year
    options = []
    for year in [current_year - 1, current_year]:
        label = f"{year}–{year + 1}"
        options.append((label, label))
    return options

class AssistanceRequestForm(forms.ModelForm):
    period = forms.ChoiceField(choices=[], label="School Year")

    class Meta:
        model = AssistanceRequest
        fields = ['assistance_type', 'period', 'semester', 'full_name', 'email', 'phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['period'].choices = get_valid_school_years()

    def clean(self):
        cleaned_data = super().clean()
        assistance_type = cleaned_data.get('assistance_type')
        email = cleaned_data.get('email')
        period = cleaned_data.get('period')
        semester = cleaned_data.get('semester')

        if assistance_type and getattr(assistance_type, 'category', '').lower() == 'educational':
            query = AssistanceRequest.objects.filter(
                assistance_type=assistance_type,
                email=email,
                period=period,
                is_active=True,
            )
            if semester:
                query = query.filter(semester=semester)

            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise forms.ValidationError(
                    "You already have an active educational assistance request for this school year and semester."
                )

class RequestDocumentForm(forms.ModelForm):
    class Meta:
        model = RequestDocument
        fields = ['document_type', 'file']

class AssistanceRequestEditForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ['full_name', 'email', 'phone', ]  # example


class CitizenReviewForm(forms.ModelForm):
    class Meta:
        model = CitizenProfile
        fields = ("review_status", "assigned_reviewer", "review_notes")
        widgets = {"review_notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["review_status"].widget.attrs["class"] = "form-select"
        self.fields["assigned_reviewer"].widget.attrs["class"] = "form-select"
        self.fields["review_notes"].widget.attrs["class"] = "form-control"
        self.fields["assigned_reviewer"].queryset = self.fields[
            "assigned_reviewer"
        ].queryset.filter(employeeprofile__assigned_department__slug__iexact="mswd").order_by(
            "first_name", "last_name", "username"
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("review_status") == "needs_update" and not (cleaned.get("review_notes") or "").strip():
            self.add_error("review_notes", "Explain what information needs to be updated.")
        return cleaned
