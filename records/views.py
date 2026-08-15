from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from assistance.models import AssistanceRequest, CitizenProfile, RequestDocument
from reporting.models import ReportRun
from social_welfare.models import ProgramActivity, SocialWelfareProgram

from .access import (
    can_approve_records, can_download_records, can_manage_records, can_manage_retention,
    can_review_records, can_view_restricted_records, department_for_user, record_is_visible,
    records_access_required, records_permission_required,
)
from .forms import DepartmentRecordForm, RecordFileForm, RetentionForm
from .models import DepartmentRecord, RecordEvent, RecordFile
from .services import (
    RecordWorkflowError, add_record_file, association_file, association_label, association_url,
    create_record, file_approved_report, source_department, transition_record,
)


SOURCE_MODELS = {
    "assistance": AssistanceRequest,
    "assistance_document": RequestDocument,
    "citizen": CitizenProfile,
    "program": SocialWelfareProgram,
    "activity": ProgramActivity,
}


def _visible_records(user):
    department = department_for_user(user)
    queryset = DepartmentRecord.objects.filter(department=department).select_related("custodian", "created_by", "approved_by", "superseded_by")
    if not can_view_restricted_records(user, department):
        queryset = queryset.filter(confidentiality=DepartmentRecord.CONFIDENTIALITY_INTERNAL)
    return queryset


def _record(user, public_id):
    record = get_object_or_404(DepartmentRecord.objects.select_related("department", "custodian", "created_by", "reviewed_by", "approved_by", "superseded_by"), public_id=public_id)
    if not record_is_visible(user, record):
        raise Http404
    return record


def _source(source_type, source_id, department):
    model = SOURCE_MODELS.get(source_type)
    if not model or not source_id:
        return None
    source = get_object_or_404(model, pk=source_id)
    if source_department(source) != department:
        raise Http404
    return source


@records_access_required
def workspace(request):
    records = _visible_records(request.user)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    classification = request.GET.get("classification", "").strip()
    if query:
        records = records.filter(Q(record_number__icontains=query) | Q(title__icontains=query) | Q(description__icontains=query))
    if status in dict(DepartmentRecord.STATUS_CHOICES):
        records = records.filter(status=status)
    if classification in dict(DepartmentRecord.CLASS_CHOICES):
        records = records.filter(classification=classification)
    department_records = _visible_records(request.user)
    return render(request, "records/workspace.html", {
        "records": records[:100], "query": query, "selected_status": status, "selected_classification": classification,
        "status_choices": DepartmentRecord.STATUS_CHOICES, "classification_choices": DepartmentRecord.CLASS_CHOICES,
        "draft_count": department_records.filter(status=DepartmentRecord.DRAFT).count(),
        "review_count": department_records.filter(status=DepartmentRecord.UNDER_REVIEW).count(),
        "official_count": department_records.filter(status=DepartmentRecord.APPROVED).count(),
        "retention_due_count": department_records.filter(status=DepartmentRecord.ARCHIVED, disposition_due_date__lte=timezone.localdate(), legal_hold=False).count(),
        "can_manage": can_manage_records(request.user),
    })


@records_access_required
def record_detail(request, public_id):
    record = _record(request.user, public_id)
    associations = []
    for item in record.associations.select_related("content_type", "created_by"):
        file_field, filename = association_file(item)
        associations.append({"item": item, "label": association_label(item), "url": association_url(item), "downloadable": bool(file_field), "filename": filename})
    replacements = _visible_records(request.user).filter(status=DepartmentRecord.APPROVED).exclude(pk=record.pk)
    return render(request, "records/record_detail.html", {
        "record": record, "associations": associations, "file_form": RecordFileForm(),
        "retention_form": RetentionForm(instance=record), "replacements": replacements,
        "can_manage": can_manage_records(request.user), "can_review": can_review_records(request.user),
        "can_approve": can_approve_records(request.user), "can_download": can_download_records(request.user),
        "can_manage_retention": can_manage_retention(request.user),
    })


@records_permission_required(can_manage_records)
@require_http_methods(["GET", "POST"])
def record_create(request):
    department = department_for_user(request.user)
    source_type = request.POST.get("source_type") or request.GET.get("source_type", "")
    source_id = request.POST.get("source_id") or request.GET.get("source_id", "")
    source = _source(source_type, source_id, department) if source_type and source_id else None
    initial = {"source_type": source_type, "source_id": source_id}
    if source and request.method == "GET":
        if isinstance(source, SocialWelfareProgram):
            initial.update({"title": f"{source.code} — {source.name}", "classification": DepartmentRecord.CLASS_PROGRAM})
        elif isinstance(source, ProgramActivity):
            initial.update({"title": source.title, "classification": DepartmentRecord.CLASS_ACTIVITY})
        elif isinstance(source, AssistanceRequest):
            initial.update({"title": f"Assistance request {source.reference_code}", "classification": DepartmentRecord.CLASS_ASSISTANCE, "confidentiality": DepartmentRecord.CONFIDENTIALITY_CONFIDENTIAL})
        elif isinstance(source, CitizenProfile):
            initial.update({"title": f"Citizen service record #{source.pk}", "classification": DepartmentRecord.CLASS_CITIZEN, "confidentiality": DepartmentRecord.CONFIDENTIALITY_CONFIDENTIAL})
    form = DepartmentRecordForm(request.POST or None, request.FILES or None, department=department, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            record = create_record(
                department=department, actor=request.user, title=form.cleaned_data["title"],
                description=form.cleaned_data["description"], classification=form.cleaned_data["classification"],
                confidentiality=form.cleaned_data["confidentiality"], custodian=form.cleaned_data["custodian"],
                retention_years=form.cleaned_data["retention_years"], retention_notes=form.cleaned_data["retention_notes"],
                sources=(source,) if source else (), uploaded_file=form.cleaned_data.get("initial_file"),
                uploaded_description=form.cleaned_data.get("file_description", ""),
            )
        except (RecordWorkflowError, ValidationError) as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Record {record.record_number} created as a draft.")
            return redirect(record)
    return render(request, "records/record_form.html", {"form": form, "source": source})


@records_permission_required(can_manage_records)
@require_POST
def add_file(request, public_id):
    record = _record(request.user, public_id)
    form = RecordFileForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_record_file(record, form.cleaned_data["file"], request.user, form.cleaned_data["description"])
        except (RecordWorkflowError, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Supporting file added with a recorded checksum.")
    else:
        messages.error(request, "Choose a valid supporting file.")
    return redirect(record)


@records_access_required
@require_POST
def transition(request, public_id, action):
    record = _record(request.user, public_id)
    allowed = (
        (action == "submit" and can_manage_records(request.user))
        or (action == "return" and can_review_records(request.user))
        or (action in ("approve", "supersede") and can_approve_records(request.user))
        or (action in ("archive", "dispose") and can_manage_retention(request.user))
    )
    if not allowed:
        raise PermissionDenied
    replacement = None
    if action == "supersede":
        replacement = get_object_or_404(_visible_records(request.user), public_id=request.POST.get("replacement"), status=DepartmentRecord.APPROVED)
    try:
        transition_record(record, action, request.user, request.POST.get("note", "").strip(), replacement)
    except (RecordWorkflowError, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Record marked {record.get_status_display().lower()}.")
    return redirect(record)


@records_permission_required(can_manage_retention)
@require_POST
def update_retention(request, public_id):
    record = _record(request.user, public_id)
    if record.status == DepartmentRecord.DISPOSED:
        messages.error(request, "Disposed record metadata is immutable.")
        return redirect(record)
    before = {"retention_years": record.retention_years, "disposition_due_date": str(record.disposition_due_date or ""), "legal_hold": record.legal_hold}
    form = RetentionForm(request.POST, instance=record)
    if form.is_valid():
        updated = form.save(commit=False)
        updated.full_clean()
        updated.save()
        RecordEvent.objects.create(record=record, actor=request.user, action="retention_updated", from_status=record.status, to_status=record.status, note="Retention controls updated.", metadata={"before": before, "after": {"retention_years": updated.retention_years, "disposition_due_date": str(updated.disposition_due_date or ""), "legal_hold": updated.legal_hold}})
        messages.success(request, "Retention controls updated with an audit entry.")
    else:
        messages.error(request, "Correct the retention settings before saving.")
    return redirect(record)


@records_access_required
def download_file(request, public_id, file_id):
    record = _record(request.user, public_id)
    if not can_download_records(request.user) or record.status == DepartmentRecord.DISPOSED:
        raise PermissionDenied
    item = get_object_or_404(RecordFile, pk=file_id, record=record, is_active=True)
    RecordEvent.objects.create(record=record, actor=request.user, action="downloaded_file", from_status=record.status, to_status=record.status, note=f"Downloaded {item.display_name}.", metadata={"file_id": item.pk, "checksum": item.checksum})
    return FileResponse(item.file.open("rb"), as_attachment=True, filename=item.display_name)


@records_access_required
def download_source(request, public_id, association_id):
    record = _record(request.user, public_id)
    if not can_download_records(request.user) or record.status == DepartmentRecord.DISPOSED:
        raise PermissionDenied
    association = get_object_or_404(record.associations.select_related("content_type"), pk=association_id)
    file_field, filename = association_file(association)
    if not file_field:
        raise Http404
    RecordEvent.objects.create(record=record, actor=request.user, action="downloaded_source", from_status=record.status, to_status=record.status, note=f"Downloaded linked source {filename}.", metadata={"association_id": association.pk})
    return FileResponse(file_field.open("rb"), as_attachment=True, filename=filename)


@records_permission_required(can_manage_records)
@require_POST
def file_report(request, public_id):
    run = get_object_or_404(ReportRun.objects.select_related("definition__department", "template_version", "reviewed_by", "approved_by"), public_id=public_id, definition__department=department_for_user(request.user))
    try:
        record, created = file_approved_report(run, request.user)
    except RecordWorkflowError as exc:
        messages.error(request, str(exc))
        return redirect(run)
    messages.success(request, f"Report {'filed as' if created else 'already belongs to'} official record {record.record_number}.")
    return redirect(record)
