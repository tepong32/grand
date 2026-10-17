from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from . import property_movements as service, property_determinations as properties
from .access import gso_department_for_user
from .models import Asset
from .property_forms import PropertyDecisionForm, PropertyVersionForm
from .property_movement_forms import MovementSourceForm, MovementForm, MovementCutoffForm

SALT = "gso-property-movement-v1"


def scoped_asset(actor, pk, action="view"):
    if not service.can_act(actor, action):
        raise PermissionDenied
    return get_object_or_404(Asset, pk=pk, department_id=gso_department_for_user(actor).pk)


@never_cache
@login_required
@require_GET
def movement_list(request, pk):
    asset = scoped_asset(request.user, pk)
    form = MovementCutoffForm(request.GET if "cutoff" in request.GET else {"cutoff": timezone.localdate()})
    projection = None
    if form.is_valid():
        try:
            projection = service.project(actor=request.user, asset=asset, cutoff=form.cleaned_data["cutoff"])
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    rows = service.visible(request.user).filter(asset=asset).select_related("recorded_by").order_by("-recorded_at", "-pk")
    return render(request, "inventory/property_movement_list.html", dict(asset=asset, form=form,
        projection=projection, page=Paginator(rows, 25).get_page(request.GET.get("page")),
        can_record=service.can_act(request.user, "record", asset)))


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def movement_new(request, pk):
    asset = scoped_asset(request.user, pk, "record")
    selected = request.POST if request.method == "POST" else request.GET
    latest = properties.latest_verified(asset)
    if request.method == "GET" and not selected:
        selected = {"source": "opening", "determination": latest.pk if latest else ""}
    selection = MovementSourceForm(selected, asset=asset)
    form, basis, previous, source_error = None, None, None, ""
    if selection.is_valid():
        kind, source_id = selection.source_identity()
        determination = selection.cleaned_data["determination"]
        try:
            key, basis, _ = service.source_basis(asset=asset, determination_id=determination.pk,
                source_kind=kind, source_id=source_id)
            previous = service.latest_verified(asset, key)
        except ValidationError as error:
            source_error = " ".join(error.messages)
        token = signing.dumps(dict(actor=request.user.pk, asset=str(asset.public_id),
            determination=determination.pk, source=selection.cleaned_data["source"], basis=basis,
            previous=str(previous.public_id) if previous else None, request_id=str(uuid4())), salt=SALT)
        initial = {name: getattr(previous, name) for name in service.CONTENT_FIELDS} if previous else {}
        initial["source_token"] = token
        form = MovementForm(request.POST if request.method == "POST" else None,
            request.FILES if request.method == "POST" else None, source_kind=kind,
            source_date=service.physical_date(kind, basis) if basis and kind != "opening" else None,
            initial=initial)
        if request.method == "POST" and not source_error and form.is_valid():
            try:
                content = dict(form.cleaned_data)
                payload = signing.loads(content.pop("source_token"), salt=SALT, max_age=1800)
                if (payload["actor"] != request.user.pk or payload["asset"] != str(asset.public_id)
                        or payload["determination"] != determination.pk
                        or payload["source"] != selection.cleaned_data["source"]):
                    raise PermissionDenied
                upload = content.pop("upload")
                row = service.record(actor=request.user, asset=asset, determination_id=determination.pk,
                    source_kind=kind, source_id=source_id, request_id=payload["request_id"],
                    expected_source=payload["basis"], expected_predecessor=payload["previous"],
                    data=content, upload=upload)
            except signing.BadSignature:
                form.add_error(None, "The source form expired or changed. Check existing entries, then reopen it.")
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
            else:
                return redirect("inventory:property-movement-detail", pk=row.pk)
    return render(request, "inventory/property_movement_form.html", dict(asset=asset, selection=selection,
        form=form, source_error=source_error, previous=previous,
        can_property_view=properties.can_act(request.user, "view", asset)))


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def movement_detail(request, pk):
    row = get_object_or_404(service.visible(request.user).select_related("asset", "predecessor", "determination"), pk=pk)
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    version = PropertyVersionForm(request.POST if request.method == "POST" else None)
    forms = {name: PropertyDecisionForm(request.POST if operation == name else None, prefix=name)
             for name in ("verify", "reject", "cancel")}
    review = service.can_act(request.user, "review", row.asset) and row.recorded_by_id != request.user.pk
    record = service.can_act(request.user, "record", row.asset)
    if request.method == "POST":
        if operation not in forms:
            version.add_error(None, "Choose a supported movement action.")
        else:
            if not (record if operation == "cancel" else review):
                raise PermissionDenied
            if version.is_valid() and forms[operation].is_valid():
                try:
                    service.decide(actor=request.user, row=row, expected_version=version.cleaned_data["expected_version"],
                        action=operation, **forms[operation].cleaned_data)
                except ValidationError as error:
                    version.add_error(None, " ".join(error.messages))
                else:
                    return redirect("inventory:property-movement-detail", pk=row.pk)
    integrity_error = ""
    try:
        service.verify_history(row)
        service.verify_evidence(row)
        key, basis, _ = service.source_basis(asset=row.asset, determination_id=row.determination_id,
            source_kind=row.source_kind, source_id=service.source_id(row))
        if key != row.source_key or basis != row.source_snapshot:
            integrity_error = "The physical source or property basis changed. Reconcile before using this entry."
    except ValidationError as error:
        integrity_error = " ".join(error.messages)
    return render(request, "inventory/property_movement_detail.html", dict(record=row, version=version,
        verify_form=forms["verify"], reject_form=forms["reject"], cancel_form=forms["cancel"],
        can_review=review and row.status == "pending", can_cancel=record and row.status == "pending",
        can_record=record, can_property_view=properties.can_act(request.user, "view", row.asset),
        integrity_error=integrity_error, latest=service.latest_verified(row.asset, row.source_key),
        selection_source="opening" if row.source_kind == "opening" else f"{row.source_kind}:{service.source_id(row)}"))


@never_cache
@login_required
@require_GET
def movement_evidence(request, pk):
    from .private_evidence import open_checked_private_evidence
    row = get_object_or_404(service.visible(request.user), pk=pk)
    try:
        service.verify_evidence(row)
        source = open_checked_private_evidence(row, namespace=f"inventory/property-movements/{row.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("Movement evidence is unavailable or needs integrity review.")
    response = FileResponse(source, as_attachment=True, filename=row.original_filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
