"""Current source actions for scheduled runs and qualifying-cycle evidence."""
from .access import can_manage_shadow_operation, can_review_shadow_reconciliation, department_for_user
from .models import FinanceShadowCycle, FinanceShadowReconciliationRun, FinanceCutoverQualificationEvidence, FinanceCutoverQualificationPlan


FIELD_CONTROL_TYPES = {
    "reconciliation_run": (FinanceShadowReconciliationRun, "field-reconciliation-run", "Scheduled reconciliation run", "cycle"),
    "qualification_evidence": (FinanceCutoverQualificationEvidence, "field-qualification-evidence", "Qualification evidence", "plan__cycle"),
}
FIELD_CONTROL_ACTION_SPECS = {}
for family, (_model, kind, label, _parent) in FIELD_CONTROL_TYPES.items():
    for mode, role in (("prepare", "manage"), ("review", "review")):
        FIELD_CONTROL_ACTION_SPECS[f"{mode}_{family}"] = {
            "family": family, "mode": mode, "source_kind": kind, "label": label, "role": role,
            "title": f"{label} {'to prepare or correct' if mode == 'prepare' else 'for independent review'}",
            "definition": (
                "Editable source records under the acting Finance office's control; prepare or correct evidence before submission."
                if mode == "prepare" else
                "Submitted source evidence under the acting Finance office's control, excluding the source's disallowed self-review actors."
            ),
            "next_action": (
                "Complete or correct the retained source evidence, then submit it for independent review."
                if mode == "prepare" else
                "Review the retained evidence and record the source's independent decision or reasoned return; unresolved exceptions remain explicit."
            ),
        }


def control_cycle(item):
    return item.plan.cycle if isinstance(item, FinanceCutoverQualificationEvidence) else item.cycle


def field_control_action_records(user, attention, *, cycles=None):
    spec = FIELD_CONTROL_ACTION_SPECS[attention]
    model, _kind, _label, parent = FIELD_CONTROL_TYPES[spec["family"]]
    department = department_for_user(user)
    allowed = can_manage_shadow_operation if spec["mode"] == "prepare" else can_review_shadow_reconciliation
    if department is None or not allowed(user, department):
        return model.objects.none()
    records = model.objects.filter(**{f"{parent}__department": department})
    if cycles is not None:
        records = records.filter(**{f"{parent}__in": cycles})
    if spec["family"] == "qualification_evidence":
        records = records.filter(plan__status=FinanceCutoverQualificationPlan.APPROVED, cycle__status=FinanceShadowCycle.RECONCILED)
    if spec["mode"] == "prepare":
        initial = model.OPEN if spec["family"] == "reconciliation_run" else model.DRAFT
        records = records.filter(status__in=(initial, model.RETURNED))
    else:
        records = records.filter(status=model.SUBMITTED).exclude(submitted_by=user)
        if spec["family"] == "qualification_evidence":
            records = records.exclude(prepared_by=user)
    return records.select_related("cycle", "cycle__department", "plan", "plan__cycle", "plan__cycle__department").distinct()
