"""Coherent ledger evidence for native Budget preparation, never certification.

One Finance SELECT captures headers, lines, current account/office metadata and
subsidiaries. No lazy ORM access is allowed while assembling the returned cohort.
Read the whole posted fund once so reversal ancestors need no later database read.
Only the requested period and its retained reversal ancestors enter the fingerprint.
"""
import json
from collections import Counter
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import FilteredRelation, Q
from django.utils import timezone

from .access import department_for_user
from .budget_actuals import permitted
from .cash_classifications import checksum
from .models import Fund, JournalEntry


FUND_FIELDS = ("id", "public_id", "department_id", "code", "name")
ENTRY_FIELDS = ("id", "public_id", "department_id", "reference", "entry_date",
    "period_id", "source_type", "description", "source_reference", "source_snapshot",
    "reversal_of_id", "reversal_reason", "posted_at", "posted_by_id", "posted_by_label")
LINE_FIELDS = ("id", "sequence", "account_id", "responsibility_center_id", "debit", "credit",
    "memo", "cash_flow_category", "payable_origin_id", "payable_allocation",
    "payable_reservation_id", "payable_party_key", "payable_claim_reference")
ACCOUNT_FIELDS = ("id", "department_id", "code", "title", "account_type", "normal_balance")
CENTER_FIELDS = ("id", "department_id", "code", "name", "office_id", "office_code")
SUBSIDIARY_FIELDS = ("id", "category", "reference_key", "reference_label", "source_code",
    "source_reference", "debit", "credit", "source_snapshot")
GROUPS = (("", FUND_FIELDS), ("posted__", ENTRY_FIELDS),
    ("posted__lines__", LINE_FIELDS), ("posted__lines__account__", ACCOUNT_FIELDS),
    ("posted__lines__responsibility_center__", CENTER_FIELDS),
    ("posted__lines__subsidiary_posting__", SUBSIDIARY_FIELDS))


def _part(row, prefix, fields):
    return {field: row[prefix + field] for field in fields}


def _mirror(child, parent):
    # Preserve duplicate line multiplicity; equal net totals are insufficient.
    def signature(line, reverse=False):
        amounts = (line["credit"], line["debit"]) if reverse else (line["debit"], line["credit"])
        return (line["account_id"], line["responsibility_center_id"],
                line["cash_flow_category"], *amounts)
    return bool(child["lines"]) and Counter(signature(line) for line in child["lines"]) == Counter(
        signature(line, True) for line in parent["lines"])


def _lineage(entry, all_entries):
    current, seen, ancestors = entry, {entry["id"]}, []
    issue = ""
    while current["reversal_of_id"]:
        parent_id = current["reversal_of_id"]
        if parent_id in seen:
            issue = "cyclic_reversal"
            break
        seen.add(parent_id)
        parent = all_entries.get(parent_id)
        if parent is None:
            issue = "missing_or_out_of_scope_reversal_source"
            break
        ancestors.append(parent_id)
        if not _mirror(current, parent):
            issue = "non_mirrored_reversal"
            break
        current = parent
    return {"ancestor_ids": ancestors, "origin_id": current["id"] if not issue else None,
        "origin_source_type": current["source_type"] if not issue else None,
        "exact_mirror": bool(entry["reversal_of_id"]) and not issue, "issue": issue}


def capture(*, actor, fund_id, period_start, period_end):
    """Return JSON-safe, detached source evidence and a reproducible fingerprint.

    This is an internal preparation primitive. It neither grants certification
    authority nor classifies account types as expenditure. A later workflow must
    retain this payload and pin separately reviewed allocation versions.
    """
    owner = department_for_user(actor)
    if not owner or not any(permitted(actor, action) for action in ("view", "prepare", "review", "export")):
        raise PermissionDenied
    if (type(period_start) is not date or type(period_end) is not date
            or period_start > period_end or period_end > timezone.localdate()):
        raise ValidationError("Select a valid completed source period, with no future dates.")
    if type(fund_id) is not int or fund_id <= 0:
        raise ValidationError("Select an explicit fund in this Accounting ledger.")
    fields = list(dict.fromkeys(prefix + field for prefix, group in GROUPS for field in group))
    rows = list(Fund.objects.using("finance").filter(pk=fund_id, department_id=owner.pk)
        .annotate(posted=FilteredRelation("journal_entries", condition=Q(
            journal_entries__status=JournalEntry.POSTED, journal_entries__department_id=owner.pk)))
        .order_by("posted__entry_date", "posted__pk", "posted__lines__sequence", "posted__lines__pk")
        .values(*fields))
    if not rows:
        raise PermissionDenied
    fund = _part(rows[0], "", FUND_FIELDS)
    entries = {}
    for row in rows:
        key = row["posted__id"]
        if key is None:
            continue
        if key not in entries:
            entries[key] = {**_part(row, "posted__", ENTRY_FIELDS), "lines": []}
        if row["posted__lines__id"] is not None:
            line = _part(row, "posted__lines__", LINE_FIELDS)
            line["account"] = _part(row, "posted__lines__account__", ACCOUNT_FIELDS)
            line["center"] = _part(row, "posted__lines__responsibility_center__", CENTER_FIELDS)
            subsidiary = _part(row, "posted__lines__subsidiary_posting__", SUBSIDIARY_FIELDS)
            line["subsidiary"] = subsidiary if subsidiary["id"] is not None else None
            entries[key]["lines"].append(line)
    selected = [item for item in entries.values() if period_start <= item["entry_date"] <= period_end]
    required = set()
    for entry in selected:
        entry["lineage"] = _lineage(entry, entries)
        required.update(entry["lineage"]["ancestor_ids"])
    selected_ids = {entry["id"] for entry in selected}
    ancestors = [entry for key, entry in entries.items() if key in required - selected_ids]
    lines = [line for entry in selected for line in entry["lines"]]
    controls = {"journals": len(selected), "lines": len(lines),
        "debit": sum((line["debit"] for line in lines), Decimal("0.00")),
        "credit": sum((line["credit"] for line in lines), Decimal("0.00")),
        "unassigned_lines": sum(line["center"]["office_id"] is None for line in lines),
        "unresolved_lineage": sum(bool(entry["lineage"]["issue"]) for entry in selected)}
    payload = json.loads(json.dumps({"schema": 1, "kind": "native_budget_ledger_sources",
        "scope": {"fund": fund, "period_start": period_start, "period_end": period_end},
        "journals": selected, "lineage_sources": ancestors, "controls": controls}, cls=DjangoJSONEncoder))
    captured = {"payload": payload, "checksum": checksum(payload), "captured_at": timezone.now().isoformat()}
    captured["evidence_checksum"] = checksum({"source_checksum": captured["checksum"],
        "captured_at": captured["captured_at"]})
    return captured


def verify(captured):
    """Integrity check, not authentication or certification of client-supplied data."""
    if (not isinstance(captured, dict) or not isinstance(captured.get("payload"), dict)
            or captured.get("checksum") != checksum(captured["payload"])
            or not isinstance(captured.get("captured_at"), str)
            or captured.get("evidence_checksum") != checksum({"source_checksum": captured.get("checksum"),
                "captured_at": captured.get("captured_at")})
            or captured["payload"].get("schema") != 1
            or captured["payload"].get("kind") != "native_budget_ledger_sources"):
        raise ValidationError("Native Budget source evidence does not match its retained fingerprint.")
    return captured["payload"]


def is_current(captured, actor):
    """Recheck authorized source coverage without changing an earlier capture.

    A result describes this read's snapshot, not a lock against future posting.
    Callers must use trusted retained evidence, never accept a browser checksum as
    approval. Classification/certification staleness belongs to the later workflow.
    """
    payload = verify(captured)
    try:
        scope = payload["scope"]
        current = capture(actor=actor, fund_id=scope["fund"]["id"],
            period_start=date.fromisoformat(scope["period_start"]),
            period_end=date.fromisoformat(scope["period_end"]))
    except (KeyError, TypeError, ValueError):
        raise ValidationError("Native Budget source evidence has an invalid scope.")
    return current["checksum"] == captured["checksum"]
