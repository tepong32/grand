from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from .access import (
    can_authorize_finance_cutover, can_manage_shadow_operation, can_review_shadow_reconciliation,
    can_approve_finance_configuration, can_manage_finance_configuration,
    can_manage_finance_templates, can_view_shadow_cycle, department_for_user, finance_access_required,
    finance_permission_required, shadow_access_required,
)
from .cutover_services import (
    build_cutover_evidence_package, cutover_readiness, decide_cutover,
    decide_stakeholder_acceptance, record_cutover_rollback, review_shadow_cycle,
    review_shadow_source_drift, stage_shadow_external_lock, stage_shadow_source_csv,
    open_next_reconciliation_run, record_shadow_defect_escalation,
    register_shadow_defect, review_reconciliation_plan, review_reconciliation_run,
    review_shadow_defect_resolution, start_shadow_cycle, submit_cutover_decision,
    submit_reconciliation_plan, submit_reconciliation_run, submit_shadow_cycle,
    submit_shadow_defect_resolution,
)
from .forms import (
    FinanceCutoverDecisionForm,
    FinanceDocumentRuleForm, FinanceItemForm, FinanceNumberingSequenceForm, FinanceReleaseForm,
    FinancePartyClaimantForm, FinancePartyForm, FinancePostingRuleForm, FinancePostingRuleLineForm,
    FinanceShadowComparisonForm, FinanceShadowCycleForm, FinanceShadowDriftReviewForm,
    FinanceShadowDefectForm, FinanceShadowDefectResolutionForm, FinanceShadowExternalLockForm,
    FinanceShadowReconciliationPlanForm, FinanceShadowSourceUploadForm, FinanceSignatoryForm,
    FinanceStakeholderAcceptanceForm, FinanceStakeholderDecisionForm,
    FinanceTemplateForm, FinanceStarterTemplateForm, FinanceTransactionVariantForm,
)
from .models import (
    FinanceConfigurationRelease, FinanceCutoverDecision, FinanceParty, FinanceShadowCycle,
    FinanceShadowDefect, FinanceShadowReconciliationPlan, FinanceShadowReconciliationRun,
    FinanceShadowSourceVersion,
    FinanceStakeholderAcceptance, FinanceTemplateVersion, FinanceTransactionVariant,
)
from .services import (
    FinanceTemplateError, build_finance_starter_workbook, create_payment_event_posting_starters,
    create_recognition_posting_starter, evaluate_readiness, preflight_finance_template,
    record_event, synthetic_preview, transition_release,
)


@finance_access_required
def workspace(request):
    department = department_for_user(request.user)
    releases = FinanceConfigurationRelease.objects.filter(department=department).prefetch_related("items", "templates", "signatories", "numbering_sequences", "parties")
    active = releases.filter(status="active").first()
    readiness = evaluate_readiness(active) if active else None
    return render(request, "finance/workspace.html", {
        "department": department, "releases": releases, "active_release": active, "readiness": readiness,
        "can_manage": can_manage_finance_configuration(request.user, department),
        "can_approve": can_approve_finance_configuration(request.user, department),
        "can_manage_templates": can_manage_finance_templates(request.user, department),
    })


@finance_permission_required(can_manage_finance_configuration)
def release_create(request):
    department = department_for_user(request.user)
    form = FinanceReleaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        release = form.save(False)
        release.department, release.created_by = department, request.user
        release.full_clean()
        release.save()
        record_event(release, request.user, "created")
        messages.success(request, "Draft finance configuration release created.")
        return redirect("finance:release_detail", pk=release.pk)
    return render(request, "finance/form.html", {"form": form, "title": "Create finance configuration release", "guidance": "A release groups reviewed master data, rules, signatories, numbering, and workbook versions for one effective period."})


@finance_access_required
def release_detail(request, pk):
    department = department_for_user(request.user)
    release = get_object_or_404(FinanceConfigurationRelease.objects.prefetch_related(
        "items", "templates", "signatories", "numbering_sequences", "parties__authorized_claimants",
        "transaction_variants__document_rules", "transaction_variants__posting_rules__lines", "events__actor",
    ), pk=pk, department=department)
    return render(request, "finance/release_detail.html", {
        "release": release, "readiness": evaluate_readiness(release),
        "today": timezone.localdate(),
        "can_manage": can_manage_finance_configuration(request.user, department),
        "can_approve": can_approve_finance_configuration(request.user, department),
        "can_manage_templates": can_manage_finance_templates(request.user, department),
    })


@finance_permission_required(can_manage_finance_configuration)
def item_create(request):
    department = department_for_user(request.user)
    initial = {"release": request.GET.get("release")}
    form = FinanceItemForm(request.POST or None, department=department, initial=initial)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department, item.created_by = department, request.user
        item.full_clean()
        item.save()
        record_event(item, request.user, "created")
        messages.success(request, "Draft finance master-data version created.")
        return redirect("finance:release_detail", pk=item.release_id)
    return render(request, "finance/form.html", {"form": form, "title": "Add finance configuration", "guidance": "Use synthetic examples only until local Accounting reviews the release. Existing approved versions are never overwritten."})


@finance_permission_required(can_manage_finance_configuration)
def variant_create(request):
    department = department_for_user(request.user)
    form = FinanceTransactionVariantForm(
        request.POST or None, department=department, initial={"release": request.GET.get("release")},
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department, item.created_by = department, request.user
        item.full_clean(); item.save(); record_event(item, request.user, "created")
        messages.success(request, "Draft transaction variant created. Add its reviewed document rules before submission.")
        return redirect("finance:release_detail", pk=item.release_id)
    return render(request, "finance/form.html", {
        "form": form, "title": "Add governed transaction variant",
        "guidance": "Configure each locally approved variant separately. A public COA/DBM source is evidence to review, not automatic proof that the exact local route or form has been accepted.",
    })


@finance_permission_required(can_manage_finance_configuration)
def document_rule_create(request):
    department = department_for_user(request.user)
    form = FinanceDocumentRuleForm(
        request.POST or None, department=department, initial={"variant": request.GET.get("variant")},
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.created_by = request.user
        item.full_clean(); item.save(); record_event(item, request.user, "document_rule_created")
        messages.success(request, "Draft transaction-specific document rule created.")
        return redirect("finance:release_detail", pk=item.variant.release_id)
    return render(request, "finance/form.html", {
        "form": form, "title": "Add transaction document rule",
        "guidance": "State whether the evidence is required, conditional, or waivable and cite the reviewed authority. Do not upload sensitive source documents into setup.",
    })


@finance_permission_required(can_manage_finance_configuration)
def posting_rule_create(request):
    department = department_for_user(request.user)
    form = FinancePostingRuleForm(
        request.POST or None, department=department, initial={"variant": request.GET.get("variant")},
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.created_by = request.user
        item.full_clean(); item.save(); record_event(item, request.user, "posting_rule_created")
        messages.success(request, "Draft posting rule created. Add both debit and credit instructions before review.")
        return redirect("finance:release_detail", pk=item.variant.release_id)
    return render(request, "finance/form.html", {
        "form": form, "title": "Add transaction posting rule",
        "guidance": (
            "Describe the accounting event in ordinary office language, choose when it is recognized, and cite the "
            "locally reviewed basis. The debit and credit instructions are added on the next screen."
        ),
    })


@finance_permission_required(can_manage_finance_configuration)
def posting_rule_line_create(request):
    department = department_for_user(request.user)
    form = FinancePostingRuleLineForm(
        request.POST or None, department=department, initial={"rule": request.GET.get("rule")},
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.full_clean(); item.save(); record_event(item.rule, request.user, "posting_rule_line_created")
        messages.success(request, "Debit or credit instruction added to the draft posting rule.")
        return redirect("finance:release_detail", pk=item.rule.variant.release_id)
    return render(request, "finance/form.html", {
        "form": form, "title": "Add debit or credit instruction",
        "guidance": (
            "Choose where the account and amount come from. Use a fixed account only after Accounting confirms the "
            "exact local chart-of-accounts code."
        ),
    })


@finance_permission_required(can_manage_finance_configuration)
def posting_rule_starter(request, variant_pk):
    if request.method != "POST":
        raise Http404
    department = department_for_user(request.user)
    variant = get_object_or_404(
        FinanceTransactionVariant.objects.select_related("release", "department"),
        pk=variant_pk, department=department,
    )
    try:
        create_recognition_posting_starter(variant, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(
            request,
            "Editable recognition starter added. Review its timing, accounts, wording, and authority before submission.",
        )
    return redirect("finance:release_detail", pk=variant.release_id)


@finance_permission_required(can_manage_finance_configuration)
def payment_posting_starters(request, variant_pk):
    if request.method != "POST":
        raise Http404
    department = department_for_user(request.user)
    variant = get_object_or_404(
        FinanceTransactionVariant.objects.select_related("release", "department"),
        pk=variant_pk,
        department=department,
    )
    try:
        created = create_payment_event_posting_starters(variant, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(
            request,
            f"{len(created)} editable payment-cycle starter rule(s) added. Replace every warning with the reviewed local treatment before submission.",
        )
    return redirect("finance:release_detail", pk=variant.release_id)


@finance_permission_required(can_manage_finance_configuration)
def signatory_create(request):
    department = department_for_user(request.user)
    form = FinanceSignatoryForm(request.POST or None, department=department, initial={"release": request.GET.get("release")})
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department, item.created_by = department, request.user
        item.full_clean(); item.save(); record_event(item, request.user, "created")
        messages.success(request, "Draft signatory assignment created.")
        return redirect("finance:release_detail", pk=item.release_id)
    return render(request, "finance/form.html", {"form": form, "title": "Add signatory assignment", "guidance": "Record the role, acting status, and exact validity period. Signature images are intentionally not collected."})


@finance_permission_required(can_manage_finance_configuration)
def sequence_create(request):
    department = department_for_user(request.user)
    form = FinanceNumberingSequenceForm(request.POST or None, department=department, initial={"release": request.GET.get("release")})
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department, item.created_by = department, request.user
        item.full_clean(); item.save(); record_event(item, request.user, "created")
        messages.success(request, "Draft numbering sequence created. No number is consumed during setup.")
        return redirect("finance:release_detail", pk=item.release_id)
    return render(request, "finance/form.html", {"form": form, "title": "Add numbering sequence", "guidance": "Sequences are scoped by fiscal year and document type. This setup phase never issues an official voucher number."})


@finance_permission_required(can_manage_finance_configuration)
def party_create(request):
    department = department_for_user(request.user)
    form = FinancePartyForm(request.POST or None, department=department, initial={"release": request.GET.get("release")})
    if request.method == "POST" and form.is_valid():
        party = form.save(False)
        party.department, party.created_by = department, request.user
        party.full_clean(); party.save(); record_event(party, request.user, "created")
        messages.success(request, "Draft supplier/payee version created.")
        return redirect("finance:release_detail", pk=party.release_id)
    return render(request, "finance/form.html", {"form": form, "title": "Add supplier or payee", "guidance": "Maintain a reviewed selectable party. Do not store bank credentials or unnecessary identity-document numbers."})


@finance_permission_required(can_manage_finance_configuration)
def claimant_create(request, party_pk):
    department = department_for_user(request.user)
    party = get_object_or_404(FinanceParty, pk=party_pk, department=department, status="draft")
    form = FinancePartyClaimantForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        claimant = form.save(False)
        claimant.party, claimant.created_by = party, request.user
        claimant.full_clean(); claimant.save(); record_event(party, request.user, "claimant_added", claimant.display_name)
        messages.success(request, "Authorized check claimant added to the draft party.")
        return redirect("finance:release_detail", pk=party.release_id)
    return render(request, "finance/form.html", {"form": form, "title": f"Add authorized claimant — {party.display_name}", "guidance": "Record a selectable claimant name and validity period; do not copy identity-document numbers into this label."})


@finance_permission_required(can_manage_finance_templates)
def template_create(request):
    department = department_for_user(request.user)
    form = FinanceTemplateForm(request.POST or None, request.FILES or None, department=department, initial={"release": request.GET.get("release")})
    if request.method == "POST" and form.is_valid():
        template = form.save(False)
        template.department, template.created_by = department, request.user
        template.full_clean(); template.save(); record_event(template, request.user, "uploaded")
        messages.success(request, "Workbook version uploaded. Run preflight before review.")
        return redirect("finance:release_detail", pk=template.release_id)
    return render(request, "finance/form.html", {"form": form, "title": "Upload finance workbook version", "multipart": True, "guidance": "Only macro-free .xlsx files are accepted. External links and suspicious formulas are rejected during preflight."})


@finance_permission_required(can_manage_finance_templates)
def starter_template(request):
    department = department_for_user(request.user)
    form = FinanceStarterTemplateForm(
        request.POST or None,
        initial={"lgu_name": department.name, "finance_office_name": department.name},
    )
    if request.method == "POST" and form.is_valid():
        payload = build_finance_starter_workbook(form.cleaned_data)
        filename = f"{slugify(form.cleaned_data['lgu_name']) or 'lgu'}-editable-dv-starter.xlsx"
        response = HttpResponse(
            payload,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-GRAND-Template-Status"] = "editable-starter-not-locally-accepted"
        return response
    return render(request, "finance/form.html", {
        "form": form,
        "title": "Build an editable DV starter",
        "guidance": (
            "Use familiar wording and simple print settings. GRAND creates a macro-free workbook that ordinary staff can "
            "adjust in Excel, then upload as a draft for preflight and side-by-side local review."
        ),
    })


@finance_permission_required(can_manage_finance_templates)
def template_preflight(request, pk):
    if request.method != "POST":
        raise Http404
    department = department_for_user(request.user)
    template = get_object_or_404(FinanceTemplateVersion, pk=pk, department=department)
    try:
        result = preflight_finance_template(template, request.user)
    except (FinanceTemplateError, ValidationError) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, result["message"])
    return redirect("finance:release_detail", pk=template.release_id)


@finance_access_required
def template_download(request, pk):
    department = department_for_user(request.user)
    template = get_object_or_404(FinanceTemplateVersion, pk=pk, department=department)
    template.workbook.open("rb")
    return FileResponse(template.workbook, as_attachment=True, filename=template.workbook.name.rsplit("/", 1)[-1])


@finance_access_required
def template_preview(request, pk):
    department = department_for_user(request.user)
    template = get_object_or_404(FinanceTemplateVersion, pk=pk, department=department)
    try:
        payload = synthetic_preview(template, request.user)
    except FinanceTemplateError as exc:
        messages.error(request, str(exc))
        return redirect("finance:release_detail", pk=template.release_id)
    response = HttpResponse(payload, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="synthetic-{template.document_type}-v{template.version}.xlsx"'
    response["X-GRAND-Preview"] = "synthetic-only"
    return response


@finance_access_required
def release_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    department = department_for_user(request.user)
    release = get_object_or_404(FinanceConfigurationRelease, pk=pk, department=department)
    try:
        transition_release(release, action, request.user, request.POST.get("reason", ""))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, f"Release {action} recorded in the immutable finance audit history.")
    return redirect("finance:release_detail", pk=release.pk)


def _visible_shadow_cycles(user):
    department = department_for_user(user)
    query = Q(stakeholder_acceptances__assigned_reviewer=user)
    if department:
        query |= Q(department=department)
    return FinanceShadowCycle.objects.filter(query).select_related(
        "department", "created_by", "submitted_by", "reconciled_by",
    ).prefetch_related("stakeholder_acceptances").distinct()


def _shadow_cycle_for_user(user, pk):
    cycle = get_object_or_404(_visible_shadow_cycles(user), pk=pk)
    if not can_view_shadow_cycle(user, cycle):
        raise PermissionDenied
    return cycle


@shadow_access_required
def shadow_workspace(request):
    department = department_for_user(request.user)
    cycles = _visible_shadow_cycles(request.user)
    return render(request, "finance/shadow_workspace.html", {
        "cycles": cycles,
        "department": department,
        "can_manage": can_manage_shadow_operation(request.user, department),
    })


@finance_permission_required(can_manage_shadow_operation)
def shadow_cycle_create(request):
    department = department_for_user(request.user)
    form = FinanceShadowCycleForm(request.POST or None, department=department)
    if request.method == "POST" and form.is_valid():
        cycle = form.save(False)
        cycle.department, cycle.created_by = department, request.user
        cycle.full_clean(); cycle.save()
        FinanceAuditEvent.objects.create(
            department=department, target_type="financeshadowcycle", target_id=str(cycle.pk),
            action="shadow_cycle_created", actor=request.user,
            snapshot={"cycle_public_id": str(cycle.public_id), "status": cycle.status, "enabled_scope": cycle.enabled_scope},
        )
        messages.success(request, "Draft shadow-cycle plan created. No official authority changed.")
        return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": "Plan a shadow or parallel cycle",
        "guidance": "State the limited scope and where the official/redacted comparison source is retained. After saving, GRAND can calculate the file and column-layout locks from a redacted CSV; this record does not make GRAND authoritative.",
    })


@shadow_access_required
def shadow_cycle_detail(request, pk):
    cycle = _shadow_cycle_for_user(request.user, pk)
    try:
        decision = cycle.cutover_decision
    except FinanceCutoverDecision.DoesNotExist:
        decision = None
    try:
        plan = cycle.reconciliation_plan
    except FinanceShadowReconciliationPlan.DoesNotExist:
        plan = None
    department = cycle.department
    return render(request, "finance/shadow_cycle_detail.html", {
        "cycle": cycle,
        "source_versions": cycle.source_versions.select_related("staged_by", "reviewed_by"),
        "reconciliation_plan": plan,
        "reconciliation_runs": cycle.reconciliation_runs.select_related("prepared_by", "submitted_by", "reviewed_by"),
        "defects": cycle.defects.select_related("comparison", "owner", "resolution_submitted_by", "resolved_by"),
        "comparisons": cycle.comparisons.select_related("defect_owner", "created_by"),
        "acceptances": cycle.stakeholder_acceptances.select_related("office", "assigned_reviewer", "decided_by"),
        "decision": decision,
        "readiness": cutover_readiness(cycle),
        "can_manage": can_manage_shadow_operation(request.user, department),
        "can_review": can_review_shadow_reconciliation(request.user, department),
        "can_authorize": can_authorize_finance_cutover(request.user, department),
        "is_assigned_reviewer": cycle.stakeholder_acceptances.filter(assigned_reviewer=request.user, decision=FinanceStakeholderAcceptance.PENDING).exists(),
    })


@finance_permission_required(can_manage_shadow_operation)
def shadow_reconciliation_plan(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    try:
        plan = cycle.reconciliation_plan
    except FinanceShadowReconciliationPlan.DoesNotExist:
        plan = None
    if plan and plan.status not in {FinanceShadowReconciliationPlan.DRAFT, FinanceShadowReconciliationPlan.RETURNED}:
        return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    form = FinanceShadowReconciliationPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.cycle = cycle
        if not item.pk:
            item.created_by = request.user
        try:
            item.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft local cadence and escalation plan saved. Submit it for independent review before starting the cycle.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Local reconciliation plan — {cycle.code}", "cycle": cycle,
        "guidance": "Enter the actual locally accepted cadence, minimum run count, correction targets, and named escalation routes. The suggested numbers are editable planning defaults—not COA, DBM, or local requirements.",
    })


@shadow_access_required
def shadow_reconciliation_plan_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    plan = get_object_or_404(FinanceShadowReconciliationPlan.objects.select_related("cycle", "cycle__department"), pk=pk)
    if not can_view_shadow_cycle(request.user, plan.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "submit":
            submit_reconciliation_plan(plan, request.user)
        elif action == "approve":
            review_reconciliation_plan(plan, request.user, approve=True, reason=reason)
        elif action == "return":
            review_reconciliation_plan(plan, request.user, approve=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The reconciliation-plan action is retained in Finance audit history.")
    return redirect("finance:shadow_cycle_detail", pk=plan.cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def shadow_reconciliation_run_open(request, cycle_pk):
    if request.method != "POST":
        raise Http404
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    try:
        open_next_reconciliation_run(cycle, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The next scheduled reconciliation run is open against the current controls.")
    return redirect("finance:shadow_cycle_detail", pk=cycle.pk)


@shadow_access_required
def shadow_reconciliation_run_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    run = get_object_or_404(FinanceShadowReconciliationRun.objects.select_related("cycle", "cycle__department"), pk=pk)
    if not can_view_shadow_cycle(request.user, run.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "submit":
            submit_reconciliation_run(run, request.user)
        elif action == "accept":
            review_reconciliation_run(run, request.user, accept=True, reason=reason)
        elif action == "return":
            review_reconciliation_run(run, request.user, accept=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The scheduled reconciliation action is checksummed and retained.")
    return redirect("finance:shadow_cycle_detail", pk=run.cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def shadow_defect_create(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    form = FinanceShadowDefectForm(request.POST or None, cycle=cycle)
    if request.method == "POST" and form.is_valid():
        try:
            register_shadow_defect(
                form.cleaned_data["comparison"], request.user,
                code=form.cleaned_data["code"], severity=form.cleaned_data["severity"],
                summary=form.cleaned_data["summary"], impact=form.cleaned_data["impact"],
                owner=form.cleaned_data["owner"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Defect triage recorded with the approved local target and escalation route.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Register comparison defect — {cycle.code}", "cycle": cycle,
        "guidance": "Classify the control impact independently of appearance. GRAND calculates the correction due time and pins the escalation route from the approved local plan.",
    })


@shadow_access_required
def shadow_defect_resolution(request, pk):
    defect = get_object_or_404(FinanceShadowDefect.objects.select_related("cycle", "cycle__department", "owner"), pk=pk)
    if not can_view_shadow_cycle(request.user, defect.cycle):
        raise PermissionDenied
    if request.user.pk != defect.owner_id and not can_manage_shadow_operation(request.user, defect.cycle.department):
        raise PermissionDenied
    form = FinanceShadowDefectResolutionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            submit_shadow_defect_resolution(
                defect, request.user, note=form.cleaned_data["resolution_note"],
                evidence_reference=form.cleaned_data["evidence_reference"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Correction submitted for independent verification; the defect remains open until accepted.")
            return redirect("finance:shadow_cycle_detail", pk=defect.cycle_id)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Submit correction — {defect.code}", "cycle": defect.cycle,
        "guidance": "Describe the completed correction and point to retained verification evidence. Submission alone does not close the defect.",
    })


@shadow_access_required
def shadow_defect_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    defect = get_object_or_404(FinanceShadowDefect.objects.select_related("cycle", "cycle__department"), pk=pk)
    if not can_view_shadow_cycle(request.user, defect.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "accept":
            review_shadow_defect_resolution(defect, request.user, accept=True, reason=reason)
        elif action == "return":
            review_shadow_defect_resolution(defect, request.user, accept=False, reason=reason)
        elif action == "escalate":
            record_shadow_defect_escalation(defect, request.user, note=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The defect action is retained without rewriting its intake evidence.")
    return redirect("finance:shadow_cycle_detail", pk=defect.cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def shadow_source_upload(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    form = FinanceShadowSourceUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            stage_shadow_source_csv(
                cycle, request.user, form.cleaned_data["source_file"],
                redaction_confirmed=form.cleaned_data["redaction_confirmed"],
                redaction_note=form.cleaned_data["redaction_note"],
                change_reason=form.cleaned_data["change_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Redacted source version retained. GRAND calculated its file lock, column-layout lock, and row count.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Stage redacted source — {cycle.code}", "cycle": cycle,
        "guidance": "Use a comparison copy only. GRAND retains prior versions and flags changed headings for an independent decision before the pilot can start.",
        "multipart": True,
    })


@finance_permission_required(can_manage_shadow_operation)
def shadow_external_lock(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    form = FinanceShadowExternalLockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            stage_shadow_external_lock(
                cycle, request.user,
                source_checksum=form.cleaned_data["source_checksum"],
                schema_signature=form.cleaned_data["schema_signature"],
                redaction_confirmed=form.cleaned_data["redaction_confirmed"],
                redaction_note=form.cleaned_data["redaction_note"],
                change_reason=form.cleaned_data["change_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "External source lock retained as a versioned record.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Record external source lock — {cycle.code}", "cycle": cycle,
        "guidance": "Use this advanced path only when an approved external custody process calculates both locks. No source file is uploaded to GRAND.",
    })


@shadow_access_required
def shadow_source_drift_review(request, pk):
    source = get_object_or_404(
        FinanceShadowSourceVersion.objects.select_related("cycle", "cycle__department", "staged_by"), pk=pk,
    )
    if not can_view_shadow_cycle(request.user, source.cycle):
        raise PermissionDenied
    if not can_review_shadow_reconciliation(request.user, source.cycle.department):
        raise PermissionDenied
    form = FinanceShadowDriftReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        decision = request.POST.get("decision")
        if decision not in {"accept", "reject"}:
            form.add_error(None, "Choose accept or reject.")
        else:
            try:
                review_shadow_source_drift(
                    source, request.user, accept=decision == "accept", reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "The independent column-layout decision is retained in the cycle history.")
                return redirect("finance:shadow_cycle_detail", pk=source.cycle_id)
    return render(request, "finance/source_drift_review.html", {"form": form, "source": source, "cycle": source.cycle})


@finance_permission_required(can_manage_shadow_operation)
def shadow_comparison_create(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    form = FinanceShadowComparisonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        comparison = form.save(False)
        comparison.cycle, comparison.created_by = cycle, request.user
        try:
            comparison.full_clean(); comparison.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Comparison control added with its exact difference and evidence reference.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Add comparison — {cycle.code}",
        "guidance": "Compare the same case, batch, period, register, ledger, or report on both sides. Zero differences may be marked matched; every non-zero difference needs a visible explanation or defect owner.",
        "cycle": cycle,
    })


@finance_permission_required(can_manage_shadow_operation)
def stakeholder_acceptance_create(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    form = FinanceStakeholderAcceptanceForm(request.POST or None, initial={"enabled_scope": cycle.enabled_scope})
    if request.method == "POST" and form.is_valid():
        acceptance = form.save(False)
        acceptance.cycle, acceptance.created_by = cycle, request.user
        try:
            acceptance.full_clean(); acceptance.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Named stakeholder acceptance assigned. Only that reviewer can record the decision.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Assign stakeholder acceptance — {cycle.code}",
        "guidance": "Name the actual reviewer and repeat the exact enabled scope. Training completion and UAT acceptance remain separate evidence.",
        "cycle": cycle,
    })


@shadow_access_required
def stakeholder_acceptance_decide(request, pk):
    acceptance = get_object_or_404(
        FinanceStakeholderAcceptance.objects.select_related("cycle", "cycle__department"),
        pk=pk, assigned_reviewer=request.user,
    )
    form = FinanceStakeholderDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            decide_stakeholder_acceptance(
                acceptance, request.user,
                decision=form.cleaned_data["decision"],
                training_reference=form.cleaned_data["training_evidence_reference"],
                uat_reference=form.cleaned_data["uat_evidence_reference"],
                reason=form.cleaned_data["conditions_or_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Your stakeholder decision is recorded and cannot be overwritten.")
            return redirect("finance:shadow_cycle_detail", pk=acceptance.cycle_id)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Record {acceptance.get_stakeholder_kind_display()} decision",
        "guidance": "Review only the stated scope. Personal Internal How-To progress is private learning support—not proof of readiness or acceptance.",
        "cycle": acceptance.cycle,
    })


@finance_permission_required(can_manage_shadow_operation)
def cutover_decision_create(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    if hasattr(cycle, "cutover_decision"):
        return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    form = FinanceCutoverDecisionForm(request.POST or None, initial={"enabled_scope": cycle.enabled_scope})
    if request.method == "POST" and form.is_valid():
        decision = form.save(False)
        decision.cycle, decision.prepared_by = cycle, request.user
        try:
            decision.full_clean(); decision.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft cutover decision record created. GRAND remains non-authoritative until separate authorization.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Prepare cutover decision — {cycle.code}",
        "guidance": "Record the exact authority matrix, opening reconciliation, rollback criteria, continuity evidence, and legacy read-only retention plan for the already reconciled scope.",
        "cycle": cycle,
    })


@shadow_access_required
def shadow_cycle_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    cycle = _shadow_cycle_for_user(request.user, pk)
    reason = request.POST.get("reason", "")
    try:
        if action == "start":
            start_shadow_cycle(cycle, request.user)
        elif action == "submit":
            submit_shadow_cycle(cycle, request.user)
        elif action == "reconcile":
            review_shadow_cycle(cycle, request.user, accept=True, reason=reason)
        elif action == "return":
            review_shadow_cycle(cycle, request.user, accept=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, f"Shadow-cycle action '{action}' recorded in append-only history.")
    return redirect("finance:shadow_cycle_detail", pk=cycle.pk)


@shadow_access_required
def cutover_decision_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    decision = get_object_or_404(FinanceCutoverDecision.objects.select_related("cycle", "cycle__department"), pk=pk)
    if not can_view_shadow_cycle(request.user, decision.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "submit":
            submit_cutover_decision(decision, request.user)
        elif action == "authorize":
            decide_cutover(decision, request.user, authorize=True, reason=reason)
        elif action == "decline":
            decide_cutover(decision, request.user, authorize=False, reason=reason)
        elif action == "rollback":
            record_cutover_rollback(decision, request.user, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, f"Cutover action '{action}' recorded without rewriting prior evidence.")
    return redirect("finance:shadow_cycle_detail", pk=decision.cycle_id)


@shadow_access_required
def shadow_cycle_export(request, pk):
    cycle = _shadow_cycle_for_user(request.user, pk)
    content, filename, receipt = build_cutover_evidence_package(cycle, request.user)
    response = HttpResponse(content, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Archive-SHA256"] = receipt["sha256"]
    response["X-GRAND-Archive-Path"] = receipt["relative_path"]
    return response
