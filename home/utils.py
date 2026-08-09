from departments.services.dashboard_service import get_department_dashboard_context as _get_department_dashboard_context


def get_department_dashboard_context(department, user):
    """
    Returns extra context specific to a department's dashboard.
    Delegates implementation to departments service so policy is maintained in one place.
    """
    return _get_department_dashboard_context(department, user)
