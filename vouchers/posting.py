from __future__ import annotations

from decimal import Decimal
import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.access import can_post_journals, can_prepare_journals, department_for_user
from accounting.models import (
    AccountingAuditEvent, AccountingPeriod, Fund, JournalEntry, JournalLine, JournalSubsidiaryLine,
    LedgerAccount, PostingMapping, ResponsibilityCenter,
)
from finance.models import FinancePostingRuleLine

from .models import VoucherCase, VoucherPostingRequest


class PostingRequestError(ValidationError):
    pass


def _one(queryset, message):
    value = queryset.first()
    if value is None:
        raise PostingRequestError(message)
    return value


def _mark_failed(request, exc):
    VoucherPostingRequest.objects.filter(pk=request.pk).update(
        status=VoucherPostingRequest.FAILED,
        failure_reason=" ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
    )


def materialize_voucher_journal(posting_request, actor):
    """Idempotently create a draft GRAND JEV from an immutable voucher snapshot."""
    if not can_prepare_journals(actor):
        raise PermissionDenied
    department = department_for_user(actor)
    request = VoucherPostingRequest.objects.select_related("case", "posting_rule").get(pk=posting_request.pk)
    if request.finance_department_id != department.pk:
        raise PermissionDenied
    if request.status == VoucherPostingRequest.NOT_REQUIRED:
        raise PostingRequestError("This governed event explicitly requires no journal entry; there is nothing to create.")
    if request.status in {VoucherPostingRequest.CANCELLED, VoucherPostingRequest.POSTED}:
        raise PostingRequestError("This posting request is no longer eligible for draft creation.")

    source_reference = str(request.public_id)
    existing = JournalEntry.objects.filter(
        department_id=department.pk, source_type="voucher", source_reference=source_reference,
    ).first()
    if existing:
        VoucherPostingRequest.objects.filter(pk=request.pk).update(
            status=VoucherPostingRequest.MATERIALIZED,
            accounting_entry_public_id=existing.public_id,
            failure_reason="",
            materialized_at=timezone.now(),
        )
        return existing, False

    payload = request.payload
    try:
        payload_checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if payload_checksum != request.payload_checksum:
            raise PostingRequestError("The immutable voucher payload checksum no longer matches its content.")
        if request.posting_rule_snapshot:
            rule_checksum = hashlib.sha256(
                json.dumps(request.posting_rule_snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if rule_checksum != request.posting_rule_checksum:
                raise PostingRequestError("The immutable posting-rule checksum no longer matches its content.")
            if request.posting_rule_public_id_snapshot != request.posting_rule_snapshot.get("rule_public_id"):
                raise PostingRequestError("The immutable posting-rule identity no longer matches its snapshot.")
            if payload.get("posting_rule_checksum") != request.posting_rule_checksum:
                raise PostingRequestError("The voucher payload and posting-rule snapshot checksums do not agree.")
        with transaction.atomic(using="finance"):
            period = _one(
                AccountingPeriod.objects.filter(
                    department_id=department.pk, status=AccountingPeriod.OPEN,
                    starts_on__lte=request.jev_date, ends_on__gte=request.jev_date,
                ),
                "No open accounting period contains the JEV date.",
            )
            allocations = payload.get("allocations") or []
            fund_codes = {str(item.get("fund_code") or "").strip() for item in allocations}
            if len(fund_codes) != 1 or "" in fund_codes:
                raise PostingRequestError("This phase requires all voucher allocation lines to use one mapped fund.")
            fund_code = fund_codes.pop()
            fund = _one(
                Fund.objects.filter(department_id=department.pk, code__iexact=fund_code, is_active=True),
                f"Map or create active fund '{fund_code}' in Accounting Setup.",
            )
            debit_total = sum((Decimal(str(item.get("amount") or "0")) for item in allocations), Decimal("0.00"))
            gross = Decimal(payload["gross_amount"])
            net = Decimal(payload["net_amount"])
            deduction_total = Decimal(payload["total_deductions"])
            if debit_total != gross or gross != net + deduction_total:
                raise PostingRequestError("The immutable voucher snapshot does not reconcile to its allocation, deduction, and net totals.")

            rule_lines = request.posting_rule_snapshot.get("lines") if request.posting_rule_snapshot else None
            policy_mode = "governed_snapshot"
            if not rule_lines:
                # Compatibility for immutable requests created before F7. New requests always pin a governed rule.
                policy_mode = "legacy_pre_f7"
                rule_lines = [
                    {
                        "sequence": 10, "label": "Reviewed voucher allocation", "side": "debit",
                        "account_source": "allocation_accounts", "amount_source": "each_allocation",
                        "mapping_code": "", "ledger_account_code": "", "memo": "Reviewed voucher allocation",
                    },
                    {
                        "sequence": 20, "label": "Voucher deduction / withholding", "side": "credit",
                        "account_source": "deduction_mappings", "amount_source": "each_deduction",
                        "mapping_code": "", "ledger_account_code": "", "memo": "Voucher deduction / withholding",
                    },
                    {
                        "sequence": 30, "label": "Net payable", "side": "credit",
                        "account_source": "payable_mapping", "amount_source": "net",
                        "mapping_code": "", "ledger_account_code": "", "memo": "Net payable",
                    },
                ]

            def posting_account(code):
                return _one(
                    LedgerAccount.objects.filter(
                        department_id=department.pk, code__iexact=code, is_active=True, allow_posting=True,
                    ),
                    f"Map or create active posting account '{code}' in Accounting Setup.",
                )

            def mapped_account(category, source_code):
                candidates = PostingMapping.objects.filter(
                    department_id=department.pk, category=category, is_active=True,
                ).select_related("account")
                mapping = candidates.filter(source_code__iexact=source_code).first()
                if mapping is None and category in {PostingMapping.PAYABLE, PostingMapping.BANK}:
                    mapping = candidates.filter(source_code="*").first()
                if mapping is None:
                    label = dict(PostingMapping.CATEGORY_CHOICES).get(category, category)
                    raise PostingRequestError(f"Add a {label.lower()} posting mapping for '{source_code}'.")
                return mapping.account

            scalar_amounts = {
                FinancePostingRuleLine.GROSS: gross,
                FinancePostingRuleLine.NET: net,
                FinancePostingRuleLine.TOTAL_DEDUCTIONS: deduction_total,
                FinancePostingRuleLine.EVENT_AMOUNT: Decimal(str(payload.get("event_amount") or "0")),
            }
            rows = []
            for instruction in sorted(rule_lines, key=lambda item: (item.get("sequence", 0), item.get("label", ""))):
                side = instruction.get("side")
                account_source = instruction.get("account_source")
                amount_source = instruction.get("amount_source")
                if side not in {FinancePostingRuleLine.DEBIT, FinancePostingRuleLine.CREDIT}:
                    raise PostingRequestError("The pinned posting rule contains an unsupported debit or credit side.")
                memo = str(instruction.get("memo") or instruction.get("label") or payload["particulars"])
                if account_source == FinancePostingRuleLine.ALLOCATION_ACCOUNTS:
                    if amount_source != FinancePostingRuleLine.EACH_ALLOCATION:
                        raise PostingRequestError("The pinned allocation instruction does not use each allocation amount.")
                    for item in allocations:
                        account = posting_account(str(item.get("account_code") or "").strip())
                        center_code = str(item.get("responsibility_center_code") or "").strip()
                        center = None
                        if center_code:
                            center = _one(
                                ResponsibilityCenter.objects.filter(
                                    department_id=department.pk, code__iexact=center_code, is_active=True,
                                ),
                                f"Map or create active responsibility center '{center_code}' in Accounting Setup.",
                            )
                        rows.append({
                            "account": account, "center": center,
                            "amount": Decimal(str(item["amount"])), "side": side, "memo": memo,
                            "subsidiary": None,
                        })
                elif account_source == FinancePostingRuleLine.DEDUCTION_MAPPINGS:
                    if amount_source != FinancePostingRuleLine.EACH_DEDUCTION:
                        raise PostingRequestError("The pinned deduction instruction does not use each deduction amount.")
                    for item in payload.get("deductions") or []:
                        account = mapped_account(PostingMapping.DEDUCTION, item["code"])
                        rows.append({
                            "account": account, "center": None,
                            "amount": Decimal(str(item["amount"])), "side": side,
                            "memo": str(item.get("description") or memo),
                            "subsidiary": {
                                "category": JournalSubsidiaryLine.WITHHOLDING,
                                "reference_key": str(item["code"]),
                                "reference_label": str(item.get("description") or item["code"]),
                                "source_code": str(item["code"]),
                            },
                        })
                else:
                    if amount_source not in scalar_amounts:
                        raise PostingRequestError("The pinned posting rule contains an unsupported amount source.")
                    amount = scalar_amounts[amount_source]
                    mapping_code = str(instruction.get("mapping_code") or "").strip()
                    if account_source == FinancePostingRuleLine.PAYABLE_MAPPING:
                        account = mapped_account(PostingMapping.PAYABLE, mapping_code or payload["transaction_type"])
                    elif account_source == FinancePostingRuleLine.BANK_MAPPING:
                        bank_code = mapping_code or str(payload.get("bank_account_code") or "").strip()
                        if not bank_code:
                            raise PostingRequestError("The pinned bank instruction needs a payment-account mapping code.")
                        account = mapped_account(PostingMapping.BANK, bank_code)
                    elif account_source == FinancePostingRuleLine.FIXED_ACCOUNT:
                        account = posting_account(str(instruction.get("ledger_account_code") or "").strip())
                    else:
                        raise PostingRequestError("The pinned posting rule contains an unsupported account source.")
                    subsidiary = None
                    if account_source == FinancePostingRuleLine.PAYABLE_MAPPING:
                        subsidiary = {
                            "category": JournalSubsidiaryLine.PAYABLE,
                            "reference_key": str(
                                payload.get("payee_key") or f"voucher-case:{payload['voucher_case_public_id']}"
                            ),
                            "reference_label": str(payload["payee_name"]),
                            "source_code": mapping_code or payload["transaction_type"],
                        }
                    rows.append({
                        "account": account, "center": None, "amount": amount,
                        "side": side, "memo": memo, "subsidiary": subsidiary,
                    })

            rows = [row for row in rows if row["amount"] != Decimal("0.00")]
            debit_sum = sum((
                row["amount"] for row in rows if row["side"] == FinancePostingRuleLine.DEBIT
            ), Decimal("0.00"))
            credit_sum = sum((
                row["amount"] for row in rows if row["side"] == FinancePostingRuleLine.CREDIT
            ), Decimal("0.00"))
            if len(rows) < 2 or debit_sum <= 0 or debit_sum != credit_sum:
                raise PostingRequestError(
                    f"The pinned posting rule produces an unbalanced entry: debit {debit_sum:.2f}, credit {credit_sum:.2f}."
                )
            entry = JournalEntry(
                department_id=department.pk,
                department_label=department.name,
                reference=request.jev_number,
                entry_date=request.jev_date,
                period=period,
                fund=fund,
                source_type="voucher",
                source_reference=source_reference,
                source_snapshot={
                    "posting_request": source_reference,
                    "voucher_case": payload["voucher_case_public_id"],
                    "voucher_reference": payload["voucher_reference"],
                    "dv_number": payload["dv_number"],
                    "payload_checksum": request.payload_checksum,
                    "posting_policy_mode": policy_mode,
                    "posting_rule_public_id": request.posting_rule_public_id_snapshot,
                    "posting_rule_checksum": request.posting_rule_checksum,
                    "posting_event": request.kind,
                    "posting_trigger": payload.get("trigger", {}),
                    "event_amount": payload.get("event_amount", ""),
                    "recognition_decision": payload.get("recognition_decision", "legacy_pre_f7"),
                    "payee_key": payload.get("payee_key", ""),
                    "payee_code": payload.get("payee_code", ""),
                    "payee_name": payload.get("payee_name", ""),
                },
                description=f"{payload['voucher_reference']} · {payload['particulars']}",
                created_by_id=actor.pk,
                created_by_label=actor.get_full_name() or actor.username,
            )
            entry.full_clean()
            entry.save()
            for sequence, row in enumerate(rows, start=1):
                line = JournalLine(
                    entry=entry, sequence=sequence, account=row["account"],
                    responsibility_center=row["center"],
                    debit=row["amount"] if row["side"] == FinancePostingRuleLine.DEBIT else Decimal("0.00"),
                    credit=row["amount"] if row["side"] == FinancePostingRuleLine.CREDIT else Decimal("0.00"),
                    memo=row["memo"],
                )
                line.full_clean(); line.save()
                if row["subsidiary"]:
                    detail = JournalSubsidiaryLine(
                        entry=entry,
                        journal_line=line,
                        category=row["subsidiary"]["category"],
                        reference_key=row["subsidiary"]["reference_key"],
                        reference_label=row["subsidiary"]["reference_label"],
                        source_code=row["subsidiary"]["source_code"],
                        source_reference=source_reference,
                        debit=line.debit,
                        credit=line.credit,
                        source_snapshot={
                            "posting_request": source_reference,
                            "voucher_case": payload["voucher_case_public_id"],
                            "voucher_reference": payload["voucher_reference"],
                            "dv_number": payload["dv_number"],
                            "transaction_type": payload.get("transaction_type", ""),
                            "posting_rule_checksum": request.posting_rule_checksum,
                        },
                    )
                    detail.full_clean(); detail.save()
            AccountingAuditEvent.objects.create(
                department_id=department.pk,
                department_label=department.name,
                entry=entry,
                action="voucher_jev_materialized",
                actor_id=actor.pk,
                actor_label=actor.get_full_name() or actor.username,
                snapshot={
                    "posting_request": source_reference,
                    "payload_checksum": request.payload_checksum,
                    "posting_policy_mode": policy_mode,
                    "posting_rule_public_id": request.posting_rule_public_id_snapshot,
                    "posting_rule_checksum": request.posting_rule_checksum,
                },
            )
    except (PostingRequestError, ValidationError) as exc:
        _mark_failed(request, exc)
        raise

    VoucherPostingRequest.objects.filter(pk=request.pk).update(
        status=VoucherPostingRequest.MATERIALIZED,
        accounting_entry_public_id=entry.public_id,
        failure_reason="",
        materialized_at=timezone.now(),
    )
    return entry, True


@transaction.atomic
def reconcile_posted_voucher_entry(entry, actor):
    """Complete the recoverable finance→core handoff after a JEV is posted."""
    if not can_post_journals(actor):
        raise PermissionDenied
    if entry.source_type != "voucher" or not entry.source_reference:
        return None
    if entry.status != JournalEntry.POSTED:
        raise PostingRequestError("The voucher handoff can advance only after the JEV is posted.")
    request = VoucherPostingRequest.objects.select_for_update().select_related("case").filter(
        public_id=entry.source_reference,
    ).first()
    if request is None:
        raise PostingRequestError("The posted JEV's source request cannot be found in the Voucher Workbench.")
    if request.accounting_entry_public_id and request.accounting_entry_public_id != entry.public_id:
        raise PostingRequestError("The posting request is linked to a different accounting entry.")
    request.status = VoucherPostingRequest.POSTED
    request.accounting_entry_public_id = entry.public_id
    request.failure_reason = ""
    request.posted_at = entry.posted_at or timezone.now()
    request.save(update_fields=("status", "accounting_entry_public_id", "failure_reason", "posted_at"))

    from .advice import complete_returned_review_after_posting
    complete_returned_review_after_posting(posting_request=request, actor=actor)

    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    from .services import _advance
    if case.current_stage == VoucherCase.ACCOUNTING_POSTING:
        destination = request.resume_stage or VoucherCase.TREASURY_CHECK_PREPARATION
        _advance(
            case, actor, destination, "grand_jev_posted",
            f"grand-jev-posted-{entry.public_id}",
            metadata={
                "posting_request": str(request.public_id),
                "posting_event": request.kind,
                "accounting_entry": str(entry.public_id),
                "jev_number": entry.reference,
                "resume_stage": destination,
            },
        )
    elif case.current_stage == VoucherCase.ACCOUNTING_EVENT_POSTING:
        destination = request.resume_stage
        if not destination:
            raise PostingRequestError("The payment-event handoff has no recorded workflow stage to resume.")
        pending_other = case.posting_requests.filter(
            status__in=(VoucherPostingRequest.PENDING, VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED),
        ).exclude(pk=request.pk).exists()
        if pending_other:
            raise PostingRequestError("Another posting request for this voucher still needs Accounting action.")
        _advance(
            case, actor, destination, f"{request.kind}_jev_posted",
            f"payment-event-jev-posted-{entry.public_id}",
            metadata={
                "posting_request": str(request.public_id),
                "posting_event": request.kind,
                "posting_trigger": request.payload.get("trigger", {}),
                "accounting_entry": str(entry.public_id),
                "jev_number": entry.reference,
                "resume_stage": destination,
            },
        )
    return request
