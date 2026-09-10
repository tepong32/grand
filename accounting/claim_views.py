from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from uuid import uuid4
from decimal import Decimal

from finance.models import FinanceParty
from .access import accounting_access_required, can_prepare_journals, can_post_journals, department_for_user
from .claim_attributions import current, propose, review, identity, allocation_rows
from .models import JournalEntry, JournalLine, PayableClaimAttribution


class AttributionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    party_key = forms.ChoiceField(label="Payee")
    claim_reference = forms.CharField(max_length=120, label="Invoice / original claim reference")
    applications = forms.ModelMultipleChoiceField(queryset=JournalLine.objects.none(), required=False,
        label="Earlier applications and their reversals", widget=forms.SelectMultiple(attrs={"size": 10}),
        help_text="Select all prior payments, deductions or reductions for this claim, including their posted reversals. Each selected liability line belongs wholly to this claim.")
    evidence_reference = forms.CharField(max_length=255, label="Supporting reconciliation schedule / documents")
    reason = forms.CharField(label="Basis and explanation", widget=forms.Textarea(attrs={"rows": 3}))
    complete_history = forms.BooleanField(label="I checked the supporting schedule and included all prior applications and reversals for this claim.")

    def __init__(self, *args, source, **kwargs):
        super().__init__(*args, **kwargs)
        parties = FinanceParty.objects.filter(department_id=source.entry.department_id,
            status__in=("approved", "scheduled", "active", "superseded")).order_by("code", "-version")
        choices = {}
        for party in parties:
            choices.setdefault(f"finance-party:{party.code}", f"{party.display_name} ({party.code})")
        prior_party = identity(source)[0]
        if prior_party:
            choices.setdefault(prior_party, prior_party)
        self.fields["party_key"].choices = [("", "Select the payee"), *choices.items()]
        self.fields["applications"].queryset = JournalLine.objects.filter(
            entry__department_id=source.entry.department_id, entry__fund_id=source.entry.fund_id,
            entry__status=JournalEntry.POSTED, entry__entry_date__gte=source.entry.entry_date,
            account_id=source.account_id, payable_origin__isnull=True, payable_reservation__isnull=True,
            payable_party_key="", payable_claim_reference="").exclude(pk=source.pk).exclude(
                entry__source_type__in=("voucher", "remittance")).select_related("entry")
        self.fields["applications"].label_from_instance = lambda line: (
            f"{line.entry.entry_date} · {line.entry.reference} / line {line.sequence} · debit {line.debit:,.2f} / credit {line.credit:,.2f}")
        for name, field in self.fields.items():
            if name != "complete_history":
                field.widget.attrs["class"] = "form-control"


class InvoiceAllocationForm(forms.Form):
    key = forms.UUIDField(required=False, widget=forms.HiddenInput)
    party_key = forms.ChoiceField(label="Payee")
    claim_reference = forms.CharField(max_length=120, label="Invoice reference")
    recognized = forms.DecimalField(max_digits=18, decimal_places=2,
        min_value=Decimal("0.01"), label="Original invoice amount")

    def __init__(self, *args, parties, applications, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["party_key"].choices = parties
        self.application_lines = applications
        for line in applications:
            self.fields[f"share_{line.pk}"] = forms.DecimalField(required=False,
                max_digits=18, decimal_places=2, min_value=0,
                label=f"{line.entry.reference} / line {line.sequence} ({line.entry.entry_date}; "
                      f"{'debit' if line.debit else 'restoring credit'} {line.debit or line.credit:,.2f})")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        for name, field in self.fields.items():
            if not field.widget.is_hidden:
                width = "18rem" if name == "party_key" else "12rem" if name == "claim_reference" else "9rem"
                field.widget.attrs["style"] = f"min-width: {width};"

    def allocation(self):
        data = self.cleaned_data
        return {"key": str(data.get("key") or uuid4()), "party_key": data["party_key"],
            "claim_reference": data["claim_reference"], "recognized": str(data["recognized"]),
            "applications": {str(line.pk): str(data[f"share_{line.pk}"])
                for line in self.application_lines if data.get(f"share_{line.pk}")}}


@require_http_methods(["GET", "POST"])
@accounting_access_required
def attribution_page(request, line_id):
    source = get_object_or_404(JournalLine.objects.select_related("entry__fund", "account"), pk=line_id,
        entry__department_id=department_for_user(request.user).pk)
    can_prepare = can_prepare_journals(request.user) and source.entry.status == JournalEntry.POSTED
    if request.method == "POST" and not can_prepare:
        raise PermissionDenied
    selected = current(source)
    if selected and selected.shared_proposal_id:
        return redirect('accounting:shared_claim_schedule', line_id=source.pk)
    split_mode = request.GET.get("mode") == "split" or bool(selected and selected.is_split)
    seed = selected
    # A returned proposal is copied into a new version, never edited in place.
    latest = source.claim_attributions.order_by("-version").first()
    if latest and latest.status == PayableClaimAttribution.RETURNED and latest.base_version == (selected.version if selected else 0):
        seed = latest
        split_mode = split_mode or seed.is_split
    form = AttributionForm(request.POST or None, source=source, initial={
        "expected_version": selected.version if selected else 0,
        "party_key": identity(source)[0], "claim_reference": identity(source)[1],
        "applications": seed.applications if seed else []})
    invoices = None
    if split_mode:
        parties = list(form.fields["party_key"].choices)
        form.fields.pop("party_key")
        form.fields.pop("claim_reference")
        form.fields["applications"].help_text = "Select every earlier application and reversal, then refresh the invoice table. Allocate each selected line in full across the invoices."
        application_ids = request.POST.getlist("applications") if request.method == "POST" else (seed.applications if seed else [])
        application_ids = [int(pk) for pk in application_ids if str(pk).isdigit()]
        lines = list(form.fields["applications"].queryset.filter(pk__in=application_ids).order_by("entry__entry_date", "pk"))
        initial = [{"key": row["key"], "party_key": row["party_key"],
            "claim_reference": row["claim_reference"], "recognized": row["recognized"],
            **{f"share_{pk}": amount for pk, amount in row["applications"].items()}}
            for row in allocation_rows(seed)] if seed and seed.is_split else []
        for row in initial:
            if row["party_key"] not in dict(parties):
                parties.append((row["party_key"], row["party_key"]))
        factory = forms.formset_factory(InvoiceAllocationForm, extra=max(0, 2-len(initial)),
            can_delete=True, min_num=0, max_num=100, validate_max=True, absolute_max=100)
        posted = request.POST.copy() if request.method == "POST" else None
        if posted is not None and posted.get("action") == "add_invoice":
            try:
                count = int(posted.get("invoices-TOTAL_FORMS", "0"))
                posted["invoices-TOTAL_FORMS"] = str(min(100, max(0, count)+1))
            except ValueError:
                pass
        invoices = factory(posted, initial=initial, prefix="invoices",
            form_kwargs={"parties": parties, "applications": lines})
    if request.method == "POST" and request.POST.get("action", "submit") == "submit" and form.is_valid() and (invoices is None or invoices.is_valid()):
        data = dict(form.cleaned_data)
        data.pop("complete_history")
        data["applications"] = list(data["applications"].values_list("pk", flat=True))
        if invoices is not None:
            data["allocations"] = [row.allocation() for row in invoices
                if row.cleaned_data and not row.cleaned_data.get("DELETE")]
        try:
            propose(source, request.user, **data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Claim attribution submitted for independent review.")
            return redirect("accounting:claim_attribution", line_id=source.pk)
    records = []
    for record in source.claim_attributions.all():
        lines = list(JournalLine.objects.filter(pk__in=record.applications).select_related("entry"))
        by_id = {str(line.pk): line for line in lines}
        rows = [{**row, "application_rows": [{"line": by_id.get(pk), "amount": amount}
            for pk, amount in row["applications"].items()]} for row in allocation_rows(record)] if record.is_split else []
        records.append({"record": record, "can_review": can_post_journals(request.user)
            and record.status == PayableClaimAttribution.SUBMITTED and record.proposed_by_id != request.user.pk,
            "lines": lines, "allocations": rows})
    return render(request, "accounting/claim_attribution.html", {"source": source, "current": selected,
        "form": form, "invoices": invoices, "split_mode": split_mode,
        "can_prepare": can_prepare, "records": records})


@require_POST
@accounting_access_required
def attribution_review(request, line_id, public_id, decision):
    record = get_object_or_404(PayableClaimAttribution, public_id=public_id, source_id=line_id,
        department_id=department_for_user(request.user).pk)
    if decision not in {"approve", "return"}:
        raise PermissionDenied
    try:
        review(record, request.user, approve=decision == "approve", note=request.POST.get("note", ""))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Claim attribution approved." if decision == "approve" else "Attribution returned for correction.")
    return redirect("accounting:claim_attribution", line_id=line_id)
