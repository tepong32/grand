"""Native dated gross cash evidence; no restrictions, certification or capacity."""
from datetime import date
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from . import budget_cash, budget_native_sources
from .access import department_for_user
from .cash_classifications import checksum
from .models import OpeningBalanceBatch, PostingMapping, LedgerAccount
from .opening_controls import opening_evidence, opening_posting_errors
from . import budget_cash_source_evidence as source_evidence


def mapping_evidence(owner):
    from reporting.models import FinanceStatementMapping
    from reporting.statement_services import statement_mapping_snapshot, snapshot_checksum
    mappings = list(FinanceStatementMapping.objects.filter(department=owner,
        statement_type=FinanceStatementMapping.CASH_FLOW, status=FinanceStatementMapping.ACTIVE))
    if len(mappings) != 1:
        raise ValidationError('Require one independently active cash-account scope.')
    mapping = mappings[0]; payload = statement_mapping_snapshot(mapping)
    events = list(mapping.events.filter(action='activated'))
    if (not mapping.reviewed_at or mapping.reviewed_by_id in (None, mapping.created_by_id, mapping.submitted_by_id)
        or mapping.snapshot_checksum != snapshot_checksum(payload) or len(events) != 1
        or events[0].actor_id != mapping.reviewed_by_id or events[0].snapshot != payload):
        raise ValidationError('Cash scope does not reproduce its independent activation evidence.')
    codes = [code for row in payload['lines'] for code in row['account_codes']]
    if (not codes or len(codes) != len(set(codes)) or any(row['selector_type'] != 'account_codes' for row in payload['lines'])):
        raise ValidationError('Use each explicit cash-account code once, not all asset accounts.')
    accounts = list(LedgerAccount.objects.filter(department_id=owner.pk, code__in=codes).values('id', 'code', 'account_type'))
    if len(accounts) != len(codes) or any(row['account_type'] != 'asset' for row in accounts):
        raise ValidationError('Every selected cash account must be an asset in this Accounting ledger.')
    known = sorted(set(PostingMapping.objects.filter(department_id=owner.pk, category=PostingMapping.BANK,
        is_active=True).values_list('account__code', flat=True)))
    return {'payload': payload, 'checksum': mapping.snapshot_checksum,
        'reviewed_by': mapping.reviewed_by_id, 'reviewed_at': mapping.reviewed_at.isoformat(),
        'activation': source_evidence.event_body(events[0]),
        'events': [source_evidence.event_body(event) for event in mapping.events.order_by('created_at', 'pk')],
        'created_by': mapping.created_by_id, 'submitted_by': mapping.submitted_by_id,
        'accounts': sorted(accounts, key=lambda row: row['id']), 'known_bank_codes': known}


def opening_source(owner, batch_id, fund_id):
    batch = OpeningBalanceBatch.objects.filter(pk=batch_id, department_id=owner.pk,
        status=OpeningBalanceBatch.RECONCILED).select_related('period').first()
    if not batch:
        raise ValidationError('Select an explicit reconciled opening batch from this Accounting ledger.')
    values, digest, errors = opening_evidence(batch)
    errors.extend(opening_posting_errors(batch))
    if (digest != batch.validation_summary.get('evidence_checksum') or
        batch.approved_by_id in (None, batch.created_by_id, batch.submitted_by_id)):
        errors.append('Opening evidence does not reproduce an independent approval.')
    postings = list(batch.postings.filter(fund_id=fund_id).values('entry_id', 'fund_id', 'row_count', 'debit', 'credit'))
    if not batch.is_zero_balance_declaration and len(postings) != 1:
        errors.append('The selected opening source has no exact posting for this fund.')
    if errors:
        raise ValidationError(list(dict.fromkeys(errors)))
    return {'public_id': str(batch.public_id), 'id': batch.pk, 'source': values, 'checksum': digest,
        'baseline_date': batch.period.starts_on.isoformat(), 'zero': batch.is_zero_balance_declaration,
        'period': {'id': batch.period_id, 'department_id': batch.period.department_id,
            'starts_on': batch.period.starts_on.isoformat(), 'ends_on': batch.period.ends_on.isoformat()},
        'postings': [{**row, 'debit': str(row['debit']), 'credit': str(row['credit'])} for row in postings],
        'approved_by': batch.approved_by_id, 'approved_at': batch.approved_at.isoformat() if batch.approved_at else None,
        'created_by': batch.created_by_id, 'submitted_by': batch.submitted_by_id,
        'reconciled_by': batch.reconciled_by_id,
        'events': [source_evidence.event_body(event) for event in batch.events.order_by('created_at', 'pk')],
        'validation': batch.validation_summary}


def project(ledger, mapping, opening, *, balance_date, boundary, entity_key, coverage_authority):
    """Project trusted server evidence; fingerprints alone do not authenticate input."""
    payload = budget_native_sources.verify(ledger)
    source_evidence.validate(mapping, opening)
    if type(balance_date) is not date or balance_date > timezone.localdate() or boundary not in ('start_of_day', 'end_of_day'):
        raise ValidationError('Retain a historical date and explicit start/end boundary.')
    budget_cash.shared.text(entity_key, 'reporting entity', 80)
    budget_cash.shared.text(coverage_authority, 'opening fund/entity coverage authority')
    fund = payload['scope']['fund']
    if (opening['source']['department'] != fund['department_id'] or
        mapping['payload']['department_id'] != fund['department_id']):
        raise ValidationError('Cash mapping, opening and ledger owners must agree.')
    baseline = date.fromisoformat(opening['baseline_date'])
    if baseline > balance_date:
        raise ValidationError('A later opening cannot establish an earlier cash balance.')
    codes = {row['code'] for row in mapping['accounts']}
    known = set(mapping['known_bank_codes'])
    for entry in payload['journals']:
        known.update(line['account']['code'] for line in entry['lines'] if line['cash_flow_category'])
    if known - codes:
        raise ValidationError('The reviewed scope omits bank-mapped or cash-classified accounts: ' + ', '.join(sorted(known - codes)))
    selected, excluded = [], []
    expected_openings = {row['entry_id'] for row in opening['postings']}
    actual_openings = set()
    accounts = {code: Decimal('0.00') for code in sorted(codes)}
    for entry in payload['journals']:
        day = date.fromisoformat(entry['entry_date'])
        if day > balance_date:
            raise ValidationError('The source cohort extends beyond this balance date.')
        is_opening = entry['source_type'] == 'opening' and not entry['reversal_of_id']
        if is_opening:
            actual_openings.add(entry['id'])
            if day != baseline or entry['source_snapshot'].get('opening_batch') != opening['public_id']:
                raise ValidationError('Unexpected or late opening source; reconcile it without double counting.')
        if day < baseline:
            raise ValidationError('The selected baseline does not cover earlier posted ledger activity.')
        if day == balance_date and boundary == 'start_of_day' and not is_opening:
            excluded.append(entry['id']); continue
        if entry['lineage']['issue']:
            raise ValidationError('Resolve retained reversal lineage before using cash evidence.')
        debit = sum((Decimal(line['debit']) for line in entry['lines']), Decimal('0.00'))
        credit = sum((Decimal(line['credit']) for line in entry['lines']), Decimal('0.00'))
        if not entry['lines'] or debit != credit:
            raise ValidationError('Every retained source journal must balance.')
        selected.append(entry['id'])
        for line in entry['lines']:
            code = line['account']['code']
            if code in codes:
                accounts[code] += Decimal(line['debit']) - Decimal(line['credit'])
    if actual_openings != expected_openings:
        raise ValidationError('Cash opening journals do not reproduce the selected batch/fund lineage.')
    source_evidence.validate_opening_lines(payload, opening)
    return {'schema': 2, 'kind': 'native_budget_gross_cash', 'scope': {
        'fund': fund, 'entity_key': entity_key, 'coverage_authority': coverage_authority,
        'balance_date': balance_date.isoformat(), 'boundary': boundary},
        'ledger': ledger, 'mapping': mapping, 'opening': opening,
        'selected_journal_ids': selected, 'boundary_excluded_journal_ids': excluded,
        'account_balances': {code: str(amount) for code, amount in accounts.items()},
        'gross': str(sum(accounts.values(), Decimal('0.00'))),
        'restriction_status': 'not_supplied', 'certification_status': 'not_certified'}


def capture(*, actor, fund_id, opening_batch_id, entity_key, coverage_authority, balance_date, boundary):
    from .budget_cash_preparations import permitted as native_permitted
    if not (any(budget_cash.permitted(actor, action) for action in ('view', 'prepare', 'review', 'export'))
        or any(native_permitted(actor, action) for action in ('view', 'prepare', 'export'))):
        raise PermissionDenied
    owner = department_for_user(actor)
    return _capture_for_owner(owner=owner, fund_id=fund_id, opening_batch_id=opening_batch_id,
        entity_key=entity_key, coverage_authority=coverage_authority, balance_date=balance_date,
        boundary=boundary)


def _capture_for_owner(*, owner, fund_id, opening_batch_id, entity_key, coverage_authority,
                       balance_date, boundary):
    """Internal recapture; callers must authorize the exact retained owner/scope first."""
    mapping = mapping_evidence(owner)
    opening = opening_source(owner, opening_batch_id, fund_id)
    # The financial cohort is one Finance SELECT. Mapping/opening controls are
    # independently retained and rechecked around it; this is not an atomic
    # transaction across stores or a lock against future posting/certification.
    ledger = budget_native_sources._capture(owner_id=owner.pk, fund_id=fund_id,
        period_start=date.min, period_end=balance_date)
    if mapping != mapping_evidence(owner) or opening != opening_source(owner, opening_batch_id, fund_id):
        raise ValidationError('Cash mapping or opening evidence changed during capture; prepare a fresh source cohort.')
    payload = project(ledger, mapping, opening, balance_date=balance_date, boundary=boundary,
        entity_key=entity_key, coverage_authority=coverage_authority)
    return {'payload': payload, 'checksum': checksum(payload), 'source_checksum': source_checksum(payload),
        'captured_at': timezone.now().isoformat()}


def source_checksum(payload):
    # Recapture timestamps are evidence of when a read occurred, not changes to
    # the underlying source cohort. Retain them in the full artifact fingerprint.
    return checksum({'ledger': payload['ledger']['checksum'], 'mapping': payload['mapping'],
        'opening': payload['opening'], 'scope': payload['scope']})


def verify(captured):
    """Reproduce trusted retained sources without querying today's approvals."""
    try:
        payload = captured.get('payload') if isinstance(captured, dict) else None
        if (not isinstance(payload, dict) or payload.get('kind') != 'native_budget_gross_cash'
            or captured.get('checksum') != checksum(payload) or captured.get('source_checksum') != source_checksum(payload)):
            raise ValidationError('Retained native cash evidence no longer reproduces its fingerprint.')
        if payload.get('schema') == 1:
            # Historical internal captures predate full decision retention. Never
            # backfill today's source decisions into those earlier bytes.
            return payload
        if payload.get('schema') != 2:
            raise ValidationError('Unsupported native cash evidence schema.')
        scope = payload['scope']
        reproduced = project(payload['ledger'], payload['mapping'], payload['opening'],
            balance_date=date.fromisoformat(scope['balance_date']), boundary=scope['boundary'],
            entity_key=scope['entity_key'], coverage_authority=scope['coverage_authority'])
        if reproduced != payload:
            raise ValidationError('Retained native cash controls do not reproduce their source projection.')
        return payload
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Retained native cash evidence has an invalid source structure.') from error


def is_current(captured, actor):
    """Compare trusted retained evidence; never authenticate client-supplied hashes."""
    payload = verify(captured); scope = payload['scope']
    current = capture(actor=actor, fund_id=scope['fund']['id'], opening_batch_id=payload['opening']['id'],
        entity_key=scope['entity_key'], coverage_authority=scope['coverage_authority'],
        balance_date=date.fromisoformat(scope['balance_date']), boundary=scope['boundary'])
    return current['source_checksum'] == captured['source_checksum']
