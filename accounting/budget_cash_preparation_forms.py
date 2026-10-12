from django import forms
from departments.models import Department
from budget.models import BudgetCall
from .access import department_for_user
from .models import Fund, OpeningBalanceBatch, BudgetCashEvidence


class SourceChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if isinstance(obj, OpeningBalanceBatch):
            return f'{obj.source_reference} · baseline {obj.period.starts_on}'
        boundary = 'Start of day' if obj.boundary == 'start_of_day' else 'End of day'
        return f'{obj.fund.code} · {obj.entity_key} · {obj.balance_date} · {boundary} · version {obj.version}'


class PreparationForm(forms.Form):
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    opening_batch = SourceChoice(queryset=OpeningBalanceBatch.objects.none(), label='Reconciled opening source')
    budget_department = forms.ModelChoiceField(queryset=Department.objects.none(), label='Designated Budget office')
    treasury_department = forms.ModelChoiceField(queryset=Department.objects.none(), label='Designated Treasury office')
    entity_key = forms.CharField(max_length=80, initial='general', help_text='Use general or the explicit enterprise key, such as enterprise:waterworks.')
    coverage_authority = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}),
        label='Opening coverage for this fund and entity', help_text='Explain the actual source coverage. An entity label alone does not allocate a whole fund to an enterprise.')
    balance_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    boundary = forms.ChoiceField(choices=(('start_of_day', 'Start of day'), ('end_of_day', 'End of day')))
    restriction_source = SourceChoice(queryset=BudgetCashEvidence.objects.none(), required=False,
        label='Adopted restriction evidence (optional)', help_text='Exact scope and gross cash must match. Leaving this blank keeps restrictions and net cash unknown.')
    expected_latest = forms.IntegerField(min_value=0, initial=0, widget=forms.HiddenInput)

    def __init__(self, *args, actor, previous=None, **kwargs):
        super().__init__(*args, **kwargs)
        from . import budget_cash
        owner = department_for_user(actor)
        self.fields['fund'].queryset = Fund.objects.filter(department_id=owner.pk)
        self.fields['opening_batch'].queryset = OpeningBalanceBatch.objects.filter(
            department_id=owner.pk, status=OpeningBalanceBatch.RECONCILED).select_related('period')
        office_ids = list(BudgetCall.objects.filter(fiscal_year__department_id=owner.pk).values_list('department_id', flat=True).distinct())
        self.fields['budget_department'].queryset = Department.objects.filter(pk__in=office_ids)
        self.fields['treasury_department'].queryset = Department.objects.all()
        # Native-only permission can prepare gross sources without granting
        # historical source access; those actors get no historical selector.
        from django.core.exceptions import PermissionDenied
        try:
            self.fields['restriction_source'].queryset = budget_cash.visible(actor).filter(
                department_id=owner.pk, status='adopted').select_related('fund')
        except PermissionDenied:
            self.fields['restriction_source'].queryset = BudgetCashEvidence.objects.none()
        if previous:
            for name in ('fund', 'budget_department', 'treasury_department', 'entity_key', 'balance_date', 'boundary'):
                self.fields[name].disabled = True
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control', 'style': 'max-width:100%'})
