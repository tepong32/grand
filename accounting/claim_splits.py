"""Exact invoice allocations over an unchanged historical liability line.

This is the calculation boundary, not an authorization or persistence API.
The attribution workflow must separately lock and verify the posted journals,
office/fund/payee scope, complete reversal lineage and independent approval.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
LIMIT = Decimal("10000000000000000")


def _amount(value):
    try:
        if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
            raise ValueError
        amount = Decimal(value)
        if not amount.is_finite() or not ZERO <= amount < LIMIT or amount != amount.quantize(CENT):
            raise ValueError
        return amount.quantize(CENT)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Enter each invoice share in exact, nonnegative centavos.")


def normalize_allocations(source, applications, rows):
    """Return canonical JSON rows after credit, payment and dated checks.

    Each row has a stable UUID key, payee, invoice reference, recognized amount
    and a map of historical JournalLine IDs to positive allocated amounts.
    Every supplied application is allocated in full; zero shares are omitted.
    Nothing here writes a journal, subsidiary, approval or reservation.
    """
    return _normalize_allocations(source, applications, rows, minimum_invoices=2)


def _normalize_allocations(source, applications, rows, *, minimum_invoices):
    """Shared arithmetic; the public single-credit contract still needs two rows."""
    if not isinstance(rows, list) or len(rows) < minimum_invoices:
        message = ("Allocate the consolidated credit to at least two invoices." if minimum_invoices == 2
            else "Identify at least one invoice for each original credit.")
        raise ValidationError(message)
    applications = list(applications)
    lines = {str(line.pk): line for line in applications}
    if len(lines) != len(applications) or str(source.pk) in lines:
        raise ValidationError("Select each historical application once, separately from its source credit.")
    credit = _amount(source.credit)
    if not credit or _amount(source.debit):
        raise ValidationError("Allocate an original liability credit.")
    for line in applications:
        if (line.entry.entry_date < source.entry.entry_date
                or bool(_amount(line.debit)) == bool(_amount(line.credit))):
            raise ValidationError("Historical applications must have one financial side and follow recognition.")

    normalized, keys, identities = [], set(), set()
    totals = defaultdict(lambda: ZERO)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"key", "party_key", "claim_reference", "recognized", "applications"}:
            raise ValidationError("Record the invoice identity, recognized amount and application shares.")
        try:
            key = str(UUID(str(row["key"])))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("An invoice allocation has an invalid identity. Reload the allocation form.")
        party, claim = row["party_key"], row["claim_reference"]
        if any(not isinstance(value, str) or not value or value != value.strip()
               or len(value) > limit for value, limit in ((party, 100), (claim, 120))):
            raise ValidationError("Record the exact payee and invoice reference without surrounding spaces.")
        identity = (party.casefold(), claim.casefold())
        if key in keys or identity in identities:
            raise ValidationError("Allocate each invoice once with its own identity.")
        keys.add(key)
        identities.add(identity)
        recognized = _amount(row["recognized"])
        if not recognized:
            raise ValidationError("Each invoice must have a positive recognized amount.")
        allocations = row["applications"]
        if not isinstance(allocations, dict) or any(pk not in lines for pk in allocations):
            raise ValidationError("Allocate only the selected historical application lines, using their retained IDs.")
        shares = {}
        daily = defaultdict(lambda: ZERO)
        for pk, value in allocations.items():
            share = _amount(value)
            if not share:
                raise ValidationError("Omit zero application shares.")
            line = lines[pk]
            shares[pk] = share
            totals[pk] += share
            daily[line.entry.entry_date] += share if line.debit else -share
        used = ZERO
        for day, movement in sorted(daily.items()):
            used += movement
            if used < ZERO or used > recognized:
                raise ValidationError(f"Invoice {claim} exceeds its dated capacity on {day}.")
        normalized.append({"key": key, "party_key": party, "claim_reference": claim,
            "recognized": str(recognized),
            "applications": {pk: str(shares[pk]) for pk in sorted(shares, key=int)}})

    if sum((_amount(row["recognized"]) for row in normalized), ZERO) != credit:
        raise ValidationError("Invoice recognized amounts must equal the original liability credit exactly.")
    for pk, line in lines.items():
        if totals[pk] != _amount(line.debit or line.credit):
            raise ValidationError("Invoice shares must allocate every historical application in full.")

    # A reversal cannot shift a restored balance to a different invoice, even
    # when the journal and all current invoice balances otherwise reconcile.
    origins = {(line.entry_id, line.sequence): line for line in [source, *applications]}
    for pk, line in lines.items():
        if not line.entry.reversal_of_id:
            if line.credit:
                raise ValidationError("Restoring credits require the original historical application reversal.")
            continue
        prior = origins.get((line.entry.reversal_of_id, line.sequence))
        if (prior is None or prior.account_id != line.account_id
                or line.entry.entry_date < prior.entry.entry_date
                or prior.debit != line.credit or prior.credit != line.debit):
            raise ValidationError("Include the exact original line for every historical reversal.")
        for row in normalized:
            expected = row["recognized"] if prior.pk == source.pk else row["applications"].get(str(prior.pk), "0.00")
            if _amount(row["applications"].get(pk, "0.00")) != _amount(expected):
                raise ValidationError("A historical reversal must retain each original invoice share exactly.")
    return sorted(normalized, key=lambda row: row["key"])


def _shares(record, shares):
    from .claim_attributions import allocation_rows
    known = {row["key"] for row in allocation_rows(record)}
    if not isinstance(shares, dict) or not shares or set(shares) - known:
        raise ValidationError("Allocate the application to invoices in its approved original credit.")
    normalized = {key: str(_amount(value)) for key, value in shares.items()}
    if any(Decimal(value) <= ZERO for value in normalized.values()):
        raise ValidationError("Use positive invoice shares and omit unused invoices.")
    return dict(sorted(normalized.items()))


def bind_allocation(source, shares, *, expected_attribution=None):
    """Capture a draft application's approved invoice identities and shares."""
    from .claim_attributions import current, attribution_evidence
    record = current(source)
    if record is None or not record.is_split:
        raise ValidationError("Select an approved consolidated credit with individual invoices.")
    if expected_attribution is not None and record.pk != expected_attribution:
        raise ValidationError("The approved invoice schedule changed. Reload and select the invoice again.")
    return {"attribution": attribution_evidence(record), "shares": _shares(record, shares)}


def retained_allocation(line, source, record, *, check_posting=True):
    """Verify a native line against its pinned and currently compatible approval."""
    from .claim_attributions import Attribution, allocation_rows, attribution_evidence, verify
    evidence = line.payable_allocation
    if (not isinstance(evidence, dict) or set(evidence) != {"attribution", "shares"}
            or not isinstance(evidence["attribution"], dict) or line.payable_origin_id != source.pk):
        raise ValidationError("Retain the application's approved invoice allocation evidence.")
    try:
        selected = Attribution.objects.get(source_id=source.pk, public_id=evidence["attribution"].get("public_id"))
    except (Attribution.DoesNotExist, ValidationError, ValueError, TypeError):
        raise ValidationError("The application's original invoice approval cannot be found.")
    verify(selected)
    if (not selected.is_split or attribution_evidence(selected) != evidence["attribution"]
            or allocation_rows(selected) != allocation_rows(record)):
        raise ValidationError("The application's invoice identities differ from their retained approval.")
    shares = _shares(record, evidence["shares"])
    if shares != evidence["shares"] or sum((Decimal(value) for value in shares.values()), ZERO) != (line.debit or line.credit):
        raise ValidationError("Invoice shares must equal the financial line amount exactly.")
    if check_posting and line.entry.status == "posted":
        events = list(line.entry.audit_events.filter(action="posted"))
        if (len(events) != 1 or events[0].actor_id != line.entry.posted_by_id
                or events[0].snapshot.get("invoice_allocations", {}).get(str(line.pk)) != posting_evidence(line)):
            raise ValidationError("The invoice application differs from its independent posting evidence.")
    return shares


def posting_evidence(line):
    return {"source": line.payable_origin_id, "allocation": line.payable_allocation,
        "debit": str(line.debit), "credit": str(line.credit)}


def effective_shares(line, source, record):
    from .claim_attributions import allocation_rows
    from .shared_claim_applications import is_shared, validate
    if is_shared(line):
        members = validate(line)
        if source.pk not in members or members[source.pk][1].pk != record.pk:
            raise ValidationError("The shared application differs from the selected source approval.")
        return members[source.pk][2]
    if line.pk == source.pk:
        return {row["key"]: row["recognized"] for row in allocation_rows(record)}
    if line.payable_origin_id:
        return retained_allocation(line, source, record)
    if line.pk not in record.applications:
        raise ValidationError("The historical application is not included in this invoice approval.")
    return {row["key"]: row["applications"][str(line.pk)] for row in allocation_rows(record)
        if str(line.pk) in row["applications"]}


def reversal_allocation(line):
    from .claim_attributions import application_origin, current, attribution_evidence
    source = application_origin(line) or line
    record = current(source)
    if record is None or not record.is_split:
        return {}
    shares = effective_shares(line, source, record)
    # A native line's reversal retains the original approval as well as shares.
    return line.payable_allocation if line.payable_allocation else {
        "attribution": attribution_evidence(record), "shares": shares}


def validate_application(line, source, record):
    shares = retained_allocation(line, source, record)
    if line.entry.reversal_of_id:
        prior = line.entry.reversal_of.lines.filter(sequence=line.sequence).first()
        if (prior is None or prior.account_id != line.account_id or prior.debit != line.credit
                or prior.credit != line.debit or line.entry.entry_date < prior.entry.entry_date
                or prior.payable_reservation_id != line.payable_reservation_id
                or effective_shares(prior, source, record) != shares):
            raise ValidationError("Reverse the original financial line with exactly its original invoice shares.")
    elif line.credit:
        raise ValidationError("Restore invoice capacity only through an exact posted financial reversal.")


def validate_capacity(source, record, candidates=()):
    """Check each invoice's chronology while the caller holds its source lock."""
    from .claim_attributions import allocation_rows, application_lines
    from .models import JournalEntry
    candidates = list(candidates)
    from .shared_claim_applications import native_lines
    posted = native_lines(source, exclude_entries={line.entry_id for line in candidates})
    daily = defaultdict(lambda: defaultdict(lambda: ZERO))
    for line in [*application_lines(source, record=record), *posted, *candidates]:
        for key, value in effective_shares(line, source, record).items():
            daily[key][line.entry.entry_date] += Decimal(value) * (1 if line.debit else -1)
    for row in allocation_rows(record):
        used = ZERO
        for day, movement in sorted(daily[row["key"]].items()):
            used += movement
            if used < ZERO or used > Decimal(row["recognized"]):
                raise ValidationError(f"Invoice {row['claim_reference']} exceeds its dated capacity on {day}.")
        from .payables import _capacity
        _capacity(source, candidates, invoice_key=row["key"])
