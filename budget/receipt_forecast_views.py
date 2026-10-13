"""Guided forecast clerk intake, retained review and complete-source exports."""
from decimal import Decimal
from copy import deepcopy
from hashlib import sha256
import json
import unicodedata

from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounting.models import Fund
from accounting.summary_actuals import RECEIPTS, text
from src.export_archive import archive_export
from .access import budget_permission_required, can_act_on_budget, department_for_user, has_budget_permission
from .models import BudgetReceiptForecast as Record
from .office_form_views import owned_version
from . import receipt_forecasts as forecasts, receipt_forecast_reviews as service
from . import form1_account_reviews

SALT = 'budget-receipt-forecast-clerk-v1'


class Intake(forms.Form):
    preview = forms.CharField(widget=forms.HiddenInput)
    allocation = forms.JSONField(widget=forms.HiddenInput)
    coverage_reference = forms.CharField(label='Complete entity/source coverage reference', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    coverage_confirmed = forms.BooleanField(label='I checked all entities and every forecast source, including exclusions and overlaps.')


def sources(proposal, fund, actor):
    records = service.inventory(proposal, fund)
    if not records:
        raise ValidationError('Prepare and independently accept the complete office reconciliation first.')
    return [forecasts.capture(reconciliation=record, actor=actor) for record in records]


def preview_data(proposal, fund, actor, captured):
    return dict(actor=actor.pk, proposal=str(proposal.public_id), fund=fund.pk,
        sources={item['payload']['scope']['entity_key']: item['checksum'] for item in captured},
        observed_on=captured[0]['observed_on'],
        latest=proposal.receipt_forecasts.filter(fund=fund).aggregate(n=Max('version'))['n'] or 0)


def clerk_proposals(captured, supplied):
    """Typed clerk choices; derive amounts only from explicit included components."""
    if not isinstance(supplied, dict) or set(supplied) != {'half_sources', 'entities'}:
        raise ValidationError('Retain the complete worksheet and entity allocation schedules.')
    if not isinstance(supplied['entities'], list):
        raise ValidationError('Retain all entity schedules.')
    by_entity = {item['payload']['scope']['entity_key']: item for item in captured}
    proposals = []; seen = set()
    for entity in supplied['entities']:
        if not isinstance(entity, dict) or set(entity) != {'entity_key', 'half_components', 'proposed_components', 'coverage'}:
            raise ValidationError('Retain the exact entity component and category schedules.')
        identity = entity['entity_key']
        if not isinstance(identity, str) or identity not in by_entity or identity in seen:
            raise ValidationError('Use every original entity once without adding another scope.')
        seen.add(identity); components = {}
        for column in ('half_estimate', 'proposed'):
            supplied_rows = entity['half_components' if column == 'half_estimate' else 'proposed_components']
            if not isinstance(supplied_rows, list):
                raise ValidationError('Supply complete component rows.')
            rows = []
            for row in supplied_rows:
                if not isinstance(row, dict) or set(row) != {'id', 'source_id', 'amount', 'disposition', 'category',
                    'account_id', 'funding_reference', 'overlap_of', 'basis'}:
                    raise ValidationError('Retain each explicit component amount, mapping and overlap choice.')
                reference = row['funding_reference']
                if not isinstance(reference, str):
                    raise ValidationError('Use a written funding coverage reference.')
                reference = reference.strip()
                if reference:
                    reference = text(reference, 'funding coverage reference', 255)
                if row['disposition'] in ('include', 'overlap') and not reference:
                    raise ValidationError('Included/overlapping components need a shared funding coverage reference.')
                basis = text(row['basis'], 'component classification/exclusion basis', 1600)
                coverage_key = 'coverage-'+sha256(unicodedata.normalize('NFC', reference).casefold().encode()).hexdigest() if reference else ''
                account = row['account_id']
                if account not in (None, ''):
                    if not isinstance(account, str) or not account.isdecimal():
                        raise ValidationError('Choose an original account from the captured list.')
                    account = int(account)
                else:
                    account = None
                rows.append(dict(key=row['id'], source_id=row['source_id'], amount=row['amount'],
                    disposition=row['disposition'], category=row['category'], account_id=account,
                    coverage_key=coverage_key, overlap_of=row['overlap_of'],
                    basis=basis+('\nFunding coverage reference: '+reference if reference else '')))
            components[column] = rows
        declarations = entity['coverage']; coverage = {}
        if not isinstance(declarations, dict) or set(declarations) != {'half_estimate', 'proposed'}:
            raise ValidationError('Retain both complete category schedules.')
        for column in ('half_estimate', 'proposed'):
            if not isinstance(declarations[column], list):
                raise ValidationError('Retain every category declaration.')
            coverage[column] = []
            for row in declarations[column]:
                if not isinstance(row, dict) or set(row) != {'category', 'coverage', 'basis'}:
                    raise ValidationError('Retain explicit category coverage and its basis.')
                value = sum((forecasts.amount(item['amount']) for item in components[column]
                    if item['disposition'] == 'include' and item['category'] == row['category']), Decimal('0.00'))
                coverage[column].append(dict(row, amount=str(value)))
        proposals.append(forecasts.propose(by_entity[identity], half_sources=supplied['half_sources'],
            half_components=components['half_estimate'], proposed_components=components['proposed'], coverage=coverage))
    if seen != set(by_entity):
        raise ValidationError('Retain every original reporting entity in this Fund package.')
    return proposals


def editor_data(captured, allocation=None):
    body = captured[0]['payload']
    eligible = {column: forecasts._accounts(body, column) for column in ('half_estimate', 'proposed')}
    return dict(entities=[dict(key=item['payload']['scope']['entity_key'], label=item['payload']['scope']['entity_label']) for item in captured],
        resources=[dict(id=str(row['id']), amount=row['amount'], description=row['description'],
            reference=row['funding_source']['code'], fund=row['funding_source']['fund_code'] or 'No assigned Fund', basis=row['basis'])
            for row in body['resources']['rows']],
        accounts=[dict(id=str(row['id']), label=row['code']+' — '+row['title'],
            columns=[column for column in eligible if row['id'] in eligible[column]]) for row in body['accounts']
            if any(row['id'] in accounts for accounts in eligible.values())],
        categories=[dict(key=key, label=label) for key, label in RECEIPTS.items()], allocation=allocation)


@require_GET
@budget_permission_required('view_budget_receipt_forecasts')
def register(request, public_id):
    proposal = owned_version(request, public_id)
    query = proposal.receipt_forecasts.select_related('fund').all()
    page = Paginator(query, 50).get_page(request.GET.get('page'))
    funds = Fund.objects.filter(department_id=proposal.fiscal_year.department_id,
        pk__in=proposal.summary_reconciliations.values('fund_id')).order_by('code')
    return render(request, 'budget/receipt_forecast_register.html', dict(proposal=proposal, page=page, funds=funds,
        can_prepare=can_act_on_budget(request.user, 'prepare_budget_receipt_forecasts')))


@require_http_methods(['GET', 'POST'])
@budget_permission_required('prepare_budget_receipt_forecasts')
def prepare(request, public_id, fund_id):
    proposal = owned_version(request, public_id)
    fund = get_object_or_404(Fund, pk=fund_id, department_id=proposal.fiscal_year.department_id)
    try:
        captured = sources(proposal, fund, request.user)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    observed = preview_data(proposal, fund, request.user, captured)
    token = signing.dumps(observed, salt=SALT)
    form = Intake(request.POST if request.method == 'POST' else None, initial={'preview': token})
    allocation = None
    if request.method == 'POST' and form.is_valid():
        allocation = form.cleaned_data['allocation']
        try:
            original = signing.loads(form.cleaned_data['preview'], salt=SALT, max_age=86400)
            if original != observed:
                raise ValidationError('This preview changed or belongs to another actor. Reload current sources before preparing.')
            proposals = clerk_proposals(captured, allocation)
            record = service.prepare(proposal=proposal, actor=request.user, fund_id=fund.pk, proposals=proposals,
                entity_inventory=[dict(key=item['payload']['scope']['entity_key'], label=item['payload']['scope']['entity_label']) for item in captured],
                coverage_reference=form.cleaned_data['coverage_reference'], coverage_confirmed=form.cleaned_data['coverage_confirmed'],
                expected_latest=original['latest'])
        except (ValidationError, signing.BadSignature) as error:
            form.add_error(None, error if isinstance(error, ValidationError) else 'The preparation preview is invalid or expired.')
        else:
            return redirect('budget:receipt_forecast_detail', public_id=record.public_id)
    # Preserve entered rows even when another field (e.g. coverage confirmation) fails.
    if allocation is None and form.is_bound:
        allocation = form.cleaned_data.get('allocation')
    return render(request, 'budget/receipt_forecast_prepare.html', dict(proposal=proposal, fund=fund,
        form=form, editor=editor_data(captured, allocation)))


def owned_record(request, public_id):
    record = get_object_or_404(Record.objects.select_related('proposal', 'fund'), public_id=public_id,
        department_id=department_for_user(request.user).pk)
    return record


@require_GET
@budget_permission_required('view_budget_receipt_forecasts')
def detail(request, public_id):
    record = owned_record(request, public_id)
    try:
        snapshot = service.snapshot(record, request.user)
        current = service.is_current(record, request.user) if record.status == 'approved' else False
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    members = deepcopy(snapshot['payload']['group']['members'])
    for member in members:
        resources = {str(row['id']): row for row in member['forecast']['payload']['capture']['payload']['resources']['rows']}
        for column, schedule in member['forecast']['payload']['columns'].items():
            original = {row['id']: row for row in schedule['sources']}
            labels = {}
            for index, row in enumerate(schedule['components'], 1):
                source = resources[row['source_id']] if column == 'proposed' else original[row['source_id']]
                row['source_label'] = (source['funding_source']['code']+' · '+source['description']) if column == 'proposed' else source['reference']
                row['source_basis'] = source['basis']
                row['as_of'] = original[row['source_id']].get('as_of', '')
                if row['as_of']:
                    row['source_basis'] += ' · Observed as of '+row['as_of']
                row['category_label'] = RECEIPTS.get(row['category'], '')
                labels[row['key']] = row['source_label']+' · component '+str(index)
            for row in schedule['components']:
                row['overlap_label'] = labels.get(row['overlap_of'], '')
            for row in schedule['categories']:
                row['label'] = RECEIPTS[row['category']]
    budget_year = members[0]['forecast']['payload']['capture']['payload']['scope']['budget_year']
    original = members[0]['forecast']['payload']
    roots = original['capture']['payload']['resource_roots'].values()
    labels = {row['proposal']+':'+str(row['resource_id']): row['resource']['funding_source']['code']+' · '+row['resource']['description'] for row in roots}
    labels.update({'half:'+row['id']: row['reference'] for row in original['columns']['half_estimate']['sources']})
    controls = deepcopy(snapshot['payload']['group']['controls'])
    for control in controls.values():
        for row in control['roots']:
            row['label'] = labels[row['root']]
    can_export = False
    if has_budget_permission(request.user, 'export_budget_receipt_forecasts'):
        try:
            service.require_visible(record, request.user, 'export')
        except PermissionDenied:
            pass
        else:
            can_export = True
    can_prepare_accounts = False
    if record.status == 'approved' and current:
        try: form1_account_reviews._access(record.proposal, record.fund, request.user, 'prepare')
        except PermissionDenied: pass
        else: can_prepare_accounts = True
    return render(request, 'budget/receipt_forecast_detail.html', dict(record=record, snapshot=snapshot, members=members,
        can_prepare_accounts=can_prepare_accounts,
        budget_year=budget_year, current_year=budget_year-1, current=current, controls=controls,
        can_review=record.status == 'prepared' and record.prepared_by_id != request.user.pk
            and can_act_on_budget(request.user, 'review_budget_receipt_forecasts'),
        can_export=can_export))


@require_POST
@budget_permission_required('review_budget_receipt_forecasts')
def review(request, public_id):
    record = owned_record(request, public_id)
    if request.POST.get('action') not in ('approve', 'return'):
        return HttpResponse('Choose approve or return.', status=400)
    try:
        service.review(record, request.user, approve=request.POST['action'] == 'approve',
            note=request.POST.get('note'), authority=request.POST.get('authority'))
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    return redirect('budget:receipt_forecast_detail', public_id=record.public_id)


@require_GET
@budget_permission_required('export_budget_receipt_forecasts')
def export(request, public_id):
    record = owned_record(request, public_id)
    try:
        retained = service.snapshot(record, request.user, export=True)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    content = json.dumps(retained, ensure_ascii=False, indent=2).encode('utf-8')
    filename = f'budget-receipt-forecast-{record.public_id}-v{record.version}.json'
    archived = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='budget-receipt-forecast', filename=filename, metadata=dict(payload_checksum=record.payload_checksum))
    service.record_event(record, 'receipt_forecast_exported', request.user, snapshot=dict(payload_checksum=record.payload_checksum))
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256'] = archived['sha256']
    response['X-Content-Type-Options'] = 'nosniff'
    return response
