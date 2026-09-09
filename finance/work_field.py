from django.urls import reverse


def completed_field_tasks(user, department, today):
    """Resolve field audit events through current cycle and child-record custody."""
    from .access import can_view_shadow_cycle
    from .models import FinanceAuditEvent, FinanceShadowDefect, FinanceCutoverReadinessExercise, FinanceStakeholderAcceptance, FinanceCutoverDecision
    from .shadow_register_exports import visible_shadow_cycles
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user):
        return []
    cycles = {str(item.pk): item for item in visible_shadow_cycles(user) if can_view_shadow_cycle(user, item)}
    if not cycles:
        return []
    defects = {str(item.pk): item for item in FinanceShadowDefect.objects.filter(cycle_id__in=cycles)}
    exercises = {str(item.pk): item for item in FinanceCutoverReadinessExercise.objects.filter(cycle_id__in=cycles)}
    stakeholders = {str(item.pk): item for item in FinanceStakeholderAcceptance.objects.filter(cycle_id__in=cycles)}
    decisions = {str(item.pk): item for item in FinanceCutoverDecision.objects.filter(cycle_id__in=cycles)}
    from .field_plan_register import FIELD_PLAN_TYPES
    plans = {kind: {str(item.pk): item for item in model.objects.filter(cycle_id__in=cycles)}
             for model, kind, _label, _route in FIELD_PLAN_TYPES.values()}
    plan_labels = {kind: label for _model, kind, label, _route in FIELD_PLAN_TYPES.values()}
    from .field_control_register import FIELD_CONTROL_TYPES, control_cycle
    controls = {kind: {str(item.pk): item for item in model.objects.filter(**{f"{parent}_id__in": cycles}).select_related("cycle", "plan__cycle")}
                for model, kind, _label, parent in FIELD_CONTROL_TYPES.values()}
    specs = {
        "stakeholder_acceptance_recorded": ("field-stakeholder", "Recorded stakeholder decision"),
        "cutover_decision_submitted": ("field-cutover", "Submitted cutover authority record"),
        "finance_cutover_authorized": ("field-cutover", "Recorded cutover authorization"),
        "finance_cutover_declined": ("field-cutover", "Recorded cutover decline"),
        "finance_cutover_rolled_back": ("field-cutover", "Recorded rollback direction"),
        "shadow_cycle_started": ("field-cycle", "Started field cycle"),
        "shadow_cycle_submitted": ("field-cycle", "Submitted field cycle for reconciliation"),
        "shadow_cycle_reconciled": ("field-cycle", "Independently reconciled field cycle"),
        "shadow_cycle_returned": ("field-cycle", "Returned field cycle for a successor"),
        "cutover_readiness_exercise_scheduled": ("field-exercise", "Scheduled readiness exercise"),
        "shadow_defect_registered": ("field-defect", "Registered field defect"),
        "shadow_defect_escalated": ("field-defect", "Recorded defect escalation"),
        "shadow_defect_resolution_submitted": ("field-defect", "Submitted defect correction"),
        "shadow_defect_resolution_accepted": ("field-defect", "Independently accepted defect resolution"),
        "shadow_defect_resolution_returned": ("field-defect", "Returned defect correction"),
        "cutover_readiness_exercise_submitted": ("field-exercise", "Submitted exercise result"),
        "cutover_readiness_exercise_passed": ("field-exercise", "Independently witnessed exercise pass"),
        "cutover_readiness_exercise_returned": ("field-exercise", "Returned exercise for rerun"),
    }
    for prefix, kind in (
        ("shadow_reconciliation_plan", "field-reconciliation-plan"),
        ("cutover_readiness_plan", "field-readiness-plan"),
        ("cutover_qualification_plan", "field-qualification-plan"),
    ):
        for action, label in (("submitted", "Submitted"), ("approved", "Independently approved"), ("returned", "Returned for correction")):
            specs[f"{prefix}_{action}"] = (kind, f"{label}: {plan_labels[kind]}")
    specs.update({
        "shadow_reconciliation_run_opened": ("field-reconciliation-run", "Opened scheduled reconciliation run"),
        "shadow_reconciliation_run_submitted": ("field-reconciliation-run", "Submitted scheduled run"),
        "shadow_reconciliation_run_reviewed": ("field-reconciliation-run", "Independently reviewed scheduled run"),
        "shadow_reconciliation_run_returned": ("field-reconciliation-run", "Returned scheduled run for correction"),
        "cutover_qualification_evidence_submitted": ("field-qualification-evidence", "Submitted qualification evidence"),
        "cutover_qualification_evidence_accepted": ("field-qualification-evidence", "Independently accepted qualification evidence"),
        "cutover_qualification_evidence_returned": ("field-qualification-evidence", "Returned qualification evidence"),
        "cutover_qualification_evidence_corrected": ("field-qualification-evidence", "Corrected qualification evidence references"),
    })
    events = FinanceAuditEvent.objects.filter(
        target_type="financeshadowcycle", target_id__in=cycles, actor=user, action__in=specs,
    )
    tasks = []
    for event in events:
        cycle = cycles[event.target_id]
        if event.department_id != cycle.department_id or not isinstance(event.snapshot, dict):
            continue
        kind, label = specs[event.action]
        if kind == "field-cycle":
            if event.snapshot.get("cycle_public_id") != str(cycle.public_id):
                continue
            item, source_id = cycle, cycle.public_id
        else:
            records, key = {
                **{plan_kind: (items, "plan_id") for plan_kind, items in plans.items()},
                "field-reconciliation-run": (controls["field-reconciliation-run"], "run_id"),
                "field-qualification-evidence": (controls["field-qualification-evidence"], "evidence_id"),
                "field-defect": (defects, "defect_id"), "field-exercise": (exercises, "exercise_id"),
                "field-stakeholder": (stakeholders, "acceptance_id"), "field-cutover": (decisions, "decision_id"),
            }[kind]
            item = records.get(str(event.snapshot.get(key)))
            if item is None:
                continue
            parent_id = control_cycle(item).pk if kind in controls else item.cycle_id
            if parent_id != cycle.pk:
                continue
            if kind == "field-qualification-evidence" and event.snapshot.get("cycle_id") != item.cycle_id:
                continue
            source_id = _source_record_identity(kind, item.pk)
        current_state = item.decision if kind == "field-stakeholder" else item.status
        state_label = item.get_decision_display() if kind == "field-stakeholder" else item.get_status_display()
        if event.action == "cutover_readiness_exercise_scheduled":
            if (event.actor_id != item.created_by_id or event.snapshot.get("created_by_id") != event.actor_id
                    or event.snapshot.get("status") != item.PLANNED):
                continue
        elif event.action == "shadow_defect_registered":
            if (event.actor_id != item.created_by_id or event.snapshot.get("status") != item.OPEN
                    or event.snapshot.get("comparison_id") != item.comparison_id):
                continue
        elif event.action == "shadow_defect_escalated":
            from django.utils.dateparse import parse_datetime
            from django.utils.timezone import is_aware
            count = event.snapshot.get("escalation_count")
            try:
                recorded_at = parse_datetime(event.snapshot.get("last_escalation_at", ""))
            except (TypeError, ValueError):
                recorded_at = None
            if (type(count) is not int or not 0 < count <= item.escalation_count
                    or event.snapshot.get("last_escalated_by_id") != event.actor_id
                    or event.snapshot.get("status") not in (item.OPEN, item.RESOLUTION_REVIEW)
                    or event.snapshot.get("last_escalation_note") != event.reason.strip()
                    or not recorded_at or not is_aware(recorded_at) or recorded_at > event.created_at):
                continue
            label = f"Recorded defect escalation #{count}"
        if kind == "field-stakeholder":
            decision = event.snapshot.get("decision")
            if decision not in (item.ACCEPTED, item.CONDITIONAL, item.REJECTED):
                continue
            label = f"Recorded stakeholder decision: {dict(item.DECISION_CHOICES)[decision]}"
        if event.action == "shadow_reconciliation_run_reviewed":
            reviewed_status = event.snapshot.get("status")
            if reviewed_status not in (item.RECONCILED, item.REVIEWED_WITH_EXCEPTIONS):
                continue
            label = "Reviewed scheduled run with open exceptions" if reviewed_status == item.REVIEWED_WITH_EXCEPTIONS else "Independently reconciled scheduled run"
        reference = cycle.code
        if kind in ("field-defect", "field-exercise"):
            reference += f" - {item.code}"
        elif kind == "field-stakeholder":
            reference += f" - {item.get_stakeholder_kind_display()}"
        elif kind == "field-reconciliation-run":
            reference += f" - run #{item.sequence}"
        elif kind == "field-qualification-evidence":
            reference += f" - qualification #{item.sequence}: {item.cycle.code}"
        elif kind in plan_labels:
            reference += f" - {plan_labels[kind]}"
        elif kind == "field-cutover":
            reference += " - cutover decision"
        event_id = _source_record_identity("field-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "actor": event.actor_id, "action": event.action,
            "at": event.created_at.isoformat(), "reason": event.reason, "snapshot": event.snapshot,
            "source_id": str(source_id), "current_state": current_state,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:field-event:{event_id}:completed",
            task_type=f"finance.{kind}.{event.action}.completed.v1", area="Field operation",
            case_id=f"{kind}:{source_id}", reference=reference,
            subject=label, transaction_type="Recorded field operation action", action="View recorded outcome",
            gate=f"The retained audit event attributes this action to your account: {label}.",
            owner_queue="Your recorded field action", scope=f"{cycle.department.name}; {cycle.enabled_scope}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained action; current source status is shown separately.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=state_label,
            source_version=f"event-sha256:{revision}", exception="",
            url=reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}),
        ))
    return tasks
