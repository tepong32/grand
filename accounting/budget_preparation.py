"""Authenticated editor context; never accept a browser-supplied ledger capture.

The token pins the source, latest proposals and office choices seen by its maker.
It is evidence for submission validation, not approval or an expenditure certificate.
The existing proposal service remains the financial/classification authority.
"""
from datetime import date

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max

from . import budget_attributions as service
from .access import department_for_user
from .budget_claim_links import application_links
from .budget_native_sources import capture
from .budget_reviewed_components import source_components
from .models import BudgetExpenditureAttribution as Attribution


SALT = 'accounting.budget-preparation.v1'
MAX_AGE = 24 * 60 * 60


def _owner(actor):
    if not service.permitted(actor, 'prepare'):
        raise PermissionDenied
    return department_for_user(actor).pk


@transaction.atomic(using='finance')
def prepare(*, actor, fund_id, period_start, period_end, entry_ids):
    """Return renderable choices plus a signed, expiring submission context.

    Only explicit selected period journals enter the editor. Dependencies are
    shown as component choices or unresolved warnings, never silently selected.
    Read/capture and pending-version selection share the proposal service's lock.
    """
    owner_id = _owner(actor)
    fund = service._fund(actor, fund_id, 'prepare')
    if (not isinstance(entry_ids, list) or not 1 <= len(entry_ids) <= 250
            or any(type(key) is not int for key in entry_ids) or len(set(entry_ids)) != len(entry_ids)):
        raise ValidationError('Select between one and 250 distinct posted journals.')
    captured = capture(actor=actor, fund_id=fund.pk, period_start=period_start, period_end=period_end)
    entries = {entry['id']: entry for entry in captured['payload']['journals']}
    if not set(entry_ids) <= entries.keys():
        raise ValidationError('Select posted journals inside this fund and period.')
    latest = dict(Attribution.objects.filter(entry_id__in=entry_ids).values('entry_id')
                  .annotate(latest=Max('version')).values_list('entry_id', 'latest'))
    context = {'schema': 1, 'actor_id': actor.pk, 'owner_id': owner_id,
        'fund_id': fund.pk, 'fund_label': f'{fund.code} · {fund.name}',
        'period_start': period_start.isoformat(), 'period_end': period_end.isoformat(),
        'source_checksum': captured['checksum'], 'entries': [],
        'centers': service._centers(owner_id), 'components': {}, 'warnings': []}
    all_entries = service.source_entries(captured['payload'])
    for key in entry_ids:
        entry = entries[key]
        context['entries'].append({**{field: entry[field] for field in (
            'id', 'reference', 'entry_date', 'description', 'reversal_of_id', 'lineage')},
            'latest': latest.get(key, 0),
            'lines': [{field: line[field] for field in (
                'id', 'sequence', 'account', 'debit', 'credit', 'center')} for line in entry['lines']]})
        if entry['reversal_of_id']:
            parent = all_entries.get(entry['reversal_of_id'])
            if parent and entry['lineage']['exact_mirror']:
                def signature(line, reverse=False):
                    return (line['account_id'], line['responsibility_center_id'], line['cash_flow_category'],
                            line['credit'] if reverse else line['debit'], line['debit'] if reverse else line['credit'])
                pairs = [{'line_id': line['id'], 'sequence': line['sequence'],
                    'choices': [(original['id'], f"{parent['reference']} · line {original['sequence']} · "
                        f"{original['account']['code']} · debit {original['debit']} / credit {original['credit']} · {original['memo'] or ''}")
                        for original in parent['lines'] if signature(line) == signature(original, True)]}
                    for line in entry['lines']]
                if any(len(pair['choices']) > 1 for pair in pairs):
                    context['entries'][-1]['pairing_choices'] = pairs
            try:
                context['entries'][-1]['reviewed_predecessor'] = bool(entry['lineage']['exact_mirror']
                    and not entry['lineage']['issue'] and service._approved_head(
                        captured['payload'], entry['reversal_of_id'], entries=all_entries))
                context['entries'][-1]['reviewed_reversal'] = service.reversal_allocations(captured, key)
            except ValidationError as exc:
                context['warnings'].append({'entry_id': key, 'messages': exc.messages})
    # Bind available choices to actual application links, not an arbitrary list
    # of all liability balances. Missing classification is shown, not inferred.
    links = application_links(captured, entry_ids=entry_ids)
    cache = {}
    for link in links['links']:
        source_id = link['source_line_id']
        if source_id not in cache:
            try:
                cache[source_id] = source_components(captured, source_id)
            except ValidationError as exc:
                cache[source_id] = None
                context['warnings'].append({'source_line_id': source_id, 'messages': exc.messages})
        source = cache[source_id]
        if source is not None:
            context['components'].setdefault(str(link['line_id']), []).extend([
                {'source_line_id': source_id, 'attribution_id': source.attribution_id,
                 'component_key': component.key, 'basis': component.basis,
                 'source_reference': all_entries[source.source_entry_id]['reference'],
                 'source_amount': str(component.amount), 'application_share': link['amount']}
                for component in source.components])
    context['unlinked_liability_lines'] = []
    for line in links['unlinked_liability_lines']:
        entry = all_entries[line['entry_id']]
        financial = next(row for row in entry['lines'] if row['id'] == line['line_id'])
        context['unlinked_liability_lines'].append({**line, 'entry_reference': entry['reference'],
            'sequence': financial['sequence'], 'account_code': financial['account']['code']})
    context = service.json_value(context)
    return {'context': context, 'token': signing.dumps(context, salt=SALT, compress=True)}


def read(*, actor, token, for_redisplay=False):
    """Authenticate first; checksum validity alone is never browser authority."""
    owner_id = _owner(actor)
    try:
        context = signing.loads(token, salt=SALT, max_age=None if for_redisplay else MAX_AGE)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValidationError('Preparation expired or changed; reload the source selection.') from exc
    if (not isinstance(context, dict) or context.get('schema') != 1
            or context.get('actor_id') != actor.pk or context.get('owner_id') != owner_id):
        raise PermissionDenied
    return context


def submit(*, actor, token, proposals, reason, evidence_reference):
    """Retain the maker's original versions; never silently rebase a stale POST."""
    context = read(actor=actor, token=token)
    expected = {entry['id']: entry['latest'] for entry in context['entries']}
    if (not isinstance(proposals, list) or len(proposals) != len(expected)
            or any(not isinstance(item, dict) or type(item.get('entry_id')) is not int for item in proposals)
            or {item['entry_id'] for item in proposals} != set(expected)):
        raise ValidationError('Submit every selected journal exactly once.')
    pinned = []
    paired_capture = None
    for item in proposals:
        if (set(item) <= {'entry_id', 'use_reviewed_reversal', 'line_pairs'}
                and item.get('use_reviewed_reversal') is True):
            entry = next(entry for entry in context['entries'] if entry['id'] == item['entry_id'])
            if item.get('line_pairs') is not None and entry.get('reviewed_predecessor'):
                if paired_capture is None:
                    paired_capture = capture(actor=actor, fund_id=context['fund_id'],
                        period_start=date.fromisoformat(context['period_start']),
                        period_end=date.fromisoformat(context['period_end']))
                    if paired_capture['checksum'] != context['source_checksum']:
                        raise ValidationError('Source coverage changed; reload before pairing this reversal.')
                allocations = service.reversal_allocations(paired_capture, entry['id'], pairs=item['line_pairs'])
            elif entry.get('reviewed_reversal'):
                allocations = entry['reviewed_reversal']
            else:
                raise ValidationError('No exact reviewed predecessor allocation was retained for this reversal.')
            item = {'entry_id': item['entry_id'], 'allocations': allocations}
        if set(item) - {'entry_id', 'allocations', 'inherit_from', 'line_pairs'}:
            raise ValidationError('Use the retained preparation versions and source choices.')
        pinned.append({**item, 'expected_latest': expected[item['entry_id']]})
    return service.propose_batch(actor=actor, fund_id=context['fund_id'],
        period_start=date.fromisoformat(context['period_start']),
        period_end=date.fromisoformat(context['period_end']),
        expected_source_checksum=context['source_checksum'],
        expected_centers={int(key): value for key, value in context['centers'].items()},
        proposals=pinned, reason=reason, evidence_reference=evidence_reference)
