from decimal import Decimal
from django import forms
from django.forms import BaseFormSet, formset_factory
from departments.models import Department


class AllocationProposalForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    finance_department = forms.ModelChoiceField(queryset=Department.objects.exclude(name='---select one---').order_by('name'),
        label='Department responsible for independent Accounting review',
        help_text='This shares the documentary proposal and its evidence with explicitly authorized reviewers in that department.')
    allocation_basis = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}),
        label='Documented allocation basis', help_text='Explain how the explicit component amounts were established. No automatic pro-rata rule is applied.')
    upload = forms.FileField(label='Supporting allocation document (PDF or image; up to 15 MB)')


class AllocationComponentForm(forms.Form):
    label = forms.CharField(max_length=180, label='Component description')
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('.001'), label='Component quantity')
    unit = forms.CharField(max_length=40, label='Component unit', help_text='For example: unit, set or bundle. These quantities do not change the asset register.')
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0, label='Explicit component amount',
                               help_text='Total amount for this component, not a unit price.')
    reference = forms.CharField(max_length=240, label='Component document / calculation reference')


class AllocationComponentSet(BaseFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if 'DELETE' in form.fields:
            form.fields['DELETE'].label = 'Omit this component'


AllocationComponents = formset_factory(AllocationComponentForm, formset=AllocationComponentSet, extra=1, min_num=1, validate_min=True,
                                     max_num=50, absolute_max=50, validate_max=True, can_delete=True)


class AllocationDecisionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=(('', 'Choose a decision'),
        ('approved', 'Accept documentary allocation'), ('rejected', 'Reject proposal')))
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}), label='Independent Accounting review findings')
