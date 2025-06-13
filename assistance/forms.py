from django import forms
from .models import AssistanceRequest, RequestDocument

class AssistanceRequestForm(forms.ModelForm):
    '''
    This logic checks if the full name + assistance type + period combination already exists in the database,
    ***specifically for educational assistance requests. If it does, it raises a validation error.***
    '''
    class Meta:
        model = AssistanceRequest
        fields = ['assistance_type', 'full_name', 'email', 'phone', 'period']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set help_text as placeholder
        for field_name, field in self.fields.items():
            if field.help_text:
                field.widget.attrs['placeholder'] = field.help_text
                
    def clean(self):
        cleaned_data = super().clean()
        full_name = cleaned_data.get('full_name')
        assistance_type = cleaned_data.get('assistance_type')
        period = cleaned_data.get('period')

        if assistance_type == 'educational' and period:
            existing = AssistanceRequest.objects.filter(
                full_name__iexact=full_name.strip(),
                assistance_type=assistance_type,
                period=period,
            )
            if existing.exists():
                raise forms.ValidationError(
                    "You have already submitted an educational assistance request for this school year."
                )

        return cleaned_data

class RequestDocumentForm(forms.ModelForm):
    class Meta:
        model = RequestDocument
        fields = ['file']

class AssistanceRequestEditForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ['full_name', 'email', 'phone', ]  # example
