from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import (
    AllotmentMovement, AllotmentOrderLine, AllotmentReleaseOrder,
    AppropriationAuthorization, AuthorizedAppropriationLine, BudgetAuditEvent, BudgetCall,
    BudgetProposalLine, BudgetResourceEstimate, BudgetVersion, BudgetVersionSource,
    ObligationMovement, ObligationRequest, ObligationRequestLine, PayableObligationAllocation,
)


def actor_label(user):
    return user.get_full_name().strip() or user.get_username()


def record_event(target, action, user, reason="", snapshot=None):
    return BudgetAuditEvent.objects.create(
        department_id=target.department_id,
        department_label=target.department_label,
        target_type=target._meta.model_name,
        target_id=str(target.public_id),
        action=action,
        actor_id=user.pk,
        actor_label=actor_label(user),
        reason=reason,
        snapshot=snapshot or {},
    )


@transaction.atomic
def transition_call(call, action, user, reason=""):
    call = BudgetCall.objects.select_for_update().get(pk=call.pk)
    now, label = timezone.now(), actor_label(user)
    if action == "submit" and call.status in (BudgetCall.DRAFT, BudgetCall.RETURNED):
        if not call.ceilings.exists():
            raise ValidationError("Add at least one reviewed department ceiling before submission.")
        call.status, call.submitted_by_id, call.submitted_by_label, call.submitted_at = BudgetCall.FOR_REVIEW, user.pk, label, now
    elif action == "publish" and call.status == BudgetCall.FOR_REVIEW:
        if call.submitted_by_id == user.pk:
            raise ValidationError("The call preparer cannot approve the same budget call.")
        call.status, call.approved_by_id, call.approved_by_label, call.approved_at = BudgetCall.PUBLISHED, user.pk, label, now
    elif action == "return" and call.status == BudgetCall.FOR_REVIEW:
        if not reason.strip():
            raise ValidationError("Record a specific correction reason.")
        call.status, call.decision_reason = BudgetCall.RETURNED, reason.strip()
    elif action == "close" and call.status == BudgetCall.PUBLISHED:
        if not reason.strip():
            raise ValidationError("Record why proposal intake is closing.")
        call.status, call.decision_reason = BudgetCall.CLOSED, reason.strip()
    else:
        raise ValidationError("That budget-call transition is not available from the current state.")
    call.state_version += 1
    call.full_clean()
    call.save()
    record_event(call, action, user, reason, {"status": call.status, "state_version": call.state_version})
    return call


def ceiling_differences(version):
    proposed = defaultdict(lambda: Decimal("0"))
    for line in version.lines.all():
        proposed[(line.fund_id, line.expense_class)] += line.amount
    ceilings = {
        (row.fund_id, row.expense_class): row.amount
        for row in version.budget_call.ceilings.filter(requesting_department_id=version.requesting_department_id)
    }
    return [
        {"fund_id": key[0], "expense_class": key[1], "proposed": amount, "ceiling": ceilings.get(key, Decimal("0")), "difference": ceilings.get(key, Decimal("0")) - amount}
        for key, amount in sorted(proposed.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def validate_version_for_submission(version):
    if version.budget_call.status != BudgetCall.PUBLISHED:
        raise ValidationError("Proposals may be submitted only under a published budget call.")
    if not version.lines.exists():
        raise ValidationError("Add at least one classified proposal line.")
    exceeded = [row for row in ceiling_differences(version) if row["difference"] < 0]
    if exceeded:
        raise ValidationError("The proposal exceeds one or more approved department ceilings.")


@transaction.atomic
def transition_version(version, action, user, reason=""):
    version = BudgetVersion.objects.select_for_update().select_related("budget_call").get(pk=version.pk)
    now, label = timezone.now(), actor_label(user)
    if action == "submit" and version.status in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
        validate_version_for_submission(version)
        version.status, version.submitted_by_id, version.submitted_by_label, version.submitted_at = BudgetVersion.FOR_REVIEW, user.pk, label, now
    elif action == "approve" and version.status == BudgetVersion.FOR_REVIEW:
        if version.submitted_by_id == user.pk:
            raise ValidationError("The proposal preparer cannot approve the same budget version.")
        if not reason.strip():
            raise ValidationError("Record the review basis for approval.")
        version.status, version.decided_by_id, version.decided_by_label, version.decided_at = BudgetVersion.APPROVED, user.pk, label, now
        version.decision_reason = reason.strip()
    elif action == "return" and version.status == BudgetVersion.FOR_REVIEW:
        if not reason.strip():
            raise ValidationError("Record a specific correction reason.")
        version.status, version.decision_reason = BudgetVersion.RETURNED, reason.strip()
    else:
        raise ValidationError("That proposal transition is not available from the current state.")
    version.state_version += 1
    version.full_clean()
    version.save()
    record_event(version, action, user, reason, {"status": version.status, "total": str(version.total_amount), "state_version": version.state_version, "spendable": False})
    return version


def compare_versions(left, right):
    def keyed(version):
        rows = defaultdict(lambda: Decimal("0"))
        for line in version.lines.all():
            key = (line.fund.code, line.responsibility_center.code, line.program.code if line.program else "", line.account.code, line.expense_class, line.appropriation_type)
            rows[key] += line.amount
        return rows
    left_rows, right_rows = keyed(left), keyed(right)
    return [
        {"key": key, "left": left_rows[key], "right": right_rows[key], "change": right_rows[key] - left_rows[key]}
        for key in sorted(set(left_rows) | set(right_rows))
    ]


@transaction.atomic
def consolidate_versions(*, sources, user, title, change_explanation):
    source_ids = [item.pk for item in sources]
    sources = list(BudgetVersion.objects.select_for_update().filter(pk__in=source_ids).select_related("budget_call", "fiscal_year"))
    if not sources:
        raise ValidationError("Choose at least one independently approved department proposal.")
    first = sources[0]
    if any(item.status != BudgetVersion.APPROVED or item.kind != BudgetVersion.DEPARTMENT for item in sources):
        raise ValidationError("Only approved department proposal versions may be consolidated.")
    if any(item.budget_call_id != first.budget_call_id for item in sources):
        raise ValidationError("All consolidation sources must use the same annual budget call.")
    next_version = (BudgetVersion.objects.filter(
        budget_call=first.budget_call, kind=BudgetVersion.EXECUTIVE,
    ).aggregate(value=models.Max("version"))["value"] or 0) + 1
    target = BudgetVersion.objects.create(
        department_id=first.department_id, department_label=first.department_label,
        budget_call=first.budget_call, fiscal_year=first.fiscal_year, kind=BudgetVersion.EXECUTIVE,
        version=next_version, title=title, change_explanation=change_explanation,
        created_by_id=user.pk, created_by_label=actor_label(user),
    )
    BudgetVersionSource.objects.bulk_create([
        BudgetVersionSource(
            department_id=target.department_id, department_label=target.department_label,
            target_version=target, source_version=source,
        ) for source in sources
    ])
    line_copies, estimate_copies = [], []
    for source in sources:
        for line in source.lines.all():
            line_copies.append(BudgetProposalLine(
                department_id=target.department_id, department_label=target.department_label,
                version=target, fund=line.fund, responsibility_center=line.responsibility_center,
                program=line.program, funding_source=line.funding_source, account=line.account,
                expense_class=line.expense_class, appropriation_type=line.appropriation_type,
                particulars=line.particulars, performance_target=line.performance_target,
                amount=line.amount, change_explanation=f"Consolidated from {source.title} v{source.version}. {line.change_explanation}".strip(),
            ))
        for estimate in source.resource_estimates.all():
            estimate_copies.append(BudgetResourceEstimate(
                department_id=target.department_id, department_label=target.department_label,
                version=target, funding_source=estimate.funding_source,
                description=f"{source.requesting_department_label}: {estimate.description}",
                amount=estimate.amount, basis=estimate.basis,
            ))
    BudgetProposalLine.objects.bulk_create(line_copies)
    BudgetResourceEstimate.objects.bulk_create(estimate_copies)
    record_event(target, "consolidated", user, change_explanation, {
        "source_version_ids": [str(item.public_id) for item in sources],
        "source_count": len(sources), "line_count": len(line_copies),
        "total": str(target.total_amount), "spendable": False,
    })
    return target


@transaction.atomic
def transition_authorization(authorization, action, user, reason=""):
    authorization = AppropriationAuthorization.objects.select_for_update().select_related("version").get(pk=authorization.pk)
    now, label = timezone.now(), actor_label(user)
    if action == "submit" and authorization.status in (AppropriationAuthorization.DRAFT, AppropriationAuthorization.RETURNED):
        if authorization.review_status not in (AppropriationAuthorization.FAVORABLE, AppropriationAuthorization.CONDITIONAL):
            raise ValidationError("Record the dated favorable review result before submission.")
        if authorization.control_difference != Decimal("0"):
            raise ValidationError("The signed control total must equal the approved version total.")
        authorization.status = AppropriationAuthorization.FOR_REVIEW
        authorization.submitted_by_id, authorization.submitted_by_label, authorization.submitted_at = user.pk, label, now
    elif action == "authorize" and authorization.status == AppropriationAuthorization.FOR_REVIEW:
        if authorization.submitted_by_id == user.pk:
            raise ValidationError("The evidence preparer cannot authorize the same appropriation version.")
        if not reason.strip():
            raise ValidationError("Record the independent authorization basis.")
        if authorization.schedule_lines.exists():
            raise ValidationError("An authorization snapshot already exists; do not duplicate it.")
        payload, snapshots = [], []
        for line in authorization.version.lines.select_related("fund", "responsibility_center", "program", "funding_source", "account"):
            item = {
                "source_line_id": line.pk, "fund_code": line.fund.code,
                "responsibility_center_code": line.responsibility_center.code,
                "program_code": line.program.code if line.program else "",
                "funding_source_code": line.funding_source.code if line.funding_source else "",
                "account_code": line.account.code, "expense_class": line.expense_class,
                "appropriation_type": line.appropriation_type, "particulars": line.particulars,
                "performance_target": line.performance_target, "amount": str(line.amount),
            }
            payload.append(item)
            snapshots.append(AuthorizedAppropriationLine(
                department_id=authorization.department_id, department_label=authorization.department_label,
                authorization=authorization, amount=line.amount, **{key: value for key, value in item.items() if key != "amount"},
            ))
        if not snapshots:
            raise ValidationError("The approved budget version has no appropriation lines to authorize.")
        AuthorizedAppropriationLine.objects.bulk_create(snapshots)
        authorization.snapshot_checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        authorization.status = AppropriationAuthorization.AUTHORIZED
        authorization.authorized_by_id, authorization.authorized_by_label, authorization.authorized_at = user.pk, label, now
        authorization.decision_reason = reason.strip()
        authorization.version.status = BudgetVersion.AUTHORIZED
        authorization.version.state_version += 1
        authorization.version.save(update_fields=("status", "state_version", "updated_at"))
    elif action == "return" and authorization.status == AppropriationAuthorization.FOR_REVIEW:
        if not reason.strip():
            raise ValidationError("Record a specific correction reason.")
        authorization.status, authorization.decision_reason = AppropriationAuthorization.RETURNED, reason.strip()
    else:
        raise ValidationError("That appropriation-authorization transition is unavailable from the current state.")
    authorization.state_version += 1
    authorization.full_clean()
    authorization.save()
    record_event(authorization.version, f"appropriation_{action}", user, reason, {
        "authorization_id": str(authorization.public_id), "status": authorization.status,
        "control_total": str(authorization.signed_control_total),
        "snapshot_checksum": authorization.snapshot_checksum,
        "spendable": authorization.status == AppropriationAuthorization.AUTHORIZED,
    })
    return authorization


def allotment_effect(movement_type, amount):
    amount = Decimal(amount)
    if movement_type == AllotmentOrderLine.RELEASE:
        return amount, Decimal("0")
    if movement_type in (AllotmentOrderLine.RELEASE_REDUCTION, AllotmentOrderLine.RETURN, AllotmentOrderLine.CANCELLATION):
        return -amount, Decimal("0")
    if movement_type in (AllotmentOrderLine.RESERVE, AllotmentOrderLine.DEFERRAL):
        return Decimal("0"), amount
    if movement_type in (AllotmentOrderLine.RESERVE_RELEASE, AllotmentOrderLine.DEFERRAL_RELEASE):
        return Decimal("0"), -amount
    raise ValidationError("Unknown allotment movement type.")


def allotment_line_balance(appropriation_line, *, as_of=None):
    movements = appropriation_line.allotment_movements.all()
    if as_of:
        movements = movements.filter(effective_date__lte=as_of)
    totals = movements.aggregate(released=models.Sum("release_effect"))
    released = totals["released"] or Decimal("0")
    reserved = Decimal("0")
    deferred = Decimal("0")
    for movement_type, hold_effect in movements.values_list("movement_type", "hold_effect"):
        if movement_type in (AllotmentOrderLine.RESERVE, AllotmentOrderLine.RESERVE_RELEASE):
            reserved += hold_effect
        elif movement_type in (AllotmentOrderLine.DEFERRAL, AllotmentOrderLine.DEFERRAL_RELEASE):
            deferred += hold_effect
    held = reserved + deferred
    return {
        "authorized": appropriation_line.amount,
        "released": released,
        "reserved": reserved,
        "deferred": deferred,
        "held": held,
        "unreleased": appropriation_line.amount - released,
        "executable": released - held,
    }


def authorization_allotment_totals(authorization):
    totals = {key: Decimal("0") for key in ("authorized", "released", "reserved", "deferred", "held", "unreleased", "executable")}
    for line in authorization.schedule_lines.all():
        balance = allotment_line_balance(line)
        for key in totals:
            totals[key] += balance[key]
    return totals


def validate_allotment_order(order, *, lock_lines=False):
    order.full_clean()
    if order.control_difference != Decimal("0"):
        raise ValidationError("The signed allotment control total must equal the exact schedule total.")
    lines = list(order.lines.select_related("appropriation_line"))
    if not lines:
        raise ValidationError("Add at least one authorized appropriation line to the allotment schedule.")
    appropriation_ids = sorted({line.appropriation_line_id for line in lines})
    locked = AuthorizedAppropriationLine.objects.filter(pk__in=appropriation_ids)
    if lock_lines:
        locked = locked.select_for_update()
    appropriation_lines = {line.pk: line for line in locked}
    projected = {pk: allotment_line_balance(line) for pk, line in appropriation_lines.items()}
    for line in lines:
        line.full_clean()
        balance = projected[line.appropriation_line_id]
        release_effect, hold_effect = allotment_effect(line.movement_type, line.amount)
        balance["released"] += release_effect
        if line.movement_type in (AllotmentOrderLine.RESERVE, AllotmentOrderLine.RESERVE_RELEASE):
            balance["reserved"] += hold_effect
        elif line.movement_type in (AllotmentOrderLine.DEFERRAL, AllotmentOrderLine.DEFERRAL_RELEASE):
            balance["deferred"] += hold_effect
        balance["held"] = balance["reserved"] + balance["deferred"]
        balance["unreleased"] = balance["authorized"] - balance["released"]
        balance["executable"] = balance["released"] - balance["held"]
        if balance["released"] < 0:
            raise ValidationError(f"{line.appropriation_line}: the order would reduce released allotment below zero.")
        if balance["released"] > balance["authorized"]:
            raise ValidationError(f"{line.appropriation_line}: cumulative releases would exceed the authorized appropriation.")
        if balance["reserved"] < 0:
            raise ValidationError(f"{line.appropriation_line}: the order would release more reserve than remains held.")
        if balance["deferred"] < 0:
            raise ValidationError(f"{line.appropriation_line}: the order would lift more deferral than remains held.")
        if balance["executable"] < 0:
            raise ValidationError(f"{line.appropriation_line}: reserve or deferral would exceed released allotment.")
        obligated = line.appropriation_line.obligation_movements.aggregate(
            total=models.Sum("obligation_effect")
        )["total"] or Decimal("0")
        if balance["executable"] < obligated:
            raise ValidationError(
                f"{line.appropriation_line}: the allotment change would fall below already certified obligations."
            )
    return lines, projected


@transaction.atomic
def transition_allotment_order(order, action, user, reason=""):
    order = AllotmentReleaseOrder.objects.select_for_update().select_related(
        "authorization", "authorization__version", "fiscal_year"
    ).get(pk=order.pk)
    now, label = timezone.now(), actor_label(user)
    if action == "submit" and order.status in (AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED):
        validate_allotment_order(order, lock_lines=True)
        order.status = AllotmentReleaseOrder.FOR_REVIEW
        order.submitted_by_id, order.submitted_by_label, order.submitted_at = user.pk, label, now
    elif action == "post" and order.status == AllotmentReleaseOrder.FOR_REVIEW:
        if order.submitted_by_id == user.pk:
            raise ValidationError("The allotment preparer cannot post the same release order.")
        if not reason.strip():
            raise ValidationError("Record the independent posting and control-total review basis.")
        if order.movements.exists():
            raise ValidationError("This allotment order already has posted movements.")
        lines, projected = validate_allotment_order(order, lock_lines=True)
        payload, movements = [], []
        for line in lines:
            release_effect, hold_effect = allotment_effect(line.movement_type, line.amount)
            item = {
                "source_line_id": line.pk,
                "appropriation_line_id": line.appropriation_line_id,
                "movement_type": line.movement_type,
                "amount": str(line.amount),
                "release_effect": str(release_effect),
                "hold_effect": str(hold_effect),
                "effective_date": order.effective_date.isoformat(),
                "order_number": order.order_number,
                "authority_reference": order.authority_reference,
                "remarks": line.remarks,
            }
            payload.append(item)
            movements.append(AllotmentMovement(
                department_id=order.department_id, department_label=order.department_label,
                order=order, source_line_id=line.pk, appropriation_line_id=line.appropriation_line_id,
                movement_type=line.movement_type, amount=line.amount,
                release_effect=release_effect, hold_effect=hold_effect,
                effective_date=order.effective_date, order_number_snapshot=order.order_number,
                authority_reference_snapshot=order.authority_reference, remarks=line.remarks,
            ))
        AllotmentMovement.objects.bulk_create(movements)
        order.snapshot_checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        order.status = AllotmentReleaseOrder.POSTED
        order.posted_by_id, order.posted_by_label, order.posted_at = user.pk, label, now
        order.decision_reason = reason.strip()
    elif action == "return" and order.status == AllotmentReleaseOrder.FOR_REVIEW:
        if not reason.strip():
            raise ValidationError("Record a specific correction reason.")
        order.status, order.decision_reason = AllotmentReleaseOrder.RETURNED, reason.strip()
    else:
        raise ValidationError("That allotment-order transition is unavailable from the current state.")
    order.state_version += 1
    order.full_clean()
    order.save()
    record_event(order, f"allotment_{action}", user, reason, {
        "status": order.status, "order_number": order.order_number,
        "control_total": str(order.signed_control_total), "snapshot_checksum": order.snapshot_checksum,
        "movement_count": order.movements.count(),
    })
    return order


def obligation_line_balance(appropriation_line, *, as_of=None):
    allotment = allotment_line_balance(appropriation_line, as_of=as_of)
    movements = appropriation_line.obligation_movements.all()
    if as_of:
        movements = movements.filter(effective_date__lte=as_of)
    obligated = movements.aggregate(total=models.Sum("obligation_effect"))["total"] or Decimal("0")
    return {
        **allotment,
        "obligated": obligated,
        "unobligated": allotment["executable"] - obligated,
    }


def authorization_obligation_totals(authorization):
    keys = (
        "authorized", "released", "reserved", "deferred", "held", "unreleased",
        "executable", "obligated", "unobligated",
    )
    totals = {key: Decimal("0") for key in keys}
    for line in authorization.schedule_lines.all():
        balance = obligation_line_balance(line)
        for key in keys:
            totals[key] += balance[key]
    return totals


def obligation_lineage_root(request):
    root, seen = request, set()
    while root.corrects_id and root.pk not in seen:
        seen.add(root.pk)
        root = root.corrects
    return root


def obligation_lineage_request_ids(request):
    root = obligation_lineage_root(request)
    lineage, frontier = set(), [root.pk]
    while frontier:
        batch = [pk for pk in frontier if pk not in lineage]
        if not batch:
            break
        lineage.update(batch)
        frontier = list(ObligationRequest.objects.filter(
            corrects_id__in=batch, status=ObligationRequest.CERTIFIED,
        ).values_list("pk", flat=True))
    return lineage


def downstream_issuance_boundary(request):
    """Return the first issued downstream artifact without making it a runtime dependency."""
    from vouchers.models import DisbursementVoucher, PaymentInstrument
    root = obligation_lineage_root(request)
    case_ids = set(ObligationRequest.objects.filter(
        pk__in=obligation_lineage_request_ids(request), linked_voucher_case_public_id__isnull=False,
    ).values_list("linked_voucher_case_public_id", flat=True))
    case_ids.update(PayableObligationAllocation.objects.filter(
        obligation=root, status=PayableObligationAllocation.ACTIVE,
    ).values_list("voucher_case_public_id", flat=True))
    if PaymentInstrument.objects.filter(case__public_id__in=case_ids).exclude(status=PaymentInstrument.DRAFT).exists():
        return "check"
    if DisbursementVoucher.objects.filter(case__public_id__in=case_ids).exists():
        return "disbursement voucher"
    return ""


def validate_obligation_request(request, *, lock_lines=False):
    request.full_clean()
    if request.control_difference != Decimal("0"):
        raise ValidationError("The signed obligation control total must equal the signed effect of the exact schedule.")
    lines = list(request.lines.select_related("appropriation_line"))
    if not lines:
        raise ValidationError("Add at least one authorized appropriation line before submission.")
    if request.kind != ObligationRequest.ORIGINAL:
        boundary = downstream_issuance_boundary(request.corrects)
        if boundary:
            raise ValidationError(
                f"The corrected obligation already has an issued {boundary}; use the later voucher/payment reversal or cancellation route."
            )
    line_ids = sorted({item.appropriation_line_id for item in lines})
    queryset = AuthorizedAppropriationLine.objects.filter(pk__in=line_ids)
    if lock_lines:
        queryset = queryset.select_for_update()
    locked = {item.pk: item for item in queryset}
    projected = defaultdict(lambda: Decimal("0"))
    for item in lines:
        if item.appropriation_line_id not in locked:
            raise ValidationError("An obligation line no longer resolves to its authorized appropriation.")
        projected[item.appropriation_line_id] += item.effect
    for line_id, effect in projected.items():
        line = locked[line_id]
        if request.kind != ObligationRequest.ORIGINAL and effect < Decimal("0"):
            lineage_ids = obligation_lineage_request_ids(request.corrects)
            lineage_effect = ObligationMovement.objects.filter(
                request_id__in=lineage_ids, appropriation_line_id=line_id,
            ).aggregate(total=models.Sum("obligation_effect"))["total"] or Decimal("0")
            if lineage_effect + effect < Decimal("0"):
                raise ValidationError(
                    f"The reduction exceeds the remaining obligation in the linked correction lineage for {line}."
                )
        dated = obligation_line_balance(line, as_of=request.obligation_date)
        current = obligation_line_balance(line)
        for label, balance in (("effective-date", dated), ("current", current)):
            resulting = balance["obligated"] + effect
            if resulting < Decimal("0"):
                raise ValidationError(f"The {label} obligation balance cannot be reduced below zero for {line}.")
            if resulting > balance["executable"]:
                raise ValidationError(f"The request exceeds the {label} unobligated allotment for {line}.")
    return lines


@transaction.atomic
def transition_obligation_request(request, action, user, reason="", obligation_number=""):
    request = ObligationRequest.objects.select_for_update().select_related(
        "authorization", "authorization__version", "fiscal_year", "corrects"
    ).get(pk=request.pk)
    now, label = timezone.now(), actor_label(user)
    actor_department = getattr(getattr(user, "employeeprofile", None), "assigned_department", None)
    if action == "submit" and request.status in (ObligationRequest.DRAFT, ObligationRequest.RETURNED):
        if not actor_department or actor_department.pk != request.requesting_department_id:
            raise ValidationError("Only the recorded requesting office may submit this obligation request.")
        validate_obligation_request(request)
        request.status = ObligationRequest.FOR_CERTIFICATION
        request.submitted_by_id, request.submitted_by_label, request.submitted_at = user.pk, label, now
    elif action == "certify" and request.status == ObligationRequest.FOR_CERTIFICATION:
        if not actor_department or actor_department.pk != request.department_id:
            raise ValidationError("Only the owning Budget office may certify this obligation.")
        if request.submitted_by_id == user.pk:
            raise ValidationError("The requesting-office submitter cannot certify the same obligation.")
        if not obligation_number.strip():
            raise ValidationError("Assign the controlled ALOBS/ORS/OBR number at certification.")
        if not reason.strip():
            raise ValidationError("Record the Budget certification and balance-review basis.")
        request.obligation_number = obligation_number.strip()
        lines = validate_obligation_request(request, lock_lines=True)
        if request.movements.exists():
            raise ValidationError("Certified movements already exist; do not post this request twice.")
        payload, movements = [], []
        for line in lines:
            item = {
                "source_line_id": line.pk, "appropriation_line_id": line.appropriation_line_id,
                "movement_type": line.movement_type, "amount": str(line.amount),
                "obligation_effect": str(line.effect), "remarks": line.remarks,
            }
            payload.append(item)
            movements.append(ObligationMovement(
                department_id=request.department_id, department_label=request.department_label,
                request=request, source_line_id=line.pk, appropriation_line=line.appropriation_line,
                movement_type=line.movement_type, amount=line.amount, obligation_effect=line.effect,
                effective_date=request.obligation_date, obligation_number_snapshot=request.obligation_number,
                requesting_department_snapshot=request.requesting_department_label,
                claimant_payee_snapshot=request.claimant_payee, particulars_snapshot=request.particulars,
                remarks=line.remarks,
            ))
        ObligationMovement.objects.bulk_create(movements)
        request.snapshot_checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        request.status = ObligationRequest.CERTIFIED
        request.certified_by_id, request.certified_by_label, request.certified_at = user.pk, label, now
        request.decision_reason = reason.strip()
    elif action == "return" and request.status == ObligationRequest.FOR_CERTIFICATION:
        if not actor_department or actor_department.pk != request.department_id:
            raise ValidationError("Only the owning Budget office may return this obligation request.")
        if not reason.strip():
            raise ValidationError("Record a specific guided correction reason.")
        request.status, request.decision_reason = ObligationRequest.RETURNED, reason.strip()
    else:
        raise ValidationError("That obligation transition is unavailable from the current state.")
    request.state_version += 1
    request.full_clean()
    request.save()
    record_event(request, f"obligation_{action}", user, reason, {
        "request_reference": request.request_reference, "obligation_number": request.obligation_number,
        "status": request.status, "signed_control_total": str(request.signed_control_total),
        "snapshot_checksum": request.snapshot_checksum,
    })
    return request
