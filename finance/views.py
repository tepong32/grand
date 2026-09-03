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
    can_manage_finance_discovery, can_manage_finance_templates,
    can_prepare_finance_discovery_decision, can_review_finance_discovery_decision,
    can_view_finance_discovery_decision, can_view_finance_setup, can_view_shadow_cycle,
    department_for_user, discovery_access_required, finance_access_required,
    finance_permission_required, shadow_access_required,
)
from .cutover_services import (
    build_cutover_evidence_package, cutover_readiness, decide_cutover,
    decide_stakeholder_acceptance, record_cutover_rollback, review_shadow_cycle,
    review_shadow_source_drift, stage_shadow_external_lock, stage_shadow_source_csv,
    open_next_reconciliation_run, record_shadow_defect_escalation,
    register_shadow_defect, review_cutover_readiness_exercise, review_cutover_readiness_plan,
    review_cutover_qualification_evidence, review_cutover_qualification_plan,
    review_reconciliation_plan, review_reconciliation_run,
    review_shadow_defect_resolution, start_shadow_cycle, submit_cutover_decision,
    schedule_cutover_readiness_exercise, submit_cutover_readiness_exercise,
    submit_cutover_qualification_evidence, submit_cutover_qualification_plan,
    submit_cutover_readiness_plan, submit_reconciliation_plan, submit_reconciliation_run, submit_shadow_cycle,
    submit_shadow_defect_resolution,
)
from .acceptance_services import build_field_acceptance_board, export_field_acceptance_board
from .discovery_services import (
    create_discovery_coverage_starters, export_discovery_decision, export_discovery_register,
    review_discovery_decision, submit_discovery_decision,
)
from .forms import (
    FinanceCutoverDecisionForm,
    FinanceDiscoveryCoverageStarterForm, FinanceDiscoveryDecisionForm,
    FinanceDocumentRuleForm, FinanceItemForm,
    FinanceNumberingSequenceForm, FinanceReleaseForm,
    FinancePartyClaimantForm, FinancePartyForm, FinancePostingRuleForm, FinancePostingRuleLineForm,
    FinanceShadowComparisonForm, FinanceShadowCycleForm, FinanceShadowDriftReviewForm,
    FinanceShadowDefectForm, FinanceShadowDefectResolutionForm, FinanceShadowExternalLockForm,
    FinanceCutoverReadinessExerciseForm, FinanceCutoverReadinessExerciseResultForm,
    FinanceRecoveryRehearsalResultForm,
    FinanceCutoverReadinessPlanForm, FinanceShadowReconciliationPlanForm,
    FinanceCutoverQualificationEvidenceForm, FinanceCutoverQualificationFormForm,
    FinanceCutoverQualificationPlanForm,
    FinanceShadowSourceUploadForm, FinanceSignatoryForm,
    FinanceStakeholderAcceptanceForm, FinanceStakeholderDecisionForm,
    FinanceTemplateForm, FinanceStarterTemplateForm, FinanceTaxRuleForm, FinanceTransactionVariantForm,
)
from .models import (
    FinanceAuditEvent, FinanceConfigurationRelease, FinanceCutoverDecision, FinanceCutoverReadinessExercise,
    FinanceCutoverQualificationEvidence, FinanceCutoverQualificationForm,
    FinanceCutoverQualificationPlan,
    FinanceCutoverReadinessPlan, FinanceDiscoveryDecision, FinanceParty,
    FinanceRecoveryRehearsalEvidence, FinanceShadowCycle,
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
def tax_rule_create(request):
    department = department_for_user(request.user)
    form = FinanceTaxRuleForm(
        request.POST or None, department=department, initial={
            "release": request.GET.get("release"),
            "effective_from": timezone.localdate(),
            "applicability_status": "candidate",
            "reporting_basis": "accounting_posting",
            "rounding_mode": "half_up",
            "requires_tax_identifier": True,
        },
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department, item.created_by = department, request.user
        item.full_clean(); item.save(); record_event(item, request.user, "tax_rule_created")
        messages.success(
            request,
            "Structured tax rule added to the draft release. Confirm its current form, ATC, rate, scope, and local basis before release submission.",
        )
        return redirect("finance:release_detail", pk=item.release_id)
    return render(request, "finance/form.html", {
        "form": form,
        "title": "Add governed tax / withholding rule",
        "guidance": (
            "Use the fields your Accounting staff recognize; no JSON is required. Public BIR forms and guidance are review evidence, "
            "not proof that a rate, ATC, deadline, certificate, or filing route applies to this LGU transaction."
        ),
    })


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
    try:
        readiness_plan = cycle.cutover_readiness_plan
    except FinanceCutoverReadinessPlan.DoesNotExist:
        readiness_plan = None
    try:
        qualification_plan = cycle.cutover_qualification_plan
    except FinanceCutoverQualificationPlan.DoesNotExist:
        qualification_plan = None
    department = cycle.department
    return render(request, "finance/shadow_cycle_detail.html", {
        "cycle": cycle,
        "source_versions": cycle.source_versions.select_related("staged_by", "reviewed_by"),
        "reconciliation_plan": plan,
        "cutover_readiness_plan": readiness_plan,
        "cutover_readiness_exercises": cycle.cutover_readiness_exercises.select_related(
            "stakeholder_acceptance", "stakeholder_acceptance__office", "owner", "witness",
            "submitted_by", "reviewed_by", "recovery_rehearsal",
        ),
        "cutover_qualification_plan": qualification_plan,
        "cutover_qualification_forms": (
            qualification_plan.accepted_forms.select_related(
                "local_form", "local_form__department", "local_form__reviewed_by",
            ) if qualification_plan else []
        ),
        "cutover_qualification_evidence": (
            qualification_plan.cycle_evidence.select_related(
                "cycle", "prepared_by", "submitted_by", "reviewed_by",
            ) if qualification_plan else []
        ),
        "reconciliation_runs": cycle.reconciliation_runs.select_related("prepared_by", "submitted_by", "reviewed_by"),
        "defects": cycle.defects.select_related("comparison", "owner", "resolution_submitted_by", "resolved_by"),
        "comparisons": cycle.comparisons.select_related("defect_owner", "created_by"),
        "acceptances": cycle.stakeholder_acceptances.select_related("office", "assigned_reviewer", "decided_by"),
        "decision": decision,
        "readiness": cutover_readiness(cycle),
        "can_manage": can_manage_shadow_operation(request.user, department),
        "can_review": can_review_shadow_reconciliation(request.user, department),
        "can_authorize": can_authorize_finance_cutover(request.user, department),
        "has_passed_recovery_rehearsal": cycle.cutover_readiness_exercises.filter(
            kind=FinanceCutoverReadinessExercise.BACKUP_RESTORE,
            status=FinanceCutoverReadinessExercise.PASSED,
            recovery_rehearsal__isnull=False,
        ).exists(),
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
def cutover_readiness_plan(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    try:
        plan = cycle.cutover_readiness_plan
    except FinanceCutoverReadinessPlan.DoesNotExist:
        plan = None
    if plan and plan.status not in {FinanceCutoverReadinessPlan.DRAFT, FinanceCutoverReadinessPlan.RETURNED}:
        return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    form = FinanceCutoverReadinessPlanForm(
        request.POST or None, instance=plan, department=department,
    )
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
            messages.success(
                request,
                "Draft curriculum, supervisor, and support plan saved. Submit it for independent review before scheduling exercises.",
            )
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Cutover readiness and support plan — {cycle.code}", "cycle": cycle,
        "guidance": (
            "Reference locally accepted, human-readable materials and actual support ownership. "
            "Floating Internal How-To progress stays private and never becomes acceptance or employee-evaluation evidence."
        ),
    })


@shadow_access_required
def cutover_readiness_plan_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    plan = get_object_or_404(
        FinanceCutoverReadinessPlan.objects.select_related("cycle", "cycle__department"), pk=pk,
    )
    if not can_view_shadow_cycle(request.user, plan.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "submit":
            submit_cutover_readiness_plan(plan, request.user)
        elif action == "approve":
            review_cutover_readiness_plan(plan, request.user, approve=True, reason=reason)
        elif action == "return":
            review_cutover_readiness_plan(plan, request.user, approve=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The readiness-plan action is checksummed and retained in Finance audit history.")
    return redirect("finance:shadow_cycle_detail", pk=plan.cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def cutover_qualification_plan(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    try:
        plan = cycle.cutover_qualification_plan
    except FinanceCutoverQualificationPlan.DoesNotExist:
        plan = None
    if plan and plan.status not in {
        FinanceCutoverQualificationPlan.DRAFT, FinanceCutoverQualificationPlan.RETURNED,
    }:
        return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    form = FinanceCutoverQualificationPlanForm(request.POST or None, instance=plan)
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
            messages.success(request, "Draft field-cycle qualification plan saved for independent review.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Field-cycle qualification plan — {cycle.code}", "cycle": cycle,
        "guidance": (
            "Set the locally accepted minimum and whether a controlled parallel run is required. "
            "The starter value of two is editable and is not represented as a COA, DBM, or local rule."
        ),
    })


@shadow_access_required
def cutover_qualification_plan_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    plan = get_object_or_404(
        FinanceCutoverQualificationPlan.objects.select_related("cycle", "cycle__department"), pk=pk,
    )
    if not can_view_shadow_cycle(request.user, plan.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "submit":
            submit_cutover_qualification_plan(plan, request.user)
        elif action == "approve":
            review_cutover_qualification_plan(plan, request.user, approve=True, reason=reason)
        elif action == "return":
            review_cutover_qualification_plan(plan, request.user, approve=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The field-qualification plan action is checksummed and retained.")
    return redirect("finance:shadow_cycle_detail", pk=plan.cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def cutover_qualification_form_create(request, pk):
    department = department_for_user(request.user)
    plan = get_object_or_404(
        FinanceCutoverQualificationPlan.objects.select_related("cycle", "cycle__department"),
        pk=pk, cycle__department=department,
    )
    if plan.status not in {FinanceCutoverQualificationPlan.DRAFT, FinanceCutoverQualificationPlan.RETURNED}:
        messages.error(request, "Accepted forms can be changed only while the qualification plan is editable.")
        return redirect("finance:shadow_cycle_detail", pk=plan.cycle_id)
    form = FinanceCutoverQualificationFormForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.plan = plan
        try:
            item.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Exact accepted form added to the field-qualification plan.")
            return redirect("finance:shadow_cycle_detail", pk=plan.cycle_id)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Add accepted form — {plan.cycle.code}", "cycle": plan.cycle,
        "guidance": (
            "Choose the exact currently accepted F10.2 form version and explain where staff use it. "
            "GRAND will pin its accepted snapshot and checksums when this qualification plan is submitted."
        ),
    })


@finance_permission_required(can_manage_shadow_operation)
def cutover_qualification_form_delete(request, pk, row_pk):
    if request.method != "POST":
        raise Http404
    department = department_for_user(request.user)
    item = get_object_or_404(
        FinanceCutoverQualificationForm.objects.select_related(
            "plan", "plan__cycle", "plan__cycle__department",
        ),
        pk=row_pk, plan_id=pk, plan__cycle__department=department,
    )
    cycle_id = item.plan.cycle_id
    try:
        item.delete()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "Accepted form removed from the editable qualification plan.")
    return redirect("finance:shadow_cycle_detail", pk=cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def cutover_qualification_evidence_create(request, cycle_pk):
    department = department_for_user(request.user)
    candidate = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    plan = get_object_or_404(
        FinanceCutoverQualificationPlan, cycle=candidate, status=FinanceCutoverQualificationPlan.APPROVED,
    )
    form = FinanceCutoverQualificationEvidenceForm(request.POST or None, candidate_cycle=candidate)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.plan = plan
        item.prepared_by = request.user
        try:
            item.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft field-cycle evidence saved. Submit it for independent review.")
            return redirect("finance:shadow_cycle_detail", pk=candidate.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Add qualifying field cycle — {candidate.code}", "cycle": candidate,
        "guidance": (
            "Record references to actual retained field evidence. Do not use synthetic UAT alone, invent signatures, "
            "or imply that a starter template is a locally accepted form."
        ),
    })


@shadow_access_required
def cutover_qualification_evidence_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    item = get_object_or_404(
        FinanceCutoverQualificationEvidence.objects.select_related(
            "plan", "plan__cycle", "plan__cycle__department", "cycle",
        ), pk=pk,
    )
    if not can_view_shadow_cycle(request.user, item.plan.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "submit":
            submit_cutover_qualification_evidence(item, request.user)
        elif action == "accept":
            review_cutover_qualification_evidence(item, request.user, accept=True, reason=reason)
        elif action == "return":
            review_cutover_qualification_evidence(item, request.user, accept=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The field-cycle evidence action is checksummed and retained.")
    return redirect("finance:shadow_cycle_detail", pk=item.plan.cycle_id)


@finance_permission_required(can_manage_shadow_operation)
def cutover_readiness_exercise_create(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    form = FinanceCutoverReadinessExerciseForm(request.POST or None, cycle=cycle)
    if request.method == "POST" and form.is_valid():
        try:
            schedule_cutover_readiness_exercise(
                cycle, request.user,
                kind=form.cleaned_data["kind"], code=form.cleaned_data["code"],
                title=form.cleaned_data["title"], enabled_scope=form.cleaned_data["enabled_scope"],
                procedure=form.cleaned_data["procedure"], expected_result=form.cleaned_data["expected_result"],
                owner=form.cleaned_data["owner"], witness=form.cleaned_data["witness"],
                scheduled_for=form.cleaned_data["scheduled_for"], due_at=form.cleaned_data["due_at"],
                stakeholder_acceptance=form.cleaned_data["stakeholder_acceptance"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Readiness exercise scheduled with the approved support route pinned to it.")
            return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Schedule readiness exercise — {cycle.code}", "cycle": cycle,
        "guidance": (
            "Use familiar instructions and observable pass results. Role training attaches to one named stakeholder; "
            "other exercise kinds cover the cutover's security, privacy, usability, operating, recovery, and support controls."
        ),
    })


@shadow_access_required
def cutover_readiness_exercise_result(request, pk):
    exercise = get_object_or_404(
        FinanceCutoverReadinessExercise.objects.select_related(
            "cycle", "cycle__department", "owner", "recovery_rehearsal",
        ), pk=pk,
    )
    if not can_view_shadow_cycle(request.user, exercise.cycle):
        raise PermissionDenied
    if request.user.pk != exercise.owner_id:
        raise PermissionDenied
    if exercise.kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE:
        try:
            recovery = exercise.recovery_rehearsal
        except FinanceRecoveryRehearsalEvidence.DoesNotExist:
            recovery = None
        form = FinanceRecoveryRehearsalResultForm(
            request.POST or None, exercise=exercise, instance=recovery,
        )
    else:
        form = FinanceCutoverReadinessExerciseResultForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            submit_cutover_readiness_exercise(
                exercise, request.user, actual_result=form.cleaned_data["actual_result"],
                evidence_reference=form.cleaned_data["evidence_reference"],
                recovery_evidence=(
                    form.recovery_values()
                    if exercise.kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE else None
                ),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Exercise result submitted; it does not pass until the assigned witness accepts it.")
            return redirect("finance:shadow_cycle_detail", pk=exercise.cycle_id)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Record exercise result — {exercise.code}", "cycle": exercise.cycle,
        "guidance": (
            "Bind the exact off-host backup set, preflight receipt, both restored stores, RPO/RTO timing, "
            "control reconciliation, cross-store case, runtime-file check, exceptions, and secure disposal. "
            "The assigned witness can pass only a checksum-intact record meeting every approved objective."
            if exercise.kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE
            else "Record observable results and retained redacted evidence. The assigned independent witness decides pass or rerun."
        ),
    })


def _visible_discovery_decisions(user):
    query = Q(owner=user) | Q(reviewer=user)
    department = department_for_user(user)
    if department and (
        can_view_finance_setup(user, department)
        or can_manage_finance_discovery(user, department)
    ):
        query |= Q(department=department)
    return FinanceDiscoveryDecision.objects.filter(query).select_related(
        "department", "cycle", "owner", "reviewer", "created_by", "submitted_by",
        "reviewed_by", "predecessor",
    ).distinct()


def _discovery_decision_for_user(user, public_id):
    item = get_object_or_404(_visible_discovery_decisions(user), public_id=public_id)
    if not can_view_finance_discovery_decision(user, item):
        raise PermissionDenied
    return item


@discovery_access_required
def discovery_workspace(request):
    decisions = _visible_discovery_decisions(request.user)
    selected_phase = request.GET.get("phase", "")
    selected_status = request.GET.get("status", "")
    if selected_phase in dict(FinanceDiscoveryDecision.PHASE_CHOICES):
        decisions = decisions.filter(phase=selected_phase)
    else:
        selected_phase = ""
    if selected_status in dict(FinanceDiscoveryDecision.STATUS_CHOICES):
        decisions = decisions.filter(status=selected_status)
    else:
        selected_status = ""
    department = department_for_user(request.user)
    can_create = can_manage_finance_discovery(request.user, department)
    coverage_summaries = []
    if can_create:
        coverage_labels = dict(FinanceDiscoveryDecision.COVERAGE_KIND_CHOICES)
        for cycle in FinanceShadowCycle.objects.filter(department=department).prefetch_related(
            "discovery_decisions",
        ).order_by("-fiscal_year", "-planned_start", "code"):
            current = [
                item for item in cycle.discovery_decisions.all()
                if item.status != FinanceDiscoveryDecision.SUPERSEDED
            ]
            accepted_kinds = {
                item.coverage_kind for item in current
                if item.status == FinanceDiscoveryDecision.RECORDED
                and item.phase == "F0"
                and item.evidence_label == FinanceDiscoveryDecision.LGU_CONFIRMED
                and not item.blocks_affected_scope
                and item.acceptance_example_reference.strip()
            }
            missing = sorted(FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS - accepted_kinds)
            scope_accepted = any(
                item.coverage_kind == FinanceDiscoveryDecision.SCOPE_ACCEPTANCE
                and item.phase == "F0"
                and item.status == FinanceDiscoveryDecision.RECORDED
                and item.evidence_label == FinanceDiscoveryDecision.LGU_CONFIRMED
                and not item.blocks_affected_scope
                and item.acceptance_example_reference.strip()
                and item.affected_scope.strip() == cycle.enabled_scope.strip()
                for item in current
            )
            coverage_summaries.append({
                "cycle": cycle,
                "current_count": len(current),
                "blocking_count": sum(item.blocks_affected_scope for item in current),
                "accepted_count": len(FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS) - len(missing),
                "required_count": len(FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS),
                "missing_labels": [coverage_labels[kind] for kind in missing],
                "scope_accepted": scope_accepted,
            })
    visible = list(decisions)
    return render(request, "finance/discovery_workspace.html", {
        "decisions": visible,
        "selected_phase": selected_phase,
        "selected_status": selected_status,
        "phase_choices": FinanceDiscoveryDecision.PHASE_CHOICES,
        "status_choices": FinanceDiscoveryDecision.STATUS_CHOICES,
        "can_create": can_create,
        "coverage_summaries": coverage_summaries,
        "can_access_setup": bool(department and can_view_finance_setup(request.user, department)),
        "blocking_count": sum(item.is_current_blocker for item in visible),
    })


@finance_permission_required(can_manage_finance_discovery)
def discovery_decision_create(request):
    department = department_for_user(request.user)
    form = FinanceDiscoveryDecisionForm(
        request.POST or None, department=department, creator=request.user,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department = department
        item.code = item.code.strip().upper()
        item.version = 1
        item.created_by = request.user
        if FinanceDiscoveryDecision.objects.filter(
            department=department, code=item.code, version=1,
        ).exists():
            form.add_error("code", "This decision code already exists. Open its recorded version and create a successor.")
        else:
            item.save()
            FinanceAuditEvent.objects.create(
                department=department,
                target_type="financediscoverydecision",
                target_id=str(item.pk),
                action="discovery_decision_created",
                actor=request.user,
                snapshot={
                    "public_id": str(item.public_id), "code": item.code,
                    "version": item.version, "phase": item.phase,
                    "affected_scope": item.affected_scope,
                    "blocks_affected_scope": item.blocks_affected_scope,
                },
            )
            messages.success(request, "Draft Finance finding/decision created. It has not been independently recorded.")
            return redirect("finance:discovery_decision_detail", public_id=item.public_id)
    return render(request, "finance/discovery_form.html", {
        "form": form,
        "title": "Add Finance finding or decision",
        "guidance": "Name only the affected scope. Public guidance, current-system observation, local confirmation, and GRAND implementation are different evidence labels; use Unresolved when authority or agreement is missing.",
    })


@finance_permission_required(can_manage_finance_discovery)
def discovery_coverage_starters(request):
    department = department_for_user(request.user)
    form = FinanceDiscoveryCoverageStarterForm(
        request.POST or None, department=department, actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            created = create_discovery_coverage_starters(
                form.cleaned_data["cycle"],
                request.user,
                owner=form.cleaned_data["owner"],
                reviewer=form.cleaned_data["reviewer"],
                due_date=form.cleaned_data["due_date"],
            )
        except ValidationError as exc:
            form.add_error(None, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        else:
            messages.success(
                request,
                f"{len(created)} unresolved discovery coverage starter(s) added. Edit each row from local evidence before review.",
            )
            return redirect("finance:discovery_workspace")
    return render(request, "finance/discovery_coverage_starter.html", {
        "form": form,
    })


@discovery_access_required
def discovery_decision_detail(request, public_id):
    item = _discovery_decision_for_user(request.user, public_id)
    return render(request, "finance/discovery_decision_detail.html", {
        "item": item,
        "can_prepare": can_prepare_finance_discovery_decision(request.user, item),
        "can_review": can_review_finance_discovery_decision(request.user, item),
    })


@discovery_access_required
def discovery_decision_edit(request, public_id):
    item = _discovery_decision_for_user(request.user, public_id)
    if not can_prepare_finance_discovery_decision(request.user, item):
        raise PermissionDenied
    if item.status not in {FinanceDiscoveryDecision.DRAFT, FinanceDiscoveryDecision.RETURNED}:
        return redirect("finance:discovery_decision_detail", public_id=item.public_id)
    form = FinanceDiscoveryDecisionForm(
        request.POST or None, instance=item, department=item.department,
        creator=item.created_by,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save()
        FinanceAuditEvent.objects.create(
            department=item.department,
            target_type="financediscoverydecision",
            target_id=str(item.pk),
            action="discovery_decision_draft_updated",
            actor=request.user,
            snapshot={
                "code": item.code, "version": item.version, "phase": item.phase,
                "affected_scope": item.affected_scope,
                "blocks_affected_scope": item.blocks_affected_scope,
            },
        )
        messages.success(request, "Draft decision updated. Submit it again for the named review when ready.")
        return redirect("finance:discovery_decision_detail", public_id=item.public_id)
    return render(request, "finance/discovery_form.html", {
        "form": form,
        "title": f"Edit {item.code} v{item.version}",
        "guidance": "Corrections are allowed while Draft or Returned. Once independently recorded, use a reasoned successor instead of rewriting this evidence.",
        "item": item,
    })


@discovery_access_required
def discovery_decision_successor(request, public_id):
    predecessor = _discovery_decision_for_user(request.user, public_id)
    if not can_prepare_finance_discovery_decision(request.user, predecessor):
        raise PermissionDenied
    if predecessor.status != FinanceDiscoveryDecision.RECORDED:
        messages.error(request, "Only the current independently recorded decision can have a successor.")
        return redirect("finance:discovery_decision_detail", public_id=predecessor.public_id)
    if hasattr(predecessor, "successor"):
        return redirect("finance:discovery_decision_detail", public_id=predecessor.successor.public_id)
    instance = FinanceDiscoveryDecision(
        department=predecessor.department,
        cycle=predecessor.cycle,
        code=predecessor.code,
        version=predecessor.version + 1,
        phase=predecessor.phase,
        question=predecessor.question,
        proposed_outcome=predecessor.proposed_outcome,
        affected_scope=predecessor.affected_scope,
        evidence_label=predecessor.evidence_label,
        authority_evidence_reference=predecessor.authority_evidence_reference,
        evidence_needed=predecessor.evidence_needed,
        evidence_custody_reference=predecessor.evidence_custody_reference,
        blocks_affected_scope=predecessor.blocks_affected_scope,
        owner=predecessor.owner,
        reviewer=predecessor.reviewer,
        due_date=predecessor.due_date,
        predecessor=predecessor,
        created_by=request.user,
    )
    form = FinanceDiscoveryDecisionForm(
        request.POST or None, instance=instance, department=predecessor.department,
        successor_of=predecessor, creator=request.user,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department = predecessor.department
        item.code = predecessor.code
        item.version = predecessor.version + 1
        item.predecessor = predecessor
        item.created_by = request.user
        item.save()
        FinanceAuditEvent.objects.create(
            department=item.department,
            target_type="financediscoverydecision",
            target_id=str(item.pk),
            action="discovery_decision_successor_created",
            actor=request.user,
            reason=item.change_reason,
            snapshot={
                "code": item.code, "version": item.version,
                "predecessor_id": predecessor.pk,
                "predecessor_checksum": predecessor.evidence_checksum,
            },
        )
        messages.success(request, "Draft successor created. The recorded predecessor remains current until this version is independently recorded.")
        return redirect("finance:discovery_decision_detail", public_id=item.public_id)
    return render(request, "finance/discovery_form.html", {
        "form": form,
        "title": f"Create successor for {predecessor.code} v{predecessor.version}",
        "guidance": "Explain the changed evidence, authority, or operating need. The earlier decision remains intact and current until a different named reviewer records this successor.",
        "item": predecessor,
    })


@discovery_access_required
def discovery_decision_action(request, public_id, action):
    if request.method != "POST":
        raise Http404
    item = _discovery_decision_for_user(request.user, public_id)
    try:
        if action == "submit":
            submit_discovery_decision(item, request.user)
        elif action == "record":
            review_discovery_decision(item, request.user, record=True, reason=request.POST.get("reason", ""))
        elif action == "return":
            review_discovery_decision(item, request.user, record=False, reason=request.POST.get("reason", ""))
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, f"Decision action '{action}' recorded in append-only Finance audit history.")
    return redirect("finance:discovery_decision_detail", public_id=item.public_id)


@discovery_access_required
def discovery_decision_export(request, public_id):
    item = _discovery_decision_for_user(request.user, public_id)
    content, filename, receipt = export_discovery_decision(item, request.user)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Archive-SHA256"] = receipt["sha256"]
    response["X-GRAND-Archive-Path"] = receipt["relative_path"]
    return response


@finance_permission_required(can_manage_finance_discovery)
def discovery_register_export(request):
    department = department_for_user(request.user)
    content, filename, receipt = export_discovery_register(
        department,
        request.user,
        phase=request.GET.get("phase", ""),
        status=request.GET.get("status", ""),
    )
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Archive-SHA256"] = receipt["sha256"]
    response["X-GRAND-Archive-Path"] = receipt["relative_path"]
    return response


def _field_acceptance_cycle(user, raw_pk=None):
    cycles = _visible_shadow_cycles(user)
    if raw_pk in (None, ""):
        return cycles.first()
    try:
        pk = int(raw_pk)
    except (TypeError, ValueError) as exc:
        raise Http404 from exc
    return get_object_or_404(cycles, pk=pk)


@shadow_access_required
def field_acceptance_board(request):
    cycles = _visible_shadow_cycles(request.user)
    cycle = _field_acceptance_cycle(request.user, request.GET.get("cycle"))
    board = build_field_acceptance_board(cycle) if cycle else None
    return render(request, "finance/field_acceptance_board.html", {
        "cycles": cycles,
        "cycle": cycle,
        "board": board,
    })


@shadow_access_required
def field_acceptance_board_export(request):
    cycle = _field_acceptance_cycle(request.user, request.GET.get("cycle"))
    if cycle is None:
        raise Http404
    content, filename, receipt = export_field_acceptance_board(cycle, request.user)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Archive-SHA256"] = receipt["sha256"]
    response["X-GRAND-Archive-Path"] = receipt["relative_path"]
    return response


@shadow_access_required
def cutover_readiness_exercise_action(request, pk, action):
    if request.method != "POST":
        raise Http404
    exercise = get_object_or_404(
        FinanceCutoverReadinessExercise.objects.select_related("cycle", "cycle__department"), pk=pk,
    )
    if not can_view_shadow_cycle(request.user, exercise.cycle):
        raise PermissionDenied
    reason = request.POST.get("reason", "")
    try:
        if action == "accept":
            review_cutover_readiness_exercise(exercise, request.user, accept=True, reason=reason)
        elif action == "return":
            review_cutover_readiness_exercise(exercise, request.user, accept=False, reason=reason)
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "The witness decision and evidence checksum are retained.")
    return redirect("finance:shadow_cycle_detail", pk=exercise.cycle_id)


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
                signed_decision_reference=form.cleaned_data["signed_decision_reference"],
                signed_decision_checksum=form.cleaned_data["signed_decision_checksum"],
                reason=form.cleaned_data["conditions_or_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Your stakeholder decision is recorded and cannot be overwritten.")
            return redirect("finance:shadow_cycle_detail", pk=acceptance.cycle_id)
    return render(request, "finance/cutover_form.html", {
        "form": form, "title": f"Record {acceptance.get_stakeholder_kind_display()} decision",
        "guidance": "Review only the stated scope. Reference the retained signed/attributable record and its SHA-256; GRAND does not store or claim to create the signature. Personal Internal How-To progress remains private learning support.",
        "cycle": acceptance.cycle,
    })


@finance_permission_required(can_manage_shadow_operation)
def cutover_decision_create(request, cycle_pk):
    department = department_for_user(request.user)
    cycle = get_object_or_404(FinanceShadowCycle, pk=cycle_pk, department=department)
    if hasattr(cycle, "cutover_decision"):
        return redirect("finance:shadow_cycle_detail", pk=cycle.pk)
    form = FinanceCutoverDecisionForm(
        request.POST or None, cycle=cycle, initial={"enabled_scope": cycle.enabled_scope},
    )
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
        "guidance": "Record the exact authority matrix, opening reconciliation, rollback criteria, continuity evidence, legacy read-only retention plan, and retained signed authority record. GRAND stores its reference and SHA-256—not the signature image.",
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
