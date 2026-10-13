from datetime import date
from django import forms
from django.utils import timezone
from departments.models import Department
from budget.models import BudgetCall
from .access import department_for_user
from .models import Fund
from .summary_actuals import RECEIPTS, EXPENDITURES
from .budget_actuals import money


def style(form):
    for field in form.fields.values():
        field.widget.attrs['class']='form-check-input' if isinstance(field,forms.BooleanField) else 'form-control'


class ScopeForm(forms.Form):
    fund=forms.ModelChoiceField(queryset=Fund.objects.none())
    budget_department=forms.ModelChoiceField(queryset=Department.objects.none(),label='Designated Budget office')
    treasury_department=forms.ModelChoiceField(queryset=Department.objects.none(),label='Designated Treasury office')
    year=forms.IntegerField(min_value=1900,max_value=9999,label='Reporting year')
    period=forms.ChoiceField(choices=(('h1','January–June'),('year','Full calendar year')))
    entity_type=forms.ChoiceField(choices=(('general','General Fund'),('enterprise','Actual LGU enterprise')))
    enterprise_reference=forms.SlugField(max_length=61,required=False,label='Stable enterprise reference')
    entity_label=forms.CharField(max_length=255,label='Reporting entity designation')

    def __init__(self,*args,actor,**kwargs):
        super().__init__(*args,**kwargs); owner=department_for_user(actor)
        self.fields['fund'].queryset=Fund.objects.filter(department_id=owner.pk).order_by('code','pk')
        offices=BudgetCall.objects.filter(fiscal_year__department_id=owner.pk).values_list('department_id',flat=True)
        self.fields['budget_department'].queryset=Department.objects.filter(pk__in=list(offices)).order_by('name')
        self.fields['treasury_department'].queryset=Department.objects.order_by('name')
        style(self)

    def clean(self):
        data=super().clean()
        if data.get('entity_type')=='enterprise' and not data.get('enterprise_reference'):
            self.add_error('enterprise_reference','Identify the actual enterprise represented by this complete Fund.')
        if data.get('year') and data.get('period'):
            end=date(data['year'],6,30) if data['period']=='h1' else date(data['year'],12,31)
            if end>timezone.localdate(): self.add_error('period','Select a completed reporting period.')
            data.update(period_start=date(data['year'],1,1),period_end=end)
        return data

    def scope_values(self):
        data=self.cleaned_data
        key='general' if data['entity_type']=='general' else 'enterprise:'+data['enterprise_reference'].lower()
        return dict(fund_id=data['fund'].pk,budget_department_id=data['budget_department'].pk,
            treasury_department_id=data['treasury_department'].pk,period_start=data['period_start'],
            period_end=data['period_end'],entity_key=key,entity_label=data['entity_label'])


def category_rows(captured,mappings=None):
    body=captured['payload']; receipt=body['receipts']['payload']
    active={row['allocation']['category'] for row in receipt['bridge'] if row['allocation']['disposition']=='include'}
    receipts=[dict(category=key,label=label,amount=receipt['category_totals'][key],
        coverage='activity' if key in active else 'no_activity') for key,label in RECEIPTS.items()]
    expense={key:money('0') for key in EXPENDITURES}; used=set()
    for row in body['expenditures']['payload']['rows']:
        category=(mappings or {}).get(row['expense_class'])
        if category in expense:
            expense[category]+=money(row['amount'])
            if row['components']: used.add(category)
    expenses=[dict(category=key,label=label,amount=str(expense[key]),
        coverage='activity' if key in used else 'no_activity') for key,label in EXPENDITURES.items()]
    if {row['expense_class'] for row in body['expenditures']['payload']['rows']} - set(mappings or {}):
        for row in expenses: row.update(amount=None,coverage='mapping_required')
    return receipts,expenses


class PreparationForm(forms.Form):
    expected_source_checksum=forms.CharField(max_length=64,widget=forms.HiddenInput)
    expected_latest=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    entity_basis=forms.CharField(max_length=1000,widget=forms.Textarea(attrs={'rows':2}),
        label='Why this complete Fund represents the named entity')
    coverage_basis=forms.CharField(max_length=1000,widget=forms.Textarea(attrs={'rows':3}),
        label='Evidence for every listed category, including those with no activity')
    mapping_basis=forms.CharField(max_length=1000,required=False,widget=forms.Textarea(attrs={'rows':2}),
        label='Basis for the expenditure category mappings')
    reference=forms.CharField(max_length=255,label='Source or reconciliation reference')
    authority=forms.CharField(max_length=2000,widget=forms.Textarea(attrs={'rows':2}),label='Preparation authority')
    reason=forms.CharField(max_length=2000,widget=forms.Textarea(attrs={'rows':2}),label='Preparation explanation')
    confirmed=forms.BooleanField(label='I checked the full named entity and every category below, including no-activity declarations and expenditure mappings.')

    def __init__(self,*args,captured,**kwargs):
        super().__init__(*args,**kwargs); self.captured=captured
        self.classes=sorted({row['expense_class'] for row in captured['payload']['expenditures']['payload']['rows']})
        for index,label in enumerate(self.classes):
            self.fields[f'mapping_{index}']=forms.ChoiceField(choices=[('','Choose category'),*EXPENDITURES.items()],
                label=f'Expenditure category for {label}')
        style(self)

    def clean(self):
        data=super().clean()
        if self.classes and not data.get('mapping_basis'):
            self.add_error('mapping_basis','Explain the explicit mapping of the retained expenditure classes.')
        return data

    def declarations(self,scope):
        data=self.cleaned_data; mappings={label:data[f'mapping_{index}'] for index,label in enumerate(self.classes)}
        receipts,expenses=category_rows(self.captured,mappings)
        return dict(entity=dict(key=scope['entity_key'],label=scope['entity_label'],full_fund=True,basis=data['entity_basis']),
            class_mappings=[dict(expense_class=label,category=mappings[label],basis=data['mapping_basis']) for label in self.classes],
            receipt_rows=[{key:row[key] for key in ('category','amount','coverage')} | {'basis':data['coverage_basis']} for row in receipts],
            expenditure_rows=[{key:row[key] for key in ('category','amount','coverage')} | {'basis':data['coverage_basis']} for row in expenses])


class ReviewForm(forms.Form):
    outcome=forms.ChoiceField(choices=(('approve','Approve category and entity coverage'),('return','Return preparation')))
    authority=forms.CharField(max_length=2000,widget=forms.Textarea(attrs={'rows':2}),label='Your independent review authority')
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':3}),label='Decision explanation')
    verified=forms.BooleanField(required=False,label='I checked the complete entity, all category declarations and original source movements.')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); style(self)

    def clean(self):
        data=super().clean()
        if data.get('outcome')=='approve' and not data.get('verified'):
            self.add_error('verified','Review the complete evidence before approving.')
        return data


class DecisionForm(ReviewForm):
    outcome=forms.ChoiceField(choices=(('certify','Certify actuals'),('return','Return for successor preparation')))
    authority=forms.CharField(max_length=2000,widget=forms.Textarea(attrs={'rows':2}),label='Your designation and certification authority')
    verified=forms.BooleanField(required=False,label='I checked the complete entity, all categories, original movements and the same-period Fund trial balance.')

    def clean(self):
        data=super().clean()
        if data.get('outcome')=='certify' and not data.get('verified'):
            self.add_error('verified','Review the complete evidence and trial balance before certifying.')
        return data
