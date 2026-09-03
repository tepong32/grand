from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, DecimalField, Exists, F, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import can_view_ledger, department_for_user
from .models import AccountingAuditEvent, AccountingPeriod, Fund, JournalEntry


ATTENTION_CHOICES = (
    ("needs_lines", "Draft needs journal lines"),
    ("needs_balance", "Draft debit and credit differ"),
    ("returned_correction", "Returned to preparer"),
    ("for_posting", "Waiting for independent posting"),
    ("posted", "Posted to the ledgers"),
    ("correction_lineage", "Has reversal or replacement lineage"),
    ("discarded", "Discarded draft retained"),
)

JOURNAL_REGISTER_COLUMNS = (
    "jev_reference", "entry_public_id", "entry_date", "period", "period_status", "fund_code",
    "source_type", "source_reference", "description", "status", "next_action", "line_count",
    "total_debit", "total_credit", "difference", "balanced", "posting_event",
    "posting_rule_checksum", "source_payload_checksum", "source_snapshot_checksum",
    "reversal_of", "active_reversal_or_replacement", "reversal_reason", "subsidiary_rows",
    "prepared_by", "prepared_at", "submitted_by", "submitted_at", "posted_by", "posted_at",
    "last_event", "last_event_reason", "last_event_at", "updated_at",
)


def _money_output():
    return DecimalField(max_digits=18, decimal_places=2)


def journal_controls(queryset):
    returned_events = AccountingAuditEvent.objects.filter(entry=OuterRef("pk"), action="returned")
    active_reversals = JournalEntry.objects.filter(reversal_of=OuterRef("pk")).exclude(status=JournalEntry.VOIDED)
    return queryset.annotate(
        control_line_count=Count("lines"),
        control_total_debit=Coalesce(Sum("lines__debit"), Value(Decimal("0.00")), output_field=_money_output()),
        control_total_credit=Coalesce(Sum("lines__credit"), Value(Decimal("0.00")), output_field=_money_output()),
        control_was_returned=Exists(returned_events),
        control_has_active_reversal=Exists(active_reversals),
    )


def apply_journal_filters(
    queryset, *, status="", source_type="", period="", fund="", attention="", search="",
):
    queryset = journal_controls(queryset)
    if status in dict(JournalEntry.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    elif status:
        queryset = queryset.none()
    else:
        status = ""

    if source_type in dict(JournalEntry.SOURCE_CHOICES):
        queryset = queryset.filter(source_type=source_type)
    elif source_type:
        queryset = queryset.none()
    else:
        source_type = ""

    department_ids = queryset.values("department_id")
    if period:
        if period.isdigit() and AccountingPeriod.objects.filter(
            pk=period, department_id__in=department_ids,
        ).exists():
            queryset = queryset.filter(period_id=period)
        else:
            queryset = queryset.none()
    if fund:
        if fund.isdigit() and Fund.objects.filter(
            pk=fund, department_id__in=department_ids,
        ).exists():
            queryset = queryset.filter(fund_id=fund)
        else:
            queryset = queryset.none()

    if attention == "needs_lines":
        queryset = queryset.filter(status=JournalEntry.DRAFT, control_line_count=0)
    elif attention == "needs_balance":
        queryset = queryset.filter(status=JournalEntry.DRAFT, control_line_count__gt=0).exclude(
            control_total_debit=F("control_total_credit"),
        )
    elif attention == "returned_correction":
        queryset = queryset.filter(status=JournalEntry.DRAFT, control_was_returned=True)
    elif attention == "for_posting":
        queryset = queryset.filter(status=JournalEntry.SUBMITTED)
    elif attention == "posted":
        queryset = queryset.filter(status=JournalEntry.POSTED)
    elif attention == "correction_lineage":
        queryset = queryset.filter(Q(reversal_of__isnull=False) | Q(control_has_active_reversal=True))
    elif attention == "discarded":
        queryset = queryset.filter(status=JournalEntry.VOIDED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""

    search = (search or "").strip()[:160]
    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search) | Q(description__icontains=search)
            | Q(source_reference__icontains=search),
        )
    return queryset, status, source_type, period, fund, attention, search


def next_journal_action(entry):
    if entry.status == JournalEntry.DRAFT:
        if entry.control_line_count == 0:
            return "Add the supported debit and credit lines"
        if entry.control_total_debit != entry.control_total_credit:
            return "Correct the lines until total debit and credit agree"
        if entry.control_was_returned:
            return "Resolve the review reason, then resubmit the same draft"
        if entry.period.status != AccountingPeriod.OPEN:
            return "Use the governed correction route in an allowed open period"
        return "Review the evidence and submit for independent posting"
    if entry.status == JournalEntry.SUBMITTED:
        return "Independent poster reviews, then posts or returns with a reason"
    if entry.status == JournalEntry.VOIDED:
        return "Retain this discarded draft; use its governed successor if work remains"
    if entry.reversal_of_id:
        return "Retain as the correcting entry linked to the original posted JEV"
    if entry.control_has_active_reversal:
        return "Review the linked correcting JEV; never rewrite this posted entry"
    return "Posted to the ledgers; correct only through a governed reversal or adjustment"


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _currency(value):
    return Decimal(value).quantize(Decimal("0.01"))


def _snapshot_checksum(snapshot):
    payload = json.dumps(snapshot or {}, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_journal_control_register(
    *, actor, queryset, status="", source_type="", period="", fund="", attention="", search="",
):
    department = department_for_user(actor)
    if department is None or not can_view_ledger(actor):
        raise PermissionDenied
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The journal register may contain only the acting Accounting department.")

    entries = list(queryset.select_related("period", "fund", "reversal_of").prefetch_related(
        "audit_events", "reversal_entries", "subsidiary_lines",
    ))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(JOURNAL_REGISTER_COLUMNS)
    for entry in entries:
        events = list(entry.audit_events.all())
        last_event = events[0] if events else None
        successors = [item.reference for item in entry.reversal_entries.all() if item.status != JournalEntry.VOIDED]
        snapshot = entry.source_snapshot or {}
        difference = entry.control_total_debit - entry.control_total_credit
        writer.writerow(tuple(_csv_safe(value) for value in (
            entry.reference, entry.public_id, entry.entry_date, str(entry.period), entry.period.get_status_display(),
            entry.fund.code, entry.get_source_type_display(), entry.source_reference, entry.description,
            entry.get_status_display(), next_journal_action(entry), entry.control_line_count,
            _currency(entry.control_total_debit), _currency(entry.control_total_credit), _currency(difference),
            entry.control_total_debit == entry.control_total_credit and entry.control_line_count > 0,
            snapshot.get("posting_event", ""), snapshot.get("posting_rule_checksum", ""),
            snapshot.get("payload_checksum", snapshot.get("source_checksum", "")), _snapshot_checksum(snapshot),
            entry.reversal_of.reference if entry.reversal_of_id else "", " | ".join(successors),
            entry.reversal_reason, len(entry.subsidiary_lines.all()), entry.created_by_label,
            entry.created_at.isoformat(), entry.submitted_by_label,
            entry.submitted_at.isoformat() if entry.submitted_at else "", entry.posted_by_label,
            entry.posted_at.isoformat() if entry.posted_at else "", last_event.action if last_event else "",
            last_event.reason if last_event else "", last_event.created_at.isoformat() if last_event else "",
            entry.updated_at.isoformat(),
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        attention, status, source_type, f"period-{period}" if period else "",
        f"fund-{fund}" if fund else "", search,
    ) if value) or "all-visible"
    filename = f"finance-journal-control-register-{suffix}.csv"
    metadata = {
        "kind": "finance_journal_control_register", "status_filter": status or "all",
        "source_type_filter": source_type or "all", "period_filter": period or "all",
        "fund_filter": fund or "all", "attention_filter": attention or "all",
        "search_filter": search, "journal_count": len(entries),
        "authority_boundary": (
            "Operational Accounting control evidence only; this register is not a wet signature, "
            "period-close approval, or proof that a COA/local schedule or form has been accepted."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-journal-control-register", filename=filename, metadata=metadata,
    )
    AccountingAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name, action="journal_register_exported",
        actor_id=actor.pk, actor_label=actor.get_full_name() or actor.username,
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
