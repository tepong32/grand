from uuid import uuid4

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from accounting.models import Fund, LedgerAccount, ResponsibilityCenter
from departments.models import Department
from inventory import property_determinations as properties
from inventory.models import PropertyDetermination
from . import property_links as service
from . import journal_mappings

SALT = "gso-property-finance-link-v1"


def style_fields(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class RequestForm(forms.Form):
    finance_department = forms.ModelChoiceField(queryset=Department.objects.none(), label="Finance owner department")
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
    source_token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["finance_department"].queryset = Department.objects.exclude(name="---select one---").order_by("name", "pk")
        self.fields["finance_department"].label_from_instance = lambda row: f"{row.name} ({row.slug or 'No office code'})"
        style_fields(self)


class ProposalForm(forms.Form):
    as_of = forms.DateField(label="Documented association date", widget=forms.DateInput(attrs={"type": "date"}))
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    account = forms.ModelChoiceField(queryset=LedgerAccount.objects.none())
    center = forms.ModelChoiceField(queryset=ResponsibilityCenter.objects.none(), required=False,
        help_text="Select only if the supplied source identifies an accounting responsibility center; physical custody is separate.")
    mapping = forms.ModelChoiceField(queryset=journal_mappings.Mapping.objects.none(), required=False,
        label="Reviewed recognition mapping (optional)", help_text="Legacy and donated property can use the supplied document without a voucher.")
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, actor, row, **kwargs):
        super().__init__(*args, **kwargs)
        for field, model in (("fund", Fund), ("account", LedgerAccount), ("center", ResponsibilityCenter)):
            self.fields[field].queryset = model.objects.filter(department_id=row.finance_department_id, is_active=True).order_by("code")
        self.fields["account"].queryset = self.fields["account"].queryset.filter(allow_posting=True, account_type__in=("asset", "expense"))
        self.fields["mapping"].queryset = journal_mappings.visible_mappings(actor).filter(status="approved",
            claim__receipt_line__registered_asset_id=row.determination.asset_id,
            claim__finance_department_id=row.finance_department_id)
        self.fields["mapping"].label_from_instance = lambda row: f"{row.public_id} · journal line {row.line_sequence} · {row.amount}"
        style_fields(self)


class DecisionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


@login_required
@never_cache
@require_GET
def workbench(request):
    rows = service.visible(request.user).select_related("determination__asset", "finance_department")
    return render(request, "inventory_finance/property_links.html", {"page": Paginator(rows, 25).get_page(request.GET.get("page"))})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def request_link(request, determination_id):
    determination = get_object_or_404(properties.visible(request.user).select_related("asset"), public_id=determination_id)
    if not service.gso_allowed(request.user, determination, "request"):
        raise PermissionDenied
    issue, basis = "", None
    try:
        basis = service.property_basis(determination)
    except ValidationError as error:
        issue = " ".join(error.messages)
    previous = determination.finance_links.order_by("-pk").first()
    token = signing.dumps({"actor": request.user.pk, "property": str(determination.public_id),
        "basis": basis, "predecessor": str(previous.public_id) if previous else None, "request": str(uuid4())}, salt=SALT)
    form = RequestForm(request.POST if request.method == "POST" else None, initial={"source_token": token})
    if request.method == "POST" and form.is_valid():
        try:
            payload = signing.loads(form.cleaned_data["source_token"], salt=SALT, max_age=1800)
            if payload["actor"] != request.user.pk or payload["property"] != str(determination.public_id):
                raise PermissionDenied
            row = service.request_link(actor=request.user, determination_id=determination.public_id,
                finance_department_id=form.cleaned_data["finance_department"].pk, reason=form.cleaned_data["reason"],
                request_id=payload["request"], expected_property=payload["basis"], expected_predecessor=payload["predecessor"])
        except signing.BadSignature:
            form.add_error(None, "The sharing form changed or expired. Check existing requests, then reopen it.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("inventory_finance:property-link-detail", link_id=row.public_id)
    return render(request, "inventory_finance/property_link_request.html", {
        "record": determination, "form": form, "issue": issue, "previous": previous})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def detail(request, link_id):
    row = get_object_or_404(service.visible(request.user).select_related("determination__asset", "finance_department"), public_id=link_id)
    can_propose = row.status == "requested" and service.finance_allowed(request.user, row.finance_department_id, "propose")
    can_review = row.status in ("requested", "proposed") and service.finance_allowed(request.user, row.finance_department_id, "review") and request.user.pk not in (row.requested_by_id, row.proposed_by_id)
    can_withdraw = row.status in ("requested", "proposed", "approved") and (
        service.finance_allowed(request.user, row.finance_department_id, "review") or service.gso_allowed(request.user, row.determination, "request"))
    action = request.POST.get("action", "") if request.method == "POST" else ""
    proposal = ProposalForm(request.POST if action == "preview" else None, actor=request.user, row=row, prefix="proposal") if can_propose else None
    decision = DecisionForm(request.POST if action in ("approve", "reject", "withdraw") else None,
        initial={"expected_version": row.state_version}, prefix="decision")
    issue, preview, preview_token = "", None, ""
    if request.method == "POST":
        try:
            if action in ("preview", "propose"):
                if not can_propose:
                    raise PermissionDenied
                if action == "preview" and proposal.is_valid():
                    data = proposal.cleaned_data
                    basis = service.dimensions(actor=request.user, owner_id=row.finance_department_id,
                        as_of=data["as_of"], fund_id=data["fund"].public_id, account_id=data["account"].public_id,
                        center_id=data["center"].public_id if data["center"] else None)
                    preview = {"actor": request.user.pk, "link": str(row.public_id), "version": row.state_version,
                        "as_of": data["as_of"].isoformat(), "fund": str(data["fund"].public_id), "account": str(data["account"].public_id),
                        "center": str(data["center"].public_id) if data["center"] else None,
                        "mapping": str(data["mapping"].public_id) if data["mapping"] else None, "reason": data["reason"], "basis": basis}
                    preview_token = signing.dumps(preview, salt=SALT)
                elif action == "propose":
                    payload = signing.loads(request.POST.get("proposal_token", ""), salt=SALT, max_age=1800)
                    if payload["actor"] != request.user.pk or payload["link"] != str(row.public_id):
                        raise PermissionDenied
                    from datetime import date
                    service.propose(actor=request.user, link_id=row.public_id, expected_version=payload["version"],
                        as_of=date.fromisoformat(payload["as_of"]), fund_id=payload["fund"], account_id=payload["account"],
                        center_id=payload["center"], mapping_id=payload["mapping"], reason=payload["reason"], expected_dimensions=payload["basis"])
                    return redirect("inventory_finance:property-link-detail", link_id=row.public_id)
            elif action in ("approve", "reject", "withdraw"):
                if not (can_withdraw if action == "withdraw" else can_review):
                    raise PermissionDenied
                if decision.is_valid():
                    service.decide(actor=request.user, link_id=row.public_id, action=action, **decision.cleaned_data)
                    return redirect("inventory_finance:property-link-detail", link_id=row.public_id)
            else:
                raise ValidationError("Choose a supported association action.")
        except signing.BadSignature:
            issue = "The dimension preview changed or expired. Preview it again."
        except ValidationError as error:
            issue = " ".join(error.messages)
    current_note = "Retained history only; no current Finance check is asserted."
    try:
        service.verify(row)
        service._property_current(row)
        if row.status == "approved" and service.finance_allowed(request.user, row.finance_department_id):
            service.current(row, request.user)
            current_note = "Property and native dimensions match this association at this read. This is not a posting or valuation."
    except (ValidationError, PermissionDenied) as error:
        current_note = "Current use requires review: " + (" ".join(error.messages) if isinstance(error, ValidationError) else "the supporting source is outside your current authority.")
    return render(request, "inventory_finance/property_link_detail.html", {"row": row, "proposal": proposal,
        "shared_asset": row.property_snapshot.get("source_snapshot", {}).get("facts", {}),
        "shared_treatment": dict(PropertyDetermination._meta.get_field("treatment").flatchoices).get(row.property_snapshot.get("treatment"), "Unknown"),
        "decision": decision, "preview": preview, "preview_token": preview_token, "issue": issue,
        "current_note": current_note, "can_propose": can_propose, "can_review": can_review,
        "can_withdraw": can_withdraw, "can_gso": service.gso_allowed(request.user, row.determination)})


@login_required
@never_cache
@require_GET
def evidence(request, link_id):
    from inventory.private_evidence import open_checked_private_evidence
    row = get_object_or_404(service.visible(request.user).select_related("determination"), public_id=link_id)
    try:
        service.verify(row)
        if properties.snapshot(row.determination) != row.property_snapshot:
            raise ValidationError("Shared packet basis changed.")
        properties.verify_source(row.determination)
        source = open_checked_private_evidence(row.determination,
            namespace=f"inventory/property-determinations/{row.determination.public_id}")
    except (OSError, ValueError, ValidationError):
        raise Http404("The shared evidence is unavailable or requires integrity review.")
    response = FileResponse(source, as_attachment=True, filename=row.determination.original_filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
