import io
import json
import uuid
import zipfile
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods
from src.export_archive import archive_export
from . import budget_cash_preparations as service, budget_cash
from . import budget_cash_certifications as certifications
from .access import department_for_user
from .budget_cash_preparation_forms import PreparationForm
from .budget_cash_certification_forms import DecisionForm
from .models import AccountingAuditEvent


@login_required
@require_GET
def register(request):
    query = service.visible(request.user)
    search = request.GET.get('q', '').strip()[:255]
    if search:
        match = (Q(fund__code__icontains=search) | Q(fund__name__icontains=search)
            | Q(payload__native__payload__scope__fund__code__icontains=search)
            | Q(payload__native__payload__scope__fund__name__icontains=search)
            | Q(entity_key__icontains=search) | Q(prepared_by_label__icontains=search))
        try: match |= Q(public_id=uuid.UUID(search))
        except ValueError: pass
        query = query.filter(match)
    params = request.GET.copy(); params.pop('page', None)
    return render(request, 'accounting/native_cash_register.html', {'page': Paginator(query, 50).get_page(request.GET.get('page')),
        'q': search, 'querystring': params.urlencode(), 'can_prepare': service.permitted(request.user, 'prepare')})


@login_required
@require_http_methods(['GET', 'POST'])
def create(request, public_id=None):
    if not service.permitted(request.user, 'prepare'): raise PermissionDenied
    previous, initial = None, {}
    if public_id:
        previous = get_object_or_404(service.visible(request.user), public_id=public_id,
            department_id=department_for_user(request.user).pk)
        try: payload = service.verify(previous)
        except ValidationError as error: return HttpResponse(' '.join(error.messages), status=409)
        initial = {'fund': previous.fund_id, 'opening_batch': payload['native']['payload']['opening']['id'],
            'budget_department': previous.budget_department_id, 'treasury_department': previous.treasury_department_id,
            'entity_key': previous.entity_key, 'coverage_authority': payload['native']['payload']['scope']['coverage_authority'],
            'balance_date': previous.balance_date, 'boundary': previous.boundary,
            'restriction_source': previous.restriction_source_id, 'expected_latest': previous.version}
    form = PreparationForm(request.POST if request.method == 'POST' else None,
        actor=request.user, previous=previous, initial=initial)
    if request.method == 'POST' and form.is_valid():
        values = dict(form.cleaned_data)
        for key in ('fund', 'opening_batch', 'budget_department', 'treasury_department', 'restriction_source'):
            selected = values.pop(key); values[key + '_id'] = selected.pk if selected else None
        if previous and values['expected_latest'] != previous.version:
            form.add_error(None, 'Use the displayed predecessor version; reload the latest preparation.')
        else:
            try: record = service.prepare(actor=request.user, **values)
            except ValidationError as error: form.add_error(None, error)
            else: return redirect('accounting:native_cash_detail', public_id=record.public_id)
    return render(request, 'accounting/native_cash_form.html', {'form': form, 'previous': previous})


@login_required
@require_GET
def detail(request, public_id):
    record = get_object_or_404(service.visible(request.user), public_id=public_id)
    return _detail(request, record)


def _detail(request, record, *, submitted_role=None, submitted_form=None, status=200):
    try:
        payload = service.verify(record)
        joint = certifications.snapshot(record, request.user)['payload']
    except ValidationError as error: return HttpResponse(' '.join(error.messages), status=409)
    decisions = joint['decisions']
    decided_roles = {item['payload']['identity']['role'] for item in decisions}
    decided_actors = {item['payload']['identity']['actor_id'] for item in decisions}
    owner = department_for_user(request.user)
    decision_forms = []
    if joint['status'] != 'returned' and request.user.pk != record.prepared_by_id and request.user.pk not in decided_actors:
        for role in certifications.ROLES:
            office = record.department_id if role == 'accountant' else record.treasury_department_id
            if role not in decided_roles and owner.pk == office and certifications.permitted(request.user, role):
                decision_forms.append({'role': role, 'label': role.title(),
                    'form': submitted_form if submitted_role == role else DecisionForm()})
    native = payload['native']['payload']; selected = set(native['selected_journal_ids'])
    lines = [{'journal': entry, 'line': line, 'included': entry['id'] in selected}
        for entry in native['ledger']['payload']['journals'] for line in entry['lines']]
    restrictions = payload['restriction_source']['payload']['restrictions'] if payload['restriction_source'] else []
    line_search, row_search = request.GET.get('line_q', '').strip()[:255], request.GET.get('row_q', '').strip()[:255]
    matching_lines = [row for row in lines if not line_search or line_search.casefold() in
        ' '.join(str(value) for value in (row['journal']['reference'], row['line']['account']['code'], row['line']['account']['title'], row['line']['memo'])).casefold()]
    matching_rows = [row for row in restrictions if not row_search or any(row_search.casefold() in str(value).casefold() for value in row.values())]
    params = request.GET.copy()
    def page_params(name):
        copied = params.copy(); copied.pop(name, None); return copied.urlencode()
    history = service.visible(request.user).filter(department_id=record.department_id, fund_id=record.fund_id,
        entity_key=record.entity_key, balance_date=record.balance_date, boundary=record.boundary)
    return render(request, 'accounting/native_cash_detail.html', {'record': record, 'payload': payload, 'native': native,
        'joint': joint, 'decision_forms': decision_forms,
        'lines': Paginator(matching_lines, 100).get_page(request.GET.get('lines_page')), 'line_count': len(lines),
        'line_q': line_search, 'line_params': page_params('lines_page'),
        'rows': Paginator(matching_rows, 100).get_page(request.GET.get('rows_page')), 'row_count': len(restrictions),
        'row_q': row_search, 'row_params': page_params('rows_page'),
        'history': Paginator(history, 25).get_page(request.GET.get('history_page')), 'history_params': page_params('history_page'),
        'can_export': service.permitted(request.user, 'export'),
        'can_export_originals': service.permitted(request.user, 'export') and budget_cash.permitted(request.user, 'export'),
        'can_prepare': record.department_id == owner.pk and service.permitted(request.user, 'prepare')}, status=status)


@login_required
@require_http_methods(['POST'])
def decide(request, public_id, role):
    if not certifications.permitted(request.user, role): raise PermissionDenied
    record = get_object_or_404(service.visible(request.user), public_id=public_id)
    office = record.department_id if role == 'accountant' else record.treasury_department_id
    if department_for_user(request.user).pk != office: raise PermissionDenied
    form = DecisionForm(request.POST)
    if form.is_valid():
        values = form.cleaned_data
        try:
            certifications.decide(preparation_id=record.pk, actor=request.user, role=role,
                certify=values['outcome'] == 'certify', authority=values['authority'], note=values['note'])
        except ValidationError as error:
            # A replay/closed preparation has no pending form. Retain the error
            # visibly even when the role form is no longer actionable.
            return HttpResponse(' '.join(error.messages), status=409)
        else: return redirect('accounting:native_cash_detail', public_id=record.public_id)
    return _detail(request, record, submitted_role=role, submitted_form=form, status=400)


@login_required
@require_GET
def export(request, public_id, kind):
    if not service.permitted(request.user, 'export'): raise PermissionDenied
    record = get_object_or_404(service.visible(request.user), public_id=public_id)
    try: payload = service.verify(record)
    except ValidationError as error: return HttpResponse(' '.join(error.messages), status=409)
    linked = payload['restriction_source'] is not None
    joint_checksum = None
    if linked and kind in ('package', 'joint_package', 'certificate', 'reconciliation') and not budget_cash.permitted(request.user, 'export'):
        raise PermissionDenied('Original historical documents require their separate source export permission.')
    if kind in ('snapshot', 'package', 'joint_snapshot', 'joint_package'):
        try:
            evidence = certifications.snapshot(record, request.user) if kind.startswith('joint_') else {
                'preparation': str(record.public_id), 'payload': payload, 'payload_checksum': record.payload_checksum}
        except ValidationError as error: return HttpResponse(' '.join(error.messages), status=409)
        if kind.startswith('joint_'): joint_checksum = evidence['checksum']
        content = json.dumps(evidence, ensure_ascii=False, indent=2).encode('utf-8')
        suffix = 'json'
        if kind in ('package', 'joint_package'):
            members = {'joint-evidence.json' if kind == 'joint_package' else 'evidence.json': content}
            if linked:
                for field in ('certificate', 'reconciliation'):
                    original = bytes(getattr(record, field))
                    extension = 'pdf' if original.startswith(b'%PDF-') else 'png' if original.startswith(b'\x89PNG') else 'jpg'
                    members[f'{field}.{extension}'] = original
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                for name, original in members.items():
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, original)
            content, suffix = buffer.getvalue(), 'zip'
    elif kind in ('certificate', 'reconciliation') and linked:
        content = bytes(getattr(record, kind))
        suffix = 'pdf' if content.startswith(b'%PDF-') else 'png' if content.startswith(b'\x89PNG') else 'jpg'
    else: return HttpResponse('No retained evidence of that kind.', status=404)
    filename = f'native-budget-cash-{record.public_id}-{kind}.{suffix}'
    metadata = {'preparation': str(record.public_id), 'payload_checksum': record.payload_checksum, 'kind': kind}
    if joint_checksum: metadata['joint_checksum'] = joint_checksum
    receipt = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='native-budget-cash', filename=filename, metadata=metadata)
    AccountingAuditEvent.objects.create(department_id=record.department_id, department_label=record.department_label,
        actor_id=request.user.pk, actor_label=(request.user.get_full_name() or request.user.username)[:160],
        action='native_budget_cash_exported', snapshot={'preparation': str(record.public_id), 'kind': kind, 'sha256': receipt['sha256']})
    response = HttpResponse(content, content_type={'json': 'application/json; charset=utf-8', 'zip': 'application/zip',
        'pdf': 'application/pdf', 'png': 'image/png', 'jpg': 'image/jpeg'}[suffix])
    response['Content-Disposition'] = f'attachment; filename="{filename}"'; response['X-Content-Type-Options'] = 'nosniff'
    response['X-GRAND-Export-SHA256'] = receipt['sha256']
    return response
