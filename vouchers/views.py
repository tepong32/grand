from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .access import can_view_workbench, has_explicit_permission, voucher_access_required
from .forms import (
    AccountingValidationForm, BankAdviceForm, BudgetCertificationForm, PayableIntakeForm,
    CancelCheckForm, CheckIssueForm, CheckReleaseForm, ReturnCaseForm,
    NonFinancialAmendmentForm, SignatureReturnForm, SubmitChecksForm, VoucherPreparationForm,
    TracePointLinkForm, PayableEvidenceForm, PayableReviewForm, PayableSubmitForm,
)
from .models import PaymentInstrument, VoucherCase, VoucherOutput
from .roles import STAGE_NEXT_ACTION, finance_workspace_profile
from .services import (
    VoucherWorkflowError, _active_release, amend_nonfinancial_voucher, cancel_check, certify_budget,
    create_payable_case_from_obligation,
    finalize_bank_advice, generate_shadow_dv, issue_check, link_tracepoint_item, prepare_voucher, record_signature_return,
    reconcile_authoritative_obligation, release_check, return_case, submit_checks_for_advice, validate_accounting,
    record_payable_document_evidence, review_payable_intake, submit_payable_intake,
)


def _permissions(user):
    return {
        "initiate_payable": has_explicit_permission(user, "vouchers.initiate_payable_case"),
        "certify": has_explicit_permission(user, "vouchers.certify_budget_obligation"),
        "review_payable": has_explicit_permission(user, "vouchers.review_payable_intake"),
        "prepare": has_explicit_permission(user, "vouchers.prepare_disbursement_voucher"),
        "signatures": has_explicit_permission(user, "vouchers.track_wet_signatures"),
        "tracepoint_link": has_explicit_permission(user, "vouchers.link_tracepoint_custody"),
        "validate": has_explicit_permission(user, "vouchers.validate_accounting_voucher"),
        "issue": has_explicit_permission(user, "vouchers.issue_payment_instruments"),
        "advice": has_explicit_permission(user, "vouchers.finalize_bank_advice"),
        "release": has_explicit_permission(user, "vouchers.release_payment_instruments"),
        "exceptions": has_explicit_permission(user, "vouchers.manage_payment_exceptions"),
        "return": has_explicit_permission(user, "vouchers.return_voucher_case"),
        "amend_nonfinancial": has_explicit_permission(user, "vouchers.amend_nonfinancial_voucher"),
        "audit": has_explicit_permission(user, "vouchers.view_voucher_audit"),
    }


def _actionable_stages(permissions, can_access_accounting=False):
    stages = []
    for allowed, stage in (
        (permissions["certify"], VoucherCase.BUDGET_DRAFT),
        (permissions["initiate_payable"], VoucherCase.PAYABLE_PREPARATION),
        (permissions["review_payable"], VoucherCase.PAYABLE_REVIEW),
        (permissions["prepare"], VoucherCase.ACCOUNTING_PREPARATION),
        (permissions["signatures"], VoucherCase.AWAITING_SIGNATURES),
        (permissions["validate"], VoucherCase.ACCOUNTING_VALIDATION),
        (can_access_accounting, VoucherCase.ACCOUNTING_POSTING),
        (permissions["issue"], VoucherCase.TREASURY_CHECK_PREPARATION),
        (permissions["advice"], VoucherCase.ACCOUNTING_BANK_ADVICE),
        (permissions["release"], VoucherCase.TREASURY_RELEASE),
    ):
        if allowed:
            stages.append(stage)
    return tuple(stages)


def _decorate_cases(cases, actionable_stages=()):
    actionable_stages = set(actionable_stages)
    rows = list(cases)
    for case in rows:
        case.next_action_label = STAGE_NEXT_ACTION.get(case.current_stage, case.get_current_stage_display())
        case.ready_for_user = case.current_stage in actionable_stages
    return rows


@voucher_access_required
def workspace(request):
    cases = VoucherCase.objects.select_related(
        "requesting_department", "current_department", "payee", "configuration_release",
    ).annotate(check_count=Count("payment_instruments"))
    permissions = _permissions(request.user)
    profile = finance_workspace_profile(request.user, request.GET.get("office"))
    from accounting.access import can_post_journals, can_prepare_journals
    can_handle_posting = can_prepare_journals(request.user) or can_post_journals(request.user)
    actionable_stages = _actionable_stages(
        permissions,
        can_handle_posting and not profile["is_uat_viewer"],
    )
    queue_stages = profile["stages"] if profile["is_uat_viewer"] else actionable_stages
    queue_query = cases.filter(current_stage__in=queue_stages)
    queue_ids = list(queue_query.values_list("pk", flat=True)[:100])
    queue_cases = _decorate_cases(
        cases.filter(pk__in=queue_ids).order_by("-updated_at", "-pk"),
        actionable_stages,
    )
    other_cases = _decorate_cases(cases.exclude(pk__in=queue_ids)[:100], actionable_stages)
    stage_counts = {stage: cases.filter(current_stage=stage).count() for stage, _label in VoucherCase.STAGE_CHOICES}
    return render(request, "vouchers/workspace.html", {
        "cases": other_cases, "queue_cases": queue_cases, "workspace_profile": profile,
        "stage_counts": stage_counts, "permissions": permissions,
        "queue_count": queue_query.count(),
        "open_count": cases.exclude(current_stage__in=(VoucherCase.COMPLETED, VoucherCase.CANCELLED)).count(),
        "completed_count": stage_counts[VoucherCase.COMPLETED],
    })


@voucher_access_required
def case_create(request):
    if not has_explicit_permission(request.user, "vouchers.initiate_payable_case"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        release = _active_release()
    except VoucherWorkflowError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("vouchers:workspace")
    from .access import department_for_user
    department = department_for_user(request.user)
    form = PayableIntakeForm(request.POST or None, release=release, department=department)
    if request.method == "POST" and form.is_valid():
        try:
            case = create_payable_case_from_obligation(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if case.obligation_binding_status == VoucherCase.BINDING_LINKED:
                messages.success(
                    request,
                    "Payable case linked to the certified obligation. Complete its transaction-specific checklist before Accounting review.",
                )
            else:
                messages.warning(request, "Payable case retained, but its obligation link needs reconciliation before Accounting can proceed.")
            return redirect(case)
    return render(request, "vouchers/form.html", {
        "form": form, "title": "Open payable from certified obligation",
        "guidance": "Select the requesting office's certified F4.2 obligation and reference, rather than duplicate, procurement, delivery, inspection/acceptance, invoice, and claim evidence. Use synthetic UAT evidence until local forms and procedures are accepted.",
    })


def _case(public_id):
    return get_object_or_404(
        VoucherCase.objects.select_related(
            "requesting_department", "current_department", "configuration_release", "voucher_template", "payee",
            "obligation", "obligation__certified_by", "payable_intake", "disbursement_voucher", "disbursement_voucher__prepared_by",
        ).prefetch_related(
            "obligation__allocation_lines", "signature_tasks", "accounting_validations__validated_by",
            "payment_instruments__advice_item__batch", "events__actor", "events__actor_department",
            "tasks", "payee__authorized_claimants", "outputs__template",
            "posting_requests",
            "nonfinancial_amendments__amended_by",
            "payable_document_evidence__source_rule", "payable_document_evidence__recorded_by",
        ), public_id=public_id,
    )


@voucher_access_required
def case_detail(request, public_id):
    case = _case(public_id)
    permissions = _permissions(request.user)
    profile = finance_workspace_profile(request.user)
    from accounting.access import can_post_journals, can_prepare_journals
    can_handle_posting = can_prepare_journals(request.user) or can_post_journals(request.user)
    actionable_stages = _actionable_stages(
        permissions,
        can_handle_posting and not profile["is_uat_viewer"],
    )
    amendment_stages = {
        VoucherCase.AWAITING_SIGNATURES,
        VoucherCase.ACCOUNTING_VALIDATION,
        VoucherCase.ACCOUNTING_POSTING,
        VoucherCase.TREASURY_CHECK_PREPARATION,
    }
    return render(request, "vouchers/case_detail.html", {
        "case": case, "permissions": permissions, "workspace_profile": profile,
        "next_action_label": STAGE_NEXT_ACTION.get(case.current_stage, case.get_current_stage_display()),
        "case_ready_for_user": case.current_stage in actionable_stages,
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
        "amendment_form": NonFinancialAmendmentForm(case=case),
        "payable_evidence_form": PayableEvidenceForm(case=case),
        "payable_submit_form": PayableSubmitForm(case=case),
        "payable_review_form": PayableReviewForm(case=case),
        "can_amend_nonfinancial": bool(
            permissions["amend_nonfinancial"]
            and hasattr(case, "disbursement_voucher")
            and case.current_stage in amendment_stages
            and not case.payment_instruments.exists()
        ),
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
        "amend-nonfinancial": NonFinancialAmendmentForm,
        "reconcile-obligation": SubmitChecksForm,
        "record-payable-evidence": PayableEvidenceForm,
        "submit-payable": PayableSubmitForm,
        "review-payable": PayableReviewForm,
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
        elif action == "reconcile-obligation":
            reconcile_authoritative_obligation(**common)
        elif action == "record-payable-evidence":
            record_payable_document_evidence(
                **common, evidence=data["evidence"], status=data["status"],
                evidence_reference=data["evidence_reference"], decision_note=data["decision_note"],
            )
        elif action == "submit-payable":
            submit_payable_intake(**common)
        elif action == "review-payable":
            review_payable_intake(**common, decision=data["decision"], reason=data["reason"])
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
        elif action == "amend-nonfinancial":
            amend_nonfinancial_voucher(
                **common,
                voucher_date=data["voucher_date"],
                signatories=data["signatories"],
                reason=data["reason"],
            )
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
