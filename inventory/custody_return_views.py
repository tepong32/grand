from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_GET

from .access import gso_department_for_user, in_gso_scope
from .custody_review import can_view_custody_review
from .custody_returns import (can_manage_return, record_return, attach_return_evidence,
    confirm_return, cancel_return, verify_return_evidence)
from .custody_return_forms import ReturnStartForm, ReturnEvidenceForm, ReturnDecisionForm, ReturnVersionForm
from .models import Asset, AssetTransfer, AssetReturnEvidence
from .private_evidence import open_checked_private_evidence
from .services import custody_source

TOKEN_SALT = "gso-witnessed-return-source-v1"


def scoped_returns(actor):
    if not can_view_custody_review(actor):
        raise PermissionDenied
    rows = AssetTransfer.objects.filter(kind=AssetTransfer.RETURN).select_related("asset", "requested_by", "acknowledged_by", "cancelled_by")
    if actor.is_superuser:
        return rows
    owner = gso_department_for_user(actor) if in_gso_scope(actor) else None
    return rows.filter(Q(source_custodian_user=actor) | Q(asset__department_id=owner.pk)) if owner else rows.filter(source_custodian_user=actor)


@never_cache
@login_required
@require_GET
def return_list(request):
    rows = scoped_returns(request.user)
    status = request.GET.get("status", "pending")
    if status in dict(AssetTransfer.STATUS_CHOICES):
        rows = rows.filter(status=status)
    else:
        status = "all"
    return render(request, "inventory/custody_return_list.html", {
        "page": Paginator(rows, 25).get_page(request.GET.get("page")), "status": status})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def return_start(request, pk):
    if not can_view_custody_review(request.user) or not can_manage_return(request.user, "record"):
        raise PermissionDenied
    rows = Asset.objects.all()
    if not request.user.is_superuser:
        rows = rows.filter(department_id=gso_department_for_user(request.user).pk)
    asset = get_object_or_404(rows, pk=pk)
    token = signing.dumps({"actor": request.user.pk, "asset": str(asset.public_id),
        "request_id": str(uuid4()), "source": custody_source(asset)}, salt=TOKEN_SALT)
    form = ReturnStartForm(request.POST if request.method == "POST" else None, initial={"source_token": token})
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            payload = signing.loads(data.pop("source_token"), salt=TOKEN_SALT, max_age=1800)
            if payload["actor"] != request.user.pk or payload["asset"] != str(asset.public_id):
                raise PermissionDenied
            transfer = record_return(actor=request.user, asset=asset, data=data, request_id=payload["request_id"],
                expected_custody=payload["source"])
        except signing.BadSignature:
            form.add_error(None, "This source review expired or changed. Reload the page to review current custody.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory:custody-return-detail", pk=transfer.pk)
    return render(request, "inventory/custody_return_start.html", {"asset": asset, "form": form})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def return_detail(request, pk):
    transfer = get_object_or_404(scoped_returns(request.user), pk=pk)
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    evidence = ReturnEvidenceForm(request.POST if operation == "evidence" else None,
        request.FILES if operation == "evidence" else None, prefix="evidence")
    confirmation = ReturnDecisionForm(request.POST if operation == "confirm" else None, prefix="confirm")
    cancellation = ReturnDecisionForm(request.POST if operation == "cancel" else None, prefix="cancel")
    version = ReturnVersionForm(request.POST if request.method == "POST" else None)
    record = can_manage_return(request.user, "record", transfer.asset) and request.user.pk != transfer.source_custodian_user_id
    verify = (can_manage_return(request.user, "verify", transfer.asset)
        and request.user.pk not in (transfer.source_custodian_user_id, transfer.requested_by_id)
        and not transfer.return_evidence.filter(uploaded_by=request.user).exists())
    if request.method == "POST":
        if (operation in ("evidence", "cancel") and not record) or (operation == "confirm" and not verify):
            raise PermissionDenied
        if version.is_valid():
            args = dict(actor=request.user, transfer=transfer, expected_version=version.cleaned_data["expected_version"])
            try:
                if operation == "evidence" and evidence.is_valid():
                    attach_return_evidence(**args, **evidence.cleaned_data)
                elif operation == "confirm" and confirmation.is_valid():
                    confirm_return(**args, **confirmation.cleaned_data)
                elif operation == "cancel" and cancellation.is_valid():
                    cancel_return(**args, **cancellation.cleaned_data)
                else:
                    raise ValidationError("Review the fields for the selected return action.")
            except ValidationError as error:
                version.add_error(None, " ".join(error.messages))
            else:
                return redirect("inventory:custody-return-detail", pk=transfer.pk)
    return render(request, "inventory/custody_return_detail.html", dict(transfer=transfer,
        evidence_form=evidence, confirm_form=confirmation, cancel_form=cancellation, version=version,
        can_record=record and transfer.status == AssetTransfer.PENDING,
        can_verify=verify and transfer.status == AssetTransfer.PENDING))


@never_cache
@login_required
@require_GET
def return_evidence(request, pk):
    evidence = get_object_or_404(AssetReturnEvidence, pk=pk, transfer__in=scoped_returns(request.user))
    try:
        verify_return_evidence(evidence.transfer)
        source = open_checked_private_evidence(evidence,
            namespace=f"inventory/custody_returns/{evidence.transfer.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("The retained evidence is unavailable or requires integrity review.")
    response = FileResponse(source, as_attachment=True, filename=evidence.original_filename,
                            content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
