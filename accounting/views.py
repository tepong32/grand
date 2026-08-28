import csv
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from src.export_archive import archive_export

from .access import (
    accounting_access_required, accounting_permission_required, can_approve_fiscal_readiness,
    can_approve_opening_balances, can_govern_setup, can_manage_setup, can_post_journals,
    can_post_opening_balances, can_prepare_journals, can_prepare_opening_balances,
    can_view_ledger, department_for_user,
)
from .forms import (
    AccountingPeriodForm, FiscalYearForm, FundForm, FundingSourceForm, JournalEntryForm, JournalLineForm,
    LedgerAccountForm, OpeningBalanceBatchCorrectionForm, OpeningBalanceBatchForm, OpeningBalanceImportForm,
    OpeningBalanceRowCorrectionForm, PostingMappingForm, ProgramActivityProjectForm,
    ResponsibilityCenterForm, ReversalForm,
)
from .models import (
    AccountingPeriod, FiscalYear, FiscalYearReadinessApproval, Fund, FundingSource, JournalEntry,
    JournalLine, LedgerAccount, OpeningBalanceBatch, OpeningBalanceRow, PostingMapping,
    ProgramActivityProject, ResponsibilityCenter,
)
from .services import (
    adopt_configuration_release, begin_foundation_amendment, close_period, create_reversal,
    correct_opening_batch, correct_opening_row, decide_opening_batch, decide_readiness_layer, discard_draft,
    ensure_readiness_layers, evaluate_fiscal_year_readiness, finalize_foundation_amendment,
    post_entry, post_opening_batch, reconcile_opening_batch, record_opening_event, return_entry, stage_opening_csv,
    submit_entry, submit_opening_batch, transition_fiscal_year, validate_opening_batch,
)


SETUP_TYPES = {
    "fiscal-years": (FiscalYear, FiscalYearForm, "Fiscal year"),
    "periods": (AccountingPeriod, AccountingPeriodForm, "Accounting period"),
    "funds": (Fund, FundForm, "Fund"),
    "centers": (ResponsibilityCenter, ResponsibilityCenterForm, "Responsibility center"),
    "accounts": (LedgerAccount, LedgerAccountForm, "Ledger account"),
    "funding-sources": (FundingSource, FundingSourceForm, "Funding source"),
    "programs": (ProgramActivityProject, ProgramActivityProjectForm, "PPA / MFO / project / activity"),
    "mappings": (PostingMapping, PostingMappingForm, "Posting mapping"),
}

FOUNDATION_EDIT_TYPES = (
    FiscalYear, AccountingPeriod, Fund, ResponsibilityCenter, LedgerAccount,
    FundingSource, ProgramActivityProject,
)


def _department_values(department):
    return {"department_id": department.pk, "department_label": department.name}


def _form_for_setup(kind, *args, department, **kwargs):
    try:
        _model, form_class, _label = SETUP_TYPES[kind]
    except KeyError as exc:
        raise Http404 from exc
    return form_class(*args, department=department, **kwargs)


@require_GET
@accounting_access_required
def workspace(request):
    department = department_for_user(request.user)
    entries = JournalEntry.objects.filter(department_id=department.pk).select_related("fund", "period")
    selected_status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    if selected_status in dict(JournalEntry.STATUS_CHOICES):
        entries = entries.filter(status=selected_status)
    else:
        selected_status = ""
    if query:
        entries = entries.filter(Q(reference__icontains=query) | Q(description__icontains=query))
    metrics = JournalEntry.objects.filter(department_id=department.pk).aggregate(
        drafts=Count("pk", filter=Q(status=JournalEntry.DRAFT)),
        submitted=Count("pk", filter=Q(status=JournalEntry.SUBMITTED)),
        posted=Count("pk", filter=Q(status=JournalEntry.POSTED)),
    )
    setup_ready = all((
        AccountingPeriod.objects.filter(department_id=department.pk, status=AccountingPeriod.OPEN).exists(),
        Fund.objects.filter(department_id=department.pk, is_active=True).exists(),
        LedgerAccount.objects.filter(department_id=department.pk, is_active=True, allow_posting=True).exists(),
    ))
    from vouchers.models import VoucherPostingRequest
    source_requests = VoucherPostingRequest.objects.filter(
        finance_department_id=department.pk,
        status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.FAILED, VoucherPostingRequest.MATERIALIZED),
    ).select_related("case")[:50]
    return render(request, "accounting/workspace.html", {
        "entries": entries[:100], "metrics": metrics, "setup_ready": setup_ready,
        "status_choices": JournalEntry.STATUS_CHOICES, "selected_status": selected_status, "query": query,
        "can_manage_setup": can_manage_setup(request.user), "can_prepare": can_prepare_journals(request.user),
        "can_post": can_post_journals(request.user), "can_view_ledger": can_view_ledger(request.user),
        "can_prepare_opening": can_prepare_opening_balances(request.user),
        "can_approve_opening": can_approve_opening_balances(request.user),
        "can_post_opening": can_post_opening_balances(request.user),
        "source_requests": source_requests,
    })


@require_GET
@accounting_permission_required(can_govern_setup)
def setup_workspace(request):
    department = department_for_user(request.user)
    fiscal_year_rows = []
    for fiscal_year in FiscalYear.objects.filter(department_id=department.pk):
        fiscal_year_rows.append({"record": fiscal_year, "readiness": evaluate_fiscal_year_readiness(fiscal_year)})
    from finance.models import FinanceConfigurationRelease
    return render(request, "accounting/setup.html", {
        "fiscal_year_rows": fiscal_year_rows,
        "periods": AccountingPeriod.objects.filter(department_id=department.pk),
        "funds": Fund.objects.filter(department_id=department.pk),
        "centers": ResponsibilityCenter.objects.filter(department_id=department.pk),
        "accounts": LedgerAccount.objects.filter(department_id=department.pk).select_related("parent"),
        "mappings": PostingMapping.objects.filter(department_id=department.pk).select_related("account"),
        "funding_sources": FundingSource.objects.filter(department_id=department.pk).select_related("fiscal_year", "fund"),
        "programs": ProgramActivityProject.objects.filter(department_id=department.pk).select_related(
            "fiscal_year", "parent", "responsibility_center", "funding_source",
        ),
        "releases": FinanceConfigurationRelease.objects.filter(
            department=department, status__in=("approved", "scheduled", "active", "superseded"),
        ),
        "can_approve_readiness": can_approve_fiscal_readiness(request.user),
        "can_manage_setup": can_manage_setup(request.user),
    })


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_manage_setup)
def setup_item_create(request, kind):
    department = department_for_user(request.user)
    form = _form_for_setup(kind, request.POST or None, department=department)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        for field, value in _department_values(department).items():
            setattr(item, field, value)
        if isinstance(item, FiscalYear):
            item.created_by_id = request.user.pk
            item.created_by_label = request.user.get_full_name() or request.user.username
        item.full_clean()
        item.save()
        if isinstance(item, FiscalYear):
            ensure_readiness_layers(item)
        messages.success(request, f"{SETUP_TYPES[kind][2]} created.")
        return redirect("accounting:setup")
    return render(request, "accounting/form.html", {"form": form, "title": f"Add {SETUP_TYPES[kind][2].lower()}", "cancel_url": "accounting:setup"})


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_manage_setup)
def setup_item_edit(request, kind, pk):
    department = department_for_user(request.user)
    try:
        model, _form_class, label = SETUP_TYPES[kind]
    except KeyError as exc:
        raise Http404 from exc
    item = get_object_or_404(model, pk=pk, department_id=department.pk)
    requires_change_reason = isinstance(item, FOUNDATION_EDIT_TYPES)
    amendment_context = None
    amendment_error = None
    if request.method == "POST" and requires_change_reason:
        try:
            amendment_context = begin_foundation_amendment(
                item, request.user, request.POST.get("change_reason", ""),
            )
        except ValidationError as exc:
            amendment_error = " ".join(exc.messages)
        else:
            item._governed_amendment = True
    form = _form_for_setup(kind, request.POST or None, instance=item, department=department)
    if amendment_error:
        form.add_error(None, amendment_error)
    if request.method == "POST" and form.is_valid() and (not requires_change_reason or amendment_context is not None):
        try:
            with transaction.atomic(using="finance"):
                saved = form.save()
                if amendment_context is not None:
                    finalize_foundation_amendment(saved, request.user, amendment_context)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, f"{label} updated. Affected readiness approvals were reopened.")
            return redirect("accounting:setup")
    return render(request, "accounting/form.html", {
        "form": form, "title": f"Edit {label.lower()}", "cancel_url": "accounting:setup",
        "requires_change_reason": requires_change_reason,
        "change_reason": request.POST.get("change_reason", ""),
    })


@require_POST
@accounting_permission_required(can_manage_setup)
def setup_item_toggle(request, kind, pk):
    department = department_for_user(request.user)
    if kind not in ("funds", "centers", "accounts", "mappings", "funding-sources", "programs"):
        raise Http404
    model, _form_class, label = SETUP_TYPES[kind]
    item = get_object_or_404(model, pk=pk, department_id=department.pk)
    if item.is_active:
        if kind == "funds":
            in_progress = item.journal_entries.exclude(status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).exists()
        elif kind in ("centers", "accounts"):
            in_progress = item.journal_lines.exclude(entry__status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).exists()
        elif kind in ("funding-sources", "programs"):
            in_progress = False
        else:
            in_progress = False
        if in_progress:
            messages.error(request, f"{label} is used by unfinished journals and cannot be archived yet.")
            return redirect("accounting:setup")
    item.is_active = not item.is_active
    try:
        item.full_clean()
        item.save(update_fields=("is_active",))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("accounting:setup")
    messages.success(request, f"{label} {'activated' if item.is_active else 'archived'}.")
    return redirect("accounting:setup")


@require_POST
@accounting_permission_required(can_manage_setup)
def configuration_release_adopt(request, pk):
    department = department_for_user(request.user)
    from finance.models import FinanceConfigurationRelease
    release = get_object_or_404(FinanceConfigurationRelease, pk=pk, department=department)
    try:
        fiscal_year, counts = adopt_configuration_release(
            release, request.user, change_reason=request.POST.get("change_reason", ""),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(
            request,
            f"Adopted {release} into {fiscal_year}. New records: "
            f"{counts['funds']} funds, {counts['centers']} centers, {counts['accounts']} accounts, "
            f"{counts['funding_sources']} funding sources, {counts['classifications']} classifications; "
            f"{len(counts['skipped'])} item(s) need review.",
        )
    return redirect("accounting:setup")


@require_POST
@accounting_access_required
def fiscal_year_transition(request, pk, action):
    department = department_for_user(request.user)
    fiscal_year = get_object_or_404(FiscalYear, pk=pk, department_id=department.pk)
    try:
        transition_fiscal_year(fiscal_year, action, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"Fiscal year {action} completed.")
    return redirect("accounting:setup")


@require_POST
@accounting_permission_required(can_approve_fiscal_readiness)
def readiness_decision(request, pk, decision):
    department = department_for_user(request.user)
    layer = get_object_or_404(FiscalYearReadinessApproval, pk=pk, department_id=department.pk)
    try:
        decide_readiness_layer(
            layer, request.user, decision=decision, evidence_note=request.POST.get("evidence_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"{layer.get_layer_display()} marked {decision}.")
    return redirect("accounting:setup")


@require_POST
@accounting_permission_required(can_manage_setup)
def period_close(request, pk):
    department = department_for_user(request.user)
    period = get_object_or_404(AccountingPeriod, pk=pk, department_id=department.pk)
    try:
        close_period(period, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Accounting period closed. New postings to it are blocked.")
    return redirect("accounting:setup")


@require_GET
@accounting_access_required
def opening_workspace(request):
    department = department_for_user(request.user)
    batches = OpeningBalanceBatch.objects.filter(department_id=department.pk).select_related(
        "fiscal_year", "period",
    )
    metrics = batches.aggregate(
        staging=Count("pk", filter=Q(status__in=(OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED))),
        review=Count("pk", filter=Q(status__in=(OpeningBalanceBatch.VALIDATED, OpeningBalanceBatch.FOR_REVIEW))),
        approved=Count("pk", filter=Q(status__in=(OpeningBalanceBatch.APPROVED, OpeningBalanceBatch.POSTED))),
        reconciled=Count("pk", filter=Q(status=OpeningBalanceBatch.RECONCILED)),
    )
    return render(request, "accounting/opening_workspace.html", {
        "batches": batches,
        "metrics": metrics,
        "can_prepare_opening": can_prepare_opening_balances(request.user),
        "can_approve_opening": can_approve_opening_balances(request.user),
        "can_post_opening": can_post_opening_balances(request.user),
    })


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_opening_balances)
def opening_create(request):
    department = department_for_user(request.user)
    form = OpeningBalanceBatchForm(request.POST or None, department=department)
    if request.method == "POST" and form.is_valid():
        batch = form.save(commit=False)
        batch.department_id = department.pk
        batch.department_label = department.name
        batch.created_by_id = request.user.pk
        batch.created_by_label = request.user.get_full_name() or request.user.username
        try:
            batch.full_clean()
            batch.save()
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Opening-balance staging batch created. Stage the CSV or validate the zero-balance declaration.")
            return redirect("accounting:opening_detail", public_id=batch.public_id)
    return render(request, "accounting/form.html", {
        "form": form,
        "title": "Create opening-balance staging batch",
        "cancel_url": "accounting:opening_workspace",
    })


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_opening_balances)
def opening_edit(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    if batch.status not in (OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED):
        messages.error(request, "Only a draft or returned opening batch can be corrected.")
        return redirect("accounting:opening_detail", public_id=public_id)
    form = OpeningBalanceBatchCorrectionForm(request.POST or None, instance=batch, department=department)
    if request.method == "POST" and form.is_valid():
        try:
            correct_opening_batch(
                batch,
                request.user,
                values=form.cleaned_data,
                reason=form.cleaned_data["change_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Declared opening controls corrected with before/after evidence. Validate again.")
            return redirect("accounting:opening_detail", public_id=public_id)
    return render(request, "accounting/form.html", {
        "form": form,
        "title": "Correct declared opening controls",
        "cancel_url": "accounting:opening_detail",
        "cancel_public_id": batch.public_id,
    })


@require_GET
@accounting_access_required
def opening_detail(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(
        OpeningBalanceBatch.objects.select_related("fiscal_year", "period"),
        public_id=public_id,
        department_id=department.pk,
    )
    return render(request, "accounting/opening_detail.html", {
        "batch": batch,
        "rows": batch.rows.select_related("fund", "account", "responsibility_center")[:500],
        "row_count": batch.rows.count(),
        "postings": batch.postings.select_related("fund", "entry"),
        "events": batch.events.all()[:50],
        "import_form": OpeningBalanceImportForm(),
        "can_prepare_opening": can_prepare_opening_balances(request.user),
        "can_approve_opening": can_approve_opening_balances(request.user),
        "can_post_opening": can_post_opening_balances(request.user),
    })


def _csv_text(value):
    value = str(value or "")
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@require_GET
@accounting_access_required
def opening_export(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(
        OpeningBalanceBatch.objects.select_related("fiscal_year", "period"),
        public_id=public_id,
        department_id=department.pk,
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename_reference = slugify(batch.source_reference)[:80] or str(batch.public_id)
    response["Content-Disposition"] = f'attachment; filename="opening-{filename_reference}.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "department", "fiscal_year", "period", "batch_reference", "batch_status",
        "source_checksum", "declared_row_count", "declared_debit", "declared_credit", "row_number",
        "fund_code", "account_code", "responsibility_center_code", "debit", "credit",
        "subsidiary_reference", "memo", "validation_status", "validation_errors",
    ))
    rows = batch.rows.order_by("row_number", "pk")
    if batch.is_zero_balance_declaration and not rows.exists():
        writer.writerow((
            "opening_zero_declaration", _csv_text(batch.department_label), batch.fiscal_year.year,
            _csv_text(batch.period.label), _csv_text(batch.source_reference), batch.status,
            batch.source_checksum, batch.expected_row_count,
            batch.expected_debit, batch.expected_credit, "", "", "", "", "0.00", "0.00", "", "",
            "valid" if batch.validation_summary.get("valid") else "pending", "",
        ))
    else:
        for row in rows:
            writer.writerow((
                "opening_balance_row", _csv_text(batch.department_label), batch.fiscal_year.year,
                _csv_text(batch.period.label), _csv_text(batch.source_reference), batch.status,
                batch.source_checksum, batch.expected_row_count, batch.expected_debit, batch.expected_credit,
                row.row_number, _csv_text(row.raw_fund_code), _csv_text(row.raw_account_code),
                _csv_text(row.raw_responsibility_center_code), row.debit, row.credit,
                _csv_text(row.subsidiary_reference), _csv_text(row.memo), row.validation_status,
                _csv_text(" | ".join(row.validation_errors)),
            ))
    archived = archive_export(
        content=response.content,
        department=department,
        user=request.user,
        category="finance-opening-balances",
        filename=f"opening-{filename_reference}.csv",
        metadata={
            "kind": "opening_balance_control_export",
            "batch_public_id": str(batch.public_id),
            "source_reference": batch.source_reference,
            "source_checksum": batch.source_checksum,
            "fiscal_year": batch.fiscal_year.year,
            "period": batch.period.label,
            "status": batch.status,
            "state_version": batch.state_version,
            "official_status": "controlled data interchange; not automatically an official form",
        },
    )
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    record_opening_event(
        batch,
        "exported",
        request.user,
        snapshot={"relative_path": archived["relative_path"], "sha256": archived["sha256"]},
    )
    return response


@require_POST
@accounting_permission_required(can_prepare_opening_balances)
def opening_stage(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    form = OpeningBalanceImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a UTF-8 CSV source file.")
    else:
        try:
            staged = stage_opening_csv(batch, request.user, form.cleaned_data["source_file"])
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            if staged.status == OpeningBalanceBatch.VALIDATED:
                messages.success(request, "The source rows and declared control totals validate with zero difference.")
            else:
                messages.warning(request, "The CSV was staged, but row or control-total differences require correction.")
    return redirect("accounting:opening_detail", public_id=batch.public_id)


@require_POST
@accounting_permission_required(can_prepare_opening_balances)
def opening_validate(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    try:
        validated = validate_opening_batch(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        if validated.status == OpeningBalanceBatch.VALIDATED:
            messages.success(request, "All staged rows, fund balances, and declared control totals validate.")
        else:
            messages.warning(request, "Validation completed with differences. Correct the flagged rows or source controls.")
    return redirect("accounting:opening_detail", public_id=batch.public_id)


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_opening_balances)
def opening_row_edit(request, public_id, pk):
    department = department_for_user(request.user)
    row = get_object_or_404(
        OpeningBalanceRow.objects.select_related("batch"),
        pk=pk,
        batch__public_id=public_id,
        batch__department_id=department.pk,
    )
    form = OpeningBalanceRowCorrectionForm(request.POST or None, row=row)
    if request.method == "POST" and form.is_valid():
        try:
            correct_opening_row(
                row,
                request.user,
                values=form.cleaned_data,
                reason=form.cleaned_data["change_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, f"Staged row {row.row_number} corrected. Validate the batch again.")
            return redirect("accounting:opening_detail", public_id=public_id)
    return render(request, "accounting/form.html", {
        "form": form,
        "title": f"Correct staged opening row {row.row_number}",
        "cancel_url": "accounting:opening_detail",
        "cancel_public_id": row.batch.public_id,
    })


@require_POST
@accounting_permission_required(can_prepare_opening_balances)
def opening_submit(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    try:
        submit_opening_batch(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Opening controls submitted for independent review.")
    return redirect("accounting:opening_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_approve_opening_balances)
def opening_decide(request, public_id, decision):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    try:
        decide_opening_batch(
            batch,
            request.user,
            decision=decision,
            evidence_note=request.POST.get("evidence_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"Opening batch {decision} with retained decision evidence.")
    return redirect("accounting:opening_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_post_opening_balances)
def opening_post(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    try:
        post_opening_batch(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Opening JEVs posted. Run the separate reconciliation check to close the control gate.")
    return redirect("accounting:opening_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_post_opening_balances)
def opening_reconcile(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(OpeningBalanceBatch, public_id=public_id, department_id=department.pk)
    try:
        _batch, summary = reconcile_opening_batch(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        if summary["reconciled"]:
            messages.success(request, "Opening balances reconcile to posted JEVs with zero unexplained difference.")
        else:
            messages.error(request, "Posted totals do not reconcile. The immutable failure evidence was retained for investigation.")
    return redirect("accounting:opening_detail", public_id=public_id)


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_journals)
def entry_create(request):
    department = department_for_user(request.user)
    form = JournalEntryForm(request.POST or None, department=department)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.department_id = department.pk
        entry.department_label = department.name
        entry.created_by_id = request.user.pk
        entry.created_by_label = request.user.get_full_name() or request.user.username
        entry.full_clean()
        entry.save()
        messages.success(request, "Draft journal created. Add debit and credit lines next.")
        return redirect("accounting:entry_detail", public_id=entry.public_id)
    return render(request, "accounting/form.html", {"form": form, "title": "Create journal entry", "cancel_url": "accounting:workspace"})


def _entry_for_department(request, public_id):
    department = department_for_user(request.user)
    return get_object_or_404(
        JournalEntry.objects.select_related("period", "fund", "reversal_of"), public_id=public_id, department_id=department.pk,
    )


@require_GET
@accounting_access_required
def entry_detail(request, public_id):
    entry = _entry_for_department(request, public_id)
    debit, credit = entry.totals
    reversal_entries = JournalEntry.objects.filter(reversal_of=entry).order_by("-pk")
    reversal_entry = reversal_entries.first()
    active_reversal_entry = reversal_entries.exclude(status=JournalEntry.VOIDED).first()
    return render(request, "accounting/entry_detail.html", {
        "entry": entry, "lines": entry.lines.select_related("account", "responsibility_center"),
        "debit_total": debit, "credit_total": credit, "balanced": debit > 0 and debit == credit,
        "can_prepare": can_prepare_journals(request.user), "can_post": can_post_journals(request.user),
        "reversal_entry": reversal_entry, "active_reversal_entry": active_reversal_entry,
    })


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_journals)
def entry_edit(request, public_id):
    entry = _entry_for_department(request, public_id)
    if entry.status != JournalEntry.DRAFT:
        raise PermissionDenied("Only draft journals can be edited.")
    if entry.source_reference:
        raise PermissionDenied("Generated journal headers cannot be edited. Discard and recreate the source draft instead.")
    department = department_for_user(request.user)
    form = JournalEntryForm(request.POST or None, instance=entry, department=department)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Journal header updated.")
        return redirect("accounting:entry_detail", public_id=entry.public_id)
    return render(request, "accounting/form.html", {"form": form, "title": f"Edit {entry.reference}", "cancel_object": entry})


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_journals)
def line_create(request, public_id):
    entry = _entry_for_department(request, public_id)
    if entry.status != JournalEntry.DRAFT:
        raise PermissionDenied("Lines can be added only to draft journals.")
    if entry.source_reference:
        raise PermissionDenied("Generated journal lines cannot be edited. Discard and recreate the source draft instead.")
    department = department_for_user(request.user)
    next_sequence = (entry.lines.aggregate(value=Max("sequence"))["value"] or 0) + 1
    form = JournalLineForm(request.POST or None, department=department, entry=entry, initial={"sequence": next_sequence})
    if request.method == "POST" and form.is_valid():
        line = form.save(commit=False)
        line.entry = entry
        line.full_clean()
        line.save()
        messages.success(request, "Journal line added.")
        return redirect("accounting:entry_detail", public_id=entry.public_id)
    return render(request, "accounting/form.html", {"form": form, "title": f"Add line to {entry.reference}", "cancel_object": entry})


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_journals)
def line_edit(request, public_id, pk):
    entry = _entry_for_department(request, public_id)
    if entry.status != JournalEntry.DRAFT:
        raise PermissionDenied("Lines can be edited only on draft journals.")
    if entry.source_reference:
        raise PermissionDenied("Generated journal lines cannot be edited. Discard and recreate the source draft instead.")
    line = get_object_or_404(JournalLine, pk=pk, entry=entry)
    form = JournalLineForm(request.POST or None, instance=line, department=department_for_user(request.user), entry=entry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Journal line updated.")
        return redirect("accounting:entry_detail", public_id=entry.public_id)
    return render(request, "accounting/form.html", {"form": form, "title": f"Edit line {line.sequence}", "cancel_object": entry})


@require_POST
@accounting_permission_required(can_prepare_journals)
def line_delete(request, public_id, pk):
    entry = _entry_for_department(request, public_id)
    if entry.status != JournalEntry.DRAFT:
        raise PermissionDenied("Lines can be removed only from draft journals.")
    if entry.source_reference:
        raise PermissionDenied("Generated journal lines cannot be edited. Discard and recreate the source draft instead.")
    line = get_object_or_404(JournalLine, pk=pk, entry=entry)
    line.delete()
    messages.success(request, "Journal line removed.")
    return redirect("accounting:entry_detail", public_id=entry.public_id)


def _transition(request, public_id, operation, success_message, reason=""):
    entry = _entry_for_department(request, public_id)
    try:
        operation(entry, request.user, reason) if reason is not None and operation in (return_entry, discard_draft) else operation(entry, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, success_message)
    return redirect("accounting:entry_detail", public_id=entry.public_id)


@require_POST
@accounting_permission_required(can_prepare_journals)
def entry_submit(request, public_id):
    return _transition(request, public_id, submit_entry, "Journal submitted for independent posting.", reason=None)


@require_POST
@accounting_permission_required(can_post_journals)
def entry_post(request, public_id):
    entry = _entry_for_department(request, public_id)
    try:
        posted = post_entry(entry, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Journal posted to the general ledger.")
        if posted.source_type == "voucher":
            try:
                from vouchers.posting import reconcile_posted_voucher_entry
                reconcile_posted_voucher_entry(posted, request.user)
            except ValidationError as exc:
                messages.warning(
                    request,
                    "The JEV is safely posted, but its Voucher Workbench handoff needs retry: " + " ".join(exc.messages),
                )
            else:
                messages.success(request, "Voucher handoff completed; Treasury can now prepare the payment instrument.")
    return redirect("accounting:entry_detail", public_id=entry.public_id)


@require_POST
@accounting_permission_required(can_post_journals)
def entry_return(request, public_id):
    return _transition(request, public_id, return_entry, "Journal returned to the preparer.", request.POST.get("reason", ""))


@require_POST
@accounting_permission_required(can_prepare_journals)
def entry_discard(request, public_id):
    entry = _entry_for_department(request, public_id)
    reason = request.POST.get("reason", "")
    try:
        discarded = discard_draft(entry, request.user, reason)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Draft journal discarded and retained in the audit trail.")
        if discarded.source_type == "voucher" and discarded.source_reference:
            from vouchers.models import VoucherPostingRequest
            updated = VoucherPostingRequest.objects.filter(
                public_id=discarded.source_reference,
                accounting_entry_public_id=discarded.public_id,
            ).exclude(status=VoucherPostingRequest.POSTED).update(
                status=VoucherPostingRequest.CANCELLED,
                failure_reason="Draft GRAND JEV was discarded; return the voucher for correction before revalidating.",
            )
            if updated:
                messages.info(request, "The voucher posting request was cancelled and can now be returned for correction.")
            else:
                messages.warning(request, "The draft was discarded, but its voucher handoff needs administrative reconciliation.")
    return redirect("accounting:entry_detail", public_id=entry.public_id)


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_journals)
def entry_reverse(request, public_id):
    entry = _entry_for_department(request, public_id)
    if entry.status != JournalEntry.POSTED:
        raise PermissionDenied("Only posted journals can be reversed.")
    department = department_for_user(request.user)
    form = ReversalForm(
        request.POST or None,
        department=department,
        initial={"reference": f"REV-{entry.reference}"[:60], "entry_date": entry.entry_date},
    )
    if request.method == "POST" and form.is_valid():
        try:
            reversal = create_reversal(entry, request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Reversing journal prepared. It must pass the normal independent submit-and-post workflow.")
            return redirect("accounting:entry_detail", public_id=reversal.public_id)
    return render(request, "accounting/form.html", {
        "form": form,
        "title": f"Prepare reversal for {entry.reference}",
        "cancel_object": entry,
    })


@require_POST
@accounting_permission_required(can_prepare_journals)
def voucher_source_materialize(request, public_id):
    from vouchers.models import VoucherPostingRequest
    from vouchers.posting import materialize_voucher_journal
    source = get_object_or_404(VoucherPostingRequest, public_id=public_id)
    try:
        entry, created = materialize_voucher_journal(source, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("accounting:workspace")
    messages.success(request, "Draft GRAND JEV created from the immutable voucher snapshot." if created else "Existing GRAND JEV reopened; no duplicate was created.")
    return redirect("accounting:entry_detail", public_id=entry.public_id)


@require_POST
@accounting_permission_required(can_post_journals)
def voucher_source_reconcile(request, public_id):
    from vouchers.models import VoucherPostingRequest
    from vouchers.posting import reconcile_posted_voucher_entry
    department = department_for_user(request.user)
    source = get_object_or_404(VoucherPostingRequest, public_id=public_id, finance_department_id=department.pk)
    if not source.accounting_entry_public_id:
        messages.error(request, "Create the GRAND JEV before retrying the handoff.")
        return redirect("accounting:workspace")
    entry = get_object_or_404(JournalEntry, public_id=source.accounting_entry_public_id, department_id=department.pk)
    try:
        reconcile_posted_voucher_entry(entry, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Voucher handoff reconciled; Treasury can continue.")
    return redirect("accounting:entry_detail", public_id=entry.public_id)


@require_GET
@accounting_permission_required(can_view_ledger)
def ledger(request):
    department = department_for_user(request.user)
    accounts = LedgerAccount.objects.filter(department_id=department.pk)
    selected_account = request.GET.get("account", "").strip()
    lines = JournalLine.objects.filter(
        entry__department_id=department.pk, entry__status=JournalEntry.POSTED,
    ).select_related("entry", "entry__fund", "account", "responsibility_center").order_by("entry__entry_date", "entry_id", "sequence")
    account = None
    if selected_account.isdigit():
        account = accounts.filter(pk=int(selected_account)).first()
        if account:
            lines = lines.filter(account=account)
    balances = {}
    rows = []
    for line in lines[:1000]:
        delta = line.debit - line.credit
        if line.account.normal_balance == "credit":
            delta = -delta
        balances[line.account_id] = balances.get(line.account_id, Decimal("0.00")) + delta
        rows.append((line, balances[line.account_id]))
    return render(request, "accounting/ledger.html", {"rows": rows, "accounts": accounts, "selected_account": account})


@require_GET
@accounting_permission_required(can_view_ledger)
def trial_balance(request):
    department = department_for_user(request.user)
    rows = list(LedgerAccount.objects.filter(department_id=department.pk).annotate(
        debit_total=Sum("journal_lines__debit", filter=Q(journal_lines__entry__status=JournalEntry.POSTED)),
        credit_total=Sum("journal_lines__credit", filter=Q(journal_lines__entry__status=JournalEntry.POSTED)),
    ).order_by("code"))
    totals = {"debit": Decimal("0.00"), "credit": Decimal("0.00")}
    for row in rows:
        row.debit_total = row.debit_total or Decimal("0.00")
        row.credit_total = row.credit_total or Decimal("0.00")
        totals["debit"] += row.debit_total
        totals["credit"] += row.credit_total
    return render(request, "accounting/trial_balance.html", {"rows": rows, "totals": totals})
