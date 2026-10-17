from uuid import uuid4
from decimal import Decimal

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from vouchers.models import VoucherPostingRequest
from .access import visible_attributions
from .forms import ConfirmProposalForm, ReviewForm
from .journal_mappings import can_act, capture, current, propose, decide, visible_mappings
from .journal_sources import can_inspect_journals

SALT = "gso-recognition-mapping-v1"


class ProposalForm(forms.Form):
    posting_request = forms.ModelChoiceField(queryset=VoucherPostingRequest.objects.none())
    sequence = forms.IntegerField(min_value=1, max_value=32767, label="Journal debit line sequence")
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    basis = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain the documentary relationship between this receipt support and the selected recognition debit.")

    def __init__(self, *args, claim, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["posting_request"].queryset = VoucherPostingRequest.objects.filter(
            case=claim.case, finance_department_id=claim.finance_department_id, kind="recognition", status="posted")
        self.fields["posting_request"].label_from_instance = lambda row: f"{row.jev_number} · recognition version {row.version}"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def workbench(request, attribution_id):
    claim = get_object_or_404(visible_attributions(request.user).select_related("case__configuration_release"),
                             public_id=attribution_id)
    if not can_inspect_journals(request.user, claim.case):
        raise PermissionDenied
    rows = visible_mappings(request.user).filter(claim=claim)
    allowed = can_act(request.user, claim, "propose")
    if request.method == "POST" and not allowed:
        raise PermissionDenied
    form = ProposalForm(request.POST or None, claim=claim)
    preview = confirmation = None
    if request.method == "POST" and request.POST.get("action") == "confirm":
        confirmation = ConfirmProposalForm(request.POST)
        if confirmation.is_valid():
            try:
                payload = signing.loads(confirmation.cleaned_data["proposal_token"], salt=SALT, max_age=1800)
                if payload["actor"] != request.user.pk or payload["claim"] != str(claim.public_id):
                    raise PermissionDenied
                row = propose(actor=request.user, claim_id=claim.public_id,
                    posting_request_id=payload["request"], sequence=payload["sequence"], amount=payload["amount"],
                    basis=payload["basis"], request_id=payload["request_id"], expected_basis=payload["evidence"])
                return redirect("inventory_finance:mapping-detail", mapping_id=row.public_id)
            except signing.BadSignature:
                form.add_error(None, "The preview expired or changed. Preview the current source again.")
            except ValidationError as exc:
                form.add_error(None, exc)
        else:
            form.add_error(None, "Preview the mapping before confirming it.")
    elif request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            evidence = capture(actor=request.user, claim=claim, posting_request_id=data["posting_request"].public_id,
                               sequence=data["sequence"])
            preview = {"actor": request.user.pk, "claim": str(claim.public_id),
                "request": str(data["posting_request"].public_id), "sequence": data["sequence"],
                "amount": str(data["amount"]), "basis": data["basis"], "request_id": str(uuid4()), "evidence": evidence}
            confirmation = ConfirmProposalForm(initial={"proposal_token": signing.dumps(preview, salt=SALT)})
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "inventory_finance/journal_mapping_workbench.html", {
        "claim": claim, "rows": rows, "form": form, "can_propose": allowed,
        "preview": preview, "confirmation": confirmation})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def detail(request, mapping_id):
    row = get_object_or_404(visible_mappings(request.user).select_related("claim__case__configuration_release"), public_id=mapping_id)
    if not can_inspect_journals(request.user, row.claim.case):
        raise PermissionDenied
    issue = ""
    try:
        current(row, request.user)
    except ValidationError as exc:
        issue = " ".join(exc.messages)
    actions = []
    if row.status == row.PROPOSED:
        if row.proposed_by_id != request.user.pk:
            if not issue:
                actions.append(("approve", "Approve mapping"))
            actions.append(("reject", "Reject mapping"))
        actions.append(("withdraw", "Withdraw mapping"))
    elif row.status == row.APPROVED:
        actions.append(("withdraw", "Withdraw mapping"))
    allowed = can_act(request.user, row.claim, "review") and bool(actions)
    form = ReviewForm(request.POST or None, initial={"expected_version": row.state_version})
    form.fields["action"].choices = actions
    if request.method == "POST":
        if not allowed:
            raise PermissionDenied
        if form.is_valid():
            try:
                decide(actor=request.user, mapping_id=row.public_id, expected_version=form.cleaned_data["expected_version"],
                    action=form.cleaned_data["action"], note=form.cleaned_data["note"])
                return redirect("inventory_finance:mapping-detail", mapping_id=row.public_id)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, "inventory_finance/journal_mapping_detail.html", {
        "row": row, "form": form, "can_review": allowed, "issue": issue,
        "events": row.events.select_related("actor")})
