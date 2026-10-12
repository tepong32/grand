"""Complete unresolved receipt evidence; cash movement is never a receipt category."""
from datetime import date
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from . import budget_native_sources, budget_native_cash, budget_cash_source_evidence, summary_actuals
from .access import department_for_user
from .cash_classifications import checksum


def collection_evidence(entry):
    """Verify the approved source body against every immutable financial line."""
    snapshot = entry['source_snapshot']
    body = snapshot.get('collection_payload')
    if body is None:
        if entry['source_type'] in ('collection', 'deposit', 'collection_fix', 'cheque_return'):
            raise ValidationError('A collection journal is missing its retained approved source.')
        return None
    expected = {'collection': 'receipt', 'deposit': 'deposit',
        'collection_fix': 'correction', 'cheque_return': 'cheque_return'}
    proposal = body['proposal']
    rows = [{'account_id': row['account_id'], 'account_code': row['account']['code'],
        'debit': row['debit'], 'credit': row['credit'], 'cash_flow_category': row['cash_flow_category']}
        for row in entry['lines']]
    if (snapshot.get('payload_checksum') != checksum(body)
        or snapshot.get('collection_source') != body['collection_source']
        or body['source_kind'] != expected.get(entry['source_type'])
        or body['proposal_checksum'] != checksum(proposal)
        or rows != proposal['financial_rows']
        or not body['reviewed_by'] or body['reviewed_by'] == body['prepared_by']):
        raise ValidationError('Receipt inventory source does not reproduce its approved collection rows.')
    return {'source': body['collection_source'], 'kind': body['source_kind'],
        'source_date': body['source_date'], 'source_amount': body['amount'],
        'approved_payload_checksum': snapshot['payload_checksum'],
        # These are retained facts requiring reviewed treatment, not automatic
        # include/exclude/category choices or live clearing assertions.
        'advance_refund': proposal.get('advance_refund'),
        'original_cheque': proposal.get('original_cheque'),
        'redemption': proposal.get('redemption'),
        'cheque': proposal.get('cheque'),
        'payment_method': proposal.get('payment_method'),
        'charges': proposal.get('charges'),
        'deposit_allocations': proposal.get('allocations'),
        'correction_original_entry': proposal.get('original_entry')}


def project(ledger, mapping, *, period_start, period_end):
    try:
        return _project(ledger, mapping, period_start=period_start, period_end=period_end)
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid receipt inventory source structure.') from error


def _project(ledger, mapping, *, period_start, period_end):
    data = budget_native_sources.verify(ledger)
    budget_cash_source_evidence.validate_mapping(mapping)
    if (type(period_start) is not date or type(period_end) is not date
        or period_start > period_end or data['scope']['period_start'] != date.min.isoformat()
        or mapping['payload']['department_id'] != data['scope']['fund']['department_id']
        or data['scope']['period_end'] != period_end.isoformat()):
        raise ValidationError('Retain the full source history through the selected receipt period.')
    codes = {row['code'] for row in mapping['accounts']}
    ids = {row['id'] for row in mapping['accounts']}
    accounts = {row['id']: row for row in mapping['accounts']}
    known = set(mapping['known_bank_codes'])
    for entry in data['journals']:
        known.update(row['account']['code'] for row in entry['lines'] if row['cash_flow_category'])
    if known - codes:
        raise ValidationError('Receipt inventory cash scope omits bank-mapped or cash-classified accounts.')
    entries, lines, seen_entries, seen_lines = [], [], set(), set()
    cash_debit, cash_credit = Decimal('0.00'), Decimal('0.00')
    for entry in data['journals']:
        if (entry['id'] in seen_entries or entry['department_id'] != data['scope']['fund']['department_id']
            or date.fromisoformat(entry['entry_date']) > period_end):
            raise ValidationError('Retain each journal once in its exact source-owner/history scope.')
        seen_entries.add(entry['id'])
        if not period_start <= date.fromisoformat(entry['entry_date']) <= period_end:
            continue
        debit = sum((Decimal(row['debit']) for row in entry['lines']), Decimal('0.00'))
        credit = sum((Decimal(row['credit']) for row in entry['lines']), Decimal('0.00'))
        events = entry['posting_evidence']
        if (not entry['lines'] or debit != credit or len(events) != 1
            or not entry['posted_by_id'] or events[0]['actor_id'] != entry['posted_by_id']
            or Decimal(events[0]['snapshot']['debit']) != debit
            or Decimal(events[0]['snapshot']['credit']) != credit):
            raise ValidationError('Receipt inventory needs balanced retained posting evidence.')
        proof = collection_evidence(entry)
        entries.append({'entry_id': entry['id'], 'public_id': entry['public_id'],
            'reference': entry['reference'], 'date': entry['entry_date'],
            'source_type': entry['source_type'], 'source_reference': entry['source_reference'],
            'lineage': entry['lineage'], 'collection': proof})
        for row in entry['lines']:
            if row['id'] in seen_lines:
                raise ValidationError('Retain each financial source line exactly once.')
            seen_lines.add(row['id'])
            d, c = Decimal(row['debit']), Decimal(row['credit'])
            if (d < 0 or c < 0 or (d > 0) == (c > 0) or not d.is_finite() or not c.is_finite()):
                raise ValidationError('Retain valid one-sided financial source lines.')
            is_cash = row['account_id'] in ids
            if (row['account']['code'] in codes) != is_cash or (is_cash and
                (row['account']['code'] != accounts[row['account_id']]['code'] or row['account']['account_type'] != 'asset')):
                raise ValidationError('Receipt inventory account identities do not reproduce the reviewed cash scope.')
            if is_cash:
                cash_debit += d; cash_credit += c
            lines.append({'entry_id': entry['id'], 'line_id': row['id'], 'account': row['account'],
                'debit': row['debit'], 'credit': row['credit'], 'cash_account': is_cash,
                'cash_flow_purpose': row['cash_flow_category'], 'classification_status': 'unresolved'})
    return {'schema': 1, 'kind': 'native_budget_receipt_source_inventory',
        'scope': {'fund': data['scope']['fund'], 'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat()}, 'ledger': ledger, 'mapping': mapping,
        'journals': entries, 'lines': lines,
        'controls': {'journals': len(entries), 'lines': len(lines),
            'cash_debit': str(cash_debit), 'cash_credit': str(cash_credit),
            'cash_movement': str(cash_debit-cash_credit), 'unresolved_lines': len(lines)},
        'receipt_total': None, 'receipt_categories': dict(summary_actuals.RECEIPTS),
        'classification_status': 'unresolved', 'certification_status': 'not_certified'}


def source_checksum(payload):
    return checksum({'ledger': payload['ledger']['checksum'], 'mapping': payload['mapping'],
        'scope': payload['scope']})


def capture(*, actor, fund_id, period_start, period_end):
    if not any(summary_actuals.permitted(actor, action) for action in ('view', 'prepare', 'review', 'export')):
        raise PermissionDenied
    owner = department_for_user(actor)
    return _capture_for_owner(owner, fund_id=fund_id, period_start=period_start, period_end=period_end)


def _capture_for_owner(owner, *, fund_id, period_start, period_end):
    """Internal only: callers establish permission and exact Accounting ownership."""
    if type(period_start) is not date or type(period_end) is not date or period_start > period_end:
        raise ValidationError('Select an explicit receipt source period.')
    mapping = budget_native_cash.mapping_evidence(owner)
    ledger = budget_native_sources._capture(owner.pk, fund_id, date.min, period_end)
    if mapping != budget_native_cash.mapping_evidence(owner):
        raise ValidationError('Cash scope changed during receipt capture; retain a fresh cohort.')
    payload = project(ledger, mapping, period_start=period_start, period_end=period_end)
    return {'payload': payload, 'checksum': checksum(payload), 'source_checksum': source_checksum(payload),
        'captured_at': timezone.now().isoformat()}


def verify(captured):
    try:
        payload = captured['payload']; scope = payload['scope']
        if (captured['checksum'] != checksum(payload) or captured['source_checksum'] != source_checksum(payload)
            or payload != project(payload['ledger'], payload['mapping'],
                period_start=date.fromisoformat(scope['period_start']), period_end=date.fromisoformat(scope['period_end']))):
            raise ValidationError('Receipt source inventory no longer reproduces its retained evidence.')
        return payload
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid retained receipt source evidence.') from error


def is_current(captured, actor):
    payload = verify(captured); scope = payload['scope']
    current = capture(actor=actor, fund_id=scope['fund']['id'],
        period_start=date.fromisoformat(scope['period_start']), period_end=date.fromisoformat(scope['period_end']))
    return current['source_checksum'] == captured['source_checksum']
