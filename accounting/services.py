from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AccountingAuditEvent, AccountingPeriod, JournalEntry, JournalLine


FINANCE_DB = "finance"


def actor_label(actor):
    return actor.get_full_name() or actor.username


def record_event(entry, action, actor, reason="", snapshot=None):
    return AccountingAuditEvent.objects.create(
        department_id=entry.department_id,
        department_label=entry.department_label,
        entry=entry,
        action=action,
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        reason=reason,
        snapshot=snapshot or {},
    )


def validate_entry_for_submission(entry):
    entry.full_clean()
    lines = list(entry.lines.select_related("account", "responsibility_center"))
    if len(lines) < 2:
        raise ValidationError("Add at least two journal lines before submitting.")
    for line in lines:
        line.full_clean()
    debit = sum((line.debit for line in lines), Decimal("0.00"))
    credit = sum((line.credit for line in lines), Decimal("0.00"))
    if debit <= 0 or debit != credit:
        raise ValidationError(f"The entry must balance before submission. Debits: {debit:,.2f}; credits: {credit:,.2f}.")
    if entry.period.status != AccountingPeriod.OPEN:
        raise ValidationError("The selected accounting period is closed.")
    return debit, credit


@transaction.atomic(using=FINANCE_DB)
def submit_entry(entry, actor):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.DRAFT:
        raise ValidationError("Only a draft journal can be submitted.")
    debit, credit = validate_entry_for_submission(locked)
    locked.status = JournalEntry.SUBMITTED
    locked.submitted_by_id = actor.pk
    locked.submitted_by_label = actor_label(actor)
    locked.submitted_at = timezone.now()
    locked.save(update_fields=("status", "submitted_by_id", "submitted_by_label", "submitted_at", "updated_at"))
    record_event(locked, "submitted", actor, snapshot={"debit": str(debit), "credit": str(credit)})
    return locked


@transaction.atomic(using=FINANCE_DB)
def post_entry(entry, actor):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.SUBMITTED:
        raise ValidationError("Only a submitted journal can be posted.")
    workflow_exemption = None
    if locked.created_by_id == actor.pk:
        from finance.exemptions import workflow_exemption_for, workflow_exemption_snapshot
        from finance.models import FinanceWorkflowExemption

        exemption = workflow_exemption_for(
            actor=actor,
            control_code=FinanceWorkflowExemption.JOURNAL_PREPARER_SELF_POSTING,
            department_id=locked.department_id,
        )
        if exemption is None:
            raise ValidationError(
                "Maker-checker control: the preparer cannot post the same journal entry unless an active "
                "administrator-authorized workflow exemption applies."
            )
        workflow_exemption = workflow_exemption_snapshot(exemption)
    debit, credit = validate_entry_for_submission(locked)
    locked.status = JournalEntry.POSTED
    locked.posted_by_id = actor.pk
    locked.posted_by_label = actor_label(actor)
    locked.posted_at = timezone.now()
    locked.save(update_fields=("status", "posted_by_id", "posted_by_label", "posted_at", "updated_at"))
    snapshot = {"debit": str(debit), "credit": str(credit)}
    if workflow_exemption:
        snapshot["workflow_exemption"] = workflow_exemption
    record_event(locked, "posted", actor, snapshot=snapshot)
    return locked


@transaction.atomic(using=FINANCE_DB)
def return_entry(entry, actor, reason):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.SUBMITTED:
        raise ValidationError("Only a submitted journal can be returned.")
    if not reason.strip():
        raise ValidationError("Explain what the preparer needs to correct.")
    locked.status = JournalEntry.DRAFT
    locked.submitted_by_id = None
    locked.submitted_by_label = ""
    locked.submitted_at = None
    locked.save(update_fields=("status", "submitted_by_id", "submitted_by_label", "submitted_at", "updated_at"))
    record_event(locked, "returned", actor, reason=reason.strip())
    return locked


@transaction.atomic(using=FINANCE_DB)
def discard_draft(entry, actor, reason=""):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.DRAFT:
        raise ValidationError("Only a draft journal can be discarded.")
    locked.status = JournalEntry.VOIDED
    locked.save(update_fields=("status", "updated_at"))
    record_event(locked, "draft_discarded", actor, reason=reason.strip())
    return locked


@transaction.atomic(using=FINANCE_DB)
def create_reversal(entry, actor, *, reference, entry_date, period, reason):
    """Prepare, but do not post, an exact reversing journal with immutable lineage."""
    locked = JournalEntry.objects.select_for_update().select_related("fund").get(pk=entry.pk)
    if locked.status != JournalEntry.POSTED:
        raise ValidationError("Only a posted journal can be reversed.")
    active_reversals = JournalEntry.objects.filter(reversal_of=locked).exclude(status=JournalEntry.VOIDED)
    if active_reversals.exists():
        raise ValidationError("A reversing journal has already been prepared for this entry.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Explain why this reversal is required.")
    if period.department_id != locked.department_id or period.status != AccountingPeriod.OPEN:
        raise ValidationError("Choose an open accounting period for the same department ledger.")
    if not (period.starts_on <= entry_date <= period.ends_on):
        raise ValidationError("The reversal date must fall inside the selected accounting period.")

    attempt_number = JournalEntry.objects.filter(reversal_of=locked).count() + 1
    reversal = JournalEntry(
        department_id=locked.department_id,
        department_label=locked.department_label,
        reference=reference.strip(),
        entry_date=entry_date,
        period=period,
        fund=locked.fund,
        source_type="reversal",
        source_reference=f"{locked.public_id}:{attempt_number}",
        source_snapshot={
            "original_entry": str(locked.public_id),
            "original_reference": locked.reference,
            "original_posted_at": locked.posted_at.isoformat() if locked.posted_at else None,
        },
        reversal_of=locked,
        reversal_reason=reason,
        description=f"Reversal of {locked.reference}: {reason}",
        created_by_id=actor.pk,
        created_by_label=actor_label(actor),
    )
    reversal.full_clean()
    reversal.save()
    for line in locked.lines.select_related("account", "responsibility_center").order_by("sequence", "pk"):
        reversed_line = JournalLine(
            entry=reversal,
            sequence=line.sequence,
            account=line.account,
            responsibility_center=line.responsibility_center,
            debit=line.credit,
            credit=line.debit,
            memo=f"Reversal: {line.memo}"[:255],
        )
        reversed_line.full_clean()
        reversed_line.save()
    record_event(
        locked, "reversal_prepared", actor, reason=reason,
        snapshot={"reversal_entry": str(reversal.public_id), "reversal_reference": reversal.reference},
    )
    record_event(
        reversal, "prepared_from_reversal", actor, reason=reason,
        snapshot={"original_entry": str(locked.public_id), "original_reference": locked.reference},
    )
    return reversal


@transaction.atomic(using=FINANCE_DB)
def close_period(period, actor):
    locked = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if locked.status != AccountingPeriod.OPEN:
        raise ValidationError("This accounting period is already closed.")
    unposted = locked.journal_entries.exclude(status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).count()
    if unposted:
        raise ValidationError(f"Close or discard {unposted} unposted journal entry/entries before closing this period.")
    locked.status = AccountingPeriod.CLOSED
    locked.closed_by_id = actor.pk
    locked.closed_by_label = actor_label(actor)
    locked.closed_at = timezone.now()
    locked.save(update_fields=("status", "closed_by_id", "closed_by_label", "closed_at"))
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id,
        department_label=locked.department_label,
        action="period_closed",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={"fiscal_year": locked.fiscal_year, "period_number": locked.period_number},
    )
    return locked
