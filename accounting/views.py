import csv
from decimal import Decimal
import hashlib
import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from src.export_archive import archive_export

from .access import (
    accounting_access_required, accounting_permission_required, can_approve_bank_reconciliation, can_approve_fiscal_readiness,
    can_approve_opening_balances, can_govern_setup, can_manage_setup, can_post_journals,
    can_post_opening_balances, can_prepare_journals, can_prepare_opening_balances,
    can_reconcile_controls, can_view_bank_reconciliation, can_view_ledger, department_for_user,
    can_export_bank_reconciliation, can_prepare_bank_reconciliation,
)
from .forms import (
    AccountingPeriodForm, FiscalYearForm, FundForm, FundingSourceForm, JournalEntryForm, JournalLineForm,
    BankMatchForm, BankOutstandingForm, BankStatementBatchCorrectionForm, BankStatementBatchForm,
    BankStatementImportForm, BankUnmatchForm,
    LedgerAccountForm, OpeningBalanceBatchCorrectionForm, OpeningBalanceBatchForm, OpeningBalanceImportForm,
    OpeningBalanceRowCorrectionForm, PostingMappingForm, ProgramActivityProjectForm,
    ResponsibilityCenterForm, ReversalForm,
)
from .models import (
    AccountingAuditEvent, AccountingPeriod, ControlAccountReconciliation, FiscalYear,
    BankOutstandingItem, BankStatementBatch, BankStatementMatch, BankStatementRow,
    FiscalYearReadinessApproval, Fund, FundingSource, JournalEntry, JournalLine,
    JournalSubsidiaryLine, LedgerAccount, OpeningBalanceBatch, OpeningBalanceRow,
    PostingMapping, ProgramActivityProject, ResponsibilityCenter,
)
from .services import (
    adopt_configuration_release, begin_foundation_amendment, close_period, create_reversal,
    auto_match_bank_statement, bank_reconciliation_snapshot, classify_bank_outstanding,
    correct_bank_statement_batch, decide_bank_reconciliation, match_bank_statement_row,
    correct_opening_batch, correct_opening_row, decide_opening_batch, decide_readiness_layer, discard_draft,
    ensure_readiness_layers, evaluate_fiscal_year_readiness, finalize_foundation_amendment,
    post_entry, post_opening_batch, reconcile_opening_batch, record_opening_event, return_entry, stage_opening_csv,
    run_control_reconciliation, subsidiary_schedule_rows, submit_entry, submit_opening_batch,
    record_bank_reconciliation_event, stage_bank_statement_csv, submit_bank_reconciliation, transition_fiscal_year,
    unclassify_bank_outstanding, unmatch_bank_statement_row, validate_bank_statement, validate_opening_batch, control_reconciliation_snapshot,
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
    from vouchers.models import RemittancePostingRequest, VoucherPostingRequest
    source_requests = VoucherPostingRequest.objects.filter(
        finance_department_id=department.pk,
        status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.FAILED, VoucherPostingRequest.MATERIALIZED),
    ).select_related("case")[:50]
    remittance_requests = RemittancePostingRequest.objects.filter(
        finance_department_id=department.pk,
        status__in=(RemittancePostingRequest.PENDING, RemittancePostingRequest.FAILED, RemittancePostingRequest.MATERIALIZED),
    ).select_related("batch", "batch__recipient_party")[:50]
    return render(request, "accounting/workspace.html", {
        "entries": entries[:100], "metrics": metrics, "setup_ready": setup_ready,
        "status_choices": JournalEntry.STATUS_CHOICES, "selected_status": selected_status, "query": query,
        "can_manage_setup": can_manage_setup(request.user), "can_prepare": can_prepare_journals(request.user),
        "can_post": can_post_journals(request.user), "can_view_ledger": can_view_ledger(request.user),
        "can_prepare_opening": can_prepare_opening_balances(request.user),
        "can_approve_opening": can_approve_opening_balances(request.user),
        "can_post_opening": can_post_opening_balances(request.user),
        "can_view_bank_reconciliation": can_view_bank_reconciliation(request.user),
        "source_requests": source_requests, "remittance_requests": remittance_requests,
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


@require_GET
@accounting_permission_required(can_view_bank_reconciliation)
def bank_reconciliation_workspace(request):
    department = department_for_user(request.user)
    batches = BankStatementBatch.objects.filter(department_id=department.pk).select_related("fund")
    metrics = batches.aggregate(
        drafts=Count("pk", filter=Q(status__in=(BankStatementBatch.DRAFT, BankStatementBatch.RETURNED))),
        validated=Count("pk", filter=Q(status=BankStatementBatch.VALIDATED)),
        review=Count("pk", filter=Q(status=BankStatementBatch.FOR_REVIEW)),
        reconciled=Count("pk", filter=Q(status=BankStatementBatch.RECONCILED)),
    )
    return render(request, "accounting/bank_reconciliation_workspace.html", {
        "batches": batches[:100],
        "metrics": metrics,
        "can_prepare_bank": can_prepare_bank_reconciliation(request.user),
    })


@require_GET
@accounting_permission_required(can_view_bank_reconciliation)
def bank_reconciliation_starter(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="bank-statement-import-starter.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow(("transaction_date", "bank_reference", "description", "withdrawal", "deposit", "running_balance"))
    writer.writerow(("2027-01-05", "CHK-000001", "Sample cleared check - replace or remove this starter row", "1250.00", "", "8750.00"))
    writer.writerow(("2027-01-08", "DEP-000001", "Sample cleared deposit - replace or remove this starter row", "", "2500.00", "11250.00"))
    return response


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_create(request):
    department = department_for_user(request.user)
    form = BankStatementBatchForm(request.POST or None, department=department)
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
            record_bank_reconciliation_event(batch, "batch_created", request.user, snapshot={
                "statement_reference": batch.statement_reference,
                "bank_account_code": batch.bank_account_code,
                "fund_code": batch.fund.code,
                "period_start": batch.period_start.isoformat(),
                "period_end": batch.period_end.isoformat(),
            })
            messages.success(request, "Bank-statement reconciliation batch created. Stage the controlled CSV next.")
            return redirect("accounting:bank_reconciliation_detail", public_id=batch.public_id)
    return render(request, "accounting/form.html", {
        "form": form,
        "title": "Create monthly bank reconciliation",
        "cancel_url": "accounting:bank_reconciliation_workspace",
    })


def _bank_batch_for_department(request, public_id):
    department = department_for_user(request.user)
    return get_object_or_404(
        BankStatementBatch.objects.select_related("fund"), public_id=public_id, department_id=department.pk,
    )


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_edit(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    if batch.status not in (BankStatementBatch.DRAFT, BankStatementBatch.VALIDATED, BankStatementBatch.RETURNED):
        messages.error(request, "Only a pre-submission or returned bank reconciliation can be corrected.")
        return redirect("accounting:bank_reconciliation_detail", public_id=public_id)
    department = department_for_user(request.user)
    form = BankStatementBatchCorrectionForm(request.POST or None, instance=batch, department=department)
    if request.method == "POST" and form.is_valid():
        try:
            correct_bank_statement_batch(
                batch, request.user, values=form.cleaned_data, reason=form.cleaned_data["change_reason"],
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Statement controls corrected with before/after evidence. Validate and match again.")
            return redirect("accounting:bank_reconciliation_detail", public_id=public_id)
    return render(request, "accounting/form.html", {
        "form": form,
        "title": f"Correct {batch.statement_reference}",
        "cancel_url": "accounting:bank_reconciliation_detail",
        "cancel_public_id": batch.public_id,
    })


@require_GET
@accounting_permission_required(can_view_bank_reconciliation)
def bank_reconciliation_detail(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    try:
        snapshot, snapshot_checksum, rows, matches, unmatched_lines, items = bank_reconciliation_snapshot(batch)
        setup_error = ""
    except ValidationError as exc:
        snapshot, snapshot_checksum, rows, matches, unmatched_lines, items = {}, "", [], [], [], []
        setup_error = " ".join(exc.messages)
    match_map = {match.statement_row_id: match for match in matches}
    reserved_ids = set(BankStatementMatch.objects.filter(status=BankStatementMatch.ACTIVE).values_list("journal_line_id", flat=True))
    for row in rows:
        row.active_match = match_map.get(row.pk)
        row.candidates = [
            line for line in unmatched_lines
            if line.pk not in reserved_ids
            and row.withdrawal == line.credit and row.deposit == line.debit
        ][:30]
    item_map = {item.journal_line_id: item for item in items}
    for line in unmatched_lines:
        line.active_outstanding_item = item_map.get(line.pk)
    return render(request, "accounting/bank_reconciliation_detail.html", {
        "batch": batch,
        "rows": rows,
        "matches": matches,
        "unmatched_lines": unmatched_lines,
        "items": items,
        "snapshot": snapshot,
        "snapshot_checksum": snapshot_checksum,
        "setup_error": setup_error,
        "import_form": BankStatementImportForm(),
        "can_prepare_bank": can_prepare_bank_reconciliation(request.user),
        "can_approve_bank": can_approve_bank_reconciliation(request.user),
        "can_export_bank": can_export_bank_reconciliation(request.user),
    })


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_stage(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    form = BankStatementImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a UTF-8 bank statement CSV and provide a restaging reason when required.")
    else:
        try:
            staged = stage_bank_statement_csv(
                batch, request.user, form.cleaned_data["source_file"],
                change_reason=form.cleaned_data.get("change_reason", ""),
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            if staged.status == BankStatementBatch.VALIDATED:
                messages.success(request, "Statement source and declared controls validate. Match the rows to posted bank journals.")
            else:
                messages.warning(request, "Statement staged, but the declared or running-balance controls need correction.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_validate(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    try:
        validated = validate_bank_statement(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        if validated.status == BankStatementBatch.VALIDATED:
            messages.success(request, "Statement rows, running balances, and declared controls validate.")
        else:
            messages.warning(request, "Validation found control differences. Correct the batch or restage the source.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_auto_match(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    try:
        count = auto_match_bank_statement(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"Recorded {count} unique exact match(es). Ambiguous rows remain for guided review.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_match(request, public_id, row_id):
    batch = _bank_batch_for_department(request, public_id)
    row = get_object_or_404(BankStatementRow, pk=row_id, batch=batch)
    form = BankMatchForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a candidate journal and record the match basis.")
    else:
        line = get_object_or_404(JournalLine, pk=form.cleaned_data["journal_line_id"])
        try:
            match_bank_statement_row(row, line, request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Statement row {row.row_number} matched with retained evidence.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_unmatch(request, public_id, row_id):
    batch = _bank_batch_for_department(request, public_id)
    row = get_object_or_404(BankStatementRow, pk=row_id, batch=batch)
    form = BankUnmatchForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Explain why the prior match is being superseded.")
    else:
        try:
            unmatch_bank_statement_row(row, request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Statement row {row.row_number} is unmatched; prior evidence remains in history.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_classify(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    form = BankOutstandingForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Complete the outstanding-item explanation, evidence, and expected clearance date.")
    else:
        line = get_object_or_404(JournalLine, pk=form.cleaned_data["journal_line_id"])
        try:
            classify_bank_outstanding(
                batch, line, request.user,
                explanation=form.cleaned_data["explanation"],
                evidence_reference=form.cleaned_data["evidence_reference"],
                expected_clearance_date=form.cleaned_data["expected_clearance_date"],
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Outstanding item classified with expected-clearance evidence.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_unclassify(request, public_id, line_id):
    batch = _bank_batch_for_department(request, public_id)
    line = get_object_or_404(JournalLine, pk=line_id)
    form = BankUnmatchForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Explain why the prior timing-item classification is being superseded.")
    else:
        try:
            unclassify_bank_outstanding(batch, line, request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Timing-item classification removed; prior evidence remains in history.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_prepare_bank_reconciliation)
def bank_reconciliation_submit(request, public_id):
    batch = _bank_batch_for_department(request, public_id)
    try:
        submit_bank_reconciliation(batch, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Zero-difference reconciliation submitted for independent Accounting review.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_POST
@accounting_permission_required(can_approve_bank_reconciliation)
def bank_reconciliation_decide(request, public_id, decision):
    batch = _bank_batch_for_department(request, public_id)
    try:
        decided = decide_bank_reconciliation(
            batch, request.user, decision=decision, evidence_note=request.POST.get("evidence_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        if decided.status == BankStatementBatch.RECONCILED:
            messages.success(request, "Bank reconciliation independently approved and checksummed.")
        else:
            messages.warning(request, "Bank reconciliation returned to the preparer for controlled correction.")
    return redirect("accounting:bank_reconciliation_detail", public_id=public_id)


@require_GET
@accounting_permission_required(can_export_bank_reconciliation)
def bank_reconciliation_export(request, public_id):
    department = department_for_user(request.user)
    batch = get_object_or_404(
        BankStatementBatch.objects.select_related("fund"), public_id=public_id, department_id=department.pk,
    )
    snapshot, checksum, rows, matches, unmatched_lines, items = bank_reconciliation_snapshot(batch)
    match_map = {match.statement_row_id: match for match in matches}
    item_map = {item.journal_line_id: item for item in items}
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    reference = slugify(batch.statement_reference)[:80] or str(batch.public_id)
    filename = f"bank-reconciliation-{reference}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow((
        "record_kind", "statement_reference", "status", "bank_account_code", "fund_code", "period_start",
        "period_end", "source_version", "source_checksum", "row_number", "transaction_date", "bank_reference",
        "description", "withdrawal", "deposit", "running_balance", "journal_reference", "journal_date",
        "journal_line_id", "match_method", "evidence_reference", "expected_clearance_date", "evidence_checksum",
    ))
    for row in rows:
        match = match_map.get(row.pk)
        writer.writerow((
            "statement_row", _csv_text(batch.statement_reference), batch.status, _csv_text(batch.bank_account_code),
            _csv_text(batch.fund.code), batch.period_start, batch.period_end, batch.source_version,
            batch.source_checksum, row.row_number, row.transaction_date, _csv_text(row.bank_reference),
            _csv_text(row.description), row.withdrawal, row.deposit, row.running_balance or "",
            _csv_text(match.journal_line.entry.reference if match else ""),
            match.journal_line.entry.entry_date if match else "", match.journal_line_id if match else "",
            match.method if match else "unmatched", "", "", match.source_checksum if match else row.row_checksum,
        ))
    for line in unmatched_lines:
        item = item_map.get(line.pk)
        writer.writerow((
            "ledger_outstanding" if item else "ledger_unclassified", _csv_text(batch.statement_reference), batch.status,
            _csv_text(batch.bank_account_code), _csv_text(batch.fund.code), batch.period_start, batch.period_end,
            batch.source_version, batch.source_checksum, "", "", "", _csv_text(line.memo), line.credit,
            line.debit, "", _csv_text(line.entry.reference), line.entry.entry_date, line.pk,
            item.kind if item else "", _csv_text(item.evidence_reference if item else ""),
            item.expected_clearance_date if item else "", item.source_checksum if item else "",
        ))
    writer.writerow((
        "reconciliation_control", _csv_text(batch.statement_reference), batch.status, _csv_text(batch.bank_account_code),
        _csv_text(batch.fund.code), batch.period_start, batch.period_end, batch.source_version, batch.source_checksum,
        "", "", "", "adjusted bank / book / difference", snapshot["outstanding_checks"],
        snapshot["outstanding_deposits"], snapshot["statement_closing_balance"], snapshot["book_balance"], "",
        "", "", "", "", checksum,
    ))
    archived = archive_export(
        content=response.content,
        department=department,
        user=request.user,
        category="finance-bank-reconciliation",
        filename=filename,
        metadata={
            "kind": "bank_reconciliation_evidence",
            "batch_public_id": str(batch.public_id),
            "statement_reference": batch.statement_reference,
            "bank_account_code": batch.bank_account_code,
            "fund_code": batch.fund.code,
            "period_end": batch.period_end,
            "status": batch.status,
            "source_checksum": batch.source_checksum,
            "reconciliation_checksum": batch.reconciliation_checksum or checksum,
            "official_status": "controlled working/evidence export; locally accepted official BRS layout remains required",
        },
    )
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    record_bank_reconciliation_event(batch, "exported", request.user, snapshot={
        "relative_path": archived["relative_path"], "sha256": archived["sha256"],
    })
    return response


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
        "entry": entry,
        "lines": entry.lines.select_related("account", "responsibility_center").prefetch_related("subsidiary_posting"),
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
        if posted.source_type in {"voucher", "remittance"}:
            try:
                if posted.source_type == "voucher":
                    from vouchers.posting import reconcile_posted_voucher_entry
                    reconcile_posted_voucher_entry(posted, request.user)
                else:
                    from vouchers.remittances import reconcile_posted_remittance_entry
                    reconcile_posted_remittance_entry(posted, request.user)
            except ValidationError as exc:
                messages.warning(
                    request,
                    "The JEV is safely posted, but its Voucher Workbench handoff needs retry: " + " ".join(exc.messages),
                )
            else:
                messages.success(request, "Source handoff completed; its recorded Finance workflow can now continue.")
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
        if discarded.source_type == "remittance" and discarded.source_reference:
            from vouchers.models import RemittancePostingRequest
            source = RemittancePostingRequest.objects.filter(
                public_id=discarded.source_reference,
                accounting_entry_public_id=discarded.public_id,
            ).exclude(status=RemittancePostingRequest.POSTED).first()
            if source:
                try:
                    from vouchers.remittances import supersede_discarded_request
                    successor = supersede_discarded_request(posting_request=source, actor=request.user, reason=reason)
                except ValidationError as exc:
                    messages.warning(request, "The draft is retained as voided, but its successor handoff needs attention: " + " ".join(exc.messages))
                else:
                    messages.info(request, f"A controlled successor request ({successor.jev_number}) is waiting in Accounting; the actual remittance was not repeated.")
            else:
                messages.warning(request, "The draft was discarded, but its remittance handoff needs administrative reconciliation.")
        elif discarded.source_type == "voucher" and discarded.source_reference:
            from vouchers.models import VoucherPostingRequest
            source = VoucherPostingRequest.objects.filter(
                public_id=discarded.source_reference,
                accounting_entry_public_id=discarded.public_id,
            ).exclude(status=VoucherPostingRequest.POSTED).first()
            if source and source.kind in {"payment", "remittance", "cancellation", "replacement"} and source.resume_stage:
                try:
                    from vouchers.services import supersede_discarded_event_posting_request
                    successor = supersede_discarded_event_posting_request(
                        posting_request=source,
                        actor=request.user,
                        reason=reason,
                    )
                except ValidationError as exc:
                    messages.warning(
                        request,
                        "The draft is safely retained as voided, but its successor handoff needs attention: "
                        + " ".join(exc.messages),
                    )
                else:
                    messages.info(
                        request,
                        f"A controlled successor request ({successor.jev_number}) is waiting in the Accounting workspace.",
                    )
            elif source:
                source.status = VoucherPostingRequest.CANCELLED
                source.failure_reason = (
                    "Draft GRAND JEV was discarded; return the voucher for correction before revalidating."
                )
                source.save(update_fields=("status", "failure_reason"))
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


@require_POST
@accounting_permission_required(can_prepare_journals)
def remittance_source_materialize(request, public_id):
    from vouchers.models import RemittancePostingRequest
    from vouchers.remittances import materialize_remittance_journal
    source = get_object_or_404(RemittancePostingRequest, public_id=public_id)
    try:
        entry, created = materialize_remittance_journal(source, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("accounting:workspace")
    messages.success(request, "Draft GRAND remittance JEV created from the immutable released schedule." if created else "Existing remittance JEV reopened; no duplicate was created.")
    return redirect("accounting:entry_detail", public_id=entry.public_id)


@require_POST
@accounting_permission_required(can_post_journals)
def remittance_source_reconcile(request, public_id):
    from vouchers.models import RemittancePostingRequest
    from vouchers.remittances import reconcile_posted_remittance_entry
    department = department_for_user(request.user)
    source = get_object_or_404(RemittancePostingRequest, public_id=public_id, finance_department_id=department.pk)
    if not source.accounting_entry_public_id:
        messages.error(request, "Create the GRAND remittance JEV before retrying the handoff.")
        return redirect("accounting:workspace")
    entry = get_object_or_404(JournalEntry, public_id=source.accounting_entry_public_id, department_id=department.pk)
    try:
        reconcile_posted_remittance_entry(entry, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Remittance handoff reconciled and completed.")
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


def _archived_csv_response(*, response, request, department, category, filename, metadata):
    archived = archive_export(
        content=response.content,
        department=department,
        user=request.user,
        category=category,
        filename=filename,
        metadata=metadata,
    )
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    response["X-GRAND-Export-Relative-Path"] = archived["relative_path"]
    AccountingAuditEvent.objects.create(
        department_id=department.pk,
        department_label=department.name,
        action="report_exported",
        actor_id=request.user.pk,
        actor_label=request.user.get_full_name() or request.user.username,
        snapshot={
            "category": category,
            "relative_path": archived["relative_path"],
            "sha256": archived["sha256"],
            **metadata,
        },
    )
    return response


@require_GET
@accounting_permission_required(can_view_ledger)
def ledger_export(request):
    department = department_for_user(request.user)
    account_id = request.GET.get("account", "").strip()
    account = LedgerAccount.objects.filter(department_id=department.pk, pk=account_id).first() if account_id.isdigit() else None
    lines = JournalLine.objects.filter(
        entry__department_id=department.pk, entry__status=JournalEntry.POSTED,
    ).select_related("entry", "entry__fund", "account", "responsibility_center").order_by(
        "entry__entry_date", "entry_id", "sequence",
    )
    if account:
        lines = lines.filter(account=account)
    filename = f"general-ledger-{slugify(account.code) if account else 'all-accounts'}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "department", "entry_date", "jev_reference", "entry_public_id", "source_type",
        "source_reference", "fund_code", "account_code", "account_title", "responsibility_center_code",
        "memo", "debit", "credit", "running_normal_balance", "posting_event", "posting_rule_checksum",
    ))
    balances = {}
    row_count = 0
    for line in lines.iterator():
        delta = line.debit - line.credit
        if line.account.normal_balance == "credit":
            delta = -delta
        balances[line.account_id] = balances.get(line.account_id, Decimal("0.00")) + delta
        writer.writerow((
            "posted_general_ledger_line", _csv_text(department.name), line.entry.entry_date,
            _csv_text(line.entry.reference), line.entry.public_id, line.entry.source_type,
            _csv_text(line.entry.source_reference), _csv_text(line.entry.fund.code),
            _csv_text(line.account.code), _csv_text(line.account.title),
            _csv_text(line.responsibility_center.code if line.responsibility_center else ""),
            _csv_text(line.memo), line.debit, line.credit, balances[line.account_id],
            _csv_text(line.entry.source_snapshot.get("posting_event", "")),
            _csv_text(line.entry.source_snapshot.get("posting_rule_checksum", "")),
        ))
        row_count += 1
    return _archived_csv_response(
        response=response, request=request, department=department,
        category="finance-general-ledger", filename=filename,
        metadata={
            "kind": "posted_general_ledger_export",
            "account_code": account.code if account else "all",
            "row_count": row_count,
            "official_status": "controlled data interchange; not automatically an official COA/local form",
        },
    )


@require_GET
@accounting_permission_required(can_view_ledger)
def trial_balance_export(request):
    department = department_for_user(request.user)
    rows = LedgerAccount.objects.filter(department_id=department.pk).annotate(
        debit_total=Sum("journal_lines__debit", filter=Q(journal_lines__entry__status=JournalEntry.POSTED)),
        credit_total=Sum("journal_lines__credit", filter=Q(journal_lines__entry__status=JournalEntry.POSTED)),
    ).order_by("code")
    filename = "trial-balance-posted.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "department", "account_code", "account_title", "account_type",
        "debit", "credit", "net_debit", "net_credit",
    ))
    totals = {"debit": Decimal("0.00"), "credit": Decimal("0.00")}
    row_count = 0
    for account in rows:
        debit = account.debit_total or Decimal("0.00")
        credit = account.credit_total or Decimal("0.00")
        net = debit - credit
        writer.writerow((
            "posted_trial_balance_account", _csv_text(department.name), _csv_text(account.code),
            _csv_text(account.title), account.account_type, debit, credit,
            net if net > 0 else Decimal("0.00"), -net if net < 0 else Decimal("0.00"),
        ))
        totals["debit"] += debit
        totals["credit"] += credit
        row_count += 1
    writer.writerow((
        "posted_trial_balance_total", _csv_text(department.name), "", "TOTAL", "",
        totals["debit"], totals["credit"], "", "",
    ))
    return _archived_csv_response(
        response=response, request=request, department=department,
        category="finance-trial-balance", filename=filename,
        metadata={
            "kind": "posted_trial_balance_export", "row_count": row_count,
            "total_debit": str(totals["debit"]), "total_credit": str(totals["credit"]),
            "balanced": totals["debit"] == totals["credit"],
            "official_status": "controlled data interchange; not automatically an official COA/local form",
        },
    )


def _report_as_of(raw_value):
    value = parse_date((raw_value or "").strip())
    today = timezone.localdate()
    if value is None:
        return today
    return min(value, today)


@require_GET
@accounting_permission_required(can_view_ledger)
def subsidiary_controls(request):
    department = department_for_user(request.user)
    as_of_date = _report_as_of(request.GET.get("as_of"))
    payables = subsidiary_schedule_rows(department.pk, JournalSubsidiaryLine.PAYABLE, as_of_date)
    withholdings = subsidiary_schedule_rows(department.pk, JournalSubsidiaryLine.WITHHOLDING, as_of_date)
    snapshot, _checksum = control_reconciliation_snapshot(department.pk, as_of_date)

    def totals(rows):
        return {
            "debit": sum((row["debit"] for row in rows), Decimal("0.00")),
            "credit": sum((row["credit"] for row in rows), Decimal("0.00")),
            "balance": sum((row["balance"] for row in rows), Decimal("0.00")),
        }

    return render(request, "accounting/subsidiary_controls.html", {
        "as_of_date": as_of_date,
        "payables": payables,
        "withholdings": withholdings,
        "payable_totals": totals(payables),
        "withholding_totals": totals(withholdings),
        "current_reconciliation": snapshot,
        "runs": ControlAccountReconciliation.objects.filter(department_id=department.pk)[:25],
        "can_reconcile": can_reconcile_controls(request.user),
    })


@require_POST
@accounting_permission_required(can_reconcile_controls)
def subsidiary_reconcile(request):
    department = department_for_user(request.user)
    raw_as_of = (request.POST.get("as_of") or "").strip()
    as_of_date = parse_date(raw_as_of) if raw_as_of else timezone.localdate()
    try:
        if as_of_date is None:
            raise ValidationError("Enter a valid reconciliation date.")
        run = run_control_reconciliation(department, request.user, as_of_date)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        if run.is_balanced:
            messages.success(request, "The configured control accounts reconcile to subsidiary detail.")
        else:
            messages.warning(
                request,
                f"Reconciliation recorded with an absolute difference of {run.absolute_difference_total:.2f}.",
            )
    redirect_date = as_of_date if as_of_date and as_of_date <= timezone.localdate() else timezone.localdate()
    return redirect(f"{reverse('accounting:subsidiary_controls')}?as_of={redirect_date.isoformat()}")


@require_GET
@accounting_permission_required(can_view_ledger)
def subsidiary_export(request, category):
    if category not in dict(JournalSubsidiaryLine.CATEGORY_CHOICES):
        raise Http404
    department = department_for_user(request.user)
    as_of_date = _report_as_of(request.GET.get("as_of"))
    rows = subsidiary_schedule_rows(department.pk, category, as_of_date)
    filename = f"{category}-subsidiary-through-{as_of_date.isoformat()}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "department", "as_of_date", "category", "fund_code", "control_account_code",
        "control_account_title", "reference_key", "reference_label", "source_code",
        "debit_movements", "credit_movements", "credit_balance",
    ))
    for row in rows:
        writer.writerow((
            "posted_subsidiary_schedule", _csv_text(department.name), as_of_date, category,
            _csv_text(row["fund_code"]), _csv_text(row["account_code"]), _csv_text(row["account_title"]),
            _csv_text(row["reference_key"]), _csv_text(row["reference_label"]), _csv_text(row["source_code"]),
            row["debit"], row["credit"], row["balance"],
        ))
    return _archived_csv_response(
        response=response, request=request, department=department,
        category=f"finance-{category}-subsidiary", filename=filename,
        metadata={
            "kind": "posted_subsidiary_schedule", "subsidiary_category": category,
            "as_of_date": as_of_date.isoformat(), "row_count": len(rows),
            "official_status": "controlled data interchange; not automatically an official COA/local schedule",
        },
    )


@require_GET
@accounting_permission_required(can_view_ledger)
def subsidiary_reconciliation_export(request, public_id):
    department = department_for_user(request.user)
    run = get_object_or_404(
        ControlAccountReconciliation, public_id=public_id, department_id=department.pk,
    )
    encoded = json.dumps(run.result_snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != run.result_checksum:
        return HttpResponse(
            "The stored control-reconciliation checksum no longer matches its evidence. Contact an administrator.",
            status=409,
            content_type="text/plain; charset=utf-8",
        )
    filename = f"control-reconciliation-{run.as_of_date.isoformat()}-{str(run.public_id)[:8]}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow((
        "export_kind", "department", "as_of_date", "result_checksum", "category", "fund_code",
        "control_account_code", "control_account_title", "mapping_codes", "gl_credit_balance",
        "subsidiary_credit_balance", "difference", "balanced",
    ))
    for row in run.result_snapshot.get("rows", []):
        writer.writerow((
            "control_account_reconciliation", _csv_text(department.name), run.as_of_date,
            run.result_checksum, row["category"], _csv_text(row["fund_code"]),
            _csv_text(row["account_code"]), _csv_text(row["account_title"]),
            _csv_text(" | ".join(row["mapping_codes"])), row["gl_balance"],
            row["subsidiary_balance"], row["difference"], row["balanced"],
        ))
    return _archived_csv_response(
        response=response, request=request, department=department,
        category="finance-control-reconciliation", filename=filename,
        metadata={
            "kind": "control_account_reconciliation", "reconciliation_public_id": str(run.public_id),
            "as_of_date": run.as_of_date.isoformat(), "result_checksum": run.result_checksum,
            "balanced": run.is_balanced,
            "absolute_difference_total": str(run.absolute_difference_total),
            "official_status": "controlled reconciliation evidence; local review and acceptance still apply",
        },
    )
