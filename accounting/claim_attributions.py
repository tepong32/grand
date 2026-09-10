"""Reviewed historical claim links. Original financial lines remain immutable."""
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .access import can_prepare_journals, can_post_journals, department_for_user
from .cash_classifications import checksum, journal_snapshot
from .models import (Fund, JournalEntry, JournalLine, JournalSubsidiaryLine,
    PayableClaimAttribution as Attribution, PayableClaimAttributionHead as Head, PayableClaimSlice)

_CURRENT = object()


def source_snapshot(source, application_ids):
    lines = list(JournalLine.objects.filter(pk__in=[source.pk, *application_ids]).select_related("entry__fund"))
    entries = {line.entry_id: line.entry for line in lines}
    payload = {"source_line": source.pk, "application_lines": sorted(application_ids),
        "claim_fields": list(JournalLine.objects.filter(pk__in=[line.pk for line in lines]).order_by("pk").values(
            "pk", "payable_origin_id", "payable_reservation_id", "payable_party_key", "payable_claim_reference")),
        "journals": [journal_snapshot(entries[key]) for key in sorted(entries)],
        "subsidiaries": list(JournalSubsidiaryLine.objects.filter(journal_line__in=lines).order_by("pk").values(
            "pk", "journal_line_id", "category", "reference_key", "reference_label", "source_code",
            "source_reference", "source_snapshot", "debit", "credit"))}
    allocations = [{"line": line.pk, "allocation": line.payable_allocation} for line in sorted(lines, key=lambda line: line.pk)
        if line.payable_allocation]
    if allocations:
        payload["invoice_allocations"] = allocations
    return payload


def serial_snapshot(source, application_ids):
    # JSON stores exact decimal strings, never backend-specific Decimal values.
    import json
    return json.loads(json.dumps(source_snapshot(source, application_ids), default=str))


def allocation_rows(record, *, fresh=False):
    if not fresh and hasattr(record, "_verified_allocations"):
        return record._verified_allocations
    return [{"key": str(row.key), "party_key": row.party_key, "claim_reference": row.claim_reference,
        "recognized": str(row.recognized), "applications": row.applications}
        for row in record.invoice_slices.order_by("key")]


def approval_payload(record, *, allocations=None):
    payload = {"public_id": str(record.public_id), "source": record.source_id, "version": record.version,
        "base_version": record.base_version, "party": record.party_key, "claim": record.claim_reference,
        "applications": record.applications, "source_checksum": record.source_checksum,
        "evidence": record.evidence_reference, "reason": record.reason, "proposed_by": record.proposed_by_id,
        "reviewed_by": record.reviewed_by_id, "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "review_note": record.review_note}
    # Preserve the byte-equivalent payload for every earlier whole-line approval.
    if record.is_split:
        payload.update(allocation_checksum=record.allocation_checksum,
            allocations=allocation_rows(record) if allocations is None else allocations)
    if record.shared_proposal_id:
        payload.update(shared_proposal=str(record.shared_proposal.public_id),
            shared_proposal_checksum=record.shared_proposal.proposal_checksum,
            application_amounts=record.application_amounts)
    return payload


def verify(record):
    rows = allocation_rows(record, fresh=True)
    if (record.is_split and (record.party_key or record.claim_reference or len(rows) < (1 if record.shared_proposal_id else 2)
            or checksum(rows) != record.allocation_checksum)) or (not record.is_split and rows):
        raise ValidationError("Historical invoice allocations differ from their retained proposal.")
    if (record.status != Attribution.APPROVED or not record.reviewed_by_id or not record.reviewed_at
            or record.reviewed_by_id == record.proposed_by_id
            or checksum(approval_payload(record, allocations=rows)) != record.approval_checksum
            or checksum(record.source_snapshot) != record.source_checksum
            or serial_snapshot(record.source, record.applications) != record.source_snapshot):
        raise ValidationError("Historical claim evidence no longer reproduces its approved source and decision.")
    record._verified_allocations = rows
    if record.shared_proposal_id:
        from .shared_claim_proposals import verify_member
        verify_member(record, rows)
    return record


def current(source):
    head = Head.objects.select_related("attribution__source").filter(source_id=source.pk).first()
    return verify_current(head.attribution) if head else None


def verify_current(record):
    verify(record)
    if record.shared_proposal_id:
        heads = dict(Head.objects.filter(source_id__in=record.shared_proposal.source_ids).values_list(
            'source_id', 'attribution__shared_proposal_id'))
        if (set(heads) != set(record.shared_proposal.source_ids)
                or any(value != record.shared_proposal_id for value in heads.values())):
            raise ValidationError("The current shared attribution is incomplete or has changed. Reload the complete schedule.")
    return record


def attribution_evidence(record):
    return {"public_id": str(record.public_id), "version": record.version,
        "approval_checksum": record.approval_checksum, "source_checksum": record.source_checksum}


def verify_retained_evidence(source, evidence, *, invoice_key=None):
    if not isinstance(evidence, dict):
        raise ValidationError("The retained historical attribution is invalid.")
    record = Attribution.objects.filter(public_id=evidence.get("public_id"), source_id=source.pk).first()
    if record is None or attribution_evidence(verify(record)) != evidence:
        raise ValidationError("The retained historical attribution differs from its original approved decision.")
    if invoice_key:
        selected = current(source)
        invoice_row(record, invoice_key)
        if selected is None or not selected.is_split or allocation_rows(selected) != allocation_rows(record):
            raise ValidationError("The retained invoice allocation differs from its original approved decision.")
    elif record.is_split or identity(source) != (record.party_key, record.claim_reference):
        raise ValidationError("The retained historical attribution differs from its original approved decision.")


def invoice_row(record, key):
    rows = [row for row in allocation_rows(record) if row["key"] == str(key)] if record and record.is_split else []
    if len(rows) != 1:
        raise ValidationError("Select an invoice from the current approved consolidated credit.")
    return rows[0]


def identity(source, *, record=_CURRENT, invoice_key=None):
    if invoice_key:
        row = invoice_row(current(source) if record is _CURRENT else record, invoice_key)
        return row["party_key"], row["claim_reference"]
    if source.payable_claim_reference and source.payable_party_key:
        return source.payable_party_key, source.payable_claim_reference
    if record is _CURRENT:
        record = current(source)
    return (record.party_key, record.claim_reference) if record else ("", "")


def eligible_claims(department_id, party_key=None):
    historical = Head.objects.filter(source__entry__department_id=department_id, attribution__allocation_checksum="")
    named = Q(payable_claim_reference__gt="", payable_party_key__gt="")
    if party_key is not None:
        historical = historical.filter(attribution__party_key=party_key)
        named &= Q(payable_party_key=party_key)
    return JournalLine.objects.filter(entry__department_id=department_id, entry__status=JournalEntry.POSTED,
        payable_origin__isnull=True, credit__gt=0).filter(named | Q(pk__in=historical.values("source_id")))


def application_lines(source, *, record=_CURRENT):
    if record is _CURRENT:
        record = current(source)
    lines = list(JournalLine.objects.filter(pk__in=record.applications).select_related("entry")) if record else []
    if record and record.shared_proposal_id:
        from copy import copy
        projected = []
        for original in lines:
            amount = Decimal(record.application_amounts[str(original.pk)])
            line = copy(original)
            line.debit, line.credit = (amount, Decimal("0")) if original.debit else (Decimal("0"), amount)
            projected.append(line)
        return projected
    return lines


def application_origin(line):
    if line.payable_origin_id:
        return line.payable_origin
    origins = []
    for head in Head.objects.filter(source__entry__department_id=line.entry.department_id).select_related("attribution__source"):
        if line.pk in head.attribution.applications:
            origins.append(verify_current(head.attribution).source)
    if len(origins) > 1:
        raise ValidationError("This application requires its complete shared-source allocation.")
    return origins[0] if origins else None


def reversal_origin(line):
    origin = application_origin(line)
    record = current(origin or line)
    if record and record.is_split:
        return origin or line
    return origin or (line if identity(line)[1] else None)


def _authorize(source, actor, review=False):
    allowed = can_post_journals(actor) if review else can_prepare_journals(actor)
    department = department_for_user(actor)
    if not allowed or department is None or source.entry.department_id != department.pk:
        raise PermissionDenied


def _exact_reversal(child, parent):
    fields = ("sequence", "account_id", "debit", "credit", "responsibility_center_id")
    expected = [(sequence, account, credit, debit, center)
        for sequence, account, debit, credit, center in parent.lines.order_by("sequence").values_list(*fields)]
    return (child.reversal_of_id == parent.pk and parent.status == JournalEntry.POSTED
        and child.department_id == parent.department_id and child.fund_id == parent.fund_id
        and child.entry_date >= parent.entry_date
        and list(child.lines.order_by("sequence").values_list(*fields)) == expected)


def _validate_party(source, party):
    if party.startswith("finance-party:"):
        from finance.models import FinanceParty
        if not FinanceParty.objects.filter(department_id=source.entry.department_id,
                code=party.removeprefix("finance-party:"), status__in=("approved", "scheduled", "active", "superseded")).exists():
            raise ValidationError("Select a governed payee from this Accounting office's Finance Setup.")


def claim_identity_exists(department_id, fund_id, party, claim, *, exclude_source=None, exclude_entry=None):
    native = JournalLine.objects.filter(entry__department_id=department_id,
        entry__fund_id=fund_id, entry__status=JournalEntry.POSTED,
        payable_party_key__iexact=party, payable_claim_reference__iexact=claim)
    historical = Head.objects.filter(source__entry__department_id=department_id,
        source__entry__fund_id=fund_id, attribution__party_key__iexact=party,
        attribution__claim_reference__iexact=claim)
    split = PayableClaimSlice.objects.filter(attribution__current_head__isnull=False,
        attribution__source__entry__department_id=department_id, attribution__source__entry__fund_id=fund_id,
        party_key__iexact=party, claim_reference__iexact=claim)
    if exclude_source is not None:
        native = native.exclude(pk=exclude_source)
        historical = historical.exclude(source_id=exclude_source)
        split = split.exclude(attribution__source_id=exclude_source)
    if exclude_entry is not None:
        native = native.exclude(entry_id=exclude_entry)
        historical = historical.exclude(source__entry_id=exclude_entry)
        split = split.exclude(attribution__source__entry_id=exclude_entry)
    return native.exists() or historical.exists() or split.exists()


def _normalize(source, application_ids, party, claim, *, split=False, coordinated_sources=()):
    if (source.entry.status != JournalEntry.POSTED or not source.entry.posted_by_id
            or source.payable_origin_id or source.payable_allocation or source.credit <= 0 or source.debit
            or source.account.account_type != "liability" or source.entry.reversal_of_id
            or source.entry.source_type in {"voucher", "remittance"}):
        raise ValidationError("Select an original posted liability credit outside an active generated payment workflow.")
    if split and (source.payable_claim_reference or source.payable_party_key):
        raise ValidationError("Preserve the original journal's recorded claim identity; do not split a named claim.")
    if not split and (not party.strip() or party != party.strip() or not claim.strip() or claim != claim.strip()):
        raise ValidationError("Record the exact payee key and claim reference without surrounding spaces.")
    if source.payable_claim_reference and (source.payable_party_key, source.payable_claim_reference) != (party, claim):
        raise ValidationError("Preserve the original journal's recorded claim identity.")
    _validate_party(source, party)
    if not isinstance(application_ids, list) or any(type(pk) is not int or pk <= 0 for pk in application_ids):
        raise ValidationError("Select actual posted application lines.")
    if len(application_ids) != len(set(application_ids)) or source.pk in application_ids:
        raise ValidationError("Select each historical application once, separately from the original credit.")
    lines = list(JournalLine.objects.filter(pk__in=application_ids).select_related("entry__reversal_of", "account"))
    if len(lines) != len(application_ids):
        raise ValidationError("A selected historical application cannot be found.")
    claimed_ids = {source.pk, *application_ids}
    for head in Head.objects.filter(source__entry__department_id=source.entry.department_id).exclude(
            source_id__in={source.pk, *coordinated_sources}).select_related("attribution"):
        if claimed_ids.intersection({head.source_id, *head.attribution.applications}):
            raise ValidationError("A selected journal line already belongs to another approved claim attribution.")
    for line in lines:
        if (line.entry.status != JournalEntry.POSTED or not line.entry.posted_by_id
                or line.entry.department_id != source.entry.department_id or line.entry.fund_id != source.entry.fund_id
                or line.account_id != source.account_id or line.entry.entry_date < source.entry.entry_date
                or line.payable_origin_id or line.payable_allocation or line.payable_reservation_id or line.payable_claim_reference
                or line.payable_party_key or line.entry.statement_origin.source_type in {"voucher", "remittance"}):
            raise ValidationError("Use unlinked posted applications for the same office, fund, account and claim chronology.")
        if line.credit:
            prior = line.entry.reversal_of.lines.filter(sequence=line.sequence).first() if line.entry.reversal_of_id else None
            if (not prior or prior.pk not in application_ids or prior.account_id != line.account_id
                    or prior.debit != line.credit or prior.credit != line.debit
                    or prior.entry.fund_id != line.entry.fund_id or prior.entry.department_id != line.entry.department_id
                    or not _exact_reversal(line.entry, prior.entry)):
                raise ValidationError("Historical restoring credits require their exact posted application reversal and original debit.")
    for line in [source, *lines]:
        detail = JournalSubsidiaryLine.objects.filter(journal_line=line).first()
        if detail and (detail.category != JournalSubsidiaryLine.PAYABLE or detail.debit != line.debit or detail.credit != line.credit):
            raise ValidationError("Reconcile incompatible retained subsidiary evidence before attributing this claim.")
        # A pre-existing unlinked reversal must be included too. An unposted one
        # cannot silently bypass the claim when it later posts.
        for reversal in JournalEntry.objects.filter(reversal_of_id=line.entry_id).exclude(status=JournalEntry.VOIDED):
            reversed_line = reversal.lines.filter(sequence=line.sequence).first()
            if reversed_line and reversed_line.payable_origin_id == source.pk:
                continue
            if reversed_line and coordinated_sources:
                from .shared_claim_applications import is_shared, validate
                if is_shared(reversed_line) and source.pk in validate(reversed_line):
                    continue
            if (not reversed_line or reversal.status != JournalEntry.POSTED or reversed_line.pk not in application_ids
                    or reversed_line.account_id != line.account_id or reversed_line.debit != line.credit
                    or reversed_line.credit != line.debit or reversal.fund_id != line.entry.fund_id
                    or not _exact_reversal(reversal, line.entry)):
                raise ValidationError("Include every exact posted reversal, or resolve the outstanding reversal draft before attribution.")
    return sorted(application_ids)


@transaction.atomic(using="finance")
def propose(source, actor, *, party_key="", claim_reference="", applications, evidence_reference, reason, expected_version,
        allocations=None):
    stored = JournalLine.objects.select_for_update().get(pk=source.pk)
    _authorize(stored, actor)
    selected = current(stored)
    if selected and selected.shared_proposal_id:
        raise ValidationError("Revise all members of the shared proposal together.")
    if expected_version != (selected.version if selected else 0):
        raise ValidationError("The approved attribution changed. Reload and prepare its successor.")
    if not evidence_reference.strip() or not reason.strip():
        raise ValidationError("Record the supporting reconciliation schedule and the reason for this attribution.")
    split = allocations is not None
    if split and (party_key or claim_reference):
        raise ValidationError("Record each invoice identity in the allocation table.")
    applications = _normalize(stored, applications, party_key, claim_reference, split=split)
    rows = []
    if split:
        from .claim_splits import normalize_allocations
        rows = normalize_allocations(stored, JournalLine.objects.filter(pk__in=applications).select_related("entry"), allocations)
        for row in rows:
            _validate_party(stored, row["party_key"])
    snapshot = serial_snapshot(stored, applications)
    version = (stored.claim_attributions.aggregate(value=Max("version"))["value"] or 0) + 1
    record = Attribution.objects.create(source=stored, department_id=stored.entry.department_id,
        department_label=stored.entry.department_label, version=version, base_version=expected_version,
        party_key=party_key, claim_reference=claim_reference, applications=applications,
        allocation_checksum=checksum(rows) if split else "",
        evidence_reference=evidence_reference.strip(), reason=reason.strip(), source_snapshot=snapshot,
        source_checksum=checksum(snapshot), proposed_by_id=actor.pk,
        proposed_by_label=actor.get_full_name() or actor.username)
    for row in rows:
        member = PayableClaimSlice(attribution=record, **row)
        member._proposal_write = True
        member.save()
    return record


@transaction.atomic(using="finance")
def review(record, actor, *, approve, note):
    initial = Attribution.objects.select_related("source__entry").get(pk=record.pk)
    _authorize(initial.source, actor, review=True)
    if initial.shared_proposal_id:
        raise ValidationError("Review the complete shared proposal together.")
    # Fund first, then original/application rows: also serializes cross-claim
    # attribution and new native claim identities without conditional constraints.
    Fund.objects.select_for_update().get(pk=initial.source.entry.fund_id)
    list(JournalLine.objects.select_for_update().filter(pk__in=[initial.source_id, *initial.applications]).order_by("pk"))
    stored = Attribution.objects.select_for_update().select_related("source").get(pk=record.pk)
    if stored.status != Attribution.SUBMITTED or stored.proposed_by_id == actor.pk or not note.strip():
        raise ValidationError("A different authorized reviewer must decide a submitted attribution and record the basis.")
    if approve:
        selected = current(stored.source)
        if stored.base_version != (selected.version if selected else 0):
            raise ValidationError("Another attribution was approved first. Return this stale proposal and prepare a successor.")
        _normalize(stored.source, stored.applications, stored.party_key, stored.claim_reference, split=stored.is_split)
        rows = allocation_rows(stored)
        if stored.is_split:
            from .claim_splits import normalize_allocations
            normalized = normalize_allocations(stored.source,
                JournalLine.objects.filter(pk__in=stored.applications).select_related("entry"), rows)
            if rows != normalized or checksum(rows) != stored.allocation_checksum:
                raise ValidationError("Historical invoice allocations differ from their retained proposal.")
            for row in rows:
                _validate_party(stored.source, row["party_key"])
        elif rows:
            raise ValidationError("Whole-claim attribution cannot contain invoice allocations.")
        if (serial_snapshot(stored.source, stored.applications) != stored.source_snapshot
                or checksum(stored.source_snapshot) != stored.source_checksum):
            raise ValidationError("The historical source differs from the proposed evidence.")
        if selected and (selected.party_key, selected.claim_reference) != (stored.party_key, stored.claim_reference):
            if stored.source.claim_reservations.exists() or stored.source.payable_applications.exists():
                raise ValidationError("The claim identity is retained by later applications or reservations and cannot be relabelled.")
        if selected and selected.is_split and allocation_rows(selected) != rows:
            if stored.source.claim_reservations.exists() or stored.source.payable_applications.exists():
                raise ValidationError("Retain invoice allocations already used by later applications or reservations.")
        if selected:
            removed = set(selected.applications) - set(stored.applications)
            for line in stored.source.payable_applications.select_related("entry__reversal_of"):
                if line.entry.reversal_of_id:
                    prior = line.entry.reversal_of.lines.filter(sequence=line.sequence).first()
                    if prior and prior.pk in removed:
                        raise ValidationError("Keep historical applications already used by a later financial reversal.")
        identities = [(row["party_key"], row["claim_reference"]) for row in rows] if stored.is_split else [(stored.party_key, stored.claim_reference)]
        for party, claim in identities:
            if claim_identity_exists(stored.department_id, stored.source.entry.fund_id,
                    party, claim, exclude_source=stored.source_id):
                raise ValidationError("This payee's claim reference is already recognized in this fund.")
    stored.status = Attribution.APPROVED if approve else Attribution.RETURNED
    stored.reviewed_by_id = actor.pk
    stored.reviewed_by_label = actor.get_full_name() or actor.username
    stored.reviewed_at = timezone.now()
    stored.review_note = note.strip()
    stored.approval_checksum = checksum(approval_payload(stored)) if approve else ""
    stored._review_transition = True
    stored.save()
    if approve:
        Head.objects.update_or_create(source=stored.source, defaults={"attribution": stored})
        from .payables import _capacity
        daily = defaultdict(lambda: Decimal("0.00"))
        for line in [*application_lines(stored.source), *stored.source.payable_applications.filter(entry__status=JournalEntry.POSTED).select_related("entry")]:
            daily[line.entry.entry_date] += line.debit - line.credit
        used = Decimal("0.00")
        for day, amount in sorted(daily.items()):
            used += amount
            if used < 0 or used > stored.source.credit:
                raise ValidationError(f"Historical applications exceed the claim's dated capacity on {day}.")
        _capacity(stored.source)
        if stored.is_split:
            from .claim_splits import validate_capacity
            validate_capacity(stored.source, stored)
    return stored


def projected_details(department_id, as_of_date):
    """Current reviewed PAYABLE projection; no stored subsidiary row is changed."""
    from copy import copy
    details = {detail.journal_line_id: [detail] for detail in JournalSubsidiaryLine.objects.filter(
        entry__department_id=department_id, entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=as_of_date, category=JournalSubsidiaryLine.PAYABLE).select_related(
            "entry__fund", "journal_line__account")}
    originals = {pk: rows[0] for pk, rows in details.items()}
    owners = {}
    for head in Head.objects.filter(source__entry__department_id=department_id,
            source__entry__entry_date__lte=as_of_date).select_related("attribution__source"):
        record = verify_current(head.attribution)
        selected_lines = Q(pk__in=[record.source_id, *record.applications])
        if record.is_split:
            from .shared_claim_applications import application_filter
            selected_lines |= application_filter(record.source_id)
        for line in JournalLine.objects.filter(selected_lines, entry__status=JournalEntry.POSTED,
                entry__entry_date__lte=as_of_date).select_related("entry__fund", "account"):
            original = originals.get(line.pk)
            rows = allocation_rows(record) if record.is_split else [{"party_key": record.party_key,
                "claim_reference": record.claim_reference}]
            if record.is_split:
                from .claim_splits import effective_shares
                shares = effective_shares(line, record.source, record)
            projected = []
            for row in rows:
                amount = (Decimal(shares.get(row["key"], "0"))
                    if record.is_split else line.debit or line.credit)
                if not amount:
                    continue
                detail = copy(original) if original else JournalSubsidiaryLine(entry=line.entry, journal_line=line,
                    category=JournalSubsidiaryLine.PAYABLE, source_reference=line.entry.reference)
                detail.debit = amount if line.debit else Decimal("0.00")
                detail.credit = amount if line.credit else Decimal("0.00")
                detail.reference_key = row["party_key"]
                detail.reference_label = row["party_key"]
                detail.source_code = "individual-claim"
                detail.source_snapshot = {"original_subsidiary": ({"id": original.pk, "reference_key": original.reference_key,
                    "reference_label": original.reference_label, "source_code": original.source_code,
                    "source_snapshot": original.source_snapshot} if original else None),
                    "claim_attribution": attribution_evidence(record),
                    "claim_line": record.source_id, "claim_reference": row["claim_reference"]}
                if record.is_split:
                    detail.source_snapshot["claim_slice"] = row["key"]
                    detail.source_snapshot["allocation_checksum"] = record.allocation_checksum
                    if line.payable_allocation:
                        detail.source_snapshot["application_allocation"] = line.payable_allocation
                detail.attribution = record
                projected.append(detail)
            if line.pk in owners:
                if not record.shared_proposal_id or owners[line.pk] != record.shared_proposal_id:
                    raise ValidationError("A subsidiary line has conflicting approved claim ownership.")
                details[line.pk].extend(projected)
            else:
                details[line.pk] = projected
                owners[line.pk] = record.shared_proposal_id
    return sorted((detail for group in details.values() for detail in group),
        key=lambda detail: (detail.entry.entry_date, detail.entry.reference, detail.journal_line.sequence,
            detail.source_snapshot.get("claim_slice", "")))
