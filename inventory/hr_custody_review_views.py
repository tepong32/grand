from uuid import uuid4

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from . import hr_custody_reviews as workflow
from .access import department_for_user
from .models import Asset, EmployeeCustodyReview as Review

SALT = "gso-hr-custody-review-v1"


class RequestForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    reference = forms.CharField(max_length=160, label="Supplied HR request reference")
    request_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    request_kind = forms.ChoiceField(choices=Review._meta.get_field("request_kind").choices)
    upload = forms.FileField(label="Private HR request document")


class FindingsForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    findings = forms.CharField(max_length=4000, widget=forms.Textarea)
    coverage_note = forms.CharField(max_length=4000, widget=forms.Textarea,
        label="Reviewed scope, paper / legacy record coverage and remaining limitations")


class ActionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    note = forms.CharField(max_length=4000, widget=forms.Textarea)


@never_cache
@login_required
@require_http_methods(["GET"])
def review_list(request):
    workflow._require(request.user, "view")
    query = request.GET.get("q", "").strip()[:100]
    rows = workflow.visible_reviews(request.user)
    if query:
        rows = rows.filter(Q(reference__icontains=query) | Q(employee_label__icontains=query))
    employees = []
    record = workflow.can_act(request.user, "record")
    if query and record:
        from .employee_custody_views import employee_results
        employees = list(employee_results(request.user, query))
        owner = department_for_user(request.user)
        historical_ids = Asset.objects.filter(department_id=owner.pk).values_list("custodian_user_id", flat=True)
        from .models import AssetTransfer
        history = AssetTransfer.objects.filter(asset__department_id=owner.pk)
        historical = get_user_model().objects.filter(is_active=False).filter(
            Q(pk__in=historical_ids) | Q(pk__in=history.values("source_custodian_user_id"))
            | Q(pk__in=history.values("destination_custodian_user_id"))).filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).only("pk", "username", "first_name", "middle_name", "last_name", "ext_name", "is_active").order_by("pk")[:25]
        employees.extend(historical)
    return render(request, "inventory/hr_custody_review_list.html", {
        "page": Paginator(rows, 25).get_page(request.GET.get("page")), "query": query,
        "can_record": record, "employees": employees})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def review_create(request, employee_id):
    workflow._require(request.user, "record")
    employee = get_object_or_404(get_user_model().objects.only(
        "pk", "username", "first_name", "middle_name", "last_name", "ext_name", "is_active"), pk=employee_id)
    label = workflow.employee_label(actor=request.user, employee=employee)
    initial = {"request_date": timezone.localdate(), "token": signing.dumps({"actor": request.user.pk,
        "employee": employee.pk, "request": str(uuid4())}, salt=SALT)}
    form = RequestForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            payload = signing.loads(data.pop("token"), salt=SALT, max_age=1800)
            if payload.get("actor") != request.user.pk or payload.get("employee") != employee.pk:
                raise PermissionDenied
            review = workflow.create_review(actor=request.user, employee=employee,
                request_id=payload["request"], **data)
            return redirect("inventory:hr-custody-review-detail", pk=review.pk)
        except signing.BadSignature:
            form.add_error(None, "The request form expired or changed. Reload it before recording.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(request, "inventory/hr_custody_review_create.html", {"employee_label": label, "form": form})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def review_detail(request, pk):
    review = get_object_or_404(workflow.visible_reviews(request.user), pk=pk)
    error, current, source_token = "", None, ""
    findings = FindingsForm(initial={"expected_version": review.state_version,
        "findings": review.findings, "coverage_note": review.coverage_note})
    action_form = ActionForm(initial={"expected_version": review.state_version}, prefix="decision")
    if request.method == "POST":
        operation = request.POST.get("operation")
        try:
            if operation == "edit":
                workflow._require(request.user, "record", review)
                findings = FindingsForm(request.POST)
                if findings.is_valid():
                    workflow.edit_findings(actor=request.user, review=review, **findings.cleaned_data)
                    return redirect("inventory:hr-custody-review-detail", pk=pk)
            elif operation == "submit":
                workflow._require(request.user, "record", review)
                payload = signing.loads(request.POST.get("source_token", ""), salt=SALT, max_age=1800)
                if payload.get("actor") != request.user.pk or payload.get("review") != str(review.public_id):
                    raise PermissionDenied
                workflow.submit_review(actor=request.user, review=review, expected_version=payload["version"],
                    expected_source=payload["source"])
                return redirect("inventory:hr-custody-review-detail", pk=pk)
            elif operation in ("review", "return", "cancel"):
                workflow._require(request.user, "record" if operation == "cancel" else "review", review)
                action_form = ActionForm(request.POST, prefix="decision")
                if action_form.is_valid():
                    workflow.decide_review(actor=request.user, review=review, action=operation, **action_form.cleaned_data)
                    return redirect("inventory:hr-custody-review-detail", pk=pk)
            else:
                raise ValidationError("Choose a supported review action.")
        except signing.BadSignature:
            error = "The custody preview expired or changed. Reload and review it again."
        except ValidationError as exception:
            error = " ".join(exception.messages)
    issue = ""
    try:
        workflow.verify_history(review)
        workflow.verify_source(review)
        current = workflow.capture(review)
        source_token = signing.dumps({"actor": request.user.pk, "review": str(review.public_id),
            "version": review.state_version, "source": current}, salt=SALT, compress=True)
    except ValidationError as exception:
        issue = " ".join(exception.messages)
    independent = request.user.pk not in (review.created_by_id, review.submitted_by_id, review.employee_id)
    return render(request, "inventory/hr_custody_review_detail.html", {"review": review, "findings_form": findings,
        "action_form": action_form, "error": error, "issue": issue, "current": current,
        "stale": bool(review.source_snapshot and current != review.source_snapshot), "source_token": source_token,
        "can_record": workflow.can_act(request.user, "record", review) and review.status in (Review.DRAFT, Review.SUBMITTED),
        "can_review": independent and workflow.can_act(request.user, "review", review) and review.status == Review.SUBMITTED,
        "events": review.events.select_related("actor")})


@never_cache
@login_required
@require_http_methods(["GET"])
def review_evidence(request, pk):
    from .private_evidence import open_checked_private_evidence
    review = get_object_or_404(workflow.visible_reviews(request.user), pk=pk)
    try:
        workflow.verify_history(review)
        workflow.verify_source(review)
        source = open_checked_private_evidence(review, namespace=f"inventory/custody-reviews/{review.public_id}")
    except (OSError, ValueError, ValidationError):
        from django.http import HttpResponse
        return HttpResponse("The retained evidence failed verification. Restore or investigate it.", status=409)
    response = FileResponse(source, as_attachment=True, filename=review.original_filename,
        content_type="application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response
