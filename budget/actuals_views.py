"""Proposal-scoped inspection and explicit certified-source choice."""
import csv
import json
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from .access import budget_access_required, can_act_on_budget, department_for_user
from .actuals_selection import preview_sources, select_source
from .models import BudgetVersion
from .planning_context import can_read_context
from .actuals_consolidation import unresolved_origins
from .actuals_scopes import available_scopes

SALT = 'budget.actuals-source-preview.v1'


class SelectionForm(forms.Form):
    preview = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
                             label='Why this source covers the office and period')


@require_http_methods(['GET', 'POST'])
@budget_access_required
def sources(request, public_id):
    version = get_object_or_404(BudgetVersion.objects.select_related('fiscal_year'),
        public_id=public_id, department_id=department_for_user(request.user).pk)
    if not can_read_context(request.user, version):
        raise PermissionDenied
    unresolved = unresolved_origins(version)
    editable = version.status in (BudgetVersion.DRAFT, BudgetVersion.RETURNED)
    can_select = editable and can_act_on_budget(request.user, 'prepare_budget_proposals')
    error_form = None
    status = 200
    if request.method == 'POST':
        if not can_act_on_budget(request.user, 'prepare_budget_proposals'):
            raise PermissionDenied
        error_form = SelectionForm(request.POST)
        if error_form.is_valid():
            try:
                data = signing.loads(error_form.cleaned_data['preview'], salt=SALT, max_age=86400)
                if data['actor'] != request.user.pk or data['version'] != str(version.public_id):
                    raise ValidationError('This preview belongs to another user or proposal.')
                select_source(version=version, actor=request.user, fund_id=data['fund_id'],
                    center_id=data['center_id'], prefix=data['prefix'], kind=data['kind'],
                    source_id=data['source_id'], expected_state_version=data['state'],
                    expected_rows_checksum=data['rows_checksum'], reason=error_form.cleaned_data['reason'])
            except (signing.BadSignature, KeyError, TypeError, ValueError):
                error_form.add_error(None, 'The source preview expired or is invalid. Inspect a fresh preview.')
            except ValidationError as exc:
                error_form.add_error(None, exc)
            else:
                messages.success(request, 'Certified source choice recorded with its reason and evidence.')
                key = f"{data['fund_id']}:{data['center_id']}:{data['prefix']}"
                return redirect(reverse('budget:actuals_sources', args=[version.public_id]) + '?' + urlencode({'scope': key}))
        status = 409
        version.refresh_from_db()
    # Submitted proposals show retained choices, without discovering later sources.
    scopes, discovery_errors = available_scopes(version, request.user) if editable else ({}, [])
    # Retain a clear path for a selected scope whose proposal lines were removed.
    for key, choice in version.actuals_source_selection.items():
        scopes.setdefault(key, {name: choice[name] for name in ('fund_id', 'center_id', 'prefix')})
        scopes[key].setdefault('label', f"Retained choice: {choice.get('fund_code', choice['fund_id'])} / {choice.get('center_code', choice['center_id'])} / {choice['prefix']}")
    selected = request.GET.get('scope', '')
    scope = scopes.get(selected)
    candidates, errors = [], list(discovery_errors)
    retained = version.actuals_source_selection.get(selected)
    origin = version.actuals_source_origins.get(selected)
    if scope and editable:
        try:
            version, candidates, preview_errors = preview_sources(version, request.user,
                scope['fund_id'], scope['center_id'], scope['prefix'])
            errors.extend(preview_errors)
        except ValidationError as exc:
            errors.extend(exc.messages)
        retained = version.actuals_source_selection.get(selected)
    def form(kind, source_id='', rows_checksum=None):
        token = signing.dumps({'actor': request.user.pk, 'version': str(version.public_id),
            'state': version.state_version, **{name: scope[name] for name in ('fund_id', 'center_id', 'prefix')},
            'kind': kind, 'source_id': source_id, 'rows_checksum': rows_checksum}, salt=SALT)
        return SelectionForm(initial={'preview': token}, auto_id=f'actuals_{kind}_%s')
    accounts = {line.account_id: f'{line.account.code} — {line.account.title}'
                for line in version.lines.select_related('account').filter(
                    fund_id=scope['fund_id'], responsibility_center_id=scope['center_id'])} if scope else {}
    for candidate in candidates:
        candidate['form'] = form(candidate['kind'], candidate['source_id'], candidate['rows_checksum'])
        candidate['evidence'] = json.dumps(candidate['rows'], ensure_ascii=False, indent=2)
        candidate['display_rows'] = [{**row,
            'account': f"{row['account_code']} — {row['account_title']}" if 'account_code' in row
                else accounts[row['account_id']],
            'has_proposal': row['account_id'] in accounts} for row in candidate['rows']]
    return render(request, 'budget/actuals_sources.html', {'version': version,
        'scopes': scopes.items(), 'selected': selected, 'scope': scope, 'candidates': candidates,
        'errors': errors, 'error_form': error_form, 'can_select': can_select,
        'origin': origin, 'unresolved': unresolved,
        'retained': json.dumps(retained, ensure_ascii=False, indent=2) if retained else '',
        'clear_form': form('clear') if retained and can_select else None, 'editable': editable}, status=status)


@require_GET
@budget_access_required
def schedule_export(request, public_id):
    from .planning_context import displayed_context
    from .views import _csv_text, archive_export
    from .services import record_event
    version = get_object_or_404(BudgetVersion, public_id=public_id,
        department_id=department_for_user(request.user).pk)
    try:
        context = displayed_context(version, request.user)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409)
    if not context or context.get('schema', 1) < 5:
        return HttpResponse('No retained object schedule exists for this proposal. Earlier snapshots remain unchanged.', status=409)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    writer = csv.writer(response)
    writer.writerow(('Coverage', 'Capture date', 'Budget year', 'Prior year', 'Current year',
        'Fund', 'Center', 'Account', 'Account title', 'Object class', 'Prior actual',
        'First-half actual', 'Second-half estimate', 'Current-year total', 'Proposed',
        'Proposal coverage', 'Prior evidence', 'First-half evidence', 'Proposal and estimate evidence') +
        (('Historical forecast evidence', 'Forecast review state') if context.get('schema', 1) >= 6 else ()) +
        (('Captured office ID', 'Captured office name') if context.get('schema', 1) >= 7 else ()))
    for row in context['certified_schedule']:
        writer.writerow(_csv_text(value) for value in (
            'Explicitly selected sources only; not issued Form 2', context['as_of'], context['budget_year'],
            context['prior_year'], context['current_year'], row['fund_code'], row['center_code'],
            row['account_code'], row['account_title'], row['expense_class'],
            row['prior_amount'] if row['prior_amount'] is not None else 'Missing',
            row['half_amount'] if row['half_amount'] is not None else 'Missing',
            row['estimate'] if row['estimate'] is not None else 'Missing',
            row['current_total'] if row['current_total'] is not None else 'Incomplete', row['proposed'],
            'Proposed' if row['has_proposal'] else 'No proposal line',
            json.dumps(row['prior_rows'], ensure_ascii=False), json.dumps(row['half_rows'], ensure_ascii=False),
            json.dumps(row['proposal_lines'], ensure_ascii=False)) +
            ((json.dumps(row.get('historical_forecast'), ensure_ascii=False), row.get('forecast_problem') or
              ('Current historical forecast' if row.get('historical_forecast') else 'Proposal-line estimate' if row['has_proposal'] else 'No historical forecast'))
             if context.get('schema', 1) >= 6 else ()) +
            ((row.get('office_id') or 'Missing', row.get('office_label') or 'Missing')
             if context.get('schema', 1) >= 7 else ()))
    filename = f'proposal-object-schedule-{version.public_id}.csv'
    receipt = archive_export(content=response.content, department=department_for_user(request.user),
        user=request.user, category='budget-object-schedule', filename=filename,
        metadata={'version': str(version.public_id), 'planning_context': context, 'issued_form_2': False})
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256'] = receipt['sha256']
    record_event(version, 'object_schedule_exported', request.user,
        snapshot={'sha256': receipt['sha256'], 'relative_path': receipt['relative_path']})
    return response
