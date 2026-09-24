import csv
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from src.export_archive import archive_export
from .access import budget_access_required, budget_permission_required, can_act_on_budget, department_for_user, has_budget_permission
from .forms import QuarterlyPlanForm, QuarterlyPlanLineForm
from .models import AppropriationAuthorization, QuarterlyFinancialPlan, BudgetAuditEvent
from .quarterly import PREPARE, REVIEW, create_plan, edit_line, plan_context, transition_plan
from .services import record_event
from .history import history_page


def owned_plan(request, public_id):
    return get_object_or_404(QuarterlyFinancialPlan.objects.select_related("authorization__version__fiscal_year", "supersedes"),
        public_id=public_id, department_id=department_for_user(request.user).pk)


@budget_permission_required(PREPARE)
def create(request, public_id):
    authority = get_object_or_404(AppropriationAuthorization, public_id=public_id,
        department_id=department_for_user(request.user).pk, status=AppropriationAuthorization.AUTHORIZED)
    form = QuarterlyPlanForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            plan = create_plan(authorization=authority, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("budget:quarterly_detail", public_id=plan.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Prepare quarterly financial plan",
        "guidance": "The complete authorized schedule is copied as planning rows. Enter explicit allocations; approval does not release allotment or certify an obligation. A new version retains the currently approved predecessor."})


@budget_access_required
def detail(request, public_id):
    plan = owned_plan(request, public_id)
    event_page = history_page(plan, request)
    context = plan_context(plan) if plan.status in (plan.DRAFT, plan.RETURNED) else plan.submitted_snapshot
    contributed = request.user.pk in (plan.created_by_id, plan.submitted_by_id) or BudgetAuditEvent.objects.filter(
        target_id=str(plan.public_id), actor_id=request.user.pk,
        action__in=("quarterly_created", "quarterly_line_changed", "quarterly_header_changed", "quarterly_submit")).exists()
    return render(request, "budget/quarterly_detail.html", {"plan": plan, "context": context,
        "is_current": plan.authorization.current_quarterly_plan_id == plan.pk,
        "can_export": has_budget_permission(request.user, "view_allotment_control"),
        "can_prepare": can_act_on_budget(request.user, PREPARE),
        "can_review": can_act_on_budget(request.user, REVIEW) and not contributed,
        "events": event_page.object_list, "event_page": event_page})


@budget_permission_required(PREPARE)
def line_edit(request, public_id, line_id):
    plan = owned_plan(request, public_id)
    line = get_object_or_404(plan.lines, pk=line_id)
    form = QuarterlyPlanLineForm(request.POST if request.method == "POST" else None, instance=line)
    if request.method == "POST" and form.is_valid():
        try:
            edit_line(plan=plan, line_id=line.pk, actor=request.user, values=form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("budget:quarterly_detail", public_id=plan.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Quarter allocations and targets",
        "guidance": f"{line.appropriation_line}. All four amounts are required for submission; use explicit zero where supported. Physical targets remain separate by indicator and unit."})


@require_POST
@budget_access_required
def action(request, public_id, action):
    plan = owned_plan(request, public_id)
    try:
        transition_plan(plan=plan, action=action, actor=request.user, reason=request.POST.get("reason", ""))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Quarterly planning decision recorded. Financial balances are unchanged.")
    return redirect("budget:quarterly_detail", public_id=plan.public_id)


@require_GET
@budget_permission_required("view_allotment_control")
def export(request, public_id):
    from .views import _csv_text
    plan = owned_plan(request, public_id)
    context = plan_context(plan) if plan.status in (plan.DRAFT, plan.RETURNED) else plan.submitted_snapshot
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow(("Plan", "Version", "Status", "As of", "Authority", "Fund", "Office", "PPA", "Account", "Authorized", "Q1", "Q2", "Q3", "Q4", "Planned", "Unplanned (not a reserve)", "Basis", "Indicator", "Unit", "Target Q1", "Target Q2", "Target Q3", "Target Q4"))
    for row in context["rows"]:
        writer.writerow([_csv_text(value if value is not None else "Missing") for value in (
            plan.reference, plan.version, plan.get_status_display(), context["prepared_on"], context["ordinance"],
            row["fund"], row["office"], row["program"], row["account"], row["authorized"], *row["quarters"],
            row["planned"], row["unplanned"], row["basis"], row["indicator"], row["target_unit"], *row["targets"])])
    filename = f"quarterly-plan-{plan.public_id}.csv"
    receipt = archive_export(content=response.content, department=department_for_user(request.user), user=request.user,
        category="budget-quarterly-plan", filename=filename, metadata={"context": context, "spending_authority": False, "status": plan.status})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-SHA256"] = receipt["sha256"]
    record_event(plan, "quarterly_exported", request.user, snapshot={"sha256": receipt["sha256"], "relative_path": receipt["relative_path"]})
    return response

@budget_permission_required(PREPARE)
def edit(request, public_id):
    from .quarterly import edit_header
    plan = owned_plan(request, public_id)
    fields = ("reference", "prepared_on", "evidence_reference", "change_basis")
    form = QuarterlyPlanForm(request.POST if request.method == "POST" else None,
        initial={key: getattr(plan, key) for key in fields})
    if request.method == "POST" and form.is_valid():
        try:
            edit_header(plan=plan, actor=request.user, values=form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("budget:quarterly_detail", public_id=plan.public_id)
    return render(request, "budget/form.html", {"form": form, "title": "Correct planning header",
        "guidance": "Only draft or returned plans may change. Submission retains each version's evidence."})
