from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.access import can_post_journals, can_prepare_journals, department_for_user
from accounting.models import (
    AccountingAuditEvent, AccountingPeriod, Fund, JournalEntry, JournalLine,
    LedgerAccount, PostingMapping, ResponsibilityCenter,
)

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
    request = VoucherPostingRequest.objects.select_related("case").get(pk=posting_request.pk)
    if request.finance_department_id != department.pk:
        raise PermissionDenied
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

            payable_mappings = PostingMapping.objects.filter(
                department_id=department.pk, category=PostingMapping.PAYABLE, is_active=True,
            ).select_related("account")
            payable_mapping = (
                payable_mappings.filter(source_code__iexact=payload["transaction_type"]).first()
                or payable_mappings.filter(source_code="*").first()
            )
            if payable_mapping is None:
                raise PostingRequestError(
                    f"Add a payable posting mapping for transaction type '{payload['transaction_type']}'."
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
                },
                description=f"{payload['voucher_reference']} · {payload['particulars']}",
                created_by_id=actor.pk,
                created_by_label=actor.get_full_name() or actor.username,
            )
            entry.full_clean()
            entry.save()
            sequence = 1
            for item in allocations:
                account_code = str(item.get("account_code") or "").strip()
                account = _one(
                    LedgerAccount.objects.filter(
                        department_id=department.pk, code__iexact=account_code, is_active=True, allow_posting=True,
                    ),
                    f"Map or create active posting account '{account_code}' in Accounting Setup.",
                )
                center_code = str(item.get("responsibility_center_code") or "").strip()
                center = None
                if center_code:
                    center = _one(
                        ResponsibilityCenter.objects.filter(
                            department_id=department.pk, code__iexact=center_code, is_active=True,
                        ),
                        f"Map or create active responsibility center '{center_code}' in Accounting Setup.",
                    )
                line = JournalLine(
                    entry=entry, sequence=sequence, account=account, responsibility_center=center,
                    debit=Decimal(str(item["amount"])), credit=Decimal("0.00"),
                    memo=str(item.get("account_code") or payload["particulars"]),
                )
                line.full_clean(); line.save(); sequence += 1
            for item in payload.get("deductions") or []:
                mapping = _one(
                    PostingMapping.objects.filter(
                        department_id=department.pk, category=PostingMapping.DEDUCTION,
                        source_code__iexact=item["code"], is_active=True,
                    ).select_related("account"),
                    f"Add a deduction posting mapping for '{item['code']}'.",
                )
                line = JournalLine(
                    entry=entry, sequence=sequence, account=mapping.account,
                    debit=Decimal("0.00"), credit=Decimal(item["amount"]), memo=item["description"],
                )
                line.full_clean(); line.save(); sequence += 1
            payable_line = JournalLine(
                entry=entry, sequence=sequence, account=payable_mapping.account,
                debit=Decimal("0.00"), credit=net, memo=f"Net payable · {payload['payee_name']}",
            )
            payable_line.full_clean(); payable_line.save()
            AccountingAuditEvent.objects.create(
                department_id=department.pk,
                department_label=department.name,
                entry=entry,
                action="voucher_jev_materialized",
                actor_id=actor.pk,
                actor_label=actor.get_full_name() or actor.username,
                snapshot={"posting_request": source_reference, "payload_checksum": request.payload_checksum},
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

    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    if case.current_stage == VoucherCase.ACCOUNTING_POSTING:
        from .services import _advance
        _advance(
            case, actor, VoucherCase.TREASURY_CHECK_PREPARATION, "grand_jev_posted",
            f"grand-jev-posted-{entry.public_id}",
            metadata={"posting_request": str(request.public_id), "accounting_entry": str(entry.public_id), "jev_number": entry.reference},
        )
    return request
