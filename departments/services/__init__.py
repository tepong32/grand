from .query_service import get_department_for_user, get_dashboard_template
from .dashboard_service import (
    DEFAULT_DASHBOARD_TEMPLATE,
    get_department_dashboard_context,
    get_department_home_context,
)

__all__ = [
    "get_department_for_user",
    "get_dashboard_template",
    "DEFAULT_DASHBOARD_TEMPLATE",
    "get_department_dashboard_context",
    "get_department_home_context",
]
