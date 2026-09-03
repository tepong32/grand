from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from vouchers.roles import is_finance_uat_viewer

from .access import (
    can_export_local_form_acceptance, can_manage_local_form_acceptance,
    can_review_local_form_acceptance, can_witness_local_form_tests, department_for_user,
)
from .models import (
    FinanceLocalFormAcceptance, FinanceLocalFormEvent, FinanceLocalFormSection,
    FinanceLocalFormTestAttempt,
)


ATTENTION_CHOICES = (
    ("needs_mapping", "Needs a governed GRAND mapping"),
    ("needs_reference", "Needs the current local reference"),
    ("candidate_sections", "Starter sections need local decisions"),
    ("returned", "Returned for correction"),
    ("witness_tests", "Practical tests awaiting my independent witness"),
    ("for_review", "Waiting for independent acceptance"),
    ("accepted", "Locally accepted evidence"),
    ("superseded", "Superseded history"),
)

LOCAL_FORM_ACTION_SPECS = {
    "needs_mapping": {
        "role": "manage",
        "title": "Local forms needing a governed GRAND mapping",
        "definition": "Editable forms in the acting office that still name no activated report template or active preflighted Finance workbook.",
        "next_action": "Compare the actual local output with the governed source, then link only the exact accepted template version used to produce it.",
    },
    "needs_reference": {
        "role": "manage",
        "title": "Local forms needing the current reference",
        "definition": "Editable forms in the acting office whose exact blank or safely redacted local reference has not been retained yet.",
        "next_action": "Obtain the current locally used copy, remove sensitive data, verify its file type, and retain its checksum before testing.",
    },
    "candidate_sections": {
        "role": "manage",
        "title": "Candidate form sections needing local decisions",
        "definition": "Editable starter forms in the acting office with one or more sections still awaiting an evidenced match or not-applicable decision.",
        "next_action": "Compare every candidate row with the retained current form and cite the page, memorandum, comparison, or decision for the outcome.",
    },
    "returned": {
        "role": "manage",
        "title": "Returned local forms to correct and retest",
        "definition": "Returned editable form versions in the acting office that require the review reason to be resolved before resubmission.",
        "next_action": "Correct the returned version, record successor attempts for affected practical tests, and resubmit only after every gate is current.",
    },
    "witness_tests": {
        "role": "witness",
        "title": "Local-form tests awaiting my independent witness",
        "definition": "Forms in the acting office containing submitted practical-test evidence not performed by the signed-in witness.",
        "next_action": "Reperform or observe the named test against its pinned basis, then pass, fail, or mark only an eligible digital printer test not applicable.",
    },
    "for_review": {
        "role": "review",
        "title": "Local forms for independent acceptance",
        "definition": "Submitted form versions in the acting office that the signed-in reviewer did not create or submit.",
        "next_action": "Verify the pinned source, reference, sections, latest witnessed tests, routing, and checksums before accepting or returning the form.",
    },
}

LOCAL_FORM_OVERSIGHT_CHOICES = tuple(
    choice for choice in ATTENTION_CHOICES if choice[0] not in LOCAL_FORM_ACTION_SPECS
)


def _local_form_action_role_allowed(user, department, role):
    if is_finance_uat_viewer(user):
        return False
    if role == "manage":
        return can_manage_local_form_acceptance(user, department)
    if role == "witness":
        return can_witness_local_form_tests(user, department)
    if role == "review":
        return can_review_local_form_acceptance(user, department)
    return False


def local_form_action_choices_for_user(user, department=None):
    department = department or department_for_user(user)
    labels = dict(ATTENTION_CHOICES)
    return tuple(
        (attention, labels[attention])
        for attention, spec in LOCAL_FORM_ACTION_SPECS.items()
        if _local_form_action_role_allowed(user, department, spec["role"])
    ) if department else ()


def local_form_attention_choices_for_user(user, department=None):
    return local_form_action_choices_for_user(user, department) + LOCAL_FORM_OVERSIGHT_CHOICES


def local_form_action_queryset(user, attention, *, queryset=None):
    queryset = queryset if queryset is not None else FinanceLocalFormAcceptance.objects.all()
    spec = LOCAL_FORM_ACTION_SPECS.get(attention)
    if spec is None:
        return queryset.none(), "", None
    department = department_for_user(user)
    if department is None or not _local_form_action_role_allowed(user, department, spec["role"]):
        return queryset.none(), attention, spec

    editable = (FinanceLocalFormAcceptance.DRAFT, FinanceLocalFormAcceptance.RETURNED)
    queryset = queryset.filter(department=department)
    if attention == "needs_mapping":
        queryset = queryset.filter(status__in=editable, source_type=FinanceLocalFormAcceptance.SOURCE_UNMAPPED)
    elif attention == "needs_reference":
        queryset = queryset.filter(status__in=editable, reference_file="")
    elif attention == "candidate_sections":
        queryset = queryset.filter(
            status__in=editable,
            sections__confirmation_status=FinanceLocalFormSection.STARTER_CANDIDATE,
        )
    elif attention == "returned":
        queryset = queryset.filter(status=FinanceLocalFormAcceptance.RETURNED)
    elif attention == "witness_tests":
        actionable_tests = FinanceLocalFormTestAttempt.objects.filter(
            status=FinanceLocalFormTestAttempt.SUBMITTED,
        ).exclude(created_by=user)
        queryset = queryset.filter(pk__in=actionable_tests.values("form_id"))
    elif attention == "for_review":
        queryset = queryset.filter(status=FinanceLocalFormAcceptance.SUBMITTED).exclude(
            Q(created_by=user) | Q(submitted_by=user),
        )
    return queryset.distinct(), attention, spec

LOCAL_FORM_REGISTER_COLUMNS = (
    "form_public_id", "code", "form_number", "name", "version", "status", "next_action",
    "source_type", "source_name", "source_version", "source_checksum", "reference_kind",
    "reference_name", "reference_checksum", "delivery_mode", "default_copy_count",
    "section_count", "candidate_section_count", "locally_resolved_section_count",
    "test_category_count", "witnessed_pass_count", "witnessed_not_applicable_count",
    "awaiting_witness_count", "failed_test_count", "missing_test_count",
    "submission_checksum", "supersedes_public_id", "created_by", "created_at",
    "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "review_note",
    "last_event", "last_event_reason", "last_event_at", "updated_at",
)


def apply_local_form_filters(
    queryset, *, user=None, status="", source_type="", delivery_mode="", attention="", search="",
):
    if status in dict(FinanceLocalFormAcceptance.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    elif status:
        queryset = queryset.none()
    else:
        status = ""

    if source_type in dict(FinanceLocalFormAcceptance.SOURCE_CHOICES):
        queryset = queryset.filter(source_type=source_type)
    elif source_type:
        queryset = queryset.none()
    else:
        source_type = ""

    if delivery_mode in dict(FinanceLocalFormAcceptance.DELIVERY_CHOICES):
        queryset = queryset.filter(delivery_mode=delivery_mode)
    elif delivery_mode:
        queryset = queryset.none()
    else:
        delivery_mode = ""

    if attention in LOCAL_FORM_ACTION_SPECS:
        if user is None:
            queryset = queryset.none()
        else:
            queryset, _selected, _spec = local_form_action_queryset(
                user, attention, queryset=queryset,
            )
    elif attention == "accepted":
        queryset = queryset.filter(status=FinanceLocalFormAcceptance.ACCEPTED)
    elif attention == "superseded":
        queryset = queryset.filter(status=FinanceLocalFormAcceptance.SUPERSEDED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""

    search = (search or "").strip()[:160]
    if search:
        queryset = queryset.filter(
            Q(code__icontains=search) | Q(form_number__icontains=search)
            | Q(name__icontains=search) | Q(purpose__icontains=search)
            | Q(authority_reference__icontains=search),
        )
    return queryset, status, source_type, delivery_mode, attention, search


def latest_test_summary(item):
    latest = {}
    for attempt in item.test_attempts.all():
        current = latest.get(attempt.category)
        if current is None or (attempt.attempt, attempt.pk) > (current.attempt, current.pk):
            latest[attempt.category] = attempt
    counts = {
        "passed": 0, "not_applicable": 0, "submitted": 0, "failed": 0,
        "missing": len(FinanceLocalFormTestAttempt.REQUIRED_CATEGORIES) - len(latest),
    }
    for attempt in latest.values():
        if attempt.status == FinanceLocalFormTestAttempt.PASSED:
            counts["passed"] += 1
        elif attempt.status == FinanceLocalFormTestAttempt.NOT_APPLICABLE:
            counts["not_applicable"] += 1
        elif attempt.status == FinanceLocalFormTestAttempt.SUBMITTED:
            counts["submitted"] += 1
        elif attempt.status == FinanceLocalFormTestAttempt.FAILED:
            counts["failed"] += 1
    return latest, counts


def next_local_form_action(item, *, sections=None, test_counts=None):
    if item.status == FinanceLocalFormAcceptance.SUBMITTED:
        return "A different authorized reviewer checks the pinned form, source, sections, tests, and routing"
    if item.status == FinanceLocalFormAcceptance.ACCEPTED:
        return "Use this exact accepted version, or create and fully retest a successor when the form changes"
    if item.status == FinanceLocalFormAcceptance.SUPERSEDED:
        return "Retain for historical reproduction and use the accepted successor for current work"
    if item.status == FinanceLocalFormAcceptance.RETURNED:
        return "Resolve the review note in this editable version, retest changed evidence, and resubmit"
    if item.source_type == FinanceLocalFormAcceptance.SOURCE_UNMAPPED:
        return "Link the exact governed report template or Finance workbook used to produce this form"
    if not item.reference_file:
        return "Upload the current blank or safely redacted local form and verify its type"
    sections = list(item.sections.all()) if sections is None else sections
    if not sections:
        return "Add the recognizable required, optional, conditional, or repeating form sections"
    if any(section.confirmation_status == FinanceLocalFormSection.STARTER_CANDIDATE for section in sections):
        return "Compare every candidate starter section with retained current local evidence"
    if item.delivery_mode == FinanceLocalFormAcceptance.DELIVERY_UNCONFIRMED:
        return "Confirm actual digital/print delivery, people, copies, deadlines, custody, and layout"
    if test_counts is None:
        _latest, test_counts = latest_test_summary(item)
    if test_counts["failed"]:
        return "Correct each failed practical test and record a reasoned successor attempt"
    if test_counts["submitted"]:
        return "A different authorized witness decides each pending practical test attempt"
    if test_counts["missing"]:
        return "Perform and independently witness every remaining practical test category"
    return "Review the complete readiness list and submit the exact evidence for independent acceptance"


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _actor_label(actor):
    return (actor.get_full_name() or actor.username) if actor else ""


def _iso(value):
    return value.isoformat() if value else ""


def _source_identity(item):
    if item.report_template_id:
        return item.report_template.definition.name, item.report_template.version
    if item.finance_template_id:
        return item.finance_template.title, item.finance_template.version
    return "", ""


def build_local_form_register(
    *, actor, queryset, status="", source_type="", delivery_mode="", attention="", search="",
):
    department = department_for_user(actor)
    if department is None or not can_export_local_form_acceptance(actor):
        raise PermissionDenied
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The local-form register may contain only the acting user's department.")

    items = list(queryset.select_related(
        "report_template__definition", "finance_template", "supersedes",
        "created_by", "submitted_by", "reviewed_by",
    ).prefetch_related("sections", "test_attempts", "events"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(LOCAL_FORM_REGISTER_COLUMNS)
    for item in items:
        sections = list(item.sections.all())
        _latest, test_counts = latest_test_summary(item)
        events = list(item.events.all())
        last_event = events[0] if events else None
        source_name, source_version = _source_identity(item)
        candidate_sections = sum(
            section.confirmation_status == FinanceLocalFormSection.STARTER_CANDIDATE
            for section in sections
        )
        writer.writerow(tuple(_csv_safe(value) for value in (
            item.public_id, item.code, item.form_number, item.name, item.version,
            item.get_status_display(),
            next_local_form_action(item, sections=sections, test_counts=test_counts),
            item.get_source_type_display(), source_name, source_version, item.source_checksum,
            item.get_reference_kind_display(), item.reference_file.name if item.reference_file else "",
            item.reference_checksum, item.get_delivery_mode_display(), item.default_copy_count,
            len(sections), candidate_sections, len(sections) - candidate_sections,
            len(FinanceLocalFormTestAttempt.REQUIRED_CATEGORIES), test_counts["passed"],
            test_counts["not_applicable"], test_counts["submitted"], test_counts["failed"],
            test_counts["missing"], item.submission_checksum,
            item.supersedes.public_id if item.supersedes_id else "", _actor_label(item.created_by),
            _iso(item.created_at), _actor_label(item.submitted_by), _iso(item.submitted_at),
            _actor_label(item.reviewed_by), _iso(item.reviewed_at), item.review_note,
            last_event.action if last_event else "", last_event.reason if last_event else "",
            _iso(last_event.created_at) if last_event else "", _iso(item.updated_at),
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        attention, status, source_type, delivery_mode, search,
    ) if value) or "all-visible"
    filename = f"finance-local-form-register-{suffix}.csv"
    metadata = {
        "kind": "finance_local_form_register", "status_filter": status or "all",
        "source_type_filter": source_type or "all", "delivery_mode_filter": delivery_mode or "all",
        "attention_filter": attention or "all", "search_filter": search, "form_count": len(items),
        "authority_boundary": (
            "Operational local-form acceptance oversight only. A row does not make a DBM/COA/BIR/bank "
            "candidate official and does not replace the accepted packet, reference, witnessed tests, or sign-off."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-local-form-register", filename=filename, metadata=metadata,
    )
    if items:
        FinanceLocalFormEvent.objects.bulk_create([
            FinanceLocalFormEvent(
                form=item, actor=actor, action="register_exported",
                reason=f"Archived {receipt['relative_path']} with SHA-256 {receipt['sha256']}.",
                snapshot={"relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
            )
            for item in items
        ])
    return content, filename, receipt
