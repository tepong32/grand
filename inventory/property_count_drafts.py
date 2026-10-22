"""Descriptive count snapshots can start a supplied draft; never infer quantities."""
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import can_manage_asset_verification
from .draft_lines import MAX_DRAFT_LINES
from .property_determinations import can_act, value
from .rpcppe_drafts import prepare
from .supply_draft_sources import read_selection, sign_selection, source_digest
from .views import _verification_round_queryset

SALT = 'gso-property-count-rpcppe-draft-v1'


def sources(round, records):
    basis = {name: value(getattr(round, name)) for name in ('pk', 'title', 'as_of_date', 'department_id', 'department_label', 'closed_at')}
    return [{'id': record.pk, 'round': basis,
             'record': {field.attname: value(getattr(record, field.attname)) for field in record._meta.concrete_fields},
             'result_label': record.get_result_display()} for record in records]


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def preparation(request, pk):
    if not can_act(request.user, 'view') or not any(can_manage_asset_verification(request.user, action, read_only=True)
                                                  for action in ('start', 'record', 'close')):
        raise PermissionDenied
    round = get_object_or_404(_verification_round_queryset(request.user), pk=pk)
    rows = round.records.order_by('pk')
    token = request.POST.get('property_source_token', '') if request.method == 'POST' else ''
    selected, initial, error = [], None, ''
    query = request.GET.get('q', '').strip()
    try:
        if request.method == 'POST':
            payload = read_selection(token, request.user, salt=SALT)
            records = list(rows.filter(pk__in=payload['ids']))
            candidate = sources(round, records)
            if len(records) != len(payload['ids']) or source_digest(candidate) != payload['digest']:
                raise ValidationError('The selected count records changed or are unavailable. Your entries are retained; reopen the count to start again.')
            selected = candidate
        else:
            if len(query) > 100:
                raise ValidationError('Use at most 100 characters to find count items or recorded tags.')
            if query:
                rows = rows.filter(Q(asset_name_snapshot__icontains=query) | Q(property_tag_snapshot__icontains=query))
            records = list(rows[:MAX_DRAFT_LINES + 1])
            if not records:
                raise ValidationError('No listed count records match. This does not certify zero property or a completed inventory.')
            if len(records) > MAX_DRAFT_LINES:
                raise ValidationError('More than 50 listed records match. Narrow the item or tag search; no records have been omitted.')
            selected = sources(round, records)
            token = sign_selection(request.user, selected, salt=SALT)
            initial = QueryDict(mutable=True)
            initial.update({'lines-TOTAL_FORMS': str(len(records)), 'lines-INITIAL_FORMS': '0'})
            for index, record in enumerate(records):
                for name, raw in {'article': record.asset_name_snapshot,
                                  'description': f'Recorded serial: {record.serial_number_snapshot}' if record.serial_number_snapshot else '',
                                  'remarks': f'{record.get_result_display()} · Recorded tag: {record.property_tag_snapshot or "Not recorded"}'}.items():
                    initial[f'lines-{index}-{name}'] = raw
    except (signing.BadSignature, KeyError, TypeError):
        error = 'The count selection is missing, expired or invalid. Your entries are retained; reopen the count to start again.'
    except ValidationError as problem:
        error = ' '.join(problem.messages)
    if error:
        selected = []
    return prepare(request, initial_data=initial, source_context={
        'property_sources': selected, 'property_source_token': token, 'source_error': error,
        'source_round': round, 'source_query': query})
