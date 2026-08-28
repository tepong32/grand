from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import (
    AppropriationAuthorization, AuthorizedAppropriationLine, BudgetAuditEvent, BudgetCall,
    BudgetProposalLine, BudgetResourceEstimate, BudgetVersion, BudgetVersionSource,
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
