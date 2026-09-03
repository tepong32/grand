from __future__ import annotations

import csv
import io
import re
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Q
from django.utils.text import slugify

from finance.models import FinanceAuditEvent
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import PayableDocumentEvidence, VoucherCase, VoucherPrintJob, WetSignatureTask
from .roles import STAGE_NEXT_ACTION, finance_workspace_profile, is_finance_uat_viewer
from .services import payable_relationship_summary


ATTENTION_CHOICES = (
    ("ready_for_me", "In this role's action queue"),
    ("open_elsewhere", "Open with another role"),
    ("completed", "Released / completed"),
    ("cancelled", "Cancelled"),
)

PAYABLE_ACTION_SPECS = {
    "preparation": {
        "permission": "vouchers.initiate_payable_case",
        "stage": VoucherCase.PAYABLE_PREPARATION,
        "title": "Payable intakes to prepare or correct",
        "definition": "Current-office payable intakes at requesting-office preparation, including governed returned corrections.",
        "next_action": "Reconcile the claim, obligation allocations, and documentary checklist, then submit the same case.",
    },
    "review": {
        "permission": "vouchers.review_payable_intake",
        "stage": VoucherCase.PAYABLE_REVIEW,
        "title": "Payable intakes for independent Accounting review",
        "definition": "Independent Accounting review of payable intakes assigned to the acting office whose preparer and submitter are not the signed-in reviewer.",
        "next_action": "Review the zero-difference relationship, evidence decisions, and recognition route; accept or return the same case.",
    },
}

DV_CUSTODY_ACTION_SPECS = {
    "dv_preparation": {
        "permissions": ("vouchers.prepare_disbursement_voucher",),
        "stage": VoucherCase.ACCOUNTING_PREPARATION,
        "title": "Disbursement vouchers to prepare or correct",
        "definition": "Cases assigned to the acting Accounting office at DV preparation, subject to the Budget-certifier separation rule.",
        "next_action": "Recheck the accepted payable and exact gross-deduction-net equation, then prepare the governed DV.",
    },
    "signing_copy": {
        "permissions": ("vouchers.control_dv_printing",),
        "stage": VoucherCase.AWAITING_SIGNATURES,
        "title": "DVs needing a controlled signing copy",
        "definition": "Controlled-form cases with no active signing copy in the acting Accounting office.",
        "next_action": "Generate and archive the current checksummed signing copy before printing.",
    },
    "record_print": {
        "permissions": ("vouchers.control_dv_printing",),
        "stage": VoucherCase.AWAITING_SIGNATURES,
        "title": "Signing copies ready for print recording",
        "definition": "Current controlled signing copies whose physical copy count and printer/form-stock evidence are not yet recorded.",
        "next_action": "Print the current version and record the actual copy count, printer, paper/form stock, and note.",
    },
    "assemble_packet": {
        "permissions": ("vouchers.control_dv_printing", "vouchers.link_tracepoint_custody"),
        "stage": VoucherCase.AWAITING_SIGNATURES,
        "title": "Printed DVs needing packet assembly",
        "definition": "Printed current signing copies awaiting counted packet assembly and TracePoint custody linkage.",
        "next_action": "Count and assemble the physical packet, then create or verify its TracePoint route.",
    },
}

DV_ACTIVE_PRINT_STATES = (
    VoucherPrintJob.READY_TO_PRINT,
    VoucherPrintJob.PRINTED,
    VoucherPrintJob.AWAITING_SIGNATURES,
)

CUSTODY_CHOICES = (
    ("needs_signing_copy", "Needs a current signing copy"),
    (VoucherPrintJob.READY_TO_PRINT, "Signing file ready to print"),
    (VoucherPrintJob.PRINTED, "Printed; packet not assembled"),
    (VoucherPrintJob.AWAITING_SIGNATURES, "Packet circulating for signatures"),
    (VoucherPrintJob.SIGNED_PACKET_RETURNED, "Signed packet returned"),
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


def payable_action_choices_for_user(user):
    if is_finance_uat_viewer(user):
        return ()
    return tuple(
        (key, spec["title"])
        for key, spec in PAYABLE_ACTION_SPECS.items()
        if has_explicit_permission(user, spec["permission"])
    )


def payable_action_queryset(user, action, queryset=None):
    spec = PAYABLE_ACTION_SPECS.get(action)
    base = visible_cases_for_user(user, queryset)
    department = department_for_user(user)
    if (
        spec is None or department is None or is_finance_uat_viewer(user)
        or not has_explicit_permission(user, spec["permission"])
    ):
        return base.none(), action if spec else "", spec
    base = base.filter(current_stage=spec["stage"])
    if action == "preparation":
        base = base.filter(
            requesting_department_id=department.pk,
            current_department_id=department.pk,
        )
    else:
        base = base.filter(current_department_id=department.pk).exclude(
            Q(payable_intake__prepared_by=user) | Q(payable_intake__submitted_by=user)
        )
    return base.distinct(), action, spec


def dv_custody_action_choices_for_user(user):
    if is_finance_uat_viewer(user):
        return ()
    return tuple(
        (key, spec["title"])
        for key, spec in DV_CUSTODY_ACTION_SPECS.items()
        if all(has_explicit_permission(user, permission) for permission in spec["permissions"])
    )


def dv_custody_action_queryset(user, action, queryset=None):
    spec = DV_CUSTODY_ACTION_SPECS.get(action)
    base = visible_cases_for_user(user, queryset)
    department = department_for_user(user)
    if (
        spec is None or department is None or is_finance_uat_viewer(user)
        or not all(has_explicit_permission(user, permission) for permission in spec["permissions"])
    ):
        return base.none(), action if spec else "", spec
    base = base.filter(
        current_stage=spec["stage"], current_department_id=department.pk,
    )
    if action == "dv_preparation":
        from finance.exemptions import workflow_exemption_for
        from finance.models import FinanceWorkflowExemption

        exemption = workflow_exemption_for(
            actor=user,
            control_code=FinanceWorkflowExemption.BUDGET_CERTIFIER_DV_PREPARATION,
            department_id=department.pk,
        )
        if exemption is None:
            base = base.exclude(obligation__certified_by=user)
    elif action == "signing_copy":
        base = base.filter(voucher_template__controlled_print_required=True).exclude(
            print_jobs__status__in=DV_ACTIVE_PRINT_STATES,
        )
    elif action == "record_print":
        base = base.filter(print_jobs__status=VoucherPrintJob.READY_TO_PRINT)
    elif action == "assemble_packet":
        base = base.filter(print_jobs__status=VoucherPrintJob.PRINTED)
    return base.distinct(), action, spec


def dv_signature_task_queryset(user):
    base_cases = visible_cases_for_user(user)
    department = department_for_user(user)
    if (
        department is None or is_finance_uat_viewer(user)
        or not has_explicit_permission(user, "vouchers.track_wet_signatures")
    ):
        return WetSignatureTask.objects.none()
    prior_pending = WetSignatureTask.objects.filter(
        case_id=OuterRef("case_id"),
        round_number=OuterRef("round_number"),
        sequence__lt=OuterRef("sequence"),
        status=WetSignatureTask.PENDING,
    )
    controlled_ready = VoucherPrintJob.objects.filter(
        case_id=OuterRef("case_id"),
        signature_round=OuterRef("round_number"),
        status=VoucherPrintJob.AWAITING_SIGNATURES,
    )
    return WetSignatureTask.objects.filter(
        case__in=base_cases,
        case__current_stage=VoucherCase.AWAITING_SIGNATURES,
        case__current_department_id=department.pk,
        status=WetSignatureTask.PENDING,
    ).annotate(
        has_prior_pending=Exists(prior_pending),
        controlled_ready=Exists(controlled_ready),
    ).filter(
        has_prior_pending=False,
    ).filter(
        Q(case__voucher_template__isnull=True)
        | Q(case__voucher_template__controlled_print_required=False)
        | Q(controlled_ready=True)
    ).select_related(
        "case", "case__requesting_department", "case__current_department", "custody_department",
    ).prefetch_related("case__print_jobs").order_by(
        "case__reference_code", "round_number", "sequence", "pk",
    )


def apply_case_filters(
    queryset, *, actionable_stages=(), stage="", transaction_type="",
    requesting_department="", attention="", custody="", search="", actor=None,
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
        actor_department = department_for_user(actor) if actor is not None else None
        if actor_department is not None:
            if VoucherCase.PAYABLE_PREPARATION in actionable_stages:
                queryset = queryset.exclude(
                    Q(current_stage=VoucherCase.PAYABLE_PREPARATION)
                    & ~Q(
                        requesting_department_id=actor_department.pk,
                        current_department_id=actor_department.pk,
                    )
                )
            if VoucherCase.PAYABLE_REVIEW in actionable_stages:
                queryset = queryset.exclude(
                    Q(current_stage=VoucherCase.PAYABLE_REVIEW)
                    & (
                        ~Q(current_department_id=actor_department.pk)
                        | Q(payable_intake__prepared_by=actor)
                        | Q(payable_intake__submitted_by=actor)
                    )
                )
            if VoucherCase.ACCOUNTING_PREPARATION in actionable_stages:
                from finance.exemptions import workflow_exemption_for
                from finance.models import FinanceWorkflowExemption

                queryset = queryset.exclude(
                    Q(current_stage=VoucherCase.ACCOUNTING_PREPARATION)
                    & ~Q(current_department_id=actor_department.pk)
                )
                exemption = workflow_exemption_for(
                    actor=actor,
                    control_code=FinanceWorkflowExemption.BUDGET_CERTIFIER_DV_PREPARATION,
                    department_id=actor_department.pk,
                )
                if exemption is None:
                    queryset = queryset.exclude(
                        current_stage=VoucherCase.ACCOUNTING_PREPARATION,
                        obligation__certified_by=actor,
                    )
            if VoucherCase.AWAITING_SIGNATURES in actionable_stages:
                queryset = queryset.exclude(
                    Q(current_stage=VoucherCase.AWAITING_SIGNATURES)
                    & ~Q(current_department_id=actor_department.pk)
                )
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

    if custody == "needs_signing_copy":
        queryset = queryset.filter(
            current_stage=VoucherCase.AWAITING_SIGNATURES,
            voucher_template__controlled_print_required=True,
        ).exclude(print_jobs__status__in=(
            VoucherPrintJob.READY_TO_PRINT, VoucherPrintJob.PRINTED,
            VoucherPrintJob.AWAITING_SIGNATURES,
        ))
    elif custody in dict(VoucherPrintJob.STATUS_CHOICES) and custody != VoucherPrintJob.SUPERSEDED:
        queryset = queryset.filter(print_jobs__status=custody)
    elif custody:
        queryset = queryset.none()
    else:
        custody = ""

    search = " ".join((search or "").split())[:160]
    if search:
        text_match = Q()
        for token in search.split()[:8]:
            token_match = (
                Q(reference_code__icontains=token)
                | Q(payee_name__icontains=token)
                | Q(particulars__icontains=token)
                | Q(transaction_type__icontains=token)
                | Q(requesting_department__name__icontains=token)
                | Q(current_department__name__icontains=token)
                | Q(authoritative_obligation_number__icontains=token)
                | Q(payable_intake__claim_reference__icontains=token)
                | Q(disbursement_voucher__dv_number__icontains=token)
                | Q(payment_instruments__check_number__icontains=token)
                | Q(payment_instruments__receipt_reference__icontains=token)
                | Q(payment_instruments__current_advice_batch__advice_number__icontains=token)
                | Q(posting_requests__jev_number__icontains=token)
            )
            text_match &= token_match

        exact_identifier_match = Q()
        try:
            identifier = UUID(search)
        except (TypeError, ValueError, AttributeError):
            identifier = None
        if identifier:
            exact_identifier_match |= (
                Q(public_id=identifier)
                | Q(authoritative_obligation_public_id=identifier)
                | Q(payment_instruments__public_id=identifier)
                | Q(payment_instruments__current_advice_batch__public_id=identifier)
                | Q(posting_requests__public_id=identifier)
            )
        if re.fullmatch(r"[0-9a-fA-F]{64}", search):
            exact_identifier_match |= (
                Q(authoritative_obligation_checksum__iexact=search)
                | Q(posting_requests__payload_checksum__iexact=search)
                | Q(posting_requests__posting_rule_checksum__iexact=search)
                | Q(outputs__checksum__iexact=search)
            )
        queryset = queryset.filter(text_match | exact_identifier_match)
    return queryset.distinct(), stage, transaction_type, requesting_department, attention, custody, search


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
    transaction_type="", requesting_department="", attention="", custody="", search="",
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
        attention, custody, search,
    ) if value) or "all-visible"
    filename = f"finance-case-control-register-{suffix}.csv"
    metadata = {
        "kind": "finance_case_control_register", "role": finance_workspace_profile(actor, requested_role)["role"],
        "stage_filter": stage or "all", "transaction_type_filter": transaction_type or "all",
        "requesting_department_filter": requesting_department or "all",
        "attention_filter": attention or "all", "custody_filter": custody or "all",
        "search_filter": search,
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
