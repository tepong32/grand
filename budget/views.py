import csv

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from src.export_archive import archive_export

from .access import budget_access_required, budget_permission_required, department_for_user, has_budget_permission
from .forms import (
    AppropriationAuthorizationForm, BudgetCallForm, BudgetCeilingForm, BudgetConsolidationForm, BudgetProposalLineForm,
    BudgetResourceEstimateForm, BudgetReviewCommentForm, BudgetVersionForm,
)
from .models import AppropriationAuthorization, BudgetAuditEvent, BudgetCall, BudgetVersion
from .services import (
    actor_label, ceiling_differences, compare_versions, consolidate_versions,
    record_event, transition_authorization, transition_call, transition_version,
)


def _message_error(request, exc):
    messages.error(request, " ".join(exc.messages) if hasattr(exc, "messages") else str(exc))


@budget_access_required
def workspace(request):
    department = department_for_user(request.user)
    calls = BudgetCall.objects.filter(department_id=department.pk).prefetch_related("ceilings", "versions")
    versions = BudgetVersion.objects.filter(department_id=department.pk).select_related("fiscal_year", "budget_call").prefetch_related("lines")[:40]
    return render(request, "budget/workspace.html", {
        "department": department, "calls": calls, "versions": versions,
        "can_prepare_calls": has_budget_permission(request.user, "prepare_budget_calls"),
        "can_prepare_proposals": has_budget_permission(request.user, "prepare_budget_proposals"),
    })


@budget_permission_required("prepare_budget_calls")
def call_create(request):
    department = department_for_user(request.user)
    form = BudgetCallForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department_id, item.department_label = department.pk, department.name
        item.created_by_id, item.created_by_label = request.user.pk, actor_label(request.user)
        try:
            item.full_clean(); item.save(); record_event(item, "created", request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft annual budget call created.")
            return redirect("budget:call_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Create annual budget call", "guidance": "Record the reviewed local authority and dates. A draft call does not authorize spending."})


@budget_access_required
def call_detail(request, public_id):
    department = department_for_user(request.user)
    call = get_object_or_404(BudgetCall.objects.select_related("fiscal_year").prefetch_related("ceilings__fund", "versions"), public_id=public_id, department_id=department.pk)
    return render(request, "budget/call_detail.html", {
        "call": call,
        "can_prepare": has_budget_permission(request.user, "prepare_budget_calls"),
        "can_approve": has_budget_permission(request.user, "approve_budget_calls"),
    })


@budget_permission_required("prepare_budget_calls")
def ceiling_create(request, public_id):
    department = department_for_user(request.user)
    call = get_object_or_404(BudgetCall, public_id=public_id, department_id=department.pk, status__in=(BudgetCall.DRAFT, BudgetCall.RETURNED))
    form = BudgetCeilingForm(request.POST or None, budget_call=call)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.budget_call = call
        item.department_id, item.department_label = department.pk, department.name
        try:
            item.full_clean(); item.save(); record_event(call, "ceiling_added", request.user, snapshot={"office": item.requesting_department_label, "fund": item.fund.code, "expense_class": item.expense_class, "amount": str(item.amount)})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Department ceiling added to the draft call.")
            return redirect("budget:call_detail", public_id=call.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Add department ceiling", "guidance": "Ceilings are Budget controls, not appropriations or allotment releases."})


@require_POST
@budget_access_required
def call_action(request, public_id, action):
    department = department_for_user(request.user)
    call = get_object_or_404(BudgetCall, public_id=public_id, department_id=department.pk)
    permission = "approve_budget_calls" if action in ("publish", "return") else "prepare_budget_calls"
    if not has_budget_permission(request.user, permission):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        transition_call(call, action, request.user, request.POST.get("reason", ""))
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, f"Budget call {action} recorded.")
    return redirect("budget:call_detail", public_id=call.public_id)


@budget_permission_required("prepare_budget_proposals")
def version_create(request):
    department = department_for_user(request.user)
    form = BudgetVersionForm(request.POST or None, department_id=department.pk)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department_id, item.department_label = department.pk, department.name
        item.created_by_id, item.created_by_label = request.user.pk, actor_label(request.user)
        try:
            item.full_clean(); item.save(); record_event(item, "created", request.user, snapshot={"spendable": False})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft budget proposal version created. It is not spendable authority.")
            return redirect("budget:version_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Create budget proposal version", "guidance": "Every version is explicit. Approved proposals remain non-spendable until F3.2 authorization evidence is complete."})


@budget_access_required
def version_detail(request, public_id):
    department = department_for_user(request.user)
    version = get_object_or_404(BudgetVersion.objects.select_related("budget_call", "fiscal_year", "supersedes").prefetch_related("lines__fund", "lines__responsibility_center", "lines__program", "lines__account", "resource_estimates__funding_source", "review_comments", "source_links__source_version"), public_id=public_id, department_id=department.pk)
    events = BudgetAuditEvent.objects.filter(target_id=str(version.public_id))[:30]
    return render(request, "budget/version_detail.html", {
        "version": version, "ceiling_rows": ceiling_differences(version), "events": events,
        "comment_form": BudgetReviewCommentForm(),
        "can_prepare": has_budget_permission(request.user, "prepare_budget_proposals"),
        "can_review": has_budget_permission(request.user, "review_budget_proposals"),
    })


@budget_permission_required("prepare_budget_proposals")
def line_create(request, public_id):
    department = department_for_user(request.user)
    version = get_object_or_404(BudgetVersion, public_id=public_id, department_id=department.pk, status__in=(BudgetVersion.DRAFT, BudgetVersion.RETURNED))
    form = BudgetProposalLineForm(request.POST or None, version=version)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.version = version
        item.department_id, item.department_label = department.pk, department.name
        try:
            item.full_clean(); item.save(); record_event(version, "line_added", request.user, snapshot={"account": item.account.code, "amount": str(item.amount)})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Classified proposal line added.")
            return redirect("budget:version_detail", public_id=version.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Add proposal line", "guidance": "Use governed Finance classifications; avoid free-text account, fund, office, or PPA codes."})


@budget_permission_required("prepare_budget_proposals")
def resource_create(request, public_id):
    department = department_for_user(request.user)
    version = get_object_or_404(BudgetVersion, public_id=public_id, department_id=department.pk, status__in=(BudgetVersion.DRAFT, BudgetVersion.RETURNED))
    form = BudgetResourceEstimateForm(request.POST or None, version=version)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.version = version
        item.department_id, item.department_label = department.pk, department.name
        try:
            item.full_clean(); item.save(); record_event(version, "resource_estimate_added", request.user, snapshot={"source": item.funding_source.code, "amount": str(item.amount)})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Revenue/resource estimate added to this version.")
            return redirect("budget:version_detail", public_id=version.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Add revenue/resource estimate", "guidance": "Record the reviewed estimate and its basis without treating it as cash availability."})


@budget_permission_required("review_budget_proposals")
def consolidate(request):
    department = department_for_user(request.user)
    form = BudgetConsolidationForm(request.POST or None, department_id=department.pk)
    if request.method == "POST" and form.is_valid():
        try:
            version = consolidate_versions(
                sources=form.cleaned_data["sources"], user=request.user,
                title=form.cleaned_data["title"], change_explanation=form.cleaned_data["change_explanation"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Approved department proposals copied into a traceable executive consolidation draft.")
            return redirect("budget:version_detail", public_id=version.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Consolidate approved proposals", "guidance": "GRAND copies approved source versions into a new executive draft and retains explicit source lineage. Source proposals are never overwritten."})


@require_POST
@budget_access_required
def version_action(request, public_id, action):
    department = department_for_user(request.user)
    version = get_object_or_404(BudgetVersion, public_id=public_id, department_id=department.pk)
    permission = "review_budget_proposals" if action in ("approve", "return") else "prepare_budget_proposals"
    if not has_budget_permission(request.user, permission):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        transition_version(version, action, request.user, request.POST.get("reason", ""))
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, f"Budget proposal {action} recorded.")
    return redirect("budget:version_detail", public_id=version.public_id)


@require_POST
@budget_permission_required("review_budget_proposals")
def comment_create(request, public_id):
    department = department_for_user(request.user)
    version = get_object_or_404(BudgetVersion, public_id=public_id, department_id=department.pk)
    form = BudgetReviewCommentForm(request.POST)
    if form.is_valid():
        item = form.save(False)
        item.version = version
        item.department_id, item.department_label = department.pk, department.name
        item.author_id, item.author_label = request.user.pk, actor_label(request.user)
        item.save(); record_event(version, "review_comment_added", request.user)
        messages.success(request, "Review comment added without changing the proposal.")
    else:
        messages.error(request, "Enter a review comment.")
    return redirect("budget:version_detail", public_id=version.public_id)


@require_GET
@budget_access_required
def version_export(request, public_id):
    department = department_for_user(request.user)
    version = get_object_or_404(BudgetVersion.objects.select_related("fiscal_year", "budget_call"), public_id=public_id, department_id=department.pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow(("export_kind", "budget_office", "fiscal_year", "version_kind", "version_number", "version_status", "spendable_authority", "requesting_department", "fund", "responsibility_center", "ppa", "funding_source", "account", "expense_class", "appropriation_type", "particulars", "performance_target", "amount", "change_explanation"))
    for line in version.lines.select_related("fund", "responsibility_center", "program", "funding_source", "account"):
        writer.writerow(("budget_proposal", version.department_label, version.fiscal_year.year, version.kind, version.version, version.status, "no" if not version.is_spendable_authority else "yes", version.requesting_department_label, line.fund.code, line.responsibility_center.code, line.program.code if line.program else "", line.funding_source.code if line.funding_source else "", line.account.code, line.expense_class, line.appropriation_type, line.particulars, line.performance_target, line.amount, line.change_explanation))
    filename = f"budget-{slugify(version.title)}-v{version.version}.csv"
    archived = archive_export(content=response.content, department=department, user=request.user, category="finance-budget-proposals", filename=filename, metadata={"kind": "budget_proposal_export", "version_public_id": str(version.public_id), "status": version.status, "spendable_authority": version.is_spendable_authority, "official_status": "controlled data interchange; not automatically an official DBM/COA form"})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"], response["X-GRAND-Export-SHA256"] = "true", archived["sha256"]
    record_event(version, "exported", request.user, snapshot={"relative_path": archived["relative_path"], "sha256": archived["sha256"]})
    return response


@budget_access_required
def version_compare(request, public_id):
    department = department_for_user(request.user)
    left = get_object_or_404(BudgetVersion, public_id=public_id, department_id=department.pk)
    right_id = request.GET.get("with")
    right = get_object_or_404(BudgetVersion, public_id=right_id, department_id=department.pk) if right_id else None
    candidates = BudgetVersion.objects.filter(department_id=department.pk, fiscal_year=left.fiscal_year).exclude(pk=left.pk)
    return render(request, "budget/compare.html", {"left": left, "right": right, "candidates": candidates, "rows": compare_versions(left, right) if right else []})


@budget_permission_required("prepare_budget_proposals")
def authorization_create(request):
    department = department_for_user(request.user)
    form = AppropriationAuthorizationForm(request.POST or None, department_id=department.pk)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department_id, item.department_label = department.pk, department.name
        item.created_by_id, item.created_by_label = request.user.pk, actor_label(request.user)
        try:
            item.full_clean(); item.save(); record_event(item.version, "appropriation_evidence_created", request.user, snapshot={"authorization_id": str(item.public_id), "spendable": False})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft appropriation authority evidence created. It is not spendable until independent authorization.")
            return redirect("budget:authorization_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Record appropriation authorization evidence", "guidance": "Use the exact approved final/supplemental/reenacted version, ordinance and review evidence, effectivity, and signed control total."})


@budget_access_required
def authorization_detail(request, public_id):
    department = department_for_user(request.user)
    item = get_object_or_404(AppropriationAuthorization.objects.select_related("version", "version__fiscal_year").prefetch_related("schedule_lines"), public_id=public_id, department_id=department.pk)
    return render(request, "budget/authorization_detail.html", {
        "authorization": item,
        "can_prepare": has_budget_permission(request.user, "prepare_budget_proposals"),
        "can_authorize": has_budget_permission(request.user, "authorize_appropriations"),
    })


@require_POST
@budget_access_required
def authorization_action(request, public_id, action):
    department = department_for_user(request.user)
    item = get_object_or_404(AppropriationAuthorization, public_id=public_id, department_id=department.pk)
    permission = "authorize_appropriations" if action in ("authorize", "return") else "prepare_budget_proposals"
    if not has_budget_permission(request.user, permission):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        transition_authorization(item, action, request.user, request.POST.get("reason", ""))
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, f"Appropriation {action} recorded.")
    return redirect("budget:authorization_detail", public_id=item.public_id)


@require_GET
@budget_access_required
def authorization_export(request, public_id):
    department = department_for_user(request.user)
    item = get_object_or_404(AppropriationAuthorization.objects.select_related("version", "version__fiscal_year"), public_id=public_id, department_id=department.pk, status=AppropriationAuthorization.AUTHORIZED)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow(("export_kind", "fiscal_year", "authority_type", "ordinance_number", "effectivity_date", "review_status", "review_reference", "snapshot_checksum", "fund", "responsibility_center", "ppa", "funding_source", "account", "expense_class", "appropriation_type", "particulars", "performance_target", "authorized_amount"))
    for line in item.schedule_lines.all():
        writer.writerow(("authorized_appropriation_schedule", item.version.fiscal_year.year, item.authority_type, item.ordinance_number, item.effectivity_date, item.review_status, item.review_reference, item.snapshot_checksum, line.fund_code, line.responsibility_center_code, line.program_code, line.funding_source_code, line.account_code, line.expense_class, line.appropriation_type, line.particulars, line.performance_target, line.amount))
    filename = f"authorized-appropriation-{slugify(item.ordinance_number)}.csv"
    archived = archive_export(content=response.content, department=department, user=request.user, category="finance-authorized-appropriations", filename=filename, metadata={"authorization_public_id": str(item.public_id), "version_public_id": str(item.version.public_id), "snapshot_checksum": item.snapshot_checksum, "official_status": "controlled schedule export; exact official form acceptance remains required"})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"], response["X-GRAND-Export-SHA256"] = "true", archived["sha256"]
    record_event(item.version, "appropriation_exported", request.user, snapshot={"relative_path": archived["relative_path"], "sha256": archived["sha256"]})
    return response
