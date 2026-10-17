"""Read-only retained custody and review needs; never an HR clearance decision."""
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .access import asset_in_scope, gso_department_for_user, in_gso_scope
from .models import Asset, AssetTransfer


def can_view_custody_review(actor):
    if not all(apps.is_installed(label) for label in ("profiles", "departments", "vouchers")):
        return False
    from vouchers.access import has_explicit_permission
    return bool(actor.is_authenticated and actor.is_active
                and has_explicit_permission(actor, "inventory.view_asset"))


def review_note(actor, asset):
    """Only disclose current HR fields through GRAND's existing profile policy."""
    from profiles.services.profile_service import can_view_profile
    target = asset.custodian_user
    if target is None:
        if asset.last_custody_return_id:
            return "Confirmed return to GSO. Review the retained return receipt and current office location."
        return "No employee link. Review the original documents; names alone do not establish identity."
    if not can_view_profile(actor, target):
        return "Current HR record unavailable to you. Retained custody still needs review with HR."
    profile = getattr(target, "employeeprofile", None)
    if profile is None:
        return "Employee profile unavailable. Retained custody is unchanged."
    if not target.is_active:
        return "Account inactive. This does not establish employment termination or clearance."
    department = profile.assigned_department
    if department is None:
        return "No current HR department. Review the retained assignment with HR."
    if department.pk != asset.assigned_department_id:
        return "HR department differs from the retained assignment. Review documents before moving the asset."
    source = asset.custodian_snapshot
    if (source.get("employee_profile_local_id") != profile.pk
            or source.get("username") != target.username
            or source.get("display_name") != target.get_full_name()
            or source.get("department_label") != department.name):
        return "Employee identity or office label changed. Review the retained handoff history."
    return "Current identity and department match the retained assignment. This is not a clearance finding."


@never_cache
@login_required
@require_GET
def custody_review(request):
    actor = request.user
    if not can_view_custody_review(actor):
        raise PermissionDenied
    office_access = in_gso_scope(actor)
    scope = request.GET.get("scope", "office" if office_access else "mine")
    if scope not in ("office", "mine") or (scope == "office" and not office_access):
        raise PermissionDenied
    assets = Asset.objects.all()
    pending = AssetTransfer.objects.filter(status=AssetTransfer.PENDING)
    if scope == "mine":
        assets = assets.filter(custodian_user=actor)
        pending = pending.filter(Q(destination_custodian_user=actor) | Q(kind=AssetTransfer.RETURN, source_custodian_user=actor))
    elif not actor.is_superuser:
        owner = gso_department_for_user(actor)
        assets = assets.filter(department_id=owner.pk)
        pending = pending.filter(asset__department_id=owner.pk)
    legacy_count = assets.filter(custodian_user__isnull=True, last_custody_return__isnull=True).count() if scope == "office" else None
    returned_count = assets.filter(custodian_user__isnull=True, last_custody_return__isnull=False).count() if scope == "office" else None
    named_count = assets.filter(custodian_user__isnull=False).count()
    mode = request.GET.get("mode", "named")
    if mode not in ("named", "legacy", "returned") or (mode != "named" and scope != "office"):
        raise PermissionDenied
    assets = assets.filter(custodian_user__isnull=(mode != "named"))
    if mode != "named":
        assets = assets.filter(last_custody_return__isnull=(mode == "legacy"))
    query = request.GET.get("q", "").strip()[:100]
    if query:
        assets = assets.filter(Q(asset_name__icontains=query) | Q(property_tag__icontains=query)
            | Q(assigned_office__icontains=query) | Q(custodian_snapshot__username__icontains=query))
        pending = pending.filter(Q(asset__asset_name__icontains=query) | Q(asset__property_tag__icontains=query)
            | Q(destination_custodian__icontains=query) | Q(destination_employee_snapshot__username__icontains=query))
    assets = assets.select_related("custodian_user__employeeprofile__assigned_department", "last_custody_return").only(
        "id", "public_id", "asset_name", "property_tag", "status", "department_id", "assigned_department_id",
        "assigned_department_label", "assigned_office", "custodian_snapshot", "custodian_user_id", "last_custody_return_id",
        "last_custody_return__id", "last_custody_return__source_custodian_user_id",
        "custodian_user__id", "custodian_user__username", "custodian_user__is_active",
        "custodian_user__first_name", "custodian_user__middle_name", "custodian_user__last_name", "custodian_user__ext_name",
        "custodian_user__employeeprofile__id", "custodian_user__employeeprofile__user_id",
        "custodian_user__employeeprofile__assigned_department__id", "custodian_user__employeeprofile__assigned_department__name")
    page = Paginator(assets.order_by("assigned_office", "asset_name", "pk"), 25).get_page(request.GET.get("page"))
    for asset in page:
        asset.custody_review_note = review_note(actor, asset)
        asset.can_open_register = asset_in_scope(actor, asset)
        asset.can_open_return = bool(asset.last_custody_return_id and (
            (in_gso_scope(actor) and asset_in_scope(actor, asset))
            or asset.last_custody_return.source_custodian_user_id == actor.pk))
    pending_page = Paginator(pending.select_related("asset").order_by("-requested_at", "-pk"), 25).get_page(request.GET.get("handoff_page"))
    from .hr_custody_reviews import can_act
    return render(request, "inventory/custody_review.html", dict(page=page, pending_page=pending_page,
        named_count=named_count, legacy_count=legacy_count, returned_count=returned_count, scope=scope, mode=mode, query=query,
        office_access=office_access, hr_review_access=can_act(actor, "view")))
