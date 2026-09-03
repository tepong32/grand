from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.core.files.base import ContentFile
from django.utils import timezone

from finance.exemptions import workflow_exemption_for, workflow_exemption_snapshot
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceNumberingSequence,
    FinancePartyClaimant, FinancePostingRule, FinanceSignatory, FinanceTransactionVariant, FinanceWorkflowExemption,
    finance_tax_rule_snapshot,
)
from finance.services import (
    FinanceTemplateError, _destination, inspect_finance_workbook, posting_rule_snapshot,
    verify_template_evidence,
)
from profiles.models import EmployeeProfile
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import (
    AccountingValidation, BankAdviceBatch, BankAdviceItem, BudgetAllocationLine,
    BudgetObligation, ControlOverride, DisbursementVoucher, PaymentInstrument,
    PayableDocumentEvidence, PayableIntake, PaymentInstrumentException, TreasuryCashReservation,
    VoucherCase, VoucherDeduction, VoucherDocumentCheck, VoucherEvent,
    VoucherLineItem, VoucherNonFinancialAmendment, VoucherNumberIssue, VoucherOutput,
    VoucherPostingRequest, VoucherPrintJob, VoucherTask, WetSignatureTask,
    voucher_tax_evidence_checksum,
)
from .issuance_boundaries import lock_foundation_issuance_boundary


class VoucherWorkflowError(ValidationError):
    pass


STAGE_PERMISSION = {
    VoucherCase.BUDGET_DRAFT: "vouchers.certify_budget_obligation",
    VoucherCase.PAYABLE_PREPARATION: "vouchers.initiate_payable_case",
    VoucherCase.PAYABLE_REVIEW: "vouchers.review_payable_intake",
    VoucherCase.ACCOUNTING_PREPARATION: "vouchers.prepare_disbursement_voucher",
    VoucherCase.AWAITING_SIGNATURES: "vouchers.track_wet_signatures",
    VoucherCase.ACCOUNTING_VALIDATION: "vouchers.validate_accounting_voucher",
    VoucherCase.ACCOUNTING_POSTING: "accounting.prepare_journal_entries",
    VoucherCase.ACCOUNTING_EVENT_POSTING: "accounting.prepare_journal_entries",
    VoucherCase.ACCOUNTING_RETURNED_ITEM: "vouchers.review_returned_instruments",
    VoucherCase.TREASURY_CHECK_PREPARATION: "vouchers.issue_payment_instruments",
    VoucherCase.ACCOUNTING_BANK_ADVICE: "vouchers.prepare_bank_advice",
    VoucherCase.TREASURY_RELEASE: "vouchers.release_payment_instruments",
}


def _require(actor, permission):
    if not has_explicit_permission(actor, permission):
        raise PermissionDenied


def _require_current_office(case, actor):
    department = department_for_user(actor)
    if department is None or department.pk != case.current_department_id:
        raise PermissionDenied


def _department_for_permission(permission, fallback):
    app_label, codename = permission.split(".", 1)
    profiles = EmployeeProfile.objects.filter(assigned_department__isnull=False, user__is_active=True).filter(
        Q(user__user_permissions__content_type__app_label=app_label, user__user_permissions__codename=codename)
        | Q(user__groups__permissions__content_type__app_label=app_label, user__groups__permissions__codename=codename)
    )
    department = profiles.select_related("assigned_department").order_by("assigned_department_id").first()
    return department.assigned_department if department else fallback


def _active_release(as_of=None):
    as_of = as_of or timezone.localdate()
    releases = FinanceConfigurationRelease.objects.filter(
        status="active", effective_from__lte=as_of,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)).order_by("-activated_at", "-pk")
    release = releases.first()
    if not release:
        raise VoucherWorkflowError("No active Accounting-approved Finance Setup release is available.")
    return release


def _event(case, actor, action, from_stage, reason, metadata, idempotency_key):
    return VoucherEvent.objects.create(
        case=case, action=action, from_stage=from_stage, to_stage=case.current_stage,
        actor=actor, actor_department=department_for_user(actor), reason=reason,
        metadata=metadata or {}, state_version=case.state_version, idempotency_key=idempotency_key,
    )


def _locked(case, expected_version, idempotency_key):
    locked = VoucherCase.objects.select_for_update().get(pk=case.pk)
    existing = locked.events.filter(idempotency_key=idempotency_key).first()
    if existing:
        return locked, existing
    if expected_version is not None and locked.state_version != expected_version:
        raise VoucherWorkflowError("This voucher changed after the page was opened. Reload it before acting.")
    if locked.current_stage in {VoucherCase.COMPLETED, VoucherCase.CANCELLED}:
        raise VoucherWorkflowError("A completed or cancelled voucher cannot be changed.")
    return locked, None


def _advance(case, actor, stage, action, idempotency_key, reason="", metadata=None, destination_department=None):
    previous = case.current_stage
    now = timezone.now()
    case.tasks.filter(status=VoucherTask.OPEN).update(status=VoucherTask.COMPLETED, completed_at=now)
    case.current_stage = stage
    permission = STAGE_PERMISSION.get(stage)
    if permission:
        case.current_department = destination_department or _department_for_permission(permission, department_for_user(actor))
        VoucherTask.objects.create(case=case, stage=stage, department=case.current_department)
    case.state_version += 1
    if stage == VoucherCase.COMPLETED:
        case.completed_at = now
    elif previous == VoucherCase.COMPLETED:
        case.completed_at = None
    case.save(update_fields=("current_stage", "current_department", "state_version", "completed_at", "updated_at"))
    _event(case, actor, action, previous, reason, metadata, idempotency_key)
    return case


def _lock_case_foundation_boundary(case):
    """Lock the office/year amendment cutoff before locking a voucher case."""

    if not case.configuration_release_id:
        raise VoucherWorkflowError(
            "This voucher has no pinned Finance Setup release. Stop processing and route the record for repair."
        )
    release = case.configuration_release
    return lock_foundation_issuance_boundary(
        department_id=release.department_id,
        fiscal_year=release.fiscal_year,
    )


def _require_active_case_foundation(case):
    """Stop new issuance while an adopted fiscal foundation awaits reapproval."""

    from accounting.models import FiscalYear

    fiscal_year = FiscalYear.objects.filter(
        department_id=case.configuration_release.department_id,
        year=case.configuration_release.fiscal_year,
    ).first()
    if fiscal_year is not None and fiscal_year.status != FiscalYear.ACTIVE:
        raise VoucherWorkflowError(
            "Finance setup for this fiscal year is not active. Finish the independent readiness review "
            "and reactivate it before issuing an OBR, DV, or check."
        )


def _consume_sequence_number(case, actor, sequence_document_type, issue_document_type):
    fiscal_year = case.configuration_release.fiscal_year
    sequence = FinanceNumberingSequence.objects.select_for_update().filter(
        release=case.configuration_release, fiscal_year=fiscal_year,
        document_type=sequence_document_type, status="active",
    ).first()
    if not sequence:
        raise VoucherWorkflowError(
            f"No active {sequence_document_type} numbering sequence is configured for this fiscal year."
        )
    value = sequence.next_number
    formatted = f"{sequence.prefix}{value:0{sequence.padding}d}"
    VoucherNumberIssue.objects.create(
        case=case, sequence=sequence, document_type=issue_document_type, numeric_value=value,
        formatted_value=formatted, issued_by=actor,
    )
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))
    return formatted


def _consume_number(case, actor, document_type):
    return _consume_sequence_number(case, actor, document_type, document_type)


def _deduction_payload(item):
    row = {"code": item.code, "description": item.description, "amount": str(item.amount)}
    if item.tax_rule_checksum:
        row["tax_reporting"] = {
            **item.tax_rule_snapshot,
            "tax_base": str(item.tax_base),
            "tax_withheld": str(item.amount),
            "tax_rule_checksum": item.tax_rule_checksum,
            "tax_evidence_checksum": item.tax_evidence_checksum,
            "payee_name": item.payee_name_snapshot,
            "payee_tax_identifier": item.payee_tax_identifier_snapshot,
            "voucher_date": item.voucher.voucher_date.isoformat(),
            "voucher_number": item.voucher.dv_number,
            "case_reference": item.voucher.case.reference_code,
            "case_public_id": str(item.voucher.case.public_id),
        }
    return row


def _event_posting_payload(case, posting_rule, rule_checksum, *, event_amount, bank_account_code, trigger):
    voucher = case.disbursement_voucher
    return {
        "schema_version": 4,
        "voucher_case_public_id": str(case.public_id),
        "voucher_reference": case.reference_code,
        "dv_number": voucher.dv_number,
        "transaction_type": case.transaction_type,
        "posting_rule_public_id": str(posting_rule.public_id),
        "posting_rule_checksum": rule_checksum,
        "payee_key": f"finance-party:{case.payee.code}" if case.payee_id else f"voucher-case:{case.public_id}",
        "payee_code": case.payee.code if case.payee_id else "",
        "payee_name": case.payee_name,
        "particulars": case.particulars,
        "gross_amount": str(voucher.gross_amount),
        "total_deductions": str(voucher.total_deductions),
        "net_amount": str(voucher.net_amount),
        "event_amount": str(event_amount),
        "bank_account_code": bank_account_code,
        "trigger": trigger,
        "allocations": [
            {
                "fund_code": line.fund_code,
                "responsibility_center_code": line.responsibility_center_code,
                "account_code": line.account_code,
                "amount": str(line.amount),
            }
            for line in case.obligation.allocation_lines.order_by("pk")
        ],
        "deductions": [
            _deduction_payload(item)
            for item in voucher.deductions.order_by("pk")
        ],
    }


def _create_event_posting_request(
    *, case, actor, event_kind, recognition_point, event_date, event_amount,
    bank_account_code, trigger_key, trigger, resume_stage,
):
    """Pin one configured payment-cycle decision and optionally queue its governed JEV."""
    variant = case.configuration_release.transaction_variants.filter(
        code=case.transaction_type,
        status__in=("approved", "scheduled", "active", "superseded"),
    ).first()
    if variant is None:
        raise VoucherWorkflowError(
            f"The pinned Finance Setup release has no governed transaction variant for '{case.transaction_type}'."
        )
    posting_rule = variant.posting_rules.filter(event_kind=event_kind).first()
    if posting_rule is None or posting_rule.recognition_point != recognition_point:
        return None
    existing = case.posting_requests.filter(kind=event_kind, trigger_key=trigger_key).first()
    if existing:
        return existing
    rule_snapshot, rule_checksum = posting_rule_snapshot(posting_rule)
    version = (case.posting_requests.filter(kind=event_kind).aggregate(value=Max("version"))["value"] or 0) + 1
    effect = rule_snapshot["accounting_effect"]
    jev_number = None
    if effect == FinancePostingRule.JOURNAL_ENTRY:
        jev_number = _consume_sequence_number(
            case,
            actor,
            "journal-entry",
            f"journal-entry-{event_kind}-{version}",
        )
    payload = _event_posting_payload(
        case,
        posting_rule,
        rule_checksum,
        event_amount=event_amount,
        bank_account_code=bank_account_code,
        trigger=trigger,
    )
    payload["jev_number"] = jev_number or ""
    payload["jev_date"] = event_date.isoformat()
    checksum = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    request = VoucherPostingRequest(
        case=case,
        kind=event_kind,
        version=version,
        jev_number=jev_number,
        jev_date=event_date,
        origin_stage=case.current_stage,
        resume_stage=resume_stage,
        trigger_key=trigger_key,
        finance_department_id=case.configuration_release.department_id,
        finance_department_label=case.configuration_release.department.name,
        posting_rule=posting_rule,
        posting_rule_public_id_snapshot=str(posting_rule.public_id),
        posting_rule_snapshot=rule_snapshot,
        posting_rule_checksum=rule_checksum,
        payload=payload,
        payload_checksum=checksum,
        status=(
            VoucherPostingRequest.NOT_REQUIRED
            if effect == FinancePostingRule.NO_ENTRY
            else VoucherPostingRequest.PENDING
        ),
        requested_by=actor,
    )
    request.full_clean()
    request.save()
    return request


def _route_event_posting_or_resume(
    *, case, actor, request, resume_stage, action, idempotency_key, metadata=None, reason="",
):
    event_metadata = dict(metadata or {})
    if request is not None:
        event_metadata.update({
            "posting_request": str(request.public_id),
            "posting_event": request.kind,
            "posting_rule_checksum": request.posting_rule_checksum,
            "accounting_effect": request.posting_rule_snapshot.get("accounting_effect"),
        })
    if request is not None and request.status != VoucherPostingRequest.NOT_REQUIRED:
        return _advance(
            case,
            actor,
            VoucherCase.ACCOUNTING_EVENT_POSTING,
            action,
            idempotency_key,
            reason,
            event_metadata,
        )
    return _advance(case, actor, resume_stage, action, idempotency_key, reason, event_metadata)


@transaction.atomic
def supersede_discarded_event_posting_request(*, posting_request, actor, reason):
    """Create a numbered successor after a generated payment-event draft is discarded."""
    _require(actor, "accounting.prepare_journal_entries")
    request = VoucherPostingRequest.objects.select_for_update().select_related(
        "case", "posting_rule",
    ).get(pk=posting_request.pk)
    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    if request.kind not in {
        VoucherPostingRequest.PAYMENT,
        VoucherPostingRequest.REMITTANCE,
        VoucherPostingRequest.CANCELLATION,
        VoucherPostingRequest.REPLACEMENT,
        VoucherPostingRequest.REVERSAL,
    } or not request.resume_stage:
        raise VoucherWorkflowError("Only payment-event handoffs use the automatic successor-draft route.")
    if case.current_stage != VoucherCase.ACCOUNTING_EVENT_POSTING:
        raise VoucherWorkflowError("The voucher is no longer waiting at its payment-event Accounting handoff.")
    if request.status == VoucherPostingRequest.POSTED:
        raise VoucherWorkflowError("A posted payment-event request must be corrected through reversal, not draft replacement.")
    if request.posting_rule_snapshot.get("accounting_effect") != FinancePostingRule.JOURNAL_ENTRY:
        raise VoucherWorkflowError("A no-entry accounting decision cannot have a discarded draft JEV.")
    version = (
        case.posting_requests.filter(kind=request.kind).aggregate(value=Max("version"))["value"] or 0
    ) + 1
    jev_number = _consume_sequence_number(
        case,
        actor,
        "journal-entry",
        f"journal-entry-{request.kind}-{version}",
    )
    payload = dict(request.payload)
    payload["jev_number"] = jev_number
    payload_checksum = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    request.status = VoucherPostingRequest.CANCELLED
    request.failure_reason = reason.strip() or "Generated payment-event draft was discarded before posting."
    request.save(update_fields=("status", "failure_reason"))
    successor = VoucherPostingRequest(
        case=case,
        kind=request.kind,
        version=version,
        jev_number=jev_number,
        jev_date=request.jev_date,
        origin_stage=request.origin_stage,
        resume_stage=request.resume_stage,
        trigger_key=f"{request.trigger_key}:retry:{version}",
        finance_department_id=request.finance_department_id,
        finance_department_label=request.finance_department_label,
        posting_rule=request.posting_rule,
        posting_rule_public_id_snapshot=request.posting_rule_public_id_snapshot,
        posting_rule_snapshot=request.posting_rule_snapshot,
        posting_rule_checksum=request.posting_rule_checksum,
        payload=payload,
        payload_checksum=payload_checksum,
        requested_by=actor,
    )
    successor.full_clean()
    successor.save()
    if hasattr(request, "returned_instrument_review"):
        review = request.returned_instrument_review
        review.posting_request = successor
        review.state_version += 1
        review.save(update_fields=("posting_request", "state_version"))
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(
        case,
        actor,
        f"{request.kind}_jev_draft_replaced",
        case.current_stage,
        request.failure_reason,
        {
            "superseded_posting_request": str(request.public_id),
            "successor_posting_request": str(successor.public_id),
            "successor_jev_number": successor.jev_number,
        },
        f"payment-event-jev-draft-replaced-{successor.public_id}",
    )
    return successor


def _create_signature_round(case, voucher_date):
    signatories = FinanceSignatory.objects.filter(
        release=case.configuration_release, status="active", valid_from__lte=voucher_date,
    ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=voucher_date)).order_by("role_code", "pk")
    return _create_signature_round_from_signatories(case, signatories)


def _create_signature_round_from_signatories(case, signatories):
    previous_round = case.signature_tasks.order_by("-round_number").values_list("round_number", flat=True).first() or 0
    round_number = previous_round + 1
    signatories = list(signatories)
    for index, signatory in enumerate(signatories, start=1):
        WetSignatureTask.objects.create(
            case=case, round_number=round_number, sequence=index, role_code=signatory.role_code,
            signatory_name_snapshot=signatory.display_name, position_snapshot=signatory.position_title,
            custody_department=signatory.custody_department or signatory.department,
            custody_instructions=signatory.custody_instructions,
        )
    return round_number, bool(signatories)


def _signatory_snapshot(signatory):
    return {
        "assignment_id": signatory.pk,
        "release_id": signatory.release_id,
        "role_code": signatory.role_code,
        "display_name": signatory.display_name,
        "position_title": signatory.position_title,
        "acting": signatory.acting,
    }


@transaction.atomic
def create_budget_case(*, actor, requesting_department, payee, particulars, transaction_type, idempotency_key):
    _require(actor, "vouchers.initiate_budget_case")
    actor_department = department_for_user(actor)
    if VoucherEvent.objects.filter(idempotency_key=idempotency_key, actor=actor).exists():
        return VoucherEvent.objects.get(idempotency_key=idempotency_key, actor=actor).case
    release = _active_release()
    if payee.release_id != release.pk or payee.status != "active":
        raise VoucherWorkflowError("Select an active supplier/payee from the current Finance Setup release.")
    valid_type = FinanceConfigurationItem.objects.filter(
        release=release, status="active", category="transaction_type", code=transaction_type,
    ).exists()
    if not valid_type:
        raise VoucherWorkflowError("Select an approved transaction type from Finance Setup.")
    case = VoucherCase.objects.create(
        reference_code=f"CASE-{timezone.localdate():%Y}-{uuid.uuid4().hex[:10].upper()}",
        transaction_type=transaction_type, requesting_department=requesting_department,
        current_department=actor_department, configuration_release=release, payee=payee,
        payee_name=payee.display_name, particulars=particulars.strip(), created_by=actor,
    )
    VoucherTask.objects.create(case=case, stage=case.current_stage, department=actor_department, assigned_to=actor)
    _event(case, actor, "case_created", "", "", {"shadow_mode": True}, idempotency_key)
    return case


def _authoritative_obligation_snapshot(obligation):
    from budget.models import ObligationMovement, ObligationRequest
    from budget.services import obligation_lineage_request_ids

    obligation = ObligationRequest.objects.select_related("authorization").get(pk=obligation.pk)
    lineage_ids = obligation_lineage_request_ids(obligation)
    lineage = list(
        ObligationRequest.objects.filter(pk__in=lineage_ids, status=ObligationRequest.CERTIFIED)
        .order_by("obligation_date", "pk")
        .values("pk", "public_id", "obligation_number", "snapshot_checksum")
    )
    lines = list(
        ObligationMovement.objects.filter(request_id__in=lineage_ids)
        .values(
            "appropriation_line_id", "appropriation_line__fund_code",
            "appropriation_line__responsibility_center_code", "appropriation_line__account_code",
        )
        .annotate(amount=Sum("obligation_effect"))
        .filter(amount__gt=0)
        .order_by("appropriation_line_id")
    )
    amount = sum((item["amount"] for item in lines), Decimal("0.00"))
    checksum = hashlib.sha256(
        json.dumps(
            {"lineage": lineage, "lines": [{**item, "amount": str(item["amount"])} for item in lines]},
            sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
    ).hexdigest()
    return obligation, {"lineage": lineage, "lines": lines, "amount": amount, "checksum": checksum}


def _actor_label(actor):
    return actor.get_full_name().strip() or actor.get_username()


def _active_payable_allocations(case):
    from budget.models import PayableObligationAllocation

    return PayableObligationAllocation.objects.filter(
        voucher_case_public_id=case.public_id,
        status=PayableObligationAllocation.ACTIVE,
    ).select_related("obligation").order_by("obligation__obligation_number", "pk")


def payable_relationship_summary(case):
    rows = list(_active_payable_allocations(case))
    total = sum((row.allocated_amount for row in rows), Decimal("0.00"))
    obligation_case_counts = {}
    if rows:
        from budget.models import PayableObligationAllocation

        for item in PayableObligationAllocation.objects.filter(
            obligation_id__in={row.obligation_id for row in rows},
            status=PayableObligationAllocation.ACTIVE,
        ).values("obligation_id").annotate(case_count=Count("voucher_case_public_id", distinct=True)):
            obligation_case_counts[item["obligation_id"]] = item["case_count"]
    for row in rows:
        row.supports_multiple_cases = obligation_case_counts.get(row.obligation_id, 0) > 1
    return {
        "allocations": rows,
        "allocated_total": total,
        "claim_total": getattr(getattr(case, "payable_intake", None), "claim_amount", Decimal("0.00")),
        "difference": getattr(getattr(case, "payable_intake", None), "claim_amount", Decimal("0.00")) - total,
        "many_to_one": len(rows) > 1,
        "one_to_many": any(row.supports_multiple_cases for row in rows),
    }


def _validate_relationship_amount(*, relationship_type, amount, available):
    from budget.models import PayableObligationAllocation

    if amount <= Decimal("0.00"):
        raise VoucherWorkflowError("An active obligation allocation must be greater than zero.")
    if amount > available:
        raise VoucherWorkflowError("The allocation exceeds the obligation's unallocated claim capacity.")
    if relationship_type in (PayableObligationAllocation.FULL, PayableObligationAllocation.FINAL):
        if amount != available:
            raise VoucherWorkflowError(
                "A one-time/full or final allocation must consume the exact remaining obligation capacity. "
                "Post a governed pre-DV obligation adjustment first when a final claim is lower."
            )
    elif relationship_type in (PayableObligationAllocation.PARTIAL, PayableObligationAllocation.PROGRESS):
        if amount >= available:
            raise VoucherWorkflowError("A partial or progress allocation must leave a positive obligation balance.")
    else:
        raise VoucherWorkflowError("Choose a governed payable relationship type.")


def _write_payable_allocation(
    *, case, obligation_public_id, amount, relationship_type, actor, reason, replaces_public_id=None,
):
    """Write one allocation version under the authoritative Finance DB obligation lock."""
    from budget.models import ObligationRequest, PayableObligationAllocation

    if not reason.strip():
        raise VoucherWorkflowError("Record the reviewed reason for this payable allocation.")
    amount = Decimal(amount)
    with transaction.atomic(using="finance"):
        obligation = ObligationRequest.objects.select_for_update().get(public_id=obligation_public_id)
        if obligation.status != ObligationRequest.CERTIFIED or obligation.kind != ObligationRequest.ORIGINAL:
            raise VoucherWorkflowError("Select a certified original obligation.")
        if obligation.requesting_department_id != case.requesting_department_id:
            raise PermissionDenied
        obligation, snapshot = _authoritative_obligation_snapshot(obligation)
        prior = None
        if replaces_public_id:
            prior = PayableObligationAllocation.objects.select_for_update().filter(
                public_id=replaces_public_id,
                obligation=obligation,
                voucher_case_public_id=case.public_id,
                status=PayableObligationAllocation.ACTIVE,
            ).first()
            if not prior:
                raise VoucherWorkflowError("That payable allocation is no longer the active version. Reload the case.")
        elif PayableObligationAllocation.objects.filter(
            obligation=obligation,
            voucher_case_public_id=case.public_id,
            status=PayableObligationAllocation.ACTIVE,
        ).exists():
            raise VoucherWorkflowError("This obligation already has an active allocation in the case; revise it instead.")
        other_allocated = PayableObligationAllocation.objects.filter(
            obligation=obligation,
            status=PayableObligationAllocation.ACTIVE,
        )
        if prior:
            other_allocated = other_allocated.exclude(pk=prior.pk)
        other_total = other_allocated.aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0.00")
        available = snapshot["amount"] - other_total
        status = PayableObligationAllocation.ACTIVE
        if amount == Decimal("0.00"):
            if not prior:
                raise VoucherWorkflowError("A new allocation cannot start at zero.")
            status = PayableObligationAllocation.CANCELLED
            relationship_type = prior.relationship_type
        else:
            _validate_relationship_amount(
                relationship_type=relationship_type, amount=amount, available=available,
            )
        if prior:
            prior.status = PayableObligationAllocation.SUPERSEDED
            prior.full_clean()
            prior.save(update_fields=("status",))
        allocation = PayableObligationAllocation(
            department_id=obligation.department_id,
            department_label=obligation.department_label,
            obligation=obligation,
            voucher_case_public_id=case.public_id,
            voucher_reference_snapshot=case.reference_code,
            relationship_type=relationship_type,
            allocated_amount=amount,
            obligation_amount_snapshot=snapshot["amount"],
            obligation_checksum_snapshot=snapshot["checksum"],
            version=(prior.version + 1) if prior else 1,
            status=status,
            supersedes=prior,
            change_reason=reason.strip(),
            recorded_by_id=actor.pk,
            recorded_by_label=_actor_label(actor),
        )
        allocation.full_clean()
        allocation.save()
        if obligation.linked_voucher_case_public_id is None:
            ObligationRequest.objects.filter(pk=obligation.pk).update(
                linked_voucher_case_public_id=case.public_id,
            )
    return allocation, snapshot


def _distributed_allocation_lines(snapshot, allocated_amount):
    """Scale authoritative schedule lines into a non-authoritative compatibility projection exactly."""
    source_lines = list(snapshot["lines"])
    if not source_lines:
        return []
    source_total = snapshot["amount"]
    remaining = allocated_amount
    result = []
    for index, item in enumerate(source_lines):
        if index == len(source_lines) - 1:
            share = remaining
        else:
            share = (allocated_amount * item["amount"] / source_total).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            share = min(share, remaining)
        remaining -= share
        if share > 0:
            result.append((item, share))
    return result


def _rebuild_payable_projection(case):
    """Refresh the default-DB compatibility projection from active authoritative relationships."""
    allocations = list(_active_payable_allocations(case))
    if not allocations:
        if hasattr(case, "obligation"):
            case.obligation.allocation_lines.all().delete()
            case.obligation.delete()
        case.authoritative_obligation_public_id = None
        case.authoritative_obligation_number = ""
        case.authoritative_obligation_checksum = ""
        case.authoritative_obligation_amount = Decimal("0.00")
        case.obligation_binding_status = VoucherCase.BINDING_PENDING
        case.obligation_binding_error = "Add at least one obligation allocation before submission."
        case.save(update_fields=(
            "authoritative_obligation_public_id", "authoritative_obligation_number",
            "authoritative_obligation_checksum", "authoritative_obligation_amount",
            "obligation_binding_status", "obligation_binding_error", "updated_at",
        ))
        return
    snapshots = []
    for allocation in allocations:
        obligation, snapshot = _authoritative_obligation_snapshot(allocation.obligation)
        snapshots.append((allocation, obligation, snapshot))
    primary, primary_obligation, primary_snapshot = snapshots[0]
    case.authoritative_obligation_public_id = primary_obligation.public_id
    case.authoritative_obligation_number = primary_obligation.obligation_number
    case.authoritative_obligation_checksum = primary_snapshot["checksum"]
    case.authoritative_obligation_amount = primary_snapshot["amount"]
    case.obligation_binding_status = VoucherCase.BINDING_LINKED
    case.obligation_binding_error = ""
    case.save(update_fields=(
        "authoritative_obligation_public_id", "authoritative_obligation_number",
        "authoritative_obligation_checksum", "authoritative_obligation_amount",
        "obligation_binding_status", "obligation_binding_error", "updated_at",
    ))
    total = sum((allocation.allocated_amount for allocation, _obligation, _snapshot in snapshots), Decimal("0.00"))
    certifier = get_user_model().objects.filter(pk=primary_obligation.certified_by_id).first() or case.created_by
    projection, _created = BudgetObligation.objects.update_or_create(
        case=case,
        defaults={
            "obr_number": primary_obligation.obligation_number if len(snapshots) == 1 else f"MULTI/{case.reference_code}",
            "obligation_date": min(item[1].obligation_date for item in snapshots),
            "budget_source_reference": "F4.2 relationship projection: " + ", ".join(str(item[1].public_id) for item in snapshots),
            "certified_amount": total,
            "certified_by": certifier,
            "certified_at": primary_obligation.certified_at or timezone.now(),
            "source_kind": (
                "authoritative_f4_projection" if len(snapshots) == 1
                else "authoritative_f4_relationship_projection"
            ),
        },
    )
    projection.allocation_lines.all().delete()
    aggregated = {}
    for allocation, _obligation, snapshot in snapshots:
        for item, share in _distributed_allocation_lines(snapshot, allocation.allocated_amount):
            key = (
                item["appropriation_line__fund_code"],
                item["appropriation_line__responsibility_center_code"],
                item["appropriation_line__account_code"],
            )
            aggregated[key] = aggregated.get(key, Decimal("0.00")) + share
    for (fund_code, center_code, account_code), amount in aggregated.items():
        BudgetAllocationLine.objects.create(
            obligation=projection,
            fund_code=fund_code,
            responsibility_center_code=center_code,
            account_code=account_code,
            amount=amount,
        )


@transaction.atomic
def reconcile_authoritative_obligation(*, case, actor, expected_version, idempotency_key):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if department_for_user(actor).pk != case.requesting_department_id:
        raise PermissionDenied
    if case.current_stage != VoucherCase.PAYABLE_PREPARATION or hasattr(case, "disbursement_voucher"):
        raise VoucherWorkflowError(
            "Return the case to requesting-office payable preparation before reconciling obligation relationships."
        )
    rows = list(_active_payable_allocations(case))
    if not rows and not case.authoritative_obligation_public_id:
        raise VoucherWorkflowError("This case has no authoritative obligation handoff to reconcile.")
    try:
        if not rows:
            _write_payable_allocation(
                case=case,
                obligation_public_id=case.authoritative_obligation_public_id,
                amount=case.payable_intake.initial_allocation_amount,
                relationship_type=case.payable_intake.initial_relationship_type,
                actor=actor,
                reason="Recover the initial payable allocation after a partial cross-database handoff.",
            )
        else:
            for row in rows:
                _source, current = _authoritative_obligation_snapshot(row.obligation)
                if (
                    current["checksum"] != row.obligation_checksum_snapshot
                    or current["amount"] != row.obligation_amount_snapshot
                ):
                    _write_payable_allocation(
                        case=case,
                        obligation_public_id=row.obligation.public_id,
                        amount=row.allocated_amount,
                        relationship_type=row.relationship_type,
                        actor=actor,
                        reason="Reconcile the allocation snapshot after a governed pre-DV obligation correction.",
                        replaces_public_id=row.public_id,
                    )
        _rebuild_payable_projection(case)
    except Exception as exc:
        # Retain a visible recovery state; never let a cross-database partial handoff advance silently.
        case.obligation_binding_status = VoucherCase.BINDING_FAILED
        case.obligation_binding_error = str(exc)
        case.state_version += 1
        case.save(update_fields=("obligation_binding_status", "obligation_binding_error", "state_version", "updated_at"))
        _event(case, actor, "obligation_link_reconciliation_failed", case.current_stage, str(exc), {}, idempotency_key)
        return case
    case.refresh_from_db()
    case.obligation_binding_status = VoucherCase.BINDING_LINKED
    case.obligation_binding_error = ""
    case.state_version += 1
    case.save(update_fields=("obligation_binding_status", "obligation_binding_error", "state_version", "updated_at"))
    _event(case, actor, "obligation_link_reconciled", case.current_stage, "", {
        "allocation_count": _active_payable_allocations(case).count(),
        "allocated_total": str(payable_relationship_summary(case)["allocated_total"]),
    }, idempotency_key)
    return case


def create_payable_case_from_obligation(
    *, actor, authoritative_obligation, payee, transaction_type, claim_reference,
    invoice_number, invoice_date, claim_amount, procurement_reference, delivery_reference,
    inspection_acceptance_reference, evidence_reference, duplicate_review_note, idempotency_key,
    initial_allocation_amount=None, initial_relationship_type=PayableIntake.FULL,
):
    _require(actor, "vouchers.initiate_payable_case")
    actor_department = department_for_user(actor)
    if not actor_department:
        raise VoucherWorkflowError("Assign the user to the requesting department before payable intake.")
    existing = VoucherEvent.objects.filter(idempotency_key=idempotency_key, actor=actor).select_related("case").first()
    if existing:
        return existing.case
    obligation, snapshot = _authoritative_obligation_snapshot(authoritative_obligation)
    if obligation.status != obligation.CERTIFIED or obligation.kind != obligation.ORIGINAL:
        raise VoucherWorkflowError("Select a certified original obligation.")
    if obligation.requesting_department_id != actor_department.pk:
        raise PermissionDenied
    amount = Decimal(claim_amount)
    allocation_amount = Decimal(initial_allocation_amount if initial_allocation_amount is not None else claim_amount)
    if snapshot["amount"] <= 0 or allocation_amount > amount:
        raise VoucherWorkflowError("The initial obligation allocation must be positive and cannot exceed the claim control total.")
    release = _active_release()
    if payee.release_id != release.pk or payee.status != "active":
        raise VoucherWorkflowError("Select an active supplier/payee from the current Finance Setup release.")
    if not FinanceConfigurationItem.objects.filter(
        release=release, status="active", category="transaction_type", code=transaction_type,
    ).exists() and not FinanceTransactionVariant.objects.filter(
        release=release, status="active", code=transaction_type,
    ).exists():
        raise VoucherWorkflowError("Select an approved transaction type from Finance Setup.")
    duplicate_qs = PayableIntake.objects.filter(case__payee=payee)
    warnings = []
    if invoice_number and duplicate_qs.filter(invoice_number__iexact=invoice_number.strip()).exists():
        warnings.append(f"A payable for this payee already uses invoice {invoice_number.strip()}.")
    if duplicate_qs.filter(claim_reference__iexact=claim_reference.strip()).exists():
        warnings.append(f"A payable for this payee already uses claim reference {claim_reference.strip()}.")
    variant = FinanceTransactionVariant.objects.filter(
        release=release, status="active", code=transaction_type,
    ).prefetch_related("document_rules").first()
    initial_stage = VoucherCase.PAYABLE_PREPARATION if variant else VoucherCase.ACCOUNTING_PREPARATION
    initial_department = actor_department if variant else _department_for_permission(
        "vouchers.prepare_disbursement_voucher", actor_department,
    )
    if not variant and allocation_amount != amount:
        raise VoucherWorkflowError("A legacy transaction route cannot start with an unreconciled multi-obligation claim.")
    with transaction.atomic():
        case = VoucherCase.objects.create(
            reference_code=f"CASE-{timezone.localdate():%Y}-{uuid.uuid4().hex[:10].upper()}",
            transaction_type=transaction_type, requesting_department=actor_department,
            current_department=initial_department, configuration_release=release, payee=payee,
            payee_name=payee.display_name, particulars=obligation.particulars, created_by=actor,
            authoritative_obligation_public_id=obligation.public_id,
            authoritative_obligation_number=obligation.obligation_number,
            authoritative_obligation_checksum=snapshot["checksum"],
            authoritative_obligation_amount=snapshot["amount"],
            obligation_binding_status=VoucherCase.BINDING_PENDING,
            current_stage=initial_stage,
        )
        intake = PayableIntake(
            case=case, claim_reference=claim_reference.strip(), invoice_number=invoice_number.strip(),
            invoice_date=invoice_date, claim_amount=amount,
            initial_allocation_amount=allocation_amount,
            initial_relationship_type=initial_relationship_type,
            relationship_policy_snapshot={
                "variant_public_id": str(variant.public_id) if variant else "",
                "variant_code": variant.code if variant else transaction_type,
                "variant_kind": variant.kind if variant else "legacy",
                "authority_reference": variant.authority_reference if variant else "legacy configured route",
                "supported_relationships": [choice[0] for choice in PayableIntake.RELATIONSHIP_CHOICES],
                "recognition_decision_status": "routing decision only; F7 governs posting",
            },
            procurement_reference=procurement_reference.strip(), delivery_reference=delivery_reference.strip(),
            inspection_acceptance_reference=inspection_acceptance_reference.strip(),
            evidence_reference=evidence_reference.strip(), duplicate_warning=" ".join(warnings),
            duplicate_review_note=duplicate_review_note.strip(), prepared_by=actor,
        )
        intake.full_clean(); intake.save()
        if variant:
            for rule in variant.document_rules.all():
                PayableDocumentEvidence.objects.create(
                    case=case, source_rule=rule, rule_public_id_snapshot=rule.public_id,
                    requirement_code=rule.code, requirement_label=rule.label,
                    evidence_kind=rule.evidence_kind, required=rule.required,
                    waiver_allowed=rule.waiver_allowed,
                    condition_description=rule.condition_description,
                    authority_reference=rule.authority_reference,
                )
        VoucherTask.objects.create(
            case=case, stage=case.current_stage, department=initial_department, assigned_to=actor if variant else None,
        )
        _event(case, actor, "payable_intake_created", "", "", {
            "authoritative_obligation_public_id": str(obligation.public_id),
            "authoritative_obligation_checksum": snapshot["checksum"],
            "claim_amount": str(amount), "initial_allocation_amount": str(allocation_amount),
            "relationship_type": initial_relationship_type,
            "duplicate_warning": intake.duplicate_warning,
        }, idempotency_key)
    try:
        _write_payable_allocation(
            case=case,
            obligation_public_id=obligation.public_id,
            amount=allocation_amount,
            relationship_type=initial_relationship_type,
            actor=actor,
            reason="Initial allocation recorded with the requesting-office payable intake.",
        )
        _rebuild_payable_projection(case)
    except Exception as exc:
        with transaction.atomic():
            locked = VoucherCase.objects.select_for_update().get(pk=case.pk)
            locked.obligation_binding_status = VoucherCase.BINDING_FAILED
            locked.obligation_binding_error = str(exc)
            locked.save(update_fields=("obligation_binding_status", "obligation_binding_error", "updated_at"))
        return locked
    with transaction.atomic():
        locked = VoucherCase.objects.select_for_update().get(pk=case.pk)
        locked.obligation_binding_status = VoucherCase.BINDING_LINKED
        locked.obligation_binding_error = ""
        locked.save(update_fields=("obligation_binding_status", "obligation_binding_error", "updated_at"))
    return locked


def _validate_payable_freshness(case):
    if case.obligation_binding_status != VoucherCase.BINDING_LINKED:
        raise VoucherWorkflowError("Reconcile the authoritative obligation handoff before payable review.")
    rows = list(_active_payable_allocations(case))
    if not rows:
        raise VoucherWorkflowError("Add and reconcile at least one authoritative obligation allocation.")
    for row in rows:
        _source, current = _authoritative_obligation_snapshot(row.obligation)
        if (
            current["checksum"] != row.obligation_checksum_snapshot
            or current["amount"] != row.obligation_amount_snapshot
        ):
            raise VoucherWorkflowError(
                "An obligation changed through a governed pre-DV correction. "
                "Return to payable preparation and reconcile every allocation snapshot before continuing."
            )
    summary = payable_relationship_summary(case)
    if summary["difference"] != Decimal("0.00"):
        raise VoucherWorkflowError(
            "The payable claim control must equal its active obligation allocations exactly before submission. "
            f"Current difference: {summary['difference']}."
        )
    return summary


def _require_payable_modification_window(case, actor):
    if hasattr(case, "disbursement_voucher") or case.payment_instruments.exists():
        raise VoucherWorkflowError(
            "A DV or check has already been issued. Use the coordinated voucher/payment reversal or cancellation route."
        )
    if case.current_stage != VoucherCase.PAYABLE_PREPARATION:
        raise VoucherWorkflowError(
            "Return the case to requesting-office payable preparation before changing claim or obligation relationships."
        )
    if department_for_user(actor).pk != case.requesting_department_id:
        raise PermissionDenied


@transaction.atomic
def add_payable_obligation_allocation(
    *, case, obligation, allocation_amount, relationship_type, reason, actor,
    expected_version, idempotency_key,
):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_payable_modification_window(case, actor)
    current = payable_relationship_summary(case)
    amount = Decimal(allocation_amount)
    if current["allocated_total"] + amount > case.payable_intake.claim_amount:
        raise VoucherWorkflowError(
            "This allocation would exceed the payable claim control total. Revise the claim control first when supported by evidence."
        )
    allocation, snapshot = _write_payable_allocation(
        case=case,
        obligation_public_id=obligation.public_id,
        amount=amount,
        relationship_type=relationship_type,
        actor=actor,
        reason=reason,
    )
    _rebuild_payable_projection(case)
    case.refresh_from_db()
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(case, actor, "payable_obligation_allocation_added", case.current_stage, reason, {
        "allocation_public_id": str(allocation.public_id),
        "obligation_public_id": str(obligation.public_id),
        "allocated_amount": str(amount),
        "relationship_type": relationship_type,
        "obligation_checksum": snapshot["checksum"],
    }, idempotency_key)
    return case


@transaction.atomic
def revise_payable_obligation_allocation(
    *, case, allocation_public_id, revised_amount, relationship_type, reason, actor,
    expected_version, idempotency_key,
):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_payable_modification_window(case, actor)
    from budget.models import PayableObligationAllocation

    prior = PayableObligationAllocation.objects.filter(
        public_id=allocation_public_id,
        voucher_case_public_id=case.public_id,
        status=PayableObligationAllocation.ACTIVE,
    ).select_related("obligation").first()
    if not prior:
        raise VoucherWorkflowError("That obligation allocation is no longer active. Reload the case.")
    amount = Decimal(revised_amount)
    current = payable_relationship_summary(case)
    revised_total = current["allocated_total"] - prior.allocated_amount + amount
    if revised_total > case.payable_intake.claim_amount:
        raise VoucherWorkflowError("The revised allocations would exceed the payable claim control total.")
    successor, snapshot = _write_payable_allocation(
        case=case,
        obligation_public_id=prior.obligation.public_id,
        amount=amount,
        relationship_type=relationship_type,
        actor=actor,
        reason=reason,
        replaces_public_id=prior.public_id,
    )
    _rebuild_payable_projection(case)
    case.refresh_from_db()
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(case, actor, "payable_obligation_allocation_revised", case.current_stage, reason, {
        "prior_allocation_public_id": str(prior.public_id),
        "successor_allocation_public_id": str(successor.public_id),
        "obligation_public_id": str(prior.obligation.public_id),
        "prior_amount": str(prior.allocated_amount),
        "revised_amount": str(amount),
        "relationship_type": successor.relationship_type,
        "status": successor.status,
        "obligation_checksum": snapshot["checksum"],
    }, idempotency_key)
    return case


@transaction.atomic
def revise_payable_claim_control(
    *, case, claim_amount, reason, actor, expected_version, idempotency_key,
):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_payable_modification_window(case, actor)
    if not reason.strip():
        raise VoucherWorkflowError("Record the reviewed basis for the claim-control revision.")
    amount = Decimal(claim_amount)
    summary = payable_relationship_summary(case)
    if amount < summary["allocated_total"]:
        raise VoucherWorkflowError(
            "Reduce or remove obligation allocations before lowering the claim control below their current total."
        )
    intake = case.payable_intake
    prior = intake.claim_amount
    intake.claim_amount = amount
    intake.recognition_decision = ""
    intake.recognition_basis = ""
    intake.obligation_adjustment_decision = ""
    intake.obligation_adjustment_basis = ""
    intake.full_clean()
    intake.save(update_fields=(
        "claim_amount", "recognition_decision", "recognition_basis",
        "obligation_adjustment_decision", "obligation_adjustment_basis",
    ))
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(case, actor, "payable_claim_control_revised", case.current_stage, reason, {
        "prior_claim_amount": str(prior), "revised_claim_amount": str(amount),
        "allocated_total": str(summary["allocated_total"]),
    }, idempotency_key)
    return case


@transaction.atomic
def record_payable_document_evidence(
    *, case, evidence, actor, status, evidence_reference, decision_note,
    expected_version, idempotency_key,
):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if case.current_stage != VoucherCase.PAYABLE_PREPARATION:
        raise VoucherWorkflowError("Payable document evidence is editable only in requesting-office preparation.")
    if department_for_user(actor).pk != case.requesting_department_id or evidence.case_id != case.pk:
        raise PermissionDenied
    intake = case.payable_intake
    if intake.status not in (PayableIntake.DRAFT, PayableIntake.RETURNED):
        raise VoucherWorkflowError("This payable checklist is currently under review or already accepted.")
    evidence.status = status
    evidence.evidence_reference = evidence_reference.strip()
    evidence.decision_note = decision_note.strip()
    evidence.recorded_by = actor
    evidence.recorded_at = timezone.now()
    evidence.full_clean(); evidence.save()
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(case, actor, "payable_document_evidence_recorded", case.current_stage, "", {
        "requirement_code": evidence.requirement_code, "status": evidence.status,
        "rule_public_id": str(evidence.rule_public_id_snapshot),
    }, idempotency_key)
    return case


def _validate_payable_checklist(case):
    evidence = list(case.payable_document_evidence.all())
    if not evidence:
        raise VoucherWorkflowError("The configured transaction variant has no pinned documentary rules.")
    pending = [item.requirement_label for item in evidence if item.status == PayableDocumentEvidence.PENDING]
    if pending:
        raise VoucherWorkflowError("Resolve every documentary rule before submission: " + "; ".join(pending))
    invalid = []
    for item in evidence:
        allowed_statuses = {PayableDocumentEvidence.PRESENT}
        if item.waiver_allowed:
            allowed_statuses.add(PayableDocumentEvidence.WAIVED)
        if item.required and item.status not in allowed_statuses:
            invalid.append(item.requirement_label)
    if invalid:
        raise VoucherWorkflowError("Required evidence is unresolved: " + "; ".join(invalid))
    return evidence


@transaction.atomic
def submit_payable_intake(*, case, actor, expected_version, idempotency_key):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if case.current_stage != VoucherCase.PAYABLE_PREPARATION or department_for_user(actor).pk != case.requesting_department_id:
        raise VoucherWorkflowError("Only the recorded requesting office can submit this payable intake.")
    _validate_payable_freshness(case)
    evidence = _validate_payable_checklist(case)
    accounting_department = _department_for_permission("vouchers.review_payable_intake", None)
    if accounting_department is None:
        raise VoucherWorkflowError(
            "No active Accounting payable reviewer is assigned. Ask an administrator to configure the independent review role."
        )
    intake = case.payable_intake
    intake.status = PayableIntake.FOR_REVIEW
    intake.submitted_by, intake.submitted_at = actor, timezone.now()
    intake.reviewed_by = None
    intake.reviewed_at = None
    intake.decision_reason = ""
    intake.recognition_decision = ""
    intake.recognition_basis = ""
    intake.obligation_adjustment_decision = ""
    intake.obligation_adjustment_basis = ""
    intake.save(update_fields=(
        "status", "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "decision_reason",
        "recognition_decision", "recognition_basis",
        "obligation_adjustment_decision", "obligation_adjustment_basis",
    ))
    summary = payable_relationship_summary(case)
    return _advance(
        case, actor, VoucherCase.PAYABLE_REVIEW, "payable_submitted", idempotency_key,
        metadata={
            "claim_amount": str(intake.claim_amount), "allocated_total": str(summary["allocated_total"]),
            "allocation_count": len(summary["allocations"]), "document_rule_count": len(evidence),
        },
        destination_department=accounting_department,
    )


@transaction.atomic
def review_payable_intake(
    *, case, actor, decision, reason, expected_version, idempotency_key,
    recognition_decision=PayableIntake.RECOGNIZE_WITH_DV,
    recognition_basis="Legacy compatible recognition through the current governed DV/JEV route.",
    obligation_adjustment_decision=PayableIntake.NO_ADJUSTMENT,
    obligation_adjustment_basis="No separate obligation adjustment identified in this review.",
):
    _require(actor, "vouchers.review_payable_intake")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if case.current_stage != VoucherCase.PAYABLE_REVIEW:
        raise VoucherWorkflowError("This payable is not awaiting Accounting review.")
    if department_for_user(actor).pk != case.current_department_id:
        raise VoucherWorkflowError("Only the Accounting office currently assigned this payable may review it.")
    intake = case.payable_intake
    if intake.submitted_by_id == actor.pk or intake.prepared_by_id == actor.pk:
        raise VoucherWorkflowError("The requesting-office preparer cannot review the same payable intake.")
    reason = reason.strip()
    if not reason:
        raise VoucherWorkflowError("Record the Accounting review or return basis.")
    intake.reviewed_by, intake.reviewed_at, intake.decision_reason = actor, timezone.now(), reason
    if decision == PayableIntake.RETURNED:
        intake.status = PayableIntake.RETURNED
        intake.recognition_decision = ""
        intake.recognition_basis = ""
        intake.obligation_adjustment_decision = ""
        intake.obligation_adjustment_basis = ""
        intake.save(update_fields=(
            "status", "reviewed_by", "reviewed_at", "decision_reason",
            "recognition_decision", "recognition_basis",
            "obligation_adjustment_decision", "obligation_adjustment_basis",
        ))
        return _advance(
            case, actor, VoucherCase.PAYABLE_PREPARATION, "payable_returned", idempotency_key,
            reason=reason, destination_department=case.requesting_department,
        )
    if decision != PayableIntake.READY:
        raise VoucherWorkflowError("Choose a valid payable review decision.")
    _validate_payable_freshness(case)
    evidence = _validate_payable_checklist(case)
    intake.status = PayableIntake.READY
    intake.recognition_decision = recognition_decision
    intake.recognition_basis = recognition_basis.strip()
    intake.obligation_adjustment_decision = obligation_adjustment_decision
    intake.obligation_adjustment_basis = obligation_adjustment_basis.strip()
    intake.full_clean()
    intake.save(update_fields=(
        "status", "reviewed_by", "reviewed_at", "decision_reason",
        "recognition_decision", "recognition_basis",
        "obligation_adjustment_decision", "obligation_adjustment_basis",
    ))
    summary = payable_relationship_summary(case)
    return _advance(
        case, actor, VoucherCase.ACCOUNTING_PREPARATION, "payable_accepted", idempotency_key,
        reason=reason, metadata={
            "claim_amount": str(intake.claim_amount), "allocated_total": str(summary["allocated_total"]),
            "allocation_count": len(summary["allocations"]), "document_rule_count": len(evidence),
            "recognition_decision": intake.recognition_decision,
            "obligation_adjustment_decision": intake.obligation_adjustment_decision,
        },
    )


@transaction.atomic
def certify_budget(*, case, actor, obligation_date, budget_source_reference, allocations, expected_version, idempotency_key):
    _require(actor, "vouchers.certify_budget_obligation")
    _lock_case_foundation_boundary(case)
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_active_case_foundation(case)
    if case.current_stage != VoucherCase.BUDGET_DRAFT or hasattr(case, "obligation"):
        raise VoucherWorkflowError("Only a Budget draft without an OBR can be certified.")
    allocations = [item for item in allocations if Decimal(item["amount"]) > 0]
    total = sum((Decimal(item["amount"]) for item in allocations), Decimal("0.00"))
    if not allocations or total <= 0:
        raise VoucherWorkflowError("Enter at least one positive allocation line.")
    obr_number = _consume_number(case, actor, "obr")
    obligation = BudgetObligation.objects.create(
        case=case, obr_number=obr_number, obligation_date=obligation_date,
        budget_source_reference=budget_source_reference.strip(), certified_amount=total,
        certified_by=actor, certified_at=timezone.now(),
    )
    for item in allocations:
        BudgetAllocationLine.objects.create(
            obligation=obligation, fund_code=item["fund_code"],
            responsibility_center_code=item["responsibility_center_code"],
            account_code=item.get("account_code", ""), amount=Decimal(item["amount"]),
        )
    return _advance(case, actor, VoucherCase.ACCOUNTING_PREPARATION, "budget_certified", idempotency_key, metadata={"obr_number": obr_number, "certified_amount": str(total)})


@transaction.atomic
def prepare_voucher(*, case, actor, voucher_date, gross_amount, deductions, line_description, line_account_code, document_codes, expected_version, idempotency_key):
    _require(actor, "vouchers.prepare_disbursement_voucher")
    _lock_case_foundation_boundary(case)
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    _require_active_case_foundation(case)
    if case.current_stage != VoucherCase.ACCOUNTING_PREPARATION:
        raise VoucherWorkflowError("This case is not awaiting Accounting DV preparation.")
    if case.payable_document_evidence.exists() and case.payable_intake.status != PayableIntake.READY:
        raise VoucherWorkflowError("Accounting must accept the transaction-specific payable checklist before DV preparation.")
    if case.authoritative_obligation_public_id:
        _validate_payable_freshness(case)
    workflow_exemption = None
    if actor.pk == case.obligation.certified_by_id:
        exemption = workflow_exemption_for(
            actor=actor,
            control_code=FinanceWorkflowExemption.BUDGET_CERTIFIER_DV_PREPARATION,
            department_id=department_for_user(actor).pk,
        )
        if exemption is None:
            raise VoucherWorkflowError(
                "The Budget certifier cannot prepare the same DV unless an active administrator-authorized "
                "workflow exemption applies."
            )
        workflow_exemption = workflow_exemption_snapshot(exemption)
    gross = Decimal(gross_amount)
    deduction_total = sum((Decimal(item["amount"]) for item in deductions), Decimal("0.00"))
    net = gross - deduction_total
    if gross != case.obligation.certified_amount:
        raise VoucherWorkflowError("The DV gross amount must equal the certified OBR amount for this pilot workflow.")
    if net <= 0:
        raise VoucherWorkflowError("Deductions cannot reduce the voucher net amount to zero or below.")
    existing_voucher = getattr(case, "disbursement_voucher", None)
    dv_number = existing_voucher.dv_number if existing_voucher else _consume_number(case, actor, "disbursement-voucher")
    template = case.configuration_release.templates.filter(
        document_type="disbursement-voucher", status="active", preflighted_at__isnull=False,
    ).order_by("-version").first()
    case.voucher_template = template
    case.save(update_fields=("voucher_template", "updated_at"))
    if existing_voucher:
        voucher = existing_voucher
        prior_snapshot = {"gross": str(voucher.gross_amount), "deductions": str(voucher.total_deductions), "net": str(voucher.net_amount)}
        voucher.voucher_date, voucher.gross_amount, voucher.total_deductions, voucher.net_amount = voucher_date, gross, deduction_total, net
        voucher.prepared_by, voucher.prepared_at = actor, timezone.now()
        voucher.full_clean(); voucher.save()
        voucher.line_items.all().delete(); voucher.deductions.all().delete(); voucher.document_checks.all().delete()
    else:
        prior_snapshot = None
        voucher = DisbursementVoucher(
            case=case, dv_number=dv_number, voucher_date=voucher_date, gross_amount=gross,
            total_deductions=deduction_total, net_amount=net, prepared_by=actor, prepared_at=timezone.now(),
        )
        voucher.full_clean(); voucher.save()
    VoucherLineItem.objects.create(voucher=voucher, description=line_description.strip(), account_code=line_account_code, amount=gross)
    for item in deductions:
        tax_rule_item = item.get("tax_rule_item")
        tax_fields = {}
        if tax_rule_item is not None and (tax_rule_item.configuration or {}).get("reporting_enabled"):
            snapshot, checksum = finance_tax_rule_snapshot(tax_rule_item)
            if snapshot["applicability_status"] != "locally_confirmed":
                raise VoucherWorkflowError(
                    f"{tax_rule_item.label} is still a starter and cannot govern a voucher tax line."
                )
            tax_fields = {
                "tax_rule_item": tax_rule_item,
                "tax_base": Decimal(item["tax_base"]),
                "tax_rule_snapshot": snapshot,
                "tax_rule_checksum": checksum,
                "payee_name_snapshot": case.payee_name,
                "payee_tax_identifier_snapshot": case.payee.tax_identifier if case.payee_id else "",
            }
            tax_fields["tax_evidence_checksum"] = voucher_tax_evidence_checksum(
                voucher=voucher, tax_rule_checksum=checksum,
                tax_base=tax_fields["tax_base"], amount=Decimal(item["amount"]),
                payee_name=tax_fields["payee_name_snapshot"],
                payee_tax_identifier=tax_fields["payee_tax_identifier_snapshot"],
            )
        VoucherDeduction.objects.create(
            voucher=voucher, code=item["code"],
            description=item.get("description", item["code"]), amount=Decimal(item["amount"]),
            **tax_fields,
        )
    for code in document_codes:
        VoucherDocumentCheck.objects.create(voucher=voucher, requirement_code=code, label=code.replace("-", " ").title(), present=True, verified_by=actor, verified_at=timezone.now())
    round_number, has_signatories = _create_signature_round(case, voucher_date)
    next_stage = VoucherCase.AWAITING_SIGNATURES if has_signatories else VoucherCase.ACCOUNTING_VALIDATION
    metadata = {
        "dv_number": dv_number,
        "gross": str(gross),
        "net": str(net),
        "signature_round": round_number,
        "prior_amounts": prior_snapshot,
    }
    if workflow_exemption:
        metadata["workflow_exemption"] = workflow_exemption
    return _advance(
        case, actor, next_stage, "dv_corrected" if prior_snapshot else "dv_prepared",
        idempotency_key, metadata=metadata,
    )


@transaction.atomic
def record_signature_return(*, case, task, actor, note, expected_version, idempotency_key):
    _require(actor, "vouchers.track_wet_signatures")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    if case.current_stage != VoucherCase.AWAITING_SIGNATURES or task.case_id != case.pk or task.status != WetSignatureTask.PENDING:
        raise VoucherWorkflowError("This wet-signature task is not awaiting return.")
    print_job = None
    if case.voucher_template_id and case.voucher_template.controlled_print_required:
        print_job = case.print_jobs.filter(status=VoucherPrintJob.AWAITING_SIGNATURES).order_by("-version").first()
        if not print_job or print_job.signature_round != task.round_number or not case.tracepoint_item_id:
            raise VoucherWorkflowError(
                "Prepare and record the current signing copies, then assemble or verify their TracePoint packet before recording signatures."
            )
    earlier_pending = case.signature_tasks.filter(round_number=task.round_number, sequence__lt=task.sequence, status=WetSignatureTask.PENDING).exists()
    if earlier_pending:
        raise VoucherWorkflowError("Record wet signatures in their configured order.")
    task.status, task.recorded_by, task.recorded_at, task.note = WetSignatureTask.SIGNED_RETURNED, actor, timezone.now(), note.strip()
    task.save(update_fields=("status", "recorded_by", "recorded_at", "note"))
    if case.signature_tasks.filter(round_number=task.round_number, status=WetSignatureTask.PENDING).exists():
        case.state_version += 1
        case.save(update_fields=("state_version", "updated_at"))
        _event(case, actor, "wet_signature_returned", case.current_stage, note, {"role_code": task.role_code}, idempotency_key)
        return case
    if print_job:
        print_job.status = VoucherPrintJob.SIGNED_PACKET_RETURNED
        print_job.signed_returned_by = actor
        print_job.signed_returned_at = timezone.now()
        print_job.full_clean()
        print_job.save(update_fields=("status", "signed_returned_by", "signed_returned_at"))
    amendment = case.nonfinancial_amendments.filter(
        status=VoucherNonFinancialAmendment.AWAITING_SIGNATURES,
        signature_round_number=task.round_number,
    ).first()
    if amendment:
        amendment.status = VoucherNonFinancialAmendment.COMPLETED
        amendment.completed_at = timezone.now()
        amendment.save(update_fields=("status", "completed_at"))
        return _advance(
            case,
            actor,
            amendment.resume_stage,
            "nonfinancial_amendment_signatures_completed",
            idempotency_key,
            note,
            {"amendment_id": amendment.pk, "amendment_version": amendment.version},
        )
    return _advance(case, actor, VoucherCase.ACCOUNTING_VALIDATION, "wet_signatures_completed", idempotency_key, note)


@transaction.atomic
def amend_nonfinancial_voucher(*, case, actor, voucher_date, signatories, reason, expected_version, idempotency_key):
    """Change only the DV date/signatory evidence before any check has been issued."""
    _require(actor, "vouchers.amend_nonfinancial_voucher")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case.nonfinancial_amendments.get(pk=existing.metadata["amendment_id"])
    allowed_stages = {
        VoucherCase.AWAITING_SIGNATURES,
        VoucherCase.ACCOUNTING_VALIDATION,
        VoucherCase.ACCOUNTING_POSTING,
        VoucherCase.TREASURY_CHECK_PREPARATION,
    }
    if case.current_stage not in allowed_stages or not hasattr(case, "disbursement_voucher"):
        raise VoucherWorkflowError("This voucher is not at a stage where non-financial details can be amended.")
    if case.payment_instruments.exists():
        raise VoucherWorkflowError("A check has already been issued for this voucher. Its date and signatory evidence can no longer be amended here.")
    if case.nonfinancial_amendments.filter(status=VoucherNonFinancialAmendment.AWAITING_SIGNATURES).exists():
        raise VoucherWorkflowError("Complete the current replacement signature round before starting another amendment.")
    reason = reason.strip()
    if not reason:
        raise VoucherWorkflowError("Explain why the date or signatory assignment is being amended.")

    selected_ids = [item.pk for item in signatories]
    if not selected_ids:
        raise VoucherWorkflowError("Choose the approved signatories for the replacement signature round.")
    department_id = case.configuration_release.department_id
    approved_signatories = list(
        FinanceSignatory.objects.filter(
            pk__in=selected_ids,
            department_id=department_id,
            status="active",
            valid_from__lte=voucher_date,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=voucher_date)).order_by("role_code", "display_name", "pk")
    )
    if {item.pk for item in approved_signatories} != set(selected_ids):
        raise VoucherWorkflowError("Choose only active, approved signatories valid on the revised voucher date.")
    selected_roles = [item.role_code for item in approved_signatories]
    if len(selected_roles) != len(set(selected_roles)):
        raise VoucherWorkflowError("Choose exactly one approved person for each signature role.")

    latest_round = case.signature_tasks.order_by("-round_number").values_list("round_number", flat=True).first()
    old_tasks = list(case.signature_tasks.filter(round_number=latest_round).order_by("sequence", "pk")) if latest_round else []
    required_roles = {task.role_code for task in old_tasks}
    if required_roles and set(selected_roles) != required_roles:
        raise VoucherWorkflowError("Keep every required signature role and choose exactly one approved person for each.")
    old_signatories = [
        {
            "role_code": task.role_code,
            "display_name": task.signatory_name_snapshot,
            "position_title": task.position_snapshot,
            "status": task.status,
            "round_number": task.round_number,
        }
        for task in old_tasks
    ]
    new_signatories = [_signatory_snapshot(item) for item in approved_signatories]
    voucher = case.disbursement_voucher
    if voucher.voucher_date == voucher_date and [
        (item["role_code"], item["display_name"], item["position_title"])
        for item in old_signatories
    ] == [
        (item["role_code"], item["display_name"], item["position_title"])
        for item in new_signatories
    ]:
        raise VoucherWorkflowError("Change the voucher date or at least one signatory before saving the amendment.")

    financial_snapshot = {
        "gross_amount": str(voucher.gross_amount),
        "total_deductions": str(voucher.total_deductions),
        "net_amount": str(voucher.net_amount),
        "certified_amount": str(case.obligation.certified_amount),
    }
    prior_stage = case.current_stage
    resume_stage = VoucherCase.ACCOUNTING_VALIDATION if prior_stage == VoucherCase.AWAITING_SIGNATURES else prior_stage
    case.signature_tasks.filter(status=WetSignatureTask.PENDING).update(
        status=WetSignatureTask.DECLINED,
        note="Superseded by a non-financial date/signatory amendment.",
    )
    signature_round, has_signatories = _create_signature_round_from_signatories(case, approved_signatories)
    if not has_signatories:
        raise VoucherWorkflowError("At least one approved signatory is required.")
    old_date = voucher.voucher_date
    voucher.voucher_date = voucher_date
    voucher.save(update_fields=("voucher_date",))
    case.outputs.exclude(status=VoucherOutput.SUPERSEDED).update(status=VoucherOutput.SUPERSEDED)
    case.print_jobs.exclude(status=VoucherPrintJob.SUPERSEDED).update(
        status=VoucherPrintJob.SUPERSEDED,
        supersession_reason=reason,
    )
    version = (case.nonfinancial_amendments.aggregate(value=Max("version"))["value"] or 0) + 1
    amendment = VoucherNonFinancialAmendment.objects.create(
        case=case,
        version=version,
        prior_stage=prior_stage,
        resume_stage=resume_stage,
        signature_round_number=signature_round,
        old_voucher_date=old_date,
        new_voucher_date=voucher_date,
        old_signatories=old_signatories,
        new_signatories=new_signatories,
        financial_snapshot=financial_snapshot,
        reason=reason,
        amended_by=actor,
    )
    _advance(
        case,
        actor,
        VoucherCase.AWAITING_SIGNATURES,
        "voucher_nonfinancial_amended",
        idempotency_key,
        reason,
        {
            "amendment_id": amendment.pk,
            "amendment_version": amendment.version,
            "old_voucher_date": old_date.isoformat(),
            "new_voucher_date": voucher_date.isoformat(),
            "financial_snapshot": financial_snapshot,
            "resume_stage": resume_stage,
        },
    )
    return amendment


def _approved_override(case, action_code, actor):
    override = case.control_overrides.filter(action_code=action_code, requested_by=actor, status=ControlOverride.APPROVED).first()
    return override


@transaction.atomic
def validate_accounting(*, case, actor, jev_number, jev_date, note, expected_version, idempotency_key):
    _require(actor, "vouchers.validate_accounting_voucher")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    if case.current_stage != VoucherCase.ACCOUNTING_VALIDATION:
        raise VoucherWorkflowError("This voucher is not awaiting Accounting validation.")
    try:
        voucher = case.disbursement_voucher
    except DisbursementVoucher.DoesNotExist:
        raise VoucherWorkflowError("The prepared disbursement voucher is missing; stop and repair the case evidence.")
    try:
        obligation = case.obligation
    except BudgetObligation.DoesNotExist:
        raise VoucherWorkflowError("The certified-obligation record is missing; stop and repair the case evidence.")
    amount_difference = voucher.gross_amount - voucher.total_deductions - voucher.net_amount
    if amount_difference != 0:
        raise VoucherWorkflowError(
            f"DV gross less deductions must equal net before validation; the unexplained difference is {amount_difference:.2f}."
        )
    if voucher.gross_amount != obligation.certified_amount:
        raise VoucherWorkflowError("DV gross must equal the certified-obligation amount before validation.")
    allocation_total = obligation.allocation_lines.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if allocation_total != voucher.gross_amount:
        raise VoucherWorkflowError(
            f"Certified allocation lines must equal DV gross before validation; the control difference is "
            f"{allocation_total - voucher.gross_amount:.2f}."
        )
    if case.voucher_template_id and case.voucher_template.controlled_print_required:
        signed_job = case.print_jobs.filter(status=VoucherPrintJob.SIGNED_PACKET_RETURNED).order_by("-version", "-pk").first()
        latest_job = case.print_jobs.order_by("-version", "-pk").first()
        if not signed_job or latest_job.pk != signed_job.pk:
            raise VoucherWorkflowError("The latest controlled signing copy must return with its TracePoint-linked packet before validation.")
    workflow_exemption = None
    case_override = None
    if actor.pk == voucher.prepared_by_id:
        override = _approved_override(case, "accounting-self-validation", actor)
        if override:
            override.status = ControlOverride.USED
            override.save(update_fields=("status",))
            case_override = {
                "override_id": override.pk,
                "action_code": override.action_code,
                "reason": override.reason,
                "approved_by_id": override.approved_by_id,
            }
        else:
            exemption = workflow_exemption_for(
                actor=actor,
                control_code=FinanceWorkflowExemption.DV_PREPARER_SELF_VALIDATION,
                department_id=department_for_user(actor).pk,
            )
            if exemption is None:
                raise VoucherWorkflowError(
                    "The DV preparer cannot validate the same voucher without a separately approved case override "
                    "or an active administrator-authorized workflow exemption."
                )
            workflow_exemption = workflow_exemption_snapshot(exemption)
    try:
        intake = case.payable_intake
    except PayableIntake.DoesNotExist:
        intake = None
    if intake is not None and intake.status != PayableIntake.READY:
        raise VoucherWorkflowError("Accounting cannot post until the payable intake is payment-ready.")
    decision_event = {
        PayableIntake.RECOGNIZE_WITH_DV: FinancePostingRule.RECOGNITION,
        PayableIntake.LIQUIDATION_DECISION: FinancePostingRule.LIQUIDATION,
    }
    recognition_decision = intake.recognition_decision if intake is not None else "legacy_pre_f5_recognize_with_dv"
    recognition_basis = (
        intake.recognition_basis if intake is not None
        else "Legacy voucher route created without a payable-intake record; apply the pinned DV-validation rule."
    )
    if recognition_decision == PayableIntake.ACCRUE_BEFORE_SETTLEMENT:
        raise VoucherWorkflowError(
            "This case requires an earlier accrual JEV. Link that posted payable before settlement; do not record it again as DV recognition."
        )
    if recognition_decision == PayableIntake.SETTLE_EXISTING_PAYABLE:
        raise VoucherWorkflowError(
            "This case settles an existing payable. Link the prior posted payable before creating the settlement JEV."
        )
    event_kind = (
        FinancePostingRule.RECOGNITION
        if recognition_decision == "legacy_pre_f5_recognize_with_dv"
        else decision_event.get(recognition_decision)
    )
    if not event_kind:
        raise VoucherWorkflowError("The payable intake does not contain a supported governed recognition decision.")
    if not case.configuration_release_id:
        raise VoucherWorkflowError("This voucher has no pinned Finance Setup release for its posting policy.")
    variant = case.configuration_release.transaction_variants.filter(
        code=case.transaction_type, status__in=("approved", "scheduled", "active", "superseded"),
    ).first()
    if variant is None:
        raise VoucherWorkflowError(
            f"The pinned Finance Setup release has no governed transaction variant for '{case.transaction_type}'."
        )
    posting_rule = variant.posting_rules.filter(event_kind=event_kind).first()
    if posting_rule is None:
        raise VoucherWorkflowError(
            f"{variant.label} has no governed {event_kind} posting rule in the pinned Finance Setup release."
        )
    if event_kind == FinancePostingRule.RECOGNITION and posting_rule.recognition_point != FinancePostingRule.DV_VALIDATION:
        raise VoucherWorkflowError(
            "This recognition rule belongs to an earlier or later accounting point and cannot be silently executed at DV validation."
        )
    rule_snapshot, rule_checksum = posting_rule_snapshot(posting_rule)
    validation = AccountingValidation.objects.create(
        case=case, decision=AccountingValidation.ACCEPTED, jev_number=jev_number.strip(), jev_date=jev_date,
        note=note.strip(), validated_by=actor, validated_at=timezone.now(),
    )
    payload = {
        "schema_version": 3,
        "voucher_case_public_id": str(case.public_id),
        "voucher_reference": case.reference_code,
        "dv_number": voucher.dv_number,
        "jev_number": jev_number.strip(),
        "jev_date": jev_date.isoformat(),
        "transaction_type": case.transaction_type,
        "recognition_decision": recognition_decision,
        "recognition_basis": recognition_basis,
        "posting_rule_public_id": str(posting_rule.public_id),
        "posting_rule_checksum": rule_checksum,
        "payee_key": f"finance-party:{case.payee.code}" if case.payee_id else f"voucher-case:{case.public_id}",
        "payee_code": case.payee.code if case.payee_id else "",
        "payee_name": case.payee_name,
        "particulars": case.particulars,
        "gross_amount": str(voucher.gross_amount),
        "total_deductions": str(voucher.total_deductions),
        "net_amount": str(voucher.net_amount),
        "allocations": [
            {
                "fund_code": line.fund_code,
                "responsibility_center_code": line.responsibility_center_code,
                "account_code": line.account_code,
                "amount": str(line.amount),
            }
            for line in obligation.allocation_lines.order_by("pk")
        ],
        "deductions": [
            _deduction_payload(item)
            for item in voucher.deductions.order_by("pk")
        ],
    }
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    version = (
        case.posting_requests.filter(kind=event_kind).aggregate(value=Max("version"))["value"] or 0
    ) + 1
    department = department_for_user(actor)
    request = VoucherPostingRequest(
        case=case,
        kind=event_kind,
        version=version,
        jev_number=jev_number.strip(),
        jev_date=jev_date,
        origin_stage=VoucherCase.ACCOUNTING_VALIDATION,
        resume_stage=VoucherCase.TREASURY_CHECK_PREPARATION,
        trigger_key=f"accounting-validation:{validation.pk}",
        finance_department_id=department.pk,
        finance_department_label=department.name,
        posting_rule=posting_rule,
        posting_rule_public_id_snapshot=str(posting_rule.public_id),
        posting_rule_snapshot=rule_snapshot,
        posting_rule_checksum=rule_checksum,
        payload=payload,
        payload_checksum=checksum,
        requested_by=actor,
    )
    request.full_clean()
    request.save()
    event_metadata = {
        "jev_number": jev_number,
        "posting_request": str(request.public_id),
        "payload_checksum": checksum,
        "posting_rule": str(posting_rule.public_id),
        "posting_rule_checksum": rule_checksum,
    }
    if case_override:
        event_metadata["case_override"] = case_override
    if workflow_exemption:
        event_metadata["workflow_exemption"] = workflow_exemption
    return _advance(
        case, actor, VoucherCase.ACCOUNTING_POSTING, "accounting_validated", idempotency_key, note,
        event_metadata,
    )


@transaction.atomic
def issue_check(*, case, actor, bank_account_code, check_number, amount, expected_version, idempotency_key, replaces=None, fund_code=""):
    _require(actor, "vouchers.issue_payment_instruments")
    _lock_case_foundation_boundary(case)
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case.payment_instruments.get(public_id=existing.metadata["instrument_id"])
    _require_current_office(case, actor)
    _require_active_case_foundation(case)
    if case.current_stage != VoucherCase.TREASURY_CHECK_PREPARATION:
        raise VoucherWorkflowError("This voucher is not ready for Treasury check preparation.")
    try:
        amount = Decimal(amount)
    except (ArithmeticError, TypeError, ValueError):
        raise VoucherWorkflowError("Enter a valid check amount.")
    if not amount.is_finite() or amount <= Decimal("0.00") or amount.as_tuple().exponent < -2:
        raise VoucherWorkflowError("A check amount must be a positive amount stated to no more than two decimal places.")
    bank_account_code = (bank_account_code or "").strip()
    check_number = (check_number or "").strip()
    if not bank_account_code or not check_number:
        raise VoucherWorkflowError("Record both the governed bank account and the physical check number.")
    if not FinanceConfigurationItem.objects.filter(
        release=case.configuration_release,
        category="bank_account",
        code=bank_account_code,
        status="active",
    ).exists():
        raise VoucherWorkflowError("Choose an active bank/payment account from the voucher's pinned Finance Setup release.")
    from .cash_positions import preflight_instrument_cash, reserve_instrument_cash
    fund_code, cash_policy, cash_availability = preflight_instrument_cash(
        case=case, bank_account_code=bank_account_code, fund_code=fund_code, amount=amount,
    )
    if PaymentInstrument.objects.filter(bank_account_code=bank_account_code, check_number=check_number).exists():
        raise VoucherWorkflowError("That physical check number has already been registered for this bank account and cannot be reused.")
    if replaces is not None:
        replaces = PaymentInstrument.objects.select_for_update().get(pk=replaces.pk)
    replacement_statuses = {PaymentInstrument.CANCELLED, PaymentInstrument.BANK_RETURNED}
    if replaces and (
        replaces.case_id != case.pk or replaces.status not in replacement_statuses or hasattr(replaces, "replacement")
    ):
        raise VoucherWorkflowError("A replacement may reference only one unreplaced cancelled or bank-returned check from this voucher.")
    if replaces and replaces.status == PaymentInstrument.BANK_RETURNED:
        returned_review = replaces.returned_accounting_reviews.filter(
            status="ready_for_treasury", outcome="reissue",
        ).order_by("-version").first()
        if returned_review is None:
            raise VoucherWorkflowError("Accounting must complete the returned-item decision before Treasury issues a replacement.")
    active_total = case.payment_instruments.exclude(
        status__in=(PaymentInstrument.CANCELLED, PaymentInstrument.BANK_RETURNED),
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if active_total + amount > case.disbursement_voucher.net_amount:
        raise VoucherWorkflowError("Active checks cannot exceed the voucher net amount.")
    instrument = PaymentInstrument(
        case=case, bank_account_code=bank_account_code, fund_code=fund_code, check_number=check_number,
        amount=amount, status=PaymentInstrument.ISSUED, replaces=replaces,
        issued_by=actor, issued_at=timezone.now(),
    )
    instrument.full_clean()
    instrument.save()
    reserve_instrument_cash(
        instrument=instrument, actor=actor, policy=cash_policy, availability=cash_availability,
    )
    if replaces and replaces.status == PaymentInstrument.BANK_RETURNED:
        from .advice import complete_returned_review_on_replacement
        complete_returned_review_on_replacement(
            original_instrument=replaces, replacement=instrument, actor=actor,
        )
    event_kind = FinancePostingRule.REPLACEMENT if replaces else FinancePostingRule.PAYMENT
    recognition_point = (
        FinancePostingRule.PAYMENT_REPLACEMENT if replaces else FinancePostingRule.PAYMENT_ISSUANCE
    )
    posting_request = _create_event_posting_request(
        case=case,
        actor=actor,
        event_kind=event_kind,
        recognition_point=recognition_point,
        event_date=timezone.localdate(instrument.issued_at),
        event_amount=instrument.amount,
        bank_account_code=instrument.bank_account_code,
        trigger_key=f"payment-instrument:{instrument.public_id}:issued",
        trigger={
            "type": "payment_instrument_issued",
            "instrument_public_id": str(instrument.public_id),
            "check_number": instrument.check_number,
            "replaces_instrument_public_id": str(replaces.public_id) if replaces else "",
        },
        resume_stage=VoucherCase.TREASURY_CHECK_PREPARATION,
    )
    _route_event_posting_or_resume(
        case=case,
        actor=actor,
        request=posting_request,
        resume_stage=VoucherCase.TREASURY_CHECK_PREPARATION,
        action="replacement_check_issued" if replaces else "check_issued",
        idempotency_key=idempotency_key,
        metadata={
            "instrument_id": str(instrument.public_id),
            "check_number": check_number,
            "amount": str(amount),
            "replaces_instrument_id": str(replaces.public_id) if replaces else "",
        },
    )
    return instrument


@transaction.atomic
def submit_checks_for_advice(*, case, actor, expected_version, idempotency_key):
    _require(actor, "vouchers.issue_payment_instruments")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    if case.current_stage != VoucherCase.TREASURY_CHECK_PREPARATION:
        raise VoucherWorkflowError("Only the currently assigned Treasury check-preparation case may be sent to bank advice.")
    issued = case.payment_instruments.filter(status=PaymentInstrument.ISSUED)
    total = issued.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if not issued.exists() or total != case.disbursement_voucher.net_amount:
        raise VoucherWorkflowError("Issued checks must exactly equal the voucher net amount before bank advice.")
    if issued.values("bank_account_code").distinct().count() != 1:
        raise VoucherWorkflowError("A pilot voucher's checks must use one bank account per advice batch.")
    return _advance(case, actor, VoucherCase.ACCOUNTING_BANK_ADVICE, "checks_submitted_for_advice", idempotency_key, metadata={"check_total": str(total)})


@transaction.atomic
def finalize_bank_advice(
    *, case, actor, advice_number, advice_date, expected_version, idempotency_key,
    preparation_note="", authority_reference="", local_applicability_note="",
):
    _require(actor, "vouchers.prepare_bank_advice")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return BankAdviceBatch.objects.get(public_id=existing.metadata["batch_id"])
    _require_current_office(case, actor)
    if case.current_stage != VoucherCase.ACCOUNTING_BANK_ADVICE:
        raise VoucherWorkflowError("This voucher is not awaiting Accounting bank advice.")
    instruments = list(case.payment_instruments.filter(status=PaymentInstrument.ISSUED))
    if not instruments:
        raise VoucherWorkflowError("There are no issued checks eligible for bank advice.")
    from .advice import create_advice_batch, submit_advice_for_review
    batch = create_advice_batch(
        actor=actor, advice_number=advice_number, advice_date=advice_date,
        instruments=instruments,
        preparation_note=preparation_note or "Prepared from the shared voucher case after issued-instrument control totals reconciled.",
        authority_reference=authority_reference or "Pending locally reviewed bank-advice authority; complete in the bank-advice workspace before approval.",
        local_applicability_note=local_applicability_note or "Controlled UAT preparation only; named Accounting, Treasury, bank, and audit owners must confirm the accepted procedure.",
    )
    submit_advice_for_review(batch=batch, actor=actor, expected_version=batch.state_version)
    _advance(
        case, actor, VoucherCase.ACCOUNTING_BANK_ADVICE, "bank_advice_prepared_for_review",
        idempotency_key, metadata={"batch_id": str(batch.public_id), "advice_number": advice_number},
    )
    return batch


@transaction.atomic
def release_check(*, case, instrument, actor, claimant, receipt_reference, expected_version, idempotency_key):
    _require(actor, "vouchers.release_payment_instruments")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    instrument = PaymentInstrument.objects.select_for_update().select_related(
        "current_advice_batch",
    ).get(pk=instrument.pk)
    claimant = FinancePartyClaimant.objects.select_for_update().get(pk=claimant.pk)
    if case.current_stage != VoucherCase.TREASURY_RELEASE or instrument.case_id != case.pk or instrument.status != PaymentInstrument.ADVISED:
        raise VoucherWorkflowError("Only an advised check in Treasury's release queue may be released.")
    if not instrument.current_advice_batch_id or instrument.current_advice_batch.status != BankAdviceBatch.ACKNOWLEDGED:
        raise VoucherWorkflowError("Record the bank's acknowledgement of the current advice version before releasing this check.")
    if instrument.operational_status in (PaymentInstrument.STALE, PaymentInstrument.RETURNED):
        raise VoucherWorkflowError("This instrument has an open stale/returned exception and cannot be released.")
    today = timezone.localdate()
    if (
        claimant.party_id != case.payee_id or claimant.status != "active"
        or claimant.valid_from > today
        or (claimant.valid_to is not None and claimant.valid_to < today)
    ):
        raise VoucherWorkflowError("Select an active authorized claimant for this payee.")
    receipt_reference = (receipt_reference or "").strip()
    if not receipt_reference:
        raise VoucherWorkflowError("Record the actual claimant receipt or release reference.")
    instrument.status = PaymentInstrument.RELEASED
    instrument.released_by, instrument.released_at = actor, timezone.now()
    instrument.released_to_claimant, instrument.released_to = claimant, claimant.display_name
    instrument.receipt_reference = receipt_reference
    instrument.save(update_fields=("status", "released_by", "released_at", "released_to_claimant", "released_to", "receipt_reference"))
    from .cash_positions import close_reservation, resolve_instrument_exception
    close_reservation(
        instrument=instrument, actor=actor, status=TreasuryCashReservation.CONSUMED,
        reason=f"Released to authorized claimant; receipt {instrument.receipt_reference}",
    )
    for exception in instrument.exceptions.filter(
        status=PaymentInstrumentException.OPEN, kind=PaymentInstrumentException.UNCLAIMED,
    ):
        resolve_instrument_exception(
            exception=exception, actor=actor,
            resolution=f"Released to authorized claimant; receipt {instrument.receipt_reference}",
            permission_required=False,
        )
    remaining = case.payment_instruments.exclude(
        status__in=(PaymentInstrument.RELEASED, PaymentInstrument.CANCELLED),
    ).exists()
    resume_stage = VoucherCase.TREASURY_RELEASE if remaining else VoucherCase.COMPLETED
    posting_request = _create_event_posting_request(
        case=case,
        actor=actor,
        event_kind=FinancePostingRule.PAYMENT,
        recognition_point=FinancePostingRule.PAYMENT_RELEASE,
        event_date=timezone.localdate(instrument.released_at),
        event_amount=instrument.amount,
        bank_account_code=instrument.bank_account_code,
        trigger_key=f"payment-instrument:{instrument.public_id}:released",
        trigger={
            "type": "payment_instrument_released",
            "instrument_public_id": str(instrument.public_id),
            "check_number": instrument.check_number,
            "claimant_id": claimant.pk,
            "receipt_reference": instrument.receipt_reference,
        },
        resume_stage=resume_stage,
    )
    return _route_event_posting_or_resume(
        case=case,
        actor=actor,
        request=posting_request,
        resume_stage=resume_stage,
        action="check_released" if remaining else "disbursement_completed",
        idempotency_key=idempotency_key,
        metadata={
            "instrument_id": str(instrument.public_id),
            "check_number": instrument.check_number,
            "receipt_reference": instrument.receipt_reference,
        },
    )


@transaction.atomic
def cancel_check(*, case, instrument, actor, reason, expected_version, idempotency_key):
    _require(actor, "vouchers.manage_payment_exceptions")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    instrument = PaymentInstrument.objects.select_for_update().get(pk=instrument.pk)
    if instrument.case_id != case.pk or instrument.status not in {PaymentInstrument.ISSUED, PaymentInstrument.ADVISED}:
        raise VoucherWorkflowError("Only an issued or advised, unreleased check can be cancelled.")
    if not reason.strip():
        raise VoucherWorkflowError("A cancellation reason is required.")
    instrument.status, instrument.cancelled_by, instrument.cancelled_at = PaymentInstrument.CANCELLED, actor, timezone.now()
    instrument.cancellation_reason = reason.strip()
    instrument.save(update_fields=("status", "cancelled_by", "cancelled_at", "cancellation_reason"))
    from .cash_positions import close_reservation, resolve_instrument_exception
    close_reservation(
        instrument=instrument, actor=actor, status=TreasuryCashReservation.RELEASED,
        reason=f"Instrument cancelled: {instrument.cancellation_reason}",
    )
    for exception in instrument.exceptions.filter(status=PaymentInstrumentException.OPEN):
        resolve_instrument_exception(
            exception=exception, actor=actor,
            resolution=f"Instrument cancelled; follow the controlled replacement/accounting route. {instrument.cancellation_reason}",
            permission_required=False,
        )
    posting_request = _create_event_posting_request(
        case=case,
        actor=actor,
        event_kind=FinancePostingRule.CANCELLATION,
        recognition_point=FinancePostingRule.PAYMENT_CANCELLATION,
        event_date=timezone.localdate(instrument.cancelled_at),
        event_amount=instrument.amount,
        bank_account_code=instrument.bank_account_code,
        trigger_key=f"payment-instrument:{instrument.public_id}:cancelled",
        trigger={
            "type": "payment_instrument_cancelled",
            "instrument_public_id": str(instrument.public_id),
            "check_number": instrument.check_number,
            "reason": instrument.cancellation_reason,
        },
        resume_stage=VoucherCase.TREASURY_CHECK_PREPARATION,
    )
    return _route_event_posting_or_resume(
        case=case,
        actor=actor,
        request=posting_request,
        resume_stage=VoucherCase.TREASURY_CHECK_PREPARATION,
        action="check_cancelled",
        idempotency_key=idempotency_key,
        reason=reason,
        metadata={
            "instrument_id": str(instrument.public_id),
            "check_number": instrument.check_number,
        },
    )


@transaction.atomic
def return_case(*, case, actor, target_stage, reason, expected_version, idempotency_key):
    _require(actor, "vouchers.return_voucher_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    _require_current_office(case, actor)
    allowed = {
        VoucherCase.ACCOUNTING_PREPARATION: {VoucherCase.PAYABLE_PREPARATION},
        VoucherCase.AWAITING_SIGNATURES: {VoucherCase.ACCOUNTING_PREPARATION},
        VoucherCase.ACCOUNTING_VALIDATION: {VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.AWAITING_SIGNATURES},
        VoucherCase.ACCOUNTING_POSTING: {VoucherCase.ACCOUNTING_VALIDATION},
        VoucherCase.TREASURY_CHECK_PREPARATION: {VoucherCase.ACCOUNTING_VALIDATION},
        VoucherCase.ACCOUNTING_BANK_ADVICE: {VoucherCase.TREASURY_CHECK_PREPARATION},
        VoucherCase.TREASURY_RELEASE: {VoucherCase.TREASURY_CHECK_PREPARATION, VoucherCase.ACCOUNTING_BANK_ADVICE},
    }
    if target_stage not in allowed.get(case.current_stage, set()) or not reason.strip():
        raise VoucherWorkflowError("Choose an allowed earlier stage and record the correction reason.")
    if target_stage == VoucherCase.PAYABLE_PREPARATION:
        if hasattr(case, "disbursement_voucher") or case.payment_instruments.exists():
            raise VoucherWorkflowError(
                "A DV or check already exists; use the later voucher/payment correction route instead of reopening payable allocations."
            )
        intake = case.payable_intake
        intake.status = PayableIntake.RETURNED
        intake.reviewed_by = actor
        intake.reviewed_at = timezone.now()
        intake.decision_reason = reason.strip()
        intake.recognition_decision = ""
        intake.recognition_basis = ""
        intake.obligation_adjustment_decision = ""
        intake.obligation_adjustment_basis = ""
        intake.save(update_fields=(
            "status", "reviewed_by", "reviewed_at", "decision_reason",
            "recognition_decision", "recognition_basis",
            "obligation_adjustment_decision", "obligation_adjustment_basis",
        ))
    if target_stage in {VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.ACCOUNTING_VALIDATION}:
        if case.posting_requests.filter(status=VoucherPostingRequest.POSTED).exists():
            raise VoucherWorkflowError("This voucher already has a posted JEV. Use an adjusting/reversal entry and a replacement case instead of rewriting it.")
        materialized = case.posting_requests.filter(status=VoucherPostingRequest.MATERIALIZED).exists()
        if materialized:
            raise VoucherWorkflowError("Discard the draft GRAND JEV before returning this voucher for correction.")
        case.posting_requests.filter(status=VoucherPostingRequest.PENDING).update(status=VoucherPostingRequest.CANCELLED)
    if target_stage == VoucherCase.ACCOUNTING_PREPARATION:
        case.signature_tasks.filter(status=WetSignatureTask.PENDING).update(status=WetSignatureTask.DECLINED, note="Superseded by a correction round.")
    elif target_stage == VoucherCase.AWAITING_SIGNATURES:
        case.signature_tasks.filter(status=WetSignatureTask.PENDING).update(status=WetSignatureTask.DECLINED, note="Superseded by a correction round.")
        _create_signature_round(case, case.disbursement_voucher.voucher_date)
    return _advance(
        case, actor, target_stage, "returned_for_correction", idempotency_key, reason,
        destination_department=case.requesting_department if target_stage == VoucherCase.PAYABLE_PREPARATION else None,
    )


@transaction.atomic
def request_override(*, case, actor, action_code, reason):
    if not reason.strip():
        raise VoucherWorkflowError("An emergency override request requires a reason.")
    return ControlOverride.objects.create(case=case, action_code=action_code, reason=reason.strip(), requested_by=actor)


@transaction.atomic
def approve_override(*, override, actor):
    _require(actor, "vouchers.approve_control_overrides")
    override = ControlOverride.objects.select_for_update().get(pk=override.pk)
    if override.status != ControlOverride.PENDING or actor.pk == override.requested_by_id:
        raise VoucherWorkflowError("A different authorized user must approve a pending override.")
    override.status, override.approved_by, override.approved_at = ControlOverride.APPROVED, actor, timezone.now()
    override.save(update_fields=("status", "approved_by", "approved_at"))
    return override


@transaction.atomic
def link_tracepoint_item(*, case, item, actor, expected_version, idempotency_key):
    _require(actor, "vouchers.link_tracepoint_custody")
    from tracepoint.access import packet_is_visible

    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if case.tracepoint_item_id:
        raise VoucherWorkflowError("This voucher already has a TracePoint item link.")
    if hasattr(item, "voucher_case") or not packet_is_visible(actor, item.current_packet):
        raise VoucherWorkflowError("Choose an unlinked TracePoint item visible to this employee.")
    case.tracepoint_item = item
    case.state_version += 1
    case.save(update_fields=("tracepoint_item", "state_version", "updated_at"))
    _event(case, actor, "tracepoint_item_linked", case.current_stage, "", {"reference_number": item.reference_number}, idempotency_key)
    return case


@transaction.atomic
def generate_shadow_dv(*, case, actor, idempotency_key):
    _require(actor, "vouchers.prepare_disbursement_voucher")
    case = VoucherCase.objects.select_for_update().select_related(
        "voucher_template", "disbursement_voucher__prepared_by", "obligation__certified_by",
    ).get(pk=case.pk)
    existing_event = case.events.filter(idempotency_key=idempotency_key).first()
    if existing_event:
        return VoucherOutput.objects.get(pk=existing_event.metadata["output_id"])
    if not hasattr(case, "disbursement_voucher") or not case.voucher_template_id:
        raise VoucherWorkflowError("A prepared DV with a pinned, preflighted workbook is required.")
    template = case.voucher_template
    try:
        verify_template_evidence(template)
        template.workbook.open("rb")
        payload = template.workbook.read()
        template.workbook.close()
        workbook, _mapping, _result = inspect_finance_workbook(payload, template.document_type)
    except FinanceTemplateError as exc:
        raise VoucherWorkflowError(str(exc)) from exc
    voucher = case.disbursement_voucher
    latest_signature_round = case.signature_tasks.order_by("-round_number").values_list("round_number", flat=True).first()
    signature_tasks = list(
        case.signature_tasks.filter(round_number=latest_signature_round).order_by("sequence", "pk")
    ) if latest_signature_round else []
    approval_task = next((task for task in signature_tasks if task.role_code == "department-head"), None)
    if approval_task is None and signature_tasks:
        approval_task = signature_tasks[-1]
    values = {
        "GRAND_DV_NUMBER": voucher.dv_number,
        "GRAND_DV_DATE": voucher.voucher_date,
        "GRAND_PAYEE": case.payee_name,
        "GRAND_PARTICULARS": case.particulars,
        "GRAND_GROSS_AMOUNT": voucher.gross_amount,
        "GRAND_TOTAL_DEDUCTIONS": voucher.total_deductions,
        "GRAND_NET_AMOUNT": voucher.net_amount,
        "GRAND_PREPARED_BY": voucher.prepared_by.get_full_name() or voucher.prepared_by.username,
        "GRAND_CERTIFIED_BY": case.obligation.certified_by.get_full_name() or case.obligation.certified_by.username,
        "GRAND_APPROVED_BY": approval_task.signatory_name_snapshot if approval_task else "WET SIGNATURE — VERIFY ORIGINAL",
    }
    for name, value in values.items():
        sheet, coordinate = _destination(workbook, name)
        target = sheet[coordinate]
        if isinstance(target, tuple):
            target = target[0][0] if isinstance(target[0], tuple) else target[0]
        target.value = value
    sheet, coordinate = _destination(workbook, "GRAND_LINE_ITEMS")
    cells = sheet[coordinate]
    if cells and not isinstance(cells[0], tuple):
        cells = (cells,)
    rows = list(voucher.line_items.all())
    if len(rows) > len(cells):
        raise VoucherWorkflowError("The pinned DV template does not have enough controlled line rows.")
    for row_index, item in enumerate(rows):
        row = cells[row_index]
        values_for_row = (item.description, item.account_code, item.amount)
        for column_index, cell in enumerate(row):
            cell.value = values_for_row[column_index] if column_index < len(values_for_row) else None
    stream = io.BytesIO()
    workbook.save(stream)
    output_payload = stream.getvalue()
    version = (case.outputs.filter(output_type="disbursement-voucher").order_by("-version").values_list("version", flat=True).first() or 0) + 1
    snapshot = {
        "case": str(case.public_id), "case_state_version": case.state_version,
        "obr_number": case.obligation.obr_number, "dv_number": voucher.dv_number,
        "gross_amount": str(voucher.gross_amount), "deductions": str(voucher.total_deductions),
        "net_amount": str(voucher.net_amount), "template_checksum": template.workbook_checksum,
        "signature_round": latest_signature_round,
        "signatories": [
            {
                "role_code": task.role_code,
                "display_name": task.signatory_name_snapshot,
                "position_title": task.position_snapshot,
            }
            for task in signature_tasks
        ],
    }
    output = VoucherOutput(
        case=case, output_type="disbursement-voucher", version=version, template=template,
        checksum=hashlib.sha256(output_payload).hexdigest(), input_snapshot=snapshot,
        status=VoucherOutput.SHADOW, generated_by=actor,
    )
    output.file.save(f"{case.reference_code}-DV-shadow-v{version}.xlsx", ContentFile(output_payload), save=False)
    output.full_clean(); output.save()
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(case, actor, "shadow_dv_generated", case.current_stage, "", {"output_id": output.pk, "checksum": output.checksum}, idempotency_key)
    return output


def _supersede_print_job(job, reason):
    job.status = VoucherPrintJob.SUPERSEDED
    job.supersession_reason = reason.strip()
    job.full_clean()
    job.save(update_fields=("status", "supersession_reason"))
    if job.output.status != VoucherOutput.SUPERSEDED:
        job.output.status = VoucherOutput.SUPERSEDED
        job.output.save(update_fields=("status",))


@transaction.atomic
def prepare_controlled_dv_print(*, case, actor, replacement_reason, expected_version, idempotency_key):
    _require(actor, "vouchers.control_dv_printing")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return VoucherPrintJob.objects.get(pk=existing.metadata["print_job_id"])
    _require_current_office(case, actor)
    if not hasattr(case, "disbursement_voucher") or not case.voucher_template_id:
        raise VoucherWorkflowError("Prepare the DV and pin a preflighted workbook before creating a signing copy.")
    if case.current_stage != VoucherCase.AWAITING_SIGNATURES:
        raise VoucherWorkflowError("Controlled signing copies are prepared only in the DV printing and wet-signature step.")
    if case.payment_instruments.exists():
        raise VoucherWorkflowError("A check already exists. Use the coordinated payment correction route instead of reprinting the DV here.")
    print_jobs = case.print_jobs.select_for_update()
    latest = print_jobs.order_by("-version", "-pk").first()
    active = print_jobs.filter(
        status__in=(
            VoucherPrintJob.READY_TO_PRINT,
            VoucherPrintJob.PRINTED,
            VoucherPrintJob.AWAITING_SIGNATURES,
        )
    ).first()
    reason = replacement_reason.strip()
    if active and not reason:
        raise VoucherWorkflowError("Explain why the earlier signing copy must be replaced and marked do-not-sign.")
    if active:
        if active.status in {VoucherPrintJob.PRINTED, VoucherPrintJob.AWAITING_SIGNATURES}:
            case.signature_tasks.filter(
                round_number=active.signature_round,
                status=WetSignatureTask.PENDING,
            ).update(status=WetSignatureTask.DECLINED, note="Superseded by a controlled DV reprint.")
            _create_signature_round(case, case.disbursement_voucher.voucher_date)
        _supersede_print_job(active, reason)
    predecessor = active or (latest if latest and latest.status == VoucherPrintJob.SUPERSEDED else None)
    if predecessor and not reason:
        reason = predecessor.supersession_reason
    output = generate_shadow_dv(
        case=case,
        actor=actor,
        idempotency_key=f"{idempotency_key}:controlled-output",
    )
    case.refresh_from_db()
    output.file.open("rb")
    try:
        archived = archive_export(
            content=output.file.read(),
            department=case.configuration_release.department,
            user=actor,
            category="finance-dv-signing-copies",
            filename=output.file.name.rsplit("/", 1)[-1],
            metadata={
                "kind": "controlled_dv_signing_copy",
                "case_public_id": str(case.public_id),
                "case_reference": case.reference_code,
                "print_version": (case.print_jobs.aggregate(value=Max("version"))["value"] or 0) + 1,
                "output_id": output.pk,
                "template_id": output.template_id,
                "template_checksum": output.template.workbook_checksum,
                "form_status": output.template.form_status,
                "official_status": "controlled signing copy; local form acceptance remains governed by the pinned template evidence",
            },
        )
    finally:
        output.file.close()
    version = (case.print_jobs.aggregate(value=Max("version"))["value"] or 0) + 1
    signature_round = output.input_snapshot.get("signature_round") or 0
    job = VoucherPrintJob(
        case=case,
        version=version,
        output=output,
        output_checksum=output.checksum,
        archive_manifest={
            "relative_path": archived["relative_path"],
            "sha256": archived["sha256"],
            "manifest_filename": archived["manifest_path"].name,
        },
        signature_round=signature_round,
        prepared_by=actor,
        supersedes=predecessor,
        supersession_reason=reason if predecessor else "",
    )
    job.full_clean()
    job.save()
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(
        case, actor, "dv_signing_copy_ready", case.current_stage, reason,
        {"print_job_id": job.pk, "print_version": job.version, "output_id": output.pk, "checksum": output.checksum},
        idempotency_key,
    )
    return job


@transaction.atomic
def record_dv_printed(*, case, actor, copy_count, printer_or_form_stock, print_note, expected_version, idempotency_key):
    _require(actor, "vouchers.control_dv_printing")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return VoucherPrintJob.objects.get(pk=existing.metadata["print_job_id"])
    _require_current_office(case, actor)
    if case.current_stage != VoucherCase.AWAITING_SIGNATURES:
        raise VoucherWorkflowError("This voucher is not in its controlled printing and wet-signature step.")
    job = case.print_jobs.select_for_update().filter(status=VoucherPrintJob.READY_TO_PRINT).first()
    if not job:
        raise VoucherWorkflowError("Create the current print-ready signing copy before recording printed copies.")
    description = printer_or_form_stock.strip()
    if not description:
        raise VoucherWorkflowError("Describe the printer and paper or form stock actually used.")
    job.status = VoucherPrintJob.PRINTED
    job.copy_count = copy_count
    job.printer_or_form_stock = description
    job.print_note = print_note.strip()
    job.printed_by = actor
    job.printed_at = timezone.now()
    job.full_clean()
    job.save(update_fields=(
        "status", "copy_count", "printer_or_form_stock", "print_note", "printed_by", "printed_at",
    ))
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(
        case, actor, "dv_copies_printed", case.current_stage, job.print_note,
        {"print_job_id": job.pk, "print_version": job.version, "copy_count": job.copy_count},
        idempotency_key,
    )
    return job


@transaction.atomic
def assemble_finance_packet(*, case, actor, expected_document_count, expected_page_count, confidentiality, assembly_note, expected_version, idempotency_key):
    _require(actor, "vouchers.control_dv_printing")
    _require(actor, "vouchers.link_tracepoint_custody")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return VoucherPrintJob.objects.get(pk=existing.metadata["print_job_id"])
    _require_current_office(case, actor)
    if case.current_stage != VoucherCase.AWAITING_SIGNATURES:
        raise VoucherWorkflowError("This voucher is not in its controlled printing and wet-signature step.")
    job = case.print_jobs.select_for_update().filter(status=VoucherPrintJob.PRINTED).first()
    if not job:
        raise VoucherWorkflowError("Record the printed signing copies before assembling their physical packet.")
    note = assembly_note.strip()
    if not note:
        raise VoucherWorkflowError("Record what was counted and assembled for signature circulation.")

    checkpoint_rows = []
    if case.tracepoint_item_id:
        item = case.tracepoint_item
        packet = item.current_packet
    else:
        from tracepoint.models import PacketCheckpoint
        from tracepoint.services import add_checkpoint, add_packet_item, create_packet

        packet = create_packet(
            actor=actor,
            title=f"DV signing packet — {case.reference_code}",
            contents_manifest=(
                f"Controlled signing copy v{job.version} for DV {case.disbursement_voucher.dv_number}; "
                "supporting documents are referenced in GRAND and counted without copying financial values into TracePoint."
            ),
            final_destination_department=case.configuration_release.department,
            confidentiality=confidentiality,
            expected_document_count=expected_document_count,
            expected_page_count=expected_page_count,
        )
        item = add_packet_item(
            packet=packet,
            actor=actor,
            title=f"DV {case.disbursement_voucher.dv_number}",
            description=f"GRAND case {case.reference_code} · signing copy v{job.version}",
            expected_attachment_count=max(int(expected_document_count or 1) - 1, 0),
            expected_page_count=expected_page_count,
        )
        tasks = case.signature_tasks.filter(round_number=job.signature_round).order_by("sequence", "pk")
        for task in tasks:
            checkpoint = add_checkpoint(
                packet=packet,
                actor=actor,
                department=task.custody_department or case.configuration_release.department,
                purpose=PacketCheckpoint.SIGNATURE,
                label=f"Signature: {task.signatory_name_snapshot} — {task.position_snapshot or task.role_code}",
                instructions=task.custody_instructions or "Confirm physical receipt for the configured wet-signature step.",
                required=True,
            )
            checkpoint_rows.append({
                "signature_task_id": task.pk,
                "checkpoint_id": checkpoint.pk,
                "sequence": checkpoint.sequence,
                "department_id": checkpoint.department_id,
                "label": checkpoint.label,
            })
        case.tracepoint_item = item

    job.status = VoucherPrintJob.AWAITING_SIGNATURES
    job.tracepoint_item = item
    job.packet_reference = packet.tracking_number
    job.custody_manifest = {
        "case_reference": case.reference_code,
        "dv_number": case.disbursement_voucher.dv_number,
        "print_version": job.version,
        "output_checksum": job.output_checksum,
        "copy_count": job.copy_count,
        "tracepoint_packet": packet.tracking_number,
        "tracepoint_item": item.reference_number,
        "expected_document_count": expected_document_count,
        "expected_page_count": expected_page_count,
        "assembly_note": note,
        "checkpoints": checkpoint_rows,
    }
    job.custody_confirmed_by = actor
    job.custody_confirmed_at = timezone.now()
    job.full_clean()
    job.save(update_fields=(
        "status", "tracepoint_item", "packet_reference", "custody_manifest",
        "custody_confirmed_by", "custody_confirmed_at",
    ))
    case.state_version += 1
    case.save(update_fields=("tracepoint_item", "state_version", "updated_at"))
    _event(
        case, actor, "finance_packet_assembled", case.current_stage, note,
        {
            "print_job_id": job.pk, "print_version": job.version,
            "packet_reference": packet.tracking_number, "item_reference": item.reference_number,
            "checkpoint_count": len(checkpoint_rows),
        },
        idempotency_key,
    )
    return job
