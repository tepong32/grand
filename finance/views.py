from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from .access import (
    can_approve_finance_configuration, can_manage_finance_configuration,
    can_manage_finance_templates, department_for_user, finance_access_required,
    finance_permission_required,
)
from .forms import (
    FinanceDocumentRuleForm, FinanceItemForm, FinanceNumberingSequenceForm, FinanceReleaseForm,
    FinancePartyClaimantForm, FinancePartyForm, FinancePostingRuleForm, FinancePostingRuleLineForm,
    FinanceSignatoryForm, FinanceTemplateForm, FinanceStarterTemplateForm, FinanceTransactionVariantForm,
)
from .models import FinanceConfigurationRelease, FinanceParty, FinanceTemplateVersion, FinanceTransactionVariant
from .services import (
    FinanceTemplateError, build_finance_starter_workbook, create_recognition_posting_starter,
    evaluate_readiness, preflight_finance_template, record_event, synthetic_preview, transition_release,
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
