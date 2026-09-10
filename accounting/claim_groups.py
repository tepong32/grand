"""Finance-side immutable claim allocation and atomic reservation groups."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import JournalLine, JournalEntry, PayableClaimReservation, PayableClaimReservationGroup, PayableClaimRetirement
from .payables import _digest, _reserve_claim, reservation_evidence, verify_reservation


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result >= Decimal("10000000000000000") or result != result.quantize(Decimal("0.01")):
            raise ValueError
        return result.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Enter nonnegative amounts in exact centavos.")


def validate_member(group, source_id, amount, case_public_id, *, invoice_key=None):
    rows = [row for row in group.allocation_snapshot.get("claims", []) if row["source_id"] == source_id
        and row.get("invoice_key", "") == (str(invoice_key) if invoice_key else "")]
    if (group.case_public_id != case_public_id or _digest(group.allocation_snapshot) != group.allocation_checksum
            or len(rows) != 1 or money(rows[0]["gross"]) != amount):
        raise ValidationError("The claim differs from its retained DV allocation.")


def retirement_movements(reservation):
    movements = []
    for record in reservation.retirements.select_related("entry"):
        entry = record.entry
        actual = sum((line.credit - line.debit for line in entry.lines.filter(payable_reservation=reservation)), Decimal("0.00"))
        if (not reservation.group_id or _digest(record.evidence) != record.checksum
                or record.amount <= 0 or record.amount != actual or entry.status != JournalEntry.POSTED
                or not entry.reversal_of_id or not entry.posted_by_id
                or record.evidence.get("entry") != str(entry.public_id)
                or record.evidence.get("reservation") != str(reservation.public_id)
                or record.evidence.get("amount") != str(record.amount)
                or entry.source_snapshot.get("prior_payable", {}).get("group") != str(reservation.group.public_id)
                or entry.source_snapshot.get("posting_trigger", {}).get("outcome") != "close"):
            raise ValidationError("The retired claim share differs from its independently posted closing return.")
        movements.append((entry.entry_date, record.amount))
    return movements


def retired_amount(reservation):
    return sum((amount for _, amount in retirement_movements(reservation)), Decimal("0.00"))


def retire_return(reservations, entry, request, review, actor):
    """Caller owns the default case and sorted Finance claim locks."""
    from .payables import _capacity
    for reservation in reservations:
        amount = sum((line.credit-line.debit for line in entry.lines.filter(payable_reservation=reservation)), Decimal("0.00"))
        if not amount:
            continue
        evidence = {"entry": str(entry.public_id), "request": str(request.public_id),
            "review": str(review.public_id), "reservation": str(reservation.public_id), "amount": str(amount)}
        prior = PayableClaimRetirement.objects.filter(reservation=reservation, entry=entry).first()
        if prior:
            if prior.evidence != evidence or prior.checksum != _digest(evidence):
                raise ValidationError("The recovered claim retirement differs from its original closing decision.")
        else:
            PayableClaimRetirement.objects.create(reservation=reservation, entry=entry,
                amount=amount, evidence=evidence, checksum=_digest(evidence), created_by_id=actor.pk)
        _capacity(reservation.source)
        if reservation.invoice_key:
            _capacity(reservation.source, invoice_key=reservation.invoice_key)


def group_evidence(group):
    return {"schema": 2, "group": str(group.public_id), "allocation": group.allocation_snapshot,
        "checksum": group.allocation_checksum,
        "claims": [reservation_evidence(r) for r in group.reservations.order_by("source_id", "invoice_key")]}


def resolve(evidence, *, case_public_id, lock=False, allow_released=False):
    """Resolve all members, preserving legacy single-claim evidence unchanged."""
    if not evidence:
        return []
    if evidence.get("schema") == 2:
        group = PayableClaimReservationGroup.objects.filter(public_id=evidence.get("group"), case_public_id=case_public_id).first()
        if (group is None or _digest(group.allocation_snapshot) != group.allocation_checksum
                or group_evidence(group) != evidence):
            raise ValidationError("The retained DV claim allocation differs from its Finance evidence.")
        reservations = list(group.reservations.order_by("source_id", "invoice_key"))
        if len(reservations) != len(group.allocation_snapshot["claims"]) or not reservations:
            raise ValidationError("The DV claim allocation is incomplete.")
        for reservation in reservations:
            validate_member(group, reservation.source_id, reservation.amount, case_public_id, invoice_key=reservation.invoice_key)
    else:
        reservation = PayableClaimReservation.objects.filter(public_id=evidence.get("reservation"), case_public_id=case_public_id).first()
        if reservation is None or reservation.group_id or reservation_evidence(reservation) != evidence:
            raise ValidationError("The retained prior-payable reservation is missing or differs from its evidence.")
        reservations = [reservation]
    if lock:
        list(JournalLine.objects.select_for_update().filter(pk__in=[r.source_id for r in reservations]).order_by("pk"))
    for reservation in reservations:
        reservation.refresh_from_db()
        if not (allow_released and reservation.released_at):
            verify_reservation(reservation)
    return reservations


def contains_reservation(evidence, reservation):
    if not evidence:
        return False
    return any(r.pk == reservation.pk for r in resolve(evidence, case_public_id=reservation.case_public_id))


@transaction.atomic(using="finance")
def reserve(*, key, case_public_id, snapshot, actor_id, as_of):
    # The caller holds the default-store case lock. Sorted source locks cover all
    # capacity writers; the entire group commits or rolls back in Finance.
    source_ids = [row["source_id"] for row in snapshot["claims"]]
    list(JournalLine.objects.select_for_update().filter(pk__in=source_ids).order_by("pk"))
    group = PayableClaimReservationGroup.objects.filter(group_key=key).first()
    if group:
        if group.case_public_id != case_public_id or group.allocation_snapshot != snapshot:
            raise ValidationError("An interrupted handoff retained different claim allocations. Recover or return it before changing the allocation.")
        evidence = group_evidence(group)
        resolve(evidence, case_public_id=case_public_id)
        return evidence
    group = PayableClaimReservationGroup.objects.create(group_key=key, case_public_id=case_public_id,
        allocation_snapshot=snapshot, allocation_checksum=_digest(snapshot), created_by_id=actor_id)
    for row in sorted(snapshot["claims"], key=lambda r: (r["source_id"], r.get("invoice_key", ""))):
        member_key = ("invoice:" + _digest([key, row["source_id"], row["invoice_key"]])
            if row.get("invoice_key") else f"{key}:{row['source_id']}")
        _reserve_claim(source_id=row["source_id"], case_public_id=case_public_id, key=member_key,
            amount=row["gross"], actor_id=actor_id, department_id=snapshot["department"],
            fund_code=snapshot["fund"], party_key=snapshot["party"], as_of=as_of, group=group,
            invoice_key=row.get("invoice_key"))
    return group_evidence(group)
