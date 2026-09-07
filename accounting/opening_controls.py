"""Read-only opening evidence used by work projections and transition guards."""
import hashlib
import json
from decimal import Decimal

from .models import AccountingPeriod, FiscalYear, JournalEntry, OpeningBalanceRow


def opening_evidence(batch):
    rows = list(batch.rows.select_related("fund", "account", "responsibility_center").order_by("row_number", "pk"))
    row_values = []
    errors = []
    debit = sum((row.debit for row in rows), Decimal("0.00"))
    credit = sum((row.credit for row in rows), Decimal("0.00"))
    if len(rows) != batch.expected_row_count or debit != batch.expected_debit or credit != batch.expected_credit or debit != credit:
        errors.append("Opening row/count/debit/credit controls must have exactly zero difference.")
    if batch.is_zero_balance_declaration:
        if rows or batch.expected_row_count or batch.expected_debit or batch.expected_credit:
            errors.append("A zero-balance declaration must contain only zero controls and no rows.")
    elif not rows or not batch.source_checksum:
        errors.append("Stage the retained source schedule before continuing.")
    funds = {}
    for row in rows:
        row_values.append({
            "id": row.pk, "number": row.row_number, "version": row.correction_version,
            "raw": [row.raw_fund_code, row.raw_account_code, row.raw_responsibility_center_code, row.raw_debit, row.raw_credit],
            "resolved": [row.fund_id, row.account_id, row.responsibility_center_id, str(row.debit), str(row.credit)],
            "detail": [row.subsidiary_reference, row.memo], "status": row.validation_status,
            "errors": row.validation_errors,
        })
        if row.validation_status != OpeningBalanceRow.VALID or not row.fund_id or not row.account_id:
            errors.append("Resolve every invalid or unmapped opening row.")
        elif (row.fund.department_id != batch.department_id or row.account.department_id != batch.department_id
              or not row.fund.is_active or not row.account.is_active or not row.account.allow_posting):
            errors.append("Opening classifications must remain active and belong to the current ledger.")
        if row.responsibility_center_id and (row.responsibility_center.department_id != batch.department_id or not row.responsibility_center.is_active):
            errors.append("Opening responsibility centers must remain active in the current ledger.")
        if (row.debit > 0) == (row.credit > 0) or row.debit < 0 or row.credit < 0:
            errors.append("Each opening row requires exactly one positive debit or credit.")
        totals = funds.setdefault(row.fund_id, [Decimal("0.00"), Decimal("0.00")])
        totals[0] += row.debit
        totals[1] += row.credit
    if any(dr != cr for dr, cr in funds.values()):
        errors.append("Each opening fund must balance exactly.")
    values = {
        "batch": str(batch.public_id), "title": batch.title, "department": batch.department_id,
        "year": batch.fiscal_year_id, "period": batch.period_id,
        "source": [batch.source_reference, batch.source_filename, batch.source_checksum, batch.import_schema_version],
        "controls": [batch.expected_row_count, str(batch.expected_debit), str(batch.expected_credit), batch.is_zero_balance_declaration],
        "rows": row_values,
    }
    checksum = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return values, checksum, list(dict.fromkeys(errors))


def opening_transition_errors(batch):
    _, checksum, errors = opening_evidence(batch)
    summary = batch.validation_summary or {}
    if not summary.get("valid") or summary.get("evidence_checksum") != checksum:
        errors.append("Opening validation evidence is missing or changed; return for revalidation.")
    if batch.period.status != AccountingPeriod.OPEN:
        errors.append("The opening accounting period is closed.")
    if batch.status == batch.APPROVED and batch.fiscal_year.status not in (FiscalYear.APPROVED, FiscalYear.ACTIVE):
        errors.append("Approve the fiscal-year definition before posting.")
    if batch.status in (batch.VALIDATED, batch.FOR_REVIEW, batch.APPROVED):
        action = {batch.VALIDATED: "validated", batch.FOR_REVIEW: "submitted", batch.APPROVED: batch.APPROVED}[batch.status]
        event = batch.events.filter(action=action).first()
        if event is None or event.snapshot != summary:
            errors.append("Retained opening validation/submission/approval evidence does not reproduce the current validation.")
    return list(dict.fromkeys(errors))


def opening_posting_errors(batch):
    """Reconciliation must prove retained source-to-line identity, not totals alone."""
    errors = []
    approval = batch.events.filter(action=batch.APPROVED).first()
    if approval is None or approval.snapshot != batch.validation_summary or approval.actor_id != batch.approved_by_id:
        errors.append("Retained opening approval evidence does not reproduce the posted source.")
    postings = list(batch.postings.select_related("entry"))
    source_rows = list(batch.rows.order_by("row_number", "pk"))
    expected_funds = {row.fund_id for row in source_rows}
    if {p.fund_id for p in postings} != expected_funds:
        errors.append("Opening posting fund lineage does not match the source schedule.")
    for posting in postings:
        entry = posting.entry
        rows = [row for row in source_rows if row.fund_id == posting.fund_id]
        lines = list(entry.lines.order_by("sequence", "pk"))
        expected = [(r.account_id, r.responsibility_center_id, r.debit, r.credit) for r in rows]
        actual = [(r.account_id, r.responsibility_center_id, r.debit, r.credit) for r in lines]
        debit, credit = entry.totals
        if (entry.status != JournalEntry.POSTED or entry.department_id != batch.department_id
                or entry.period_id != batch.period_id or entry.fund_id != posting.fund_id
                or entry.source_snapshot.get("opening_batch") != str(batch.public_id)
                or expected != actual or posting.row_count != len(rows)
                or posting.debit != debit or posting.credit != credit):
            errors.append("Posted opening lines or retained lineage differ from the approved source.")
    return list(dict.fromkeys(errors))
