from django import forms
from .models import AssistanceRequest, RequestDocument

class AssistanceRequestForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ['full_name', 'email', 'assistance_type'] #'purpose'
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'assistance_type': forms.Select(attrs={'class': 'form-select'}),
            # 'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class EmailUpdateForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ['email']

class RequestDocumentForm(forms.ModelForm):
    class Meta:
        model = RequestDocument
        fields = ['file']

