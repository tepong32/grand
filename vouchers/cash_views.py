import csv

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounting.models import Fund
from finance.models import FinanceConfigurationItem, FinanceConfigurationRelease

from .access import department_for_user, has_explicit_permission, voucher_access_required
from .roles import is_finance_uat_viewer
from .cash_positions import (
    create_policy, create_position, decide_policy, decide_position, export_cash_position_csv,
    open_instrument_exception, policy_availability, resolve_instrument_exception,
    submit_policy, submit_position,
)
from .forms import (
    InstrumentExceptionForm, InstrumentExceptionResolutionForm, TreasuryCashPolicyForm,
    TreasuryCashPositionForm, TreasuryCashReviewForm,
)
from .models import PaymentInstrument, PaymentInstrumentException, TreasuryCashPolicy, TreasuryCashPosition


def _can_view(user):
    return any(has_explicit_permission(user, permission) for permission in (
        "vouchers.view_cash_position", "vouchers.prepare_cash_position",
        "vouchers.approve_cash_position", "vouchers.export_cash_position",
    ))


def _error(request, exc):
    messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))


def _policy(public_id, user=None):
    policy = get_object_or_404(TreasuryCashPolicy.objects.select_related(
        "configuration_release", "configuration_release__department", "treasury_department",
        "created_by", "submitted_by", "approved_by",
    ), public_id=public_id)
    if user and not has_explicit_permission(user, "vouchers.approve_cash_position") and not is_finance_uat_viewer(user):
        if policy.treasury_department != department_for_user(user):
            raise PermissionDenied
    return policy


@require_GET
@voucher_access_required
def workspace(request):
    if not _can_view(request.user):
        raise PermissionDenied
    policy_query = TreasuryCashPolicy.objects.select_related(
        "configuration_release", "treasury_department",
    )
    if not has_explicit_permission(request.user, "vouchers.approve_cash_position") and not is_finance_uat_viewer(request.user):
        policy_query = policy_query.filter(treasury_department=department_for_user(request.user))
    policies = list(policy_query.order_by("-effective_from", "bank_account_code", "fund_code")[:100])
    for policy in policies:
        availability = policy_availability(policy)
        policy.current_position = availability["position"]
        policy.position_current = availability["current"]
        policy.reserved_amount = availability["reserved"]
        policy.available_amount = availability["available"]
    instrument_query = PaymentInstrument.objects.select_related("case").exclude(
        status__in=(PaymentInstrument.DRAFT, PaymentInstrument.CANCELLED),
    )
    exception_query = PaymentInstrumentException.objects.select_related(
        "instrument", "instrument__case", "policy", "opened_by",
    ).filter(status=PaymentInstrumentException.OPEN)
    if not has_explicit_permission(request.user, "vouchers.approve_cash_position") and not is_finance_uat_viewer(request.user):
        instrument_query = instrument_query.filter(case__current_department=department_for_user(request.user))
        exception_query = exception_query.filter(policy__treasury_department=department_for_user(request.user))
    instruments = instrument_query.order_by("-issued_at", "check_number")[:100]
    exceptions = exception_query[:100]
    return render(request, "vouchers/cash/workspace.html", {
        "policies": policies, "instruments": instruments, "exceptions": exceptions,
        "exception_form": InstrumentExceptionForm(),
        "can_prepare": has_explicit_permission(request.user, "vouchers.prepare_cash_position"),
        "can_approve": has_explicit_permission(request.user, "vouchers.approve_cash_position"),
        "can_export": has_explicit_permission(request.user, "vouchers.export_cash_position"),
        "can_exceptions": has_explicit_permission(request.user, "vouchers.manage_payment_exceptions"),
    })


@require_GET
@voucher_access_required
def starter(request):
    if not _can_view(request.user):
        raise PermissionDenied
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="treasury-cash-position-starter.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "finance_setup", "bank_account_code", "fund_code", "control_mode", "minimum_reserve",
        "position_max_age_days", "unclaimed_after_days", "stale_after_days", "effective_from",
        "authority_reference", "local_applicability_note", "as_of_date", "confirmed_inflows",
        "confirmed_outflows", "other_holds", "position_evidence_reference", "preparation_note",
    ])
    releases = FinanceConfigurationRelease.objects.filter(status="active").order_by("-fiscal_year", "code")
    for release in releases:
        banks = FinanceConfigurationItem.objects.filter(
            release=release, category="bank_account", status="active",
        ).order_by("code")
        funds = Fund.objects.filter(department_id=release.department_id, is_active=True).order_by("code")
        for bank in banks:
            for fund in funds:
                writer.writerow([
                    f"{release.code} v{release.version}", bank.code, fund.code, "observe", "0.00",
                    35, 30, 180, release.effective_from, "", "", "", "0.00", "0.00", "0.00", "", "",
                ])
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["GET", "POST"])
@voucher_access_required
def policy_create(request):
    if not has_explicit_permission(request.user, "vouchers.prepare_cash_position"):
        raise PermissionDenied
    form = TreasuryCashPolicyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            policy = create_policy(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Cash-control policy prepared. Submit it for independent review before use.")
            return redirect("vouchers:cash_policy_detail", public_id=policy.public_id)
    return render(request, "vouchers/form.html", {
        "form": form, "title": "Prepare cash-control policy", "cancel_url": "vouchers:cash_workspace",
        "guidance": "Start in Observe mode unless the named Treasury and Accounting owners have accepted the bank/fund route, source evidence, reserve, position age, and instrument-ageing thresholds. Public guidance is not local acceptance by itself.",
    })


@require_GET
@voucher_access_required
def policy_detail(request, public_id):
    if not _can_view(request.user):
        raise PermissionDenied
    policy = _policy(public_id, request.user)
    availability = policy_availability(policy)
    return render(request, "vouchers/cash/detail.html", {
        "policy": policy, "positions": policy.positions.select_related("created_by", "submitted_by", "approved_by"),
        "availability": availability, "position_form": TreasuryCashPositionForm(),
        "review_form": TreasuryCashReviewForm(),
        "can_prepare": has_explicit_permission(request.user, "vouchers.prepare_cash_position"),
        "can_approve": has_explicit_permission(request.user, "vouchers.approve_cash_position"),
        "can_export": has_explicit_permission(request.user, "vouchers.export_cash_position"),
    })


@require_POST
@voucher_access_required
def policy_submit(request, public_id):
    policy = _policy(public_id, request.user)
    try:
        submit_policy(policy=policy, actor=request.user)
    except (ValidationError, PermissionDenied) as exc:
        _error(request, exc)
    else:
        messages.success(request, "Cash policy submitted for independent review.")
    return redirect("vouchers:cash_policy_detail", public_id=public_id)


@require_POST
@voucher_access_required
def policy_decide(request, public_id):
    policy = _policy(public_id, request.user)
    form = TreasuryCashReviewForm(request.POST)
    if form.is_valid():
        try:
            decide_policy(
                policy=policy, actor=request.user,
                approve=form.cleaned_data["decision"] == "approve", reason=form.cleaned_data["reason"],
            )
        except (ValidationError, PermissionDenied) as exc:
            _error(request, exc)
        else:
            messages.success(request, "Cash-policy review decision recorded.")
    else:
        _error(request, ValidationError("Complete the review decision and basis."))
    return redirect("vouchers:cash_policy_detail", public_id=public_id)


@require_POST
@voucher_access_required
def position_create(request, public_id):
    policy = _policy(public_id, request.user)
    form = TreasuryCashPositionForm(request.POST)
    if form.is_valid():
        try:
            create_position(policy=policy, actor=request.user, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _error(request, exc)
        else:
            messages.success(request, "Cash position prepared from the latest reconciled bank evidence.")
    else:
        _error(request, ValidationError("Correct the cash-position form before saving."))
    return redirect("vouchers:cash_policy_detail", public_id=public_id)


@require_POST
@voucher_access_required
def position_submit(request, public_id, position_id):
    policy = _policy(public_id, request.user)
    position = get_object_or_404(TreasuryCashPosition, public_id=position_id, policy=policy)
    try:
        submit_position(position=position, actor=request.user)
    except (ValidationError, PermissionDenied) as exc:
        _error(request, exc)
    else:
        messages.success(request, "Cash position submitted for independent review.")
    return redirect("vouchers:cash_policy_detail", public_id=public_id)


@require_POST
@voucher_access_required
def position_decide(request, public_id, position_id):
    policy = _policy(public_id, request.user)
    position = get_object_or_404(TreasuryCashPosition, public_id=position_id, policy=policy)
    form = TreasuryCashReviewForm(request.POST)
    if form.is_valid():
        try:
            decide_position(
                position=position, actor=request.user,
                approve=form.cleaned_data["decision"] == "approve", reason=form.cleaned_data["reason"],
            )
        except (ValidationError, PermissionDenied) as exc:
            _error(request, exc)
        else:
            messages.success(request, "Cash-position review decision recorded.")
    else:
        _error(request, ValidationError("Complete the review decision and basis."))
    return redirect("vouchers:cash_policy_detail", public_id=public_id)


@require_POST
@voucher_access_required
def exception_open(request):
    form = InstrumentExceptionForm(request.POST)
    if form.is_valid():
        try:
            open_instrument_exception(actor=request.user, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _error(request, exc)
        else:
            messages.success(request, "Instrument exception recorded without rewriting its issue/release history.")
    else:
        _error(request, ValidationError("Complete the instrument exception and evidence fields."))
    return redirect("vouchers:cash_workspace")


@require_POST
@voucher_access_required
def exception_resolve(request, public_id):
    exception = get_object_or_404(PaymentInstrumentException, public_id=public_id)
    form = InstrumentExceptionResolutionForm(request.POST)
    if form.is_valid():
        try:
            resolve_instrument_exception(exception=exception, actor=request.user, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _error(request, exc)
        else:
            messages.success(request, "Instrument exception resolution recorded.")
    else:
        _error(request, ValidationError("Record the reviewed resolution action and evidence."))
    return redirect("vouchers:cash_workspace")


@require_GET
@voucher_access_required
def export(request, public_id=None):
    policy = _policy(public_id, request.user) if public_id else None
    content, archived = export_cash_position_csv(actor=request.user, policy=policy)
    stem = slugify(str(policy)) if policy else "all-cash-positions"
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{stem}-cash-position.csv"'
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    return response
