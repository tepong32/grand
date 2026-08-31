import csv

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from src.export_archive import archive_export

from .access import budget_access_required, budget_permission_required, department_for_user, has_budget_permission
from .forms import (
    AllotmentOrderLineForm, AllotmentReleaseOrderForm, AppropriationAuthorizationForm,
    BudgetCallForm, BudgetCeilingForm, BudgetConsolidationForm, BudgetProposalLineForm,
    BudgetResourceEstimateForm, BudgetReviewCommentForm, BudgetVersionForm,
    ObligationRequestForm, ObligationRequestLineForm,
)
from .models import (
    AllotmentReleaseOrder, AppropriationAuthorization, BudgetAuditEvent, BudgetCall, BudgetVersion,
    ObligationRequest,
)
from .services import (
    actor_label, allotment_line_balance, authorization_allotment_totals,
    authorization_obligation_totals, downstream_issuance_boundary, obligation_line_balance,
    ceiling_differences, compare_versions, consolidate_versions, record_event,
    transition_allotment_order, transition_authorization, transition_call, transition_version,
    transition_obligation_request,
)


def _message_error(request, exc):
    messages.error(request, " ".join(exc.messages) if hasattr(exc, "messages") else str(exc))


def _obligation_scope(user):
    department = department_for_user(user)
    if not department:
        return ObligationRequest.objects.none()
    scope = Q(pk__in=[])
    if has_budget_permission(user, "view_obligation_registry") or has_budget_permission(user, "certify_obligations"):
        scope |= Q(department_id=department.pk)
    if has_budget_permission(user, "initiate_obligation_requests"):
        scope |= Q(requesting_department_id=department.pk)
    return ObligationRequest.objects.filter(scope)


def _require_obligation_permission(user, *codenames):
    if not any(has_budget_permission(user, codename) for codename in codenames):
        raise PermissionDenied


@budget_access_required
def workspace(request):
    department = department_for_user(request.user)
    calls = BudgetCall.objects.filter(department_id=department.pk).prefetch_related("ceilings", "versions")
    versions = BudgetVersion.objects.filter(department_id=department.pk).select_related("fiscal_year", "budget_call").prefetch_related("lines")[:40]
    return render(request, "budget/workspace.html", {
        "department": department, "calls": calls, "versions": versions,
        "can_prepare_calls": has_budget_permission(request.user, "prepare_budget_calls"),
        "can_prepare_proposals": has_budget_permission(request.user, "prepare_budget_proposals"),
        "can_view_allotments": has_budget_permission(request.user, "view_allotment_control"),
        "can_view_obligations": any(has_budget_permission(request.user, code) for code in (
            "view_obligation_registry", "initiate_obligation_requests", "certify_obligations",
        )),
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


@budget_permission_required("view_allotment_control")
def allotment_workspace(request):
    department = department_for_user(request.user)
    authorizations = list(AppropriationAuthorization.objects.filter(
        department_id=department.pk, status=AppropriationAuthorization.AUTHORIZED,
    ).select_related("version", "version__fiscal_year").prefetch_related("schedule_lines"))
    authority_rows = [
        {"authorization": item, "totals": authorization_allotment_totals(item)} for item in authorizations
    ]
    orders = AllotmentReleaseOrder.objects.filter(department_id=department.pk).select_related(
        "fiscal_year", "authorization", "corrects"
    )[:60]
    return render(request, "budget/allotment_workspace.html", {
        "department": department, "authority_rows": authority_rows, "orders": orders,
        "can_prepare": has_budget_permission(request.user, "prepare_allotment_releases"),
    })


@budget_permission_required("prepare_allotment_releases")
def allotment_create(request):
    department = department_for_user(request.user)
    form = AllotmentReleaseOrderForm(request.POST or None, department_id=department.pk)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.department_id, item.department_label = department.pk, department.name
        item.fiscal_year = item.authorization.version.fiscal_year
        item.created_by_id, item.created_by_label = request.user.pk, actor_label(request.user)
        try:
            item.full_clean(); item.save()
            record_event(item, "allotment_created", request.user, snapshot={"order_number": item.order_number, "kind": item.kind})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft allotment release order created. Add the exact authorized schedule lines before submission.")
            return redirect("budget:allotment_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": "Create allotment release order",
        "guidance": "Choose only posted operational appropriation authority. A draft is editable; posting creates immutable movements, and later corrections require a linked order.",
    })


@budget_permission_required("prepare_allotment_releases")
def allotment_edit(request, public_id):
    department = department_for_user(request.user)
    item = get_object_or_404(
        AllotmentReleaseOrder, public_id=public_id, department_id=department.pk,
        status__in=(AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED),
    )
    form = AllotmentReleaseOrderForm(request.POST or None, instance=item, department_id=department.pk)
    if request.method == "POST" and form.is_valid():
        updated = form.save(False)
        updated.fiscal_year = updated.authorization.version.fiscal_year
        updated.state_version += 1
        try:
            updated.full_clean(); updated.save()
            record_event(updated, "allotment_draft_edited", request.user, snapshot={"order_number": updated.order_number, "state_version": updated.state_version})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft allotment order updated; the edit remains visible in audit history.")
            return redirect("budget:allotment_detail", public_id=updated.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": f"Edit allotment order {item.order_number}",
        "guidance": "Edit only while draft or returned. Once posted, use a linked correction, return, or cancellation order.",
    })


@budget_permission_required("view_allotment_control")
def allotment_detail(request, public_id):
    department = department_for_user(request.user)
    item = get_object_or_404(AllotmentReleaseOrder.objects.select_related(
        "authorization", "authorization__version", "fiscal_year", "corrects"
    ).prefetch_related("lines__appropriation_line", "movements__appropriation_line"), public_id=public_id, department_id=department.pk)
    line_rows = [
        {"line": line, "balance": allotment_line_balance(line.appropriation_line)} for line in item.lines.all()
    ]
    return render(request, "budget/allotment_detail.html", {
        "order": item, "line_rows": line_rows,
        "can_prepare": has_budget_permission(request.user, "prepare_allotment_releases"),
        "can_post": has_budget_permission(request.user, "approve_allotment_releases"),
    })


@budget_permission_required("prepare_allotment_releases")
def allotment_line_create(request, public_id):
    department = department_for_user(request.user)
    item = get_object_or_404(
        AllotmentReleaseOrder.objects.select_related("authorization"), public_id=public_id,
        department_id=department.pk, status__in=(AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED),
    )
    form = AllotmentOrderLineForm(request.POST or None, order=item)
    if request.method == "POST" and form.is_valid():
        line = form.save(False)
        line.order = item
        line.department_id, line.department_label = department.pk, department.name
        try:
            line.full_clean(); line.save()
            item.state_version += 1; item.save(update_fields=("state_version", "updated_at"))
            record_event(item, "allotment_line_added", request.user, snapshot={
                "appropriation_line_id": line.appropriation_line_id,
                "movement_type": line.movement_type, "amount": str(line.amount),
            })
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Authorized appropriation line added to the draft order.")
            return redirect("budget:allotment_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": f"Add schedule line to {item.order_number}",
        "guidance": "The movement type is constrained by the order type. Posting will recheck the cumulative line balance under a database lock.",
    })


@budget_permission_required("prepare_allotment_releases")
def allotment_line_edit(request, public_id, line_id):
    department = department_for_user(request.user)
    item = get_object_or_404(
        AllotmentReleaseOrder.objects.select_related("authorization"), public_id=public_id,
        department_id=department.pk, status__in=(AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED),
    )
    line = get_object_or_404(item.lines, pk=line_id, department_id=department.pk)
    before = {"appropriation_line_id": line.appropriation_line_id, "movement_type": line.movement_type, "amount": str(line.amount), "remarks": line.remarks}
    form = AllotmentOrderLineForm(request.POST or None, instance=line, order=item)
    if request.method == "POST" and form.is_valid():
        updated = form.save(False)
        try:
            updated.full_clean(); updated.save()
            item.state_version += 1; item.save(update_fields=("state_version", "updated_at"))
            record_event(item, "allotment_line_edited", request.user, snapshot={
                "before": before,
                "after": {"appropriation_line_id": updated.appropriation_line_id, "movement_type": updated.movement_type, "amount": str(updated.amount), "remarks": updated.remarks},
            })
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft schedule line corrected with before/after audit evidence.")
            return redirect("budget:allotment_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": f"Correct schedule line in {item.order_number}",
        "guidance": "Before submission/posting, correct the selected authority line, movement, amount, or remarks. After posting, use a linked successor order instead.",
    })


@require_POST
@budget_permission_required("prepare_allotment_releases")
def allotment_line_delete(request, public_id, line_id):
    department = department_for_user(request.user)
    item = get_object_or_404(
        AllotmentReleaseOrder, public_id=public_id, department_id=department.pk,
        status__in=(AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED),
    )
    line = get_object_or_404(item.lines, pk=line_id, department_id=department.pk)
    snapshot = {"appropriation_line_id": line.appropriation_line_id, "movement_type": line.movement_type, "amount": str(line.amount), "remarks": line.remarks}
    line.delete()
    item.state_version += 1; item.save(update_fields=("state_version", "updated_at"))
    record_event(item, "allotment_line_removed", request.user, reason=request.POST.get("reason", ""), snapshot=snapshot)
    messages.success(request, "Draft schedule line removed; its prior values remain in audit history.")
    return redirect("budget:allotment_detail", public_id=item.public_id)


@require_POST
@budget_permission_required("view_allotment_control")
def allotment_action(request, public_id, action):
    department = department_for_user(request.user)
    item = get_object_or_404(AllotmentReleaseOrder, public_id=public_id, department_id=department.pk)
    permission = "approve_allotment_releases" if action in ("post", "return") else "prepare_allotment_releases"
    if not has_budget_permission(request.user, permission):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        transition_allotment_order(item, action, request.user, request.POST.get("reason", ""))
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, f"Allotment order {action} recorded.")
    return redirect("budget:allotment_detail", public_id=item.public_id)


@require_GET
@budget_permission_required("view_allotment_control")
def allotment_export(request, public_id):
    department = department_for_user(request.user)
    item = get_object_or_404(AllotmentReleaseOrder.objects.select_related(
        "authorization", "authorization__version", "fiscal_year"
    ).prefetch_related("movements__appropriation_line"), public_id=public_id, department_id=department.pk, status=AllotmentReleaseOrder.POSTED)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "budget_office", "fiscal_year", "order_number", "order_type", "effective_date",
        "authority_reference", "appropriation_checksum", "allotment_checksum", "fund", "responsibility_center",
        "ppa", "funding_source", "account", "expense_class", "movement_type", "movement_amount",
        "release_effect", "hold_effect", "authorized_amount", "released_to_date", "reserved_to_date", "deferred_to_date", "held_to_date",
        "unreleased_balance", "executable_balance", "remarks",
    ))
    for movement in item.movements.all():
        line, balance = movement.appropriation_line, allotment_line_balance(movement.appropriation_line)
        writer.writerow((
            "posted_allotment_movement", item.department_label, item.fiscal_year.year, item.order_number,
            item.kind, item.effective_date, item.authority_reference, item.authorization.snapshot_checksum,
            item.snapshot_checksum, line.fund_code, line.responsibility_center_code, line.program_code,
            line.funding_source_code, line.account_code, line.expense_class, movement.movement_type,
            movement.amount, movement.release_effect, movement.hold_effect, balance["authorized"],
            balance["released"], balance["reserved"], balance["deferred"], balance["held"], balance["unreleased"], balance["executable"], movement.remarks,
        ))
    filename = f"allotment-{slugify(item.order_number)}.csv"
    archived = archive_export(
        content=response.content, department=department, user=request.user,
        category="finance-allotment-releases", filename=filename,
        metadata={
            "kind": "posted_allotment_schedule", "allotment_public_id": str(item.public_id),
            "appropriation_public_id": str(item.authorization.public_id), "snapshot_checksum": item.snapshot_checksum,
            "official_status": "controlled schedule export; exact local/DBM/COA form acceptance remains required",
        },
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"], response["X-GRAND-Export-SHA256"] = "true", archived["sha256"]
    record_event(item, "allotment_exported", request.user, snapshot={"relative_path": archived["relative_path"], "sha256": archived["sha256"]})
    return response


@budget_access_required
def obligation_workspace(request):
    department = department_for_user(request.user)
    can_registry = has_budget_permission(request.user, "view_obligation_registry") or has_budget_permission(request.user, "certify_obligations")
    authorizations = []
    if can_registry:
        authorizations = list(AppropriationAuthorization.objects.filter(
            department_id=department.pk, status=AppropriationAuthorization.AUTHORIZED,
        ).select_related("version", "version__fiscal_year").prefetch_related("schedule_lines"))
    authority_rows = [{"authorization": item, "totals": authorization_obligation_totals(item)} for item in authorizations]
    items = _obligation_scope(request.user).select_related(
        "fiscal_year", "authorization", "corrects"
    )[:100]
    return render(request, "budget/obligation_workspace.html", {
        "department": department, "authority_rows": authority_rows, "requests": items,
        "can_initiate": has_budget_permission(request.user, "initiate_obligation_requests"),
        "can_certify": has_budget_permission(request.user, "certify_obligations"),
        "can_registry": can_registry,
    })


@budget_access_required
def obligation_create(request):
    _require_obligation_permission(request.user, "initiate_obligation_requests")
    department = department_for_user(request.user)
    form = ObligationRequestForm(request.POST or None, requesting_department=department)
    if request.method == "POST" and form.is_valid():
        item = form.save(False)
        item.created_by_id, item.created_by_label = request.user.pk, actor_label(request.user)
        try:
            item.full_clean(); item.save()
            record_event(item, "obligation_request_created", request.user, snapshot={
                "request_reference": item.request_reference, "requesting_department": item.requesting_department_label,
            })
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft obligation request created. Add the exact appropriation schedule before Budget submission.")
            return redirect("budget:obligation_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": "Initiate obligation request",
        "guidance": "Choose the exact authority and locally applicable ALOBS/ORS/OBR type. This draft does not consume allotment until Budget independently certifies it.",
    })


@budget_access_required
def obligation_edit(request, public_id):
    _require_obligation_permission(request.user, "initiate_obligation_requests")
    department = department_for_user(request.user)
    item = get_object_or_404(
        ObligationRequest, public_id=public_id, requesting_department_id=department.pk,
        status__in=(ObligationRequest.DRAFT, ObligationRequest.RETURNED),
    )
    form = ObligationRequestForm(request.POST or None, instance=item, requesting_department=department)
    if request.method == "POST" and form.is_valid():
        updated = form.save(False)
        updated.state_version += 1
        try:
            updated.full_clean(); updated.save()
            record_event(updated, "obligation_draft_edited", request.user, snapshot={
                "request_reference": updated.request_reference, "state_version": updated.state_version,
            })
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft request corrected with retained audit evidence.")
            return redirect("budget:obligation_detail", public_id=updated.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": f"Edit obligation request {item.request_reference}",
        "guidance": "Guided edits are allowed while draft or returned. After certification, create a linked adjustment, return, or cancellation; after DV/check issuance use the later reversal route.",
    })


@budget_access_required
def obligation_detail(request, public_id):
    _require_obligation_permission(
        request.user, "view_obligation_registry", "initiate_obligation_requests", "certify_obligations"
    )
    item = get_object_or_404(_obligation_scope(request.user).select_related(
        "authorization", "authorization__version", "fiscal_year", "corrects"
    ).prefetch_related("lines__appropriation_line", "movements__appropriation_line"), public_id=public_id)
    line_rows = [{"line": line, "balance": obligation_line_balance(line.appropriation_line)} for line in item.lines.all()]
    department = department_for_user(request.user)
    return render(request, "budget/obligation_detail.html", {
        "obligation": item, "line_rows": line_rows,
        "can_edit": has_budget_permission(request.user, "initiate_obligation_requests") and item.requesting_department_id == department.pk,
        "can_certify": has_budget_permission(request.user, "certify_obligations") and item.department_id == department.pk,
        "downstream_boundary": downstream_issuance_boundary(item),
    })


@budget_access_required
def obligation_line_create(request, public_id):
    _require_obligation_permission(request.user, "initiate_obligation_requests")
    department = department_for_user(request.user)
    item = get_object_or_404(
        ObligationRequest.objects.select_related("authorization"), public_id=public_id,
        requesting_department_id=department.pk, status__in=(ObligationRequest.DRAFT, ObligationRequest.RETURNED),
    )
    form = ObligationRequestLineForm(request.POST or None, request_item=item)
    if request.method == "POST" and form.is_valid():
        line = form.save(False)
        try:
            line.full_clean(); line.save()
            item.state_version += 1; item.save(update_fields=("state_version", "updated_at"))
            record_event(item, "obligation_line_added", request.user, snapshot={
                "appropriation_line_id": line.appropriation_line_id, "movement_type": line.movement_type,
                "amount": str(line.amount),
            })
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Authorized appropriation line added to the draft request.")
            return redirect("budget:obligation_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": f"Add obligation schedule line to {item.request_reference}",
        "guidance": "Budget will recheck the exact unobligated allotment under a database lock at certification.",
    })


@budget_access_required
def obligation_line_edit(request, public_id, line_id):
    _require_obligation_permission(request.user, "initiate_obligation_requests")
    department = department_for_user(request.user)
    item = get_object_or_404(
        ObligationRequest.objects.select_related("authorization"), public_id=public_id,
        requesting_department_id=department.pk, status__in=(ObligationRequest.DRAFT, ObligationRequest.RETURNED),
    )
    line = get_object_or_404(item.lines, pk=line_id, department_id=item.department_id)
    before = {"appropriation_line_id": line.appropriation_line_id, "movement_type": line.movement_type, "amount": str(line.amount), "remarks": line.remarks}
    form = ObligationRequestLineForm(request.POST or None, instance=line, request_item=item)
    if request.method == "POST" and form.is_valid():
        updated = form.save(False)
        try:
            updated.full_clean(); updated.save()
            item.state_version += 1; item.save(update_fields=("state_version", "updated_at"))
            record_event(item, "obligation_line_edited", request.user, snapshot={
                "before": before, "after": {"appropriation_line_id": updated.appropriation_line_id,
                "movement_type": updated.movement_type, "amount": str(updated.amount), "remarks": updated.remarks},
            })
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Draft line corrected with before/after audit evidence.")
            return redirect("budget:obligation_detail", public_id=item.public_id)
    return render(request, "budget/form.html", {
        "form": form, "title": f"Correct obligation line in {item.request_reference}",
        "guidance": "This guided edit remains available only before submission/certification. Certified history is never rewritten.",
    })


@require_POST
@budget_access_required
def obligation_line_delete(request, public_id, line_id):
    _require_obligation_permission(request.user, "initiate_obligation_requests")
    department = department_for_user(request.user)
    item = get_object_or_404(
        ObligationRequest, public_id=public_id, requesting_department_id=department.pk,
        status__in=(ObligationRequest.DRAFT, ObligationRequest.RETURNED),
    )
    line = get_object_or_404(item.lines, pk=line_id, department_id=item.department_id)
    snapshot = {"appropriation_line_id": line.appropriation_line_id, "movement_type": line.movement_type, "amount": str(line.amount), "remarks": line.remarks}
    line.delete()
    item.state_version += 1; item.save(update_fields=("state_version", "updated_at"))
    record_event(item, "obligation_line_removed", request.user, reason=request.POST.get("reason", ""), snapshot=snapshot)
    messages.success(request, "Draft line removed; its prior values remain in audit history.")
    return redirect("budget:obligation_detail", public_id=item.public_id)


@require_POST
@budget_access_required
def obligation_action(request, public_id, action):
    _require_obligation_permission(request.user, "initiate_obligation_requests", "certify_obligations")
    item = get_object_or_404(_obligation_scope(request.user), public_id=public_id)
    if action == "submit" and not has_budget_permission(request.user, "initiate_obligation_requests"):
        raise PermissionDenied
    if action in ("certify", "return") and not has_budget_permission(request.user, "certify_obligations"):
        raise PermissionDenied
    try:
        transition_obligation_request(
            item, action, request.user, request.POST.get("reason", ""), request.POST.get("obligation_number", ""),
        )
    except ValidationError as exc:
        _message_error(request, exc)
    else:
        messages.success(request, f"Obligation {action} recorded.")
    return redirect("budget:obligation_detail", public_id=item.public_id)


@require_GET
@budget_access_required
def obligation_registry_export(request):
    _require_obligation_permission(request.user, "view_obligation_registry", "certify_obligations")
    department = department_for_user(request.user)
    items = ObligationRequest.objects.filter(
        department_id=department.pk, status=ObligationRequest.CERTIFIED,
    ).select_related("authorization", "fiscal_year").prefetch_related("movements__appropriation_line")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "budget_office", "fiscal_year", "form_type", "obligation_number", "request_reference",
        "requesting_office", "obligation_date", "claimant_payee", "kind", "corrects", "appropriation_checksum",
        "obligation_checksum", "fund", "responsibility_center", "ppa", "funding_source", "account", "expense_class",
        "movement", "effect", "released_allotment", "held_allotment", "executable_allotment", "obligated_to_date",
        "unobligated_balance", "particulars", "remarks",
    ))
    for item in items:
        for movement in item.movements.all():
            line, balance = movement.appropriation_line, obligation_line_balance(movement.appropriation_line)
            writer.writerow((
                "certified_obligation_movement", item.department_label, item.fiscal_year.year, item.form_type,
                item.obligation_number, item.request_reference, item.requesting_department_label, item.obligation_date,
                item.claimant_payee, item.kind, item.corrects.obligation_number if item.corrects else "",
                item.authorization.snapshot_checksum, item.snapshot_checksum, line.fund_code,
                line.responsibility_center_code, line.program_code, line.funding_source_code, line.account_code,
                line.expense_class, movement.movement_type, movement.obligation_effect, balance["released"],
                balance["held"], balance["executable"], balance["obligated"], balance["unobligated"],
                item.particulars, movement.remarks,
            ))
    filename = f"raao-obligation-registry-{slugify(department.name)}.csv"
    archived = archive_export(
        content=response.content, department=department, user=request.user,
        category="finance-obligation-registry", filename=filename,
        metadata={
            "kind": "certified_obligation_registry", "row_scope": "current certified registry",
            "official_status": "controlled RAAO-equivalent export; exact local/DBM/COA template acceptance remains required",
        },
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"], response["X-GRAND-Export-SHA256"] = "true", archived["sha256"]
    return response
