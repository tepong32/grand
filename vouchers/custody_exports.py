from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.text import slugify

from finance.models import FinanceAuditEvent
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .case_exports import visible_cases_for_user
from .models import VoucherCase


CUSTODY_REGISTER_COLUMNS = (
    "case_reference", "case_public_id", "case_stage", "requesting_office", "current_office",
    "dv_number", "dv_date", "gross_amount", "deductions", "net_amount", "template_title",
    "template_version", "template_form_status", "template_checksum", "print_version",
    "print_status", "next_custody_action", "signature_round", "output_checksum",
    "archive_relative_path", "copy_count", "printer_or_form_stock", "print_note",
    "prepared_by", "prepared_at", "printed_by", "printed_at", "tracepoint_packet",
    "tracepoint_item", "expected_document_count", "expected_page_count", "checkpoint_count",
    "assembly_note", "custody_confirmed_by", "custody_confirmed_at", "signature_tasks",
    "signatures_pending", "signatures_returned", "signatures_declined", "signed_returned_by",
    "signed_returned_at", "supersedes_print_version", "supersession_reason", "case_state_version",
    "case_updated_at",
)


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _actor_label(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def next_custody_action(case, job):
    if not job:
        if case.current_stage == VoucherCase.AWAITING_SIGNATURES:
            return "Prepare the current checksum-backed signing copy"
        return "No controlled signing copy is due at this case stage"
    if job.status == job.READY_TO_PRINT:
        return "Print, inspect, and record the actual copies and form stock"
    if job.status == job.PRINTED:
        return "Count and assemble the linked TracePoint packet"
    if job.status == job.AWAITING_SIGNATURES:
        return "Track the physical packet and record returned wet signatures"
    if job.status == job.SIGNED_PACKET_RETURNED:
        return "Retain current packet evidence for Accounting validation"
    return "Do not sign; use the current successor version"


def build_custody_register(
    *, actor, queryset, requested_role=None, stage="", transaction_type="",
    requesting_department="", attention="", custody="", search="",
):
    department = department_for_user(actor)
    if department is None or not has_explicit_permission(actor, "vouchers.view_voucher_audit"):
        raise PermissionDenied
    visible = visible_cases_for_user(actor, requested_role=requested_role)
    if queryset.exclude(pk__in=visible.values("pk")).exists():
        raise ValidationError("The DV custody register may contain only the current workbench role scope.")

    cases = list(queryset.select_related(
        "requesting_department", "current_department", "voucher_template", "disbursement_voucher",
    ).prefetch_related(
        "print_jobs__output__template", "print_jobs__prepared_by", "print_jobs__printed_by",
        "print_jobs__tracepoint_item",
        "print_jobs__custody_confirmed_by", "print_jobs__signed_returned_by", "print_jobs__supersedes",
        "signature_tasks",
    ))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(CUSTODY_REGISTER_COLUMNS)
    row_count = 0
    for case in cases:
        jobs = list(case.print_jobs.all()) or [None]
        voucher = getattr(case, "disbursement_voucher", None)
        tasks = list(case.signature_tasks.all())
        for job in jobs:
            template = job.output.template if job else case.voucher_template
            round_tasks = [item for item in tasks if job and item.round_number == job.signature_round]
            manifest = job.custody_manifest if job else {}
            values = (
                case.reference_code, case.public_id, case.get_current_stage_display(),
                case.requesting_department.name, case.current_department.name,
                voucher.dv_number if voucher else "", voucher.voucher_date if voucher else "",
                voucher.gross_amount if voucher else "", voucher.total_deductions if voucher else "",
                voucher.net_amount if voucher else "", template.title if template else "",
                template.version if template else "", template.get_form_status_display() if template else "",
                template.workbook_checksum if template else "", job.version if job else "",
                job.get_status_display() if job else "Not prepared",
                next_custody_action(case, job), job.signature_round if job else "",
                job.output_checksum if job else "", job.archive_manifest.get("relative_path", "") if job else "",
                job.copy_count if job else "", job.printer_or_form_stock if job else "",
                job.print_note if job else "", _actor_label(job.prepared_by) if job else "",
                job.prepared_at.isoformat() if job else "", _actor_label(job.printed_by) if job else "",
                job.printed_at.isoformat() if job and job.printed_at else "",
                job.packet_reference if job else "",
                job.tracepoint_item.reference_number if job and job.tracepoint_item_id else "",
                manifest.get("expected_document_count", ""), manifest.get("expected_page_count", ""),
                len(manifest.get("checkpoints", [])), manifest.get("assembly_note", ""),
                _actor_label(job.custody_confirmed_by) if job else "",
                job.custody_confirmed_at.isoformat() if job and job.custody_confirmed_at else "",
                len(round_tasks), sum(item.status == item.PENDING for item in round_tasks),
                sum(item.status == item.SIGNED_RETURNED for item in round_tasks),
                sum(item.status == item.DECLINED for item in round_tasks),
                _actor_label(job.signed_returned_by) if job else "",
                job.signed_returned_at.isoformat() if job and job.signed_returned_at else "",
                job.supersedes.version if job and job.supersedes_id else "",
                job.supersession_reason if job else "", case.state_version, case.updated_at.isoformat(),
            )
            writer.writerow(tuple(_csv_safe(value) for value in values))
            row_count += 1

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        custody, stage, transaction_type,
        f"department-{requesting_department}" if requesting_department else "", attention, search,
    ) if value) or "all-visible"
    filename = f"finance-dv-custody-register-{suffix}.csv"
    metadata = {
        "kind": "finance_dv_custody_register", "stage_filter": stage or "all",
        "transaction_type_filter": transaction_type or "all",
        "requesting_department_filter": requesting_department or "all",
        "attention_filter": attention or "all", "custody_filter": custody or "all",
        "search_filter": search, "case_count": len(cases), "print_history_row_count": row_count,
        "authority_boundary": (
            "Controlled print and custody evidence only; this register is not a wet signature, approval, "
            "payment authority, or proof that a starter/pilot form is locally accepted."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-dv-custody-register", filename=filename, metadata=metadata,
    )
    FinanceAuditEvent.objects.create(
        department=department, target_type="vouchercustodyregister", target_id=str(department.pk),
        action="dv_custody_register_exported", actor=actor,
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
