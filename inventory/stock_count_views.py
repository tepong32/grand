from decimal import Decimal
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
from django.utils import timezone
from urllib.parse import urlencode

from .access import can_stock, gso_department_for_user, in_gso_scope
from .models import ConsumableItem, StockCount, StockCountEvidence
from .private_evidence import open_checked_private_evidence
from .stock_count_forms import StockCountForm, StockCountEvidenceForm, StockCountDecisionForm, StockCountVersionForm
from .stock_counts import can_manage_count, stock_basis, record_count, attach_count_evidence, decide_count, verify_count_evidence

TOKEN_SALT = "gso-physical-stock-count-v1"


def scoped_items(actor):
    if not in_gso_scope(actor) or not can_stock(actor, "view"):
        raise PermissionDenied
    rows = ConsumableItem.objects.all()
    return rows if actor.is_superuser else rows.filter(department_id=gso_department_for_user(actor).pk)


def scoped_counts(actor):
    return StockCount.objects.filter(item__in=scoped_items(actor)).select_related("item", "recorded_by", "decided_by", "adjustment")


def _count_selection(request):
    rows = scoped_counts(request.user)
    query = request.GET.get("q", "").strip()[:100]
    if query:
        rows = rows.filter(Q(reference__icontains=query) | Q(item__name__icontains=query))
    status = request.GET.get("status", "pending")
    if status in ("pending", "approved", "cancelled"):
        rows = rows.filter(status=status)
    elif status != "all":
        raise ValidationError("Choose Pending, Reviewed, Cancelled or All counts before opening a copy.")
    return rows, {"status": status, "query": query, "query_string": urlencode({"status": status, "q": query})}


@never_cache
@login_required
@require_GET
def count_list(request):
    try:
        rows, context = _count_selection(request)
    except ValidationError as error:
        return render(request, "inventory/stock_count_list.html", {"selection_error": " ".join(error.messages)}, status=400)
    return render(request, "inventory/stock_count_list.html", {**context,
        "page": Paginator(rows, 25).get_page(request.GET.get("page")), "can_export": can_stock(request.user, "export")})


@never_cache
@login_required
@require_GET
def count_working_copy(request):
    if not can_stock(request.user, "export"):
        raise PermissionDenied
    try:
        rows, context = _count_selection(request)
    except ValidationError as error:
        return render(request, "inventory/stock_count_list.html", {"selection_error": " ".join(error.messages)}, status=400)
    counts = list(rows)
    for count in counts:
        count.difference = count.quantity - Decimal(count.basis["balance"])
    return render(request, "inventory/stock_count_working_copy.html", {**context, "counts": counts,
        "status_label": {"pending": "Pending", "approved": "Reviewed", "cancelled": "Cancelled", "all": "All counts"}[context["status"]],
        "generated_at": timezone.now()})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def count_start(request, pk):
    item = get_object_or_404(scoped_items(request.user), pk=pk)
    if not can_manage_count(request.user, "record", item):
        raise PermissionDenied
    basis = stock_basis(item)
    token = signing.dumps({"actor": request.user.pk, "item": str(item.public_id), "basis": basis,
        "request_id": str(uuid4())}, salt=TOKEN_SALT)
    form = StockCountForm(request.POST if request.method == "POST" else None, initial={"source_token": token})
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            payload = signing.loads(data.pop("source_token"), salt=TOKEN_SALT, max_age=1800)
            if payload["actor"] != request.user.pk or payload["item"] != str(item.public_id):
                raise PermissionDenied
            count = record_count(actor=request.user, item=item, request_id=payload["request_id"],
                expected_basis=payload["basis"], **data)
        except signing.BadSignature:
            form.add_error(None, "The count basis expired or changed. Reload and recount against the current ledger.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory:stock-count-detail", pk=count.pk)
    return render(request, "inventory/stock_count_start.html", {"item": item, "basis": basis, "form": form})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def count_detail(request, pk):
    count = get_object_or_404(scoped_counts(request.user), pk=pk)
    operation = request.POST.get("operation", "") if request.method == "POST" else ""
    evidence = StockCountEvidenceForm(request.POST if operation == "evidence" else None,
        request.FILES if operation == "evidence" else None, prefix="evidence")
    approval = StockCountDecisionForm(request.POST if operation == "approve" else None, prefix="approve")
    cancellation = StockCountDecisionForm(request.POST if operation == "cancel" else None, prefix="cancel")
    version = StockCountVersionForm(request.POST if request.method == "POST" else None)
    record = can_manage_count(request.user, "record", count.item)
    review_grant = can_manage_count(request.user, "review", count.item)
    cancel = record or review_grant
    review = (review_grant and request.user.pk != count.recorded_by_id
              and not count.evidence.filter(uploaded_by=request.user).exists())
    if request.method == "POST":
        if ((operation == "evidence" and not record) or (operation == "cancel" and not cancel)
            or (operation == "approve" and not review)):
            raise PermissionDenied
        if version.is_valid():
            args = dict(actor=request.user, count=count, expected_version=version.cleaned_data["expected_version"])
            try:
                if operation == "evidence" and evidence.is_valid():
                    attach_count_evidence(**args, **evidence.cleaned_data)
                elif operation == "approve" and approval.is_valid():
                    decide_count(**args, action="approve", **approval.cleaned_data)
                elif operation == "cancel" and cancellation.is_valid():
                    decide_count(**args, action="cancel", **cancellation.cleaned_data)
                else:
                    raise ValidationError("Review the fields for the selected count action.")
            except ValidationError as error:
                version.add_error(None, " ".join(error.messages))
            else:
                return redirect("inventory:stock-count-detail", pk=count.pk)
    return render(request, "inventory/stock_count_detail.html", dict(count=count, evidence_form=evidence,
        approve_form=approval, cancel_form=cancellation, version=version,
        difference=count.quantity-Decimal(count.basis["balance"]), basis_changed=stock_basis(count.item) != count.basis,
        can_record=record and count.status == StockCount.PENDING, can_review=review and count.status == StockCount.PENDING,
        can_cancel=cancel and count.status == StockCount.PENDING))


@never_cache
@login_required
@require_GET
def count_evidence(request, pk):
    evidence = get_object_or_404(StockCountEvidence, pk=pk, count__in=scoped_counts(request.user))
    try:
        verify_count_evidence(evidence.count)
        source = open_checked_private_evidence(evidence,
            namespace=f"inventory/stock_counts/{evidence.count.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("The count evidence is unavailable or needs integrity review.")
    response = FileResponse(source, as_attachment=True, filename=evidence.original_filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
