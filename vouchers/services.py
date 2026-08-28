from __future__ import annotations

from decimal import Decimal
import hashlib
import io
import json
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.core.files.base import ContentFile
from django.utils import timezone

from finance.exemptions import workflow_exemption_for, workflow_exemption_snapshot
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceNumberingSequence,
    FinanceSignatory, FinanceTransactionVariant, FinanceWorkflowExemption,
)
from finance.services import FinanceTemplateError, _destination, inspect_finance_workbook, verify_template_evidence
from profiles.models import EmployeeProfile

from .access import department_for_user, has_explicit_permission
from .models import (
    AccountingValidation, BankAdviceBatch, BankAdviceItem, BudgetAllocationLine,
    BudgetObligation, ControlOverride, DisbursementVoucher, PaymentInstrument,
    PayableDocumentEvidence, PayableIntake,
    VoucherCase, VoucherDeduction, VoucherDocumentCheck, VoucherEvent,
    VoucherLineItem, VoucherNonFinancialAmendment, VoucherNumberIssue, VoucherOutput,
    VoucherPostingRequest, VoucherTask, WetSignatureTask,
)


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
    VoucherCase.TREASURY_CHECK_PREPARATION: "vouchers.issue_payment_instruments",
    VoucherCase.ACCOUNTING_BANK_ADVICE: "vouchers.finalize_bank_advice",
    VoucherCase.TREASURY_RELEASE: "vouchers.release_payment_instruments",
}


def _require(actor, permission):
    if not has_explicit_permission(actor, permission):
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
    case.save(update_fields=("current_stage", "current_department", "state_version", "completed_at", "updated_at"))
    _event(case, actor, action, previous, reason, metadata, idempotency_key)
    return case


def _consume_number(case, actor, document_type):
    sequence = FinanceNumberingSequence.objects.select_for_update().filter(
        release=case.configuration_release, fiscal_year=timezone.localdate().year,
        document_type=document_type, status="active",
    ).first()
    if not sequence:
        raise VoucherWorkflowError(f"No active {document_type} numbering sequence is configured for this fiscal year.")
    value = sequence.next_number
    formatted = f"{sequence.prefix}{value:0{sequence.padding}d}"
    VoucherNumberIssue.objects.create(
        case=case, sequence=sequence, document_type=document_type, numeric_value=value,
        formatted_value=formatted, issued_by=actor,
    )
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))
    return formatted


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


def _bind_authoritative_obligation(case, obligation_public_id):
    from budget.models import ObligationRequest

    with transaction.atomic(using="finance"):
        obligation = ObligationRequest.objects.select_for_update().get(public_id=obligation_public_id)
        if obligation.status != ObligationRequest.CERTIFIED or obligation.kind != ObligationRequest.ORIGINAL:
            raise VoucherWorkflowError("The selected authoritative obligation is no longer an eligible certified original.")
        if obligation.linked_voucher_case_public_id not in (None, case.public_id):
            raise VoucherWorkflowError("That certified obligation is already linked to another voucher case.")
        if obligation.linked_voucher_case_public_id is None:
            ObligationRequest.objects.filter(pk=obligation.pk).update(linked_voucher_case_public_id=case.public_id)


@transaction.atomic
def reconcile_authoritative_obligation(*, case, actor, expected_version, idempotency_key):
    _require(actor, "vouchers.initiate_payable_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if department_for_user(actor).pk != case.requesting_department_id:
        raise PermissionDenied
    if not case.authoritative_obligation_public_id:
        raise VoucherWorkflowError("This legacy case has no authoritative obligation handoff to reconcile.")
    try:
        _bind_authoritative_obligation(case, case.authoritative_obligation_public_id)
    except Exception as exc:
        # Retain a visible recovery state; never let a cross-database partial handoff advance silently.
        case.obligation_binding_status = VoucherCase.BINDING_FAILED
        case.obligation_binding_error = str(exc)
        case.state_version += 1
        case.save(update_fields=("obligation_binding_status", "obligation_binding_error", "state_version", "updated_at"))
        _event(case, actor, "obligation_link_reconciliation_failed", case.current_stage, str(exc), {}, idempotency_key)
        return case
    case.obligation_binding_status = VoucherCase.BINDING_LINKED
    case.obligation_binding_error = ""
    case.state_version += 1
    case.save(update_fields=("obligation_binding_status", "obligation_binding_error", "state_version", "updated_at"))
    _event(case, actor, "obligation_link_reconciled", case.current_stage, "", {
        "authoritative_obligation_public_id": str(case.authoritative_obligation_public_id),
    }, idempotency_key)
    return case


def create_payable_case_from_obligation(
    *, actor, authoritative_obligation, payee, transaction_type, claim_reference,
    invoice_number, invoice_date, claim_amount, procurement_reference, delivery_reference,
    inspection_acceptance_reference, evidence_reference, duplicate_review_note, idempotency_key,
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
    if obligation.linked_voucher_case_public_id:
        raise VoucherWorkflowError("That certified obligation is already linked to a voucher case.")
    amount = Decimal(claim_amount)
    if snapshot["amount"] <= 0 or amount != snapshot["amount"]:
        raise VoucherWorkflowError(
            "The payable must equal the current certified obligation lineage. "
            "Record a governed adjustment before intake when the final claim differs."
        )
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
    certifier = get_user_model().objects.filter(pk=obligation.certified_by_id).first() or actor
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
        projection = BudgetObligation.objects.create(
            case=case, obr_number=obligation.obligation_number, obligation_date=obligation.obligation_date,
            budget_source_reference=f"Authoritative F4.2 obligation {obligation.public_id}",
            certified_amount=snapshot["amount"], certified_by=certifier,
            certified_at=obligation.certified_at or timezone.now(), source_kind="authoritative_f4_projection",
        )
        for item in snapshot["lines"]:
            BudgetAllocationLine.objects.create(
                obligation=projection,
                fund_code=item["appropriation_line__fund_code"],
                responsibility_center_code=item["appropriation_line__responsibility_center_code"],
                account_code=item["appropriation_line__account_code"], amount=item["amount"],
            )
        intake = PayableIntake(
            case=case, claim_reference=claim_reference.strip(), invoice_number=invoice_number.strip(),
            invoice_date=invoice_date, claim_amount=amount,
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
            "amount": str(amount), "duplicate_warning": intake.duplicate_warning,
        }, idempotency_key)
    try:
        _bind_authoritative_obligation(case, obligation.public_id)
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
    from budget.models import ObligationRequest
    source = ObligationRequest.objects.get(public_id=case.authoritative_obligation_public_id)
    _source, current = _authoritative_obligation_snapshot(source)
    if (
        current["checksum"] != case.authoritative_obligation_checksum
        or current["amount"] != case.authoritative_obligation_amount
    ):
        raise VoucherWorkflowError(
            "The obligation changed through a governed pre-DV correction. "
            "Reconcile the payable amount and evidence to the current obligation before continuing."
        )
    return current


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
    intake.save(update_fields=(
        "status", "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "decision_reason",
    ))
    return _advance(
        case, actor, VoucherCase.PAYABLE_REVIEW, "payable_submitted", idempotency_key,
        metadata={"claim_amount": str(intake.claim_amount), "document_rule_count": len(evidence)},
        destination_department=accounting_department,
    )


@transaction.atomic
def review_payable_intake(*, case, actor, decision, reason, expected_version, idempotency_key):
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
        intake.save(update_fields=("status", "reviewed_by", "reviewed_at", "decision_reason"))
        return _advance(
            case, actor, VoucherCase.PAYABLE_PREPARATION, "payable_returned", idempotency_key,
            reason=reason, destination_department=case.requesting_department,
        )
    if decision != PayableIntake.READY:
        raise VoucherWorkflowError("Choose a valid payable review decision.")
    _validate_payable_freshness(case)
    evidence = _validate_payable_checklist(case)
    intake.status = PayableIntake.READY
    intake.save(update_fields=("status", "reviewed_by", "reviewed_at", "decision_reason"))
    return _advance(
        case, actor, VoucherCase.ACCOUNTING_PREPARATION, "payable_accepted", idempotency_key,
        reason=reason, metadata={"claim_amount": str(intake.claim_amount), "document_rule_count": len(evidence)},
    )


@transaction.atomic
def certify_budget(*, case, actor, obligation_date, budget_source_reference, allocations, expected_version, idempotency_key):
    _require(actor, "vouchers.certify_budget_obligation")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
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
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
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
        VoucherDeduction.objects.create(voucher=voucher, code=item["code"], description=item.get("description", item["code"]), amount=Decimal(item["amount"]))
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
    if case.current_stage != VoucherCase.AWAITING_SIGNATURES or task.case_id != case.pk or task.status != WetSignatureTask.PENDING:
        raise VoucherWorkflowError("This wet-signature task is not awaiting return.")
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
    if case.current_stage != VoucherCase.ACCOUNTING_VALIDATION:
        raise VoucherWorkflowError("This voucher is not awaiting Accounting validation.")
    workflow_exemption = None
    case_override = None
    if actor.pk == case.disbursement_voucher.prepared_by_id:
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
    AccountingValidation.objects.create(
        case=case, decision=AccountingValidation.ACCEPTED, jev_number=jev_number.strip(), jev_date=jev_date,
        note=note.strip(), validated_by=actor, validated_at=timezone.now(),
    )
    voucher = case.disbursement_voucher
    payload = {
        "schema_version": 1,
        "voucher_case_public_id": str(case.public_id),
        "voucher_reference": case.reference_code,
        "dv_number": voucher.dv_number,
        "jev_number": jev_number.strip(),
        "jev_date": jev_date.isoformat(),
        "transaction_type": case.transaction_type,
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
            for line in case.obligation.allocation_lines.order_by("pk")
        ],
        "deductions": [
            {"code": item.code, "description": item.description, "amount": str(item.amount)}
            for item in voucher.deductions.order_by("pk")
        ],
    }
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    version = (case.posting_requests.aggregate(value=Max("version"))["value"] or 0) + 1
    department = department_for_user(actor)
    request = VoucherPostingRequest(
        case=case,
        version=version,
        jev_number=jev_number.strip(),
        jev_date=jev_date,
        finance_department_id=department.pk,
        finance_department_label=department.name,
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
def issue_check(*, case, actor, bank_account_code, check_number, amount, expected_version, idempotency_key, replaces=None):
    _require(actor, "vouchers.issue_payment_instruments")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case.payment_instruments.get(public_id=existing.metadata["instrument_id"])
    if case.current_stage != VoucherCase.TREASURY_CHECK_PREPARATION:
        raise VoucherWorkflowError("This voucher is not ready for Treasury check preparation.")
    amount = Decimal(amount)
    if PaymentInstrument.objects.filter(bank_account_code=bank_account_code, check_number=check_number).exists():
        raise VoucherWorkflowError("That physical check number has already been registered for this bank account and cannot be reused.")
    if replaces and (replaces.case_id != case.pk or replaces.status != PaymentInstrument.CANCELLED or hasattr(replaces, "replacement")):
        raise VoucherWorkflowError("A replacement may reference only one unreplaced cancelled check from this voucher.")
    active_total = case.payment_instruments.exclude(status=PaymentInstrument.CANCELLED).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if active_total + amount > case.disbursement_voucher.net_amount:
        raise VoucherWorkflowError("Active checks cannot exceed the voucher net amount.")
    instrument = PaymentInstrument.objects.create(
        case=case, bank_account_code=bank_account_code, check_number=check_number,
        amount=amount, status=PaymentInstrument.ISSUED, replaces=replaces,
        issued_by=actor, issued_at=timezone.now(),
    )
    case.state_version += 1
    case.save(update_fields=("state_version", "updated_at"))
    _event(case, actor, "check_issued", case.current_stage, "", {"instrument_id": str(instrument.public_id), "check_number": check_number, "amount": str(amount)}, idempotency_key)
    return instrument


@transaction.atomic
def submit_checks_for_advice(*, case, actor, expected_version, idempotency_key):
    _require(actor, "vouchers.issue_payment_instruments")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    issued = case.payment_instruments.filter(status=PaymentInstrument.ISSUED)
    total = issued.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if not issued.exists() or total != case.disbursement_voucher.net_amount:
        raise VoucherWorkflowError("Issued checks must exactly equal the voucher net amount before bank advice.")
    if issued.values("bank_account_code").distinct().count() != 1:
        raise VoucherWorkflowError("A pilot voucher's checks must use one bank account per advice batch.")
    return _advance(case, actor, VoucherCase.ACCOUNTING_BANK_ADVICE, "checks_submitted_for_advice", idempotency_key, metadata={"check_total": str(total)})


@transaction.atomic
def finalize_bank_advice(*, case, actor, advice_number, advice_date, expected_version, idempotency_key):
    _require(actor, "vouchers.finalize_bank_advice")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return BankAdviceBatch.objects.get(public_id=existing.metadata["batch_id"])
    if case.current_stage != VoucherCase.ACCOUNTING_BANK_ADVICE:
        raise VoucherWorkflowError("This voucher is not awaiting Accounting bank advice.")
    instruments = list(case.payment_instruments.filter(status=PaymentInstrument.ISSUED))
    if not instruments:
        raise VoucherWorkflowError("There are no issued checks eligible for bank advice.")
    bank_code = instruments[0].bank_account_code
    if any(item.bank_account_code != bank_code for item in instruments):
        raise VoucherWorkflowError("One advice batch cannot mix bank accounts.")
    batch = BankAdviceBatch.objects.create(
        advice_number=advice_number, advice_date=advice_date, bank_account_code=bank_code,
        status=BankAdviceBatch.FINALIZED, created_by=actor, finalized_by=actor, finalized_at=timezone.now(),
    )
    for instrument in instruments:
        BankAdviceItem.objects.create(batch=batch, instrument=instrument)
        instrument.status = PaymentInstrument.ADVISED
        instrument.save(update_fields=("status",))
    _advance(case, actor, VoucherCase.TREASURY_RELEASE, "bank_advice_finalized", idempotency_key, metadata={"batch_id": str(batch.public_id), "advice_number": advice_number})
    return batch


@transaction.atomic
def release_check(*, case, instrument, actor, claimant, receipt_reference, expected_version, idempotency_key):
    _require(actor, "vouchers.release_payment_instruments")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if case.current_stage != VoucherCase.TREASURY_RELEASE or instrument.case_id != case.pk or instrument.status != PaymentInstrument.ADVISED:
        raise VoucherWorkflowError("Only an advised check in Treasury's release queue may be released.")
    if claimant.party_id != case.payee_id or claimant.status != "active":
        raise VoucherWorkflowError("Select an active authorized claimant for this payee.")
    instrument.status = PaymentInstrument.RELEASED
    instrument.released_by, instrument.released_at = actor, timezone.now()
    instrument.released_to_claimant, instrument.released_to = claimant, claimant.display_name
    instrument.receipt_reference = receipt_reference.strip()
    instrument.save(update_fields=("status", "released_by", "released_at", "released_to_claimant", "released_to", "receipt_reference"))
    if case.payment_instruments.exclude(status__in=(PaymentInstrument.RELEASED, PaymentInstrument.CANCELLED)).exists():
        case.state_version += 1
        case.save(update_fields=("state_version", "updated_at"))
        _event(case, actor, "check_released", case.current_stage, "", {"check_number": instrument.check_number}, idempotency_key)
        return case
    return _advance(case, actor, VoucherCase.COMPLETED, "disbursement_completed", idempotency_key, metadata={"last_check_number": instrument.check_number})


@transaction.atomic
def cancel_check(*, case, instrument, actor, reason, expected_version, idempotency_key):
    _require(actor, "vouchers.manage_payment_exceptions")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    if instrument.case_id != case.pk or instrument.status not in {PaymentInstrument.ISSUED, PaymentInstrument.ADVISED}:
        raise VoucherWorkflowError("Only an issued or advised, unreleased check can be cancelled.")
    if not reason.strip():
        raise VoucherWorkflowError("A cancellation reason is required.")
    instrument.status, instrument.cancelled_by, instrument.cancelled_at = PaymentInstrument.CANCELLED, actor, timezone.now()
    instrument.cancellation_reason = reason.strip()
    instrument.save(update_fields=("status", "cancelled_by", "cancelled_at", "cancellation_reason"))
    return _advance(case, actor, VoucherCase.TREASURY_CHECK_PREPARATION, "check_cancelled", idempotency_key, reason, {"check_number": instrument.check_number})


@transaction.atomic
def return_case(*, case, actor, target_stage, reason, expected_version, idempotency_key):
    _require(actor, "vouchers.return_voucher_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if existing:
        return case
    allowed = {
        VoucherCase.AWAITING_SIGNATURES: {VoucherCase.ACCOUNTING_PREPARATION},
        VoucherCase.ACCOUNTING_VALIDATION: {VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.AWAITING_SIGNATURES},
        VoucherCase.ACCOUNTING_POSTING: {VoucherCase.ACCOUNTING_VALIDATION},
        VoucherCase.TREASURY_CHECK_PREPARATION: {VoucherCase.ACCOUNTING_VALIDATION},
        VoucherCase.ACCOUNTING_BANK_ADVICE: {VoucherCase.TREASURY_CHECK_PREPARATION},
        VoucherCase.TREASURY_RELEASE: {VoucherCase.TREASURY_CHECK_PREPARATION, VoucherCase.ACCOUNTING_BANK_ADVICE},
    }
    if target_stage not in allowed.get(case.current_stage, set()) or not reason.strip():
        raise VoucherWorkflowError("Choose an allowed earlier stage and record the correction reason.")
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
    return _advance(case, actor, target_stage, "returned_for_correction", idempotency_key, reason)


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
