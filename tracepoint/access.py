from django.core.exceptions import PermissionDenied


def department_for_user(user):
    profile = getattr(user, "employeeprofile", None)
    return getattr(profile, "assigned_department", None)


def is_eligible_employee(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and department_for_user(user)
    )


def department_head(user, department=None):
    department = department or department_for_user(user)
    return bool(department and department.deptHead_or_oic_id == getattr(user, "pk", None))


def _authorized(user, permission, department=None):
    if not is_eligible_employee(user):
        return False
    assigned = department_for_user(user)
    if department is not None and assigned != department and not user.is_superuser:
        return False
    department = department or assigned
    return bool(user.is_superuser or department_head(user, department) or user.has_perm(permission))


def can_view_workspace(user, department=None):
    return _authorized(user, "tracepoint.view_tracepoint_workspace", department)


def can_prepare_packets(user, department=None):
    return _authorized(user, "tracepoint.prepare_tracked_packets", department)


def can_print_labels(user, department=None):
    return _authorized(user, "tracepoint.print_packet_labels", department)


def can_complete_packets(user, department=None):
    return _authorized(user, "tracepoint.complete_tracked_packets", department)


def can_resolve_exceptions(user, department=None):
    return _authorized(user, "tracepoint.resolve_tracepoint_exceptions", department)


def can_revoke_credentials(user, department=None):
    return _authorized(user, "tracepoint.revoke_employee_credentials", department)


def can_view_restricted(user, department=None):
    return _authorized(user, "tracepoint.view_restricted_tracepoint", department)


def can_receive_packets(user):
    """Normal receipt is available to every active, assigned LGU employee."""
    return is_eligible_employee(user)


def packet_is_visible(user, packet):
    if not is_eligible_employee(user):
        return False
    if user.is_superuser:
        return True

    department = department_for_user(user)
    direct_participant = user.pk in {
        packet.prepared_by_id,
        packet.current_holder_id,
        packet.final_destination_employee_id,
    } or packet.handoffs.filter(confirmed_by=user).exists() or packet.checkpoints.filter(employee=user).exists()
    department_participant = department.pk in {
        packet.origin_department_id,
        packet.final_destination_department_id,
        packet.current_department_id,
    } or packet.checkpoints.filter(department=department).exists()
    if not direct_participant and not (department_participant and can_view_workspace(user, department)):
        return False
    if packet.confidentiality == packet.INTERNAL:
        return True
    return direct_participant or can_view_restricted(user, department)


def require_packet_visibility(user, packet):
    if not packet_is_visible(user, packet):
        raise PermissionDenied
