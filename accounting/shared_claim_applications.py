"""Exact multi-credit reversal evidence on the existing financial journal line."""
from copy import copy, deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import JournalEntry, JournalLine
from . import claim_attributions as history

ZERO = Decimal('0.00')


def is_shared(line):
    return isinstance(line.payable_allocation, dict) and 'sources' in line.payable_allocation


def application_filter(source_id):
    # Both supported databases implement JSON has_key. Approval records retain
    # protected relational references to every original credit in this envelope.
    return Q(payable_origin_id=source_id) | Q(payable_allocation__sources__has_key=str(source_id))


def native_lines(source, *, exclude_entries=()):
    lines = JournalLine.objects.filter(application_filter(source.pk), entry__status=JournalEntry.POSTED)
    if exclude_entries:
        lines = lines.exclude(entry_id__in=exclude_entries)
    return [project(line, source) for line in lines.select_related('entry')]


def capture(line):
    """Return a complete envelope only for an actual multi-source application."""
    if is_shared(line):
        validate(line)
        return deepcopy(line.payable_allocation)
    if line.payable_origin_id:
        return None
    records = [history.verify_current(head.attribution) for head in history.Head.objects.filter(
        source__entry__department_id=line.entry.department_id).select_related('attribution__source')
        if line.pk in head.attribution.applications]
    if len(records) < 2:
        return None
    group = records[0].shared_proposal_id
    if not group or any(record.shared_proposal_id != group for record in records):
        raise ValidationError('The application has conflicting shared claim ownership.')
    from .claim_splits import effective_shares
    sources = {str(record.source_id): {'attribution': history.attribution_evidence(record),
        'shares': effective_shares(line, record.source, record)} for record in sorted(records, key=lambda r: r.source_id)}
    if sum((Decimal(value) for row in sources.values() for value in row['shares'].values()), ZERO) != (line.debit or line.credit):
        raise ValidationError('All shared claim allocations must equal the original financial line.')
    return {'sources': sources}


def validate(line):
    """Verify a retained envelope and its exact posted predecessor, not a new payment."""
    original = getattr(line, '_shared_original', line)
    evidence = original.payable_allocation
    if (not isinstance(evidence, dict) or set(evidence) != {'sources'}
            or not isinstance(evidence['sources'], dict) or len(evidence['sources']) < 2
            or original.payable_origin_id or original.payable_reservation_id
            or original.payable_party_key or original.payable_claim_reference):
        raise ValidationError('Retain every source of the shared reversal without a single-claim override.')
    result = {}
    group = None
    retained_group = None
    from .claim_splits import retained_allocation
    for key, member in evidence['sources'].items():
        if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key:
            raise ValidationError('Select actual original credits for the shared reversal.')
        try:
            source = JournalLine.objects.get(pk=int(key))
        except JournalLine.DoesNotExist:
            raise ValidationError('A shared reversal original credit is missing.')
        record = history.current(source)
        if (record is None or not record.shared_proposal_id
                or (group is not None and record.shared_proposal_id != group)
                or source.entry.department_id != original.entry.department_id
                or source.entry.fund_id != original.entry.fund_id or source.account_id != original.account_id
                or original.entry.entry_date < source.entry.entry_date):
            raise ValidationError('The shared reversal must retain its complete approved source group and ledger.')
        group = record.shared_proposal_id
        # Reuse the single-credit retained identity verifier on a per-credit copy.
        if not isinstance(member, dict) or not isinstance(member.get('shares'), dict):
            raise ValidationError('Retain the shared reversal invoice shares.')
        from .claim_splits import _shares
        shares = _shares(record, member['shares'])
        amount = sum((Decimal(value) for value in shares.values()), ZERO)
        item = copy(original)
        item.payable_origin = source
        item.payable_allocation = member
        item.debit, item.credit = (amount, ZERO) if original.debit else (ZERO, amount)
        # The real line's independent audit is checked below, not this projection.
        shares = retained_allocation(item, source, record, check_posting=False)
        retained = history.Attribution.objects.get(source=source, public_id=member['attribution']['public_id'])
        if (not retained.shared_proposal_id
                or (retained_group is not None and retained.shared_proposal_id != retained_group)):
            raise ValidationError('Retain one complete shared decision for the original application.')
        retained_group = retained.shared_proposal_id
        result[source.pk] = (source, record, shares, amount)
    if sum((row[3] for row in result.values()), ZERO) != (original.debit or original.credit):
        raise ValidationError('Shared allocations must equal the whole financial line exactly.')
    prior = (original.entry.reversal_of.lines.filter(sequence=original.sequence).first()
        if original.entry.reversal_of_id else None)
    prior_evidence = capture(prior) if prior is not None else None
    # A historical predecessor has no stored application envelope. Its current
    # compatible approval may be newer; retain the pinned original decision
    # above and compare the actual source/invoice shares. Native predecessors
    # must preserve their entire original envelope byte-for-byte as JSON data.
    same_allocation = prior_evidence == evidence
    if prior is not None and prior_evidence and not is_shared(prior):
        same_allocation = ({key: row['shares'] for key, row in prior_evidence['sources'].items()}
            == {key: row['shares'] for key, row in evidence['sources'].items()})
    if (prior is None or prior.entry.status != JournalEntry.POSTED
            or prior.account_id != original.account_id or prior.debit != original.credit
            or prior.credit != original.debit or prior.responsibility_center_id != original.responsibility_center_id
            or original.entry.entry_date < prior.entry.entry_date or not same_allocation):
        raise ValidationError('A shared application requires the exact original financial reversal and all its shares.')
    if original.entry.status == JournalEntry.POSTED:
        from .claim_splits import posting_evidence
        events = list(original.entry.audit_events.filter(action='posted'))
        if (len(events) != 1 or events[0].actor_id != original.entry.posted_by_id
                or events[0].snapshot.get('invoice_allocations', {}).get(str(original.pk)) != posting_evidence(original)):
            raise ValidationError('The shared reversal differs from its independent posting evidence.')
    return result


def project(line, source):
    if not is_shared(line):
        return line
    original = getattr(line, '_shared_original', line)
    members = validate(original)
    if source.pk not in members:
        raise ValidationError('The original credit is absent from this shared application.')
    amount = members[source.pk][3]
    item = copy(original)
    item._shared_original = original
    item.debit, item.credit = (amount, ZERO) if original.debit else (ZERO, amount)
    return item
