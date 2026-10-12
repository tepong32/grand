"""Detached receipt partition proposals, never review, certification or posting."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from . import budget_receipt_sources as sources
from .cash_classifications import checksum
from .models import JournalEntry


EXCLUSIONS = {'transfer', 'settlement', 'advance', 'refund', 'counterpart',
    'opening', 'closing', 'direct_equity', 'other_exclusion'}
FIELDS = {'line_id', 'amount', 'disposition', 'purpose', 'category', 'basis'}


def amount(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0 or result != result.quantize(Decimal('0.01')):
            raise ValueError
        return result.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValidationError('Use a positive finite component amount with exact cents.') from error


def entry_source(inventory, entry_id):
    payload = sources.verify(inventory)
    if type(entry_id) is not int:
        raise ValidationError('Select an exact captured journal identity.')
    matches = [row for row in payload['ledger']['payload']['journals'] if row['id'] == entry_id]
    if len(matches) != 1:
        raise ValidationError('Select a journal in the retained Fund history.')
    entry = matches[0]
    # Earlier originals are dependencies, never extra reporting-period activity.
    # Validate their posting/source rows at the same boundary as period journals.
    from datetime import date
    day = date.fromisoformat(entry['entry_date'])
    projected = sources.project(payload['ledger'], payload['mapping'],
        period_start=day, period_end=date.fromisoformat(payload['scope']['period_end']))
    proof = next(row['collection'] for row in projected['journals'] if row['entry_id'] == entry_id)
    return payload, entry, proof


def _normalize(payload, entry, proof, rows, *, inherited=False):
    if not isinstance(rows, list) or not rows:
        raise ValidationError('Partition every financial line, including excluded and unresolved amounts.')
    lines = {row['id']: row for row in entry['lines']}
    cash_ids = {row['id'] for row in payload['mapping']['accounts']}
    totals = {key: Decimal('0.00') for key in lines}
    normalized = []
    for supplied in rows:
        if (not isinstance(supplied, dict) or set(supplied) != FIELDS
            or type(supplied['line_id']) is not int or supplied['line_id'] not in lines):
            raise ValidationError('Use exact source line, amount, disposition, purpose, category and basis fields.')
        row = lines[supplied['line_id']]
        value = amount(supplied['amount'])
        disposition, purpose, category, basis = (supplied[key] for key in ('disposition', 'purpose', 'category', 'basis'))
        if not all(isinstance(item, str) for item in (disposition, purpose, category, basis)) or not basis.strip() or len(basis) > 1000:
            raise ValidationError('Retain explicit text choices and a supporting basis up to 1,000 characters.')
        if entry['lineage']['issue'] and disposition != 'unresolved':
            raise ValidationError('Keep invalid source lineage unresolved.')
        if entry['reversal_of_id'] and disposition != 'unresolved' and not inherited:
            raise ValidationError('An exact reversal must inherit its complete predecessor partition.')
        if disposition != 'unresolved' and proof and (proof['advance_refund'] or proof['original_cheque'] or proof['redemption']):
            raise ValidationError('Retain cheque-return, redemption and advance-refund components unresolved until linked treatment is established.')
        cash = row['account_id'] in cash_ids
        if disposition == 'include':
            if not cash or purpose != 'receipt' or category not in payload['receipt_categories']:
                raise ValidationError('Include only an explicitly classified cash component and receipt leaf category.')
            if not inherited and Decimal(row['debit']) <= 0:
                raise ValidationError('A cash credit needs exact linked receipt treatment; it is not a new receipt.')
            if entry['lineage']['origin_source_type'] in {'opening', 'closing', 'deposit', *JournalEntry.DIRECT_EQUITY_SOURCES}:
                raise ValidationError('Opening, closing, equity and deposits cannot become period receipts.')
        elif disposition == 'exclude':
            if purpose not in EXCLUSIONS or category:
                raise ValidationError('Choose an explicit exclusion purpose without a receipt category.')
        elif disposition != 'unresolved' or purpose != 'unresolved' or category:
            raise ValidationError('Use include, exclude or unresolved without guessing missing receipt meaning.')
        totals[row['id']] += value
        normalized.append({'line_id': row['id'], 'account_id': row['account_id'], 'amount': str(value),
            'signed_amount': str(value if Decimal(row['debit']) > 0 else -value),
            'disposition': disposition, 'purpose': purpose, 'category': category, 'basis': basis.strip()})
    if any(totals[key] != Decimal(row['debit']) + Decimal(row['credit']) for key, row in lines.items()):
        raise ValidationError('Component amounts must cover each financial line exactly once in total.')
    return normalized


def _artifact(payload, entry, rows, dependency=None, pairs=None):
    included = [row for row in rows if row['disposition'] == 'include']
    unresolved = sum((Decimal(row['amount']) for row in rows if row['disposition'] == 'unresolved'), Decimal('0.00'))
    body = {'schema': 2, 'kind': 'native_budget_receipt_partition_proposal',
        'fund': payload['scope']['fund'], 'entry_id': entry['id'], 'entry_date': entry['entry_date'],
        'source_checksum': checksum({key: value for key, value in entry.items() if key != 'attribution'}),
        'mapping_checksum': checksum(payload['mapping']),
        'receipt_categories': payload['receipt_categories'], 'allocations': rows,
        'dependency': dependency, 'line_pairs': pairs,
        'controls': {'classified_receipts': str(sum((Decimal(row['signed_amount']) for row in included), Decimal('0.00'))),
            'unresolved_amount': str(unresolved)},
        'receipt_total': None, 'review_status': 'not_reviewed', 'certification_status': 'not_certified'}
    return {'payload': deepcopy(body), 'checksum': checksum(body)}


def propose(inventory, entry_id, rows):
    payload, entry, proof = entry_source(inventory, entry_id)
    return _artifact(payload, entry, _normalize(payload, entry, proof, rows))


def _input_rows(partition):
    return [{key: row[key] for key in FIELDS} for row in partition['payload']['allocations']]


def verify(inventory, partition):
    try:
        body = partition['payload']
        if body.get('schema') not in (1, 2):
            raise ValidationError('Use a supported retained receipt partition schema.')
        if checksum(body) != partition['checksum']:
            raise ValidationError('Receipt partition proposal checksum changed.')
        if body['dependency'] is None:
            expected = propose(inventory, body['entry_id'], _input_rows(partition))
        else:
            expected = inherit(inventory, body['entry_id'], body['dependency'], pairs=body['line_pairs'])
        if body['schema'] == 1:
            # Reproduce the historical broader fingerprint; never silently
            # upgrade an independently retained proposal or its dependencies.
            _, entry, _ = entry_source(inventory, body['entry_id'])
            expected['payload'].update(schema=1, source_checksum=checksum(entry))
            expected['checksum'] = checksum(expected['payload'])
        if expected != partition:
            raise ValidationError('Receipt partition proposal no longer reproduces its source and components.')
        return body
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        raise ValidationError('Invalid retained receipt partition proposal.') from error


def inherit(inventory, entry_id, parent, *, pairs):
    try:
        return _inherit(inventory, entry_id, parent, pairs=pairs)
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        raise ValidationError('Invalid retained reversal partition dependency.') from error


def _inherit(inventory, entry_id, parent, *, pairs):
    payload, entry, proof = entry_source(inventory, entry_id)
    if not entry['reversal_of_id'] or not entry['lineage']['exact_mirror'] or entry['lineage']['issue']:
        raise ValidationError('Use an exact financial reversal with complete retained lineage.')
    if parent['payload']['entry_id'] != entry['reversal_of_id']:
        raise ValidationError('Select the immediate original partition for this reversal.')
    previous = verify(inventory, parent)
    _, original, _ = entry_source(inventory, entry['reversal_of_id'])
    children = {row['id']: row for row in entry['lines']}
    originals = {row['id']: row for row in original['lines']}
    if (not isinstance(pairs, dict) or any(type(k) is not str or not k.isdecimal() or str(int(k)) != k for k in pairs)
        or any(type(v) is not int for v in pairs.values())
        or {int(key) for key in pairs} != set(children) or set(pairs.values()) != set(originals)
        or len(pairs) != len(originals)):
        raise ValidationError('Pair every reversal line with a distinct exact original line.')
    rows = []
    for child_id, child in children.items():
        original_id = pairs[str(child_id)]
        before = originals[original_id]
        if any(child[key] != before[key] for key in ('account_id', 'responsibility_center_id', 'cash_flow_category')) or (
            child['debit'], child['credit']) != (before['credit'], before['debit']):
            raise ValidationError('Pair only exact mirrored financial source lines.')
        for allocation in previous['allocations']:
            if allocation['line_id'] == original_id:
                rows.append({**{key: allocation[key] for key in FIELDS}, 'line_id': child_id})
    return _artifact(payload, entry, _normalize(payload, entry, proof, rows, inherited=True), parent, pairs)
