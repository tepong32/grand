"""Retained shared claim proposals and independent, atomic group decisions."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import claim_attributions as history
from .cash_classifications import checksum
from .models import Fund, JournalLine, SharedPayableClaimProposal as Proposal
from .shared_claim_allocations import normalize_shared_allocations


def proposal_payload(record):
    return {"public_id": str(record.public_id), "department": record.department_id,
        "fund": record.fund_id, "sources": record.source_ids, "applications": record.application_ids,
        "source_set_checksum": record.source_set_checksum, "version": record.version,
        "base_approvals": record.base_approvals, "allocations": record.allocations,
        "source_checksum": record.source_checksum, "evidence": record.evidence_reference,
        "reason": record.reason, "proposed_by": record.proposed_by_id}


def _ids(values):
    if (not isinstance(values, list) or not values
            or any(type(pk) is not int or pk <= 0 for pk in values)
            or len(values) != len(set(values))):
        raise ValidationError("Select distinct actual historical journal lines.")
    return sorted(values)


def _snapshot(sources, applications):
    return {str(source.pk): history.serial_snapshot(source, applications) for source in sources}


def verify(record):
    sources = list(JournalLine.objects.filter(pk__in=record.source_ids).order_by("pk"))
    if (len(sources) != len(record.source_ids) or checksum(record.source_ids) != record.source_set_checksum
            or checksum(proposal_payload(record)) != record.proposal_checksum
            or checksum(record.source_snapshot) != record.source_checksum
            or _snapshot(sources, record.application_ids) != record.source_snapshot):
        raise ValidationError("The shared proposal no longer reproduces its retained source evidence.")
    return record


@transaction.atomic(using='finance')
def review(proposal, actor, *, approve, note):
    initial = Proposal.objects.get(pk=proposal.pk)
    seed = JournalLine.objects.get(pk=initial.source_ids[0])
    history._authorize(seed, actor, review=True)
    Fund.objects.select_for_update().get(pk=initial.fund_id)
    locked = {line.pk: line for line in JournalLine.objects.select_for_update().filter(
        pk__in=[*initial.source_ids, *initial.application_ids]).order_by('pk')}
    stored = verify(Proposal.objects.select_for_update().get(pk=initial.pk))
    if (stored.attributions.exists() or actor.pk == stored.proposed_by_id
            or not isinstance(approve, bool) or not note.strip()):
        raise ValidationError('A different authorized reviewer must decide an undecided shared proposal and record the basis.')
    sources = [locked[pk] for pk in stored.source_ids]
    selected = {}
    for source in sources:
        history._authorize(source, actor, review=True)
        selected[source.pk] = history.current(source)
    if approve:
        latest = Proposal.objects.filter(fund_id=stored.fund_id, source_set_checksum=stored.source_set_checksum).aggregate(
            version=Max('version'))['version']
        if latest != stored.version:
            raise ValidationError('Review the latest shared proposal; return this older version.')
        bases = {str(pk): history.attribution_evidence(record) if record else None for pk, record in selected.items()}
        if bases != stored.base_approvals:
            raise ValidationError('An approved attribution changed; prepare a new complete shared proposal.')
        rows = [{'source_id': row['source_id'], 'invoices': row['invoices']} for row in stored.allocations]
        if normalize_shared_allocations(sources, [locked[pk] for pk in stored.application_ids], rows) != stored.allocations:
            raise ValidationError('The shared allocations differ from their retained proposal.')
        from .shared_claim_applications import application_filter
        for source, allocation in zip(sources, stored.allocations):
            old = selected[source.pk]
            if old and old.shared_proposal_id and not set(old.shared_proposal.source_ids).issubset(stored.source_ids):
                raise ValidationError('Revise every member of an existing shared group together.')
            history._normalize(source, [int(pk) for pk in allocation['applications']], '', '',
                split=True, coordinated_sources=stored.source_ids)
            for row in allocation['invoices']:
                history._validate_party(source, row['party_key'])
            used = source.claim_reservations.exists() or JournalLine.objects.filter(application_filter(source.pk)).exists()
            if used and (old is None or not old.is_split or history.allocation_rows(old) != allocation['invoices']):
                raise ValidationError('Retain invoice allocations already used by applications or reservations.')
    records = []
    for source, allocation in zip(sources, stored.allocations):
        applications = sorted(int(pk) for pk in allocation['applications'])
        snapshot = history.serial_snapshot(source, applications)
        version = (source.claim_attributions.aggregate(value=Max('version'))['value'] or 0) + 1
        record = history.Attribution(source=source, shared_proposal=stored,
            department_id=stored.department_id, department_label=stored.department_label,
            version=version, base_version=(stored.base_approvals[str(source.pk)] or {}).get('version', 0),
            applications=applications, application_amounts=allocation['applications'],
            source_snapshot=snapshot, source_checksum=checksum(snapshot),
            allocation_checksum=checksum(allocation['invoices']), evidence_reference=stored.evidence_reference,
            reason=stored.reason, proposed_by_id=stored.proposed_by_id, proposed_by_label=stored.proposed_by_label)
        record.save()
        for row in allocation['invoices']:
            item = history.PayableClaimSlice(attribution=record, **row)
            item._proposal_write = True
            item.save()
        records.append(record)
    decided_at = timezone.now()
    for record in records:
        record.status = history.Attribution.APPROVED if approve else history.Attribution.RETURNED
        record.reviewed_by_id = actor.pk
        record.reviewed_by_label = actor.get_full_name() or actor.username
        record.reviewed_at = decided_at
        record.review_note = note.strip()
        record.approval_checksum = checksum(history.approval_payload(record)) if approve else ''
        record._review_transition = True
        record.save()
    if approve:
        # No reader within the transaction sees a deliberately half-written group.
        # All heads move before verification/capacity; any failure rolls back all.
        for record in records:
            history.Head.objects.update_or_create(source=record.source, defaults={'attribution': record})
        from .claim_splits import validate_capacity
        for record in records:
            history.verify_current(record)
            for row in history.allocation_rows(record):
                if history.claim_identity_exists(stored.department_id, stored.fund_id,
                        row['party_key'], row['claim_reference'], exclude_source=record.source_id):
                    raise ValidationError("This payee's claim reference is already recognized in this fund.")
            validate_capacity(record.source, record)
    return records


def verify_member(record, rows):
    """Read a per-credit allocation only with the complete sealed decision set.

    This validates retained data; it does not create or authorize approvals.
    The standalone review service must never approve one such member alone.
    """
    proposal = verify(record.shared_proposal)
    expected = {row['source_id']: row for row in proposal.allocations}
    members = list(proposal.attributions.select_related('source', 'shared_proposal').order_by('source_id'))
    if (len(members) != len(expected) or {member.source_id for member in members} != set(expected)
            or record.source_id not in expected):
        raise ValidationError("The shared attribution decision is incomplete.")
    decision = (record.reviewed_by_id, record.reviewed_at, record.review_note)
    for member in members:
        allocation = expected[member.source_id]
        invoices = history.allocation_rows(member, fresh=True)
        if (member.status != history.Attribution.APPROVED
                or member.department_id != proposal.department_id or member.source.entry.fund_id != proposal.fund_id
                or member.base_version != ((proposal.base_approvals[str(member.source_id)] or {}).get('version', 0))
                or member.version <= member.base_version
                or member.evidence_reference != proposal.evidence_reference or member.reason != proposal.reason
                or not member.reviewed_by_id or member.reviewed_by_id == proposal.proposed_by_id
                or not member.reviewed_at or not member.review_note.strip()
                or member.proposed_by_id != proposal.proposed_by_id
                or (member.reviewed_by_id, member.reviewed_at, member.review_note) != decision
                or member.application_amounts != allocation['applications']
                or member.applications != sorted((int(pk) for pk in allocation['applications']))
                or invoices != allocation['invoices'] or checksum(invoices) != member.allocation_checksum
                or checksum(history.approval_payload(member, allocations=invoices)) != member.approval_checksum
                or checksum(member.source_snapshot) != member.source_checksum
                or history.serial_snapshot(member.source, member.applications) != member.source_snapshot):
            raise ValidationError("The shared attribution differs from its complete approved schedule.")
    if rows != expected[record.source_id]['invoices'] or record.application_amounts != expected[record.source_id]['applications']:
        raise ValidationError("The credit differs from its shared attribution member.")


@transaction.atomic(using="finance")
def propose(*, actor, source_ids, application_ids, rows, expected_approvals,
        expected_version, evidence_reference, reason):
    source_ids = _ids(source_ids)
    if not isinstance(application_ids, list):
        raise ValidationError("Select actual historical application lines.")
    application_ids = _ids(application_ids) if application_ids else []
    if len(source_ids) < 2 or set(source_ids).intersection(application_ids):
        raise ValidationError("Select several original credits separately from their historical applications.")
    seed = JournalLine.objects.filter(pk=source_ids[0]).first()
    if seed is None:
        raise ValidationError("An original credit cannot be found.")
    history._authorize(seed, actor)
    # Match approval/native-recognition order: fund, then all original lines.
    Fund.objects.select_for_update().get(pk=seed.entry.fund_id)
    locked = {line.pk: line for line in JournalLine.objects.select_for_update().filter(
        pk__in=[*source_ids, *application_ids]).order_by("pk")}
    if len(locked) != len(source_ids) + len(application_ids):
        raise ValidationError("A selected historical journal line cannot be found.")
    sources = [locked[pk] for pk in source_ids]
    applications = [locked[pk] for pk in application_ids]
    allocations = normalize_shared_allocations(sources, applications, rows)
    bases = {}
    for source, row in zip(sources, allocations):
        history._authorize(source, actor)
        approved = history.current(source)
        bases[str(source.pk)] = history.attribution_evidence(approved) if approved else None
        # Only members captured together may propose replacing each other's
        # current ownership. This writes no approval head or financial hold.
        history._normalize(source, [int(pk) for pk in row['applications']], '', '',
            split=True, coordinated_sources=source_ids)
        for invoice in row['invoices']:
            history._validate_party(source, invoice['party_key'])
    versions = {pk: (value['version'] if value else 0) for pk, value in bases.items()}
    if (not isinstance(expected_approvals, dict)
            or any(type(value) is not int or value < 0 for value in expected_approvals.values())
            or expected_approvals != versions):
        raise ValidationError("An approved attribution changed; reload the complete shared schedule.")
    cohort = checksum(source_ids)
    latest = Proposal.objects.filter(fund_id=seed.entry.fund_id, source_set_checksum=cohort).aggregate(
        version=Max("version"))["version"] or 0
    if type(expected_version) is not int or expected_version != latest:
        raise ValidationError("The shared proposal changed; reload its latest version.")
    if not evidence_reference.strip() or not reason.strip():
        raise ValidationError("Record the shared reconciliation schedule and its explanation.")
    snapshot = _snapshot(sources, application_ids)
    record = Proposal(department_id=seed.entry.department_id, department_label=seed.entry.department_label,
        fund_id=seed.entry.fund_id, source_ids=source_ids, application_ids=application_ids,
        source_set_checksum=cohort, version=latest + 1, base_approvals=bases,
        allocations=allocations, source_snapshot=snapshot, source_checksum=checksum(snapshot),
        evidence_reference=evidence_reference.strip(), reason=reason.strip(),
        proposed_by_id=actor.pk, proposed_by_label=actor.get_full_name() or actor.username)
    record.proposal_checksum = checksum(proposal_payload(record))
    record._proposal_write = True
    record.save()
    return record
