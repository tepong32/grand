"""Governed quarterly planning; these services never create financial movements."""
import hashlib
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import AppropriationAuthorization, QuarterlyFinancialPlan, QuarterlyPlanLine
from .services import _require_action, actor_label, obligation_line_balance, record_event

PREPARE = "prepare_allotment_releases"
REVIEW = "approve_allotment_releases"
LINE_FIELDS = tuple(f"q{i}" for i in range(1, 5)) + ("basis", "indicator", "target_unit") + tuple(f"target_q{i}" for i in range(1, 5))


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plan_context(plan):
    rows = []
    for line in plan.lines.select_related("appropriation_line"):
        source = line.appropriation_line
        quarters = [getattr(line, f"q{i}") for i in range(1, 5)]
        complete = all(value is not None for value in quarters)
        planned = sum((value or Decimal("0") for value in quarters), Decimal("0"))
        balances = obligation_line_balance(source, as_of=plan.prepared_on)
        control_sources = [{"kind": "allotment", "id": move.pk, "reference": move.order_number_snapshot,
            "date": move.effective_date.isoformat(), "release_effect": str(move.release_effect), "hold_effect": str(move.hold_effect)}
            for move in source.allotment_movements.filter(effective_date__lte=plan.prepared_on)]
        control_sources += [{"kind": "obligation", "id": move.pk, "reference": move.obligation_number_snapshot,
            "date": move.effective_date.isoformat(), "obligation_effect": str(move.obligation_effect)}
            for move in source.obligation_movements.filter(effective_date__lte=plan.prepared_on)]
        rows.append({"id": line.pk, "source_id": source.pk, "fund": source.fund_code,
            "office": source.responsibility_center_code, "program": source.program_code,
            "account": source.account_code, "particulars": source.particulars,
            "authorized": str(source.amount), "quarters": [str(value) if value is not None else None for value in quarters],
            "complete": complete, "planned": str(planned) if complete else None,
            "unplanned": str(source.amount-planned) if complete else None,
            "basis": line.basis, "indicator": line.indicator, "target_unit": line.target_unit,
            "targets": [getattr(line, f"target_q{i}") for i in range(1, 5)],
            "balances": {key: str(value) for key, value in balances.items()}, "control_sources": control_sources})
    return {"schema": 1, "reference": plan.reference, "version": plan.version,
        "prepared_on": plan.prepared_on.isoformat(), "captured_at": timezone.now().isoformat(),
        "authorization": str(plan.authorization.public_id), "ordinance": plan.authorization.ordinance_number,
        "authority_checksum": plan.authorization.snapshot_checksum,
        "fiscal_year": plan.authorization.version.fiscal_year.year,
        "evidence_reference": plan.evidence_reference, "change_basis": plan.change_basis,
        "supersedes": str(plan.supersedes.public_id) if plan.supersedes_id else None, "rows": rows}


@transaction.atomic(using="finance")
def create_plan(*, authorization, actor, reference, prepared_on, evidence_reference, change_basis):
    authorization = AppropriationAuthorization.objects.select_for_update().get(pk=authorization.pk)
    _require_action(actor, authorization, PREPARE)
    current = authorization.current_quarterly_plan
    version = (authorization.quarterly_plans.aggregate(value=Max("version"))["value"] or 0) + 1
    plan = QuarterlyFinancialPlan(department_id=authorization.department_id,
        department_label=authorization.department_label, authorization=authorization, version=version,
        supersedes=current, reference=reference.strip(), prepared_on=prepared_on,
        evidence_reference=evidence_reference.strip(), change_basis=change_basis.strip(),
        created_by_id=actor.pk, created_by_label=actor_label(actor))
    plan.full_clean(); plan.save()
    prior = {line.appropriation_line_id: line for line in current.lines.all()} if current else {}
    for source in authorization.schedule_lines.all():
        line = QuarterlyPlanLine(plan=plan, appropriation_line=source,
            department_id=plan.department_id, department_label=plan.department_label)
        if source.pk in prior:
            for field in LINE_FIELDS:
                setattr(line, field, getattr(prior[source.pk], field))
        line.full_clean(); line.save()
    record_event(plan, "quarterly_created", actor, plan.change_basis, {"version": version, "supersedes": current.pk if current else None})
    return plan


@transaction.atomic(using="finance")
def edit_line(*, plan, line_id, actor, values):
    plan = QuarterlyFinancialPlan.objects.select_for_update().get(pk=plan.pk)
    _require_action(actor, plan, PREPARE)
    if plan.status not in (plan.DRAFT, plan.RETURNED):
        raise ValidationError("Return the plan before changing its allocations.")
    if set(values) - set(LINE_FIELDS):
        raise ValidationError("Only quarter allocations, targets and their basis may be edited here.")
    line = plan.lines.select_for_update().get(pk=line_id)
    for field, value in values.items():
        setattr(line, field, value.strip() if isinstance(value, str) else value)
    line.full_clean(); line.save()
    record_event(plan, "quarterly_line_changed", actor, snapshot={"line": line.pk,
        "values": {field: str(getattr(line, field)) for field in LINE_FIELDS}})
    return line


@transaction.atomic(using="finance")
def transition_plan(*, plan, action, actor, reason=""):
    # One stable authority lock serializes creation and competing successor approvals.
    authority = AppropriationAuthorization.objects.select_for_update().get(pk=plan.authorization_id)
    plan = QuarterlyFinancialPlan.objects.select_for_update().select_related("authorization", "supersedes").get(pk=plan.pk)
    _require_action(actor, plan, PREPARE if action == "submit" else REVIEW)
    if action == "submit" and plan.status in (plan.DRAFT, plan.RETURNED):
        plan.full_clean()
        if plan.supersedes_id != authority.current_quarterly_plan_id:
            raise ValidationError("A newer approved plan exists. Create a successor from the current plan.")
        source_ids = set(authority.schedule_lines.values_list("pk", flat=True))
        lines = list(plan.lines.select_related("appropriation_line", "plan"))
        if not source_ids or {line.appropriation_line_id for line in lines} != source_ids:
            raise ValidationError("Include the complete authorized schedule.")
        for line in lines:
            line.full_clean()
            if any(getattr(line, f"q{i}") is None for i in range(1, 5)) or not line.basis.strip():
                raise ValidationError("Every line needs four explicit quarterly amounts and a planning basis.")
        plan.submitted_snapshot = plan_context(plan)
        plan.snapshot_checksum = checksum(plan.submitted_snapshot)
        plan.status, plan.submitted_by_id, plan.submitted_at = plan.FOR_REVIEW, actor.pk, timezone.now()
    elif action in ("approve", "return") and plan.status == plan.FOR_REVIEW:
        from .models import BudgetAuditEvent
        contributed = BudgetAuditEvent.objects.filter(target_id=str(plan.public_id), actor_id=actor.pk,
            action__in=("quarterly_created", "quarterly_line_changed", "quarterly_header_changed", "quarterly_submit")).exists()
        if actor.pk == plan.submitted_by_id or actor.pk == plan.created_by_id or contributed:
            raise ValidationError("The preparer cannot independently review this plan.")
        if not reason.strip():
            raise ValidationError("Record the independent review basis or specific correction reason.")
        if action == "approve":
            if plan.supersedes_id != authority.current_quarterly_plan_id:
                raise ValidationError("A newer approved plan exists. This stale review cannot replace it.")
            event = BudgetAuditEvent.objects.filter(target_id=str(plan.public_id), action="quarterly_submit").order_by("-pk").first()
            if not event or event.snapshot.get("context") != plan.submitted_snapshot or checksum(plan.submitted_snapshot) != plan.snapshot_checksum:
                raise ValidationError("The retained review evidence no longer matches submission.")
            live = plan_context(plan)
            # Financial movements after submission remain separate, while editable planning inputs must match.
            retained = plan.submitted_snapshot
            if any(live[key] != retained[key] for key in ("reference", "version", "prepared_on", "authorization", "authority_checksum", "evidence_reference", "change_basis", "supersedes")):
                raise ValidationError("Planning inputs changed after submission. Return and resubmit.")
            strip_controls = lambda rows: [{k: v for k, v in row.items() if k not in {"balances", "control_sources"}} for row in rows]
            if strip_controls(live["rows"]) != strip_controls(retained["rows"]):
                raise ValidationError("Planning rows changed after submission. Return and resubmit.")
            plan.status, plan.approved_by_id, plan.approved_by_label = plan.APPROVED, actor.pk, actor_label(actor)
            plan.approved_at = timezone.now()
        else:
            plan.status = plan.RETURNED
        plan.decision_basis = reason.strip()
    else:
        raise ValidationError("This quarterly planning action is not available in the current state.")
    plan.save()
    if action == "approve":
        AppropriationAuthorization.objects.filter(pk=authority.pk).update(current_quarterly_plan=plan)
    record_event(plan, "quarterly_" + action, actor, reason,
        {"context": plan.submitted_snapshot, "checksum": plan.snapshot_checksum, "status": plan.status})
    return plan


def allotment_planning_context(order, *, retained_plan_id=None):
    from datetime import date
    from django.db.models import Sum
    from .models import AllotmentMovement
    from .services import allotment_effect
    plan_id = retained_plan_id or order.authorization.current_quarterly_plan_id
    if not plan_id:
        return {"schema": 1, "state": "missing", "message": "No approved quarterly plan was available at submission."}
    plan = QuarterlyFinancialPlan.objects.get(pk=plan_id, authorization_id=order.authorization_id, status=QuarterlyFinancialPlan.APPROVED)
    if checksum(plan.submitted_snapshot) != plan.snapshot_checksum or plan.submitted_snapshot.get("authority_checksum") != order.authorization.snapshot_checksum:
        raise ValidationError("The approved planning evidence does not match its retained authority.")
    quarter = (order.effective_date.month - 1) // 3 + 1
    start = date(order.effective_date.year, (quarter-1)*3+1, 1)
    sources = {row["source_id"]: row for row in plan.submitted_snapshot["rows"]}
    effects = {}
    for line in order.lines.all():
        effects[line.appropriation_line_id] = effects.get(line.appropriation_line_id, Decimal("0")) + allotment_effect(line.movement_type, line.amount)[0]
    rows = []
    for source_id, effect in sorted(effects.items()):
        row = sources[source_id]
        released = AllotmentMovement.objects.filter(appropriation_line_id=source_id,
            effective_date__range=(start, order.effective_date)).exclude(order_id=order.pk).aggregate(value=Sum("release_effect"))["value"] or Decimal("0")
        planned = Decimal(row["quarters"][quarter-1])
        rows.append({"source_id": source_id, "fund": row["fund"], "office": row["office"],
            "account": row["account"], "program": row["program"], "planned": str(planned),
            "released_through_date": str(released), "this_release_effect": str(effect),
            "projected_release": str(released+effect), "exceeds_plan": effect > 0 and released+effect > planned})
    return {"schema": 1, "state": "available", "plan_id": plan.pk, "plan": str(plan.public_id),
        "reference": plan.reference, "version": plan.version, "checksum": plan.snapshot_checksum,
        "quarter": quarter, "effective_date": order.effective_date.isoformat(), "rows": rows,
        "deviation_basis": order.planning_deviation_basis,
        "deviation": any(row["exceeds_plan"] for row in rows)}

@transaction.atomic(using="finance")
def edit_header(*, plan, actor, values):
    plan = QuarterlyFinancialPlan.objects.select_for_update().get(pk=plan.pk)
    _require_action(actor, plan, PREPARE)
    if plan.status not in (plan.DRAFT, plan.RETURNED):
        raise ValidationError("Return the plan before changing its header.")
    if set(values) != {"reference", "prepared_on", "evidence_reference", "change_basis"}:
        raise ValidationError("Supply the complete governed planning header.")
    for field, value in values.items():
        setattr(plan, field, value.strip() if isinstance(value, str) else value)
    plan.full_clean(); plan.save()
    record_event(plan, "quarterly_header_changed", actor, snapshot={key: str(value) for key, value in values.items()})
    return plan
