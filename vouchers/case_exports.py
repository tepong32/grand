from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.text import slugify

from finance.models import FinanceAuditEvent
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import PayableDocumentEvidence, VoucherCase
from .roles import STAGE_NEXT_ACTION, finance_workspace_profile
from .services import payable_relationship_summary


ATTENTION_CHOICES = (
    ("ready_for_me", "In this role's action queue"),
    ("open_elsewhere", "Open with another role"),
    ("completed", "Released / completed"),
    ("cancelled", "Cancelled"),
)

CASE_REGISTER_COLUMNS = (
    "case_reference", "case_public_id", "stage", "next_action", "requesting_office",
    "current_office", "transaction_type", "payee", "particulars", "binding_status",
    "binding_error", "obligation_public_id", "obligation_number", "obligation_checksum",
    "obligation_amount", "payable_status", "claim_reference", "claim_amount",
    "relationship_type", "allocation_total", "control_difference", "checklist_total",
    "checklist_pending", "duplicate_warning", "duplicate_review_note", "recognition_decision",
    "recognition_basis", "obligation_adjustment_decision", "obligation_adjustment_basis",
    "state_version", "created_at", "updated_at", "completed_at", "cancelled_at",
    "cancellation_reason",
)


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def visible_cases_for_user(user, queryset=None, *, requested_role=None):
    """Return the cases visible to this workbench role without granting action authority."""
    queryset = queryset if queryset is not None else VoucherCase.objects.all()
    department = department_for_user(user)
    if department is None:
        return queryset.none()
    profile = finance_workspace_profile(user, requested_role)
    if profile["role"] == "requesting" and not profile["is_uat_viewer"]:
        return queryset.filter(requesting_department_id=department.pk)
    return queryset


def apply_case_filters(
    queryset, *, actionable_stages=(), stage="", transaction_type="",
    requesting_department="", attention="", search="",
):
    actionable_stages = tuple(actionable_stages)
    if stage:
        if stage in dict(VoucherCase.STAGE_CHOICES):
            queryset = queryset.filter(current_stage=stage)
        else:
            queryset = queryset.none()
    else:
        stage = ""

    valid_transaction_types = set(queryset.model.objects.filter(
        pk__in=queryset.values("pk"),
    ).values_list("transaction_type", flat=True).distinct())
    if transaction_type:
        if transaction_type in valid_transaction_types:
            queryset = queryset.filter(transaction_type=transaction_type)
        else:
            queryset = queryset.none()
    else:
        transaction_type = ""

    valid_departments = {
        str(value) for value in queryset.model.objects.filter(
            pk__in=queryset.values("pk"),
        ).values_list("requesting_department_id", flat=True).distinct()
    }
    if requesting_department:
        if requesting_department in valid_departments:
            queryset = queryset.filter(requesting_department_id=requesting_department)
        else:
            queryset = queryset.none()
    else:
        requesting_department = ""

    open_stages = tuple(
        value for value, _label in VoucherCase.STAGE_CHOICES
        if value not in (VoucherCase.COMPLETED, VoucherCase.CANCELLED)
    )
    if attention == "ready_for_me":
        queryset = queryset.filter(current_stage__in=actionable_stages)
    elif attention == "open_elsewhere":
        queryset = queryset.filter(current_stage__in=open_stages).exclude(current_stage__in=actionable_stages)
    elif attention == "completed":
        queryset = queryset.filter(current_stage=VoucherCase.COMPLETED)
    elif attention == "cancelled":
        queryset = queryset.filter(current_stage=VoucherCase.CANCELLED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""

    search = (search or "").strip()[:160]
    if search:
        queryset = queryset.filter(
            Q(reference_code__icontains=search)
            | Q(payee_name__icontains=search)
            | Q(particulars__icontains=search)
            | Q(authoritative_obligation_number__icontains=search)
        )
    return queryset, stage, transaction_type, requesting_department, attention, search


def filter_options(queryset):
    transaction_types = [
        {"value": value, "label": value.replace("-", " ").replace("_", " ").title()}
        for value in queryset.values_list("transaction_type", flat=True).distinct().order_by("transaction_type")
    ]
    departments = [
        {"value": str(pk), "label": name}
        for pk, name in queryset.values_list(
            "requesting_department_id", "requesting_department__name",
        ).distinct().order_by("requesting_department__name")
    ]
    return transaction_types, departments


def build_case_control_register(
    *, actor, queryset, requested_role=None, stage="",
    transaction_type="", requesting_department="", attention="", search="",
):
    department = department_for_user(actor)
    if department is None or not has_explicit_permission(actor, "vouchers.view_voucher_audit"):
        raise PermissionDenied
    visible = visible_cases_for_user(actor, requested_role=requested_role)
    if queryset.exclude(pk__in=visible.values("pk")).exists():
        raise ValidationError("The case control register may contain only the current workbench role scope.")

    cases = list(queryset.select_related(
        "requesting_department", "current_department", "payable_intake",
    ).prefetch_related("payable_document_evidence"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(CASE_REGISTER_COLUMNS)
    for case in cases:
        intake = getattr(case, "payable_intake", None)
        summary = payable_relationship_summary(case) if intake else {
            "allocated_total": "0.00", "difference": "0.00",
        }
        evidence = list(case.payable_document_evidence.all())
        writer.writerow(tuple(_csv_safe(value) for value in (
            case.reference_code, case.public_id, case.get_current_stage_display(),
            STAGE_NEXT_ACTION.get(case.current_stage, case.get_current_stage_display()),
            case.requesting_department.name, case.current_department.name,
            case.transaction_type, case.payee_name, case.particulars,
            case.get_obligation_binding_status_display(), case.obligation_binding_error,
            case.authoritative_obligation_public_id, case.authoritative_obligation_number,
            case.authoritative_obligation_checksum, case.authoritative_obligation_amount,
            intake.get_status_display() if intake else "", intake.claim_reference if intake else "",
            intake.claim_amount if intake else "", intake.get_initial_relationship_type_display() if intake else "",
            summary["allocated_total"], summary["difference"], len(evidence),
            sum(item.status == PayableDocumentEvidence.PENDING for item in evidence),
            intake.duplicate_warning if intake else "", intake.duplicate_review_note if intake else "",
            intake.get_recognition_decision_display() if intake and intake.recognition_decision else "",
            intake.recognition_basis if intake else "",
            intake.get_obligation_adjustment_decision_display() if intake and intake.obligation_adjustment_decision else "",
            intake.obligation_adjustment_basis if intake else "", case.state_version,
            case.created_at.isoformat(), case.updated_at.isoformat(),
            case.completed_at.isoformat() if case.completed_at else "",
            case.cancelled_at.isoformat() if case.cancelled_at else "", case.cancellation_reason,
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        stage, transaction_type, f"department-{requesting_department}" if requesting_department else "",
        attention, search,
    ) if value) or "all-visible"
    filename = f"finance-case-control-register-{suffix}.csv"
    metadata = {
        "kind": "finance_case_control_register", "role": finance_workspace_profile(actor, requested_role)["role"],
        "stage_filter": stage or "all", "transaction_type_filter": transaction_type or "all",
        "requesting_department_filter": requesting_department or "all",
        "attention_filter": attention or "all", "search_filter": search,
        "case_count": len(cases),
        "authority_boundary": (
            "Controlled queue and oversight evidence only; this register is not an approval, payment authority, "
            "or automatically an official COA/DBM/local form."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-case-control-register", filename=filename, metadata=metadata,
    )
    FinanceAuditEvent.objects.create(
        department=department, target_type="voucherworkbench", target_id=str(department.pk),
        action="case_register_exported", actor=actor,
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
