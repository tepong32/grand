from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .access import department_for_user, has_explicit_permission, voucher_access_required
from .forms import (
    RemittanceBatchForm, RemittanceLineForm, RemittanceLineRevisionForm,
    RemittanceReleaseForm, RemittanceReviewForm, TaxFilingAmendmentForm,
    TaxFilingEvidenceForm, TaxFilingEvidenceReviewForm,
)
from .models import TaxFilingEvidence, TreasuryRemittanceBatch, TreasuryRemittanceLine
from .remittance_register import (
    remittance_action_choices_for_user, remittance_action_queryset,
    visible_remittance_batches,
)
from .remittances import (
    add_line, create_batch, export_batch_csv, release_batch, review_batch,
    revise_line, submit_batch, withholding_availability,
)
from .tax_filings import (
    create_amendment, export_evidence_csv, review_evidence, save_draft, submit_evidence, tax_scope,
)


def _can_view(user):
    return any(has_explicit_permission(user, permission) for permission in (
        "vouchers.view_remittance_workbench", "vouchers.prepare_remittances",
        "vouchers.approve_remittances", "vouchers.release_remittances",
        "vouchers.view_remittance_audit",
    ))


def _batch(public_id, user):
    return get_object_or_404(visible_remittance_batches(
        user, TreasuryRemittanceBatch.objects.select_related(
        "configuration_release", "transaction_variant", "recipient_party", "treasury_department",
        "created_by", "submitted_by", "reviewed_by", "released_by", "posting_rule",
        )
    ), public_id=public_id)


def _message_error(request, exc):
    messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))


def _require_treasury_action(user, batch):
    if batch.treasury_department != department_for_user(user):
        raise PermissionDenied


def _evidence(public_id, evidence_id, user):
    batch = _batch(public_id, user)
    return get_object_or_404(
        TaxFilingEvidence.objects.select_related("batch", "created_by", "submitted_by", "reviewed_by"),
        public_id=evidence_id, batch=batch,
    )


@require_GET
@voucher_access_required
def workspace(request):
    if not _can_view(request.user):
        raise PermissionDenied
    batches = visible_remittance_batches(
        request.user,
        TreasuryRemittanceBatch.objects.select_related("recipient_party", "treasury_department"),
    )
    attention = request.GET.get("attention", "")
    work_items, selected_attention, work_spec = remittance_action_queryset(
        request.user, attention, queryset=batches,
    )
    selected = request.GET.get("status", "")
    if selected_attention:
        batches = work_items
        selected = ""
    elif selected in dict(TreasuryRemittanceBatch.STATUS_CHOICES):
        batches = batches.filter(status=selected)
    else:
        selected = ""
    return render(request, "vouchers/remittances/workspace.html", {
        "batches": batches[:100], "status_choices": TreasuryRemittanceBatch.STATUS_CHOICES,
        "selected_status": selected,
        "selected_attention": selected_attention,
        "work_spec": work_spec,
        "attention_choices": remittance_action_choices_for_user(request.user),
        "can_prepare": has_explicit_permission(request.user, "vouchers.prepare_remittances"),
        "can_approve": has_explicit_permission(request.user, "vouchers.approve_remittances"),
        "can_release": has_explicit_permission(request.user, "vouchers.release_remittances"),
    })


@require_http_methods(["GET", "POST"])
@voucher_access_required
def create(request):
    if not has_explicit_permission(request.user, "vouchers.prepare_remittances"):
        raise PermissionDenied
    form = RemittanceBatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            batch = create_batch(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, f"Remittance {batch.reference_code} created. Add posted withholding balances next.")
            return redirect(batch)
    return render(request, "vouchers/remittances/form.html", {"form": form, "title": "Prepare deduction / withholding remittance", "cancel_url": "vouchers:remittance_workspace"})


@require_GET
@voucher_access_required
def detail(request, public_id):
    if not _can_view(request.user):
        raise PermissionDenied
    batch = _batch(public_id, request.user)
    active_lines = batch.lines.filter(status=TreasuryRemittanceLine.ACTIVE)
    available = withholding_availability(finance_department_id=batch.finance_department_id, transaction_type=batch.transaction_variant.code, as_of_date=batch.remittance_date)
    can_audit = has_explicit_permission(request.user, "vouchers.view_remittance_audit")
    filing_history = batch.tax_filing_evidence.select_related("created_by", "reviewed_by").order_by("-version")
    current_filing = filing_history.exclude(status=TaxFilingEvidence.SUPERSEDED).first()
    try:
        tax_scope(batch)
    except ValidationError:
        tax_filing_eligible = False
    else:
        tax_filing_eligible = True
    return render(request, "vouchers/remittances/detail.html", {
        "batch": batch, "active_lines": active_lines,
        "line_history": batch.lines.exclude(status=TreasuryRemittanceLine.ACTIVE),
        "events": batch.events.select_related("actor", "actor_department")[:50] if can_audit else (),
        "posting_requests": batch.posting_requests.order_by("-version"),
        "available_count": len([row for row in available if row["fund_code"] == batch.fund_code]),
        "line_form": RemittanceLineForm(batch=batch),
        "review_form": RemittanceReviewForm(), "release_form": RemittanceReleaseForm(),
        "can_prepare": (
            has_explicit_permission(request.user, "vouchers.prepare_remittances")
            and batch.treasury_department == department_for_user(request.user)
        ),
        "can_approve": (
            has_explicit_permission(request.user, "vouchers.approve_remittances")
            and request.user.pk not in (batch.created_by_id, batch.submitted_by_id)
        ),
        "can_release": (
            has_explicit_permission(request.user, "vouchers.release_remittances")
            and batch.treasury_department == department_for_user(request.user)
        ),
        "can_audit": can_audit,
        "filing_history": filing_history, "current_filing": current_filing,
        "tax_filing_eligible": tax_filing_eligible,
        "filing_review_form": TaxFilingEvidenceReviewForm(),
        "filing_amendment_form": TaxFilingAmendmentForm(),
    })


@require_POST
@voucher_access_required
def add_allocation(request, public_id):
    batch = _batch(public_id, request.user)
    form = RemittanceLineForm(request.POST, batch=batch)
    if form.is_valid():
        try:
            add_line(batch=batch, actor=request.user, choice_key=form.cleaned_data["balance"], amount=form.cleaned_data["amount"], reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            _message_error(request, exc)
        else:
            messages.success(request, "Posted withholding balance added to the remittance schedule.")
    else:
        _message_error(request, ValidationError(" ".join(sum(form.errors.values(), []))))
    return redirect(batch)


@require_http_methods(["GET", "POST"])
@voucher_access_required
def revise_allocation(request, public_id, pk):
    batch = _batch(public_id, request.user)
    line = get_object_or_404(TreasuryRemittanceLine, pk=pk, batch=batch, status=TreasuryRemittanceLine.ACTIVE)
    form = RemittanceLineRevisionForm(request.POST or None, line=line)
    if request.method == "POST" and form.is_valid():
        try:
            revise_line(line=line, actor=request.user, amount=form.cleaned_data["revised_amount"], reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Allocation changed through a retained successor version.")
            return redirect(batch)
    return render(request, "vouchers/remittances/form.html", {"form": form, "title": f"Revise {line.reference_label}", "cancel_object": batch})


@require_POST
@voucher_access_required
def submit(request, public_id):
    batch = _batch(public_id, request.user)
    try:
        submit_batch(batch=batch, actor=request.user)
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, "Remittance submitted for independent Accounting review.")
    return redirect(batch)


@require_POST
@voucher_access_required
def review(request, public_id):
    batch = _batch(public_id, request.user)
    form = RemittanceReviewForm(request.POST)
    if form.is_valid():
        try:
            review_batch(batch=batch, actor=request.user, approve=form.cleaned_data["decision"] == "approve", reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            _message_error(request, exc)
        else:
            messages.success(request, "Remittance review decision recorded.")
    else:
        _message_error(request, ValidationError("Complete the review decision and basis."))
    return redirect(batch)


@require_POST
@voucher_access_required
def release(request, public_id):
    batch = _batch(public_id, request.user)
    form = RemittanceReleaseForm(request.POST)
    if form.is_valid():
        try:
            posting = release_batch(batch=batch, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            _message_error(request, exc)
        else:
            messages.success(request, f"Actual remittance recorded. JEV {posting.jev_number} is waiting in Accounting.")
    else:
        _message_error(request, ValidationError("Record the actual release reference."))
    return redirect(batch)


@require_GET
@voucher_access_required
def export(request, public_id):
    batch = _batch(public_id, request.user)
    content, archived = export_batch_csv(batch=batch, actor=request.user)
    filename = f"{slugify(batch.reference_code)}-remittance-register.csv"
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    return response


@require_http_methods(["GET", "POST"])
@voucher_access_required
def tax_filing_create(request, public_id):
    batch = _batch(public_id, request.user)
    if not has_explicit_permission(request.user, "vouchers.prepare_remittances"):
        raise PermissionDenied
    _require_treasury_action(request.user, batch)
    form = TaxFilingEvidenceForm(request.POST or None, batch=batch)
    if request.method == "POST" and form.is_valid():
        try:
            save_draft(batch=batch, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Tax filing evidence saved as a checksum-backed draft.")
            return redirect(batch)
    return render(request, "vouchers/remittances/tax_filing_form.html", {
        "form": form, "title": f"Record tax filing evidence · {batch.reference_code}",
        "cancel_object": batch,
    })


@require_http_methods(["GET", "POST"])
@voucher_access_required
def tax_filing_edit(request, public_id, evidence_id):
    evidence = _evidence(public_id, evidence_id, request.user)
    if not has_explicit_permission(request.user, "vouchers.prepare_remittances"):
        raise PermissionDenied
    _require_treasury_action(request.user, evidence.batch)
    form = TaxFilingEvidenceForm(request.POST or None, instance=evidence, batch=evidence.batch)
    if request.method == "POST" and form.is_valid():
        try:
            save_draft(batch=evidence.batch, evidence=evidence, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Filing evidence correction saved; the prior audit events remain retained.")
            return redirect(evidence.batch)
    return render(request, "vouchers/remittances/tax_filing_form.html", {
        "form": form, "title": f"Correct tax filing evidence v{evidence.version}",
        "cancel_object": evidence.batch,
    })


@require_POST
@voucher_access_required
def tax_filing_submit(request, public_id, evidence_id):
    evidence = _evidence(public_id, evidence_id, request.user)
    try:
        submit_evidence(evidence=evidence, actor=request.user)
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, "Tax filing evidence submitted for independent Accounting verification.")
    return redirect(evidence.batch)


@require_POST
@voucher_access_required
def tax_filing_review(request, public_id, evidence_id):
    evidence = _evidence(public_id, evidence_id, request.user)
    form = TaxFilingEvidenceReviewForm(request.POST)
    if form.is_valid():
        try:
            review_evidence(
                evidence=evidence, actor=request.user,
                approve=form.cleaned_data["decision"] == "approve", reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            _message_error(request, exc)
        else:
            messages.success(request, "Tax filing evidence review recorded.")
    else:
        _message_error(request, ValidationError("Complete the evidence decision and basis."))
    return redirect(evidence.batch)


@require_POST
@voucher_access_required
def tax_filing_amend(request, public_id, evidence_id):
    evidence = _evidence(public_id, evidence_id, request.user)
    form = TaxFilingAmendmentForm(request.POST)
    if form.is_valid():
        try:
            create_amendment(evidence=evidence, actor=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            _message_error(request, exc)
        else:
            messages.success(request, "Amended filing-evidence draft created; the verified prior version is retained.")
    else:
        _message_error(request, ValidationError("Explain why an amended version is required."))
    return redirect(evidence.batch)


@require_GET
@voucher_access_required
def tax_filing_export(request, public_id, evidence_id):
    evidence = _evidence(public_id, evidence_id, request.user)
    content, archived = export_evidence_csv(evidence=evidence, actor=request.user)
    filename = f"{slugify(evidence.batch.reference_code)}-tax-filing-v{evidence.version}.csv"
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    return response
