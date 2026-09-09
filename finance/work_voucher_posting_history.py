"""Read-only personal history for verified Accounting-to-voucher synchronization."""
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.urls import reverse


def _uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def completed_voucher_posting_tasks(user, department, today):
    from accounting.models import AccountingAuditEvent, JournalEntry, JournalLine
    from accounting.posted_evidence import verify_source_link
    from vouchers.access import can_view_workbench
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import VoucherCase, VoucherEvent, VoucherPostingRequest
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_workbench(user):
        return []
    specs = {f"{kind}_jev_posted": (kind, VoucherCase.ACCOUNTING_EVENT_POSTING)
             for kind, _label in VoucherPostingRequest.KIND_CHOICES}
    specs["grand_jev_posted"] = (VoucherPostingRequest.RECOGNITION, VoucherCase.ACCOUNTING_POSTING)
    events = list(VoucherEvent.objects.filter(
        actor_id=user.pk, case__in=visible_cases_for_user(user), action__in=specs,
    ).select_related("case", "actor_department"))
    request_ids = {_uuid(event.metadata.get("posting_request")) for event in events
                   if isinstance(event.metadata, dict)} - {None}
    requests = {row.public_id: row for row in VoucherPostingRequest.objects.filter(
        public_id__in=request_ids, status=VoucherPostingRequest.POSTED,
    ).select_related("case")}
    entries = {row.public_id: row for row in JournalEntry.objects.filter(
        public_id__in={row.accounting_entry_public_id for row in requests.values()} - {None},
        status=JournalEntry.POSTED,
    )}
    entry_ids = {row.pk for row in entries.values()}
    posting_events = {}
    for event in AccountingAuditEvent.objects.filter(entry_id__in=entry_ids, action="posted").order_by("-created_at", "-pk"):
        posting_events.setdefault(event.entry_id, event)
    totals = {row["entry_id"]: (row["debit"], row["credit"]) for row in JournalLine.objects.filter(
        entry_id__in=entry_ids,
    ).values("entry_id").annotate(debit=Sum("debit"), credit=Sum("credit"))}
    tasks = []
    for event in events:
        meta = event.metadata
        if not isinstance(meta, dict):
            continue
        request = requests.get(_uuid(meta.get("posting_request")))
        if request is None:
            continue
        entry = entries.get(_uuid(meta.get("accounting_entry")))
        kind, before = specs[event.action]
        destination = request.resume_stage or (VoucherCase.TREASURY_CHECK_PREPARATION if event.action == "grand_jev_posted" else "")
        if (
            entry is None or request.case_id != event.case_id or request.kind != kind
            or event.actor_department_id != request.finance_department_id
            or event.from_stage != before or not destination or event.to_stage != destination
            or meta.get("posting_event", kind) != kind or meta.get("resume_stage", destination) != destination
            or meta.get("jev_number") != entry.reference
            or request.accounting_entry_public_id != entry.public_id
            or not request.posted_at or not entry.posted_at or not entry.posted_by_id
            or entry.posted_at > event.created_at
            or not all(isinstance(value, dict) for value in (request.payload, request.posting_rule_snapshot, entry.source_snapshot))
        ):
            continue
        posting_event = posting_events.get(entry.pk)
        amounts = totals.get(entry.pk, (Decimal("0.00"), Decimal("0.00")))
        try:
            recorded = (Decimal(posting_event.snapshot["debit"]), Decimal(posting_event.snapshot["credit"])) if posting_event else None
            if (recorded is None or not all(value.is_finite() for value in recorded)
                    or posting_event.actor_id != entry.posted_by_id or posting_event.department_id != entry.department_id
                    or amounts[0] <= 0 or amounts[0] != amounts[1] or recorded != amounts):
                continue
            verify_source_link(request, entry, source_type="voucher")
        except (ValidationError, InvalidOperation, KeyError, TypeError, ValueError):
            continue
        item = event.case
        event_id = _source_record_identity("voucher-posting-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
            "metadata": meta, "from_stage": event.from_stage, "to_stage": event.to_stage,
            "source_id": str(item.public_id), "current_stage": item.current_stage,
            "request_id": str(request.public_id), "request_version": request.version,
            "payload_checksum": request.payload_checksum, "rule_checksum": request.posting_rule_checksum,
            "entry_id": str(entry.public_id), "posted_by_id": entry.posted_by_id,
            "posted_at": entry.posted_at.isoformat(), "posting_event_id": posting_event.pk,
            "totals": [str(value) for value in amounts],
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:voucher-posting-event:{event_id}:completed",
            task_type=f"finance.voucher-posting.{event.action}.completed.v1", area="Voucher case",
            case_id=f"voucher-case:{item.public_id}", reference=f"{item.reference_code} - {request.get_kind_display()} v{request.version}",
            subject=f"Synchronized posted JEV {entry.reference} with voucher",
            transaction_type="Recorded posting handoff", action="View source voucher",
            gate="The retained voucher request and posted Accounting evidence match. This credits source synchronization, not the original JEV posting.",
            owner_queue=f"Recorded synchronizer: {user.get_username()}; office: {event.actor_department.name}",
            scope=f"Current voucher read access; retained Accounting office: {request.finance_department_label}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained synchronization event; the JEV date is not a deadline.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_current_stage_display(),
            source_version=f"event-sha256:{revision}", exception="Current case state remains separate from this completed handoff.",
            url=reverse("vouchers:case_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks
