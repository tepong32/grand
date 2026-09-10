"""Individual payable claims and applications on the existing posted journal."""
from collections import defaultdict
from decimal import Decimal
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Fund, JournalEntry, JournalLine, JournalSubsidiaryLine, PayableClaimReservation


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def claim_snapshot(source):
    return {"line": source.pk, "entry": str(source.entry.public_id), "reference": source.entry.reference,
        "date": source.entry.entry_date.isoformat(), "sequence": source.sequence,
        "department": source.entry.department_id, "fund": source.entry.fund.code,
        "account": source.account.code, "party": source.payable_party_key,
        "claim": source.payable_claim_reference, "credit": str(source.credit)}


def reservation_evidence(reservation):
    return {"reservation": str(reservation.public_id), "key": reservation.reservation_key,
        "case": str(reservation.case_public_id), "amount": str(reservation.amount),
        "source": reservation.source_snapshot, "checksum": reservation.source_checksum}


def verify_reservation(reservation, evidence=None):
    if (reservation.released_at or _digest(reservation.source_snapshot) != reservation.source_checksum
            or claim_snapshot(reservation.source) != reservation.source_snapshot
            or reservation.source.entry.status != JournalEntry.POSTED
            or (evidence is not None and reservation_evidence(reservation) != evidence)):
        raise ValidationError("The retained prior-payable reservation differs from its posted source or has been released. Investigate the handoff.")
    return reservation


def _capacity(source, candidate_lines=(), *, as_of=None):
    """Called with the original credit locked by every capacity writer."""
    used = Decimal("0.00")
    by_reservation = defaultdict(lambda: Decimal("0.00"))
    candidates = list(candidate_lines)
    applications = JournalLine.objects.filter(payable_origin=source, entry__status=JournalEntry.POSTED)
    if candidates:
        applications = applications.exclude(entry_id=candidates[0].entry_id)
    movements = [*applications.select_related("entry"), *candidates]
    for line in movements:
        delta = line.debit - line.credit
        used += delta
        if line.payable_reservation_id:
            by_reservation[line.payable_reservation_id] += delta
    held = Decimal("0.00")
    active_reservations = set()
    committed_holds = Decimal("0.00")
    for reservation in source.claim_reservations.all():
        consumed = by_reservation.pop(reservation.pk, Decimal("0.00"))
        if consumed < 0 or consumed > reservation.amount:
            raise ValidationError("The application exceeds its voucher's prior-payable reservation.")
        if not reservation.released_at:
            held += reservation.amount - consumed
            active_reservations.add(reservation.pk)
            committed_holds += reservation.amount
    if any(by_reservation.values()):
        raise ValidationError("A missing payable reservation has financial applications.")
    if used + held > source.credit:
        raise ValidationError("The claim amount is already applied or reserved for another voucher.")
    available = source.credit - used - held
    if as_of is not None:
        # A new reservation must fit on its effective date and throughout later
        # posted history, not just after a subsequent reversal restores capacity.
        # Active reservations already commit their whole amount: their linked
        # applications convert held capacity to used capacity, not a second use.
        daily = defaultdict(lambda: Decimal("0.00"))
        daily[as_of] = Decimal("0.00")
        for line in movements:
            if line.payable_reservation_id not in active_reservations:
                daily[line.entry.entry_date] += line.debit - line.credit
        committed = committed_holds
        for day, delta in sorted(daily.items()):
            committed += delta
            if day >= as_of:
                available = min(available, source.credit - committed)
    return available


@transaction.atomic(using="finance")
def _reserve_claim(*, source_id, case_public_id, key, amount, actor_id, department_id, fund_code, party_key, as_of):
    """Internal handoff; the voucher service owns actor/case authorization."""
    # Lock only the source row. Joining Fund here would also lock it on MySQL,
    # reversing the fund-before-claim order used by mixed recognition entries.
    source = JournalLine.objects.select_for_update().get(pk=source_id)
    if (source.entry.department_id != department_id or source.entry.fund.code != fund_code
            or source.payable_party_key != party_key or source.entry.entry_date > as_of
            or source.entry.status != JournalEntry.POSTED or not source.entry.posted_by_id
            or source.payable_origin_id or not source.payable_claim_reference or source.credit <= 0
            or source.debit or source.account.account_type != "liability"
            or not source.account.is_active or not source.account.allow_posting):
        raise ValidationError("Select a posted original claim for this payee, fund, Accounting office and date.")
    amount = Decimal(amount)
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValidationError("Reserve a positive claim amount in exact centavos.")
    existing = PayableClaimReservation.objects.filter(reservation_key=key).first()
    if existing:
        if existing.source_id != source_id or existing.case_public_id != case_public_id or existing.amount != amount:
            raise ValidationError("An interrupted handoff retained different claim evidence. Release the unused reservation before changing it.")
        return verify_reservation(existing)
    if PayableClaimReservation.objects.filter(case_public_id=case_public_id, released_at__isnull=True).exists():
        raise ValidationError("This case already retains a claim reservation. Recover or release it before validating again.")
    if _capacity(source, as_of=as_of) < amount:
        raise ValidationError("The claim amount is already applied or reserved for another voucher on or after the requested date. Review the dated claim applications or use the actual later settlement date.")
    snapshot = claim_snapshot(source)
    reservation = PayableClaimReservation(reservation_key=key, case_public_id=case_public_id, source=source,
        amount=amount, source_snapshot=snapshot, source_checksum=_digest(snapshot), created_by_id=actor_id)
    reservation.full_clean()
    reservation.save()
    return reservation


@transaction.atomic(using="finance")
def _release_unused_claim(reservation, *, actor_id, reason):
    JournalLine.objects.select_for_update().get(pk=reservation.source_id)
    reservation.refresh_from_db()
    if reservation.released_at:
        return  # Recover an interrupted default-store return without rewriting evidence.
    if not reason.strip():
        raise ValidationError("Record why the unused claim reservation is being released.")
    if reservation.applications.exclude(entry__status=JournalEntry.VOIDED).exists():
        raise ValidationError("This reservation has journal applications. Resolve the posted or pending financial evidence before releasing it.")
    reservation.released_at = timezone.now()
    reservation.released_by_id = actor_id
    reservation.release_reason = reason.strip()
    reservation._release_transition = True
    reservation.save(update_fields=("released_at", "released_by_id", "release_reason"))


def validate_claim_line(line):
    if line.payable_reservation_id:
        reservation = verify_reservation(line.payable_reservation)
        if line.payable_origin_id != reservation.source_id:
            raise ValidationError("The application must use its reserved original claim.")
        evidence = line.entry.source_snapshot.get("prior_payable")
        linked_entry = line.entry
        if line.entry.reversal_of_id:
            linked_entry = line.entry.reversal_of
            evidence = linked_entry.source_snapshot.get("prior_payable")
        if (evidence != reservation_evidence(reservation) or linked_entry.source_type != "voucher"
                or linked_entry.source_snapshot.get("voucher_case") != str(reservation.case_public_id)):
            raise ValidationError("A reserved application requires its retained voucher handoff evidence.")
    named = bool(line.payable_party_key or line.payable_claim_reference)
    if not named and not line.payable_origin_id:
        return
    if not line.account_id:
        return  # The model/form reports its required account field.
    if line.account.account_type != "liability":
        raise ValidationError("Payable claims and applications require a liability account.")
    if named:
        if (line.payable_origin_id or (line.credit or 0) <= 0 or (line.debit or 0) != 0
                or not line.payable_party_key.strip() or not line.payable_claim_reference.strip()):
            raise ValidationError("A new payable claim needs a liability credit, payee key and claim reference; use the original claim for a settlement.")
        if line.payable_party_key != line.payable_party_key.strip() or line.payable_claim_reference != line.payable_claim_reference.strip():
            raise ValidationError("Remove leading or trailing spaces from the payee key and claim reference.")
        return
    origin = line.payable_origin
    if (origin.pk == line.pk or origin.payable_origin_id or not origin.payable_claim_reference
            or not origin.payable_party_key or origin.credit <= 0 or origin.debit
            or origin.entry.status != JournalEntry.POSTED or not origin.entry.posted_by_id):
        raise ValidationError("Select an independently posted original payable claim.")
    if (line.entry.department_id != origin.entry.department_id or line.entry.fund_id != origin.entry.fund_id
            or line.account_id != origin.account_id):
        raise ValidationError("The application must use the original claim's office, fund and liability account.")
    if line.entry.entry_date < origin.entry.entry_date:
        raise ValidationError("A claim cannot be settled before its recognition date.")
    if line.credit:
        # A credit restores capacity only through an actual, exactly mirrored reversal.
        prior = (line.entry.reversal_of.lines.filter(sequence=line.sequence).first()
                 if line.entry.reversal_of_id else None)
        if (not prior or prior.payable_origin_id != origin.pk or prior.debit != line.credit
                or prior.payable_reservation_id != line.payable_reservation_id
                or prior.credit != line.debit or prior.account_id != line.account_id
                or prior.entry.fund_id != line.entry.fund_id or prior.entry.status != JournalEntry.POSTED
                or line.entry.entry_date < prior.entry.entry_date):
            raise ValidationError("Restore a payable claim only through an exact reversal of its posted application.")


def validate_claim_applications(entry, *, lock=False):
    lines = list(entry.lines.select_related("entry", "account", "payable_origin__entry"))
    new_claims = [line for line in lines if line.payable_claim_reference]
    if lock and new_claims:
        # Serialize invoice identity checks without a competing claim registry.
        Fund.objects.select_for_update().get(pk=entry.fund_id)
    origin_ids = sorted({line.payable_origin_id for line in lines if line.payable_origin_id})
    if lock:
        # Every writer locks original credit rows in the same order, then reads
        # posted applications and remaining voucher reservations.
        list(JournalLine.objects.select_for_update().filter(pk__in=origin_ids).order_by("pk"))
    for line in lines:
        validate_claim_line(line)
    identities = set()
    for line in new_claims:
        identity = (line.payable_party_key.casefold(), line.payable_claim_reference.casefold())
        duplicate = JournalLine.objects.filter(entry__department_id=entry.department_id,
            entry__fund_id=entry.fund_id, entry__status=JournalEntry.POSTED,
            payable_party_key__iexact=line.payable_party_key,
            payable_claim_reference__iexact=line.payable_claim_reference).exclude(entry_id=entry.pk).exists()
        if identity in identities or duplicate:
            raise ValidationError("This payee's claim reference is already recognized in this fund. Link the original claim instead of recognizing it again.")
        identities.add(identity)
    for origin_id in origin_ids:
        origin = JournalLine.objects.get(pk=origin_id)
        daily = defaultdict(lambda: Decimal("0.00"))
        for applied in JournalLine.objects.filter(payable_origin_id=origin_id,
                entry__status=JournalEntry.POSTED).exclude(entry_id=entry.pk).select_related("entry"):
            daily[applied.entry.entry_date] += applied.debit - applied.credit
        for line in lines:
            if line.payable_origin_id == origin_id:
                daily[entry.entry_date] += line.debit - line.credit
        used = Decimal("0.00")
        for day, amount in sorted(daily.items()):
            used += amount
            if used < 0 or used > origin.credit:
                raise ValidationError(
                    f"Claim {origin.payable_claim_reference}: applications through {day} would use "
                    f"{used:,.2f} of its {origin.credit:,.2f} recognized amount. Correct the amount or linked claim.")
        _capacity(origin, [line for line in lines if line.payable_origin_id == origin_id])


def record_claim_subsidiaries(entry):
    for line in entry.lines.select_related("payable_origin"):
        origin = line.payable_origin if line.payable_origin_id else line
        if not origin.payable_claim_reference:
            continue
        if JournalSubsidiaryLine.objects.filter(journal_line=line).exists():
            # create_reversal already copied the immutable original detail.
            detail = line.subsidiary_posting
            if (detail.reference_key != origin.payable_party_key or detail.debit != line.debit
                    or detail.credit != line.credit or detail.category != JournalSubsidiaryLine.PAYABLE):
                raise ValidationError("Retained payable subsidiary detail differs from the linked claim.")
            continue
        detail = JournalSubsidiaryLine(entry=entry, journal_line=line, category=JournalSubsidiaryLine.PAYABLE,
            reference_key=origin.payable_party_key, reference_label=origin.payable_party_key,
            source_code="individual-claim", source_reference=entry.reference,
            debit=line.debit, credit=line.credit,
            source_snapshot={"claim_line": origin.pk, "claim_reference": origin.payable_claim_reference})
        detail.full_clean()
        detail.save()


def claim_rows(department_id, as_of_date):
    claims = JournalLine.objects.filter(entry__department_id=department_id,
        entry__status=JournalEntry.POSTED, entry__entry_date__lte=as_of_date,
        payable_origin__isnull=True, credit__gt=0).exclude(payable_claim_reference="").select_related("entry__fund", "account")
    amounts = defaultdict(lambda: Decimal("0.00"))
    for row in JournalLine.objects.filter(payable_origin__in=claims,
            entry__status=JournalEntry.POSTED, entry__entry_date__lte=as_of_date):
        amounts[row.payable_origin_id] += row.debit - row.credit
    return [{"line": line, "applied": amounts[line.pk], "outstanding": line.credit - amounts[line.pk]}
            for line in claims.order_by("entry__entry_date", "entry__reference", "sequence")]
