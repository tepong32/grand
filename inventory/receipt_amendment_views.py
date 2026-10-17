from uuid import uuid4
from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_GET

from .models import ReceivingLine, ReceiptCostAmendment
from .receiving_views import scoped
from .receipt_amendments import (can_amend, amendment_basis, record_amendment,
    decide_amendment, effective_cost, verify_amendment_evidence)

SALT = "gso-receipt-cost-amendment-v1"


class AmendmentForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    unit_cost = forms.DecimalField(max_digits=13, decimal_places=2, min_value=0, required=False,
        label="Corrected documented unit cost", help_text="Leave blank only when the source establishes that cost is unknown. Zero means a documented zero.")
    reference = forms.CharField(max_length=180, label="Correcting source reference")
    reason = forms.CharField(max_length=4000, widget=forms.Textarea)
    upload = forms.FileField(label="Private correcting document")


class DecisionForm(forms.Form):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=(("approve", "Approve documentary correction"), ("reject", "Reject")))
    note = forms.CharField(max_length=4000, widget=forms.Textarea, label="Independent review basis")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def amendments(request, pk):
    line = get_object_or_404(ReceivingLine.objects.select_related("receipt"), pk=pk, receipt__in=scoped(request.user))
    can_record = can_amend(request.user, "record", line.receipt)
    if request.method == "POST" and not can_record:
        raise PermissionDenied
    basis, error = None, ""
    try:
        basis = amendment_basis(line)
    except ValidationError as exc:
        error = " ".join(exc.messages)
    form = None
    if can_record and basis and line.receipt.status == line.receipt.ACCEPTED and not line.is_void and line.accepted_quantity > 0:
        token = signing.dumps({"actor": request.user.pk, "line": line.pk, "basis": basis, "request_id": str(uuid4())}, salt=SALT)
        form = AmendmentForm(request.POST if request.method == "POST" else None, request.FILES or None,
                             initial={"source_token": token})
        if request.method == "POST" and form.is_valid():
            try:
                data = dict(form.cleaned_data)
                payload = signing.loads(data.pop("source_token"), salt=SALT, max_age=1800)
                if payload.get("actor") != request.user.pk or payload.get("line") != line.pk:
                    raise PermissionDenied
                row = record_amendment(actor=request.user, line=line, request_id=payload["request_id"],
                    expected_basis=payload["basis"], **data)
            except signing.BadSignature:
                form.add_error(None, "This receipt preview expired or changed. Reload and review the current facts.")
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                return redirect("inventory:receipt-amendment-detail", pk=row.pk)
    return render(request, "inventory/receipt_amendments.html", {"line": line, "basis": basis,
        "form": form, "error": error, "rows": line.cost_amendments.select_related("recorded_by", "reviewed_by")})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def amendment_detail(request, pk):
    row = get_object_or_404(ReceiptCostAmendment.objects.select_related("line__receipt", "recorded_by", "reviewed_by"),
        pk=pk, line__receipt__in=scoped(request.user))
    reviewer = can_amend(request.user, "review", row.line.receipt) and row.recorded_by_id != request.user.pk
    if request.method == "POST" and not reviewer:
        raise PermissionDenied
    form = DecisionForm(request.POST if request.method == "POST" else None, initial={"expected_version": row.state_version}) if reviewer and row.status == row.PENDING else None
    if request.method == "POST":
        if not form:
            raise PermissionDenied
        if form.is_valid():
            try:
                decide_amendment(actor=request.user, amendment=row, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                return redirect("inventory:receipt-amendment-detail", pk=row.pk)
    return render(request, "inventory/receipt_amendment_detail.html", {"row": row, "form": form})


@never_cache
@login_required
@require_GET
def amendment_evidence(request, pk):
    row = get_object_or_404(ReceiptCostAmendment, pk=pk, line__receipt__in=scoped(request.user))
    try:
        verify_amendment_evidence(row)
        source = row.file.open("rb")
    except (ValidationError, OSError):
        raise Http404("The retained document is unavailable or changed; investigate the evidence store.")
    response = FileResponse(source, as_attachment=True, filename=row.original_filename, content_type="application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response
