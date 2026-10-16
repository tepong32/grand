"""Clerk declarations and independent findings; no financial re-entry."""
from django import forms
from . import form1_signing as signing, form1_signed_copies as signed

CHECK_LABELS = {'complete_pages':'Every original page and copy identity',
    'financial_fields':'Original financial fields and amounts', 'physical_custody':'Actual return and original paper custody'}


def _style(form):
    for field in form.fields.values():
        if not field.widget.is_hidden:
            field.widget.attrs.update({'class':'form-select' if isinstance(field.widget,forms.Select) else 'form-control',
                                       'style':'min-width:0;max-width:100%'})


class SignedReceipt(forms.Form):
    expected_latest = forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    predecessor = forms.UUIDField(required=False,widget=forms.HiddenInput)
    upload = forms.FileField(label='Complete returned Form 1 PDF (up to 8 MiB)')
    received_on = forms.DateField(label='Actual physical receipt date',widget=forms.DateInput(attrs={'type':'date'}))
    received_by = forms.CharField(label='Actual on-site recipient',max_length=180)
    custody_reference = forms.CharField(label='Physical handover / custody reference',max_length=2000)
    custody_location = forms.CharField(label='Location of the retained original paper',max_length=2000)
    correction_reason = forms.CharField(label='Receipt or correction reference and basis',max_length=2000,
        widget=forms.Textarea(attrs={'rows':2}))

    def __init__(self,*args,copy,**kwargs):
        super().__init__(*args,**kwargs)
        self.members = copy.preparation.package.payload['assembly']['payload']['members']
        for number, member in enumerate(self.members):
            for role,title in signing.ROLES.items():
                self.fields[f'entity{number}_{role}'] = forms.DateField(label=title+' — actual signing date',
                    required=False,widget=forms.DateInput(attrs={'type':'date'}),
                    help_text='Leave unknown if absent or unreadable. Verification/issuance requires every actual date.')
        _style(self)

    def date_groups(self):
        return [(member['entity_label'],[self[f'entity{number}_{role}'] for role in signing.ROLES])
                for number,member in enumerate(self.members)]

    def receipt_fields(self):
        return [self[key] for key in ('upload','received_on','received_by','custody_reference',
                                      'custody_location','correction_reason')]

    def arguments(self):
        return dict(**{key:self.cleaned_data[key] for key in
            ('expected_latest','upload','received_on','received_by','custody_reference','custody_location','correction_reason')},
            signed_dates={member['entity_key']:{role:self.cleaned_data[f'entity{number}_{role}'] for role in signing.ROLES}
                          for number,member in enumerate(self.members)})


class SignedDecision(forms.Form):
    note = forms.CharField(label='Independent decision reference and basis',max_length=2000,
                          widget=forms.Textarea(attrs={'rows':2}))
    reference = forms.CharField(label='Final issue reference (required when issuing)',required=False,max_length=2000)

    def __init__(self,*args,copy,**kwargs):
        super().__init__(*args,**kwargs)
        self.findings = list(CHECK_LABELS.items())
        for member in copy.preparation.package.payload['assembly']['payload']['members']:
            self.findings.extend((member['entity_key']+':'+role,member['entity_label']+' — '+title)
                                 for role,title in signing.ROLES.items())
        for number,(_,label) in enumerate(self.findings):
            self.fields[f'finding{number}_verified'] = forms.TypedChoiceField(label='Finding',
                choices=(('','Choose a finding'),('true','Verified'),('false','Not verified')),
                coerce=lambda value:value=='true')
            self.fields[f'finding{number}_basis'] = forms.CharField(label='Evidence and basis',max_length=2000)
        _style(self)

    def finding_fields(self):
        return [(label,self[f'finding{number}_verified'],self[f'finding{number}_basis'])
                for number,(_,label) in enumerate(self.findings)]

    def checks(self):
        return {key:dict(verified=self.cleaned_data[f'finding{number}_verified'],basis=self.cleaned_data[f'finding{number}_basis'])
                for number,(key,_) in enumerate(self.findings)}


class FinalIssue(forms.Form):
    reference = forms.CharField(label='Final issue reference and purpose',max_length=2000,
                               widget=forms.Textarea(attrs={'rows':2,'class':'form-control'}))
