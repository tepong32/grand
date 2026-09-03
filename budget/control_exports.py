from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import department_for_user, has_budget_permission
from .models import AllotmentReleaseOrder, BudgetAuditEvent, ObligationRequest
from .services import actor_label


ALLOTMENT_ATTENTION_CHOICES = (
    ("needs_preparation", "Needs preparation or correction"),
    ("awaiting_review", "Awaiting independent review"),
    ("posted", "Posted control evidence"),
)

OBLIGATION_ATTENTION_CHOICES = (
    ("needs_preparation", "Needs requesting-office preparation or correction"),
    ("awaiting_certification", "Awaiting Budget certification"),
    ("certified", "Certified registry evidence"),
)

ALLOTMENT_REGISTER_COLUMNS = (
    "order_public_id", "budget_office", "fiscal_year", "appropriation_authority",
    "appropriation_checksum", "order_number", "order_type", "status", "next_action",
    "release_date", "effective_date", "authority_reference", "evidence_reference", "purpose",
    "signed_control_total", "computed_line_total", "control_difference", "allotment_checksum",
    "corrects_order", "prepared_by", "submitted_by", "posted_by", "decision_reason",
    "state_version", "updated_at",
)

OBLIGATION_REGISTER_COLUMNS = (
    "request_public_id", "budget_office", "fiscal_year", "appropriation_authority",
    "appropriation_checksum", "requesting_office", "form_type", "request_reference",
    "obligation_number", "obligation_kind", "status", "next_action", "obligation_date",
    "claimant_payee", "particulars", "evidence_reference", "signed_control_total",
    "computed_effect_total", "control_difference", "obligation_checksum", "corrects_obligation",
    "linked_voucher_case", "prepared_by", "submitted_by", "certified_by", "decision_reason",
    "state_version", "updated_at",
)


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def apply_allotment_filters(queryset, *, fiscal_year=None, kind="", status="", attention=""):
    if fiscal_year is not None:
        queryset = queryset.filter(fiscal_year=fiscal_year)
    if kind:
        if kind in dict(AllotmentReleaseOrder.KIND_CHOICES):
            queryset = queryset.filter(kind=kind)
        else:
            queryset = queryset.none()
    else:
        kind = ""
    if status:
        if status in dict(AllotmentReleaseOrder.STATUS_CHOICES):
            queryset = queryset.filter(status=status)
        else:
            queryset = queryset.none()
    else:
        status = ""
    if attention == "needs_preparation":
        queryset = queryset.filter(status__in=(AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED))
    elif attention == "awaiting_review":
        queryset = queryset.filter(status=AllotmentReleaseOrder.FOR_REVIEW)
    elif attention == "posted":
        queryset = queryset.filter(status=AllotmentReleaseOrder.POSTED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""
    return queryset, kind, status, attention


def next_allotment_action(order):
    if order.status == AllotmentReleaseOrder.DRAFT:
        return "Complete and reconcile the order, then submit"
    if order.status == AllotmentReleaseOrder.RETURNED:
        return "Correct the returned order, then resubmit"
    if order.status == AllotmentReleaseOrder.FOR_REVIEW:
        return "Independent reviewer: post or return"
    if order.status == AllotmentReleaseOrder.POSTED:
        return "Retain evidence; use a linked successor for corrections"
    return "Review current status"


def apply_obligation_filters(
    queryset, *, fiscal_year=None, kind="", form_type="", status="", attention="",
):
    if fiscal_year is not None:
        queryset = queryset.filter(fiscal_year=fiscal_year)
    if kind:
        if kind in dict(ObligationRequest.KIND_CHOICES):
            queryset = queryset.filter(kind=kind)
        else:
            queryset = queryset.none()
    else:
        kind = ""
    if form_type:
        if form_type in dict(ObligationRequest.FORM_CHOICES):
            queryset = queryset.filter(form_type=form_type)
        else:
            queryset = queryset.none()
    else:
        form_type = ""
    if status:
        if status in dict(ObligationRequest.STATUS_CHOICES):
            queryset = queryset.filter(status=status)
        else:
            queryset = queryset.none()
    else:
        status = ""
    if attention == "needs_preparation":
        queryset = queryset.filter(status__in=(ObligationRequest.DRAFT, ObligationRequest.RETURNED))
    elif attention == "awaiting_certification":
        queryset = queryset.filter(status=ObligationRequest.FOR_CERTIFICATION)
    elif attention == "certified":
        queryset = queryset.filter(status=ObligationRequest.CERTIFIED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""
    return queryset, kind, form_type, status, attention


def next_obligation_action(item):
    if item.status == ObligationRequest.DRAFT:
        return "Requesting office: complete and submit"
    if item.status == ObligationRequest.RETURNED:
        return "Requesting office: correct and resubmit"
    if item.status == ObligationRequest.FOR_CERTIFICATION:
        return "Budget reviewer: certify or return"
    if item.status == ObligationRequest.CERTIFIED:
        return "Retain evidence; use a linked successor before DV/check issuance"
    return "Review current status"


def _assert_actor_department(department, actor):
    actor_department = department_for_user(actor)
    if actor_department is None or actor_department.pk != department.pk:
        raise PermissionDenied


def build_allotment_register(
    department, actor, queryset, *, fiscal_year=None, kind="", status="", attention="",
):
    _assert_actor_department(department, actor)
    if not has_budget_permission(actor, "view_allotment_control"):
        raise PermissionDenied
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The allotment control register may contain only the current Budget office.")
    orders = list(queryset.select_related(
        "authorization", "authorization__version", "fiscal_year", "corrects",
    ).prefetch_related("lines"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(ALLOTMENT_REGISTER_COLUMNS)
    for order in orders:
        writer.writerow(tuple(_csv_safe(value) for value in (
            order.public_id, order.department_label, order.fiscal_year.year,
            order.authorization.ordinance_number, order.authorization.snapshot_checksum,
            order.order_number, order.get_kind_display(), order.get_status_display(),
            next_allotment_action(order), order.release_date, order.effective_date,
            order.authority_reference, order.evidence_reference, order.purpose,
            order.signed_control_total, order.computed_total, order.control_difference,
            order.snapshot_checksum, order.corrects.order_number if order.corrects else "",
            order.created_by_label, order.submitted_by_label, order.posted_by_label,
            order.decision_reason, order.state_version, order.updated_at.isoformat(),
        )))
    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    year_label = str(fiscal_year.year) if fiscal_year is not None else "all-years"
    filename = f"finance-allotment-control-register-{slugify(year_label)}.csv"
    metadata = {
        "kind": "finance_allotment_control_register",
        "fiscal_year_public_id": str(fiscal_year.public_id) if fiscal_year is not None else "",
        "fiscal_year": fiscal_year.year if fiscal_year is not None else "all",
        "order_kind_filter": kind or "all", "status_filter": status or "all",
        "attention_filter": attention or "all", "order_count": len(orders),
        "authority_boundary": (
            "Oversight evidence only; only posted movements affect balances and exact local/DBM/COA form "
            "acceptance remains separately required."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-allotment-control-register", filename=filename, metadata=metadata,
    )
    BudgetAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name,
        target_type="allotment_workspace", target_id=str(department.pk),
        action="allotment_register_exported", actor_id=actor.pk, actor_label=actor_label(actor),
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt


def build_obligation_register(
    department, actor, queryset, *, fiscal_year=None, kind="", form_type="", status="", attention="",
):
    _assert_actor_department(department, actor)
    if not any(has_budget_permission(actor, codename) for codename in (
        "view_obligation_registry", "initiate_obligation_requests", "certify_obligations",
    )):
        raise PermissionDenied
    if queryset.exclude(Q(department_id=department.pk) | Q(requesting_department_id=department.pk)).exists():
        raise ValidationError("The obligation control register may contain only the user's current role scope.")
    items = list(queryset.select_related(
        "authorization", "authorization__version", "fiscal_year", "corrects",
    ).prefetch_related("lines"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(OBLIGATION_REGISTER_COLUMNS)
    for item in items:
        writer.writerow(tuple(_csv_safe(value) for value in (
            item.public_id, item.department_label, item.fiscal_year.year,
            item.authorization.ordinance_number, item.authorization.snapshot_checksum,
            item.requesting_department_label, item.get_form_type_display(), item.request_reference,
            item.obligation_number, item.get_kind_display(), item.get_status_display(),
            next_obligation_action(item), item.obligation_date, item.claimant_payee, item.particulars,
            item.evidence_reference, item.signed_control_total, item.computed_effect_total,
            item.control_difference, item.snapshot_checksum,
            (item.corrects.obligation_number or item.corrects.request_reference) if item.corrects else "",
            item.linked_voucher_case_public_id, item.created_by_label, item.submitted_by_label,
            item.certified_by_label, item.decision_reason, item.state_version, item.updated_at.isoformat(),
        )))
    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    year_label = str(fiscal_year.year) if fiscal_year is not None else "all-years"
    filename = f"finance-obligation-control-register-{slugify(year_label)}.csv"
    metadata = {
        "kind": "finance_obligation_control_register",
        "fiscal_year_public_id": str(fiscal_year.public_id) if fiscal_year is not None else "",
        "fiscal_year": fiscal_year.year if fiscal_year is not None else "all",
        "obligation_kind_filter": kind or "all", "form_type_filter": form_type or "all",
        "status_filter": status or "all", "attention_filter": attention or "all",
        "request_count": len(items),
        "role_scope": "current user's Budget-registry and/or requesting-office visibility",
        "authority_boundary": (
            "Queue oversight evidence only; only certified movements affect balances and exact local/DBM/COA "
            "form acceptance remains separately required."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-obligation-control-register", filename=filename, metadata=metadata,
    )
    BudgetAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name,
        target_type="obligation_workspace", target_id=str(department.pk),
        action="obligation_register_exported", actor_id=actor.pk, actor_label=actor_label(actor),
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
