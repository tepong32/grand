from django import forms
from .models import AssistanceRequest, RequestDocument
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
        fields = ['file']

class AssistanceRequestEditForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ['full_name', 'email', 'phone', ]  # example
