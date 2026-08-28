from django.db.models import Q
from django.utils import timezone

from .models import FinanceWorkflowExemption


def workflow_exemption_for(*, actor, control_code, department_id, as_of=None):
    """Return the most specific active exemption without weakening normal permissions."""
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False):
        return None
    assigned_department_id = getattr(
        getattr(actor, "employeeprofile", None), "assigned_department_id", None,
    )
    if assigned_department_id != department_id:
        return None
    as_of = as_of or timezone.localdate()
    return (
        FinanceWorkflowExemption.objects.filter(
            department_id=department_id,
            control_code=control_code,
            is_active=True,
            effective_from__lte=as_of,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .filter(Q(subject_user=actor) | Q(subject_group__user=actor))
        .select_related("department", "subject_user", "subject_group", "created_by")
        .order_by("-subject_user_id", "-effective_from", "-pk")
        .first()
    )


def workflow_exemption_snapshot(exemption):
    if exemption is None:
        return None
    subject_type = "user" if exemption.subject_user_id else "group"
    subject = exemption.subject_user if exemption.subject_user_id else exemption.subject_group
    return {
        "policy_id": exemption.pk,
        "control_code": exemption.control_code,
        "department_id": exemption.department_id,
        "subject_type": subject_type,
        "subject_id": subject.pk,
        "subject_label": str(subject),
        "rationale": exemption.rationale,
        "effective_from": exemption.effective_from.isoformat(),
        "effective_to": exemption.effective_to.isoformat() if exemption.effective_to else None,
        "authorized_by_id": exemption.created_by_id,
        "authorized_by_label": exemption.created_by.get_full_name() or exemption.created_by.username,
    }
