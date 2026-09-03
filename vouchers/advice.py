from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from finance.models import FinancePostingRule
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import (
    BankAdviceBatch, BankAdviceEvent, BankAdviceItem, PaymentInstrument,
    PaymentInstrumentException, ReturnedInstrumentReview, VoucherCase,
    VoucherPostingRequest,
)


def _require(actor, permission):
    if not has_explicit_permission(actor, permission):
        raise PermissionDenied


def _event(*, batch, actor, action, instrument=None, reason="", snapshot=None):
    department = department_for_user(actor)
    if department is None:
        raise ValidationError("Your account needs an assigned department before bank-advice work.")
    return BankAdviceEvent.objects.create(
        batch=batch, instrument=instrument, action=action, actor=actor,
        actor_department=department, reason=str(reason or "").strip(), snapshot=snapshot or {},
    )


def _item_snapshot(instrument):
    return {
        "instrument_public_id": str(instrument.public_id),
        "case_public_id": str(instrument.case.public_id),
        "case_reference": instrument.case.reference_code,
        "check_number": instrument.check_number,
        "bank_account_code": instrument.bank_account_code,
        "fund_code": instrument.fund_code,
        "amount": str(instrument.amount),
        "issued_at": instrument.issued_at.isoformat() if instrument.issued_at else "",
    }


def advice_snapshot(batch, instruments=None):
    if instruments is None:
        items = [
            {
                "instrument_public_id": str(item.instrument_public_id_snapshot or item.instrument.public_id),
                "case_public_id": str(item.instrument.case.public_id),
                "case_reference": item.instrument.case.reference_code,
                "check_number": item.check_number_snapshot,
                "bank_account_code": batch.bank_account_code,
                "fund_code": item.fund_code_snapshot,
                "amount": str(item.amount_snapshot),
                "issued_at": item.issued_at_snapshot.isoformat() if item.issued_at_snapshot else "",
            }
            for item in batch.items.select_related("instrument__case").order_by("check_number_snapshot", "pk")
        ]
    else:
        items = [_item_snapshot(item) for item in sorted(instruments, key=lambda value: (value.check_number, value.pk))]
    return {
        "schema_version": 1,
        "batch_public_id": str(batch.public_id),
        "advice_number": batch.advice_number,
        "advice_date": batch.advice_date.isoformat(),
        "bank_account_code": batch.bank_account_code,
        "configuration_release_id": batch.configuration_release_id,
        "accounting_department_id": batch.accounting_department_id,
        "version": batch.version,
        "supersedes_public_id": str(batch.supersedes.public_id) if batch.supersedes_id else "",
        "preparation_note": batch.preparation_note,
        "authority_reference": batch.authority_reference,
        "local_applicability_note": batch.local_applicability_note,
        "items": items,
    }


def _checksum(snapshot):
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _verify_snapshot(batch):
    snapshot = advice_snapshot(batch)
    if len(snapshot["items"]) != batch.item_count:
        raise ValidationError("The retained advice item count no longer matches its snapshot.")
    total = sum((Decimal(item["amount"]) for item in snapshot["items"]), Decimal("0.00"))
    if total != batch.total_amount or _checksum(snapshot) != batch.snapshot_checksum:
        raise ValidationError("The bank-advice snapshot checksum no longer matches its retained items.")
    return snapshot


def eligible_advice_instruments(actor):
    _require(actor, "vouchers.view_bank_advice")
    department = department_for_user(actor)
    query = PaymentInstrument.objects.filter(
        status=PaymentInstrument.ISSUED,
        case__current_stage=VoucherCase.ACCOUNTING_BANK_ADVICE,
        case__current_department=department,
    ).select_related("case", "case__configuration_release", "current_advice_batch")
    return query.filter(
        Q(current_advice_batch__isnull=True)
        | Q(current_advice_batch__status__in=(
            BankAdviceBatch.REVIEW_RETURNED, BankAdviceBatch.RETURNED, BankAdviceBatch.SUPERSEDED,
        ))
    ).order_by("bank_account_code", "check_number")


@transaction.atomic
def create_advice_batch(
    *, actor, advice_number, advice_date, instruments, preparation_note,
    authority_reference, local_applicability_note, supersedes=None, correction_reason="",
):
    _require(actor, "vouchers.prepare_bank_advice")
    department = department_for_user(actor)
    if department is None:
        raise ValidationError("Assign the preparer to an Accounting department first.")
    advice_number = str(advice_number or "").strip()
    preparation_note = str(preparation_note or "").strip()
    authority_reference = str(authority_reference or "").strip()
    local_applicability_note = str(local_applicability_note or "").strip()
    correction_reason = str(correction_reason or "").strip()
    if not all((advice_number, preparation_note, authority_reference, local_applicability_note)):
        raise ValidationError("Complete the advice number, preparation note, authority, and local-applicability note.")

    instrument_ids = [getattr(item, "pk", item) for item in instruments]
    locked_instruments = list(
        PaymentInstrument.objects.select_for_update().select_related(
            "case", "case__configuration_release", "current_advice_batch",
        ).filter(pk__in=instrument_ids).order_by("check_number", "pk")
    )
    if not locked_instruments or len(locked_instruments) != len(set(instrument_ids)):
        raise ValidationError("Select at least one valid issued instrument for the advice.")
    case_ids = {item.case_id for item in locked_instruments}
    locked_cases = {
        item.pk: item for item in VoucherCase.objects.select_for_update().filter(pk__in=case_ids)
    }
    if any(locked_cases[item.case_id].current_stage != VoucherCase.ACCOUNTING_BANK_ADVICE for item in locked_instruments):
        raise ValidationError("Every selected instrument must still be in Accounting's bank-advice queue.")
    if any(locked_cases[item.case_id].current_department_id != department.pk for item in locked_instruments):
        raise PermissionDenied("Advice preparation is limited to the cases assigned to your Accounting office.")
    if any(item.status != PaymentInstrument.ISSUED for item in locked_instruments):
        raise ValidationError("Only issued instruments may enter a new advice version.")
    bank_codes = {item.bank_account_code for item in locked_instruments}
    release_ids = {item.case.configuration_release_id for item in locked_instruments}
    if len(bank_codes) != 1 or len(release_ids) != 1 or None in release_ids:
        raise ValidationError("One advice version must use one bank account and one pinned Finance Setup release.")

    prior = None
    version = 1
    if supersedes is not None:
        prior = BankAdviceBatch.objects.select_for_update().get(pk=supersedes.pk)
        if prior.accounting_department_id != department.pk:
            raise PermissionDenied("Only the owning Accounting office may prepare the correction.")
        if prior.status not in (BankAdviceBatch.REVIEW_RETURNED, BankAdviceBatch.RETURNED):
            raise ValidationError("Only a returned advice version can be corrected through a successor.")
        if not correction_reason:
            raise ValidationError("Explain what is being corrected in the successor advice.")
        if prior.bank_account_code not in bank_codes or prior.configuration_release_id not in release_ids:
            raise ValidationError("A successor must retain the same bank account and Finance Setup release.")
        prior_item_ids = set(prior.items.values_list("instrument_id", flat=True))
        selected_ids = {item.pk for item in locked_instruments}
        if not selected_ids.issubset(prior_item_ids):
            raise ValidationError("A successor may contain only instruments retained from the returned advice version.")
        if any(item.current_advice_batch_id != prior.pk for item in locked_instruments):
            raise ValidationError("Every successor instrument must still point to the returned advice version.")
        version = prior.version + 1
    else:
        conflicting = [
            item for item in locked_instruments
            if item.current_advice_batch_id and item.current_advice_batch.status not in (
                BankAdviceBatch.REVIEW_RETURNED, BankAdviceBatch.RETURNED, BankAdviceBatch.SUPERSEDED,
            )
        ]
        if conflicting:
            raise ValidationError("At least one selected instrument already belongs to an active advice version.")

    batch = BankAdviceBatch(
        advice_number=advice_number, advice_date=advice_date, bank_account_code=bank_codes.pop(),
        configuration_release_id=release_ids.pop(), accounting_department=department,
        preparation_note=preparation_note, authority_reference=authority_reference,
        local_applicability_note=local_applicability_note, status=BankAdviceBatch.DRAFT,
        version=version, supersedes=prior, created_by=actor,
        item_count=len(locked_instruments),
        total_amount=sum((item.amount for item in locked_instruments), Decimal("0.00")),
    )
    snapshot = advice_snapshot(batch, locked_instruments)
    batch.snapshot_checksum = _checksum(snapshot)
    batch.full_clean()
    batch.save()
    BankAdviceItem.objects.bulk_create([
        BankAdviceItem(
            batch=batch, instrument=item, instrument_public_id_snapshot=item.public_id,
            check_number_snapshot=item.check_number, fund_code_snapshot=item.fund_code,
            amount_snapshot=item.amount, issued_at_snapshot=item.issued_at,
        )
        for item in locked_instruments
    ])
    PaymentInstrument.objects.filter(pk__in=[item.pk for item in locked_instruments]).update(
        current_advice_batch=batch,
    )
    if prior:
        prior.status = BankAdviceBatch.SUPERSEDED
        prior.state_version += 1
        prior.save(update_fields=("status", "state_version"))
        PaymentInstrument.objects.filter(
            pk__in=prior_item_ids - selected_ids, current_advice_batch=prior,
        ).update(current_advice_batch=None, status=PaymentInstrument.ISSUED)
        _event(
            batch=prior, actor=actor, action="advice_superseded", reason=correction_reason,
            snapshot={"successor_public_id": str(batch.public_id), "successor_version": batch.version},
        )
    _event(
        batch=batch, actor=actor,
        action="advice_successor_prepared" if prior else "advice_prepared",
        reason=correction_reason,
        snapshot={"checksum": batch.snapshot_checksum, "item_count": batch.item_count, "total": str(batch.total_amount)},
    )
    return batch


def _lock_batch(batch, expected_version):
    locked = BankAdviceBatch.objects.select_for_update().select_related(
        "accounting_department", "configuration_release", "created_by",
    ).get(pk=batch.pk)
    if expected_version is not None and locked.state_version != expected_version:
        raise ValidationError("This advice changed after the page was opened. Reload before acting.")
    return locked


@transaction.atomic
def submit_advice_for_review(*, batch, actor, expected_version=None):
    _require(actor, "vouchers.prepare_bank_advice")
    locked = _lock_batch(batch, expected_version)
    if locked.accounting_department != department_for_user(actor) or locked.status != locked.DRAFT:
        raise ValidationError("Only the owning Accounting office may submit a prepared draft.")
    _verify_snapshot(locked)
    locked.status = locked.FOR_REVIEW
    locked.review_submitted_by = actor
    locked.review_submitted_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=("status", "review_submitted_by", "review_submitted_at", "state_version"))
    _event(batch=locked, actor=actor, action="advice_submitted_for_review", snapshot={"checksum": locked.snapshot_checksum})
    return locked


@transaction.atomic
def review_advice(*, batch, actor, approve, note, expected_version=None):
    _require(actor, "vouchers.approve_bank_advice")
    locked = _lock_batch(batch, expected_version)
    note = str(note or "").strip()
    if locked.status != locked.FOR_REVIEW or not note:
        raise ValidationError("Review an advice awaiting decision and record the decision basis.")
    if locked.created_by_id == actor.pk or locked.review_submitted_by_id == actor.pk:
        raise ValidationError("The advice preparer cannot independently approve the same version.")
    if approve and (
        locked.authority_reference.lower().startswith(("pending", "edit"))
        or locked.local_applicability_note.lower().startswith(("pending", "edit"))
    ):
        raise ValidationError("Replace starter or pending authority notes with the reviewed local basis before approval.")
    _verify_snapshot(locked)
    locked.status = locked.APPROVED if approve else locked.REVIEW_RETURNED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.review_note = note
    locked.state_version += 1
    locked.save(update_fields=("status", "approved_by", "approved_at", "review_note", "state_version"))
    if approve:
        PaymentInstrument.objects.filter(current_advice_batch=locked).update(status=PaymentInstrument.ADVISED)
    _event(
        batch=locked, actor=actor, action="advice_approved" if approve else "advice_returned_by_reviewer",
        reason=note, snapshot={"checksum": locked.snapshot_checksum},
    )
    return locked


@transaction.atomic
def record_advice_submission(*, batch, actor, submission_reference, evidence_reference, expected_version=None):
    _require(actor, "vouchers.submit_bank_advice")
    locked = _lock_batch(batch, expected_version)
    submission_reference = str(submission_reference or "").strip()
    evidence_reference = str(evidence_reference or "").strip()
    if locked.status != locked.APPROVED or not submission_reference or not evidence_reference:
        raise ValidationError("Record both the bank submission reference and retained evidence for an approved advice.")
    _verify_snapshot(locked)
    locked.status = locked.SUBMITTED
    locked.bank_submitted_by = actor
    locked.bank_submitted_at = timezone.now()
    locked.submission_reference = submission_reference
    locked.submission_evidence_reference = evidence_reference
    locked.state_version += 1
    locked.save(update_fields=(
        "status", "bank_submitted_by", "bank_submitted_at", "submission_reference",
        "submission_evidence_reference", "state_version",
    ))
    _event(batch=locked, actor=actor, action="advice_submitted_to_bank", snapshot={"submission_reference": submission_reference})
    return locked


def _case_ready_after_ack(case):
    active = case.payment_instruments.exclude(
        status__in=(PaymentInstrument.CANCELLED, PaymentInstrument.BANK_RETURNED),
    ).select_related("current_advice_batch")
    return active.exists() and all(
        item.status == PaymentInstrument.ADVISED
        and item.current_advice_batch_id
        and item.current_advice_batch.status == BankAdviceBatch.ACKNOWLEDGED
        for item in active
    )


@transaction.atomic
def record_bank_response(
    *, batch, actor, acknowledged, response_reference, evidence_reference,
    reason="", expected_version=None,
):
    _require(actor, "vouchers.acknowledge_bank_advice")
    locked = _lock_batch(batch, expected_version)
    response_reference = str(response_reference or "").strip()
    evidence_reference = str(evidence_reference or "").strip()
    reason = str(reason or "").strip()
    if locked.status != locked.SUBMITTED or not response_reference or not evidence_reference:
        raise ValidationError("Record the bank response reference and retained evidence for a submitted advice.")
    if not acknowledged and not reason:
        raise ValidationError("Explain why the bank returned the advice.")
    _verify_snapshot(locked)
    now = timezone.now()
    locked.state_version += 1
    case_ids = list(locked.items.values_list("instrument__case_id", flat=True).distinct())
    cases = {
        item.pk: item for item in VoucherCase.objects.select_for_update().filter(pk__in=case_ids)
    }
    if acknowledged:
        locked.status = locked.ACKNOWLEDGED
        locked.acknowledged_by = actor
        locked.acknowledged_at = now
        locked.acknowledgement_reference = response_reference
        locked.acknowledgement_evidence_reference = evidence_reference
        locked.save(update_fields=(
            "status", "acknowledged_by", "acknowledged_at", "acknowledgement_reference",
            "acknowledgement_evidence_reference", "state_version",
        ))
        _event(batch=locked, actor=actor, action="advice_acknowledged_by_bank", snapshot={"acknowledgement_reference": response_reference})
        from .services import _advance
        for case in cases.values():
            if case.current_stage == VoucherCase.ACCOUNTING_BANK_ADVICE and _case_ready_after_ack(case):
                _advance(
                    case, actor, VoucherCase.TREASURY_RELEASE, "bank_advice_acknowledged",
                    f"bank-advice-acknowledged-{locked.public_id}-{case.public_id}",
                    metadata={
                        "batch_id": str(locked.public_id), "advice_number": locked.advice_number,
                        "acknowledgement_reference": response_reference,
                    },
                )
    else:
        locked.status = locked.RETURNED
        locked.returned_by = actor
        locked.returned_at = now
        locked.return_reason = reason
        locked.return_evidence_reference = evidence_reference
        locked.acknowledgement_reference = response_reference
        locked.save(update_fields=(
            "status", "returned_by", "returned_at", "return_reason", "return_evidence_reference",
            "acknowledgement_reference", "state_version",
        ))
        PaymentInstrument.objects.filter(current_advice_batch=locked).update(status=PaymentInstrument.ISSUED)
        _event(
            batch=locked, actor=actor, action="advice_returned_by_bank", reason=reason,
            snapshot={"response_reference": response_reference, "evidence_reference": evidence_reference},
        )
    return locked


@transaction.atomic
def begin_returned_instrument_review(*, exception, actor):
    instrument = PaymentInstrument.objects.select_for_update().select_related(
        "case", "current_advice_batch",
    ).get(pk=exception.instrument_id)
    case = VoucherCase.objects.select_for_update().get(pk=instrument.case_id)
    if instrument.status != PaymentInstrument.RELEASED or case.current_stage != VoucherCase.COMPLETED:
        raise ValidationError("Returned-item Accounting review starts only after a completed released payment.")
    if not instrument.current_advice_batch_id or instrument.current_advice_batch.status != BankAdviceBatch.ACKNOWLEDGED:
        raise ValidationError("The released instrument has no acknowledged bank-advice evidence.")
    payment_request = case.posting_requests.filter(
        kind=VoucherPostingRequest.PAYMENT,
        trigger_key=f"payment-instrument:{instrument.public_id}:released",
        status__in=(VoucherPostingRequest.POSTED, VoucherPostingRequest.NOT_REQUIRED),
    ).order_by("-version").first()
    if payment_request is None:
        raise ValidationError("Complete the governed payment-release Accounting decision before recording a bank return.")
    review = ReturnedInstrumentReview.objects.create(
        exception=exception, case=case, instrument=instrument,
        original_payment_request=payment_request,
        treasury_evidence_reference=exception.evidence_reference,
        treasury_note=exception.reason,
        status=ReturnedInstrumentReview.AWAITING_REVIEW,
        prepared_by=actor,
    )
    from .services import _advance
    _advance(
        case, actor, VoucherCase.ACCOUNTING_RETURNED_ITEM, "returned_instrument_sent_to_accounting",
        f"returned-instrument-review-{review.public_id}", reason=exception.reason,
        metadata={
            "review_public_id": str(review.public_id),
            "instrument_public_id": str(instrument.public_id),
            "exception_public_id": str(exception.public_id),
            "advice_public_id": str(instrument.current_advice_batch.public_id),
        },
    )
    return review


@transaction.atomic
def clarify_returned_instrument_review(*, review, actor, note, evidence_reference, expected_version=None):
    _require(actor, "vouchers.manage_payment_exceptions")
    locked = ReturnedInstrumentReview.objects.select_for_update().select_related(
        "exception__policy", "case", "instrument",
    ).get(pk=review.pk)
    if expected_version is not None and locked.state_version != expected_version:
        raise ValidationError("This returned-item review changed. Reload before acting.")
    if locked.status != locked.RETURNED_FOR_CLARIFICATION:
        raise ValidationError("Only an Accounting-returned review can be clarified.")
    if locked.exception.policy.treasury_department != department_for_user(actor):
        raise PermissionDenied("Clarification is limited to the owning Treasury office.")
    note = str(note or "").strip()
    evidence_reference = str(evidence_reference or "").strip()
    if not note or not evidence_reference:
        raise ValidationError("Record the clarification and its evidence reference.")
    successor = ReturnedInstrumentReview.objects.create(
        exception=locked.exception, case=locked.case, instrument=locked.instrument,
        original_payment_request=locked.original_payment_request,
        treasury_evidence_reference=evidence_reference, treasury_note=note,
        status=ReturnedInstrumentReview.AWAITING_REVIEW,
        version=locked.version + 1, supersedes=locked, prepared_by=actor,
    )
    locked.status = locked.SUPERSEDED
    locked.state_version += 1
    locked.save(update_fields=("status", "state_version"))
    from .services import _advance
    _advance(
        locked.case, actor, VoucherCase.ACCOUNTING_RETURNED_ITEM,
        "returned_instrument_clarified", f"returned-instrument-clarified-{successor.public_id}",
        reason=note, metadata={"review_public_id": str(successor.public_id), "supersedes": str(locked.public_id)},
    )
    return successor


@transaction.atomic
def decide_returned_instrument(
    *, review, actor, approve, outcome="", decision_reason="",
    evidence_reference="", expected_version=None,
):
    _require(actor, "vouchers.review_returned_instruments")
    locked = ReturnedInstrumentReview.objects.select_for_update().select_related(
        "case", "instrument", "exception__policy", "prepared_by",
    ).get(pk=review.pk)
    case = VoucherCase.objects.select_for_update().get(pk=locked.case_id)
    if expected_version is not None and locked.state_version != expected_version:
        raise ValidationError("This returned-item review changed. Reload before acting.")
    if locked.status != locked.AWAITING_REVIEW or case.current_stage != VoucherCase.ACCOUNTING_RETURNED_ITEM:
        raise ValidationError("This returned instrument is not awaiting Accounting review.")
    if locked.prepared_by_id == actor.pk:
        raise ValidationError("The Treasury preparer cannot perform the independent Accounting decision.")
    decision_reason = str(decision_reason or "").strip()
    evidence_reference = str(evidence_reference or "").strip()
    if not decision_reason or not evidence_reference:
        raise ValidationError("Record the Accounting decision basis and retained evidence reference.")
    from .services import _advance, _create_event_posting_request, _route_event_posting_or_resume
    if not approve:
        locked.status = locked.RETURNED_FOR_CLARIFICATION
        locked.accounting_decision_reason = decision_reason
        locked.accounting_evidence_reference = evidence_reference
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.state_version += 1
        locked.save(update_fields=(
            "status", "accounting_decision_reason", "accounting_evidence_reference",
            "reviewed_by", "reviewed_at", "state_version",
        ))
        _advance(
            case, actor, VoucherCase.ACCOUNTING_RETURNED_ITEM,
            "returned_instrument_review_returned",
            f"returned-instrument-review-returned-{locked.public_id}-v{locked.state_version}",
            reason=decision_reason, metadata={"review_public_id": str(locked.public_id)},
            destination_department=locked.exception.policy.treasury_department,
        )
        return locked
    if outcome not in dict(ReturnedInstrumentReview.OUTCOME_CHOICES):
        raise ValidationError("Choose whether Treasury may replace the returned instrument or close it.")
    variant = case.configuration_release.transaction_variants.filter(
        code=case.transaction_type,
        status__in=("approved", "scheduled", "active", "superseded"),
    ).first()
    rule = variant.posting_rules.filter(event_kind=FinancePostingRule.REVERSAL).first() if variant else None
    if rule is None or rule.recognition_point != FinancePostingRule.PAYMENT_RETURN:
        raise ValidationError(
            "The pinned Finance Setup release needs a locally reviewed returned-payment reversal/no-entry rule before Accounting can decide this item."
        )
    destination = VoucherCase.TREASURY_CHECK_PREPARATION if outcome == locked.REISSUE else VoucherCase.COMPLETED
    posting_request = _create_event_posting_request(
        case=case, actor=actor, event_kind=FinancePostingRule.REVERSAL,
        recognition_point=FinancePostingRule.PAYMENT_RETURN,
        event_date=timezone.localdate(), event_amount=locked.instrument.amount,
        bank_account_code=locked.instrument.bank_account_code,
        trigger_key=f"payment-instrument:{locked.instrument.public_id}:bank-returned:{locked.public_id}",
        trigger={
            "type": "payment_instrument_returned_by_bank",
            "instrument_public_id": str(locked.instrument.public_id),
            "check_number": locked.instrument.check_number,
            "review_public_id": str(locked.public_id),
            "source_payment_request": str(locked.original_payment_request.public_id),
            "outcome": outcome,
            "evidence_reference": evidence_reference,
        },
        resume_stage=destination,
    )
    if posting_request is None:
        raise ValidationError("The returned-payment rule could not be pinned to the Accounting request.")
    locked.outcome = outcome
    locked.accounting_decision_reason = decision_reason
    locked.accounting_evidence_reference = evidence_reference
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.posting_request = posting_request
    locked.status = (
        locked.AWAITING_POSTING
        if posting_request.status != VoucherPostingRequest.NOT_REQUIRED
        else locked.READY_FOR_TREASURY if outcome == locked.REISSUE else locked.CLOSED
    )
    if locked.status == locked.CLOSED:
        locked.closed_by = actor
        locked.closed_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=(
        "outcome", "accounting_decision_reason", "accounting_evidence_reference",
        "reviewed_by", "reviewed_at", "posting_request", "status", "closed_by",
        "closed_at", "state_version",
    ))
    locked.instrument.status = PaymentInstrument.BANK_RETURNED
    locked.instrument.save(update_fields=("status",))
    if locked.status == locked.CLOSED:
        from .cash_positions import resolve_instrument_exception
        resolve_instrument_exception(
            exception=locked.exception, actor=actor,
            resolution=f"Accounting closed the bank-returned payment without replacement. {decision_reason}",
            permission_required=False,
        )
    _route_event_posting_or_resume(
        case=case, actor=actor, request=posting_request, resume_stage=destination,
        action="returned_instrument_accounting_decided",
        idempotency_key=f"returned-instrument-decided-{locked.public_id}",
        reason=decision_reason,
        metadata={
            "review_public_id": str(locked.public_id), "instrument_public_id": str(locked.instrument.public_id),
            "outcome": outcome, "evidence_reference": evidence_reference,
        },
    )
    return locked


def complete_returned_review_after_posting(*, posting_request, actor):
    review = ReturnedInstrumentReview.objects.select_for_update().select_related("exception").filter(
        posting_request=posting_request, status=ReturnedInstrumentReview.AWAITING_POSTING,
    ).first()
    if review is None:
        return None
    review.status = review.READY_FOR_TREASURY if review.outcome == review.REISSUE else review.CLOSED
    if review.status == review.CLOSED:
        review.closed_by = actor
        review.closed_at = timezone.now()
        from .cash_positions import resolve_instrument_exception
        resolve_instrument_exception(
            exception=review.exception, actor=actor,
            resolution=f"Returned-payment Accounting JEV posted; closed without replacement. {review.accounting_decision_reason}",
            permission_required=False,
        )
    review.state_version += 1
    review.save(update_fields=("status", "closed_by", "closed_at", "state_version"))
    return review


def complete_returned_review_on_replacement(*, original_instrument, replacement, actor):
    review = ReturnedInstrumentReview.objects.select_for_update().select_related("exception").filter(
        instrument=original_instrument, status=ReturnedInstrumentReview.READY_FOR_TREASURY,
        outcome=ReturnedInstrumentReview.REISSUE,
    ).order_by("-version").first()
    if review is None:
        return None
    review.status = review.CLOSED
    review.closed_by = actor
    review.closed_at = timezone.now()
    review.state_version += 1
    review.save(update_fields=("status", "closed_by", "closed_at", "state_version"))
    from .cash_positions import resolve_instrument_exception
    resolve_instrument_exception(
        exception=review.exception, actor=actor,
        resolution=f"Controlled replacement check {replacement.check_number} issued for returned instrument {original_instrument.check_number}.",
        permission_required=False,
    )
    return review


def export_bank_advice_csv(
    *, actor, batch=None, status="", attention="", returned_attention="",
):
    _require(actor, "vouchers.export_bank_advice")
    from .advice_register import (
        apply_bank_advice_filters, bank_advice_action_queryset, visible_bank_advice_batches,
    )
    from .returned_instrument_register import (
        returned_instrument_attention_queryset, visible_returned_instrument_reviews,
    )

    batches = visible_bank_advice_batches(actor)
    if batch is not None:
        batches = batches.filter(pk=batch.pk)
        status = attention = ""
        returned_reviews = ReturnedInstrumentReview.objects.none()
    else:
        batches, status, _ignored_attention = apply_bank_advice_filters(batches, status=status)
        if attention:
            batches, attention, _spec = bank_advice_action_queryset(
                actor, attention, queryset=batches,
            )
    if batch is None and returned_attention:
        returned_reviews, returned_attention, _returned_spec = returned_instrument_attention_queryset(
            actor, returned_attention,
        )
    elif batch is None:
        returned_reviews = visible_returned_instrument_reviews(actor).exclude(
            status=ReturnedInstrumentReview.SUPERSEDED,
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    columns = (
        "record_type", "advice_id", "advice_number", "version", "status", "advice_date",
        "bank_account", "item_count", "total_amount", "snapshot_checksum", "instrument_id",
        "case_reference", "instrument_number", "fund", "amount", "submission_reference",
        "acknowledgement_reference", "return_reason", "event_action", "event_reason", "evidence_reference",
        "returned_review_id", "returned_review_version", "returned_review_status", "returned_outcome",
        "exception_id", "exception_observed_on", "treasury_note", "accounting_decision_reason",
        "posting_request_id", "source_state_version",
    )

    def row(values):
        values = list(values) + [""] * (len(columns) - len(values))
        writer.writerow([
            "'" + value if isinstance(value, str) and value[:1] in ("=", "+", "-", "@") else value
            for value in values
        ])

    row(columns)
    for item in batches.order_by("advice_date", "advice_number", "version"):
        row([
            "advice", item.public_id, item.advice_number, item.version, item.status, item.advice_date,
            item.bank_account_code, item.item_count, item.total_amount, item.snapshot_checksum,
            "", "", "", "", "", item.submission_reference, item.acknowledgement_reference,
            item.return_reason, "", "", item.authority_reference,
        ])
        for advice_item in item.items.select_related("instrument__case").all():
            row([
                "instrument", item.public_id, item.advice_number, item.version, item.status, item.advice_date,
                item.bank_account_code, item.item_count, item.total_amount, item.snapshot_checksum,
                advice_item.instrument_public_id_snapshot, advice_item.instrument.case.reference_code,
                advice_item.check_number_snapshot, advice_item.fund_code_snapshot, advice_item.amount_snapshot,
                item.submission_reference, item.acknowledgement_reference, item.return_reason, "", "",
                item.acknowledgement_evidence_reference or item.return_evidence_reference,
            ])
        for event in item.events.all():
            row([
                "event", item.public_id, item.advice_number, item.version, item.status, item.advice_date,
                item.bank_account_code, item.item_count, item.total_amount, item.snapshot_checksum,
                event.instrument.public_id if event.instrument_id else "", "", "", "", "",
                item.submission_reference, item.acknowledgement_reference, item.return_reason,
                event.action, event.reason, json.dumps(event.snapshot, sort_keys=True),
            ])
    for review in returned_reviews.select_related(
        "case", "instrument", "exception", "posting_request",
    ).order_by("prepared_at", "pk"):
        row([
            "returned_review", "", "", "", "", "", review.instrument.bank_account_code,
            "", "", "", review.instrument.public_id, review.case.reference_code,
            review.instrument.check_number, review.instrument.fund_code, review.instrument.amount,
            "", "", "", "", "", review.treasury_evidence_reference,
            review.public_id, review.version, review.status, review.outcome,
            review.exception.public_id, review.exception.observed_on, review.treasury_note,
            review.accounting_decision_reason,
            review.posting_request.public_id if review.posting_request_id else "",
            review.state_version,
        ])
    content = output.getvalue().encode("utf-8-sig")
    owner = batch.accounting_department if batch else department_for_user(actor)
    return content, archive_export(
        content=content, department=owner, user=actor, category="finance-bank-advice",
        filename=f"bank-advice-{batch.advice_number if batch else timezone.localdate().isoformat()}.csv",
        metadata={
            "kind": "bank_advice_and_returned_item_evidence",
            "batch_public_id": str(batch.public_id) if batch else "all",
            "status_filter": status or "all",
            "attention_filter": attention or "all",
            "returned_attention_filter": returned_attention or "all",
            "advice_row_count": batches.count(),
            "returned_review_row_count": returned_reviews.count(),
        },
    )
