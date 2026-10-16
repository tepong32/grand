"""Named Form 1 designation evidence, separate from actual signatures."""
from django import forms
from .form1_signing import ROLES, CHECKS


class SigningPreparation(forms.Form):
    expected_latest = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    document_date = forms.DateField(label='Intended Form 1 date', widget=forms.DateInput(attrs={'type': 'date'}))
    lgu = forms.CharField(label='LGU name exactly as retained in the original office sources', max_length=200)
    reference = forms.CharField(label='Preparation reference and basis', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ROLES:
            self.fields[key + '_name'] = forms.CharField(label='Designated officer name', max_length=180)
            self.fields[key + '_position'] = forms.CharField(label='Actual position', max_length=180)
            self.fields[key + '_authority_reference'] = forms.CharField(label='Designation authority reference', max_length=2000)
            self.fields[key + '_valid_from'] = forms.DateField(label='Designation effective from', widget=forms.DateInput(attrs={'type': 'date'}))
            self.fields[key + '_valid_to'] = forms.DateField(label='Designation effective until (if stated)', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
            self.fields[key + '_document'] = forms.FileField(label='Original designation document (PDF, PNG or JPEG; up to 8 MiB)')
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs['class'] = 'form-control'

    def role_fields(self):
        return [(title, [self[key + '_' + field] for field in
                 ('name', 'position', 'authority_reference', 'valid_from', 'valid_to', 'document')])
                for key, title in ROLES.items()]

    def arguments(self):
        return dict(
            **{key: self.cleaned_data[key] for key in ('expected_latest', 'document_date', 'lgu', 'reference')},
            signatories={key: {field: self.cleaned_data[key + '_' + field] for field in
                ('name', 'position', 'authority_reference', 'valid_from', 'valid_to')} for key in ROLES},
            documents={key: self.cleaned_data[key + '_document'] for key in ROLES})


class SigningDecision(forms.Form):
    note = forms.CharField(label='Independent review or return reason', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in CHECKS:
            self.fields[key + '_verified'] = forms.TypedChoiceField(label=key.replace('_', ' ').capitalize(),
                choices=(('', 'Choose a finding'), ('true', 'Verified'), ('false', 'Not verified')),
                coerce=lambda value: value == 'true')
            self.fields[key + '_basis'] = forms.CharField(label='Evidence and basis for ' + key.replace('_', ' '), max_length=2000)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'

    def checks(self):
        return {key: dict(verified=self.cleaned_data[key + '_verified'],
                          basis=self.cleaned_data[key + '_basis']) for key in CHECKS}


class SigningCopyRelease(forms.Form):
    reference = forms.CharField(label='Unsigned-copy release reference and purpose', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
