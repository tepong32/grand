from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import can_govern_setup, department_for_user
from .models import (
    AccountingAuditEvent,
    AccountingPeriod,
    FiscalYear,
    Fund,
    FundingSource,
    LedgerAccount,
    PostingMapping,
    ProgramActivityProject,
    ResponsibilityCenter,
)
from .services import actor_label, evaluate_fiscal_year_readiness


FOUNDATION_REGISTER_COLUMNS = (
    "record_kind",
    "fiscal_year",
    "record_id",
    "code",
    "label",
    "status",
    "category",
    "parent_code",
    "related_code",
    "normal_balance",
    "starts_on",
    "ends_on",
    "business_date",
    "authority_or_evidence",
    "prepared_by",
    "reviewed_by",
    "state_version",
    "structural_check",
    "structural_passed",
    "source_release",
    "source_checksum",
    "notes",
)


def _csv_safe(value):
    value = str(value or "")
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _row(**values):
    return tuple(_csv_safe(values.get(column, "")) for column in FOUNDATION_REGISTER_COLUMNS)


def _status(active):
    return "active" if active else "archived"


def build_foundation_register(department, actor, *, fiscal_year=None):
    """Build, archive, and audit a portable snapshot of governed F2.1 setup."""
    actor_department = department_for_user(actor)
    if not can_govern_setup(actor) or actor_department is None or actor_department.pk != department.pk:
        raise PermissionDenied
    if fiscal_year is not None and fiscal_year.department_id != department.pk:
        raise ValidationError("Choose a fiscal year from the current Accounting office.")

    years = FiscalYear.objects.filter(department_id=department.pk)
    if fiscal_year is not None:
        years = years.filter(pk=fiscal_year.pk)
    years = list(years.order_by("year", "pk"))
    year_ids = [item.pk for item in years]

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(FOUNDATION_REGISTER_COLUMNS)
    counts = {kind: 0 for kind in (
        "fiscal_year", "readiness", "period", "fund", "responsibility_center",
        "ledger_account", "funding_source", "program_classification", "posting_mapping",
    )}

    def write(kind, **values):
        writer.writerow(_row(record_kind=kind, **values))
        counts[kind] += 1

    for year in years:
        source_release = ""
        if year.source_release_code:
            source_release = f"{year.source_release_code} v{year.source_release_version or ''}".strip()
        write(
            "fiscal_year", fiscal_year=year.year, record_id=year.public_id, code=year.year,
            label=year.label, status=year.status, starts_on=year.starts_on, ends_on=year.ends_on,
            business_date=year.business_date, prepared_by=year.created_by_label,
            reviewed_by=year.approved_by_label, state_version=year.state_version,
            source_release=source_release, source_checksum=year.source_checksum,
            notes=f"Submitted by {year.submitted_by_label}" if year.submitted_by_label else "",
        )
        readiness = evaluate_fiscal_year_readiness(year)
        for result in readiness["layers"]:
            layer = result["record"]
            write(
                "readiness", fiscal_year=year.year, record_id=layer.pk, code=layer.layer,
                label=layer.get_layer_display(), status=layer.status,
                authority_or_evidence=layer.evidence_note, reviewed_by=layer.decided_by_label,
                state_version=layer.state_version, structural_check=result["check_message"],
                structural_passed="yes" if result["checks_passed"] else "no",
                notes="Fiscal year ready" if readiness["ready"] else "Readiness remains open",
            )

    periods = AccountingPeriod.objects.filter(department_id=department.pk)
    if fiscal_year is not None:
        periods = periods.filter(fiscal_year_record=fiscal_year)
    elif year_ids:
        periods = periods.filter(fiscal_year_record_id__in=year_ids)
    else:
        periods = periods.none()
    for item in periods.order_by("fiscal_year", "period_number", "pk"):
        write(
            "period", fiscal_year=item.fiscal_year, record_id=item.pk, code=item.period_number,
            label=item.label, status=item.status,
            category="adjustment" if item.is_adjustment_period else "regular",
            starts_on=item.starts_on, ends_on=item.ends_on, reviewed_by=item.closed_by_label,
        )

    # These dimensions are department-wide and are intentionally written once even
    # when the register is filtered to one fiscal year.
    for item in Fund.objects.filter(department_id=department.pk).order_by("code", "pk"):
        write(
            "fund", record_id=item.public_id, code=item.code, label=item.name,
            status=_status(item.is_active), category=item.category,
            starts_on=item.effective_from, ends_on=item.effective_to, notes=item.description,
        )
    for item in ResponsibilityCenter.objects.filter(department_id=department.pk).order_by("code", "pk"):
        write(
            "responsibility_center", record_id=item.public_id, code=item.code, label=item.name,
            status=_status(item.is_active), related_code=item.office_code,
            starts_on=item.effective_from, ends_on=item.effective_to, notes=item.description,
        )
    for item in LedgerAccount.objects.filter(department_id=department.pk).select_related("parent").order_by("code", "pk"):
        notes = "; ".join(filter(None, (
            f"Government account code: {item.government_account_code}" if item.government_account_code else "",
            f"Subsidiary reference: {item.subsidiary_reference_type}" if item.subsidiary_reference_type else "",
            "Posting account" if item.allow_posting else "Header account",
        )))
        write(
            "ledger_account", record_id=item.public_id, code=item.code, label=item.title,
            status=_status(item.is_active), category=item.account_type,
            parent_code=item.parent.code if item.parent_id else "", normal_balance=item.normal_balance,
            starts_on=item.effective_from, ends_on=item.effective_to, notes=notes,
        )

    funding_sources = FundingSource.objects.filter(department_id=department.pk).select_related("fiscal_year", "fund")
    programs = ProgramActivityProject.objects.filter(department_id=department.pk).select_related(
        "fiscal_year", "parent", "responsibility_center", "funding_source",
    )
    if fiscal_year is not None:
        funding_sources = funding_sources.filter(fiscal_year=fiscal_year)
        programs = programs.filter(fiscal_year=fiscal_year)
    elif year_ids:
        funding_sources = funding_sources.filter(fiscal_year_id__in=year_ids)
        programs = programs.filter(fiscal_year_id__in=year_ids)
    else:
        funding_sources = funding_sources.none()
        programs = programs.none()
    for item in funding_sources.order_by("fiscal_year__year", "code", "pk"):
        write(
            "funding_source", fiscal_year=item.fiscal_year.year, record_id=item.public_id,
            code=item.code, label=item.name, status=_status(item.is_active), category=item.kind,
            related_code=item.fund.code if item.fund_id else "", starts_on=item.effective_from,
            ends_on=item.effective_to, authority_or_evidence=item.authority_reference,
        )
    for item in programs.order_by("fiscal_year__year", "code", "pk"):
        related = "; ".join(filter(None, (
            f"Office {item.responsibility_center.code}" if item.responsibility_center_id else "",
            f"Source {item.funding_source.code}" if item.funding_source_id else "",
        )))
        write(
            "program_classification", fiscal_year=item.fiscal_year.year,
            record_id=item.public_id, code=item.code, label=item.name,
            status=_status(item.is_active), category=item.kind,
            parent_code=item.parent.code if item.parent_id else "", related_code=related,
            starts_on=item.effective_from, ends_on=item.effective_to,
            authority_or_evidence=item.authority_reference,
        )
    for item in PostingMapping.objects.filter(department_id=department.pk).select_related("account").order_by(
        "category", "source_code", "pk",
    ):
        write(
            "posting_mapping", record_id=item.pk, code=item.source_code, label=item.label,
            status=_status(item.is_active), category=item.category, related_code=item.account.code,
        )

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    year_label = str(fiscal_year.year) if fiscal_year is not None else "all-years"
    filename = f"finance-fiscal-foundation-{slugify(year_label)}.csv"
    metadata = {
        "kind": "finance_fiscal_foundation_register",
        "fiscal_year_public_id": str(fiscal_year.public_id) if fiscal_year is not None else "",
        "fiscal_year": fiscal_year.year if fiscal_year is not None else "all",
        "record_counts": counts,
        "authority_boundary": (
            "Portable setup and readiness evidence only; this export does not approve classifications, "
            "opening balances, forms, transactions, or production cutover."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-fiscal-foundation", filename=filename, metadata=metadata,
    )
    AccountingAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name,
        action="foundation_register_exported", actor_id=actor.pk, actor_label=actor_label(actor),
        snapshot={
            **metadata,
            "relative_path": receipt["relative_path"],
            "sha256": receipt["sha256"],
        },
    )
    return content, filename, receipt
