"""Individual payable claims and applications on the existing posted journal."""
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import Fund, JournalEntry, JournalLine, JournalSubsidiaryLine


def validate_claim_line(line):
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
        # posted applications. No cross-store reservation or second ledger.
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
