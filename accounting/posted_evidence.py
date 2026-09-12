"""Stored Accounting evidence required before a cross-store handoff may advance."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError

from .access import can_post_journals, department_for_user
from .models import JournalEntry


def require_persisted_posting(entry, actor, *, source_type):
    department = department_for_user(actor)
    if not can_post_journals(actor) or department is None:
        raise PermissionDenied
    stored = JournalEntry.objects.filter(pk=entry.pk, department_id=department.pk).first()
    if stored is None:
        raise PermissionDenied
    if stored.source_type != source_type or not stored.source_reference:
        raise ValidationError("The stored JEV does not belong to this source handoff.")
    if stored.status != JournalEntry.POSTED or not stored.posted_at or not stored.posted_by_id:
        raise ValidationError("The handoff requires a persisted, attributed posted JEV.")
    evidence = stored.audit_events.filter(action="posted").first()
    debit, credit = stored.totals
    try:
        recorded = (Decimal(evidence.snapshot["debit"]), Decimal(evidence.snapshot["credit"])) if evidence else None
        if recorded is not None and not all(value.is_finite() for value in recorded):
            recorded = None
    except (InvalidOperation, KeyError, TypeError, ValueError):
        recorded = None
    if (evidence is None or evidence.actor_id != stored.posted_by_id
            or evidence.department_id != stored.department_id
            or debit <= 0 or debit != credit or recorded != (debit, credit)):
        raise ValidationError("Stored posting attribution or exact ledger totals do not reproduce the posting event.")
    return stored


def verify_source_link(source, entry, *, source_type):
    """Validate both ends even on recovery of an already materialized journal."""
    digest = lambda value: hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    if (source.finance_department_id != entry.department_id or entry.source_type != source_type
            or entry.source_reference != str(source.public_id)
            or (source.accounting_entry_public_id and source.accounting_entry_public_id != entry.public_id)):
        raise ValidationError("The source and stored JEV do not share the same office and immutable identity.")
    if digest(source.payload) != source.payload_checksum:
        raise ValidationError("The retained source payload checksum no longer matches its content.")
    if source.posting_rule_snapshot and digest(source.posting_rule_snapshot) != source.posting_rule_checksum:
        raise ValidationError("The retained posting-rule checksum no longer matches its content.")
    snapshot = entry.source_snapshot or {}
    if snapshot.get("payload_checksum") != source.payload_checksum or snapshot.get("posting_rule_checksum", "") != source.posting_rule_checksum:
        raise ValidationError("The stored JEV no longer reproduces its retained source and rule checksums.")
    if entry.reference != source.jev_number or entry.entry_date != source.jev_date:
        raise ValidationError("The stored JEV number/date differs from its retained source.")
    if source_type == "voucher":
        if snapshot.get("voucher_case") != str(source.case.public_id):
            raise ValidationError("The stored JEV points to a different voucher case.")
    elif source_type in ('collection', 'deposit', 'collection_fix'):
        if snapshot.get('collection_source') != str(source.source.public_id):
            raise ValidationError('The stored JEV points to a different collection/deposit source.')
    elif snapshot.get("remittance_batch") != str(source.batch.public_id):
        raise ValidationError("The stored JEV points to a different remittance batch.")
