from uuid import uuid4
from decimal import Decimal

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .models import ReceivingLine, ReceiptQuantityCorrection as Correction
from .receiving_views import scoped
from .receipt_correction_sources import lock_unused_source
from .receipt_quantity_corrections import (can_correct, source_basis, effective_quantities,
                                         record, decide, verify_history, verify_evidence)

SALT = "gso-receipt-quantity-correction-v1"


class CorrectionForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"),
        label="Overstated quantity to subtract", help_text="Subtract this from both delivered and accepted quantities.")
    reference = forms.CharField(max_length=180, label="Correcting source reference")
    reason = forms.CharField(max_length=4000, widget=forms.Textarea)
    upload = forms.FileField(label="Private correction packet")
    clerical_case = forms.BooleanField(label="The delivered and accepted quantities were entered too high before use. This is not a return or changed inspection decision.")


class DecisionForm(forms.Form):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=())
    note = forms.CharField(max_length=4000, widget=forms.Textarea, label="Decision basis")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def corrections(request, pk):
    line = get_object_or_404(ReceivingLine.objects.select_related("receipt"),
                            pk=pk, receipt__in=scoped(request.user))
    allowed = can_correct(request.user, "record", line.receipt)
    if request.method == "POST" and not allowed:
        raise PermissionDenied
    basis, quantities, error, form = None, None, "", None
    try:
        quantities = effective_quantities(line)
        if allowed:
            with transaction.atomic():
                fresh, _ = lock_unused_source(actor=request.user, line_id=line.pk)
                basis = source_basis(fresh)
    except ValidationError as exc:
        error = " ".join(exc.messages)
    if allowed and (basis is not None or request.method == "POST"):
        token = signing.dumps({"actor": request.user.pk, "line": line.pk, "basis": basis,
                               "request_id": str(uuid4())}, salt=SALT)
        form = CorrectionForm(request.POST if request.method == "POST" else None, request.FILES or None,
                              initial={"source_token": token})
        if request.method == "POST" and form.is_valid():
            try:
                data = dict(form.cleaned_data)
                payload = signing.loads(data.pop("source_token"), salt=SALT, max_age=1800)
                if payload.get("actor") != request.user.pk or payload.get("line") != line.pk:
                    raise PermissionDenied
                data.pop("clerical_case")
                row = record(actor=request.user, line_id=line.pk, request_id=payload["request_id"],
                             expected_basis=payload["basis"], **data)
            except signing.BadSignature:
                form.add_error(None, "This preview expired or changed. Reload the receipt and review it again.")
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                return redirect("inventory:receipt-quantity-detail", pk=row.pk)
    return render(request, "inventory/receipt_quantity_corrections.html", {"line": line,
        "quantities": quantities, "error": error, "form": form,
        "rows": line.quantity_corrections.select_related("recorded_by", "decided_by")})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def detail(request, pk):
    row = get_object_or_404(Correction.objects.select_related("line__receipt", "recorded_by", "decided_by"),
                           pk=pk, line__receipt__in=scoped(request.user))
    choices = []
    if row.status == row.PENDING:
        if row.recorded_by_id == request.user.pk and can_correct(request.user, "record", row.line.receipt):
            choices = [("cancel", "Cancel this proposal")]
        elif can_correct(request.user, "review", row.line.receipt):
            choices = [("approve", "Approve clerical overstatement correction"), ("reject", "Reject proposal")]
    form = DecisionForm(request.POST if request.method == "POST" else None,
                        initial={"expected_version": row.state_version}) if choices else None
    if form:
        form.fields["action"].choices = choices
    error = ""
    try:
        verify_history(row)
    except ValidationError as exc:
        error = " ".join(exc.messages)
    if request.method == "POST":
        if not form:
            raise PermissionDenied
        if form.is_valid():
            try:
                decide(actor=request.user, correction_id=row.pk, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                return redirect("inventory:receipt-quantity-detail", pk=row.pk)
    return render(request, "inventory/receipt_quantity_detail.html", {"row": row, "form": form, "error": error})


@never_cache
@login_required
@require_GET
def evidence(request, pk):
    row = get_object_or_404(Correction, pk=pk, line__receipt__in=scoped(request.user))
    try:
        verify_evidence(row)
        source = row.file.open("rb")
    except (ValidationError, OSError):
        raise Http404("The retained correction packet is unavailable or changed.")
    response = FileResponse(source, as_attachment=True, filename=row.original_filename,
                            content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
