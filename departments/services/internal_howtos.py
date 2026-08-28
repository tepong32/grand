from __future__ import annotations

from fnmatch import fnmatchcase

from django.core.exceptions import PermissionDenied
from django.db import transaction

from ..models import InternalHowTo, InternalHowToStep, InternalHowToStepCompletion
from .query_service import get_department_for_user


def _matches_page(guide, route_name):
    patterns = guide.page_patterns or []
    return not patterns or any(fnmatchcase(route_name or "", pattern) for pattern in patterns)


def visible_internal_how_tos(user, route_name=""):
    department = get_department_for_user(user)
    if not department or not getattr(user, "is_authenticated", False):
        return department, []
    guides = list(
        InternalHowTo.objects.filter(department=department, status=InternalHowTo.PUBLISHED)
        .prefetch_related("steps")
        .order_by("sort_order", "title", "-version")
    )
    visible = [guide for guide in guides if not guide.required_permission or user.has_perm(guide.required_permission)]
    completed_ids = set(
        InternalHowToStepCompletion.objects.filter(
            user=user,
            department=department,
            step__how_to__in=visible,
        ).values_list("step_id", flat=True)
    )
    for guide in visible:
        steps = list(guide.steps.all())
        guide.visible_steps = steps
        guide.completed_step_ids = completed_ids.intersection(step.pk for step in steps)
        guide.completed_count = len(guide.completed_step_ids)
        guide.step_count = len(steps)
        guide.progress_percent = round(100 * guide.completed_count / guide.step_count) if guide.step_count else 0
        guide.matches_current_page = _matches_page(guide, route_name)
    visible.sort(key=lambda guide: (not guide.matches_current_page, guide.sort_order, guide.title.lower()))
    return department, visible


@transaction.atomic
def set_step_completion(*, user, step_id, completed):
    department, guides = visible_internal_how_tos(user)
    visible_step_ids = {
        step.pk
        for guide in guides
        for step in getattr(guide, "visible_steps", guide.steps.all())
    }
    if step_id not in visible_step_ids or not department:
        raise PermissionDenied("This guide is not available for your current department and role.")
    step = InternalHowToStep.objects.select_related("how_to__department").get(pk=step_id)
    if completed:
        completion, _created = InternalHowToStepCompletion.objects.get_or_create(
            user=user,
            step=step,
            defaults={"department": department},
        )
        return completion, True
    InternalHowToStepCompletion.objects.filter(user=user, step=step, department=department).delete()
    return None, False
