import uuid
import csv
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from finance.models import FinancePostingRule
from vouchers.advance_sources import disbursement, original
from vouchers.advance_applications import prepare, materialize, withdraw, applications, capacity
from vouchers.models import VoucherPostingRequest, TreasuryCollectionSource
from .access import accounting_permission_required, can_view_advances, can_export_advances, can_prepare_journals, can_post_journals, department_for_user
from .models import JournalSubsidiaryLine, LedgerAccount


class LiquidationForm(forms.Form):
    day = forms.DateField(label="Liquidation date", widget=forms.DateInput(attrs={"type":"date"}))
    rule = forms.ModelChoiceField(queryset=FinancePostingRule.objects.none(), label="Reviewed accounting basis")
    document_reference = forms.CharField(max_length=240, label="Liquidation document reference")
    key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rule"].queryset = FinancePostingRule.objects.filter(variant__department=owner,
            variant__kind__in=("cash_advance", "liquidation"),
            event_kind=FinancePostingRule.LIQUIDATION, recognition_point=FinancePostingRule.LIQUIDATION_ACCEPTANCE,
            variant__status__in=("approved", "active"), variant__release__status__in=("approved", "active"))
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = "form-control"


class LiquidationCorrectionForm(forms.Form):
    day = forms.DateField(label='Correction date', widget=forms.DateInput(attrs={'type':'date', 'class':'form-control'}))
    reason = forms.CharField(label='Why the posted liquidation is incorrect',
        widget=forms.Textarea(attrs={'rows':3, 'class':'form-control'}))
    key = forms.UUIDField(widget=forms.HiddenInput)


class ExpenseForm(forms.Form):
    account = forms.ChoiceField(label="Expense account")
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    document_reference = forms.CharField(max_length=240, label="Expense document reference")

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].choices = [("", "Choose an expense account")] + [
            (item.code, f"{item.code} — {item.title}") for item in LedgerAccount.objects.filter(
                department_id=owner.pk, account_type="expense", is_active=True, allow_posting=True).order_by("code")]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


@require_http_methods(["GET", "POST"])
@accounting_permission_required(can_view_advances)
def detail(request, pk):
    owner = department_for_user(request.user)
    source = get_object_or_404(JournalSubsidiaryLine.objects.select_related("entry", "journal_line"),
        pk=pk, category=JournalSubsidiaryLine.ADVANCE, debit__gt=0, entry__department_id=owner.pk,
        entry__source_snapshot__advance_application_correction__isnull=True)
    form = LiquidationForm(request.POST or None, owner=owner, initial={"day":timezone.localdate(), "key":uuid.uuid4()})
    FormSet = forms.formset_factory(ExpenseForm, extra=1, max_num=100, validate_max=True, min_num=1, validate_min=True)
    expenses = FormSet(request.POST or None, prefix="expenses", form_kwargs={"owner":owner})
    if request.method == "POST":
        if not can_prepare_journals(request.user):
            raise PermissionDenied
        if form.is_valid() and expenses.is_valid():
            try:
                application = prepare(detail=source, actor=request.user, rule=form.cleaned_data["rule"],
                    day=form.cleaned_data["day"], key=str(form.cleaned_data["key"]),
                    evidence_reference=form.cleaned_data["document_reference"], expenses=[
                        {"account_code": row.cleaned_data["account"], "amount":row.cleaned_data["amount"],
                         "document_reference":row.cleaned_data["document_reference"]}
                        for row in expenses if row.cleaned_data])
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                try:
                    entry, _ = materialize(application, request.user)
                except ValidationError as exc:
                    messages.error(request, " ".join(exc.messages) + " The retained request is available below for recovery or independent withdrawal.")
                    return redirect("accounting:advance_detail", pk=source.pk)
                return redirect("accounting:entry_detail", public_id=entry.public_id)
    proof, issue = None, ""
    retained = list(VoucherPostingRequest.objects.filter(finance_department_id=owner.pk,
        payload__advance_application__original_detail=source.pk).order_by("pk"))
    retained_corrections = list(VoucherPostingRequest.objects.filter(finance_department_id=owner.pk,
        payload__advance_application_correction__original_detail=source.pk).order_by('pk'))
    active_corrections = {item.payload['advance_application_correction']['original_request']: item
        for item in retained_corrections if item.status != VoucherPostingRequest.CANCELLED}
    for item in retained:
        item.current_correction = active_corrections.get(str(item.public_id))
    try:
        proof = disbursement(source, timezone.localdate())
        _, recognition, _ = original(source)
        proof["applied_or_reserved"] = sum((Decimal(item.payload["advance_application"]["amount"])
            for item in applications(recognition.case, source)), Decimal("0"))
        from vouchers.advance_refunds import movements
        proof['applied_or_reserved'] += sum((value for day, value in movements(source)
            if day <= timezone.localdate()), Decimal('0'))
        from vouchers.liquidation_corrections import restored_movements
        proof['applied_or_reserved'] += sum((value for application in applications(recognition.case, source)
            for day, value in restored_movements(application) if day <= timezone.localdate()), Decimal('0'))
        proof["remaining"] = proof["released_net"] - proof["applied_or_reserved"]
        capacity(source, timezone.localdate(), Decimal("0"))
    except ValidationError as exc:
        issue = " ".join(exc.messages)
    source_request = VoucherPostingRequest.objects.select_related('case').filter(public_id=source.source_reference).first()
    recognition_corrections = VoucherPostingRequest.objects.filter(finance_department_id=owner.pk,
        payload__advance_recognition_correction__original_detail=source.pk).order_by('pk')
    can_correct_recognition = bool(source_request and source_request.status == VoucherPostingRequest.POSTED
        and source_request.case.current_stage == 'treasury_check_preparation'
        and not source_request.case.payment_instruments.exists()
        and not recognition_corrections.exclude(status=VoucherPostingRequest.CANCELLED).exists())
    return render(request, "accounting/advance_detail.html", {"source":source, "proof":proof, "issue":issue,
        "recognition_corrections":recognition_corrections, "can_correct_recognition":can_correct_recognition,
        "original_recognition_has_correction":recognition_corrections.exclude(status=VoucherPostingRequest.CANCELLED).exists(),
        "form":form, "expenses":expenses, "applications":retained,
        "refunds":TreasuryCollectionSource.objects.filter(
            finance_department_id=owner.pk, proposal__advance_refund__original_detail=source.pk),
        "corrections":retained_corrections,
        "can_prepare":can_prepare_journals(request.user), "can_review":can_post_journals(request.user)})


@require_http_methods(['GET', 'POST'])
@accounting_permission_required(lambda user: can_prepare_journals(user) and can_view_advances(user))
def correct(request, public_id):
    from vouchers.liquidation_corrections import prepare as prepare_correction, materialize as make_correction
    owner = department_for_user(request.user)
    application = get_object_or_404(VoucherPostingRequest, public_id=public_id,
        finance_department_id=owner.pk, status=VoucherPostingRequest.POSTED)
    data = application.payload.get('advance_application')
    if not data:
        raise PermissionDenied
    form = LiquidationCorrectionForm(request.POST or None, initial={'day':timezone.localdate(), 'key':uuid.uuid4()})
    if request.method == 'POST' and form.is_valid():
        try:
            correction = prepare_correction(application=application, actor=request.user, day=form.cleaned_data['day'],
                reason=form.cleaned_data['reason'], key=str(form.cleaned_data['key']))
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            try:
                entry, _ = make_correction(correction, request.user)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages) + ' The retained correction is available on the original advance for recovery.')
                return redirect('accounting:advance_detail', pk=data['original_detail'])
            return redirect('accounting:entry_detail', public_id=entry.public_id)
    return render(request, 'accounting/advance_correction.html', {'application':application, 'original':data, 'form':form})


@require_POST
@accounting_permission_required(can_view_advances)
def action(request, public_id, action):
    owner = department_for_user(request.user)
    application = get_object_or_404(VoucherPostingRequest, public_id=public_id, finance_department_id=owner.pk)
    data = (application.payload.get("advance_application") or application.payload.get('advance_application_correction')
            or application.payload.get('advance_recognition_correction'))
    if not data:
        raise PermissionDenied
    try:
        if action == "recover":
            from vouchers.posting import materialize_voucher_journal
            entry, _ = materialize_voucher_journal(application, request.user)
            return redirect("accounting:entry_detail", public_id=entry.public_id)
        if action == "withdraw":
            if application.payload.get('advance_recognition_correction'):
                from vouchers.advance_recognition_corrections import withdraw as withdraw_recognition
                withdraw_recognition(application, request.user, request.POST.get('reason', ''))
            else:
                withdraw(application, request.user, request.POST.get("reason", ""))
            messages.success(request, "The unposted advance request was withdrawn; its history is retained.")
        else:
            raise PermissionDenied
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("accounting:advance_detail", pk=data["original_detail"])


@require_http_methods(['GET', 'POST'])
@accounting_permission_required(lambda user: can_prepare_journals(user) and can_view_advances(user))
def correct_recognition(request, pk):
    from vouchers.advance_recognition_corrections import prepare as prepare_correction
    from vouchers.posting import materialize_voucher_journal
    owner = department_for_user(request.user)
    source = get_object_or_404(JournalSubsidiaryLine.objects.select_related('entry'), pk=pk,
        category=JournalSubsidiaryLine.ADVANCE, debit__gt=0, entry__department_id=owner.pk)
    form = LiquidationCorrectionForm(request.POST or None, initial={'day':timezone.localdate(), 'key':uuid.uuid4()})
    form.fields['reason'].label = 'Why the original unpaid advance is incorrect'
    if request.method == 'POST' and form.is_valid():
        try:
            correction = prepare_correction(detail=source, actor=request.user, day=form.cleaned_data['day'],
                reason=form.cleaned_data['reason'], key=str(form.cleaned_data['key']))
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            try:
                entry, _ = materialize_voucher_journal(correction, request.user)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages) + ' Recover the retained correction from the original advance.')
                return redirect('accounting:advance_detail', pk=source.pk)
            return redirect('accounting:entry_detail', public_id=entry.public_id)
    return render(request, 'accounting/advance_recognition_correction.html', {'source':source, 'form':form})


@require_http_methods(["GET"])
@accounting_permission_required(can_view_advances)
def register(request):
    owner = department_for_user(request.user)
    sources = JournalSubsidiaryLine.objects.filter(category=JournalSubsidiaryLine.ADVANCE,
        debit__gt=0, entry__department_id=owner.pk, entry__status="posted", entry__source_type='voucher',
        entry__entry_date__lte=timezone.localdate()).exclude(
            entry__source_snapshot__has_key='advance_application_correction').select_related("entry", "entry__fund")
    query = (request.GET.get("q") or "").strip()
    if query:
        sources = sources.filter(Q(reference_label__icontains=query) | Q(entry__reference__icontains=query))
    return render(request, "accounting/advance_register.html", {
        "page":Paginator(sources.order_by("-entry__entry_date", "-pk"),50).get_page(request.GET.get("page")),
        "query":query, "can_export":can_export_advances(request.user)})


@require_http_methods(["GET"])
@accounting_permission_required(can_view_advances)
def export(request):
    if not can_export_advances(request.user):
        raise PermissionDenied
    from .services import subsidiary_schedule_rows
    from .views import _archived_csv_response, _csv_text
    owner = department_for_user(request.user)
    day = timezone.localdate()
    rows = subsidiary_schedule_rows(owner.pk, JournalSubsidiaryLine.ADVANCE, day)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"recognized-officer-advances-{day.isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow(("as_of_date","fund_code","account_code","officer_key","officer","debits","credits","recognized_balance"))
    for row in rows:
        writer.writerow((day, _csv_text(row["fund_code"]), _csv_text(row["account_code"]),
            _csv_text(row["reference_key"]), _csv_text(row["reference_label"]),row["debit"],row["credit"],row["balance"]))
    return _archived_csv_response(response=response,request=request,department=owner,
        category="finance-advance-subsidiary",filename=filename,
        metadata={"kind":"recognized_officer_advances","as_of_date":day.isoformat(),"row_count":len(rows),
            "balance_basis":"recognized debit balance, not cash-release or liquidation authority"})
