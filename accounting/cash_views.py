from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from finance.cash_flows import CASH_FLOW_CHOICES, CASH_FLOW_BY_CODE
from .access import accounting_access_required, department_for_user
from .cash_classifications import can_prepare, can_review, cash_scope, cash_codes, current_version, propose_classification, review_classification
from .models import CashFlowClassification, CashFlowClassificationHead, JournalEntry, JournalLine


class CashAllocationForm(forms.Form):
    journal_line = forms.ModelChoiceField(queryset=JournalLine.objects.none(), label="Posted cash line")
    category = forms.ChoiceField(choices=(("", "Select a cash-flow purpose"),) + CASH_FLOW_CHOICES[1:], label="Cash-flow purpose")
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    def __init__(self, *args, entry, codes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["journal_line"].queryset = entry.lines.filter(account__code__in=codes).select_related("account")
        self.fields["journal_line"].label_from_instance = lambda line: f"Line {line.sequence}: {line.account.code} - {line.debit + line.credit:,.2f}"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class CashProposalForm(forms.Form):
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    reason = forms.CharField(label="Purpose / explanation of this change", widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    evidence_reference = forms.CharField(max_length=255, label="Supporting schedule / document reference",
        widget=forms.TextInput(attrs={"class": "form-control"}))


@require_http_methods(["GET", "POST"])
@accounting_access_required
def classification_page(request, public_id):
    department = department_for_user(request.user)
    entry = get_object_or_404(JournalEntry.objects.select_related("fund", "period"), public_id=public_id, department_id=department.pk)
    prepare = can_prepare(request.user) and entry.status == JournalEntry.POSTED and entry.statement_source_type != "opening"
    if request.method == "POST" and not prepare:
        raise PermissionDenied
    head = CashFlowClassificationHead.objects.select_related("classification").filter(entry=entry).first()
    records = list(entry.cash_classifications.all())
    initial_record = head.classification if head else None
    if records and records[0].status == CashFlowClassification.RETURNED and records[0].proposed_by_id == request.user.pk:
        initial_record = records[0]
    try:
        scope = cash_scope(department)
        scope_error = ""
    except ValidationError as exc:
        scope, scope_error = {}, "; ".join(exc.messages)
    codes = cash_codes(scope)
    cash_lines = list(entry.lines.filter(account__code__in=codes).select_related("account"))
    initial = ([{"journal_line": item["line_id"], "category": item["category"], "amount": item["amount"]}
        for item in initial_record.allocations] if initial_record else
        [{"journal_line": line.pk, "category": line.cash_flow_category, "amount": line.debit + line.credit} for line in cash_lines])
    form = CashProposalForm(request.POST or None, initial={"expected_version": current_version(entry)})
    allocation_set = formset_factory(CashAllocationForm, extra=0, can_delete=True)
    formset = allocation_set(request.POST or None, initial=initial, form_kwargs={"entry": entry, "codes": codes})
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            propose_classification(entry, request.user,
                [{"line_id": row["journal_line"].pk, "category": row["category"], "amount": row["amount"]}
                    for row in formset.cleaned_data if row and not row.get("DELETE")],
                **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Cash-purpose allocations submitted for independent review.")
            return redirect("accounting:cash_classification", public_id=entry.public_id)
    history = []
    for record in records:
        source_lines = {line["line_id"]: line for line in record.source_snapshot["lines"]}
        history.append({"record": record,
            "rows": [{"line": source_lines[item["line_id"]], "amount": item["amount"],
                "purpose": CASH_FLOW_BY_CODE.get(item["category"], ("", "", item["category"]))[2]}
                for item in record.allocations],
            "can_review": can_review(request.user) and record.status == CashFlowClassification.SUBMITTED
                and record.proposed_by_id != request.user.pk})
    return render(request, "accounting/cash_classification.html", {"entry": entry, "form": form, "formset": formset,
        "cash_lines": cash_lines, "can_prepare": prepare and bool(scope), "scope_error": scope_error,
        "current": head.classification if head else None, "history": history})


@require_POST
@accounting_access_required
def classification_review(request, public_id, classification_id, decision):
    record = get_object_or_404(CashFlowClassification.objects.select_related("entry"), public_id=classification_id,
        entry__public_id=public_id, department_id=department_for_user(request.user).pk)
    if decision not in {"approve", "return"}:
        raise PermissionDenied
    try:
        review_classification(record, request.user, approve=decision == "approve", note=request.POST.get("note", ""))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Cash classification approved." if decision == "approve" else "Cash classification returned for correction.")
    return redirect("accounting:cash_classification", public_id=public_id)
