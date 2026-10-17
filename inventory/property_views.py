from uuid import uuid4
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django import forms
from django.db.models import OuterRef, Subquery, Exists, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from . import property_determinations as service
from .property_card_views import can_prepare as can_prepare_source_card
from .access import can as can_asset, gso_department_for_user
from .models import Asset, PropertyDetermination
from .property_forms import PropertyForm, PropertyDecisionForm, PropertyVersionForm

SALT = "gso-property-determination-v1"


class PropertyRegisterFilter(forms.Form):
    q = forms.CharField(label="Asset name or tag contains", required=False, max_length=180)
    property_class = forms.CharField(label="Supplied class contains", required=False, max_length=160)
    fund = forms.CharField(label="Supplied fund label contains", required=False, max_length=160)
    treatment = forms.ChoiceField(required=False, choices=(("", "All treatments"),
        ("ppe", "PPE (as supplied)"), ("semi_expendable", "Semi-expendable (as supplied)"),
        ("missing", "No verified determination")))


@never_cache
@login_required
@require_GET
def property_register(request):
    if not service.can_act(request.user, "view"):
        raise PermissionDenied
    form = PropertyRegisterFilter(request.GET)
    latest = PropertyDetermination.objects.filter(asset_id=OuterRef("pk"), status="verified").order_by("-decided_at", "-pk")
    assets = Asset.objects.filter(department_id=gso_department_for_user(request.user).pk).annotate(
        determination_id=Subquery(latest.values("pk")[:1]),
        supplied_class=Subquery(latest.values("property_class")[:1]),
        supplied_fund=Subquery(latest.values("fund_label")[:1]),
        supplied_treatment=Subquery(latest.values("treatment")[:1]),
        pending_document=Exists(PropertyDetermination.objects.filter(asset_id=OuterRef("pk"), status="pending")))
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            assets = assets.filter(Q(asset_name__icontains=data["q"]) | Q(property_tag__icontains=data["q"]))
        if data["property_class"]:
            assets = assets.filter(supplied_class__icontains=data["property_class"])
        if data["fund"]:
            assets = assets.filter(supplied_fund__icontains=data["fund"])
        if data["treatment"] == "missing":
            assets = assets.filter(determination_id__isnull=True)
        elif data["treatment"]:
            assets = assets.filter(supplied_treatment=data["treatment"])
    else:
        assets = assets.none()
    page = Paginator(assets.order_by("asset_name", "pk"), 25).get_page(request.GET.get("page"))
    records = {row.pk: row for row in service.visible(request.user).filter(
        pk__in=[asset.determination_id for asset in page]).prefetch_related("events")}
    rows = []
    for asset in page:
        record = records.get(asset.determination_id)
        issues = []
        if asset.quantity != 1:
            issues.append("Grouped quantity needs reconciliation.")
        if not record:
            issues.append("No verified property determination.")
        else:
            try:
                service.verify_history(record)
                service.verify_source(record)
                if service.source_basis(asset) != record.source_snapshot:
                    issues.append("Asset or receipt facts changed; review the retained determination.")
            except ValidationError as error:
                issues.extend(error.messages)
            for field, label in (("property_class", "Property class"), ("fund_label", "Fund label"),
                    ("useful_life", "Useful life"), ("expires_on", "Expiry date"),
                    ("acquisition_date", "Documented acquisition date"),
                    ("acquisition_reference", "Acquisition source reference"),
                    ("receipt_item_number", "Receipt-item number")):
                if getattr(record, field) in (None, ""):
                    issues.append(f"{label} not supplied.")
        if asset.pending_document:
            issues.append("A supplied determination is awaiting review.")
        if not asset.property_tag:
            issues.append("Property tag not recorded.")
        if asset.purchase_date is None:
            issues.append("Asset register purchase date not recorded.")
        if asset.unit_cost is None:
            issues.append("Register unit cost unknown.")
        rows.append({"asset": asset, "record": record, "issues": issues})
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "inventory/property_register.html", {"form": form, "page": page,
        "rows": rows, "filter_query": query.urlencode(),
        "can_copy_to_draft": can_asset(request.user, "export"),
        "can_prepare_source_card": can_prepare_source_card(request.user)})


def display_value(model, name, raw):
    field = model._meta.get_field(name)
    return dict(field.flatchoices).get(raw, service.value(raw)) if field.choices else service.value(raw)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def property_records(request, pk):
    if not service.can_act(request.user, "view"):
        raise PermissionDenied
    asset = get_object_or_404(Asset, pk=pk, department_id=gso_department_for_user(request.user).pk)
    can_record = service.can_act(request.user, "record", asset)
    if request.method == "POST" and not can_record:
        raise PermissionDenied
    previous = service.latest_verified(asset)
    source_error = ""
    try:
        basis = service.source_basis(asset)
    except ValidationError as error:
        basis = None
        source_error = " ".join(error.messages)
    token = signing.dumps({"actor": request.user.pk, "asset": str(asset.public_id), "source": basis,
        "previous": str(previous.public_id) if previous else None, "request_id": str(uuid4())}, salt=SALT)
    form = PropertyForm(request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None, initial={"source_token": token})
    if request.method == "POST" and form.is_valid():
        try:
            fields = dict(form.cleaned_data)
            payload = signing.loads(fields.pop("source_token"), salt=SALT, max_age=1800)
            if payload["actor"] != request.user.pk or payload["asset"] != str(asset.public_id):
                raise PermissionDenied
            upload = fields.pop("upload")
            row = service.record(actor=request.user, asset=asset, request_id=payload["request_id"],
                expected_source=payload["source"], expected_predecessor=payload["previous"], data=fields, upload=upload)
        except signing.BadSignature:
            form.add_error(None, "The source form expired or changed. Check existing records, then reopen it.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory:property-detail", pk=row.pk)
    rows = service.visible(request.user).filter(asset=asset)
    return render(request, "inventory/property_records.html", {"asset": asset, "form": form,
        "page": Paginator(rows, 25).get_page(request.GET.get("page")), "previous": previous,
        "can_record": can_record, "source_error": source_error,
        "pending": rows.filter(status="pending").exists()})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def property_detail(request, pk):
    row = get_object_or_404(service.visible(request.user).select_related("asset", "predecessor"), pk=pk)
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    version = PropertyVersionForm(request.POST if request.method == "POST" else None)
    forms = {name: PropertyDecisionForm(request.POST if operation == name else None, prefix=name) for name in ("verify", "reject", "cancel")}
    review = service.can_act(request.user, "review", row.asset) and row.recorded_by_id != request.user.pk
    record = service.can_act(request.user, "record", row.asset)
    if request.method == "POST":
        if operation not in forms:
            version.add_error(None, "Choose a supported property action.")
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
                    return redirect("inventory:property-detail", pk=row.pk)
    integrity_error = ""
    try:
        service.verify_history(row)
        service.verify_source(row)
        stale = service.source_basis(row.asset) != row.source_snapshot
    except ValidationError as error:
        integrity_error, stale = " ".join(error.messages), True
    latest = service.latest_verified(row.asset)
    can_request_finance = False
    if apps.is_installed("inventory_finance"):
        from inventory_finance.property_links import gso_allowed
        can_request_finance = gso_allowed(request.user, row, "request")
    return render(request, "inventory/property_detail.html", {"record": row, "version": version,
        "can_request_finance": can_request_finance,
        "verify_form": forms["verify"], "reject_form": forms["reject"], "cancel_form": forms["cancel"],
        "can_review": review and row.status == "pending", "can_cancel": record and row.status == "pending",
        "integrity_error": integrity_error, "stale": stale, "latest": latest,
        "basis_facts": [(Asset._meta.get_field(name).verbose_name, display_value(Asset, name, row.source_snapshot.get("facts", {}).get(name))) for name in service.ASSET_FIELDS],
        "facts": [(PropertyForm.Meta.labels.get(name, row._meta.get_field(name).verbose_name), display_value(type(row), name, getattr(row, name))) for name in service.CONTENT_FIELDS]})


@never_cache
@login_required
@require_GET
def property_evidence(request, pk):
    from .private_evidence import open_checked_private_evidence
    row = get_object_or_404(service.visible(request.user), pk=pk)
    try:
        service.verify_source(row)
        source = open_checked_private_evidence(row, namespace=f"inventory/property-determinations/{row.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("Property evidence is unavailable or needs integrity review.")
    response = FileResponse(source, as_attachment=True, filename=row.original_filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
