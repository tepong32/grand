from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import can, gso_department_for_user
from .models import Asset
from .employee_sources import require_employee_custody_manager, resolve_employee_custodian
from .employee_custody_forms import EmployeeHandoffForm, ConfirmEmployeeHandoffForm
from .services import create_asset_transfer, custody_source

TOKEN_SALT = "gso-employee-custody-handoff-v1"


def employee_results(actor, query):
    from profiles.services.profile_service import can_view_profile
    # Only directory columns needed to select custody; never HR/payroll identifiers.
    rows = get_user_model().objects.filter(is_active=True, employeeprofile__assigned_department__isnull=False)
    if not query:
        return rows.none()
    matches = rows.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).select_related("employeeprofile__assigned_department").only(
            "pk", "username", "is_active", "first_name", "middle_name", "last_name", "ext_name",
            "employeeprofile__id", "employeeprofile__user_id", "employeeprofile__assigned_department__id",
            "employeeprofile__assigned_department__name").order_by("last_name", "first_name", "pk")[:25]
    return [row for row in matches if can_view_profile(actor, row)]


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def employee_handoff(request, pk):
    require_employee_custody_manager(request.user)
    if not can(request.user, "view"):
        raise PermissionDenied
    rows = Asset.objects.all()
    if not request.user.is_superuser:
        rows = rows.filter(department_id=gso_department_for_user(request.user).pk)
    asset = get_object_or_404(rows, pk=pk)
    query = (request.POST.get("query", "") if request.method == "POST" else request.GET.get("q", "")).strip()[:100]
    employees = list(employee_results(request.user, query))
    form = EmployeeHandoffForm(request.POST if request.method == "POST" else None,
                               employees=employees, initial={"query": query})
    preview, confirmation = None, None
    if request.method == "POST" and request.POST.get("action") == "confirm":
        confirmation = ConfirmEmployeeHandoffForm(request.POST)
        if confirmation.is_valid():
            try:
                payload = signing.loads(confirmation.cleaned_data["handoff_token"], salt=TOKEN_SALT, max_age=1800)
                if payload["actor_id"] != request.user.pk or payload["asset_id"] != str(asset.public_id):
                    raise PermissionDenied
                create_asset_transfer(actor=request.user, asset=asset, request_id=payload["request_id"],
                                      data=payload["data"], expected_custody=payload["custody_source"])
                return redirect("inventory:asset-transfer-list")
            except signing.BadSignature:
                form.add_error(None, "This preview expired or changed. Search and review the handoff again.")
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
        else:
            form.add_error(None, "Review the handoff before confirming it.")
    elif request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            source = resolve_employee_custodian(actor=request.user, user_id=data["employee_id"])
            payload = {"actor_id": request.user.pk, "asset_id": str(asset.public_id), "request_id": str(uuid4()),
                "custody_source": custody_source(asset),
                "data": {"destination_employee_id": data["employee_id"], "employee_source_checksum": source["sha256"],
                         "transfer_date": data["transfer_date"].isoformat(), "reference": data["reference"], "reason": data["reason"]}}
            confirmation = ConfirmEmployeeHandoffForm(initial={"handoff_token": signing.dumps(payload, salt=TOKEN_SALT)})
            preview = {"source": source["source"], "data": payload["data"]}
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(request, "inventory/employee_handoff.html", {
        "asset": asset, "query": query, "form": form, "employees": employees,
        "preview": preview, "confirmation": confirmation})
