import csv

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import can_view_workbench, has_explicit_permission, voucher_access_required
from .forms import (
    AccountingValidationForm, BankAdviceForm, BudgetCertificationForm, PayableIntakeForm,
    CancelCheckForm, CheckIssueForm, CheckReleaseForm, ReturnCaseForm,
    NonFinancialAmendmentForm, SignatureReturnForm, SubmitChecksForm,
    VoucherDeductionFormSet, VoucherPreparationForm,
    TracePointLinkForm, PayableEvidenceForm, PayableReviewForm, PayableSubmitForm,
    PayableAllocationAddForm, PayableAllocationRevisionForm, PayableClaimControlForm,
    ControlledPrintPrepareForm, FinancePacketAssemblyForm, PrintEvidenceForm,
)
from .models import PaymentInstrument, VoucherCase, VoucherOutput, VoucherPostingRequest, VoucherPrintJob
from .roles import STAGE_NEXT_ACTION, finance_workspace_profile
from .services import (
    VoucherWorkflowError, _active_release, amend_nonfinancial_voucher, cancel_check, certify_budget,
    create_payable_case_from_obligation,
    finalize_bank_advice, generate_shadow_dv, issue_check, link_tracepoint_item, prepare_voucher, record_signature_return,
    reconcile_authoritative_obligation, release_check, return_case, submit_checks_for_advice, validate_accounting,
    record_payable_document_evidence, review_payable_intake, submit_payable_intake,
    add_payable_obligation_allocation, payable_relationship_summary,
    revise_payable_claim_control, revise_payable_obligation_allocation,
    assemble_finance_packet, prepare_controlled_dv_print, record_dv_printed,
)


def _csv_safe(value):
    """Keep portable CSV text from being treated as a spreadsheet formula."""
    text = str(value or "")
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def _permissions(user):
    return {
        "initiate_payable": has_explicit_permission(user, "vouchers.initiate_payable_case"),
        "certify": has_explicit_permission(user, "vouchers.certify_budget_obligation"),
        "review_payable": has_explicit_permission(user, "vouchers.review_payable_intake"),
        "prepare": has_explicit_permission(user, "vouchers.prepare_disbursement_voucher"),
        "control_print": has_explicit_permission(user, "vouchers.control_dv_printing"),
        "signatures": has_explicit_permission(user, "vouchers.track_wet_signatures"),
        "tracepoint_link": has_explicit_permission(user, "vouchers.link_tracepoint_custody"),
        "validate": has_explicit_permission(user, "vouchers.validate_accounting_voucher"),
        "issue": has_explicit_permission(user, "vouchers.issue_payment_instruments"),
        "advice": has_explicit_permission(user, "vouchers.prepare_bank_advice"),
        "advice_view": has_explicit_permission(user, "vouchers.view_bank_advice"),
        "returned_review": has_explicit_permission(user, "vouchers.review_returned_instruments"),
        "release": has_explicit_permission(user, "vouchers.release_payment_instruments"),
        "exceptions": has_explicit_permission(user, "vouchers.manage_payment_exceptions"),
        "cash_view": has_explicit_permission(user, "vouchers.view_cash_position"),
        "cash_prepare": has_explicit_permission(user, "vouchers.prepare_cash_position"),
        "cash_approve": has_explicit_permission(user, "vouchers.approve_cash_position"),
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
        (can_access_accounting, VoucherCase.ACCOUNTING_EVENT_POSTING),
        (permissions["returned_review"], VoucherCase.ACCOUNTING_RETURNED_ITEM),
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
            "payment_instruments__current_advice_batch", "events__actor", "events__actor_department",
            "tasks", "payee__authorized_claimants", "outputs__template",
            "posting_requests",
            "nonfinancial_amendments__amended_by",
            "payable_document_evidence__source_rule", "payable_document_evidence__recorded_by",
        ), public_id=public_id,
    )


def _voucher_deduction_formset(case, data=None):
    initial = []
    if data is None and hasattr(case, "disbursement_voucher"):
        initial = [
            {"tax_rule": item.tax_rule_item_id, "tax_base": item.tax_base, "amount": item.amount}
            for item in case.disbursement_voucher.deductions.select_related("tax_rule_item").order_by("pk")
        ]
    return VoucherDeductionFormSet(data, prefix="deductions", case=case, initial=initial)


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
    relationship_summary = payable_relationship_summary(case) if hasattr(case, "payable_intake") else None
    current_print_job = case.print_jobs.order_by("-version").first()
    return render(request, "vouchers/case_detail.html", {
        "case": case, "permissions": permissions, "workspace_profile": profile,
        "next_action_label": STAGE_NEXT_ACTION.get(case.current_stage, case.get_current_stage_display()),
        "case_ready_for_user": case.current_stage in actionable_stages,
        "budget_form": BudgetCertificationForm(case=case),
        "voucher_form": VoucherPreparationForm(case=case),
        "voucher_deduction_formset": _voucher_deduction_formset(case),
        "signature_form": SignatureReturnForm(case=case),
        "validation_form": AccountingValidationForm(case=case),
        "check_form": CheckIssueForm(case=case),
        "submit_checks_form": SubmitChecksForm(case=case),
        "advice_form": BankAdviceForm(case=case),
        "release_form": CheckReleaseForm(case=case),
        "return_form": ReturnCaseForm(case=case),
        "cancel_form": CancelCheckForm(case=case),
        "tracepoint_form": TracePointLinkForm(case=case),
        "controlled_print_form": ControlledPrintPrepareForm(case=case),
        "print_evidence_form": PrintEvidenceForm(case=case),
        "packet_assembly_form": FinancePacketAssemblyForm(case=case),
        "amendment_form": NonFinancialAmendmentForm(case=case),
        "payable_evidence_form": PayableEvidenceForm(case=case),
        "payable_submit_form": PayableSubmitForm(case=case),
        "payable_review_form": PayableReviewForm(case=case),
        "payable_allocation_add_form": PayableAllocationAddForm(case=case),
        "payable_allocation_revision_form": PayableAllocationRevisionForm(case=case),
        "payable_claim_control_form": PayableClaimControlForm(case=case),
        "payable_relationships": relationship_summary,
        "current_print_job": current_print_job,
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
        "prepare-controlled-print": ControlledPrintPrepareForm,
        "record-dv-printed": PrintEvidenceForm,
        "assemble-finance-packet": FinancePacketAssemblyForm,
        "link-tracepoint": TracePointLinkForm,
        "amend-nonfinancial": NonFinancialAmendmentForm,
        "reconcile-obligation": SubmitChecksForm,
        "record-payable-evidence": PayableEvidenceForm,
        "submit-payable": PayableSubmitForm,
        "review-payable": PayableReviewForm,
        "add-payable-allocation": PayableAllocationAddForm,
        "revise-payable-allocation": PayableAllocationRevisionForm,
        "revise-payable-claim": PayableClaimControlForm,
    }
    form_class = forms.get(action)
    if not form_class:
        raise Http404
    form = form_class(request.POST, case=case)
    deduction_formset = _voucher_deduction_formset(case, request.POST) if action == "prepare-dv" else None
    form_valid = form.is_valid()
    deductions_valid = deduction_formset.is_valid() if deduction_formset is not None else True
    if not form_valid or not deductions_valid:
        errors = [f"{field}: {', '.join(values)}" for field, values in form.errors.items()]
        if deduction_formset is not None:
            for index, row in enumerate(deduction_formset.errors, start=1):
                if row:
                    errors.append(
                        f"deduction row {index}: "
                        + "; ".join(f"{field}: {', '.join(values)}" for field, values in row.items())
                    )
            errors.extend(str(value) for value in deduction_formset.non_form_errors())
        messages.error(request, "Correct the action form: " + "; ".join(errors))
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
            review_payable_intake(
                **common, decision=data["decision"], reason=data["reason"],
                recognition_decision=data["recognition_decision"],
                recognition_basis=data["recognition_basis"],
                obligation_adjustment_decision=data["obligation_adjustment_decision"],
                obligation_adjustment_basis=data["obligation_adjustment_basis"],
            )
        elif action == "add-payable-allocation":
            add_payable_obligation_allocation(
                **common, obligation=data["authoritative_obligation"],
                allocation_amount=data["allocation_amount"],
                relationship_type=data["relationship_type"], reason=data["reason"],
            )
        elif action == "revise-payable-allocation":
            revise_payable_obligation_allocation(
                **common, allocation_public_id=data["allocation"],
                revised_amount=data["revised_amount"],
                relationship_type=data["relationship_type"], reason=data["reason"],
            )
        elif action == "revise-payable-claim":
            revise_payable_claim_control(
                **common, claim_amount=data["claim_amount"], reason=data["reason"],
            )
        elif action == "prepare-dv":
            deductions = [
                {
                    "tax_rule_item": row.cleaned_data["tax_rule"],
                    "code": row.cleaned_data["tax_rule"].code,
                    "description": row.cleaned_data["tax_rule"].label,
                    "tax_base": row.cleaned_data.get("tax_base"),
                    "amount": row.cleaned_data["amount"],
                }
                for row in deduction_formset.forms
                if row.cleaned_data.get("tax_rule") and not row.cleaned_data.get("DELETE")
            ]
            prepare_voucher(
                **common, voucher_date=data["voucher_date"], gross_amount=data["gross_amount"], deductions=deductions,
                line_description=data["line_description"], line_account_code=data["line_account_code"], document_codes=data["document_codes"],
            )
        elif action == "record-signature":
            record_signature_return(**common, task=data["task"], note=data["note"])
        elif action == "validate-accounting":
            validate_accounting(**common, jev_number=data["jev_number"], jev_date=data["jev_date"], note=data["note"])
        elif action == "issue-check":
            issue_check(
                **common, bank_account_code=data["bank_account_code"], fund_code=data["fund_code"],
                check_number=data["check_number"], amount=data["amount"], replaces=data["replaces"],
            )
        elif action == "submit-checks":
            submit_checks_for_advice(**common)
        elif action == "finalize-advice":
            finalize_bank_advice(
                **common, advice_number=data["advice_number"], advice_date=data["advice_date"],
                preparation_note=data["preparation_note"], authority_reference=data["authority_reference"],
                local_applicability_note=data["local_applicability_note"],
            )
        elif action == "release-check":
            release_check(**common, instrument=data["instrument"], claimant=data["claimant"], receipt_reference=data["receipt_reference"])
        elif action == "return":
            return_case(**common, target_stage=data["target_stage"], reason=data["reason"])
        elif action == "cancel-check":
            cancel_check(**common, instrument=data["instrument"], reason=data["reason"])
        elif action == "generate-dv":
            generate_shadow_dv(case=case, actor=request.user, idempotency_key=data["idempotency_key"])
        elif action == "prepare-controlled-print":
            prepare_controlled_dv_print(
                **common,
                replacement_reason=data["replacement_reason"],
            )
        elif action == "record-dv-printed":
            record_dv_printed(
                **common,
                copy_count=data["copy_count"],
                printer_or_form_stock=data["printer_or_form_stock"],
                print_note=data["print_note"],
            )
        elif action == "assemble-finance-packet":
            assemble_finance_packet(
                **common,
                expected_document_count=data["expected_document_count"],
                expected_page_count=data["expected_page_count"],
                confidentiality=data["confidentiality"],
                assembly_note=data["assembly_note"],
            )
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


@voucher_access_required
def transaction_export(request, public_id):
    case = _case(public_id)
    if not has_explicit_permission(request.user, "vouchers.view_voucher_audit"):
        raise PermissionDenied
    summary = payable_relationship_summary(case) if hasattr(case, "payable_intake") else {
        "allocations": [], "allocated_total": "0.00", "difference": "0.00",
    }
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow((
        "section", "case_reference", "case_public_id", "stage", "requesting_office",
        "transaction_type", "payee", "claim_reference", "claim_amount", "allocated_total",
        "control_difference", "obligation_number", "obligation_public_id", "relationship_type",
        "allocation_amount", "obligation_amount_snapshot", "obligation_checksum_snapshot",
        "allocation_version", "recognition_decision", "recognition_basis",
        "obligation_adjustment_decision", "obligation_adjustment_basis", "evidence_code",
        "evidence_status", "evidence_reference", "authority_reference",
        "deduction_code", "deduction_amount", "tax_base", "tax_atc", "tax_rate_percent",
        "tax_return_form", "tax_certificate_form", "tax_rule_checksum", "tax_evidence_checksum",
    ))
    intake = getattr(case, "payable_intake", None)
    base = (
        case.reference_code, case.public_id, case.current_stage, case.requesting_department.name,
        case.transaction_type, case.payee_name,
        intake.claim_reference if intake else "", intake.claim_amount if intake else "",
        summary["allocated_total"], summary["difference"],
    )
    for allocation in summary["allocations"]:
        writer.writerow((
            "obligation_allocation", *base,
            allocation.obligation.obligation_number, allocation.obligation.public_id,
            allocation.relationship_type, allocation.allocated_amount,
            allocation.obligation_amount_snapshot, allocation.obligation_checksum_snapshot,
            allocation.version,
            intake.recognition_decision if intake else "", intake.recognition_basis if intake else "",
            intake.obligation_adjustment_decision if intake else "",
            intake.obligation_adjustment_basis if intake else "", "", "", "", "",
            "", "", "", "", "", "", "", "", "",
        ))
    if intake:
        for evidence in case.payable_document_evidence.all():
            writer.writerow((
                "documentary_evidence", *base,
                "", "", "", "", "", "", "",
                intake.recognition_decision, intake.recognition_basis,
                intake.obligation_adjustment_decision, intake.obligation_adjustment_basis,
                evidence.requirement_code, evidence.status, evidence.evidence_reference,
                evidence.authority_reference,
                "", "", "", "", "", "", "", "", "",
            ))
    if hasattr(case, "disbursement_voucher"):
        for deduction in case.disbursement_voucher.deductions.order_by("pk"):
            tax = deduction.tax_rule_snapshot or {}
            writer.writerow((
                "deduction_tax_evidence", *base,
                "", "", "", "", "", "", "",
                intake.recognition_decision if intake else "", intake.recognition_basis if intake else "",
                intake.obligation_adjustment_decision if intake else "",
                intake.obligation_adjustment_basis if intake else "",
                "", "", "", tax.get("authority_reference", ""),
                deduction.code, deduction.amount, deduction.tax_base or "", tax.get("atc", ""),
                tax.get("rate_percent", ""), tax.get("return_form_code", ""),
                tax.get("certificate_form_code", ""), deduction.tax_rule_checksum,
                deduction.tax_evidence_checksum,
            ))
    filename = f"{slugify(case.reference_code)}-payable-transaction.csv"
    archived = archive_export(
        content=response.content,
        department=case.requesting_department,
        user=request.user,
        category="finance-payable-transactions",
        filename=filename,
        metadata={
            "kind": "payable_transaction_relationship_export",
            "case_public_id": str(case.public_id),
            "case_reference": case.reference_code,
            "stage": case.current_stage,
            "state_version": case.state_version,
            "claim_amount": str(intake.claim_amount) if intake else "",
            "allocated_total": str(summary["allocated_total"]),
            "control_difference": str(summary["difference"]),
            "official_status": "controlled transaction export; not automatically an official COA/DBM/local form",
        },
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    return response


@voucher_access_required
def payment_register_export(request, public_id):
    case = _case(public_id)
    if not has_explicit_permission(request.user, "vouchers.view_voucher_audit"):
        raise PermissionDenied
    from .access import department_for_user

    request_by_trigger = {}
    for posting in case.posting_requests.all():
        parts = posting.trigger_key.split(":")
        if not posting.trigger_key.startswith("payment-instrument:") or len(parts) < 3:
            continue
        key = (posting.kind, parts[1])
        current = request_by_trigger.get(key)
        if current is None or posting.version > current.version:
            request_by_trigger[key] = posting
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "case_reference", "case_public_id", "dv_number", "requesting_office",
        "transaction_type", "payee", "instrument_public_id", "bank_account_code", "check_number",
        "amount", "status", "issued_at", "issued_by", "replaces_instrument_public_id",
        "replaces_check_number", "advice_number", "advice_date", "released_at", "released_by",
        "released_to", "receipt_reference", "cancelled_at", "cancelled_by", "cancellation_reason",
        "payment_accounting_effect", "payment_jev_number", "payment_posting_status",
        "cancellation_accounting_effect", "cancellation_jev_number", "cancellation_posting_status",
        "replacement_accounting_effect", "replacement_jev_number", "replacement_posting_status",
    ))
    for instrument in case.payment_instruments.select_related(
        "issued_by", "released_by", "cancelled_by", "replaces", "current_advice_batch",
    ).order_by("issued_at", "pk"):
        requests = {
            kind: request_by_trigger.get((kind, str(instrument.public_id)))
            for kind in (
                VoucherPostingRequest.PAYMENT,
                VoucherPostingRequest.CANCELLATION,
                VoucherPostingRequest.REPLACEMENT,
            )
        }

        def posting_value(kind, key):
            posting = requests[kind]
            if posting is None:
                return ""
            if key == "effect":
                return posting.posting_rule_snapshot.get("accounting_effect_label", "")
            if key == "number":
                return posting.jev_number or ""
            return posting.get_status_display()

        advice = instrument.current_advice_batch
        writer.writerow((
            "payment_instrument_register", _csv_safe(case.reference_code), case.public_id,
            _csv_safe(case.disbursement_voucher.dv_number), _csv_safe(case.requesting_department.name),
            _csv_safe(case.transaction_type), _csv_safe(case.payee_name), instrument.public_id,
            _csv_safe(instrument.bank_account_code), _csv_safe(instrument.check_number), instrument.amount,
            instrument.get_status_display(), instrument.issued_at.isoformat(),
            _csv_safe(instrument.issued_by.get_full_name() or instrument.issued_by.username),
            instrument.replaces.public_id if instrument.replaces_id else "",
            _csv_safe(instrument.replaces.check_number if instrument.replaces_id else ""),
            _csv_safe(advice.advice_number if advice else ""), advice.advice_date if advice else "",
            instrument.released_at.isoformat() if instrument.released_at else "",
            _csv_safe(
                instrument.released_by.get_full_name() or instrument.released_by.username
                if instrument.released_by_id else ""
            ),
            _csv_safe(instrument.released_to), _csv_safe(instrument.receipt_reference),
            instrument.cancelled_at.isoformat() if instrument.cancelled_at else "",
            _csv_safe(
                instrument.cancelled_by.get_full_name() or instrument.cancelled_by.username
                if instrument.cancelled_by_id else ""
            ),
            _csv_safe(instrument.cancellation_reason),
            posting_value(VoucherPostingRequest.PAYMENT, "effect"),
            posting_value(VoucherPostingRequest.PAYMENT, "number"),
            posting_value(VoucherPostingRequest.PAYMENT, "status"),
            posting_value(VoucherPostingRequest.CANCELLATION, "effect"),
            posting_value(VoucherPostingRequest.CANCELLATION, "number"),
            posting_value(VoucherPostingRequest.CANCELLATION, "status"),
            posting_value(VoucherPostingRequest.REPLACEMENT, "effect"),
            posting_value(VoucherPostingRequest.REPLACEMENT, "number"),
            posting_value(VoucherPostingRequest.REPLACEMENT, "status"),
        ))
    filename = f"{slugify(case.reference_code)}-payment-register.csv"
    export_department = department_for_user(request.user)
    archived = archive_export(
        content=response.content,
        department=export_department,
        user=request.user,
        category="finance-payment-registers",
        filename=filename,
        metadata={
            "kind": "payment_instrument_register_export",
            "case_public_id": str(case.public_id),
            "case_reference": case.reference_code,
            "state_version": case.state_version,
            "row_count": case.payment_instruments.count(),
            "official_status": "controlled data interchange; not automatically an official COA/local form",
        },
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    return response
