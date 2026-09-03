from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from accounting.access import can_post_journals, can_prepare_journals
from accounting.models import (
    AccountingAuditEvent, AccountingPeriod, Fund, JournalEntry, JournalLine,
    JournalSubsidiaryLine, LedgerAccount, PostingMapping,
)
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceNumberingSequence, FinanceParty,
    FinancePostingRule, FinancePostingRuleLine,
)
from finance.services import posting_rule_snapshot
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import (
    RemittanceEvent, RemittanceNumberIssue, RemittancePostingRequest,
    TaxFilingEvidence, TreasuryRemittanceBatch, TreasuryRemittanceLine,
)


class RemittanceWorkflowError(ValidationError):
    pass


def _require(actor, permission):
    if not has_explicit_permission(actor, permission):
        raise PermissionDenied


def _require_treasury_scope(actor, batch):
    department = department_for_user(actor)
    if department is None or batch.treasury_department_id != department.pk:
        raise PermissionDenied("Remittance preparation and release are limited to the owning Treasury office.")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _event(batch, actor, action, previous, reason="", metadata=None):
    return RemittanceEvent.objects.create(
        batch=batch, action=action, actor=actor, actor_department=department_for_user(actor),
        from_status=previous, to_status=batch.status, reason=reason.strip(),
        metadata=metadata or {}, state_version=batch.state_version,
    )


def _consume_number(batch, actor, document_type, issue_document_type=None):
    sequence = FinanceNumberingSequence.objects.select_for_update().filter(
        release=batch.configuration_release, fiscal_year=batch.remittance_date.year,
        document_type=document_type, status="active",
    ).first()
    if sequence is None:
        raise RemittanceWorkflowError(
            f"No active {document_type} numbering sequence is configured for {batch.remittance_date.year}."
        )
    value = sequence.next_number
    formatted = f"{sequence.prefix}{value:0{sequence.padding}d}"
    RemittanceNumberIssue.objects.create(
        batch=batch, sequence=sequence, document_type=issue_document_type or document_type,
        numeric_value=value, formatted_value=formatted, issued_by=actor,
    )
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))
    return formatted


def active_release(as_of=None):
    as_of = as_of or timezone.localdate()
    return FinanceConfigurationRelease.objects.filter(
        status="active", effective_from__lte=as_of,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)).order_by("-activated_at", "-pk").first()


def _tax_scope_for_identity(*, finance_department_id, transaction_type, as_of_date, identity):
    """Return one governed rule scope only when every tagged source agrees."""
    details = JournalSubsidiaryLine.objects.filter(
        entry__department_id=finance_department_id, entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=as_of_date, category=JournalSubsidiaryLine.WITHHOLDING,
        entry__fund__code=identity["fund_code"], journal_line__account__code=identity["account_code"],
        reference_key=identity["reference_key"], source_code=identity["deduction_code"],
        source_snapshot__transaction_type=transaction_type,
    ).only("source_snapshot", "credit")
    scopes = {}
    for detail in details:
        tax = (detail.source_snapshot or {}).get("tax_reporting") or {}
        checksum = str(tax.get("tax_rule_checksum") or "")
        if detail.credit > 0 and checksum:
            scopes.setdefault(checksum, tax)
    if len(scopes) != 1:
        return {}, ""
    checksum, tax = next(iter(scopes.items()))
    keys = (
        "tax_family", "atc", "rate_percent", "tax_base_label", "return_form_code",
        "certificate_form_code", "rounding_mode", "authority_reference",
        "local_applicability_note", "tax_rule_checksum",
    )
    return {key: tax.get(key, "") for key in keys}, checksum


def withholding_availability(*, finance_department_id, transaction_type, as_of_date, include_nonpositive=False):
    """Return posted balances less live remittance reservations, with a stable row key."""
    ledger_rows = JournalSubsidiaryLine.objects.filter(
        entry__department_id=finance_department_id,
        entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=as_of_date,
        category=JournalSubsidiaryLine.WITHHOLDING,
        source_snapshot__transaction_type=transaction_type,
    ).values(
        "entry__fund__code", "journal_line__account__code", "journal_line__account__title",
        "reference_key", "reference_label", "source_code",
    ).annotate(debit_total=Sum("debit"), credit_total=Sum("credit"))
    reservations = TreasuryRemittanceLine.objects.filter(
        status=TreasuryRemittanceLine.ACTIVE,
        batch__finance_department_id=finance_department_id,
        batch__transaction_variant__code=transaction_type,
        batch__status__in=(
            TreasuryRemittanceBatch.DRAFT, TreasuryRemittanceBatch.RETURNED,
            TreasuryRemittanceBatch.FOR_REVIEW, TreasuryRemittanceBatch.APPROVED,
            TreasuryRemittanceBatch.ACCOUNTING_POSTING,
        ),
    ).values(
        "fund_code", "account_code", "reference_key", "deduction_code",
    ).annotate(total=Sum("amount"))
    reserved = {
        (row["fund_code"], row["account_code"], row["reference_key"], row["deduction_code"]): row["total"]
        for row in reservations
    }
    result = []
    for row in ledger_rows:
        identity = {
            "fund_code": row["entry__fund__code"],
            "account_code": row["journal_line__account__code"],
            "account_title": row["journal_line__account__title"],
            "reference_key": row["reference_key"],
            "reference_label": row["reference_label"],
            "deduction_code": row["source_code"],
        }
        balance = (row["credit_total"] or Decimal("0.00")) - (row["debit_total"] or Decimal("0.00"))
        held = reserved.get((identity["fund_code"], identity["account_code"], identity["reference_key"], identity["deduction_code"]), Decimal("0.00"))
        identity["ledger_balance"] = balance
        identity["reserved"] = held
        identity["available"] = balance - held
        tax_snapshot, tax_checksum = _tax_scope_for_identity(
            finance_department_id=finance_department_id, transaction_type=transaction_type,
            as_of_date=as_of_date, identity=identity,
        )
        identity["tax_rule_snapshot"] = tax_snapshot
        identity["tax_rule_checksum"] = tax_checksum
        identity["source_checksum"] = _digest({**identity, "as_of_date": as_of_date.isoformat(), "ledger_balance": str(balance), "reserved": str(held)})
        identity["choice_key"] = _digest({key: identity[key] for key in ("fund_code", "account_code", "reference_key", "deduction_code")})
        if include_nonpositive or identity["available"] > 0:
            result.append(identity)
    return sorted(result, key=lambda item: (item["fund_code"], item["reference_label"], item["account_code"]))


def _available_row(batch, choice_key):
    rows = withholding_availability(
        finance_department_id=batch.finance_department_id,
        transaction_type=batch.transaction_variant.code,
        as_of_date=batch.remittance_date,
    )
    return next((row for row in rows if row["choice_key"] == choice_key), None)


def _lock_reservation_scope(batch):
    """Serialize live reservations across batches sharing the same governed release."""
    FinanceConfigurationRelease.objects.select_for_update().get(pk=batch.configuration_release_id)


@transaction.atomic
def create_batch(*, actor, configuration_release, transaction_variant, recipient_party, fund_code,
                 bank_account_code, remittance_date, payment_method, authority_reference, evidence_reference):
    _require(actor, "vouchers.prepare_remittances")
    treasury_department = department_for_user(actor)
    if treasury_department is None:
        raise PermissionDenied("Assign the preparer to a Treasury department before creating a remittance.")
    configuration_release = FinanceConfigurationRelease.objects.select_for_update().get(
        pk=configuration_release.pk,
    )
    transaction_variant = type(transaction_variant).objects.get(pk=transaction_variant.pk)
    recipient_party = FinanceParty.objects.get(pk=recipient_party.pk)
    today = timezone.localdate()
    if not isinstance(remittance_date, date):
        raise RemittanceWorkflowError("Enter a valid remittance date.")
    if (
        configuration_release.status != "active"
        or configuration_release.effective_from > today
        or (configuration_release.effective_to is not None and configuration_release.effective_to < today)
    ):
        raise RemittanceWorkflowError("Choose the currently active Accounting-approved Finance Setup release.")
    if (
        transaction_variant.release_id != configuration_release.pk
        or transaction_variant.status != "active"
        or transaction_variant.effective_from > remittance_date
        or (transaction_variant.effective_to is not None and transaction_variant.effective_to < remittance_date)
    ):
        raise RemittanceWorkflowError("Choose a transaction variant active for the remittance date from the pinned release.")
    if (
        recipient_party.release_id != configuration_release.pk
        or recipient_party.party_type != FinanceParty.AGENCY
        or recipient_party.status != "active"
        or recipient_party.effective_from > remittance_date
        or (recipient_party.effective_to is not None and recipient_party.effective_to < remittance_date)
    ):
        raise RemittanceWorkflowError("Choose an active receiving government agency for the remittance date.")
    fund_code = str(fund_code or "").strip()
    bank_account_code = str(bank_account_code or "").strip()
    configured = set(FinanceConfigurationItem.objects.filter(
        release=configuration_release, status="active",
        category__in=("fund", "bank_account"),
        effective_from__lte=remittance_date,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=remittance_date),
    ).values_list("category", "code"))
    if ("fund", fund_code) not in configured or ("bank_account", bank_account_code) not in configured:
        raise RemittanceWorkflowError("Choose an active fund and bank/payment account from the pinned Finance Setup release.")
    payment_method = str(payment_method or "").strip()
    authority_reference = str(authority_reference or "").strip()
    evidence_reference = str(evidence_reference or "").strip()
    if not payment_method or not authority_reference or not evidence_reference:
        raise RemittanceWorkflowError("Record the payment method, reviewed authority, and retained evidence reference.")
    batch = TreasuryRemittanceBatch(
        reference_code=f"PENDING-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
        configuration_release=configuration_release, transaction_variant=transaction_variant,
        recipient_party=recipient_party, treasury_department=treasury_department,
        finance_department_id=configuration_release.department_id,
        finance_department_label=configuration_release.department.name,
        fund_code=fund_code, bank_account_code=bank_account_code,
        remittance_date=remittance_date, payment_method=payment_method,
        authority_reference=authority_reference, evidence_reference=evidence_reference,
        created_by=actor,
    )
    batch.full_clean(); batch.save()
    batch.reference_code = _consume_number(batch, actor, "deduction-remittance")
    batch.save(update_fields=("reference_code", "updated_at"))
    _event(batch, actor, "batch_created", "", metadata={"fund_code": fund_code, "recipient": recipient_party.display_name})
    return batch


@transaction.atomic
def add_line(*, batch, actor, choice_key, amount, reason):
    _require(actor, "vouchers.prepare_remittances")
    locked = TreasuryRemittanceBatch.objects.select_for_update().get(pk=batch.pk)
    _require_treasury_scope(actor, locked)
    _lock_reservation_scope(locked)
    if locked.status not in {locked.DRAFT, locked.RETURNED}:
        raise RemittanceWorkflowError("Allocations can be changed only before submission or after an Accounting return.")
    row = _available_row(locked, choice_key)
    if row is None:
        raise RemittanceWorkflowError("That posted withholding balance is no longer available. Refresh the batch.")
    if row["fund_code"] != locked.fund_code:
        raise RemittanceWorkflowError("One remittance batch must use one fund. Start another batch for a different fund.")
    try:
        amount = Decimal(amount)
    except (ArithmeticError, TypeError, ValueError):
        raise RemittanceWorkflowError("Enter a valid remittance allocation amount.")
    if not amount.is_finite() or amount.as_tuple().exponent < -2 or amount <= 0 or amount > row["available"]:
        raise RemittanceWorkflowError(f"Enter an amount up to the currently available {row['available']:,.2f}.")
    reason = str(reason or "").strip()
    if not reason:
        raise RemittanceWorkflowError("Record why this posted withholding balance belongs in the schedule.")
    line = TreasuryRemittanceLine(
        batch=locked, fund_code=row["fund_code"], account_code=row["account_code"],
        account_title=row["account_title"], reference_key=row["reference_key"],
        reference_label=row["reference_label"], deduction_code=row["deduction_code"],
        source_as_of_date=locked.remittance_date, available_balance_snapshot=row["available"],
        amount=amount, source_checksum=row["source_checksum"],
        tax_rule_snapshot=row["tax_rule_snapshot"], tax_rule_checksum=row["tax_rule_checksum"],
        change_reason=reason, created_by=actor,
    )
    line.full_clean(); line.save()
    locked.total_amount = locked.lines.filter(status=TreasuryRemittanceLine.ACTIVE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    locked.state_version += 1; locked.save(update_fields=("total_amount", "state_version", "updated_at"))
    _event(locked, actor, "allocation_added", locked.status, reason, {"line": line.pk, "amount": str(amount), "source_checksum": line.source_checksum})
    return line


@transaction.atomic
def revise_line(*, line, actor, amount, reason):
    _require(actor, "vouchers.prepare_remittances")
    current = TreasuryRemittanceLine.objects.select_for_update().select_related("batch").get(pk=line.pk)
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=current.batch_id)
    _require_treasury_scope(actor, batch)
    _lock_reservation_scope(batch)
    if current.status != current.ACTIVE or batch.status not in {batch.DRAFT, batch.RETURNED}:
        raise RemittanceWorkflowError("Only an active pre-submission allocation can be revised.")
    reason = str(reason or "").strip()
    if not reason:
        raise RemittanceWorkflowError("Explain the allocation modification.")
    try:
        amount = Decimal(amount)
    except (ArithmeticError, TypeError, ValueError):
        raise RemittanceWorkflowError("Enter a valid revised remittance amount.")
    available_without_self = next((row for row in withholding_availability(
        finance_department_id=batch.finance_department_id,
        transaction_type=batch.transaction_variant.code,
        as_of_date=batch.remittance_date,
        include_nonpositive=True,
    ) if row["fund_code"] == current.fund_code and row["account_code"] == current.account_code and row["reference_key"] == current.reference_key and row["deduction_code"] == current.deduction_code), None)
    if available_without_self is None:
        raise RemittanceWorkflowError(
            "The original posted withholding balance no longer exists. Stop and route the batch for reconciliation."
        )
    capacity = available_without_self["available"] + current.amount
    if not amount.is_finite() or amount.as_tuple().exponent < -2 or amount < 0 or amount > capacity:
        raise RemittanceWorkflowError(f"Enter zero to remove, or an amount up to {capacity:,.2f}.")
    current.status = current.REMOVED if amount == 0 else current.SUPERSEDED
    TreasuryRemittanceLine.objects.filter(pk=current.pk).update(status=current.status)
    successor = TreasuryRemittanceLine(
        batch=batch, lineage_key=current.lineage_key, version=current.version + 1,
        status=TreasuryRemittanceLine.REMOVED if amount == 0 else TreasuryRemittanceLine.ACTIVE,
        supersedes=current, fund_code=current.fund_code, account_code=current.account_code,
        account_title=current.account_title, reference_key=current.reference_key,
        reference_label=current.reference_label, deduction_code=current.deduction_code,
        source_as_of_date=batch.remittance_date, available_balance_snapshot=capacity,
        amount=amount if amount > 0 else current.amount, source_checksum=current.source_checksum,
        tax_rule_snapshot=current.tax_rule_snapshot, tax_rule_checksum=current.tax_rule_checksum,
        change_reason=reason, created_by=actor,
    )
    successor.full_clean(); successor.save()
    batch.total_amount = batch.lines.filter(status=TreasuryRemittanceLine.ACTIVE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    batch.state_version += 1; batch.save(update_fields=("total_amount", "state_version", "updated_at"))
    _event(batch, actor, "allocation_removed" if amount == 0 else "allocation_revised", batch.status, reason, {"prior_line": current.pk, "successor_line": successor.pk, "amount": str(amount)})
    return successor


def _validate_live_lines(batch):
    lines = list(batch.lines.filter(status=TreasuryRemittanceLine.ACTIVE))
    if not lines:
        raise RemittanceWorkflowError("Add at least one posted withholding balance before submission.")
    current = withholding_availability(
        finance_department_id=batch.finance_department_id,
        transaction_type=batch.transaction_variant.code,
        as_of_date=batch.remittance_date,
        include_nonpositive=True,
    )
    available = {(r["fund_code"], r["account_code"], r["reference_key"], r["deduction_code"]): r["available"] for r in current}
    for line in lines:
        key = (line.fund_code, line.account_code, line.reference_key, line.deduction_code)
        if key not in available:
            raise RemittanceWorkflowError(
                f"The posted withholding balance for {line.reference_label} no longer exists. Return to preparation and reconcile it."
            )
        remaining = available[key]
        if remaining < 0:
            raise RemittanceWorkflowError(f"The available balance for {line.reference_label} changed. Return to preparation and refresh it.")
    total = sum((line.amount for line in lines), Decimal("0.00"))
    if total != batch.total_amount or total <= 0:
        raise RemittanceWorkflowError("The active allocation lines must equal the positive remittance control total.")
    return lines


@transaction.atomic
def submit_batch(*, batch, actor):
    _require(actor, "vouchers.prepare_remittances")
    locked = TreasuryRemittanceBatch.objects.select_for_update().select_related("transaction_variant").get(pk=batch.pk)
    _require_treasury_scope(actor, locked)
    _lock_reservation_scope(locked)
    if locked.status not in {locked.DRAFT, locked.RETURNED}:
        raise RemittanceWorkflowError("Only a draft or returned remittance can be submitted.")
    _validate_live_lines(locked)
    rule = locked.transaction_variant.posting_rules.filter(event_kind=FinancePostingRule.REMITTANCE).first()
    if rule is None or rule.recognition_point != FinancePostingRule.DEDUCTION_REMITTANCE:
        raise RemittanceWorkflowError("The selected variant needs a locally reviewed remittance rule at deduction/withholding remittance.")
    if rule.accounting_effect != FinancePostingRule.JOURNAL_ENTRY:
        raise RemittanceWorkflowError("A remittance must reduce its posted withholding liability through a governed journal entry.")
    snapshot, checksum = posting_rule_snapshot(rule)
    previous = locked.status
    locked.status = locked.FOR_REVIEW; locked.posting_rule = rule
    locked.posting_rule_snapshot = snapshot; locked.posting_rule_checksum = checksum
    locked.submitted_by = actor; locked.submitted_at = timezone.now(); locked.review_reason = ""
    locked.state_version += 1
    locked.full_clean(); locked.save()
    _event(locked, actor, "submitted_for_accounting_review", previous, metadata={"posting_rule_checksum": checksum})
    return locked


@transaction.atomic
def review_batch(*, batch, actor, approve, reason):
    _require(actor, "vouchers.approve_remittances")
    locked = TreasuryRemittanceBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status != locked.FOR_REVIEW:
        raise RemittanceWorkflowError("Only a submitted remittance is awaiting Accounting review.")
    if locked.created_by_id == actor.pk or locked.submitted_by_id == actor.pk:
        raise RemittanceWorkflowError("Maker-checker control: the preparer cannot approve the same remittance.")
    reason = str(reason or "").strip()
    if not reason:
        raise RemittanceWorkflowError("Record the review basis or correction reason.")
    if approve:
        _lock_reservation_scope(locked)
        _validate_live_lines(locked)
    previous = locked.status
    locked.status = locked.APPROVED if approve else locked.RETURNED
    locked.reviewed_by = actor; locked.reviewed_at = timezone.now(); locked.review_reason = reason
    locked.state_version += 1; locked.save()
    _event(locked, actor, "approved_for_release" if approve else "returned_for_correction", previous, reason)
    return locked


def _posting_payload(batch, lines):
    payload = {
        "schema_version": 1, "batch_public_id": str(batch.public_id),
        "remittance_reference": batch.reference_code, "transaction_type": batch.transaction_variant.code,
        "recipient_code": batch.recipient_party.code, "recipient_name": batch.recipient_party.display_name,
        "fund_code": batch.fund_code, "bank_account_code": batch.bank_account_code,
        "remittance_date": batch.remittance_date.isoformat(), "payment_method": batch.payment_method,
        "release_reference": batch.release_reference, "acknowledgement_reference": batch.acknowledgement_reference,
        "authority_reference": batch.authority_reference, "evidence_reference": batch.evidence_reference,
        "event_amount": str(batch.total_amount), "total_deductions": str(batch.total_amount),
        "posting_rule_checksum": batch.posting_rule_checksum,
        "lines": [{
            "line_id": line.pk, "fund_code": line.fund_code, "account_code": line.account_code,
            "account_title": line.account_title, "reference_key": line.reference_key,
            "reference_label": line.reference_label, "deduction_code": line.deduction_code,
            "amount": str(line.amount), "source_checksum": line.source_checksum,
            "tax_rule_snapshot": line.tax_rule_snapshot, "tax_rule_checksum": line.tax_rule_checksum,
        } for line in lines],
    }
    return payload, _digest(payload)


@transaction.atomic
def release_batch(*, batch, actor, release_reference, acknowledgement_reference):
    _require(actor, "vouchers.release_remittances")
    locked = TreasuryRemittanceBatch.objects.select_for_update().get(pk=batch.pk)
    _require_treasury_scope(actor, locked)
    _lock_reservation_scope(locked)
    if locked.status != locked.APPROVED:
        raise RemittanceWorkflowError("Only an independently approved remittance can be released.")
    release_reference = str(release_reference or "").strip()
    acknowledgement_reference = str(acknowledgement_reference or "").strip()
    if not release_reference:
        raise RemittanceWorkflowError("Record the bank, payment, or official release reference.")
    lines = _validate_live_lines(locked)
    locked.release_reference = release_reference
    locked.acknowledgement_reference = acknowledgement_reference
    locked.released_by = actor; locked.released_at = timezone.now()
    previous = locked.status; locked.status = locked.ACCOUNTING_POSTING; locked.state_version += 1
    locked.save()
    jev_number = _consume_number(locked, actor, "journal-entry", "journal-entry-v1")
    payload, checksum = _posting_payload(locked, lines)
    request = RemittancePostingRequest(
        batch=locked, version=1, jev_number=jev_number, jev_date=locked.remittance_date,
        finance_department_id=locked.finance_department_id,
        finance_department_label=locked.finance_department_label,
        posting_rule=locked.posting_rule, posting_rule_snapshot=locked.posting_rule_snapshot,
        posting_rule_checksum=locked.posting_rule_checksum, payload=payload, payload_checksum=checksum,
        requested_by=actor,
    )
    request.full_clean(); request.save()
    _event(locked, actor, "actual_remittance_released", previous, metadata={"posting_request": str(request.public_id), "jev_number": jev_number})
    return request


def _one(queryset, message):
    item = queryset.first()
    if item is None:
        raise RemittanceWorkflowError(message)
    return item


def _mark_failed(request, exc):
    RemittancePostingRequest.objects.filter(pk=request.pk).update(status=RemittancePostingRequest.FAILED, failure_reason=" ".join(getattr(exc, "messages", [str(exc)])))


def materialize_remittance_journal(posting_request, actor):
    if not can_prepare_journals(actor):
        raise PermissionDenied
    request = RemittancePostingRequest.objects.select_related("batch", "posting_rule").get(pk=posting_request.pk)
    if request.status in {request.CANCELLED, request.POSTED}:
        raise RemittanceWorkflowError("This remittance request is no longer eligible for draft creation.")
    existing = JournalEntry.objects.filter(
        department_id=request.finance_department_id, source_type="remittance", source_reference=str(request.public_id),
    ).first()
    if existing:
        RemittancePostingRequest.objects.filter(pk=request.pk).update(status=request.MATERIALIZED, accounting_entry_public_id=existing.public_id, failure_reason="", materialized_at=timezone.now())
        return existing, False
    try:
        if _digest(request.payload) != request.payload_checksum or _digest(request.posting_rule_snapshot) != request.posting_rule_checksum:
            raise RemittanceWorkflowError("The immutable remittance or posting-rule checksum no longer matches its content.")
        payload = request.payload
        with transaction.atomic(using="finance"):
            period = _one(AccountingPeriod.objects.filter(
                department_id=request.finance_department_id, status=AccountingPeriod.OPEN,
                starts_on__lte=request.jev_date, ends_on__gte=request.jev_date,
            ), "No open accounting period contains the remittance date.")
            fund = _one(Fund.objects.filter(
                department_id=request.finance_department_id, code__iexact=payload["fund_code"], is_active=True,
            ), f"Map or create active fund '{payload['fund_code']}' in Accounting Setup.")

            def mapped(category, code):
                candidates = PostingMapping.objects.filter(
                    department_id=request.finance_department_id, category=category, is_active=True,
                ).select_related("account")
                item = candidates.filter(source_code__iexact=code).first()
                if item is None and category == PostingMapping.BANK:
                    item = candidates.filter(source_code="*").first()
                return item.account if item else None

            rows = []
            for instruction in sorted(request.posting_rule_snapshot["lines"], key=lambda item: item["sequence"]):
                if instruction["account_source"] == FinancePostingRuleLine.DEDUCTION_MAPPINGS:
                    if instruction["side"] != FinancePostingRuleLine.DEBIT or instruction["amount_source"] != FinancePostingRuleLine.EACH_DEDUCTION:
                        raise RemittanceWorkflowError("The remittance liability instruction must debit each deduction mapping.")
                    for item in payload["lines"]:
                        account = mapped(PostingMapping.DEDUCTION, item["deduction_code"])
                        if account is None:
                            raise RemittanceWorkflowError(f"Add a deduction posting mapping for '{item['deduction_code']}'.")
                        if account.code.lower() != item["account_code"].lower():
                            raise RemittanceWorkflowError(f"The current mapping for '{item['deduction_code']}' no longer matches the posted liability account {item['account_code']}.")
                        rows.append((account, Decimal(item["amount"]), "debit", item))
                elif instruction["account_source"] == FinancePostingRuleLine.BANK_MAPPING:
                    if instruction["side"] != FinancePostingRuleLine.CREDIT or instruction["amount_source"] not in {FinancePostingRuleLine.EVENT_AMOUNT, FinancePostingRuleLine.TOTAL_DEDUCTIONS}:
                        raise RemittanceWorkflowError("The remittance payment instruction must credit the batch total to the bank mapping.")
                    code = instruction.get("mapping_code") or payload["bank_account_code"]
                    account = mapped(PostingMapping.BANK, code)
                    if account is None:
                        raise RemittanceWorkflowError(f"Add a bank posting mapping for '{code}'.")
                    rows.append((account, Decimal(payload["event_amount"]), "credit", None))
                else:
                    raise RemittanceWorkflowError("This remittance phase supports each-deduction liability debits and one mapped bank credit.")
            debit = sum((amount for _account, amount, side, _item in rows if side == "debit"), Decimal("0.00"))
            credit = sum((amount for _account, amount, side, _item in rows if side == "credit"), Decimal("0.00"))
            if debit <= 0 or debit != credit or debit != Decimal(payload["event_amount"]):
                raise RemittanceWorkflowError("The pinned remittance rule does not produce the exact balanced control total.")
            entry = JournalEntry(
                department_id=request.finance_department_id, department_label=request.finance_department_label,
                reference=request.jev_number, entry_date=request.jev_date, period=period, fund=fund,
                source_type="remittance", source_reference=str(request.public_id),
                source_snapshot={"remittance_batch": str(request.batch.public_id), "remittance_reference": payload["remittance_reference"], "payload_checksum": request.payload_checksum, "posting_rule_checksum": request.posting_rule_checksum},
                description=f"{payload['remittance_reference']} · Remittance to {payload['recipient_name']}",
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username,
            )
            entry.full_clean(); entry.save()
            for sequence, (account, amount, side, item) in enumerate(rows, start=1):
                line = JournalLine(
                    entry=entry, sequence=sequence, account=account,
                    debit=amount if side == "debit" else Decimal("0.00"),
                    credit=amount if side == "credit" else Decimal("0.00"),
                    memo=item["reference_label"] if item else f"Remittance via {payload['bank_account_code']}",
                )
                line.full_clean(); line.save()
                if item:
                    detail = JournalSubsidiaryLine(
                        entry=entry, journal_line=line, category=JournalSubsidiaryLine.WITHHOLDING,
                        reference_key=item["reference_key"], reference_label=item["reference_label"],
                        source_code=item["deduction_code"], source_reference=str(request.public_id),
                        debit=line.debit, credit=line.credit,
                        source_snapshot={
                            "remittance_batch": str(request.batch.public_id),
                            "transaction_type": payload["transaction_type"],
                            "source_balance_checksum": item["source_checksum"],
                            "tax_remittance": item.get("tax_rule_snapshot") or {},
                            "tax_rule_checksum": item.get("tax_rule_checksum") or "",
                        },
                    )
                    detail.full_clean(); detail.save()
            AccountingAuditEvent.objects.create(
                department_id=request.finance_department_id, department_label=request.finance_department_label,
                entry=entry, action="remittance_jev_materialized", actor_id=actor.pk,
                actor_label=actor.get_full_name() or actor.username,
                snapshot={"remittance_batch": str(request.batch.public_id), "payload_checksum": request.payload_checksum, "posting_rule_checksum": request.posting_rule_checksum},
            )
    except (RemittanceWorkflowError, ValidationError) as exc:
        _mark_failed(request, exc); raise
    RemittancePostingRequest.objects.filter(pk=request.pk).update(status=request.MATERIALIZED, accounting_entry_public_id=entry.public_id, failure_reason="", materialized_at=timezone.now())
    return entry, True


@transaction.atomic
def reconcile_posted_remittance_entry(entry, actor):
    if not can_post_journals(actor):
        raise PermissionDenied
    if entry.source_type != "remittance" or entry.status != JournalEntry.POSTED or not entry.source_reference:
        raise RemittanceWorkflowError("Only a posted GRAND remittance JEV can complete this handoff.")
    request = RemittancePostingRequest.objects.select_for_update().select_related("batch").filter(public_id=entry.source_reference).first()
    if request is None:
        raise RemittanceWorkflowError("The posted JEV's remittance request cannot be found.")
    request.status = request.POSTED; request.accounting_entry_public_id = entry.public_id
    request.failure_reason = ""; request.posted_at = entry.posted_at or timezone.now(); request.save()
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=request.batch_id)
    if batch.status != batch.ACCOUNTING_POSTING:
        raise RemittanceWorkflowError("The remittance batch is not waiting for Accounting posting.")
    previous = batch.status; batch.status = batch.COMPLETED; batch.state_version += 1; batch.save()
    _event(batch, actor, "remittance_jev_posted", previous, metadata={"posting_request": str(request.public_id), "accounting_entry": str(entry.public_id), "jev_number": entry.reference})
    return request


@transaction.atomic
def supersede_discarded_request(*, posting_request, actor, reason):
    if not reason.strip():
        raise RemittanceWorkflowError("Explain why the generated remittance JEV draft was discarded.")
    original = RemittancePostingRequest.objects.select_for_update().select_related("batch").get(pk=posting_request.pk)
    if original.status == original.POSTED:
        raise RemittanceWorkflowError("A posted remittance JEV cannot be replaced; use a reversal or adjustment.")
    original.status = original.CANCELLED; original.failure_reason = f"Draft discarded: {reason.strip()}"; original.save()
    version = original.batch.posting_requests.aggregate(value=Max("version"))["value"] or 1
    jev_number = _consume_number(original.batch, actor, "journal-entry", f"journal-entry-v{version + 1}")
    successor = RemittancePostingRequest.objects.create(
        batch=original.batch, version=version + 1, jev_number=jev_number, jev_date=original.jev_date,
        finance_department_id=original.finance_department_id, finance_department_label=original.finance_department_label,
        posting_rule=original.posting_rule, posting_rule_snapshot=original.posting_rule_snapshot,
        posting_rule_checksum=original.posting_rule_checksum, payload=original.payload,
        payload_checksum=original.payload_checksum, requested_by=actor,
    )
    _event(original.batch, actor, "posting_request_replaced", original.batch.status, reason, {"prior_request": str(original.public_id), "successor_request": str(successor.public_id), "jev_number": jev_number})
    return successor


def export_batch_csv(*, batch, actor):
    _require(actor, "vouchers.view_remittance_workbench")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["remittance_reference", "status", "date", "fund", "recipient", "payment_method", "bank_account", "release_reference", "acknowledgement_reference", "line_version", "line_status", "deduction_code", "reference_key", "reference_label", "liability_account", "amount", "tax_family", "return_form_code", "atc", "tax_rule_checksum", "source_balance_checksum", "jev_number", "jev_status"])
    latest_request = batch.posting_requests.order_by("-version").first()
    for line in batch.lines.order_by("lineage_key", "version"):
        writer.writerow([
            batch.reference_code, batch.get_status_display(), batch.remittance_date.isoformat(), batch.fund_code,
            batch.recipient_party.display_name, batch.payment_method, batch.bank_account_code,
            batch.release_reference, batch.acknowledgement_reference, line.version, line.get_status_display(),
            line.deduction_code, line.reference_key, line.reference_label, line.account_code,
            str(line.amount), line.tax_rule_snapshot.get("tax_family", ""),
            line.tax_rule_snapshot.get("return_form_code", ""), line.tax_rule_snapshot.get("atc", ""),
            line.tax_rule_checksum, line.source_checksum,
            latest_request.jev_number if latest_request else "", latest_request.get_status_display() if latest_request else "",
        ])
    content = output.getvalue().encode("utf-8-sig")
    return content, archive_export(
        content=content, department=batch.treasury_department, user=actor,
        category="finance-remittances", filename=f"{batch.reference_code}-remittance-register.csv",
        metadata={"remittance_public_id": str(batch.public_id), "status": batch.status, "total_amount": str(batch.total_amount)},
    )
