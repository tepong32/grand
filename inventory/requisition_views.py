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
from . import requisitions as service
from .requisition_forms import RequisitionForm, RequisitionLines, DecisionForm, FulfillmentForm, VersionForm

SALT = "gso-supplied-requisition-v1"


@never_cache
@login_required
@require_GET
def request_list(request):
    if not service.can_act(request.user, "view"):
        raise PermissionDenied
    rows = service.visible(request.user)
    query = request.GET.get("q", "").strip()[:120]
    if query:
        rows = rows.filter(Q(reference__icontains=query) | Q(requesting_department_label__icontains=query))
    return render(request, "inventory/requisition_list.html", {"page": Paginator(rows, 25).get_page(request.GET.get("page")),
        "query": query, "can_record": service.can_act(request.user, "record")})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def request_create(request):
    if not service.can_act(request.user, "record"):
        raise PermissionDenied
    data = request.POST if request.method == "POST" else None
    token = signing.dumps({"actor": request.user.pk, "request_id": str(uuid4())}, salt=SALT)
    form = RequisitionForm(data, request.FILES if data is not None else None, initial={"request_token": token})
    lines = RequisitionLines(data, prefix="lines", form_kwargs={"actor": request.user})
    if request.method == "POST" and form.is_valid() and lines.is_valid():
        try:
            fields = dict(form.cleaned_data)
            payload = signing.loads(fields.pop("request_token"), salt=SALT, max_age=1800)
            if payload["actor"] != request.user.pk:
                raise PermissionDenied
            record = service.create_request(actor=request.user, request_id=payload["request_id"],
                lines=[row for row in lines.cleaned_data if row], **fields)
        except signing.BadSignature:
            form.add_error(None, "This form expired or changed. Check existing requisitions before reopening it.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory:requisition-detail", pk=record.pk)
    return render(request, "inventory/requisition_create.html", {"form": form, "lines": lines})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def request_detail(request, pk):
    record = get_object_or_404(service.visible(request.user), pk=pk)
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    version = VersionForm(request.POST if request.method == "POST" else None)
    approve = DecisionForm(request.POST if operation == "approve" else None, prefix="approve")
    close = DecisionForm(request.POST if operation == "close" else None, prefix="close")
    issue = FulfillmentForm(request.POST if operation == "issue" else None, prefix="issue", request=record)
    can_review = service.can_act(request.user, "review", record) and request.user.pk != record.created_by_id
    if request.method == "POST":
        if operation not in ("approve", "close", "issue"):
            version.add_error(None, "Choose a supported requisition action.")
        else:
            action = {"approve": "review", "close": "record", "issue": "issue"}[operation]
            if not service.can_act(request.user, action, record) or (operation == "approve" and not can_review):
                raise PermissionDenied
            target = {"approve": approve, "close": close, "issue": issue}[operation]
            if version.is_valid() and target.is_valid():
                try:
                    args = dict(actor=request.user, request=record, expected_version=version.cleaned_data["expected_version"])
                    if operation == "issue":
                        service.fulfill(**args, **issue.cleaned_data)
                    else:
                        service.decide_request(**args, action=operation, **target.cleaned_data)
                except ValidationError as error:
                    version.add_error(None, " ".join(error.messages))
                else:
                    return redirect("inventory:requisition-detail", pk=record.pk)
    rows = list(record.lines.select_related("item"))
    for line in rows:
        line.issued_quantity = service.issued(line)
        line.remaining_quantity = line.quantity - line.issued_quantity
    integrity_error = ""
    try:
        service.verify_history(record)
        service.verify_source(record)
    except ValidationError as error:
        integrity_error = " ".join(error.messages)
    return render(request, "inventory/requisition_detail.html", {"record": record, "lines": rows,
        "version": version, "approve_form": approve, "close_form": close, "issue_form": issue,
        "integrity_error": integrity_error,
        "can_review": can_review and record.status == "pending",
        "can_close": service.can_act(request.user, "record", record) and record.status in ("pending", "approved"),
        "can_issue": service.can_act(request.user, "issue", record) and record.status == "approved"})


@never_cache
@login_required
@require_GET
def request_evidence(request, pk):
    record = get_object_or_404(service.visible(request.user), pk=pk)
    try:
        source = service.verify_source(record).open("rb")
    except (OSError, ValidationError):
        raise Http404("The supplied document is unavailable or needs integrity review.")
    response = FileResponse(source, as_attachment=True, filename=record.original_filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
