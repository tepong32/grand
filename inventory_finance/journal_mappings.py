"""Receipt recognition mappings: one write store, retained independent decisions."""
import hashlib
import json
from uuid import UUID
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.access import can_view_ledger
from vouchers.models import VoucherCase, VoucherPostingRequest
from vouchers.access import can_manage_owned_case_artifact, department_for_user, has_explicit_permission
from inventory.finance_sources import resolve_claim_line
from inventory.models import ReceivingReceipt
from inventory.receiving import verify_receipt_evidence
from .access import visible_attributions
from .journal_sources import can_inspect_journals, inspect_recognition
from .models import ReceiptClaimAttribution, ReceiptJournalMapping as Mapping, ReceiptJournalMappingEvent as Event
from .receipt_basis import receipt_basis_current
from .services import _amount, _receipt_support_limit


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def visible_mappings(actor):
    department = department_for_user(actor)
    if not department or not can_view_ledger(actor) or not any(has_explicit_permission(actor,
            f"inventory_finance.{action}_receiptjournalmapping") for action in ("view", "propose", "review")):
        return Mapping.objects.none()
    return Mapping.objects.filter(claim__in=visible_attributions(actor),
        claim__finance_department_id=department.pk)


def can_act(actor, claim, action):
    return can_inspect_journals(actor, claim.case) and can_manage_owned_case_artifact(
        actor, claim.case, f"inventory_finance.{action}_receiptjournalmapping")


def _note(value):
    value = str(value or "").strip()
    if not value or len(value) > 4000:
        raise ValidationError("Record the documentary basis in at most 4,000 characters.")
    return value


def _claim_basis(claim, actor):
    claim.refresh_from_db()
    if claim.status != claim.APPROVED or not receipt_basis_current(claim):
        raise ValidationError("The claim support is not currently approved on this receipt basis.")
    verify_receipt_evidence(claim.receipt_line.receipt)
    source = resolve_claim_line(actor=actor, case_public_id=claim.case.public_id, line_id=claim.source_line_id)
    if source["sha256"] != claim.source_checksum or source["source"]["finance_department_id"] != claim.finance_department_id:
        raise ValidationError("The approved claim source changed; resolve its support first.")
    if claim.amount > _receipt_support_limit(claim.receipt_line):
        raise ValidationError("Claim support exceeds the current documentary receipt ceiling.")
    event = claim.events.filter(action="approved").first()
    expected = {"public_id": str(claim.public_id), "version": claim.state_version, "status": claim.status,
        "receipt_public_id": str(claim.receipt_line.receipt.public_id), "receipt_line_sequence": claim.receipt_line.sequence,
        "case_public_id": str(claim.case.public_id), "source": claim.source_snapshot,
        "source_checksum": claim.source_checksum, "receipt": claim.receipt_snapshot,
        "amount": str(claim.amount), "basis": claim.basis, "note": claim.review_note}
    if (not event or event.snapshot != expected or event.actor_id != claim.reviewed_by_id
            or not claim.reviewed_at or claim.reviewed_by_id == claim.proposed_by_id):
        raise ValidationError("The approved claim no longer reproduces its retained decision.")
    return {"claim": str(claim.public_id), "facts": expected, "reviewed_by": claim.reviewed_by_id,
            "reviewed_at": claim.reviewed_at.isoformat()}


def capture(*, actor, claim, posting_request_id, sequence):
    """Read current evidence; mutation callers also hold source and receipt locks."""
    if (not can_inspect_journals(actor, claim.case)
            or not visible_attributions(actor).filter(pk=claim.pk).exists()):
        raise PermissionDenied
    try:
        request_id = UUID(str(posting_request_id))
        if isinstance(sequence, bool) or str(int(sequence)) != str(sequence) or int(sequence) <= 0:
            raise ValueError
        sequence = int(sequence)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Select a posting request and positive journal line sequence.")
    source = VoucherPostingRequest.objects.select_related("case__configuration_release").filter(
        public_id=request_id, case_id=claim.case_id, finance_department_id=claim.finance_department_id).first()
    if not source:
        raise ValidationError("Select a recognition request belonging to this claim's ledger.")
    observed = inspect_recognition(source, actor=actor)
    if observed["issue"]:
        raise ValidationError(observed["issue"])
    entry = observed["entry"]
    line = next((line for line in observed["lines"] if line.sequence == sequence), None)
    if not line or line.account.account_type not in ("asset", "expense"):
        raise ValidationError("Select an asset or expense debit; liability/payment lines do not establish this mapping.")
    dimensions = lambda obj: {"uuid": str(obj.public_id), "code": obj.code} if obj else None
    journal = {"request": str(source.public_id), "version": source.version, "kind": source.kind,
        "payload_checksum": source.payload_checksum, "rule_checksum": source.posting_rule_checksum,
        "journal": str(entry.public_id), "owner": entry.department_id, "reference": entry.reference,
        "date": entry.entry_date.isoformat(), "fund": dimensions(entry.fund),
        "period": {"year": entry.period.fiscal_year, "number": entry.period.period_number},
        "posted_by": entry.posted_by_id, "posted_at": entry.posted_at.isoformat(),
        "sequence": line.sequence, "account": {**dimensions(line.account), "title": line.account.title,
            "type": line.account.account_type}, "center": dimensions(line.responsibility_center),
        "debit": str(line.debit), "credit": str(line.credit)}
    return {"journal": journal, "claim": _claim_basis(claim, actor)}


def _payload(row):
    return {"uuid": str(row.public_id), "claim": str(row.claim.public_id),
        "request": str(row.posting_request.public_id), "journal": str(row.journal_public_id),
        "sequence": row.line_sequence, "amount": format(row.amount, ".2f"), "basis": row.basis,
        "source": row.source_snapshot, "claim_basis": row.claim_snapshot, "proposed_by": row.proposed_by_id}


def _decision(row):
    return {"proposal_checksum": row.proposal_checksum, "status": row.status, "version": row.state_version,
        "reviewed_by": row.reviewed_by_id, "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "review_note": row.review_note}


def _event(row, actor, action, note):
    snapshot = {**_decision(row), "note": note, "actor": actor.pk, "action": action}
    Event.objects.create(mapping=row, actor=actor, action=action, snapshot=snapshot, checksum=checksum(snapshot))


def verify(row):
    events = list(row.events.all())
    if (checksum(_payload(row)) != row.proposal_checksum or len(events) != row.state_version
            or any(checksum(event.snapshot) != event.checksum or event.snapshot.get("version") != index
                   or event.snapshot.get("proposal_checksum") != row.proposal_checksum
                   or event.snapshot.get("actor") != event.actor_id or event.snapshot.get("action") != event.action
                   for index, event in enumerate(events, 1))
            or not events or any(events[-1].snapshot.get(key) != value for key, value in _decision(row).items())):
        raise ValidationError("Retained mapping evidence or decision history is inconsistent.")
    return row


def current(row, actor):
    verify(row)
    evidence = capture(actor=actor, claim=row.claim, posting_request_id=row.posting_request.public_id,
                       sequence=row.line_sequence)
    if evidence != {"journal": row.source_snapshot, "claim": row.claim_snapshot}:
        raise ValidationError("The retained journal or claim basis changed; review and withdraw this mapping.")
    return evidence


def _locked_claim(actor, claim_id, action):
    candidate = visible_attributions(actor).select_related("case__configuration_release").filter(public_id=claim_id).first()
    if not candidate or not can_act(actor, candidate, action):
        raise PermissionDenied
    locked_case = VoucherCase.objects.select_for_update().get(pk=candidate.case_id)
    ReceivingReceipt.objects.select_for_update().get(pk=candidate.receipt_line.receipt_id)
    claim = ReceiptClaimAttribution.objects.select_for_update().get(pk=candidate.pk)
    claim.case = locked_case
    if (not can_act(actor, claim, action)
            or claim.finance_department_id != department_for_user(actor).pk):
        raise PermissionDenied
    return claim


def _lock_source(claim, request_id):
    source = VoucherPostingRequest.objects.select_for_update().filter(public_id=request_id, case_id=claim.case_id).first()
    if not source or not source.accounting_entry_public_id:
        raise ValidationError("A bound recognition journal is required.")
    if not JournalEntry.objects.select_for_update().filter(public_id=source.accounting_entry_public_id,
            department_id=claim.finance_department_id).exists():
        raise ValidationError("The source journal is unavailable.")
    return source


# Finance is the outer read/lock transaction: default commits while its journal
# lock is held. There are NO Finance writes and no distributed commit claim.
@transaction.atomic(using="finance")
@transaction.atomic(using="default", durable=True)
def propose(*, actor, claim_id, posting_request_id, sequence, amount, basis, request_id, expected_basis):
    claim = _locked_claim(actor, claim_id, "propose")
    amount, basis = _amount(amount), _note(basis)
    try:
        request_id, posting_request_id = UUID(str(request_id)), UUID(str(posting_request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Valid request identities are required.")
    existing = Mapping.objects.filter(public_id=request_id).first()
    if existing:
        verify(existing)
        if (existing.claim_id == claim.pk and existing.proposed_by_id == actor.pk
                and existing.posting_request.public_id == posting_request_id and existing.line_sequence == sequence
                and existing.amount == amount and existing.basis == basis
                and expected_basis == {"journal": existing.source_snapshot, "claim": existing.claim_snapshot}):
            return existing
        raise ValidationError("This request identity already belongs to different mapping content.")
    source = _lock_source(claim, posting_request_id)
    evidence = capture(actor=actor, claim=claim, posting_request_id=posting_request_id, sequence=sequence)
    if evidence != expected_basis:
        raise ValidationError("The preview changed. Inspect the current source before proposing a mapping.")
    if amount > claim.amount or amount > Decimal(evidence["journal"]["debit"]):
        raise ValidationError("The mapping exceeds the selected debit or approved claim support.")
    row = Mapping(public_id=request_id, claim=claim, posting_request=source,
        journal_public_id=evidence["journal"]["journal"], line_sequence=sequence, amount=amount, basis=basis,
        source_snapshot=evidence["journal"], claim_snapshot=evidence["claim"], proposed_by=actor)
    row.proposal_checksum = checksum(_payload(row))
    row.full_clean()
    row.save()
    _event(row, actor, "proposed", basis)
    return row


@transaction.atomic(using="finance")
@transaction.atomic(using="default", durable=True)
def decide(*, actor, mapping_id, expected_version, action, note):
    if action not in ("approve", "reject", "withdraw"):
        raise ValidationError("Select approve, reject or withdraw.")
    note = _note(note)
    candidate = visible_mappings(actor).filter(public_id=mapping_id).first()
    if not candidate:
        raise PermissionDenied
    claim = _locked_claim(actor, candidate.claim.public_id, "review")
    row = Mapping.objects.select_for_update().get(pk=candidate.pk)
    verify(row)
    if row.state_version != expected_version or row.status not in (
            (row.PROPOSED, row.APPROVED) if action == "withdraw" else (row.PROPOSED,)):
        raise ValidationError("This mapping changed or cannot take that decision. Reload it.")
    if action != "withdraw" and row.proposed_by_id == actor.pk:
        raise PermissionDenied("A different authorized officer must review the proposal.")
    if action == "approve":
        _lock_source(claim, row.posting_request.public_id)
        evidence = current(row, actor)
        # The case lock serializes every debit allocation from this source. The
        # receipt/claim locks serialize this claim's competing mapping approvals.
        approved = Mapping.objects.filter(claim__case_id=claim.case_id, status=Mapping.APPROVED)
        for previous in approved:
            current(previous, actor)
        debit_total = approved.filter(journal_public_id=row.journal_public_id,
            line_sequence=row.line_sequence).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        claim_total = approved.filter(claim=claim).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if debit_total + row.amount > Decimal(evidence["journal"]["debit"]) or claim_total + row.amount > claim.amount:
            raise ValidationError("Approved mappings would exceed the debit or claim-support amount.")
    if action != "withdraw":
        row.reviewed_by, row.reviewed_at, row.review_note = actor, timezone.now(), note
    row.status = {"approve": row.APPROVED, "reject": row.REJECTED, "withdraw": row.WITHDRAWN}[action]
    row.state_version += 1
    row._decision_write = True
    row.full_clean()
    row.save(update_fields=("status", "state_version", "reviewed_by", "reviewed_at", "review_note"))
    _event(row, actor, row.status, note)
    return row
