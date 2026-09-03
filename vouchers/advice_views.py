import csv
import io

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from finance.models import FinanceConfigurationItem

from .access import department_for_user, has_explicit_permission, voucher_access_required
from .advice import (
    clarify_returned_instrument_review, create_advice_batch, decide_returned_instrument,
    export_bank_advice_csv, record_advice_submission, record_bank_response,
    review_advice, submit_advice_for_review,
)
from .advice_register import (
    BANK_ADVICE_ATTENTION_CHOICES, apply_bank_advice_filters, visible_bank_advice_batches,
)
from .forms import (
    AdviceStateForm, BankAdviceBatchForm, BankAdviceResponseForm, BankAdviceReviewForm,
    BankAdviceSubmissionForm, ReturnedInstrumentClarificationForm,
    ReturnedInstrumentDecisionForm,
)
from .models import BankAdviceBatch, ReturnedInstrumentReview
from .returned_instrument_register import (
    returned_instrument_attention_choices_for_user, returned_instrument_attention_queryset,
    visible_returned_instrument_reviews,
)
from .roles import finance_workspace_profile


def _review_query(user):
    return visible_returned_instrument_reviews(user)


def _batch(public_id, user):
    item = get_object_or_404(visible_bank_advice_batches(user), public_id=public_id)
    return item


@voucher_access_required
def workspace(request):
    if not has_explicit_permission(request.user, "vouchers.view_bank_advice"):
        raise PermissionDenied
    batches, selected_status, selected_attention = apply_bank_advice_filters(
        visible_bank_advice_batches(request.user),
        status=request.GET.get("status", ""), attention=request.GET.get("attention", ""),
    )
    batches = batches.order_by("-advice_date", "-created_at")
    returned_attention = request.GET.get("returned_attention", "")
    if returned_attention:
        reviews, selected_returned_attention, returned_work_spec = returned_instrument_attention_queryset(
            request.user, returned_attention,
        )
    else:
        reviews = _review_query(request.user).exclude(status=ReturnedInstrumentReview.SUPERSEDED)
        selected_returned_attention, returned_work_spec = "", None
    reviews = reviews.order_by("-prepared_at")
    return render(request, "vouchers/advice/workspace.html", {
        "batches": batches,
        "returned_reviews": reviews,
        "profile": finance_workspace_profile(request.user),
        "can_prepare": has_explicit_permission(request.user, "vouchers.prepare_bank_advice"),
        "can_review": has_explicit_permission(request.user, "vouchers.approve_bank_advice"),
        "can_submit": has_explicit_permission(request.user, "vouchers.submit_bank_advice"),
        "can_acknowledge": has_explicit_permission(request.user, "vouchers.acknowledge_bank_advice"),
        "can_review_returns": has_explicit_permission(request.user, "vouchers.review_returned_instruments"),
        "can_manage_returns": has_explicit_permission(request.user, "vouchers.manage_payment_exceptions"),
        "can_export": has_explicit_permission(request.user, "vouchers.export_bank_advice"),
        "status_choices": BankAdviceBatch.STATUS_CHOICES,
        "attention_choices": BANK_ADVICE_ATTENTION_CHOICES,
        "selected_status": selected_status,
        "selected_attention": selected_attention,
        "visible_count": batches.count(),
        "returned_attention_choices": returned_instrument_attention_choices_for_user(request.user),
        "selected_returned_attention": selected_returned_attention,
        "returned_work_spec": returned_work_spec,
        "returned_visible_count": reviews.count(),
    })


@voucher_access_required
def create(request):
    if not has_explicit_permission(request.user, "vouchers.prepare_bank_advice"):
        raise PermissionDenied
    form = BankAdviceBatchForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            batch = create_advice_batch(actor=request.user, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, " ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Bank-advice draft prepared with a retained instrument snapshot.")
            return redirect("vouchers:advice_detail", public_id=batch.public_id)
    return render(request, "vouchers/advice/form.html", {
        "form": form, "title": "Prepare bank-advice batch",
        "guidance": "Group issued instruments for one bank account. This creates a retained version; corrections after review use a successor.",
    })


@voucher_access_required
def successor(request, public_id):
    prior = _batch(public_id, request.user)
    if not has_explicit_permission(request.user, "vouchers.prepare_bank_advice"):
        raise PermissionDenied
    if prior.status not in (BankAdviceBatch.REVIEW_RETURNED, BankAdviceBatch.RETURNED):
        raise Http404
    form = BankAdviceBatchForm(request.POST or None, actor=request.user, supersedes=prior)
    if request.method == "POST" and form.is_valid():
        try:
            batch = create_advice_batch(actor=request.user, supersedes=prior, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, " ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Corrected advice successor prepared; the returned version remains in history.")
            return redirect("vouchers:advice_detail", public_id=batch.public_id)
    return render(request, "vouchers/advice/form.html", {
        "form": form, "title": f"Correct {prior.advice_number} · v{prior.version}",
        "guidance": "Keep valid evidence, make only the instructed correction, and explain the successor clearly.",
    })


@voucher_access_required
def detail(request, public_id):
    batch = _batch(public_id, request.user)
    return render(request, "vouchers/advice/detail.html", {
        "batch": batch,
        "submit_form": AdviceStateForm(batch=batch),
        "review_form": BankAdviceReviewForm(batch=batch),
        "submission_form": BankAdviceSubmissionForm(batch=batch),
        "response_form": BankAdviceResponseForm(batch=batch),
        "can_prepare": has_explicit_permission(request.user, "vouchers.prepare_bank_advice"),
        "can_review": has_explicit_permission(request.user, "vouchers.approve_bank_advice"),
        "can_submit": has_explicit_permission(request.user, "vouchers.submit_bank_advice"),
        "can_acknowledge": has_explicit_permission(request.user, "vouchers.acknowledge_bank_advice"),
        "can_export": has_explicit_permission(request.user, "vouchers.export_bank_advice"),
    })


def _transition(request, public_id, form_class, operation, success):
    batch = _batch(public_id, request.user)
    form = form_class(request.POST, batch=batch)
    if not form.is_valid():
        messages.error(request, "Correct the action form: " + "; ".join(
            f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()
        ))
        return redirect("vouchers:advice_detail", public_id=batch.public_id)
    try:
        operation(batch, form.cleaned_data)
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
    else:
        messages.success(request, success)
    return redirect("vouchers:advice_detail", public_id=batch.public_id)


@require_POST
@voucher_access_required
def submit_review(request, public_id):
    return _transition(
        request, public_id, AdviceStateForm,
        lambda batch, data: submit_advice_for_review(
            batch=batch, actor=request.user, expected_version=data["state_version"],
        ),
        "Advice submitted for independent Accounting review.",
    )


@require_POST
@voucher_access_required
def review(request, public_id):
    return _transition(
        request, public_id, BankAdviceReviewForm,
        lambda batch, data: review_advice(
            batch=batch, actor=request.user, approve=data["decision"] == "approve",
            note=data["note"], expected_version=data["state_version"],
        ),
        "Accounting review decision recorded.",
    )


@require_POST
@voucher_access_required
def submit_bank(request, public_id):
    return _transition(
        request, public_id, BankAdviceSubmissionForm,
        lambda batch, data: record_advice_submission(
            batch=batch, actor=request.user, submission_reference=data["submission_reference"],
            evidence_reference=data["evidence_reference"], expected_version=data["state_version"],
        ),
        "Bank submission evidence recorded.",
    )


@require_POST
@voucher_access_required
def bank_response(request, public_id):
    return _transition(
        request, public_id, BankAdviceResponseForm,
        lambda batch, data: record_bank_response(
            batch=batch, actor=request.user, acknowledged=data["response"] == "acknowledged",
            response_reference=data["response_reference"], evidence_reference=data["evidence_reference"],
            reason=data["reason"], expected_version=data["state_version"],
        ),
        "Bank response recorded; affected voucher queues were updated without rewriting prior evidence.",
    )


@require_POST
@voucher_access_required
def returned_decide(request, public_id):
    review = get_object_or_404(_review_query(request.user), public_id=public_id)
    form = ReturnedInstrumentDecisionForm(request.POST, review=review)
    if form.is_valid():
        try:
            decide_returned_instrument(
                review=review, actor=request.user, approve=form.cleaned_data["decision"] == "approve",
                outcome=form.cleaned_data["outcome"], decision_reason=form.cleaned_data["decision_reason"],
                evidence_reference=form.cleaned_data["evidence_reference"],
                expected_version=form.cleaned_data["state_version"],
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Returned-instrument Accounting decision recorded.")
    else:
        messages.error(request, "Correct the returned-item decision form.")
    return redirect("vouchers:advice_workspace")


@require_POST
@voucher_access_required
def returned_clarify(request, public_id):
    review = get_object_or_404(_review_query(request.user), public_id=public_id)
    form = ReturnedInstrumentClarificationForm(request.POST, review=review)
    if form.is_valid():
        try:
            clarify_returned_instrument_review(
                review=review, actor=request.user, note=form.cleaned_data["note"],
                evidence_reference=form.cleaned_data["evidence_reference"],
                expected_version=form.cleaned_data["state_version"],
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Clarified successor returned to Accounting; the earlier review remains retained.")
    else:
        messages.error(request, "Record both the clarification and evidence reference.")
    return redirect("vouchers:advice_workspace")


@voucher_access_required
def export(request, public_id=None):
    batch = _batch(public_id, request.user) if public_id else None
    content, archived = export_bank_advice_csv(actor=request.user, batch=batch)
    filename = f"bank-advice-{batch.advice_number if batch else timezone.localdate().isoformat()}.csv"
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    return response


@voucher_access_required
def starter(request):
    if not has_explicit_permission(request.user, "vouchers.view_bank_advice"):
        raise PermissionDenied
    department = department_for_user(request.user)
    bank_accounts = FinanceConfigurationItem.objects.filter(
        release__department=department, category="bank_account",
        status__in=("approved", "scheduled", "active", "superseded"),
    ).select_related("release").order_by("release__fiscal_year", "code")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow([
        "advice_number", "advice_date", "bank_account_code", "instrument_number",
        "fund_code", "amount", "preparation_note", "authority_reference",
        "local_applicability_note", "submission_reference", "bank_response_reference",
    ])
    if bank_accounts:
        for bank in bank_accounts:
            writer.writerow([
                "EDIT-ME", timezone.localdate().isoformat(), bank.code, "EDIT-ME", "EDIT-ME", "0.00",
                "Describe the familiar Accounting/Treasury preparation check.",
                "Replace with reviewed COA/bank/local authority before submission.",
                "Name local approvers, bank practice, copies, deadlines, and retained evidence.", "", "",
            ])
    else:
        writer.writerow([
            "EDIT-ME", timezone.localdate().isoformat(), "EDIT-ME", "EDIT-ME", "EDIT-ME", "0.00",
            "Describe the familiar Accounting/Treasury preparation check.",
            "Replace with reviewed COA/bank/local authority before submission.",
            "Name local approvers, bank practice, copies, deadlines, and retained evidence.", "", "",
        ])
    response = HttpResponse(stream.getvalue().encode("utf-8-sig"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="BANK_ADVICE_STARTER.csv"'
    return response
