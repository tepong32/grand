from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from src.export_archive import archive_export
from .access import _explicit_permission, department_for_user
from .models import FinanceAuditEvent
from .operations import finance_operations_access
from .work_tasks import finance_work_tasks

WORK_EXPORT_LIMIT = 100
WORK_EXPORT_FIELDS = (
    "task_id", "task_type", "area", "case_id", "reference", "transaction_type", "subject",
    "action", "gate", "owner_queue", "scope", "received_at", "due_on", "due_state",
    "calendar_basis", "age_days", "state", "source_state", "source_version", "exception", "url",
)


def can_export_work(user):
    from vouchers.roles import is_finance_uat_viewer
    return bool(
        department_for_user(user) and not is_finance_uat_viewer(user)
        and _explicit_permission(user, "finance.export_finance_work")
        and finance_operations_access(user)["allowed"]
    )


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def build_work_export(user, *, view="ready", planned_days=7):
    if not can_export_work(user):
        raise PermissionDenied("My Work export requires an explicit administrator-assigned permission and current source access.")
    department = department_for_user(user)
    generated_at = timezone.now()
    projection = finance_work_tasks(user, display_limit=WORK_EXPORT_LIMIT, view=view, planned_days=planned_days)
    export_id = str(uuid.uuid4())
    metadata = {
        "kind": "finance_my_work", "export_id": export_id, "view": view, "planned_days": planned_days,
        "generated_at": generated_at.isoformat(), "row_limit": WORK_EXPORT_LIMIT,
        "row_count": len(projection["tasks"]), "eligible_count": projection["task_count"],
        "truncated": projection["tasks_truncated"], "coverage": projection["task_coverage"],
        "task_ids": [row["task_id"] for row in projection["tasks"]],
        "status": "Personal source-linked work snapshot; not an assignment, approval, or official financial form.",
    }
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    context_fields = ("export_id", "view", "generated_at", "row_count", "eligible_count", "row_limit", "truncated")
    writer.writerow(context_fields + WORK_EXPORT_FIELDS)
    for row in projection["tasks"]:
        writer.writerow([_csv_cell(metadata[key]) for key in context_fields] + [_csv_cell(row[key]) for key in WORK_EXPORT_FIELDS])
    content = stream.getvalue().encode("utf-8-sig")
    filename = f"finance-my-work-{view}.csv"
    receipt = archive_export(
        content=content, department=department, user=user, category="finance-my-work",
        filename=filename, metadata=metadata,
    )
    FinanceAuditEvent.objects.create(
        department=department, target_type="finance_work_export", target_id=export_id,
        action="work_exported", actor=user,
        snapshot={**metadata, "sha256": receipt["sha256"], "relative_path": receipt["relative_path"]},
    )
    return content, filename, receipt, metadata
