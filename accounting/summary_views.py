import io
import json
import zipfile

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.forms import formset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from budget.models import BudgetCall
from departments.models import Department
from src.export_archive import archive_export
from .access import department_for_user
from .models import Fund, LedgerAccount
from . import summary_actuals as services
from . import summary_csv


class AdoptionForm(forms.Form):
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    budget_department = forms.ModelChoiceField(queryset=Department.objects.none())
    treasury_department = forms.ModelChoiceField(queryset=Department.objects.none())
    entity_key = forms.CharField(max_length=80, initial='general', label='Reporting entity code',
        help_text='Use general for the General Fund, or an established enterprise code such as enterprise:waterworks. Use only the LGU’s actual scope.')
    entity_label = forms.CharField(max_length=255, label='Reporting entity designation')
    period_start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    expected_latest = forms.IntegerField(min_value=0, initial=0, widget=forms.HiddenInput)
    reference = forms.CharField(max_length=2000, label='Original joint certificate reference')
    issuer = forms.CharField(max_length=2000)
    scope_authority = forms.CharField(max_length=2000, label='Fund/entity and participating office designation evidence')
    coverage = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Complete receipt/expenditure coverage and explicit omissions')
    trial_balance_reference = forms.CharField(max_length=2000, label='Trial balance period, fund and source reference')
    reconciliation_basis = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Reconciliation to trial balance, including source pages and basis differences')
    accountant_name = forms.CharField(max_length=2000, label='Original Local Accountant')
    accountant_authority = forms.CharField(max_length=2000, label='Original Accountant designation')
    accountant_certified_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    treasurer_name = forms.CharField(max_length=2000, label='Original Local Treasurer')
    treasurer_authority = forms.CharField(max_length=2000, label='Original Treasurer designation')
    treasurer_certified_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    receipt_total = forms.DecimalField(max_digits=18, decimal_places=2, label='Signed receipts total')
    expenditure_total = forms.DecimalField(max_digits=18, decimal_places=2, label='Signed expenditures total')
    evidence = forms.FileField(label='Original joint certificate (PDF/PNG/JPEG, up to 8 MiB)')
    trial_balance = forms.FileField(label='Original trial balance/supporting reconciliation (PDF/PNG/JPEG, up to 8 MiB)')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Adoption/successor reason')
    row_input = forms.ChoiceField(required=False, initial='manual', label='Source row entry', choices=(
        ('manual', 'Enter/edit rows below (up to 100)'), ('csv', 'Replace rows from UTF-8 CSV (up to 10,000)')))
    row_csv = forms.FileField(required=False, label='Source row CSV (up to 2 MiB)',
        help_text='Transcribed rows only; the original certificate and trial-balance documents are still required.')

    def __init__(self, *args, actor, previous=None, **kwargs):
        super().__init__(*args, **kwargs)
        owner = department_for_user(actor)
        self.fields['fund'].queryset = Fund.objects.filter(department_id=owner.pk)
        offices = list(BudgetCall.objects.filter(fiscal_year__department_id=owner.pk).values_list('department_id', flat=True).distinct())
        self.fields['budget_department'].queryset = Department.objects.filter(pk__in=offices)
        self.fields['treasury_department'].queryset = Department.objects.all()
        if previous:
            self.fields['row_input'].choices = [*self.fields['row_input'].choices,
                ('retain', 'Retain every row from the preceding version')]
            for name in ('fund', 'budget_department', 'treasury_department', 'entity_key', 'entity_label', 'period_start', 'period_end'):
                self.fields[name].disabled = True
            for name in ('evidence', 'trial_balance'):
                self.fields[name].required = False
                self.fields[name].help_text = 'Leave blank to retain the exact previous document.'
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        data = super().clean()
        mode = data.get('row_input') or 'manual'
        data['row_input'] = mode
        if mode == 'csv' and not data.get('row_csv'):
            self.add_error('row_csv', 'Attach the complete replacement row CSV.')
        elif mode != 'csv' and data.get('row_csv'):
            self.add_error('row_input', 'Select CSV replacement to use the uploaded file; it will not be silently ignored.')
        return data


class RowForm(forms.Form):
    kind = forms.ChoiceField(choices=(('', 'Choose kind'), ('receipt', 'Receipt'), ('expenditure', 'Expenditure')))
    category = forms.ChoiceField(choices=[('', 'Choose category'), ('Receipt categories', list(services.RECEIPTS.items())),
        ('Expenditure classes', list(services.EXPENDITURES.items()))])
    account = forms.ModelChoiceField(queryset=LedgerAccount.objects.none(), required=False,
        help_text='Required except for explicit certified zero without an account.')
    amount = forms.DecimalField(max_digits=18, decimal_places=2)
    source_row = forms.CharField(max_length=255, label='Unique source page / leaf row')

    def __init__(self, *args, owner_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = LedgerAccount.objects.filter(department_id=owner_id)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


Rows = formset_factory(RowForm, extra=0, min_num=2, validate_min=True, max_num=100,
    validate_max=True, absolute_max=100, can_delete=True)


@login_required
@require_GET
def register(request):
    query = services.visible(request.user)
    from . import budget_cash
    try:
        budget_cash.visible(request.user)
        can_cash = True
    except PermissionDenied:
        can_cash = False
    search = request.GET.get('q', '').strip()[:255]
    status = request.GET.get('status', '')
    if search:
        query = query.filter(Q(payload__reference__icontains=search) | Q(scope__entity_label__icontains=search)
            | Q(scope__fund__code__icontains=search))
    if status in ('submitted', 'approved', 'returned'):
        query = query.filter(status=status)
    params = request.GET.copy(); params.pop('page', None)
    return render(request, 'accounting/summary_register.html', {'page': Paginator(query, 50).get_page(request.GET.get('page')),
        'q': search, 'status': status, 'querystring': params.urlencode(), 'can_prepare': services.permitted(request.user, 'prepare'),
        'can_cash': can_cash})


@login_required
@require_http_methods(['GET', 'POST'])
def create(request, public_id=None):
    if not services.permitted(request.user, 'prepare'):
        raise PermissionDenied
    owner = department_for_user(request.user)
    previous, initial, row_initial = None, {}, []
    if public_id:
        previous = get_object_or_404(services.visible(request.user), public_id=public_id, department_id=owner.pk)
        try:
            payload = services.verify(previous)
        except ValidationError as exc:
            return HttpResponse(' '.join(exc.messages), status=409)
        initial = {key: value for key, value in payload.items() if key in AdoptionForm.base_fields}
        scope = previous.scope
        initial.update(fund=scope.fund_id, budget_department=scope.budget_department_id,
            treasury_department=scope.treasury_department_id, entity_key=scope.entity_key, entity_label=scope.entity_label,
            period_start=scope.period_start, period_end=scope.period_end,
            receipt_total=payload['totals']['receipt'], expenditure_total=payload['totals']['expenditure'],
            expected_latest=scope.versions.aggregate(n=Max('version'))['n'])
        initial.pop('evidence', None); initial.pop('trial_balance', None)
        if len(payload['rows']) <= 100:
            row_initial = [{**row, 'account': row['account_id']} for row in payload['rows']]
        else:
            initial['row_input'] = 'retain'
    data = request.POST if request.method == 'POST' else None
    form = AdoptionForm(data, request.FILES or None, actor=request.user, previous=previous, initial=initial)
    rows = Rows(data, initial=row_initial, form_kwargs={'owner_id': owner.pk})
    if request.method == 'POST' and form.is_valid():
        values = dict(form.cleaned_data)
        mode, upload = values.pop('row_input'), values.pop('row_csv')
        supplied = None
        if mode == 'manual':
            if rows.is_valid():
                supplied = [{'kind': row['kind'], 'category': row['category'],
                    'account_id': row['account'].pk if row['account'] else None,
                    'amount': row['amount'], 'source_row': row['source_row']}
                    for row in rows.cleaned_data if row and not row.get('DELETE')]
        elif mode == 'retain' and previous:
            supplied = previous.payload['rows']
        elif mode == 'csv':
            try:
                supplied = summary_csv.parse(upload, owner.pk)
            except ValidationError as exc:
                form.add_error('row_csv', exc)
        for field in ('fund', 'budget_department', 'treasury_department'):
            values[field + '_id'] = values.pop(field).pk
        for field in ('evidence', 'trial_balance'):
            if values[field] is None and previous:
                values[field] = io.BytesIO(bytes(getattr(previous, field)))
                values[field].name = previous.payload[field]['name']
        if supplied is not None:
            try:
                record = services.propose(actor=request.user, rows=supplied, **values)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect('accounting:summary_detail', public_id=record.public_id)
    return render(request, 'accounting/summary_form.html', {'form': form, 'formset': rows, 'previous': previous,
        'receipt_categories': services.RECEIPTS, 'expenditure_categories': services.EXPENDITURES})


@login_required
@require_GET
def csv_template(request):
    if not services.permitted(request.user, 'prepare'):
        raise PermissionDenied
    response = HttpResponse(','.join(summary_csv.COLUMNS) + '\r\n', content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="joint-actuals-row-template.csv"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_GET
def detail(request, public_id):
    record = get_object_or_404(services.visible(request.user), public_id=public_id)
    try:
        services.verify(record)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409)
    own = record.department_id == department_for_user(request.user).pk
    row_query = request.GET.get('row_q', '').strip()[:255]
    source_rows = record.payload['rows']
    matching = [row for row in source_rows if not row_query or any(row_query.casefold() in str(row[key]).casefold()
        for key in ('source_row', 'account_code', 'account_title', 'category_label', 'kind', 'amount'))]
    row_params = request.GET.copy(); row_params.pop('rows_page', None)
    history_params = request.GET.copy(); history_params.pop('page', None)
    return render(request, 'accounting/summary_detail.html', {'record': record,
        'row_page': Paginator(matching, 100).get_page(request.GET.get('rows_page')),
        'row_q': row_query, 'row_count': len(source_rows), 'row_querystring': row_params.urlencode(),
        'history_querystring': history_params.urlencode(),
        'history': Paginator(services.visible(request.user).filter(scope_id=record.scope_id), 25).get_page(request.GET.get('page')),
        'can_prepare': own and services.permitted(request.user, 'prepare'),
        'can_review': own and services.permitted(request.user, 'review') and record.status == record.SUBMITTED
            and record.prepared_by_id != request.user.pk, 'can_export': services.permitted(request.user, 'export')})


@login_required
@require_POST
def decide(request, public_id):
    record = get_object_or_404(services.visible(request.user), public_id=public_id)
    if request.POST.get('decision') not in ('approve', 'return'):
        return HttpResponse('Choose adopt or return.', status=400)
    try:
        services.review(record, request.user, approve=request.POST['decision'] == 'approve',
            note=request.POST.get('note'), authority=request.POST.get('authority'),
            verified_documents=request.POST.get('verified_documents') == 'yes')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('accounting:summary_detail', public_id=record.public_id)


@login_required
@require_GET
def export(request, public_id, kind):
    if not services.permitted(request.user, 'export'):
        raise PermissionDenied
    record = get_object_or_404(services.visible(request.user), public_id=public_id)
    try:
        payload = services.verify(record)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409)
    if kind in ('snapshot', 'package'):
        content = json.dumps({'payload': payload, 'payload_checksum': record.payload_checksum,
            'decision': services.decision_snapshot(record), 'decision_checksum': record.decision_checksum},
            ensure_ascii=False, indent=2).encode('utf-8')
        suffix = 'json'
        if kind == 'package':
            members = {'evidence.json': content}
            for field, stem in (('evidence', 'certificate'), ('trial_balance', 'trial-balance')):
                original = bytes(getattr(record, field))
                extension = 'pdf' if original.startswith(b'%PDF-') else 'png' if original.startswith(b'\x89PNG') else 'jpg'
                members[f'{stem}.{extension}'] = original
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                for name, original in members.items():
                    # Fixed safe names and timestamps make repeated decided exports reproducible.
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, original)
            content, suffix = buffer.getvalue(), 'zip'
    elif kind in ('evidence', 'trial_balance'):
        content = bytes(getattr(record, kind))
        suffix = 'pdf' if content.startswith(b'%PDF-') else 'png' if content.startswith(b'\x89PNG') else 'jpg'
    else:
        return HttpResponse('Unknown evidence kind.', status=404)
    filename = f'summary-actuals-{record.public_id}-{kind}.{suffix}'
    receipt = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='budget-summary-actuals', filename=filename,
        metadata={'record': str(record.public_id), 'kind': kind, 'payload_checksum': record.payload_checksum})
    services.event(record, request.user, 'summary_actual_exported')
    response = HttpResponse(content, content_type={'pdf': 'application/pdf', 'png': 'image/png',
        'jpg': 'image/jpeg', 'json': 'application/json; charset=utf-8', 'zip': 'application/zip'}[suffix])
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-GRAND-Export-SHA256'] = receipt['sha256']
    return response
