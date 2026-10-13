"""Scoped retained cash inspection and exports; no native cash certification."""
import io
import json
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from src.export_archive import archive_export
from .access import department_for_user
from . import budget_cash as services
from .budget_cash_forms import CashForm, Rows, COLUMNS, parse_csv


@login_required
@require_GET
def register(request):
    query = services.visible(request.user)
    search = request.GET.get('q', '').strip()[:255]
    status = request.GET.get('status', '')
    if search:
        query = query.filter(Q(payload__reference__icontains=search) |
            Q(payload__scope__entity_label__icontains=search) | Q(payload__scope__fund_code__icontains=search))
    if status in ('submitted', 'adopted', 'returned'):
        query = query.filter(status=status)
    params = request.GET.copy(); params.pop('page', None)
    return render(request, 'accounting/budget_cash_register.html', {
        'page': Paginator(query, 50).get_page(request.GET.get('page')),
        'q': search, 'status': status, 'querystring': params.urlencode(),
        'can_prepare': services.permitted(request.user, 'prepare')})


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
        initial = {key: value for key, value in payload.items() if key in CashForm.base_fields}
        initial.update(fund=previous.fund_id, budget_department=previous.budget_department_id,
            treasury_department=previous.treasury_department_id, entity_key=previous.entity_key,
            entity_label=payload['scope']['entity_label'], balance_date=previous.balance_date,
            boundary=previous.boundary, expected_latest=previous.version)
        for field in ('certificate', 'reconciliation'): initial.pop(field, None)
        if len(payload['restrictions']) <= 100:
            row_initial = payload['restrictions']
        else:
            initial['row_input'] = 'retain'
    data = request.POST if request.method == 'POST' else None
    form = CashForm(data, request.FILES or None, actor=request.user, previous=previous, initial=initial)
    rows = Rows(data, initial=row_initial)
    if request.method == 'POST' and form.is_valid():
        values = dict(form.cleaned_data)
        mode, upload = values.pop('row_input'), values.pop('row_csv')
        supplied = None
        if mode == 'manual' and rows.is_valid():
            supplied = [{key: row[key] for key in COLUMNS} for row in rows.cleaned_data if row and not row.get('DELETE')]
        elif mode == 'csv':
            try:
                supplied = parse_csv(upload)
            except ValidationError as exc:
                form.add_error('row_csv', exc)
        elif mode == 'retain' and previous:
            supplied = previous.payload['restrictions']
        for field in ('fund', 'budget_department', 'treasury_department'):
            values[field + '_id'] = values.pop(field).pk
        for field in ('certificate', 'reconciliation'):
            if values[field] is None and previous:
                values[field] = io.BytesIO(bytes(getattr(previous, field)))
                values[field].name = previous.payload[field]['name']
        if previous and values['expected_latest'] != previous.version:
            form.add_error(None, 'The successor must use its displayed predecessor version; reload the latest evidence.')
        elif supplied is not None:
            try:
                record = services.propose(actor=request.user, rows=supplied, **values)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect('accounting:budget_cash_detail', public_id=record.public_id)
    return render(request, 'accounting/budget_cash_form.html', {'form': form, 'formset': rows, 'previous': previous})


@login_required
@require_GET
def csv_template(request):
    if not services.permitted(request.user, 'prepare'):
        raise PermissionDenied
    response = HttpResponse(','.join(COLUMNS) + '\r\n', content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="cash-restriction-template.csv"'
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
    rows = record.payload['restrictions']
    search = request.GET.get('row_q', '').strip()[:255]
    matching = [row for row in rows if not search or any(search.casefold() in str(value).casefold() for value in row.values())]
    params = request.GET.copy(); params.pop('rows_page', None)
    history_params = request.GET.copy(); history_params.pop('page', None)
    history = services.visible(request.user).filter(department_id=record.department_id,
        fund_id=record.fund_id, entity_key=record.entity_key, balance_date=record.balance_date, boundary=record.boundary)
    return render(request, 'accounting/budget_cash_detail.html', {'record': record,
        'row_page': Paginator(matching, 100).get_page(request.GET.get('rows_page')), 'row_count': len(rows),
        'row_q': search, 'row_querystring': params.urlencode(),
        'history': Paginator(history, 25).get_page(request.GET.get('page')),
        'history_querystring': history_params.urlencode(),
        'can_export': services.permitted(request.user, 'export'),
        'can_prepare': record.department_id == department_for_user(request.user).pk and services.permitted(request.user, 'prepare'),
        'can_review': record.department_id == department_for_user(request.user).pk and
            services.permitted(request.user, 'review') and record.status == 'submitted' and
            record.prepared_by_id != request.user.pk})


@login_required
@require_POST
def decide(request, public_id):
    record = get_object_or_404(services.visible(request.user), public_id=public_id)
    if request.POST.get('decision') not in ('adopt', 'return'):
        return HttpResponse('Choose adopt or return.', status=400)
    try:
        services.review(record, request.user, adopt=request.POST['decision'] == 'adopt',
            note=request.POST.get('note'), authority=request.POST.get('authority'),
            verified_documents=request.POST.get('verified_documents') == 'yes')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('accounting:budget_cash_detail', public_id=record.public_id)


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
            'decision': services.decision(record), 'decision_checksum': record.decision_checksum},
            ensure_ascii=False, indent=2).encode('utf-8')
        suffix = 'json'
        if kind == 'package':
            members = {'evidence.json': content}
            for field in ('certificate', 'reconciliation'):
                original = bytes(getattr(record, field))
                extension = 'pdf' if original.startswith(b'%PDF-') else 'png' if original.startswith(b'\x89PNG') else 'jpg'
                members[f'{field}.{extension}'] = original
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                for name, original in members.items():
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, original)
            content, suffix = buffer.getvalue(), 'zip'
    elif kind in ('certificate', 'reconciliation'):
        content = bytes(getattr(record, kind))
        suffix = 'pdf' if content.startswith(b'%PDF-') else 'png' if content.startswith(b'\x89PNG') else 'jpg'
    else:
        return HttpResponse('Unknown cash evidence kind.', status=404)
    filename = f'budget-cash-{record.public_id}-{kind}.{suffix}'
    receipt = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='budget-cash-evidence', filename=filename,
        metadata={'record': str(record.public_id), 'kind': kind, 'payload_checksum': record.payload_checksum})
    services.event(record, request.user, 'budget_cash_exported')
    response = HttpResponse(content, content_type={'pdf': 'application/pdf', 'png': 'image/png',
        'jpg': 'image/jpeg', 'json': 'application/json; charset=utf-8', 'zip': 'application/zip'}[suffix])
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-GRAND-Export-SHA256'] = receipt['sha256']
    return response
