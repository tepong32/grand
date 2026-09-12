"""Exact reversal of a posted prior-payable deduction before payment correction."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.access import can_prepare_journals, department_for_user
from accounting.models import AccountingPeriod, Fund, JournalEntry, JournalLine, JournalSubsidiaryLine, PayableClaimReservation
from accounting.payables import reservation_evidence, verify_reservation, _capacity
from accounting.posted_evidence import verify_source_link, require_persisted_posting
from finance.models import FinancePostingRule as Rule
from .models import VoucherCase, VoucherPostingRequest, PaymentInstrument


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def lock_withholding_scope(department_id):
    # Identity spans setup-release versions, as does the posted subsidiary balance.
    from departments.models import Department
    Department.objects.select_for_update().get(pk=department_id)


def pending_holds(department_id, transaction_type):
    holds = {}
    for request in VoucherPostingRequest.objects.filter(finance_department_id=department_id,
            kind=Rule.REVERSAL, status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED)):
        correction = request.payload.get("deduction_correction")
        if correction and request.payload.get("transaction_type") == transaction_type:
            for row in correction["withholding"]:
                key = tuple(row[k] for k in ("fund_code", "account_code", "reference_key", "deduction_code"))
                holds[key] = holds.get(key, Decimal("0")) + Decimal(row["amount"])
    return holds


def corrected_request_ids(case):
    ids = set()
    for request in case.posting_requests.filter(status=VoucherPostingRequest.POSTED):
        correction = request.payload.get("deduction_correction")
        if correction:
            ids.update((str(request.public_id), correction["original_request"]))
    return ids


def original_request(case):
    corrected = corrected_request_ids(case)
    requests = [r for r in case.posting_requests.filter(kind=Rule.ADJUSTMENT, status=VoucherPostingRequest.POSTED)
                if r.payload.get("prior_payable") and str(r.public_id) not in corrected]
    if len(requests) != 1:
        raise ValidationError("Select a case with exactly one uncorrected posted prior-payable deduction adjustment.")
    return requests[0]


@transaction.atomic
def request_correction(*, case, actor, correction_date, reason, expected_version, idempotency_key):
    from .services import _require, _locked, _advance, _consume_sequence_number
    _require(actor, "vouchers.return_voucher_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if department_for_user(actor).pk != case.configuration_release.department_id:
        raise PermissionDenied
    if existing:
        return case
    if case.current_stage != VoucherCase.TREASURY_CHECK_PREPARATION:
        raise ValidationError("Correct posted deductions before payment preparation proceeds, or resolve the payment cycle first.")
    if case.posting_requests.filter(status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED)).exists():
        raise ValidationError("Resolve pending source postings before correcting deductions.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Record the reason for reversing the posted deductions and correcting the DV.")
    original = original_request(case)
    entry = JournalEntry.objects.get(public_id=original.accounting_entry_public_id)
    verify_source_link(original, entry, source_type="voucher")
    if (not isinstance(correction_date, date) or correction_date < entry.entry_date
            or correction_date > timezone.localdate()):
        raise ValidationError("Use the actual correction date, on or after the original adjustment and no later than today.")
    from .cancelled_corrections import cancellation_evidence
    cancelled = cancellation_evidence(case, original.payload["prior_payable"], correction_date)
    if not AccountingPeriod.objects.filter(department_id=original.finance_department_id, status=AccountingPeriod.OPEN,
            starts_on__lte=correction_date, ends_on__gte=correction_date).exists():
        raise ValidationError("The correction date must be in an open Accounting period.")
    if entry.status != JournalEntry.POSTED or entry.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError("The original deduction must be posted and have no active reversal.")
    lock_withholding_scope(original.finance_department_id)
    from .remittances import withholding_availability
    available = withholding_availability(finance_department_id=original.finance_department_id,
        transaction_type=case.transaction_type, as_of_date=correction_date, include_nonpositive=True)
    keys = ("fund_code", "account_code", "reference_key", "deduction_code")
    balances = {tuple(r[k] for k in keys): r["available"] for r in available}
    withheld = []
    for detail in entry.subsidiary_lines.filter(category=JournalSubsidiaryLine.WITHHOLDING).select_related("journal_line__account"):
        row = dict(fund_code=entry.fund.code, account_code=detail.journal_line.account.code,
            reference_key=detail.reference_key, deduction_code=detail.source_code, amount=str(detail.credit - detail.debit))
        key = tuple(row[k] for k in keys)
        amount = Decimal(row["amount"])
        if amount <= 0 or balances.get(key, Decimal("0")) < amount:
            raise ValidationError("The deduction balance is already remitted, reserved or corrected. Resolve that downstream evidence before reversing it.")
        balances[key] -= amount
        withheld.append(row)
    if not withheld or sum((Decimal(r["amount"]) for r in withheld), Decimal("0")) != Decimal(original.payload["total_deductions"]):
        raise ValidationError("The original withholding details do not reproduce the posted deduction amount.")
    version = (case.posting_requests.filter(kind=Rule.REVERSAL).aggregate(value=Max("version"))["value"] or 0) + 1
    number = _consume_sequence_number(case, actor, "journal-entry", f"journal-entry-deduction-correction-{version}")
    payload = deepcopy(original.payload)
    payload.update(schema_version=6, jev_number=number, jev_date=correction_date.isoformat(),
        posting_rule_public_id="", posting_rule_checksum="", event_amount=original.payload["total_deductions"],
        deduction_correction={"original_request": str(original.public_id), "original_entry": str(entry.public_id),
            "original_payload_checksum": original.payload_checksum, "original_rule_checksum": original.posting_rule_checksum,
            "reason": reason, "withholding": withheld})
    if cancelled:
        payload["deduction_correction"]["cancelled_instruments"] = cancelled
    request = VoucherPostingRequest(case=case, kind=Rule.REVERSAL, version=version, jev_number=number,
        jev_date=correction_date, origin_stage=case.current_stage, resume_stage=VoucherCase.ACCOUNTING_PREPARATION,
        trigger_key=f"deduction-correction:{original.public_id}:{version}", finance_department_id=original.finance_department_id,
        finance_department_label=original.finance_department_label, payload=payload, payload_checksum=digest(payload), requested_by=actor)
    request.full_clean()
    request.save()
    return _advance(case, actor, VoucherCase.ACCOUNTING_EVENT_POSTING, "deduction_correction_requested",
        idempotency_key, reason, metadata={"posting_request": str(request.public_id), "original_request": str(original.public_id)})


@transaction.atomic
def withdraw_correction(*, case, actor, reason, expected_version, idempotency_key):
    from .services import _require, _locked, _advance
    _require(actor, "vouchers.return_voucher_case")
    case, existing = _locked(case, expected_version, idempotency_key)
    if department_for_user(actor).pk != case.configuration_release.department_id:
        raise PermissionDenied
    if existing:
        return case
    reason = (reason or "").strip()
    pending = [r for r in case.posting_requests.filter(status__in=(VoucherPostingRequest.PENDING,
        VoucherPostingRequest.FAILED, VoucherPostingRequest.MATERIALIZED)) if r.payload.get("deduction_correction")]
    if case.current_stage != VoucherCase.ACCOUNTING_EVENT_POSTING or len(pending) != 1 or not reason:
        raise ValidationError("Record a reason to withdraw the one pending deduction correction.")
    request = pending[0]
    if JournalEntry.objects.filter(source_type="voucher", source_reference=str(request.public_id)).exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError("Discard an unposted correction draft first. A posted correction cannot be withdrawn.")
    lock_withholding_scope(request.finance_department_id)
    request.status, request.failure_reason = request.CANCELLED, reason
    request.save(update_fields=("status", "failure_reason"))
    return _advance(case, actor, VoucherCase.TREASURY_CHECK_PREPARATION, "deduction_correction_withdrawn",
        idempotency_key, reason, metadata={"posting_request": str(request.public_id)})


def materialize(request, actor):
    """Caller holds the default case lock. No current mapping can change the reversal."""
    if not can_prepare_journals(actor) or department_for_user(actor).pk != request.finance_department_id:
        raise PermissionDenied
    request.refresh_from_db()
    if request.status not in (request.PENDING, request.FAILED, request.MATERIALIZED):
        raise ValidationError("This correction request is no longer eligible for JEV creation.")
    if digest(request.payload) != request.payload_checksum:
        raise ValidationError("The correction source checksum no longer reproduces.")
    correction = request.payload["deduction_correction"]
    from .cancelled_corrections import cancellation_evidence
    if cancellation_evidence(request.case, request.payload["prior_payable"], request.jev_date,
            exclude_request=request.pk) != correction.get("cancelled_instruments", []):
        raise ValidationError("The cancelled checks differ from the retained correction evidence.")
    original = VoucherPostingRequest.objects.get(public_id=correction["original_request"], case_id=request.case_id, kind=Rule.ADJUSTMENT)
    if (original.status != original.POSTED or original.payload_checksum != correction["original_payload_checksum"]
            or original.posting_rule_checksum != correction["original_rule_checksum"]
            or original.payload.get("prior_payable") != request.payload.get("prior_payable")):
        raise ValidationError("The correction differs from its original posted adjustment and reservation.")
    with transaction.atomic(using="finance"):
        source = JournalEntry.objects.select_for_update().get(public_id=correction["original_entry"], status=JournalEntry.POSTED)
        verify_source_link(original, source, source_type="voucher")
        existing = JournalEntry.objects.filter(source_type="voucher", source_reference=str(request.public_id)).first()
        if existing:
            verify_source_link(request, existing, source_type="voucher")
            if existing.status == JournalEntry.VOIDED:
                raise ValidationError("The correction draft was discarded. Recover its governed successor request.")
            entry, created = existing, False
        else:
            if request.accounting_entry_public_id or source.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
                raise ValidationError("Resolve the retained correction JEV or existing reversal before creating another.")
            from accounting.claim_groups import resolve
            resolve(request.payload["prior_payable"], case_public_id=request.case.public_id, lock=True)
            period = AccountingPeriod.objects.filter(department_id=request.finance_department_id,
                status=AccountingPeriod.OPEN, starts_on__lte=request.jev_date, ends_on__gte=request.jev_date).first()
            if period is None:
                raise ValidationError("The correction date must remain in an open Accounting period.")
            entry = JournalEntry(department_id=source.department_id, department_label=source.department_label,
                reference=request.jev_number, entry_date=request.jev_date, period=period, fund=source.fund,
                source_type="voucher", source_reference=str(request.public_id), reversal_of=source,
                reversal_reason=correction["reason"], description=f"Deduction correction of {source.reference}: {correction['reason']}",
                source_snapshot={"voucher_case": str(request.case.public_id), "payload_checksum": request.payload_checksum,
                    "posting_rule_checksum": "", "posting_policy_mode": "exact_source_reversal",
                    "prior_payable": request.payload["prior_payable"], "deduction_correction": correction},
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username)
            entry.full_clean(); entry.save()
            for line in source.lines.select_related("account", "responsibility_center").order_by("sequence"):
                mirrored = JournalLine(entry=entry, sequence=line.sequence, account=line.account,
                    responsibility_center=line.responsibility_center, debit=line.credit, credit=line.debit,
                    memo=line.memo, cash_flow_category=line.cash_flow_category,
                    payable_origin_id=line.payable_origin_id, payable_reservation_id=line.payable_reservation_id,
                    payable_allocation=line.payable_allocation)
                mirrored.full_clean(); mirrored.save()
                detail = getattr(line, "subsidiary_posting", None)
                if detail:
                    retained = JournalSubsidiaryLine(entry=entry, journal_line=mirrored, category=detail.category,
                        reference_key=detail.reference_key, reference_label=detail.reference_label, source_code=detail.source_code,
                        source_reference=str(request.public_id), debit=mirrored.debit, credit=mirrored.credit,
                        source_snapshot={**detail.source_snapshot, "original_subsidiary": detail.pk,
                            "deduction_correction_request": str(request.public_id)})
                    retained.full_clean(); retained.save()
            from accounting.services import record_event
            record_event(source, "reversal_prepared", actor, reason=correction["reason"],
                snapshot={"reversal_entry": str(entry.public_id), "reversal_reference": entry.reference})
            record_event(entry, "prepared_from_reversal", actor, reason=correction["reason"],
                snapshot={"original_entry": str(source.public_id), "correction_request": str(request.public_id)})
            created = True
    VoucherPostingRequest.objects.filter(pk=request.pk).update(status=request.MATERIALIZED,
        accounting_entry_public_id=entry.public_id, materialized_at=timezone.now(), failure_reason="")
    return entry, created


def complete(request, actor):
    """Called in the default synchronization transaction after independent posting."""
    from .services import _apply_case_return
    entry = require_persisted_posting(JournalEntry.objects.get(public_id=request.accounting_entry_public_id), actor, source_type="voucher")
    verify_source_link(request, entry, source_type="voucher")
    correction = request.payload["deduction_correction"]
    from .cancelled_corrections import cancellation_evidence
    if cancellation_evidence(request.case, request.payload["prior_payable"], request.jev_date,
            exclude_request=request.pk) != correction.get("cancelled_instruments", []):
        raise ValidationError("The cancelled checks differ from the retained correction evidence.")
    if not entry.reversal_of_id or str(entry.reversal_of.public_id) != correction["original_entry"]:
        raise ValidationError("The posted correction must reverse the exact retained deduction journal.")
    with transaction.atomic(using="finance"):
        from accounting.claim_groups import resolve
        reservations = resolve(request.payload["prior_payable"], case_public_id=request.case.public_id, lock=True, allow_released=True)
        for reservation in reservations:
            reason = f"Deduction correction {request.public_id}: original adjustment reversed by {entry.reference}."
            if reservation.released_at:
                if reservation.release_reason != reason:
                    raise ValidationError("This claim hold was retired by a different decision.")
            else:
                verify_reservation(reservation)
                applications = list(reservation.applications.exclude(entry__status=JournalEntry.VOIDED).select_related("entry"))
                if any(r.entry.status != JournalEntry.POSTED for r in applications) or sum((r.debit-r.credit for r in applications), Decimal("0")) != 0:
                    raise ValidationError("Resolve other claim applications before reopening this DV.")
                _capacity(reservation.source)
                reservation.released_at, reservation.released_by_id, reservation.release_reason = timezone.now(), actor.pk, reason
                reservation._release_transition = True
                reservation.save(update_fields=("released_at", "released_by_id", "release_reason"))
    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    return _apply_case_return(case, actor, VoucherCase.ACCOUNTING_PREPARATION, correction["reason"],
        f"deduction-correction-posted:{request.public_id}")
