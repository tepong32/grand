from __future__ import annotations

import hashlib
import json

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from accounting.models import LedgerAccount

from .models import FinanceStatementLine, FinanceStatementMapping, FinanceStatementMappingEvent


STARTER_LINES = {
    FinanceStatementMapping.POSITION: (
        (10, "assets", "Assets", "assets", "Assets", "asset"),
        (20, "liabilities", "Liabilities", "liabilities", "Liabilities", "liability"),
        (30, "equity", "Equity", "equity", "Equity", "equity"),
    ),
    FinanceStatementMapping.PERFORMANCE: (
        (10, "revenue", "Revenue", "revenue", "Revenue", "revenue"),
        (20, "expenses", "Expenses", "expenses", "Expenses", "expense"),
    ),
}


def statement_mapping_snapshot(mapping):
    return {
        "public_id": str(mapping.public_id),
        "department_id": mapping.department_id,
        "statement_type": mapping.statement_type,
        "version": mapping.version,
        "title": mapping.title,
        "description": mapping.description,
        "status": mapping.status,
        "authority_reference": mapping.authority_reference,
        "local_acceptance_note": mapping.local_acceptance_note,
        "lines": [
            {
                "position": line.position,
                "section_code": line.section_code,
                "section_title": line.section_title,
                "line_code": line.line_code,
                "line_title": line.line_title,
                "selector_type": line.selector_type,
                "account_type": line.account_type,
                "account_codes": list(line.account_codes or []),
            }
            for line in mapping.lines.order_by("position", "pk")
        ],
    }


def snapshot_checksum(snapshot):
    payload = json.dumps(
        snapshot, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_statement_mapping(department, statement_type):
    mappings = FinanceStatementMapping.objects.filter(
        department=department, statement_type=statement_type,
    )
    return mappings.filter(status=FinanceStatementMapping.ACTIVE).first() or mappings.filter(
        status=FinanceStatementMapping.STARTER,
    ).first()


def mapping_coverage(mapping):
    allowed_types = (
        {"asset", "liability", "equity"}
        if mapping.statement_type == FinanceStatementMapping.POSITION
        else {"revenue", "expense"}
    )
    accounts = list(LedgerAccount.objects.filter(
        department_id=mapping.department_id, allow_posting=True, is_active=True,
        account_type__in=allowed_types,
    ).order_by("code"))
    by_code = {account.code: account for account in accounts}
    assignments = {}
    errors = []
    for line in mapping.lines.order_by("position", "pk"):
        if line.selector_type == FinanceStatementLine.ACCOUNT_TYPE:
            selected = [account.code for account in accounts if account.account_type == line.account_type]
        else:
            selected = list(line.account_codes or [])
            for code in selected:
                account = by_code.get(code)
                if not account:
                    errors.append(f"{line.line_title}: {code} is not an active posting account for this statement.")
        for code in selected:
            if code in assignments:
                errors.append(f"{code} is assigned to both {assignments[code]} and {line.line_title}.")
            else:
                assignments[code] = line.line_title
    unmapped = [account.code for account in accounts if account.code not in assignments]
    if unmapped:
        errors.append("Unmapped active posting accounts: " + ", ".join(unmapped))
    if not mapping.lines.exists():
        errors.append("Add at least one statement line before review.")
    return {
        "valid": not errors,
        "errors": errors,
        "active_account_count": len(accounts),
        "mapped_account_count": len(assignments),
        "unmapped_account_codes": unmapped,
    }


def seed_statement_starters(department, actor):
    created = []
    for statement_type, starter_lines in STARTER_LINES.items():
        if FinanceStatementMapping.objects.filter(
            department=department, statement_type=statement_type,
        ).exists():
            continue
        mapping = FinanceStatementMapping.objects.create(
            department=department, statement_type=statement_type, version=1,
            title=dict(FinanceStatementMapping.STATEMENT_CHOICES)[statement_type],
            description=(
                "Broad, human-editable management starter. Adopt an independently reviewed successor "
                "after the municipality confirms its current COA mapping and signed reference statements."
            ),
            status=FinanceStatementMapping.DRAFT, created_by=actor,
        )
        for position, section_code, section_title, line_code, line_title, account_type in starter_lines:
            FinanceStatementLine.objects.create(
                mapping=mapping, position=position, section_code=section_code,
                section_title=section_title, line_code=line_code, line_title=line_title,
                selector_type=FinanceStatementLine.ACCOUNT_TYPE, account_type=account_type,
            )
        mapping.status = FinanceStatementMapping.STARTER
        snapshot = statement_mapping_snapshot(mapping)
        mapping.snapshot_checksum = snapshot_checksum(snapshot)
        mapping.save(update_fields=("snapshot_checksum", "status", "updated_at"))
        FinanceStatementMappingEvent.objects.create(
            mapping=mapping, actor=actor, action="starter_seeded",
            reason="Controlled broad starter; local signed-statement comparison remains pending.",
            snapshot=snapshot,
        )
        created.append(mapping)
    return created


def submit_statement_mapping(mapping, actor):
    if not mapping.is_editable:
        raise ValidationError("Only an editable draft can be submitted.")
    coverage = mapping_coverage(mapping)
    if not coverage["valid"]:
        raise ValidationError(coverage["errors"])
    mapping.status = FinanceStatementMapping.SUBMITTED
    mapping.submitted_by = actor
    mapping.submitted_at = timezone.now()
    mapping.review_note = ""
    mapping.save(update_fields=("status", "submitted_by", "submitted_at", "review_note", "updated_at"))
    FinanceStatementMappingEvent.objects.create(
        mapping=mapping, actor=actor, action="submitted", snapshot=statement_mapping_snapshot(mapping),
    )
    return mapping


@transaction.atomic
def review_statement_mapping(mapping, actor, *, approve, note=""):
    if mapping.status != FinanceStatementMapping.SUBMITTED:
        raise ValidationError("Only a submitted mapping can be independently reviewed.")
    if mapping.created_by_id == actor.pk or mapping.submitted_by_id == actor.pk:
        raise ValidationError("The preparer or submitter cannot approve or return the same mapping.")
    note = (note or "").strip()
    if not approve:
        if not note:
            raise ValidationError("Explain the correction required before returning the mapping.")
        mapping.status = FinanceStatementMapping.RETURNED
        mapping.reviewed_by = actor
        mapping.reviewed_at = timezone.now()
        mapping.review_note = note
        mapping.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        FinanceStatementMappingEvent.objects.create(
            mapping=mapping, actor=actor, action="returned", reason=note,
            snapshot=statement_mapping_snapshot(mapping),
        )
        return mapping

    coverage = mapping_coverage(mapping)
    if not coverage["valid"]:
        raise ValidationError(coverage["errors"])
    if not mapping.authority_reference.strip() or not mapping.local_acceptance_note.strip():
        raise ValidationError("Record both the reviewed authority and local acceptance evidence before activation.")
    prior = FinanceStatementMapping.objects.select_for_update().filter(
        department=mapping.department, statement_type=mapping.statement_type,
        status=FinanceStatementMapping.ACTIVE,
    ).first()
    mapping.reviewed_by = actor
    mapping.reviewed_at = timezone.now()
    mapping.review_note = note
    mapping.status = FinanceStatementMapping.ACTIVE
    snapshot = statement_mapping_snapshot(mapping)
    mapping.snapshot_checksum = snapshot_checksum(snapshot)
    if prior:
        prior.status = FinanceStatementMapping.SUPERSEDED
        prior.save(update_fields=("status", "updated_at"))
        FinanceStatementMappingEvent.objects.create(
            mapping=prior, actor=actor, action="superseded", reason=f"Replaced by version {mapping.version}.",
            snapshot=statement_mapping_snapshot(prior),
        )
    mapping.full_clean()
    mapping.save(update_fields=(
        "status", "reviewed_by", "reviewed_at", "review_note", "snapshot_checksum", "updated_at",
    ))
    FinanceStatementMappingEvent.objects.create(
        mapping=mapping, actor=actor, action="activated", reason=note, snapshot=snapshot,
    )
    return mapping
