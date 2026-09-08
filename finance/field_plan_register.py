"""Shared source selectors for governed field-plan actions."""
from django.db.models import Q

from .access import can_manage_shadow_operation, can_review_shadow_reconciliation, department_for_user
from .models import FinanceShadowCycle, FinanceShadowReconciliationPlan, FinanceCutoverReadinessPlan, FinanceCutoverQualificationPlan


FIELD_PLAN_TYPES = {
    "reconciliation_plan": (FinanceShadowReconciliationPlan, "field-reconciliation-plan", "Reconciliation plan", "shadow_reconciliation_plan"),
    "readiness_plan": (FinanceCutoverReadinessPlan, "field-readiness-plan", "Readiness and support plan", "cutover_readiness_plan"),
    "qualification_plan": (FinanceCutoverQualificationPlan, "field-qualification-plan", "Field qualification plan", "cutover_qualification_plan"),
}
FIELD_PLAN_ACTION_SPECS = {}
for family, (_model, kind, label, route) in FIELD_PLAN_TYPES.items():
    for mode, role in (("prepare", "manage"), ("review", "review")):
        FIELD_PLAN_ACTION_SPECS[f"{mode}_{family}"] = {
            "family": family, "mode": mode, "source_kind": kind, "plan_label": label,
            "role": role, "title": f"{label}s {'to prepare or correct' if mode == 'prepare' else 'for independent review'}",
            "definition": (
                "Draft or returned plans in the acting Finance office; complete the source requirements before submission."
                if mode == "prepare" else
                "Submitted plans in the acting Finance office whose creator and submitter differ from the reviewer."
            ),
            "next_action": (
                "Prepare or correct the local plan, then submit its current evidence for independent review."
                if mode == "prepare" else
                "Inspect the submitted plan and record an independent approval or reasoned return; acceptance requires unchanged evidence."
            ),
            "edit_route": route,
        }


def field_plan_action_records(user, attention, *, cycles=None):
    spec = FIELD_PLAN_ACTION_SPECS[attention]
    model = FIELD_PLAN_TYPES[spec["family"]][0]
    department = department_for_user(user)
    allowed = can_manage_shadow_operation if spec["mode"] == "prepare" else can_review_shadow_reconciliation
    if department is None or not allowed(user, department):
        return model.objects.none()
    records = model.objects.filter(cycle__department=department)
    if cycles is not None:
        records = records.filter(cycle__in=cycles)
    if spec["family"] == "reconciliation_plan":
        records = records.filter(cycle__status=FinanceShadowCycle.DRAFT)
    if spec["mode"] == "prepare":
        records = records.filter(status__in=(model.DRAFT, model.RETURNED))
    else:
        records = records.filter(status=model.SUBMITTED).exclude(Q(created_by=user) | Q(submitted_by=user))
    return records.select_related("cycle", "cycle__department", "created_by", "submitted_by").distinct()
