"""Read-only observations of GRAND recognition sources; never an allocation."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError

from accounting.access import can_view_ledger, department_for_user
from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from vouchers.case_exports import visible_cases_for_user


def can_inspect_journals(actor, case):
    department = department_for_user(actor)
    return bool(department and can_view_ledger(actor)
                and department.pk == case.configuration_release.department_id)


def inspect_recognition(source, *, actor):
    """Caller must scope the case and require its owner's explicit ledger grant.

    This is a live observation across two stores, not a transactional guarantee
    or retained approval basis. Do not consume its results as allocation authority.
    """
    if (not can_inspect_journals(actor, source.case)
            or source.finance_department_id != source.case.configuration_release.department_id
            or not visible_cases_for_user(actor).filter(pk=source.case_id).exists()):
        raise PermissionDenied
    try:
        if source.kind != "recognition" or source.status != "posted" or not source.accounting_entry_public_id:
            raise ValidationError("Recognition has no bound posted journal yet.")
        entry = JournalEntry.objects.select_related("period", "fund").filter(
            public_id=source.accounting_entry_public_id,
            department_id=source.finance_department_id).first()
        if entry is None:
            raise ValidationError("The bound journal is unavailable in the source ledger.")
        verify_source_link(source, entry, source_type="voucher")
        if entry.status != JournalEntry.POSTED or not entry.posted_at or not entry.posted_by_id:
            raise ValidationError("The bound journal does not retain posted attribution.")
        if entry.reversal_of_id or entry.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
            raise ValidationError("This journal has reversal activity; Accounting review is required.")
        lines = list(entry.lines.select_related("account", "responsibility_center").order_by("sequence"))
        if (entry.period.department_id != entry.department_id or entry.fund.department_id != entry.department_id
                or any(line.account.department_id != entry.department_id or
                       (line.responsibility_center_id and line.responsibility_center.department_id != entry.department_id)
                       for line in lines)):
            raise ValidationError("Journal dimensions do not share the source ledger owner.")
        debit = sum((line.debit for line in lines), Decimal("0"))
        credit = sum((line.credit for line in lines), Decimal("0"))
        event = entry.audit_events.filter(action="posted").first()
        try:
            recorded = (Decimal(event.snapshot["debit"]), Decimal(event.snapshot["credit"])) if event else None
        except (InvalidOperation, KeyError, TypeError, ValueError):
            recorded = None
        # Same persisted evidence checks as GRAND's posting handoff, without
        # demanding write/post authority from a ledger reader.
        if (not event or event.actor_id != entry.posted_by_id or event.department_id != entry.department_id
                or not recorded or not all(value.is_finite() for value in recorded)
                or debit <= 0 or debit != credit or recorded != (debit, credit)
                or any(line.debit < 0 or line.credit < 0 or bool(line.debit) == bool(line.credit) for line in lines)):
            raise ValidationError("Stored posting evidence and journal totals do not agree.")
        return {"entry": entry, "lines": [line for line in lines if line.debit > 0], "issue": ""}
    except ValidationError as exc:
        return {"entry": None, "lines": [], "issue": " ".join(exc.messages)}
