from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Max, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .access import (
    accounting_access_required, accounting_permission_required, can_manage_setup,
    can_post_journals, can_prepare_journals, can_view_ledger, department_for_user,
)
from .forms import (
    AccountingPeriodForm, FundForm, JournalEntryForm, JournalLineForm,
    LedgerAccountForm, PostingMappingForm, ResponsibilityCenterForm, ReversalForm,
)
from .models import AccountingPeriod, Fund, JournalEntry, JournalLine, LedgerAccount, PostingMapping, ResponsibilityCenter
from .services import close_period, create_reversal, discard_draft, post_entry, return_entry, submit_entry


SETUP_TYPES = {
    "periods": (AccountingPeriod, AccountingPeriodForm, "Accounting period"),
    "funds": (Fund, FundForm, "Fund"),
    "centers": (ResponsibilityCenter, ResponsibilityCenterForm, "Responsibility center"),
    "accounts": (LedgerAccount, LedgerAccountForm, "Ledger account"),
    "mappings": (PostingMapping, PostingMappingForm, "Posting mapping"),
}


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
        "source_requests": source_requests,
    })


@require_GET
@accounting_permission_required(can_manage_setup)
def setup_workspace(request):
    department = department_for_user(request.user)
    return render(request, "accounting/setup.html", {
        "periods": AccountingPeriod.objects.filter(department_id=department.pk),
        "funds": Fund.objects.filter(department_id=department.pk),
        "centers": ResponsibilityCenter.objects.filter(department_id=department.pk),
        "accounts": LedgerAccount.objects.filter(department_id=department.pk).select_related("parent"),
        "mappings": PostingMapping.objects.filter(department_id=department.pk).select_related("account"),
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
        item.full_clean()
        item.save()
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
    form = _form_for_setup(kind, request.POST or None, instance=item, department=department)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{label} updated.")
        return redirect("accounting:setup")
    return render(request, "accounting/form.html", {"form": form, "title": f"Edit {label.lower()}", "cancel_url": "accounting:setup"})


@require_POST
@accounting_permission_required(can_manage_setup)
def setup_item_toggle(request, kind, pk):
    department = department_for_user(request.user)
    if kind not in ("funds", "centers", "accounts", "mappings"):
        raise Http404
    model, _form_class, label = SETUP_TYPES[kind]
    item = get_object_or_404(model, pk=pk, department_id=department.pk)
    if item.is_active:
        if kind == "funds":
            in_progress = item.journal_entries.exclude(status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).exists()
        elif kind in ("centers", "accounts"):
            in_progress = item.journal_lines.exclude(entry__status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).exists()
        else:
            in_progress = False
        if in_progress:
            messages.error(request, f"{label} is used by unfinished journals and cannot be archived yet.")
            return redirect("accounting:setup")
    item.is_active = not item.is_active
    item.save(update_fields=("is_active",))
    messages.success(request, f"{label} {'activated' if item.is_active else 'archived'}.")
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
