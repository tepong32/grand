from __future__ import annotations

import hashlib

from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceRequest, CitizenProfile, RequestDocument
from assistance.services.file_validation import validate_uploaded_file
from reporting.models import ReportRun
from social_welfare.models import ProgramActivity, SocialWelfareProgram

from .models import DepartmentRecord, RecordAssociation, RecordEvent, RecordFile


class RecordWorkflowError(ValueError):
    pass


def source_department(source):
    if isinstance(source, ReportRun):
        return source.definition.department
    if isinstance(source, SocialWelfareProgram):
        return source.department
    if isinstance(source, ProgramActivity):
        return source.program.department
    if isinstance(source, RequestDocument):
        source = source.request
    if isinstance(source, (AssistanceRequest, CitizenProfile)):
        from departments.models import Department
        return Department.objects.filter(slug__iexact="mswd").first()
    raise RecordWorkflowError("This source type is not approved for the records registry.")


def record_number(department, public_id):
    return f"{department.slug.upper()}-REC-{timezone.localdate():%Y}-{public_id.hex[:8].upper()}"


def _file_digest(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


@transaction.atomic
def add_association(record, source, actor, role="context"):
    department = source_department(source)
    if not department or department.pk != record.department_id:
        raise RecordWorkflowError("The linked item must belong to the record's department.")
    content_type = ContentType.objects.get_for_model(source, for_concrete_model=True)
    association = RecordAssociation(
        record=record, content_type=content_type, object_id=source.pk, role=role, created_by=actor,
    )
    association.full_clean()
    association.save()
    return association


@transaction.atomic
def create_record(*, department, actor, title, description="", classification="general", confidentiality="internal", custodian=None, retention_years=None, retention_notes="", sources=(), uploaded_file=None, uploaded_description=""):
    record = DepartmentRecord(
        department=department, record_number="pending", title=title, description=description,
        classification=classification, confidentiality=confidentiality, custodian=custodian,
        retention_years=retention_years, retention_notes=retention_notes, created_by=actor,
    )
    record.record_number = record_number(department, record.public_id)
    record.full_clean()
    record.save()
    for source in sources:
        add_association(record, source, actor)
    if uploaded_file:
        add_record_file(record, uploaded_file, actor, uploaded_description)
    RecordEvent.objects.create(
        record=record, actor=actor, action="created", from_status="", to_status=record.status,
        note="Record registered in the department workspace.",
    )
    return record


@transaction.atomic
def add_record_file(record, uploaded_file, actor, description=""):
    if record.status not in (DepartmentRecord.DRAFT, DepartmentRecord.UNDER_REVIEW):
        raise RecordWorkflowError("Files cannot be added after a record is approved. Create a new version instead.")
    validate_uploaded_file(uploaded_file)
    checksum = _file_digest(uploaded_file)
    item = RecordFile(
        record=record, file=uploaded_file, display_name=uploaded_file.name,
        description=description, content_type=getattr(uploaded_file, "content_type", "") or "",
        size_bytes=uploaded_file.size, checksum=checksum, uploaded_by=actor,
    )
    item.full_clean()
    item.save()
    RecordEvent.objects.create(
        record=record, actor=actor, action="file_added", from_status=record.status, to_status=record.status,
        note=f"Added {item.display_name}.", metadata={"file_id": item.pk, "checksum": checksum, "size_bytes": item.size_bytes},
    )
    return item


@transaction.atomic
def transition_record(record, action, actor, note="", replacement=None):
    previous = record.status
    now = timezone.now()
    if action == "submit" and previous == DepartmentRecord.DRAFT:
        record.status = DepartmentRecord.UNDER_REVIEW
    elif action == "return" and previous == DepartmentRecord.UNDER_REVIEW:
        record.status = DepartmentRecord.DRAFT
        record.reviewed_by, record.reviewed_at = actor, now
    elif action == "approve" and previous == DepartmentRecord.UNDER_REVIEW:
        if not record.files.exists() and not record.associations.exists():
            raise RecordWorkflowError("Add a file or approved operational source before approval.")
        record.status = DepartmentRecord.APPROVED
        record.reviewed_by, record.reviewed_at = actor, now
        record.approved_by, record.approved_at = actor, now
        record.retention_start_date = record.retention_start_date or timezone.localdate()
        if record.retention_years:
            record.disposition_due_date = record.retention_start_date + relativedelta(years=record.retention_years)
    elif action == "archive" and previous == DepartmentRecord.APPROVED:
        record.status, record.archived_at = DepartmentRecord.ARCHIVED, now
    elif action == "dispose" and previous == DepartmentRecord.ARCHIVED:
        if not record.can_be_disposed:
            raise RecordWorkflowError("This record is not due for disposition or is protected by a legal hold.")
        record.status, record.disposed_at = DepartmentRecord.DISPOSED, now
    elif action == "supersede" and previous in (DepartmentRecord.APPROVED, DepartmentRecord.ARCHIVED):
        if not replacement or replacement.department_id != record.department_id or replacement.status != DepartmentRecord.APPROVED:
            raise RecordWorkflowError("Choose an approved replacement from the same department.")
        if replacement.pk == record.pk:
            raise RecordWorkflowError("A record cannot supersede itself.")
        record.status, record.superseded_by = DepartmentRecord.SUPERSEDED, replacement
    else:
        raise RecordWorkflowError("That record cannot make the requested status transition.")
    record.full_clean()
    record.save()
    RecordEvent.objects.create(
        record=record, actor=actor, action=action, from_status=previous, to_status=record.status, note=note,
        metadata={"replacement_record": replacement.record_number} if replacement else {},
    )
    return record


@transaction.atomic
def file_approved_report(run, actor):
    if run.status != ReportRun.APPROVED or not run.is_official_output or not run.output_file:
        raise RecordWorkflowError("Only an approved official report output can become a department record.")
    content_type = ContentType.objects.get_for_model(run)
    existing = RecordAssociation.objects.filter(content_type=content_type, object_id=run.pk, role="official_source").select_related("record").first()
    if existing:
        return existing.record, False
    record = create_record(
        department=run.definition.department, actor=actor,
        title=f"{run.definition.name} — {run.period_start:%Y-%m-%d} to {run.period_end:%Y-%m-%d}",
        description="Official report output filed from the governed reporting ledger.",
        classification=DepartmentRecord.CLASS_REPORT,
        confidentiality=DepartmentRecord.CONFIDENTIALITY_INTERNAL,
        retention_notes="Assign the governing departmental or national retention schedule before archival.",
    )
    add_association(record, run, actor, role="official_source")
    record.status = DepartmentRecord.APPROVED
    record.reviewed_by = run.reviewed_by or actor
    record.reviewed_at = run.reviewed_at or timezone.now()
    record.approved_by = run.approved_by or actor
    record.approved_at = run.approved_at or timezone.now()
    record.retention_start_date = (run.approved_at or timezone.now()).date()
    record.full_clean()
    record.save()
    RecordEvent.objects.create(
        record=record, actor=actor, action="filed_official_report", from_status=DepartmentRecord.DRAFT,
        to_status=DepartmentRecord.APPROVED, note="Filed without duplicating the reporting output file.",
        metadata={"report_run": str(run.public_id), "output_checksum": run.checksum},
    )
    return record, True


def association_label(association):
    source = association.content_object
    if isinstance(source, ReportRun):
        return f"Report run: {source.definition.name} ({source.period_start} to {source.period_end})"
    if isinstance(source, RequestDocument):
        return f"Assistance document: {source.get_document_type_display()} ({source.request.reference_code})"
    if isinstance(source, AssistanceRequest):
        return f"Assistance request: {source.reference_code}"
    if isinstance(source, CitizenProfile):
        return f"Citizen profile #{source.pk}"
    if isinstance(source, SocialWelfareProgram):
        return f"Program: {source.code} — {source.name}"
    if isinstance(source, ProgramActivity):
        return f"Activity: {source.title}"
    return str(source)


def association_url(association):
    source = association.content_object
    if isinstance(source, ReportRun):
        return source.get_absolute_url()
    if isinstance(source, RequestDocument):
        source = source.request
    if isinstance(source, AssistanceRequest):
        return reverse("assistance:mswd_request_detail", kwargs={"ref_code": source.reference_code})
    if isinstance(source, CitizenProfile):
        return reverse("assistance:citizen_profile_detail", kwargs={"profile_id": source.pk})
    if isinstance(source, (SocialWelfareProgram, ProgramActivity)):
        return source.get_absolute_url()
    return ""


def association_file(association):
    source = association.content_object
    if isinstance(source, ReportRun) and source.output_file:
        return source.output_file, source.output_file.name.rsplit("/", 1)[-1]
    if isinstance(source, RequestDocument) and source.file and not source.is_removed:
        return source.file, source.file.name.rsplit("/", 1)[-1]
    return None, None
