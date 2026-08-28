from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from openpyxl import load_workbook

from .access import can_approve_finance_configuration, can_manage_finance_configuration, can_manage_finance_templates
from .models import (
    FinanceAuditEvent, FinanceConfigurationItem, FinanceConfigurationRelease,
    FinanceNumberingSequence, FinanceParty, FinanceSignatory, FinanceTemplateVersion,
)


class FinanceTemplateError(ValueError):
    pass


def _snapshot(instance):
    data = model_to_dict(instance)
    for key, value in tuple(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif isinstance(value, uuid_types()):
            data[key] = str(value)
        elif hasattr(value, "name"):
            data[key] = value.name
    return data


def uuid_types():
    import uuid
    return (uuid.UUID,)


def record_event(instance, actor, action, reason="", evidence=None):
    release = instance if isinstance(instance, FinanceConfigurationRelease) else getattr(instance, "release", None)
    snapshot = _snapshot(instance)
    if evidence:
        snapshot["workflow_exemption"] = evidence
    return FinanceAuditEvent.objects.create(
        department=instance.department, release=release, target_type=instance._meta.model_name,
        target_id=str(instance.pk), action=action, actor=actor, reason=reason,
        snapshot=snapshot,
    )


@transaction.atomic
def transition_release(release, action, actor, reason=""):
    release = FinanceConfigurationRelease.objects.select_for_update().get(pk=release.pk)
    workflow_exemption = None
    if action == "submit":
        if not can_manage_finance_configuration(actor, release.department):
            raise PermissionDenied
        if release.status != "draft":
            raise ValidationError("Only draft releases can be submitted.")
        release.status, release.submitted_by, release.submitted_at = "submitted", actor, timezone.now()
        release.items.filter(status="draft").update(status="submitted")
        release.templates.filter(status="draft").update(status="submitted")
        release.signatories.filter(status="draft").update(status="submitted")
        release.parties.filter(status="draft").update(status="submitted")
        release.numbering_sequences.filter(status="draft").update(status="submitted")
        fields = ("status", "submitted_by", "submitted_at", "updated_at")
    elif action == "approve":
        if not can_approve_finance_configuration(actor, release.department):
            raise PermissionDenied
        if release.status != "submitted":
            raise ValidationError("Only submitted releases can be approved.")
        if actor.pk in {release.created_by_id, release.submitted_by_id}:
            from .exemptions import workflow_exemption_for, workflow_exemption_snapshot
            from .models import FinanceWorkflowExemption

            exemption = workflow_exemption_for(
                actor=actor,
                control_code=FinanceWorkflowExemption.RELEASE_SELF_APPROVAL,
                department_id=release.department_id,
            )
            if exemption is None:
                raise ValidationError(
                    "The approver must be different from the release preparer and submitter unless an active "
                    "administrator-authorized workflow exemption applies."
                )
            workflow_exemption = workflow_exemption_snapshot(exemption)
        if not reason.strip():
            raise ValidationError("Record the local Accounting approval basis before approval.")
        failed_templates = release.templates.exclude(preflighted_at__isnull=False, preflight_result__passed=True)
        if failed_templates.exists():
            raise ValidationError("Every workbook template in the release must pass preflight before approval.")
        try:
            for template in release.templates.all():
                verify_template_evidence(template)
        except FinanceTemplateError as exc:
            raise ValidationError(str(exc)) from exc
        release.status, release.approved_by, release.approved_at = "approved", actor, timezone.now()
        release.items.filter(status="submitted").update(status="approved")
        release.templates.filter(status="submitted").update(status="approved")
        release.signatories.filter(status="submitted").update(status="approved")
        release.parties.filter(status="submitted").update(status="approved")
        for party in release.parties.all():
            party.authorized_claimants.filter(status="draft").update(status="approved")
        release.numbering_sequences.filter(status="submitted").update(status="approved")
        release.accounting_approval_note = reason.strip()
        fields = ("status", "approved_by", "approved_at", "accounting_approval_note", "updated_at")
    elif action == "activate":
        if not can_approve_finance_configuration(actor, release.department):
            raise PermissionDenied
        if release.status not in {"approved", "scheduled"}:
            raise ValidationError("Only approved or scheduled releases can be activated.")
        if release.effective_from > timezone.localdate():
            raise ValidationError("A future-dated release must be scheduled and cannot activate early.")
        if release.effective_to and release.effective_to < timezone.localdate():
            raise ValidationError("An expired configuration release cannot be activated.")
        try:
            for template in release.templates.all():
                verify_template_evidence(template)
        except FinanceTemplateError as exc:
            raise ValidationError(str(exc)) from exc
        readiness = evaluate_readiness(release, as_of=release.effective_from)
        if not readiness["ready"]:
            raise ValidationError("Activation is blocked: " + "; ".join(item["message"] for item in readiness["blocking"]))
        preceding = list(FinanceConfigurationRelease.objects.select_for_update().filter(
            department=release.department, status="active"
        ).exclude(pk=release.pk))
        for prior in preceding:
            prior.status = "superseded"
            prior.save(update_fields=("status", "updated_at"))
            prior.items.filter(status="active").update(status="superseded")
            prior.templates.filter(status="active").update(status="superseded")
            prior.signatories.filter(status="active").update(status="superseded")
            prior.parties.filter(status="active").update(status="superseded")
            for party in prior.parties.all():
                party.authorized_claimants.filter(status="active").update(status="superseded")
            prior.numbering_sequences.filter(status="active").update(status="superseded")
            record_event(prior, actor, "superseded", f"Superseded by {release}.")
        release.status, release.activated_by, release.activated_at = "active", actor, timezone.now()
        release.items.filter(status__in=("approved", "scheduled")).update(status="active")
        release.templates.filter(status__in=("approved", "scheduled")).update(status="active")
        release.signatories.filter(status__in=("approved", "scheduled")).update(status="active")
        release.parties.filter(status__in=("approved", "scheduled")).update(status="active")
        for party in release.parties.all():
            party.authorized_claimants.filter(status__in=("approved", "scheduled")).update(status="active")
        release.numbering_sequences.filter(status__in=("approved", "scheduled")).update(status="active")
        fields = ("status", "activated_by", "activated_at", "updated_at")
    elif action == "schedule":
        if not can_approve_finance_configuration(actor, release.department):
            raise PermissionDenied
        if release.status != "approved" or release.effective_from <= timezone.localdate():
            raise ValidationError("Scheduling requires an approved release with a future effective date.")
        release.status = "scheduled"
        release.items.filter(status="approved").update(status="scheduled")
        release.templates.filter(status="approved").update(status="scheduled")
        release.signatories.filter(status="approved").update(status="scheduled")
        release.parties.filter(status="approved").update(status="scheduled")
        release.numbering_sequences.filter(status="approved").update(status="scheduled")
        fields = ("status", "updated_at")
    elif action == "rollback":
        if not can_approve_finance_configuration(actor, release.department):
            raise PermissionDenied
        if release.status != "superseded":
            raise ValidationError("Only a previously superseded release can be restored.")
        if not reason.strip():
            raise ValidationError("Record the Accounting rollback basis.")
        readiness = evaluate_readiness(release, as_of=timezone.localdate())
        if not readiness["ready"]:
            raise ValidationError("Rollback is blocked: " + "; ".join(item["message"] for item in readiness["blocking"]))
        current = list(FinanceConfigurationRelease.objects.select_for_update().filter(department=release.department, status="active"))
        for prior in current:
            prior.status = "superseded"
            prior.save(update_fields=("status", "updated_at"))
            record_event(prior, actor, "superseded_by_rollback", f"Replaced by rollback to {release}.")
        release.status, release.activated_by, release.activated_at = "active", actor, timezone.now()
        release.items.filter(status="superseded").update(status="active")
        release.templates.filter(status="superseded").update(status="active")
        release.signatories.filter(status="superseded").update(status="active")
        release.parties.filter(status="superseded").update(status="active")
        for party in release.parties.all():
            party.authorized_claimants.filter(status="superseded").update(status="active")
        release.numbering_sequences.filter(status="superseded").update(status="active")
        fields = ("status", "activated_by", "activated_at", "updated_at")
    elif action == "retire":
        if not can_approve_finance_configuration(actor, release.department):
            raise PermissionDenied
        if release.status not in {"approved", "scheduled", "active", "superseded"}:
            raise ValidationError("This release cannot be retired from its current state.")
        release.status = "retired"
        fields = ("status", "updated_at")
    else:
        raise ValidationError("Unsupported finance release action.")
    release.save(update_fields=fields)
    record_event(release, actor, action, reason, evidence=workflow_exemption)
    return release


def evaluate_readiness(release, as_of=None):
    as_of = as_of or timezone.localdate()
    governed_statuses = ("approved", "scheduled", "active", "superseded")
    items = release.items.filter(status__in=governed_statuses, effective_from__lte=as_of).filter(
        models_q_open_ended("effective_to", as_of)
    )
    categories = set(items.values_list("category", flat=True))
    checks = [
        ("approved_voucher_template", release.templates.filter(status__in=governed_statuses, preflighted_at__isnull=False, effective_from__lte=as_of).filter(models_q_open_ended("effective_to", as_of)).exists(), "An approved, checksum-verified voucher template applies.", "No approved, preflighted voucher template applies."),
        ("transaction_type_checklist", "transaction_type" in categories and "document_requirement" in categories, "An approved transaction type and supporting-document checklist apply.", "A transaction type and its supporting-document checklist are required."),
        ("active_signatory", release.signatories.filter(status__in=governed_statuses, valid_from__lte=as_of).filter(models_q_open_ended("valid_to", as_of)).exists(), "An approved signatory assignment covers the applicable date.", "No approved signatory is valid for the applicable date."),
        ("fund_and_payment_account", "fund" in categories and bool(categories & {"bank_account", "payment_method"}), "An approved fund and payment account or method apply.", "An approved fund and payment account or method are required."),
        ("approved_tax_rule", "tax_rule" in categories, "An approved tax/deduction rule is available.", "No approved tax/deduction rule is available."),
        ("numbering_sequence", release.numbering_sequences.filter(status__in=governed_statuses, fiscal_year=release.fiscal_year).exists(), f"An approved numbering sequence covers fiscal year {release.fiscal_year}.", f"No approved numbering sequence exists for fiscal year {release.fiscal_year}."),
    ]
    conflicts = FinanceConfigurationRelease.objects.filter(
        department=release.department, status__in=("scheduled", "active"), effective_from__lte=release.effective_to or date.max,
    ).exclude(pk=release.pk).filter(models_q_open_ended("effective_to", release.effective_from)).exists()
    checks.append(("activation_date_conflict", not conflicts, "No scheduled or active release overlaps this effective period.", "The release effective dates overlap another scheduled or active release."))
    result = [{"code": code, "passed": passed, "message": success if passed else failure, "help_anchor": f"finance-readiness-{code}"} for code, passed, success, failure in checks]
    blocking = [item for item in result if not item["passed"]]
    return {"ready": not blocking, "checks": result, "blocking": blocking, "as_of": as_of.isoformat(), "sandbox_available": True}


def models_q_open_ended(field, value):
    from django.db.models import Q
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__gte": value})


def _workbook_bytes(template):
    template.workbook.open("rb")
    try:
        return template.workbook.read()
    finally:
        template.workbook.close()


def _destination(workbook, name):
    defined = workbook.defined_names.get(name)
    if not defined:
        raise FinanceTemplateError(f"Missing required workbook-level named range: {name}.")
    destinations = list(defined.destinations)
    if len(destinations) != 1:
        raise FinanceTemplateError(f"{name} must point to exactly one worksheet range.")
    sheet_name, coordinate = destinations[0]
    if sheet_name not in workbook.sheetnames:
        raise FinanceTemplateError(f"{name} points to a worksheet that does not exist.")
    return workbook[sheet_name], coordinate


def inspect_finance_workbook(payload, document_type="disbursement-voucher"):
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            names = {member.filename.lower() for member in members}
            if sum(member.file_size for member in members) > 50 * 1024 * 1024 or any(member.file_size > 25 * 1024 * 1024 for member in members):
                raise FinanceTemplateError("The expanded workbook is too large to inspect safely.")
    except (zipfile.BadZipFile, OSError) as exc:
        raise FinanceTemplateError("The uploaded file is not a valid macro-free XLSX workbook.") from exc
    if any("vbaproject" in name or name.endswith(".bin") for name in names):
        raise FinanceTemplateError("Macro-enabled workbook content is not allowed.")
    if any(name.startswith("xl/externallinks/") for name in names):
        raise FinanceTemplateError("External workbook links are not allowed.")
    try:
        workbook = load_workbook(io.BytesIO(payload), data_only=False, keep_links=False)
    except Exception as exc:
        raise FinanceTemplateError("The XLSX workbook could not be opened safely.") from exc
    suspicious = ("WEBSERVICE(", "HYPERLINK(", "RTD(", "DDE(", "CALL(")
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    normalized = cell.value.upper().replace(" ", "")
                    if "[" in cell.value or any(token in normalized for token in suspicious):
                        raise FinanceTemplateError(f"Suspicious or externally linked formula found in {sheet.title}!{cell.coordinate}.")
    schema = FinanceTemplateVersion.schema_for(document_type)
    if not schema:
        raise FinanceTemplateError("That finance document type does not have an approved controlled-range schema.")
    mapping = {}
    table_name = schema["table"]
    for name in schema["required"]:
        sheet, coordinate = _destination(workbook, name)
        if name != table_name:
            area = sheet[coordinate]
            if isinstance(area, tuple):
                flattened = [cell for row in area for cell in (row if isinstance(row, tuple) else (row,))]
                if len(flattened) != 1:
                    raise FinanceTemplateError(f"{name} must point to exactly one cell.")
        mapping[name] = {"worksheet": sheet.title, "range": coordinate}
    row_capacity = 0
    if table_name:
        line_sheet, line_coordinate = _destination(workbook, table_name)
        area = line_sheet[line_coordinate]
        if not isinstance(area, tuple):
            area = ((area,),)
        elif area and not isinstance(area[0], tuple):
            area = (area,)
        row_capacity = len(area)
        if row_capacity < 1:
            raise FinanceTemplateError(f"{table_name} must reserve at least one row.")
    print_sheets = [sheet.title for sheet in workbook.worksheets if sheet.print_area]
    if not print_sheets:
        raise FinanceTemplateError("Set a print area before submitting the voucher workbook.")
    mapped_sheets = {value["worksheet"] for value in mapping.values()}
    if mapped_sheets - set(print_sheets):
        raise FinanceTemplateError("Every worksheet receiving a controlled GRAND field must define a print area.")
    return workbook, mapping, {
        "passed": True, "worksheets": len(workbook.sheetnames), "required_names": len(mapping),
        "line_item_row_capacity": row_capacity, "print_area_sheets": print_sheets,
        "message": "Macro-free workbook, controlled names, formulas, print areas, and row capacity passed preflight.",
    }


@transaction.atomic
def preflight_finance_template(template, actor):
    if not can_manage_finance_templates(actor, template.department):
        raise PermissionDenied
    if template.status != "draft":
        raise ValidationError("Only draft template versions can be preflighted.")
    payload = _workbook_bytes(template)
    _workbook, mapping, result = inspect_finance_workbook(payload, template.document_type)
    template.workbook_checksum = hashlib.sha256(payload).hexdigest()
    template.mapping = mapping
    template.mapping_checksum = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    template.preflight_result = result
    template.preflighted_by = actor
    template.preflighted_at = timezone.now()
    template.full_clean()
    template.save(update_fields=("workbook_checksum", "mapping", "mapping_checksum", "preflight_result", "preflighted_by", "preflighted_at"))
    record_event(template, actor, "preflight_passed")
    return result


def verify_template_evidence(template):
    payload = _workbook_bytes(template)
    if hashlib.sha256(payload).hexdigest() != template.workbook_checksum:
        raise FinanceTemplateError(f"{template} no longer matches its preflighted workbook checksum.")
    _workbook, mapping, _result = inspect_finance_workbook(payload, template.document_type)
    mapping_checksum = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if mapping_checksum != template.mapping_checksum:
        raise FinanceTemplateError(f"{template} no longer matches its preflighted named-range mapping.")
    return True


def synthetic_preview(template, actor):
    if not can_view_template_preview(actor, template):
        raise PermissionDenied
    payload = _workbook_bytes(template)
    checksum = hashlib.sha256(payload).hexdigest()
    if not template.preflight_passed or checksum != template.workbook_checksum:
        raise FinanceTemplateError("Preview requires the exact workbook version that passed preflight.")
    workbook, _mapping, _result = inspect_finance_workbook(payload, template.document_type)
    special_values = {
        "GRAND_DV_NUMBER": "SYNTHETIC-DV-000001", "GRAND_DV_DATE": timezone.localdate(),
        "GRAND_OBR_NUMBER": "SYNTHETIC-OBR-000001", "GRAND_OBR_DATE": timezone.localdate(),
        "GRAND_ADVICE_NUMBER": "SYNTHETIC-ADV-000001", "GRAND_ADVICE_DATE": timezone.localdate(),
        "GRAND_REGISTER_DATE": timezone.localdate(), "GRAND_RELEASE_DATE": timezone.localdate(),
        "GRAND_PAYEE": "Synthetic Demonstration Payee", "GRAND_PARTICULARS": "Synthetic preview only — not an official voucher",
        "GRAND_GROSS_AMOUNT": 1000, "GRAND_OBLIGATED_AMOUNT": 1000, "GRAND_TOTAL_DEDUCTIONS": 100, "GRAND_NET_AMOUNT": 900,
        "GRAND_BANK_ACCOUNT": "SYNTHETIC BANK ACCOUNT", "GRAND_CHECK_NUMBER": "SYNTHETIC-CHECK-000001",
        "GRAND_CLAIMANT": "Synthetic Authorized Claimant", "GRAND_FUND": "Synthetic Fund",
        "GRAND_RESPONSIBILITY_CENTER": "Synthetic Office", "GRAND_ACCOUNT_CODE": "SYNTHETIC-ACCOUNT",
        "GRAND_PREPARED_BY": "Sample Preparer", "GRAND_CERTIFIED_BY": "Sample Certifier", "GRAND_APPROVED_BY": "Sample Approver",
        "GRAND_RELEASED_BY": "Sample Releasing Officer", "GRAND_ACKNOWLEDGED_BY": "Sample Claimant",
    }
    schema = FinanceTemplateVersion.schema_for(template.document_type)
    table_name = schema["table"]
    values = {name: special_values.get(name, "SYNTHETIC PREVIEW") for name in schema["required"] if name != table_name}
    for name, value in values.items():
        sheet, coordinate = _destination(workbook, name)
        cells = sheet[coordinate]
        if isinstance(cells, tuple):
            cell = cells[0][0] if isinstance(cells[0], tuple) else cells[0]
        else:
            cell = cells
        cell.value = value
    if table_name:
        sheet, coordinate = _destination(workbook, table_name)
        cells = sheet[coordinate]
        if cells and not isinstance(cells[0], tuple):
            cells = (cells,)
        sample = ("Synthetic line / check", "SYNTHETIC-CODE", 1000, 900)
        for index, cell in enumerate(cells[0]):
            cell.value = sample[index] if index < len(sample) else None
    workbook.properties.title = "GRAND synthetic finance template preview"
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def can_view_template_preview(actor, template):
    from .access import can_view_finance_setup
    return can_view_finance_setup(actor, template.department)
