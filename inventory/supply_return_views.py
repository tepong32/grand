from uuid import uuid4
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from .private_evidence import open_checked_private_evidence
from . import supply_returns as service
from .models import StockMovement
from .access import gso_department_for_user
from .supply_return_forms import ReturnForm, ReturnDecisionForm, ReturnVersionForm

SALT = "gso-supply-return-v1"


@never_cache
@login_required
@require_GET
def return_list(request):
    if not service.can_act(request.user, "view"):
        raise PermissionDenied
    query = request.GET.get("q", "").strip()[:120]
    rows = service.visible(request.user).select_related("issue__item")
    if query:
        rows = rows.filter(Q(reference__icontains=query) | Q(issue__item__name__icontains=query))
    return render(request, "inventory/supply_return_list.html", {"page": Paginator(rows, 25).get_page(request.GET.get("page")), "query": query})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def return_start(request, pk):
    if not service.can_act(request.user, "record"):
        raise PermissionDenied
    issue = get_object_or_404(StockMovement.objects.select_related("item"), pk=pk, kind="issue",
        item__department_id=gso_department_for_user(request.user).pk)
    basis = service.source_basis(issue)
    token = signing.dumps({"actor": request.user.pk, "issue": str(issue.public_id), "source": basis,
        "request_id": str(uuid4())}, salt=SALT)
    form = ReturnForm(request.POST if request.method == "POST" else None, request.FILES if request.method == "POST" else None,
        initial={"source_token": token}, issue=issue)
    if request.method == "POST" and form.is_valid():
        try:
            fields = dict(form.cleaned_data)
            payload = signing.loads(fields.pop("source_token"), salt=SALT, max_age=1800)
            if payload["actor"] != request.user.pk or payload["issue"] != str(issue.public_id):
                raise PermissionDenied
            case = service.record_return(actor=request.user, issue=issue, request_id=payload["request_id"],
                expected_source=payload["source"], **fields)
        except signing.BadSignature:
            form.add_error(None, "The source form expired or changed. Check existing returns, then reopen this issue.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory:supply-return-detail", pk=case.pk)
    return render(request, "inventory/supply_return_start.html", {"issue": issue, "form": form,
        "already_returned": service.returned_quantity(issue)})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def return_detail(request, pk):
    case = get_object_or_404(service.visible(request.user).select_related("issue__item", "source_allocation__lot", "movement"), pk=pk)
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    version = ReturnVersionForm(request.POST if request.method == "POST" else None)
    forms = {name: ReturnDecisionForm(request.POST if operation == name else None, prefix=name) for name in ("accept", "decline", "cancel")}
    review = service.can_act(request.user, "review", case.issue) and case.created_by_id != request.user.pk
    record = service.can_act(request.user, "record", case.issue)
    if request.method == "POST":
        if operation not in forms:
            version.add_error(None, "Choose a supported return action.")
        else:
            if not (record if operation == "cancel" else review):
                raise PermissionDenied
            form = forms[operation]
            if version.is_valid() and form.is_valid():
                try:
                    service.decide_return(actor=request.user, case=case, expected_version=version.cleaned_data["expected_version"],
                        action=operation, **form.cleaned_data)
                except ValidationError as error:
                    version.add_error(None, " ".join(error.messages))
                else:
                    return redirect("inventory:supply-return-detail", pk=case.pk)
    integrity_error = ""
    try:
        service.verify_history(case)
        service.verify_source(case)
    except ValidationError as error:
        integrity_error = " ".join(error.messages)
    cost = next((row["unit_cost"] for row in case.source_snapshot.get("allocations", []) if row["id"] == case.source_allocation_id), None)
    return render(request, "inventory/supply_return_detail.html", {"case": case, "version": version,
        "accept_form": forms["accept"], "decline_form": forms["decline"], "cancel_form": forms["cancel"],
        "can_review": review and case.status == "pending", "can_cancel": record and case.status == "pending",
        "integrity_error": integrity_error, "retained_cost": cost, "already_returned": service.returned_quantity(case.issue)})


@never_cache
@login_required
@require_GET
def return_evidence(request, pk):
    case = get_object_or_404(service.visible(request.user), pk=pk)
    try:
        service.verify_source(case)
        source = open_checked_private_evidence(case,
            namespace=f"inventory/supply-returns/{case.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("Return evidence is unavailable or needs integrity review.")
    response = FileResponse(source, as_attachment=True, filename=case.original_filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
