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
    PayableClaimAttribution as Attribution, PayableClaimAttributionHead as Head)

_CURRENT = object()


def source_snapshot(source, application_ids):
    lines = list(JournalLine.objects.filter(pk__in=[source.pk, *application_ids]).select_related("entry__fund"))
    entries = {line.entry_id: line.entry for line in lines}
    return {"source_line": source.pk, "application_lines": sorted(application_ids),
        "claim_fields": list(JournalLine.objects.filter(pk__in=[line.pk for line in lines]).order_by("pk").values(
            "pk", "payable_origin_id", "payable_reservation_id", "payable_party_key", "payable_claim_reference")),
        "journals": [journal_snapshot(entries[key]) for key in sorted(entries)],
        "subsidiaries": list(JournalSubsidiaryLine.objects.filter(journal_line__in=lines).order_by("pk").values(
            "pk", "journal_line_id", "category", "reference_key", "reference_label", "source_code",
            "source_reference", "source_snapshot", "debit", "credit"))}


def serial_snapshot(source, application_ids):
    # JSON stores exact decimal strings, never backend-specific Decimal values.
    import json
    return json.loads(json.dumps(source_snapshot(source, application_ids), default=str))


def approval_payload(record):
    return {"public_id": str(record.public_id), "source": record.source_id, "version": record.version,
        "base_version": record.base_version, "party": record.party_key, "claim": record.claim_reference,
        "applications": record.applications, "source_checksum": record.source_checksum,
        "evidence": record.evidence_reference, "reason": record.reason, "proposed_by": record.proposed_by_id,
        "reviewed_by": record.reviewed_by_id, "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "review_note": record.review_note}


def verify(record):
    if (record.status != Attribution.APPROVED or not record.reviewed_by_id or not record.reviewed_at
            or record.reviewed_by_id == record.proposed_by_id
            or checksum(approval_payload(record)) != record.approval_checksum
            or checksum(record.source_snapshot) != record.source_checksum
            or serial_snapshot(record.source, record.applications) != record.source_snapshot):
        raise ValidationError("Historical claim evidence no longer reproduces its approved source and decision.")
    return record


def current(source):
    head = Head.objects.select_related("attribution__source").filter(source_id=source.pk).first()
    return verify(head.attribution) if head else None


def attribution_evidence(record):
    return {"public_id": str(record.public_id), "version": record.version,
        "approval_checksum": record.approval_checksum, "source_checksum": record.source_checksum}


def verify_retained_evidence(source, evidence):
    if not isinstance(evidence, dict):
        raise ValidationError("The retained historical attribution is invalid.")
    record = Attribution.objects.filter(public_id=evidence.get("public_id"), source_id=source.pk).first()
    if (record is None or attribution_evidence(verify(record)) != evidence
            or identity(source) != (record.party_key, record.claim_reference)):
        raise ValidationError("The retained historical attribution differs from its original approved decision.")


def identity(source, *, record=_CURRENT):
    if source.payable_claim_reference and source.payable_party_key:
        return source.payable_party_key, source.payable_claim_reference
    if record is _CURRENT:
        record = current(source)
    return (record.party_key, record.claim_reference) if record else ("", "")


def eligible_claims(department_id, party_key=None):
    historical = Head.objects.filter(source__entry__department_id=department_id)
    named = Q(payable_claim_reference__gt="", payable_party_key__gt="")
    if party_key is not None:
        historical = historical.filter(attribution__party_key=party_key)
        named &= Q(payable_party_key=party_key)
    return JournalLine.objects.filter(entry__department_id=department_id, entry__status=JournalEntry.POSTED,
        payable_origin__isnull=True, credit__gt=0).filter(named | Q(pk__in=historical.values("source_id")))


def application_lines(source, *, record=_CURRENT):
    if record is _CURRENT:
        record = current(source)
    return list(JournalLine.objects.filter(pk__in=record.applications).select_related("entry")) if record else []


def application_origin(line):
    if line.payable_origin_id:
        return line.payable_origin
    for head in Head.objects.filter(source__entry__department_id=line.entry.department_id).select_related("attribution__source"):
        if line.pk in head.attribution.applications:
            return verify(head.attribution).source
    return None


def reversal_origin(line):
    return application_origin(line) or (line if identity(line)[1] else None)


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


def _normalize(source, application_ids, party, claim):
    if (source.entry.status != JournalEntry.POSTED or not source.entry.posted_by_id
            or source.payable_origin_id or source.credit <= 0 or source.debit
            or source.account.account_type != "liability" or source.entry.reversal_of_id
            or source.entry.source_type in {"voucher", "remittance"}):
        raise ValidationError("Select an original posted liability credit outside an active generated payment workflow.")
    if not party.strip() or party != party.strip() or not claim.strip() or claim != claim.strip():
        raise ValidationError("Record the exact payee key and claim reference without surrounding spaces.")
    if source.payable_claim_reference and (source.payable_party_key, source.payable_claim_reference) != (party, claim):
        raise ValidationError("Preserve the original journal's recorded claim identity.")
    if party.startswith("finance-party:"):
        from finance.models import FinanceParty
        if not FinanceParty.objects.filter(department_id=source.entry.department_id,
                code=party.removeprefix("finance-party:"), status__in=("approved", "scheduled", "active", "superseded")).exists():
            raise ValidationError("Select a governed payee from this Accounting office's Finance Setup.")
    if not isinstance(application_ids, list) or any(type(pk) is not int or pk <= 0 for pk in application_ids):
        raise ValidationError("Select actual posted application lines.")
    if len(application_ids) != len(set(application_ids)) or source.pk in application_ids:
        raise ValidationError("Select each historical application once, separately from the original credit.")
    lines = list(JournalLine.objects.filter(pk__in=application_ids).select_related("entry__reversal_of", "account"))
    if len(lines) != len(application_ids):
        raise ValidationError("A selected historical application cannot be found.")
    claimed_ids = {source.pk, *application_ids}
    for head in Head.objects.filter(source__entry__department_id=source.entry.department_id).exclude(source=source).select_related("attribution"):
        if claimed_ids.intersection({head.source_id, *head.attribution.applications}):
            raise ValidationError("A selected journal line already belongs to another approved claim attribution.")
    for line in lines:
        if (line.entry.status != JournalEntry.POSTED or not line.entry.posted_by_id
                or line.entry.department_id != source.entry.department_id or line.entry.fund_id != source.entry.fund_id
                or line.account_id != source.account_id or line.entry.entry_date < source.entry.entry_date
                or line.payable_origin_id or line.payable_reservation_id or line.payable_claim_reference
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
            if (not reversed_line or reversal.status != JournalEntry.POSTED or reversed_line.pk not in application_ids
                    or reversed_line.account_id != line.account_id or reversed_line.debit != line.credit
                    or reversed_line.credit != line.debit or reversal.fund_id != line.entry.fund_id
                    or not _exact_reversal(reversal, line.entry)):
                raise ValidationError("Include every exact posted reversal, or resolve the outstanding reversal draft before attribution.")
    return sorted(application_ids)


@transaction.atomic(using="finance")
def propose(source, actor, *, party_key, claim_reference, applications, evidence_reference, reason, expected_version):
    stored = JournalLine.objects.select_for_update().get(pk=source.pk)
    _authorize(stored, actor)
    selected = current(stored)
    if expected_version != (selected.version if selected else 0):
        raise ValidationError("The approved attribution changed. Reload and prepare its successor.")
    if not evidence_reference.strip() or not reason.strip():
        raise ValidationError("Record the supporting reconciliation schedule and the reason for this attribution.")
    applications = _normalize(stored, applications, party_key, claim_reference)
    snapshot = serial_snapshot(stored, applications)
    version = (stored.claim_attributions.aggregate(value=Max("version"))["value"] or 0) + 1
    return Attribution.objects.create(source=stored, department_id=stored.entry.department_id,
        department_label=stored.entry.department_label, version=version, base_version=expected_version,
        party_key=party_key, claim_reference=claim_reference, applications=applications,
        evidence_reference=evidence_reference.strip(), reason=reason.strip(), source_snapshot=snapshot,
        source_checksum=checksum(snapshot), proposed_by_id=actor.pk,
        proposed_by_label=actor.get_full_name() or actor.username)


@transaction.atomic(using="finance")
def review(record, actor, *, approve, note):
    initial = Attribution.objects.select_related("source__entry").get(pk=record.pk)
    _authorize(initial.source, actor, review=True)
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
        _normalize(stored.source, stored.applications, stored.party_key, stored.claim_reference)
        if (serial_snapshot(stored.source, stored.applications) != stored.source_snapshot
                or checksum(stored.source_snapshot) != stored.source_checksum):
            raise ValidationError("The historical source differs from the proposed evidence.")
        if selected and (selected.party_key, selected.claim_reference) != (stored.party_key, stored.claim_reference):
            if stored.source.claim_reservations.exists() or stored.source.payable_applications.exists():
                raise ValidationError("The claim identity is retained by later applications or reservations and cannot be relabelled.")
        if selected:
            removed = set(selected.applications) - set(stored.applications)
            for line in stored.source.payable_applications.select_related("entry__reversal_of"):
                if line.entry.reversal_of_id:
                    prior = line.entry.reversal_of.lines.filter(sequence=line.sequence).first()
                    if prior and prior.pk in removed:
                        raise ValidationError("Keep historical applications already used by a later financial reversal.")
        duplicate = JournalLine.objects.filter(entry__department_id=stored.department_id,
            entry__fund_id=stored.source.entry.fund_id, entry__status=JournalEntry.POSTED,
            payable_party_key__iexact=stored.party_key, payable_claim_reference__iexact=stored.claim_reference
            ).exclude(pk=stored.source_id).exists()
        duplicate = duplicate or Head.objects.filter(source__entry__department_id=stored.department_id,
            source__entry__fund_id=stored.source.entry.fund_id, attribution__party_key__iexact=stored.party_key,
            attribution__claim_reference__iexact=stored.claim_reference).exclude(source_id=stored.source_id).exists()
        if duplicate:
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
    return stored


def projected_details(department_id, as_of_date):
    """Current reviewed PAYABLE projection; no stored subsidiary row is changed."""
    from copy import copy
    details = {detail.journal_line_id: detail for detail in JournalSubsidiaryLine.objects.filter(
        entry__department_id=department_id, entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=as_of_date, category=JournalSubsidiaryLine.PAYABLE).select_related(
            "entry__fund", "journal_line__account")}
    for head in Head.objects.filter(source__entry__department_id=department_id,
            source__entry__entry_date__lte=as_of_date).select_related("attribution__source"):
        record = verify(head.attribution)
        for line in JournalLine.objects.filter(pk__in=[record.source_id, *record.applications],
                entry__entry_date__lte=as_of_date).select_related("entry__fund", "account"):
            original = details.get(line.pk)
            detail = copy(original) if original else JournalSubsidiaryLine(entry=line.entry, journal_line=line,
                category=JournalSubsidiaryLine.PAYABLE, debit=line.debit, credit=line.credit,
                source_reference=line.entry.reference)
            detail.reference_key = record.party_key
            detail.reference_label = record.party_key
            detail.source_code = "individual-claim"
            detail.source_snapshot = {"original_subsidiary": ({"id": original.pk, "reference_key": original.reference_key,
                "reference_label": original.reference_label, "source_code": original.source_code,
                "source_snapshot": original.source_snapshot} if original else None),
                "claim_attribution": {"public_id": str(record.public_id), "version": record.version,
                    "approval_checksum": record.approval_checksum, "source_checksum": record.source_checksum},
                "claim_line": record.source_id, "claim_reference": record.claim_reference}
            detail.attribution = record
            details[line.pk] = detail
    return sorted(details.values(), key=lambda detail: (detail.entry.entry_date, detail.entry.reference, detail.journal_line.sequence))
