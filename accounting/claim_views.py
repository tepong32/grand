from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from finance.models import FinanceParty
from .access import accounting_access_required, can_prepare_journals, can_post_journals, department_for_user
from .claim_attributions import current, propose, review, identity
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


@require_http_methods(["GET", "POST"])
@accounting_access_required
def attribution_page(request, line_id):
    source = get_object_or_404(JournalLine.objects.select_related("entry__fund", "account"), pk=line_id,
        entry__department_id=department_for_user(request.user).pk)
    can_prepare = can_prepare_journals(request.user) and source.entry.status == JournalEntry.POSTED
    if request.method == "POST" and not can_prepare:
        raise PermissionDenied
    selected = current(source)
    form = AttributionForm(request.POST or None, source=source, initial={
        "expected_version": selected.version if selected else 0,
        "party_key": identity(source)[0], "claim_reference": identity(source)[1],
        "applications": selected.applications if selected else []})
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        data.pop("complete_history")
        data["applications"] = list(data["applications"].values_list("pk", flat=True))
        try:
            propose(source, request.user, **data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Claim attribution submitted for independent review.")
            return redirect("accounting:claim_attribution", line_id=source.pk)
    records = [{"record": record, "can_review": can_post_journals(request.user)
        and record.status == PayableClaimAttribution.SUBMITTED and record.proposed_by_id != request.user.pk,
        "lines": JournalLine.objects.filter(pk__in=record.applications).select_related("entry")}
        for record in source.claim_attributions.all()]
    return render(request, "accounting/claim_attribution.html", {"source": source, "current": selected,
        "form": form, "can_prepare": can_prepare, "records": records})


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
