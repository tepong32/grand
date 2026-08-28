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

from finance.models import FinanceConfigurationItem, FinanceConfigurationRelease, FinanceNumberingSequence, FinanceSignatory
from finance.services import FinanceTemplateError, _destination, inspect_finance_workbook, verify_template_evidence
from profiles.models import EmployeeProfile

from .access import department_for_user, has_explicit_permission
from .models import (
    AccountingValidation, BankAdviceBatch, BankAdviceItem, BudgetAllocationLine,
    BudgetObligation, ControlOverride, DisbursementVoucher, PaymentInstrument,
    VoucherCase, VoucherDeduction, VoucherDocumentCheck, VoucherEvent,
    VoucherLineItem, VoucherNumberIssue, VoucherOutput, VoucherPostingRequest, VoucherTask, WetSignatureTask,
)


class VoucherWorkflowError(ValidationError):
    pass


STAGE_PERMISSION = {
    VoucherCase.BUDGET_DRAFT: "vouchers.certify_budget_obligation",
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


def _advance(case, actor, stage, action, idempotency_key, reason="", metadata=None):
    previous = case.current_stage
    now = timezone.now()
    case.tasks.filter(status=VoucherTask.OPEN).update(status=VoucherTask.COMPLETED, completed_at=now)
    case.current_stage = stage
    permission = STAGE_PERMISSION.get(stage)
    if permission:
        case.current_department = _department_for_permission(permission, department_for_user(actor))
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
    previous_round = case.signature_tasks.order_by("-round_number").values_list("round_number", flat=True).first() or 0
    round_number = previous_round + 1
    signatories = FinanceSignatory.objects.filter(
        release=case.configuration_release, status="active", valid_from__lte=voucher_date,
    ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=voucher_date)).order_by("role_code", "pk")
    for index, signatory in enumerate(signatories, start=1):
        WetSignatureTask.objects.create(
            case=case, round_number=round_number, sequence=index, role_code=signatory.role_code,
            signatory_name_snapshot=signatory.display_name, position_snapshot=signatory.position_title,
        )
    return round_number, signatories.exists()


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
    if actor.pk == case.obligation.certified_by_id:
        raise VoucherWorkflowError("The Budget certifier cannot prepare the DV without an approved control override.")
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
    return _advance(case, actor, next_stage, "dv_corrected" if prior_snapshot else "dv_prepared", idempotency_key, metadata={"dv_number": dv_number, "gross": str(gross), "net": str(net), "signature_round": round_number, "prior_amounts": prior_snapshot})


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
    return _advance(case, actor, VoucherCase.ACCOUNTING_VALIDATION, "wet_signatures_completed", idempotency_key, note)


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
    if actor.pk == case.disbursement_voucher.prepared_by_id:
        override = _approved_override(case, "accounting-self-validation", actor)
        if not override:
            raise VoucherWorkflowError("The DV preparer cannot validate the same voucher without a separately approved override.")
        override.status = ControlOverride.USED
        override.save(update_fields=("status",))
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
    return _advance(
        case, actor, VoucherCase.ACCOUNTING_POSTING, "accounting_validated", idempotency_key, note,
        {"jev_number": jev_number, "posting_request": str(request.public_id), "payload_checksum": checksum},
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
        "GRAND_APPROVED_BY": "WET SIGNATURE — VERIFY ORIGINAL",
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
