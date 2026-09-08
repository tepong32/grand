from django.urls import reverse


def accountability_tasks(user, department, today):
    from reporting.accountability_register import ACTION_SPECS, accountability_action_queryset
    from reporting.accountability_services import validate_profile, validate_package, profile_snapshot, package_snapshot, evidence_checksum
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum

    tasks = []
    for action, (kind, label, _allowed, review) in ACTION_SPECS.items():
        for item in accountability_action_queryset(user, action).select_related("department"):
            validation = (validate_profile if kind == "profile" else validate_package)(item)
            snapshot = (profile_snapshot if kind == "profile" else package_snapshot)(item)
            returned = item.status == item.RETURNED
            received = item.submitted_at if review else item.reviewed_at if returned else item.created_at
            errors = list(validation["errors"])
            if review:
                if kind == "profile":
                    if not item.authority_reference.strip() or not item.local_acceptance_note.strip():
                        errors.append("Record reviewed authority and local acceptance before activation.")
                    if evidence_checksum(snapshot) != item.snapshot_checksum:
                        errors.append("Submitted profile checksum differs; return and resubmit it.")
                elif snapshot != item.package_snapshot or evidence_checksum(snapshot) != item.package_checksum:
                    errors.append("Submitted package evidence differs; return and resubmit it.")
            revision = _projection_checksum({
                "snapshot": snapshot, "status": item.status, "updated": item.updated_at.isoformat(),
                "validation_errors": errors, "review_note": item.review_note,
            })
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:accountability-{kind}:{item.public_id}:{action}",
                task_type=f"finance.accountability-{kind}.{action}.v1", area="Reporting",
                case_id=f"accountability-{kind}:{item.public_id}",
                reference=f"{item.name if kind == 'profile' else item.title} v{item.version}",
                subject=label, transaction_type=f"Accountability {kind}", action=label,
                gate=("Independently verify the retained evidence or return it with a correction reason."
                      if review else "Complete the governed requirements before submitting for independent review."),
                owner_queue=f"{'Independent reviewers' if review else 'Preparers'} - {department.name}",
                scope=department.name, received_at=received, due_on=None, due_state="No structured target",
                calendar_basis="Elapsed calendar days since the retained handoff or preparation; reporting periods are not deadlines.",
                age_days=_age_days(received, today),
                state="Returned" if returned else "Exception" if errors else "Ready",
                source_state=item.get_status_display(), source_version=f"projection-sha256:{revision}",
                exception=" ".join(errors),
                url=reverse(f"reporting:accountability_{kind}_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks


def completed_accountability_tasks(user, department, today):
    from reporting.accountability_register import visible_accountability_records
    from reporting.models import FinanceAccountabilityPackageEvent, FinanceAccountabilityPackageProfileEvent
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user):
        return []
    specs = (
        ("profile", FinanceAccountabilityPackageProfileEvent,
         {"submitted": "Submitted accountability profile", "returned": "Returned accountability profile", "activated": "Activated accountability profile"}),
        ("package", FinanceAccountabilityPackageEvent,
         {"submitted": "Submitted accountability package", "returned": "Returned accountability package", "approved": "Approved accountability package"}),
    )
    tasks = []
    for kind, model, labels in specs:
        events = model.objects.filter(actor=user, action__in=labels, **{
            f"{kind}__in": visible_accountability_records(user, kind),
        }).select_related(kind)
        for event in events:
            item = getattr(event, kind)
            event_id = _source_record_identity(f"accountability-{kind}-event", event.pk)
            label = labels[event.action]
            revision = _projection_checksum({
                "event_id": str(event_id), "actor": event.actor_id, "at": event.created_at.isoformat(),
                "action": event.action, "snapshot": event.snapshot, "reason": event.reason,
                "source_id": str(item.public_id), "current_state": item.status,
            })
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:accountability-{kind}-event:{event_id}:completed",
                task_type=f"finance.accountability-{kind}.{event.action}.completed.v1", area="Reporting",
                case_id=f"accountability-{kind}:{item.public_id}",
                reference=f"{item.name if kind == 'profile' else item.title} v{item.version}",
                subject=label, transaction_type=f"Recorded accountability {kind} action", action="View recorded outcome",
                gate=f"The retained event attributes this action to your account: {label}.",
                owner_queue="Your recorded accountability action", scope=department.name,
                received_at=event.created_at, due_on=None, due_state="Recorded completion",
                calendar_basis="Elapsed calendar days since the retained action; reporting periods are not deadlines.",
                age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
                source_version=f"event-sha256:{revision}", exception="",
                url=reverse(f"reporting:accountability_{kind}_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks
