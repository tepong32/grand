"""Historical cash transcription, separate from native ledger capture."""
import csv
import io
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from budget.models import BudgetCall
from departments.models import Department
from .access import department_for_user
from .models import Fund

COLUMNS = ('key', 'reference', 'purpose', 'coverage', 'amount')
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000


def parse_csv(upload):
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError('The restriction CSV exceeds 2 MiB; nothing was imported.')
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError('Use UTF-8 CSV; nothing was imported.')
    if '\x00' in content:
        raise ValidationError('Invalid CSV text; nothing was imported.')
    try:
        reader = csv.DictReader(io.StringIO(content, newline=''), strict=True)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValidationError('Use exactly these columns in order: ' + ', '.join(COLUMNS))
        rows = []
        for number, row in enumerate(reader, 2):
            if len(rows) >= MAX_ROWS:
                raise ValidationError('The CSV exceeds 10,000 items; nothing was imported.')
            if None in row or any(value is None for value in row.values()):
                raise ValidationError(f'CSV row {number}: use exactly five columns; quote text containing commas.')
            values = {key: value.strip() for key, value in row.items()}
            if any(not values[key] or len(values[key]) > limit for key, limit in
                (('key', 120), ('reference', 255), ('purpose', 2000), ('coverage', 2000), ('amount', 32))):
                raise ValidationError(f'CSV row {number}: required text is missing or too long; nothing was imported.')
            rows.append(values)
    except csv.Error:
        raise ValidationError('Malformed CSV quoting or field lengths; nothing was imported.')
    if not rows:
        raise ValidationError('An empty CSV is not an evidenced no-restriction declaration.')
    return rows


class CashForm(forms.Form):
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    budget_department = forms.ModelChoiceField(queryset=Department.objects.none(), label='Designated Budget office')
    treasury_department = forms.ModelChoiceField(queryset=Department.objects.none(), label='Designated Treasury office')
    entity_key = forms.CharField(max_length=80, initial='general', label='Reporting entity code',
        help_text='Use general or the LGU’s established enterprise designation, such as enterprise:waterworks.')
    entity_label = forms.CharField(max_length=255, label='Reporting entity designation')
    balance_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    boundary = forms.ChoiceField(choices=(('start_of_day', 'Start of day'), ('end_of_day', 'End of day')))
    expected_latest = forms.IntegerField(min_value=0, initial=0, widget=forms.HiddenInput)
    reference = forms.CharField(max_length=2000, label='Original cash certificate reference')
    scope_authority = forms.CharField(max_length=2000, label='Fund/entity and participating office designation evidence')
    gross_basis = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Gross cash source and dated basis')
    coverage = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Complete source coverage and explicit omissions')
    reconciliation_basis = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Original reconciliation basis and source pages')
    accountant_name = forms.CharField(max_length=2000, label='Original Accountant')
    accountant_authority = forms.CharField(max_length=2000, label='Original Accountant designation')
    accountant_certified_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    treasurer_name = forms.CharField(max_length=2000, label='Original Treasurer')
    treasurer_authority = forms.CharField(max_length=2000, label='Original Treasurer designation')
    treasurer_certified_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    gross = forms.DecimalField(max_digits=18, decimal_places=2, label='Signed gross cash')
    restricted = forms.DecimalField(max_digits=18, decimal_places=2, label='Signed restricted cash')
    net = forms.DecimalField(max_digits=18, decimal_places=2, label='Signed net cash (gross less restricted)')
    no_restrictions = forms.BooleanField(required=False, label='Original source explicitly certifies no restrictions')
    declaration = forms.CharField(max_length=2000, required=False, label='Original no-restriction declaration and source reference')
    overlap_basis = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Restriction coverage, overlap checks and reconciliation')
    certificate = forms.FileField(label='Original joint cash certificate (PDF/PNG/JPEG, up to 8 MiB)')
    reconciliation = forms.FileField(label='Original reconciliation (PDF/PNG/JPEG, up to 8 MiB)')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Submission/successor reason')
    row_input = forms.ChoiceField(initial='manual', label='Restriction entry', choices=(
        ('manual', 'Enter/edit up to 100 items'), ('csv', 'Replace from complete UTF-8 CSV')))
    row_csv = forms.FileField(required=False, label='Restriction CSV (up to 10,000 items / 2 MiB)')

    def __init__(self, *args, actor, previous=None, **kwargs):
        super().__init__(*args, **kwargs)
        owner = department_for_user(actor)
        self.fields['fund'].queryset = Fund.objects.filter(department_id=owner.pk)
        offices = list(BudgetCall.objects.filter(fiscal_year__department_id=owner.pk).values_list('department_id', flat=True).distinct())
        self.fields['budget_department'].queryset = Department.objects.filter(pk__in=offices)
        self.fields['treasury_department'].queryset = Department.objects.all()
        if previous:
            self.fields['row_input'].choices = [*self.fields['row_input'].choices, ('retain', 'Retain every preceding restriction')]
            for name in ('fund', 'budget_department', 'treasury_department', 'entity_key', 'entity_label', 'balance_date', 'boundary'):
                self.fields[name].disabled = True
            for name in ('certificate', 'reconciliation'):
                self.fields[name].required = False
                self.fields[name].help_text = 'Leave blank to retain the exact preceding document.'
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput): field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['style'] = 'max-width:100%'

    def clean(self):
        data = super().clean()
        if data.get('row_input') == 'csv' and not data.get('row_csv'):
            self.add_error('row_csv', 'Attach the complete replacement CSV.')
        elif data.get('row_input') != 'csv' and data.get('row_csv'):
            self.add_error('row_input', 'Choose CSV replacement to use this file; it will not be silently ignored.')
        return data


class RestrictionForm(forms.Form):
    key = forms.CharField(max_length=120, label='Stable restriction identity')
    reference = forms.CharField(max_length=255, label='Unique source page / leaf row')
    purpose = forms.CharField(max_length=2000)
    coverage = forms.CharField(max_length=2000, label='Scope and overlap treatment')
    amount = forms.DecimalField(max_digits=18, decimal_places=2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs['class'] = 'form-control'


Rows = formset_factory(RestrictionForm, extra=1, max_num=100, validate_max=True, absolute_max=100, can_delete=True)
