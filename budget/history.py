from django.core.paginator import Paginator

from .models import BudgetAuditEvent


def history_page(target, request):
    """Retained history for an already authorized Budget target."""
    events = BudgetAuditEvent.objects.filter(
        department_id=target.department_id, target_id=str(target.public_id),
    ).order_by("-created_at", "-pk")
    page = Paginator(events, 30).get_page(request.GET.get("events_page"))
    page.expanded = "events_page" in request.GET
    params = request.GET.copy()
    for name, number in (("previous_url", page.number - 1), ("next_url", page.number + 1)):
        params["events_page"] = number
        setattr(page, name, "?" + params.urlencode() + "#budget-history")
    return page
