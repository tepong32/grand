from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import can_view, department_for_user
from .models import AppropriationAuthorization, BudgetAuditEvent, BudgetVersion
from .services import actor_label


AUTHORITY_ELIGIBLE_KINDS = (
    BudgetVersion.FINAL,
    BudgetVersion.SUPPLEMENTAL,
    BudgetVersion.REENACTED,
)

ANNUAL_ATTENTION_CHOICES = (
    ("needs_preparation", "Needs preparation or correction"),
    ("awaiting_proposal_review", "Awaiting proposal review"),
    ("approved_nonspendable", "Approved proposal; not spendable"),
    ("needs_authority_evidence", "Needs authority evidence"),
    ("awaiting_authorization", "Awaiting independent authorization"),
    ("operational_authority", "Operational appropriation authority"),
)

ANNUAL_REGISTER_COLUMNS = (
    "version_public_id",
    "budget_office",
    "fiscal_year",
    "budget_call",
    "version_kind",
    "version_number",
    "title",
    "requesting_department",
    "proposal_status",
    "next_action",
    "line_count",
    "proposal_total",
    "resource_estimate_total",
    "spendable_authority",
    "authorization_status",
    "authority_type",
    "ordinance_or_authority_number",
    "effectivity_date",
    "review_status",
    "review_reference",
    "signed_control_total",
    "control_difference",
    "authorization_checksum",
    "prepared_by",
    "submitted_by",
    "reviewed_by",
    "state_version",
    "updated_at",
)


def _csv_safe(value):
    value = str(value or "")
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def apply_annual_filters(queryset, *, fiscal_year=None, kind="", status="", attention="", actor=None):
    if fiscal_year is not None:
        queryset = queryset.filter(fiscal_year=fiscal_year)
    if kind in dict(BudgetVersion.KIND_CHOICES):
        queryset = queryset.filter(kind=kind)
    else:
        kind = ""
    if status in dict(BudgetVersion.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""

    if attention == "needs_preparation":
        queryset = queryset.filter(status__in=(BudgetVersion.DRAFT, BudgetVersion.RETURNED))
    elif attention == "awaiting_proposal_review":
        queryset = queryset.filter(status=BudgetVersion.FOR_REVIEW)
        if actor is not None:
            queryset = queryset.exclude(submitted_by_id=actor.pk)
    elif attention == "approved_nonspendable":
        queryset = queryset.filter(status=BudgetVersion.APPROVED).exclude(kind__in=AUTHORITY_ELIGIBLE_KINDS)
    elif attention == "needs_authority_evidence":
        queryset = queryset.filter(status=BudgetVersion.APPROVED, kind__in=AUTHORITY_ELIGIBLE_KINDS).filter(
            Q(appropriation_authorization__isnull=True)
            | Q(appropriation_authorization__status__in=(AppropriationAuthorization.DRAFT, AppropriationAuthorization.RETURNED))
        )
    elif attention == "awaiting_authorization":
        queryset = queryset.filter(
            status=BudgetVersion.APPROVED,
            kind__in=AUTHORITY_ELIGIBLE_KINDS,
            appropriation_authorization__status=AppropriationAuthorization.FOR_REVIEW,
        )
    elif attention == "operational_authority":
        queryset = queryset.filter(
            status=BudgetVersion.AUTHORIZED,
            appropriation_authorization__status=AppropriationAuthorization.AUTHORIZED,
        )
    else:
        attention = ""
    return queryset, kind, status, attention


def next_annual_action(version):
    if version.status == BudgetVersion.DRAFT:
        return "Continue preparation, then submit"
    if version.status == BudgetVersion.RETURNED:
        return "Correct returned version, then resubmit"
    if version.status == BudgetVersion.FOR_REVIEW:
        return "Independent reviewer: approve or return"
    if version.status == BudgetVersion.AUTHORIZED:
        return "Operational authority; proceed to allotment control"
    if version.status != BudgetVersion.APPROVED:
        return "Review current status"
    if version.kind not in AUTHORITY_ELIGIBLE_KINDS:
        return "Approved proposal; continue governed consolidation/versioning"
    authorization = getattr(version, "appropriation_authorization", None)
    if authorization is None:
        return "Record appropriation authority evidence"
    if authorization.status in (AppropriationAuthorization.DRAFT, AppropriationAuthorization.RETURNED):
        return "Complete or correct authority evidence, then submit"
    if authorization.status == AppropriationAuthorization.FOR_REVIEW:
        return "Independent authorizer: authorize or return"
    return "Verify operational authority state"


def _authorization(version):
    try:
        return version.appropriation_authorization
    except AppropriationAuthorization.DoesNotExist:
        return None


def build_annual_register(department, actor, queryset, *, fiscal_year=None, kind="", status="", attention=""):
    actor_department = department_for_user(actor)
    if not can_view(actor) or actor_department is None or actor_department.pk != department.pk:
        raise PermissionDenied
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The annual Budget register may contain only the current Budget office.")

    versions = list(queryset.select_related(
        "fiscal_year", "budget_call", "appropriation_authorization",
    ).prefetch_related("lines", "resource_estimates"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(ANNUAL_REGISTER_COLUMNS)
    for version in versions:
        authorization = _authorization(version)
        writer.writerow(tuple(_csv_safe(value) for value in (
            version.public_id,
            version.department_label,
            version.fiscal_year.year,
            version.budget_call.title,
            version.get_kind_display(),
            version.version,
            version.title,
            version.requesting_department_label or "Consolidated / LGU-wide",
            version.get_status_display(),
            next_annual_action(version),
            len(version.lines.all()),
            sum((line.amount for line in version.lines.all()), 0),
            sum((item.amount for item in version.resource_estimates.all()), 0),
            "yes" if version.is_spendable_authority else "no",
            authorization.get_status_display() if authorization else "Not recorded",
            authorization.get_authority_type_display() if authorization else "",
            authorization.ordinance_number if authorization else "",
            authorization.effectivity_date if authorization else "",
            authorization.get_review_status_display() if authorization else "",
            authorization.review_reference if authorization else "",
            authorization.signed_control_total if authorization else "",
            authorization.control_difference if authorization else "",
            authorization.snapshot_checksum if authorization else "",
            version.created_by_label,
            version.submitted_by_label,
            version.decided_by_label,
            version.state_version,
            version.updated_at.isoformat(),
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    year_label = str(fiscal_year.year) if fiscal_year is not None else "all-years"
    filename = f"finance-annual-budget-register-{slugify(year_label)}.csv"
    metadata = {
        "kind": "finance_annual_budget_register",
        "fiscal_year_public_id": str(fiscal_year.public_id) if fiscal_year is not None else "",
        "fiscal_year": fiscal_year.year if fiscal_year is not None else "all",
        "version_kind_filter": kind or "all",
        "status_filter": status or "all",
        "attention_filter": attention or "all",
        "version_count": len(versions),
        "authority_boundary": (
            "Budget oversight evidence only; approved proposals remain nonspendable unless the row carries "
            "independently authorized operational appropriation evidence."
        ),
    }
    receipt = archive_export(
        content=content,
        department=department,
        user=actor,
        category="finance-annual-budget-register",
        filename=filename,
        metadata=metadata,
    )
    BudgetAuditEvent.objects.create(
        department_id=department.pk,
        department_label=department.name,
        target_type="budget_workspace",
        target_id=str(department.pk),
        action="annual_register_exported",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
