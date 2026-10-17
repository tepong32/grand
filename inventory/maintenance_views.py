from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import in_gso_scope, gso_department_for_user, has_inventory_permission
from .models import Asset, AssetMaintenanceCase, AssetMaintenanceEvidence
from .maintenance import (can_manage_maintenance, open_maintenance, update_maintenance,
                          attach_maintenance_evidence, close_maintenance)
from .maintenance_forms import (MaintenanceOpenForm, MaintenanceWorkForm, MaintenanceCloseForm,
                                MaintenanceEvidenceForm, MaintenanceVersionForm)


def can_view_maintenance(actor):
    return bool(in_gso_scope(actor) and (has_inventory_permission(actor, "view_assetmaintenancecase") or
                                        can_manage_maintenance(actor)))


def scoped_assets(actor):
    if not can_view_maintenance(actor):
        raise PermissionDenied
    rows = Asset.objects.all()
    if actor.is_superuser:
        return rows
    department = gso_department_for_user(actor)
    return rows.filter(department_id=department.pk) if department else rows.none()


@never_cache
@login_required
@require_http_methods(["GET"])
def maintenance_list(request):
    rows = AssetMaintenanceCase.objects.filter(asset__in=scoped_assets(request.user)).select_related("asset")
    status = request.GET.get("status", "open")
    if status in dict(AssetMaintenanceCase.STATUS_CHOICES):
        rows = rows.filter(status=status)
    else:
        status = "all"
    return render(request, "inventory/maintenance_list.html", {
        "page": Paginator(rows, 25).get_page(request.GET.get("page")), "status": status})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def maintenance_open(request, pk):
    asset = get_object_or_404(scoped_assets(request.user), pk=pk)
    if not can_manage_maintenance(request.user, asset):
        raise PermissionDenied
    form = MaintenanceOpenForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            case = open_maintenance(actor=request.user, asset=asset, data=form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory:maintenance-detail", pk=case.pk)
    return render(request, "inventory/maintenance_open.html", {"form": form, "asset": asset})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def maintenance_detail(request, pk):
    case = get_object_or_404(AssetMaintenanceCase.objects.select_related("asset"), pk=pk,
                             asset__in=scoped_assets(request.user))
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    work = MaintenanceWorkForm(request.POST if operation == "work" else None,
        initial={name: getattr(case, name) for name in MaintenanceWorkForm.base_fields}, prefix="work")
    evidence = MaintenanceEvidenceForm(request.POST if operation == "evidence" else None,
        request.FILES if operation == "evidence" else None, prefix="evidence")
    close = MaintenanceCloseForm(request.POST if operation == "close" else None, prefix="close")
    version = MaintenanceVersionForm(request.POST if request.method == "POST" else None,
                                      initial={"expected_version": case.state_version})
    editable = can_manage_maintenance(request.user, case.asset) and case.status == case.OPEN
    if request.method == "POST":
        if not can_manage_maintenance(request.user, case.asset):
            raise PermissionDenied
        if version.is_valid():
            args = dict(actor=request.user, case=case, expected_version=version.cleaned_data["expected_version"])
            try:
                if operation == "work" and work.is_valid():
                    update_maintenance(**args, data=work.cleaned_data)
                elif operation == "evidence" and evidence.is_valid():
                    attach_maintenance_evidence(**args, **evidence.cleaned_data)
                elif operation == "close" and close.is_valid():
                    close_maintenance(**args, **close.cleaned_data)
                else:
                    raise ValidationError("Review the fields for the selected action.")
            except ValidationError as error:
                version.add_error(None, " ".join(error.messages))
            else:
                return redirect("inventory:maintenance-detail", pk=case.pk)
    return render(request, "inventory/maintenance_detail.html", dict(
        case=case, work_form=work, evidence_form=evidence, close_form=close, version=version, editable=editable))


@never_cache
@login_required
@require_http_methods(["GET"])
def maintenance_evidence(request, pk):
    evidence = get_object_or_404(AssetMaintenanceEvidence, pk=pk,
                                 case__asset__in=scoped_assets(request.user))
    from .private_evidence import open_checked_private_evidence
    try:
        source = open_checked_private_evidence(evidence,
            namespace=f"inventory/maintenance/{evidence.case.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("The retained document is unavailable.")
    response = FileResponse(source, as_attachment=True, filename=evidence.original_filename,
                            content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
