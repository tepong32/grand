from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .access import can_view_workbench, has_explicit_permission, voucher_access_required
from .forms import (
    AccountingValidationForm, BankAdviceForm, BudgetCaseForm, BudgetCertificationForm,
    CancelCheckForm, CheckIssueForm, CheckReleaseForm, ReturnCaseForm,
    SignatureReturnForm, SubmitChecksForm, VoucherPreparationForm,
    TracePointLinkForm,
)
from .models import PaymentInstrument, VoucherCase, VoucherOutput
from .services import (
    VoucherWorkflowError, _active_release, cancel_check, certify_budget, create_budget_case,
    finalize_bank_advice, generate_shadow_dv, issue_check, link_tracepoint_item, prepare_voucher, record_signature_return,
    release_check, return_case, submit_checks_for_advice, validate_accounting,
)


def _permissions(user):
    return {
        "initiate": has_explicit_permission(user, "vouchers.initiate_budget_case"),
        "certify": has_explicit_permission(user, "vouchers.certify_budget_obligation"),
        "prepare": has_explicit_permission(user, "vouchers.prepare_disbursement_voucher"),
        "signatures": has_explicit_permission(user, "vouchers.track_wet_signatures"),
        "tracepoint_link": has_explicit_permission(user, "vouchers.link_tracepoint_custody"),
        "validate": has_explicit_permission(user, "vouchers.validate_accounting_voucher"),
        "issue": has_explicit_permission(user, "vouchers.issue_payment_instruments"),
        "advice": has_explicit_permission(user, "vouchers.finalize_bank_advice"),
        "release": has_explicit_permission(user, "vouchers.release_payment_instruments"),
        "exceptions": has_explicit_permission(user, "vouchers.manage_payment_exceptions"),
        "return": has_explicit_permission(user, "vouchers.return_voucher_case"),
        "audit": has_explicit_permission(user, "vouchers.view_voucher_audit"),
    }


@voucher_access_required
def workspace(request):
    cases = VoucherCase.objects.select_related(
        "requesting_department", "current_department", "payee", "configuration_release",
    ).annotate(check_count=Count("payment_instruments"))
    stage_counts = {stage: cases.filter(current_stage=stage).count() for stage, _label in VoucherCase.STAGE_CHOICES}
    return render(request, "vouchers/workspace.html", {
        "cases": cases[:100], "stage_counts": stage_counts, "permissions": _permissions(request.user),
        "open_count": cases.exclude(current_stage__in=(VoucherCase.COMPLETED, VoucherCase.CANCELLED)).count(),
        "completed_count": stage_counts[VoucherCase.COMPLETED],
    })


@voucher_access_required
def case_create(request):
    if not has_explicit_permission(request.user, "vouchers.initiate_budget_case"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        release = _active_release()
    except VoucherWorkflowError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("vouchers:workspace")
    form = BudgetCaseForm(request.POST or None, release=release)
    if request.method == "POST" and form.is_valid():
        try:
            case = create_budget_case(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Shadow-mode Budget case created from governed master data.")
            return redirect(case)
    return render(request, "vouchers/form.html", {"form": form, "title": "Open Budget obligation case", "guidance": "This creates one shared case. It does not create a new appropriation or claim official authority while shadow mode is active."})


def _case(public_id):
    return get_object_or_404(
        VoucherCase.objects.select_related(
            "requesting_department", "current_department", "configuration_release", "voucher_template", "payee",
            "obligation", "obligation__certified_by", "disbursement_voucher", "disbursement_voucher__prepared_by",
        ).prefetch_related(
            "obligation__allocation_lines", "signature_tasks", "accounting_validations__validated_by",
            "payment_instruments__advice_item__batch", "events__actor", "events__actor_department",
            "tasks", "payee__authorized_claimants", "outputs__template",
            "posting_requests",
        ), public_id=public_id,
    )


@voucher_access_required
def case_detail(request, public_id):
    case = _case(public_id)
    return render(request, "vouchers/case_detail.html", {
        "case": case, "permissions": _permissions(request.user),
        "budget_form": BudgetCertificationForm(case=case),
        "voucher_form": VoucherPreparationForm(case=case),
        "signature_form": SignatureReturnForm(case=case),
        "validation_form": AccountingValidationForm(case=case),
        "check_form": CheckIssueForm(case=case),
        "submit_checks_form": SubmitChecksForm(case=case),
        "advice_form": BankAdviceForm(case=case),
        "release_form": CheckReleaseForm(case=case),
        "return_form": ReturnCaseForm(case=case),
        "cancel_form": CancelCheckForm(case=case),
        "tracepoint_form": TracePointLinkForm(case=case),
    })


@voucher_access_required
def case_action(request, public_id, action):
    if request.method != "POST":
        raise Http404
    case = _case(public_id)
    forms = {
        "certify-budget": BudgetCertificationForm,
        "prepare-dv": VoucherPreparationForm,
        "record-signature": SignatureReturnForm,
        "validate-accounting": AccountingValidationForm,
        "issue-check": CheckIssueForm,
        "submit-checks": SubmitChecksForm,
        "finalize-advice": BankAdviceForm,
        "release-check": CheckReleaseForm,
        "return": ReturnCaseForm,
        "cancel-check": CancelCheckForm,
        "generate-dv": SubmitChecksForm,
        "link-tracepoint": TracePointLinkForm,
    }
    form_class = forms.get(action)
    if not form_class:
        raise Http404
    form = form_class(request.POST, case=case)
    if not form.is_valid():
        messages.error(request, "Correct the action form: " + "; ".join(f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()))
        return redirect(case)
    data = form.cleaned_data
    common = {"case": case, "actor": request.user, "expected_version": data["state_version"], "idempotency_key": data["idempotency_key"]}
    try:
        if action == "certify-budget":
            certify_budget(
                **common, obligation_date=data["obligation_date"], budget_source_reference=data["budget_source_reference"],
                allocations=[{"fund_code": data["fund_code"], "responsibility_center_code": data["responsibility_center_code"], "account_code": data["account_code"], "amount": data["amount"]}],
            )
        elif action == "prepare-dv":
            deductions = []
            if data.get("deduction_code"):
                deductions.append({"code": data["deduction_code"], "description": dict(form.fields["deduction_code"].choices)[data["deduction_code"]], "amount": data["deduction_amount"]})
            prepare_voucher(
                **common, voucher_date=data["voucher_date"], gross_amount=data["gross_amount"], deductions=deductions,
                line_description=data["line_description"], line_account_code=data["line_account_code"], document_codes=data["document_codes"],
            )
        elif action == "record-signature":
            record_signature_return(**common, task=data["task"], note=data["note"])
        elif action == "validate-accounting":
            validate_accounting(**common, jev_number=data["jev_number"], jev_date=data["jev_date"], note=data["note"])
        elif action == "issue-check":
            issue_check(**common, bank_account_code=data["bank_account_code"], check_number=data["check_number"], amount=data["amount"], replaces=data["replaces"])
        elif action == "submit-checks":
            submit_checks_for_advice(**common)
        elif action == "finalize-advice":
            finalize_bank_advice(**common, advice_number=data["advice_number"], advice_date=data["advice_date"])
        elif action == "release-check":
            release_check(**common, instrument=data["instrument"], claimant=data["claimant"], receipt_reference=data["receipt_reference"])
        elif action == "return":
            return_case(**common, target_stage=data["target_stage"], reason=data["reason"])
        elif action == "cancel-check":
            cancel_check(**common, instrument=data["instrument"], reason=data["reason"])
        elif action == "generate-dv":
            generate_shadow_dv(case=case, actor=request.user, idempotency_key=data["idempotency_key"])
        elif action == "link-tracepoint":
            from tracepoint.models import PacketItem
            item = get_object_or_404(PacketItem, reference_number=data["reference_number"])
            link_tracepoint_item(**common, item=item)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "Voucher action recorded in the append-only workflow history.")
    return redirect(case)


@voucher_access_required
def output_download(request, public_id, output_pk):
    case = _case(public_id)
    output = get_object_or_404(VoucherOutput, pk=output_pk, case=case)
    output.file.open("rb")
    response = FileResponse(output.file, as_attachment=True, filename=output.file.name.rsplit("/", 1)[-1])
    response["X-GRAND-Output-Mode"] = output.status
    response["X-GRAND-SHA256"] = output.checksum
    return response
