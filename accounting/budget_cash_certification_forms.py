from django import forms


class DecisionForm(forms.Form):
    outcome = forms.ChoiceField(choices=(('certify', 'Certify this fixed cash snapshot'),
        ('return', 'Return this preparation')))
    authority = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}),
        label='Your designation and certification authority')
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}),
        label='Decision explanation')
    verified = forms.BooleanField(required=False,
        label='I reviewed the full cash sources, original restrictions and reconciliation for this exact preparation.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field, forms.BooleanField) else 'form-control'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('outcome') == 'certify' and not cleaned.get('verified'):
            self.add_error('verified', 'Review the complete evidence before certifying.')
        return cleaned
