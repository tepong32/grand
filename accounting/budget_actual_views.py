import csv
import io

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.forms import formset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from budget.access import has_budget_permission
from budget.models import BudgetCall
from departments.models import Department
from src.export_archive import archive_export
from .access import department_for_user
from . import budget_actuals as services
from .models import BudgetActualVersion, Fund, LedgerAccount, ResponsibilityCenter


class AdoptionForm(forms.Form):
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    center = forms.ModelChoiceField(queryset=ResponsibilityCenter.objects.none(), label="Office / responsibility center")
    budget_department = forms.ModelChoiceField(queryset=Department.objects.none(), label="Budget office receiving this evidence")
    period_start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reference = forms.CharField(max_length=255, label="Original certificate reference")
    issuer = forms.CharField(max_length=255, label="Issuing office / LGU")
    accountant_name = forms.CharField(max_length=255, label="Original Local Accountant / authorized signatory")
    certified_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Original certification date")
    certification_authority = forms.CharField(max_length=2000, label="Original signatory's certification authority / designation")
    coverage = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}),
        label="Covered office, fund, objects and evidence of complete coverage")
    signed_total = forms.DecimalField(max_digits=18, decimal_places=2, label="Signed certificate control total")
    evidence = forms.FileField(label="Original certificate (PDF, PNG or JPEG; up to 8 MiB)")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}), label="Adoption or correction basis")
    expected_latest = forms.IntegerField(min_value=0, widget=forms.HiddenInput, initial=0)

    def __init__(self, *args, actor, previous=None, **kwargs):
        super().__init__(*args, **kwargs)
        owner = department_for_user(actor)
        self.fields["fund"].queryset = Fund.objects.filter(department_id=owner.pk)
        self.fields["center"].queryset = ResponsibilityCenter.objects.filter(department_id=owner.pk, office_id__isnull=False)
        office_ids = list(BudgetCall.objects.filter(fiscal_year__department_id=owner.pk).values_list("department_id", flat=True).distinct())
        self.fields["budget_department"].queryset = Department.objects.filter(pk__in=office_ids)
        if previous:
            for name in ("fund", "center", "budget_department", "period_start", "period_end"):
                self.fields[name].disabled = True
            self.fields["evidence"].required = False
            self.fields["evidence"].help_text = "Leave blank to retain the preceding version's exact original document. Upload only when the source document changed."
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault("class", "form-control")


class ActualRowForm(forms.Form):
    account = forms.ModelChoiceField(queryset=LedgerAccount.objects.none())
    expense_class = forms.CharField(max_length=40, help_text="Use the source and Budget classification, such as PS, MOOE, FE or CO.")
    amount = forms.DecimalField(max_digits=18, decimal_places=2)
    source_row = forms.CharField(max_length=255, label="Source page / row")

    def __init__(self, *args, owner_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = LedgerAccount.objects.filter(department_id=owner_id)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


Rows = formset_factory(ActualRowForm, extra=1, min_num=1, validate_min=True,
    max_num=1000, validate_max=True, absolute_max=1000, can_delete=True)


def _visible(request):
    office = department_for_user(request.user)
    if not office or not request.user.is_active:
        raise PermissionDenied
    own = any(services.permitted(request.user, action) for action in ("view", "prepare", "review", "export"))
    shared = any(has_budget_permission(request.user, code) for code in
        ("prepare_budget_proposals", "review_budget_proposals", "view_budget_audit"))
    if not own and not shared:
        raise PermissionDenied
    selection = Q(pk__in=[])
    if own:
        selection |= Q(department_id=office.pk)
    if shared:
        selection |= Q(scope__budget_department_id=office.pk, status=BudgetActualVersion.APPROVED)
    return BudgetActualVersion.objects.filter(selection).defer("evidence").select_related(
        "scope__fund", "scope__responsibility_center").order_by("-prepared_at", "-pk")


def _filtered(request):
    query = _visible(request)
    text = request.GET.get("q", "").strip()[:255]
    status = request.GET.get("status", "")
    if text:
        query = query.filter(Q(payload__reference__icontains=text) | Q(scope__fund__code__icontains=text)
                             | Q(scope__responsibility_center__code__icontains=text))
    if status in ("submitted", "approved", "returned"):
        query = query.filter(status=status)
    return query, text, status


@login_required
@require_GET
def register(request):
    query, text, status = _filtered(request)
    page = Paginator(query, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "accounting/budget_actual_register.html", {"page": page, "q": text,
        "status": status, "querystring": params.urlencode(), "can_prepare": services.permitted(request.user, "prepare"),
        "can_export": services.permitted(request.user, "export")})


@login_required
@require_http_methods(["GET", "POST"])
def create(request, public_id=None):
    if not services.permitted(request.user, "prepare"):
        raise PermissionDenied
    owner = department_for_user(request.user)
    previous, initial, row_initial = None, {}, []
    if public_id:
        previous = get_object_or_404(_visible(request), public_id=public_id, department_id=owner.pk)
        try:
            services.verify(previous)
        except ValidationError as exc:
            return HttpResponse(" ".join(exc.messages), status=409)
        scope = previous.scope
        initial = {key: previous.payload[key] for key in ("reference", "issuer", "accountant_name",
            "certified_on", "certification_authority", "coverage", "signed_total")}
        initial.update(fund=scope.fund_id, center=scope.responsibility_center_id,
            budget_department=scope.budget_department_id, period_start=scope.period_start, period_end=scope.period_end,
            expected_latest=scope.versions.aggregate(number=Max("version"))["number"])
        row_initial = [{"account": row["account_id"], **{key: row[key] for key in
            ("expense_class", "amount", "source_row")}} for row in previous.payload["rows"]]
    form = AdoptionForm(request.POST if request.method == "POST" else None, request.FILES or None,
        actor=request.user, previous=previous, initial=initial)
    rows = Rows(request.POST if request.method == "POST" else None,
        initial=row_initial, form_kwargs={"owner_id": owner.pk})
    if request.method == "POST" and form.is_valid() and rows.is_valid():
        data = dict(form.cleaned_data)
        data["fund_id"], data["center_id"] = data.pop("fund").pk, data.pop("center").pk
        data["budget_department_id"] = data.pop("budget_department").pk
        document = data.pop("evidence")
        if document is None and previous:
            document = io.BytesIO(bytes(previous.evidence))
            document.name = previous.evidence_name
        try:
            record = services.propose(actor=request.user, document=document, rows=[{
                "account_id": row["account"].pk, "expense_class": row["expense_class"],
                "amount": row["amount"], "source_row": row["source_row"]}
                for row in rows.cleaned_data if row and not row.get("DELETE")], **data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("accounting:budget_actual_detail", public_id=record.public_id)
    return render(request, "accounting/budget_actual_form.html", {"form": form, "formset": rows, "previous": previous})


@login_required
@require_GET
def detail(request, public_id):
    record = get_object_or_404(_visible(request), public_id=public_id)
    try:
        services.verify(record)
    except ValidationError as exc:
        return HttpResponse(" ".join(exc.messages), status=409)
    scope = record.scope
    history = Paginator(_visible(request).filter(scope_id=scope.pk), 25).get_page(request.GET.get("page"))
    return render(request, "accounting/budget_actual_detail.html", {"record": record,
        "history": history, "is_current": scope.current_version_id == record.pk,
        "can_prepare": services.permitted(request.user, "prepare") and record.department_id == department_for_user(request.user).pk,
        "can_review": services.permitted(request.user, "review") and record.department_id == department_for_user(request.user).pk
            and record.status == record.SUBMITTED and record.prepared_by_id != request.user.pk,
        "can_export": services.permitted(request.user, "export")})


@login_required
@require_POST
def decide(request, public_id):
    record = get_object_or_404(_visible(request), public_id=public_id)
    if request.POST.get("decision") not in ("approve", "return"):
        return HttpResponse("Choose adopt or return.", status=400)
    try:
        services.review(record, request.user, approve=request.POST["decision"] == "approve",
            note=request.POST.get("note", ""), authority=request.POST.get("authority", ""))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("accounting:budget_actual_detail", public_id=record.public_id)


def _export_response(request, content, filename, metadata, content_type="text/csv; charset=utf-8"):
    receipt = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category="budget-actual-certificates", filename=filename, metadata=metadata)
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-GRAND-Export-SHA256"] = receipt["sha256"]
    return response


def _safe(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@login_required
@require_GET
def export(request, public_id=None):
    if not services.permitted(request.user, "export"):
        raise PermissionDenied
    query = _filtered(request)[0]
    if public_id:
        record = get_object_or_404(query, public_id=public_id)
        try:
            services.verify(record)
        except ValidationError as exc:
            return HttpResponse(" ".join(exc.messages), status=409)
        content = bytes(record.evidence)
        suffix = "pdf" if content.startswith(b"%PDF-") else "png" if content.startswith(b"\x89PNG") else "jpg"
        return _export_response(request, content, f"budget-actual-{record.public_id}.{suffix}",
            {"certificate_version": str(record.public_id), "payload_checksum": record.payload_checksum,
             "decision_checksum": record.decision_checksum}, "application/octet-stream")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(("Certificate", "Version", "State", "Current", "Fund", "Office", "From", "To",
        "Certified on", "Original Accountant", "Signed total", "Payload SHA256", "Evidence SHA256"))
    for record in query.iterator(chunk_size=100):
        try:
            services.verify(record)
        except ValidationError as exc:
            return HttpResponse(" ".join(exc.messages), status=409)
        writer.writerow([_safe(value) for value in (record.payload["reference"], record.version,
            record.get_status_display(), record.scope.current_version_id == record.pk,
            record.payload["scope"]["fund_code"], record.payload["scope"]["center_code"],
            record.scope.period_start, record.scope.period_end, record.payload["certified_on"],
            record.payload["accountant_name"], record.payload["signed_total"], record.payload_checksum, record.evidence_sha256)])
    return _export_response(request, buffer.getvalue().encode("utf-8-sig"), "budget-actual-certificates.csv",
        {"filters": {"q": request.GET.get("q", ""), "status": request.GET.get("status", "")}})
