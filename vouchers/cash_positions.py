from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from accounting.models import BankStatementBatch, Fund
from accounting.services import bank_reconciliation_snapshot
from finance.models import FinanceConfigurationItem
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import (
    PaymentInstrument, PaymentInstrumentException, TreasuryCashEvent, TreasuryCashPolicy,
    TreasuryCashPosition, TreasuryCashReservation,
)


def _require(actor, permission):
    if not has_explicit_permission(actor, permission):
        raise PermissionDenied


def _require_preparer_scope(actor, policy):
    if department_for_user(actor) != policy.treasury_department:
        raise PermissionDenied("Treasury cash preparation is limited to the policy's owning Treasury department.")


def _actor_label(actor):
    return actor.get_full_name() or actor.username


def _event(*, actor, action, policy=None, position=None, instrument=None, reason="", snapshot=None):
    department = department_for_user(actor)
    if department is None:
        raise ValidationError("Your account needs an assigned department before Treasury cash work.")
    return TreasuryCashEvent.objects.create(
        policy=policy, position=position, instrument=instrument, action=action, actor=actor,
        actor_department=department, reason=str(reason or "").strip(), snapshot=snapshot or {},
    )


def _policy_snapshot(policy):
    return {
        "schema_version": 1,
        "policy_public_id": str(policy.public_id),
        "configuration_release_id": policy.configuration_release_id,
        "bank_account_code": policy.bank_account_code,
        "fund_code": policy.fund_code,
        "mode": policy.mode,
        "minimum_reserve": str(policy.minimum_reserve),
        "position_max_age_days": policy.position_max_age_days,
        "unclaimed_after_days": policy.unclaimed_after_days,
        "stale_after_days": policy.stale_after_days,
        "effective_from": policy.effective_from.isoformat(),
        "effective_to": policy.effective_to.isoformat() if policy.effective_to else "",
        "authority_reference": policy.authority_reference,
        "local_applicability_note": policy.local_applicability_note,
        "version": policy.version,
    }


def _position_snapshot(position):
    return {
        "schema_version": 1,
        "position_public_id": str(position.public_id),
        "policy_public_id": str(position.policy.public_id),
        "bank_account_code": position.policy.bank_account_code,
        "fund_code": position.policy.fund_code,
        "as_of_date": position.as_of_date.isoformat(),
        "reconciliation_public_id": str(position.reconciliation_public_id),
        "reconciliation_checksum": position.reconciliation_checksum,
        "reconciliation_period_end": position.reconciliation_period_end.isoformat(),
        "reconciled_book_balance": str(position.reconciled_book_balance),
        "confirmed_inflows": str(position.confirmed_inflows),
        "confirmed_outflows": str(position.confirmed_outflows),
        "other_holds": str(position.other_holds),
        "minimum_reserve": str(position.policy.minimum_reserve),
        "approved_available_cash": str(position.approved_available_cash),
        "evidence_reference": position.evidence_reference,
        "preparation_note": position.preparation_note,
        "version": position.version,
    }


def _checksum(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_route(release, bank_account_code, fund_code):
    valid_bank = FinanceConfigurationItem.objects.filter(
        release=release, category="bank_account", code=bank_account_code, status="active",
    ).exists()
    if not valid_bank:
        raise ValidationError("Choose an active bank/payment account from the selected Finance release.")
    if not Fund.objects.filter(department_id=release.department_id, code=fund_code, is_active=True).exists():
        raise ValidationError("Choose an active Accounting fund owned by this Finance release.")


@transaction.atomic
def create_policy(*, actor, configuration_release, bank_account_code, fund_code, mode, minimum_reserve,
                  position_max_age_days, unclaimed_after_days, stale_after_days, effective_from,
                  effective_to=None, authority_reference, local_applicability_note):
    _require(actor, "vouchers.prepare_cash_position")
    configuration_release = type(configuration_release).objects.select_for_update().get(pk=configuration_release.pk)
    _validate_route(configuration_release, bank_account_code, fund_code)
    route = TreasuryCashPolicy.objects.filter(
        configuration_release=configuration_release, bank_account_code=bank_account_code, fund_code=fund_code,
    )
    list(route.select_for_update().order_by("pk").values_list("pk", flat=True))
    prior = route.order_by("-version").first()
    version = (route.aggregate(value=Max("version"))["value"] or 0) + 1
    policy = TreasuryCashPolicy(
        configuration_release=configuration_release,
        treasury_department=department_for_user(actor),
        bank_account_code=bank_account_code,
        fund_code=fund_code,
        mode=mode,
        minimum_reserve=Decimal(minimum_reserve),
        position_max_age_days=position_max_age_days,
        unclaimed_after_days=unclaimed_after_days,
        stale_after_days=stale_after_days,
        effective_from=effective_from,
        effective_to=effective_to,
        authority_reference=str(authority_reference or "").strip(),
        local_applicability_note=str(local_applicability_note or "").strip(),
        version=version,
        supersedes=prior,
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    _event(actor=actor, action="cash_policy_created", policy=policy, snapshot={
        **_policy_snapshot(policy), "supersedes_policy_public_id": str(prior.public_id) if prior else "",
    })
    return policy


@transaction.atomic
def submit_policy(*, policy, actor):
    _require(actor, "vouchers.prepare_cash_position")
    _require_preparer_scope(actor, policy)
    locked = TreasuryCashPolicy.objects.select_for_update().get(pk=policy.pk)
    if locked.status != locked.DRAFT:
        raise ValidationError("Only a draft cash policy can be submitted. Prepare a reasoned successor after a return.")
    locked.full_clean()
    locked.status = locked.FOR_REVIEW
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=("status", "submitted_by", "submitted_at", "state_version"))
    _event(actor=actor, action="cash_policy_submitted", policy=locked, snapshot=_policy_snapshot(locked))
    return locked


@transaction.atomic
def decide_policy(*, policy, actor, approve, reason):
    _require(actor, "vouchers.approve_cash_position")
    type(policy.configuration_release).objects.select_for_update().get(pk=policy.configuration_release_id)
    route = list(TreasuryCashPolicy.objects.select_for_update().filter(
        configuration_release_id=policy.configuration_release_id,
        bank_account_code=policy.bank_account_code,
        fund_code=policy.fund_code,
    ).order_by("pk"))
    locked = next(item for item in route if item.pk == policy.pk)
    note = str(reason or "").strip()
    if locked.status != locked.FOR_REVIEW:
        raise ValidationError("Only a policy under review can be decided.")
    if not note:
        raise ValidationError("Record the review basis or correction instruction.")
    if actor.pk in (locked.created_by_id, locked.submitted_by_id):
        raise ValidationError("The cash-policy reviewer must differ from its preparer and submitter.")
    if not approve:
        locked.status = locked.RETURNED
        locked.state_version += 1
        locked.save(update_fields=("status", "state_version"))
        _event(actor=actor, action="cash_policy_returned", policy=locked, reason=note)
        return locked
    TreasuryCashPolicy.objects.filter(
        configuration_release=locked.configuration_release,
        bank_account_code=locked.bank_account_code,
        fund_code=locked.fund_code,
        status=locked.ACTIVE,
    ).exclude(pk=locked.pk).update(status=locked.SUPERSEDED)
    locked.status = locked.ACTIVE
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=("status", "approved_by", "approved_at", "state_version"))
    _event(actor=actor, action="cash_policy_activated", policy=locked, reason=note, snapshot=_policy_snapshot(locked))
    return locked


def latest_reconciled_bank_position(policy, as_of_date):
    fund = Fund.objects.filter(
        department_id=policy.configuration_release.department_id,
        code=policy.fund_code,
        is_active=True,
    ).first()
    if fund is None:
        raise ValidationError("The cash policy's Accounting fund is not active.")
    batch = BankStatementBatch.objects.filter(
        department_id=policy.configuration_release.department_id,
        fund=fund,
        bank_account_code=policy.bank_account_code,
        status=BankStatementBatch.RECONCILED,
        period_end__lte=as_of_date,
    ).order_by("-period_end", "-reconciled_at", "-pk").first()
    if batch is None:
        raise ValidationError("No reconciled bank position exists for this bank, fund, and date.")
    snapshot, checksum, *_unused = bank_reconciliation_snapshot(batch)
    if checksum != batch.reconciliation_checksum:
        raise ValidationError("The latest bank-reconciliation checksum no longer agrees with its retained evidence.")
    return batch, snapshot


@transaction.atomic
def create_position(*, policy, actor, as_of_date, confirmed_inflows, confirmed_outflows, other_holds,
                    evidence_reference, preparation_note=""):
    _require(actor, "vouchers.prepare_cash_position")
    _require_preparer_scope(actor, policy)
    policy = TreasuryCashPolicy.objects.select_for_update().get(pk=policy.pk)
    if policy.status != policy.ACTIVE:
        raise ValidationError("Prepare cash positions only under an independently activated policy.")
    batch, bank_snapshot = latest_reconciled_bank_position(policy, as_of_date)
    prior = policy.positions.order_by("-as_of_date", "-version").first()
    version = (policy.positions.filter(as_of_date=as_of_date).aggregate(value=Max("version"))["value"] or 0) + 1
    supersedes = prior if prior and prior.as_of_date == as_of_date else None
    if supersedes and not str(preparation_note or "").strip():
        raise ValidationError("Explain why this successor cash position replaces the prior same-date version.")
    position = TreasuryCashPosition(
        policy=policy,
        as_of_date=as_of_date,
        reconciliation_public_id=batch.public_id,
        reconciliation_checksum=batch.reconciliation_checksum,
        reconciliation_period_end=batch.period_end,
        reconciled_book_balance=Decimal(bank_snapshot["book_balance"]),
        confirmed_inflows=Decimal(confirmed_inflows),
        confirmed_outflows=Decimal(confirmed_outflows),
        other_holds=Decimal(other_holds),
        evidence_reference=str(evidence_reference or "").strip(),
        preparation_note=str(preparation_note or "").strip(),
        version=version,
        supersedes=supersedes,
        created_by=actor,
    )
    position.full_clean()
    position.save()
    _event(actor=actor, action="cash_position_created", policy=policy, position=position,
           snapshot={
               **_position_snapshot(position), "bank_snapshot_checksum": batch.reconciliation_checksum,
               "supersedes_position_public_id": str(supersedes.public_id) if supersedes else "",
           })
    return position


@transaction.atomic
def submit_position(*, position, actor):
    _require(actor, "vouchers.prepare_cash_position")
    _require_preparer_scope(actor, position.policy)
    locked = TreasuryCashPosition.objects.select_for_update().select_related("policy").get(pk=position.pk)
    if locked.status != locked.DRAFT:
        raise ValidationError("Only a draft cash position can be submitted. Prepare a reasoned successor after a return.")
    batch, bank_snapshot = latest_reconciled_bank_position(locked.policy, locked.as_of_date)
    if str(batch.public_id) != str(locked.reconciliation_public_id) or bank_snapshot["book_balance"] != str(locked.reconciled_book_balance):
        raise ValidationError("A newer or changed reconciliation is now authoritative. Prepare a successor cash position.")
    snapshot = _position_snapshot(locked)
    locked.snapshot_checksum = _checksum(snapshot)
    locked.status = locked.FOR_REVIEW
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=("snapshot_checksum", "status", "submitted_by", "submitted_at", "state_version"))
    _event(actor=actor, action="cash_position_submitted", policy=locked.policy, position=locked,
           snapshot={**snapshot, "snapshot_checksum": locked.snapshot_checksum})
    return locked


@transaction.atomic
def decide_position(*, position, actor, approve, reason):
    _require(actor, "vouchers.approve_cash_position")
    policy_id = TreasuryCashPosition.objects.only("policy_id").get(pk=position.pk).policy_id
    TreasuryCashPolicy.objects.select_for_update().get(pk=policy_id)
    locked = TreasuryCashPosition.objects.select_for_update().select_related("policy").get(pk=position.pk)
    note = str(reason or "").strip()
    if locked.status != locked.FOR_REVIEW:
        raise ValidationError("Only a cash position under review can be decided.")
    if not note:
        raise ValidationError("Record the reviewed evidence or correction instruction.")
    if actor.pk in (locked.created_by_id, locked.submitted_by_id):
        raise ValidationError("The cash-position reviewer must differ from its preparer and submitter.")
    if not approve:
        locked.status = locked.RETURNED
        locked.state_version += 1
        locked.save(update_fields=("status", "state_version"))
        _event(actor=actor, action="cash_position_returned", policy=locked.policy, position=locked, reason=note)
        return locked
    batch, bank_snapshot = latest_reconciled_bank_position(locked.policy, locked.as_of_date)
    if (
        str(batch.public_id) != str(locked.reconciliation_public_id)
        or batch.reconciliation_checksum != locked.reconciliation_checksum
        or bank_snapshot["book_balance"] != str(locked.reconciled_book_balance)
    ):
        raise ValidationError("The authoritative bank reconciliation changed during review. Return this version and prepare a successor.")
    snapshot = _position_snapshot(locked)
    if _checksum(snapshot) != locked.snapshot_checksum:
        raise ValidationError("The submitted cash-position snapshot changed during review.")
    TreasuryCashPosition.objects.filter(policy=locked.policy, status=locked.APPROVED).exclude(pk=locked.pk).update(status=locked.SUPERSEDED)
    locked.status = locked.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=("status", "approved_by", "approved_at", "state_version"))
    _event(actor=actor, action="cash_position_approved", policy=locked.policy, position=locked,
           reason=note, snapshot={**snapshot, "snapshot_checksum": locked.snapshot_checksum})
    return locked


def active_policy(*, release, bank_account_code, fund_code, on_date=None):
    on_date = on_date or timezone.localdate()
    return TreasuryCashPolicy.objects.filter(
        configuration_release=release,
        bank_account_code=bank_account_code,
        fund_code=fund_code,
        status=TreasuryCashPolicy.ACTIVE,
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date)).order_by("-version").first()


def policy_availability(policy, on_date=None):
    on_date = on_date or timezone.localdate()
    position = policy.positions.filter(status=TreasuryCashPosition.APPROVED, as_of_date__lte=on_date).order_by("-as_of_date", "-version").first()
    if position is None:
        return {"policy": policy, "position": None, "current": False, "reserved": Decimal("0.00"), "available": None}
    current = position.as_of_date >= on_date - timedelta(days=policy.position_max_age_days)
    reserved = TreasuryCashReservation.objects.filter(
        position__policy__configuration_release__department_id=policy.configuration_release.department_id,
        position__policy__bank_account_code=policy.bank_account_code,
        position__policy__fund_code=policy.fund_code,
        status=TreasuryCashReservation.RESERVED,
    ).aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
    return {
        "policy": policy, "position": position, "current": current,
        "reserved": reserved, "available": position.approved_available_cash - reserved,
    }


def infer_case_fund(case, requested=""):
    requested = str(requested or "").strip()
    funds = list(case.obligation.allocation_lines.values_list("fund_code", flat=True).distinct()) if hasattr(case, "obligation") else []
    if requested:
        if funds and requested not in funds:
            raise ValidationError("The selected cash fund is not carried by this voucher's authoritative obligation.")
        return requested
    return funds[0] if len(funds) == 1 else ""


def preflight_instrument_cash(*, case, bank_account_code, fund_code, amount, on_date=None):
    on_date = on_date or timezone.localdate()
    fund_code = infer_case_fund(case, fund_code)
    route_policies = TreasuryCashPolicy.objects.filter(
        configuration_release=case.configuration_release,
        bank_account_code=bank_account_code,
        status=TreasuryCashPolicy.ACTIVE,
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
    if not fund_code:
        if route_policies.filter(mode=TreasuryCashPolicy.ENFORCE).exists():
            raise ValidationError("Choose the voucher fund before issuing under an enforced cash-control route.")
        return fund_code, None, None
    policy = active_policy(release=case.configuration_release, bank_account_code=bank_account_code, fund_code=fund_code, on_date=on_date)
    if policy is None:
        return fund_code, None, None
    availability = policy_availability(policy, on_date)
    if policy.mode == policy.ENFORCE:
        if availability["position"] is None:
            raise ValidationError("Cash enforcement is active, but no approved cash position covers this bank and fund.")
        if not availability["current"]:
            raise ValidationError("The approved cash position is older than the locally accepted maximum age.")
        if availability["available"] < Decimal(amount):
            raise ValidationError("Available cash after existing reservations and the minimum reserve is insufficient for this instrument.")
    return fund_code, policy, availability


def reserve_instrument_cash(*, instrument, actor, policy, availability):
    if policy is None or availability is None:
        return None
    locked_policy = TreasuryCashPolicy.objects.select_for_update().get(pk=policy.pk)
    current = policy_availability(locked_policy)
    if current["position"] is None:
        if locked_policy.mode == locked_policy.ENFORCE:
            raise ValidationError("Cash enforcement is active, but no approved cash position covers this bank and fund.")
        return None
    if not current["current"] or current["available"] < instrument.amount:
        if locked_policy.mode == locked_policy.ENFORCE:
            raise ValidationError("Available cash changed during issue and is no longer sufficient. Reload the position before retrying.")
        _event(actor=actor, action="cash_reservation_observed_not_created", policy=policy, instrument=instrument,
               snapshot={"mode": policy.mode, "amount": str(instrument.amount), "available": str(current["available"])})
        return None
    reservation = TreasuryCashReservation.objects.create(
        position=current["position"], instrument=instrument, amount=instrument.amount, created_by=actor,
    )
    _event(actor=actor, action="cash_reserved_at_issue", policy=policy, position=current["position"],
           instrument=instrument, snapshot={"amount": str(instrument.amount), "mode": policy.mode})
    return reservation


def close_reservation(*, instrument, actor, status, reason):
    reservation = TreasuryCashReservation.objects.select_for_update().filter(
        instrument=instrument, status=TreasuryCashReservation.RESERVED,
    ).select_related("position__policy").first()
    if reservation is None:
        return None
    reservation.status = status
    reservation.closed_by = actor
    reservation.closed_at = timezone.now()
    reservation.close_reason = str(reason or "").strip()
    reservation.save(update_fields=("status", "closed_by", "closed_at", "close_reason"))
    _event(actor=actor, action=f"cash_reservation_{status}", policy=reservation.position.policy,
           position=reservation.position, instrument=instrument, reason=reservation.close_reason,
           snapshot={"amount": str(reservation.amount)})
    return reservation


@transaction.atomic
def open_instrument_exception(*, instrument, actor, kind, observed_on, reason, evidence_reference):
    _require(actor, "vouchers.manage_payment_exceptions")
    if instrument.case.current_department_id != department_for_user(actor).pk:
        raise PermissionDenied("Instrument exceptions are limited to Treasury's currently assigned cases.")
    reason = str(reason or "").strip()
    evidence_reference = str(evidence_reference or "").strip()
    if not reason or not evidence_reference:
        raise ValidationError("Record both the exception reason and its reviewed evidence reference.")
    if observed_on > timezone.localdate():
        raise ValidationError("The instrument exception date cannot be in the future.")
    policy = active_policy(
        release=instrument.case.configuration_release,
        bank_account_code=instrument.bank_account_code,
        fund_code=instrument.fund_code,
        on_date=observed_on,
    )
    if policy is None:
        raise ValidationError("Activate a locally reviewed cash policy before classifying instrument ageing.")
    age = (observed_on - timezone.localdate(instrument.issued_at)).days
    if kind == PaymentInstrumentException.UNCLAIMED:
        if instrument.status != PaymentInstrument.ADVISED or age < policy.unclaimed_after_days:
            raise ValidationError("Only an advised, unreleased instrument beyond the configured unclaimed threshold can be marked unclaimed.")
        operational = PaymentInstrument.UNCLAIMED
    elif kind == PaymentInstrumentException.STALE:
        if instrument.status != PaymentInstrument.ADVISED or age < policy.stale_after_days:
            raise ValidationError("Only an advised, unreleased instrument beyond the configured stale threshold can be marked stale.")
        operational = PaymentInstrument.STALE
    elif kind == PaymentInstrumentException.RETURNED:
        if instrument.status != PaymentInstrument.RELEASED:
            raise ValidationError("Only a released instrument can be classified as returned by the bank.")
        operational = PaymentInstrument.RETURNED
    else:
        raise ValidationError("Choose a supported instrument exception.")
    PaymentInstrumentException.objects.filter(instrument=instrument, status=PaymentInstrumentException.OPEN).update(
        status=PaymentInstrumentException.RESOLVED,
        resolved_by=actor,
        resolved_at=timezone.now(),
        resolution=f"Superseded by {kind} classification: {reason}",
    )
    exception = PaymentInstrumentException.objects.create(
        instrument=instrument, policy=policy, kind=kind, observed_on=observed_on,
        reason=reason, evidence_reference=evidence_reference, opened_by=actor,
    )
    instrument.operational_status = operational
    instrument.save(update_fields=("operational_status",))
    _event(actor=actor, action=f"instrument_{kind}_classified", policy=policy, instrument=instrument,
           reason=reason, snapshot={"exception_public_id": str(exception.public_id), "evidence_reference": evidence_reference, "age_days": age})
    return exception


@transaction.atomic
def resolve_instrument_exception(*, exception, actor, resolution, permission_required=True):
    if permission_required:
        _require(actor, "vouchers.manage_payment_exceptions")
        if exception.policy.treasury_department != department_for_user(actor):
            raise PermissionDenied("Instrument exception resolution is limited to the owning Treasury department.")
    locked = PaymentInstrumentException.objects.select_for_update().select_related("instrument", "policy").get(pk=exception.pk)
    note = str(resolution or "").strip()
    if locked.status != locked.OPEN or not note:
        raise ValidationError("Resolve an open exception with the reviewed action and evidence.")
    locked.status = locked.RESOLVED
    locked.resolved_by = actor
    locked.resolved_at = timezone.now()
    locked.resolution = note
    locked.save(update_fields=("status", "resolved_by", "resolved_at", "resolution"))
    if not locked.instrument.exceptions.filter(status=PaymentInstrumentException.OPEN).exists():
        locked.instrument.operational_status = PaymentInstrument.NORMAL
        locked.instrument.save(update_fields=("operational_status",))
    _event(actor=actor, action="instrument_exception_resolved", policy=locked.policy,
           instrument=locked.instrument, reason=note, snapshot={"exception_public_id": str(locked.public_id), "kind": locked.kind})
    return locked


def export_cash_position_csv(*, actor, policy=None):
    _require(actor, "vouchers.export_cash_position")
    policies = TreasuryCashPolicy.objects.all().select_related("configuration_release", "treasury_department")
    if policy:
        if not has_explicit_permission(actor, "vouchers.approve_cash_position") and policy.treasury_department != department_for_user(actor):
            raise PermissionDenied
        policies = policies.filter(pk=policy.pk)
    elif not has_explicit_permission(actor, "vouchers.approve_cash_position"):
        policies = policies.filter(treasury_department=department_for_user(actor))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    def write_row(values):
        writer.writerow([
            "'" + value if isinstance(value, str) and value[:1] in ("=", "+", "-", "@") else value
            for value in values
        ])

    write_row([
        "record_type", "policy_id", "bank_account", "fund", "policy_mode", "policy_status",
        "position_id", "as_of_date", "reconciled_book_balance", "confirmed_inflows",
        "confirmed_outflows", "other_holds", "minimum_reserve", "approved_available_cash",
        "reserved_amount", "instrument_number", "instrument_status", "operational_status",
        "exception_kind", "exception_status", "evidence_reference", "snapshot_checksum",
    ])
    for item in policies:
        write_row(["policy", item.public_id, item.bank_account_code, item.fund_code, item.mode, item.status,
                         "", "", "", "", "", "", item.minimum_reserve, "", "", "", "", "", "", "",
                         item.authority_reference, ""])
        for position in item.positions.all().order_by("as_of_date", "version"):
            reserved = position.reservations.filter(status=TreasuryCashReservation.RESERVED).aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
            write_row(["position", item.public_id, item.bank_account_code, item.fund_code, item.mode, item.status,
                             position.public_id, position.as_of_date, position.reconciled_book_balance, position.confirmed_inflows,
                             position.confirmed_outflows, position.other_holds, item.minimum_reserve, position.approved_available_cash,
                             reserved, "", "", "", "", "", position.evidence_reference, position.snapshot_checksum])
            for reservation in position.reservations.select_related("instrument").all():
                instrument = reservation.instrument
                write_row(["reservation", item.public_id, item.bank_account_code, item.fund_code, item.mode, item.status,
                                 position.public_id, position.as_of_date, "", "", "", "", "", "", reservation.amount,
                                 instrument.check_number, instrument.status, instrument.operational_status, "", reservation.status,
                                 reservation.close_reason, position.snapshot_checksum])
        for exception in item.instrument_exceptions.select_related("instrument").all():
            instrument = exception.instrument
            write_row(["instrument_exception", item.public_id, item.bank_account_code, item.fund_code, item.mode, item.status,
                             "", exception.observed_on, "", "", "", "", "", "", "", instrument.check_number,
                             instrument.status, instrument.operational_status, exception.kind, exception.status,
                             exception.evidence_reference, ""])
    content = output.getvalue().encode("utf-8-sig")
    department = policy.treasury_department if policy else department_for_user(actor)
    return content, archive_export(
        content=content, department=department, user=actor, category="finance-cash-position",
        filename=f"cash-position-{timezone.localdate().isoformat()}.csv",
        metadata={"kind": "treasury_cash_position_evidence", "policy_public_id": str(policy.public_id) if policy else "all"},
    )
