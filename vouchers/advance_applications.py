"""Expense liquidations over explicit original advances and retained disbursements."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.access import can_prepare_journals, can_post_journals, department_for_user
from accounting.models import AccountingPeriod, Fund, JournalEntry, JournalLine, JournalSubsidiaryLine, LedgerAccount
from accounting.posted_evidence import verify_source_link, require_persisted_posting
from finance.models import FinanceNumberingSequence, FinancePostingRule as Rule, FinancePostingRuleLine as Line
from finance.services import posting_rule_snapshot
from .models import VoucherCase, VoucherPostingRequest as Request, PaymentInstrumentException
from .advance_sources import original, disbursement
from .remittances import _digest


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError
        return amount.quantize(Decimal("0.01"))
    except (ValueError, InvalidOperation):
        raise ValidationError("Enter a positive amount with at most two decimal places.")


def applications(case, detail):
    queryset = case.posting_requests.filter(trigger_key__startswith="advance-liquidation:")
    if transaction.get_connection("default").in_atomic_block:
        queryset = queryset.select_for_update()
    result = []
    for request in queryset:
        if not request.trigger_key.startswith("advance-liquidation:"):
            continue
        data = request.payload.get("advance_application")
        if (not data or _digest(request.payload) != request.payload_checksum
                or _digest(request.posting_rule_snapshot) != request.posting_rule_checksum):
            raise ValidationError("The retained liquidation reservation evidence changed.")
        if request.status == Request.CANCELLED:
            event = case.events.filter(action="advance_liquidation_withdrawn",
                metadata__posting_request=str(request.public_id)).first()
            if (event is None or event.actor_id == request.requested_by_id or not event.reason
                    or JournalEntry.objects.filter(source_type="voucher", source_reference=str(request.public_id))
                    .exclude(status=JournalEntry.VOIDED).exists()):
                raise ValidationError("Retain the independently withdrawn, unposted liquidation source before releasing its reservation.")
            continue
        if data.get("original_detail") == detail.pk:
            result.append(request)
    return result


def capacity(detail, day, amount, *, exclude=None, exclude_refund=None):
    detail, recognition, _ = original(detail)
    from accounting.services import control_reconciliation_snapshot
    controls, _ = control_reconciliation_snapshot(detail.entry.department_id, timezone.localdate())
    if any(row["category"] == JournalSubsidiaryLine.ADVANCE
           and row["account_id"] == detail.journal_line.account_id
           and row["fund_id"] == detail.entry.fund_id and Decimal(row["difference"]) != 0
           for row in controls["rows"]):
        raise ValidationError("Reconcile the advance control account before applying an individual source.")
    requests = [request for request in applications(recognition.case, detail) if request.pk != exclude]
    from .advance_refunds import movements
    refund_movements = movements(detail, exclude=exclude_refund)
    boundaries = {day, timezone.localdate()}
    boundaries.update(moment for moment, value in refund_movements if moment >= day)
    boundaries.update(request.jev_date for request in requests if request.jev_date >= day)
    boundaries.update(timezone.localdate(item.released_at) for item in recognition.case.payment_instruments.all()
                      if item.released_at and timezone.localdate(item.released_at) >= day)
    boundaries.update(PaymentInstrumentException.objects.filter(instrument__case=recognition.case,
        kind=PaymentInstrumentException.RETURNED, observed_on__gte=day).values_list("observed_on", flat=True))
    for boundary in sorted(boundaries):
        proof = disbursement(detail, boundary)
        held = sum((money(request.payload["advance_application"]["amount"]) for request in requests
                    if request.jev_date <= boundary), Decimal("0"))
        held += sum((value for moment, value in refund_movements if moment <= boundary), Decimal('0'))
        if amount + held > proof["released_net"]:
            raise ValidationError(f"The liquidation exceeds the released advance remaining on {boundary.isoformat()}.")
    return disbursement(detail, day)


@transaction.atomic
def prepare(*, detail, actor, rule, day, expenses, evidence_reference, key):
    owner = department_for_user(actor)
    if not can_prepare_journals(actor) or owner is None or owner.pk != detail.entry.department_id:
        raise PermissionDenied
    detail, recognition, _ = original(detail)
    case = VoucherCase.objects.select_for_update().get(pk=recognition.case_id)
    if not key or len(str(key)) > 100 or not str(evidence_reference).strip():
        raise ValidationError("Retain a request identity and the actual liquidation document reference.")
    if day > timezone.localdate() or day < detail.entry.entry_date:
        raise ValidationError("Choose an actual liquidation date on or after original recognition.")
    rule = Rule.objects.select_related("variant__release").get(pk=rule.pk)
    variant = rule.variant
    if (variant.department_id != owner.pk or variant.kind not in ("cash_advance", "liquidation")
            or variant.status not in ("approved", "active") or variant.release.status not in ("approved", "active")
            or variant.effective_from > day or (variant.effective_to and variant.effective_to < day)
            or variant.release.effective_from > day
            or (variant.release.effective_to and variant.release.effective_to < day)
            or rule.event_kind != Rule.LIQUIDATION or rule.recognition_point != Rule.LIQUIDATION_ACCEPTANCE):
        raise ValidationError("Select an effective reviewed liquidation-acceptance recipe for this Accounting office.")
    snapshot, checksum = posting_rule_snapshot(rule)
    instructions = snapshot["lines"]
    if (len(instructions) != 2 or not any(item["account_source"] == Line.PRIOR_ADVANCE
            and item["side"] == Line.CREDIT and item["amount_source"] == Line.GROSS for item in instructions)
            or not any(item["account_source"] == Line.ALLOCATION_ACCOUNTS and item["side"] == Line.DEBIT
                       and item["amount_source"] == Line.EACH_ALLOCATION for item in instructions)
            or any(item.get("cash_flow_category") or item.get("mapping_code") or item.get("ledger_account_code")
                   for item in instructions)):
        raise ValidationError("Use expense-allocation debits and one selected-original-advance credit, without cash movement.")
    rows = []
    for item in expenses:
        account = LedgerAccount.objects.filter(department_id=owner.pk, code=item["account_code"],
            is_active=True, allow_posting=True, account_type="expense").first()
        if account is None or not str(item.get("document_reference", "")).strip():
            raise ValidationError("Each accepted expense needs an active expense account and its document reference.")
        rows.append({"account_id": account.pk, "account_code": account.code,
            "amount": str(money(item["amount"])), "document_reference": str(item["document_reference"]).strip()})
    if not rows:
        raise ValidationError("Enter at least one accepted expense.")
    amount = money(sum((Decimal(row["amount"]) for row in rows), Decimal("0")))
    application = {"schema_version": 1, "original_detail": detail.pk,
        "original_entry": str(detail.entry.public_id), "original_request": str(recognition.public_id),
        "original_payload_checksum": recognition.payload_checksum, "amount": str(amount),
        "expenses": rows, "document_reference": str(evidence_reference).strip(), "prepared_by": actor.pk}
    trigger = f"advance-liquidation:{key}"
    existing = case.posting_requests.filter(kind=Request.LIQUIDATION, trigger_key=trigger).first()
    if existing:
        previous = dict(existing.payload.get("advance_application", {}))
        previous.pop("disbursement", None)
        if existing.jev_date != day or previous != application or existing.posting_rule_checksum != checksum:
            raise ValidationError("This request identity belongs to a different retained liquidation.")
        if existing.status == Request.CANCELLED:
            raise ValidationError("This liquidation was withdrawn; prepare a new request identity.")
        capacity(detail, day, amount, exclude=existing.pk)
        return existing
    if any(item.payload["advance_application"]["document_reference"].casefold()
           == application["document_reference"].casefold() for item in applications(case, detail)):
        raise ValidationError("This original advance already has an active liquidation with that document reference.")
    application["disbursement"] = capacity(detail, day, amount)
    sequence = FinanceNumberingSequence.objects.select_for_update().filter(department_id=owner.pk,
        release=variant.release, fiscal_year=day.year, document_type="journal-entry", status="active").first()
    if sequence is None:
        raise ValidationError("Configure the active Accounting JEV sequence for this liquidation date.")
    number = f"{sequence.prefix}{sequence.next_number:0{sequence.padding}d}"
    # JSON stores decimal strings so the retained evidence is reproducible on both stores.
    proof = application["disbursement"]
    application["disbursement"] = {name: str(value) if isinstance(value, Decimal) else value for name, value in proof.items()}
    payload = {"advance_application": application, "voucher_case_public_id": str(case.public_id),
        "voucher_reference": case.reference_code, "dv_number": recognition.payload["dv_number"],
        "payee_key": detail.reference_key, "payee_name": detail.reference_label}
    request = Request(case=case, kind=Request.LIQUIDATION,
        version=(case.posting_requests.filter(kind=Request.LIQUIDATION).aggregate(v=Max("version"))["v"] or 0) + 1,
        trigger_key=trigger, jev_number=number, jev_date=day, finance_department_id=owner.pk,
        finance_department_label=owner.name, posting_rule=rule, posting_rule_public_id_snapshot=str(rule.public_id),
        posting_rule_snapshot=snapshot, posting_rule_checksum=checksum, payload=payload,
        payload_checksum=_digest(payload), requested_by=actor)
    request.full_clean(); request.save()
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))
    return request


def validate(entry, *, check_capacity=True):
    request = Request.objects.select_related("case").get(public_id=entry.source_reference)
    if request.status == Request.CANCELLED:
        raise ValidationError("The retained liquidation request was withdrawn.")
    verify_source_link(request, entry, source_type="voucher")
    data = request.payload["advance_application"]
    if entry.source_snapshot.get("advance_application") != data:
        raise ValidationError("The liquidation journal must retain its original application evidence.")
    detail, recognition, _ = original(JournalSubsidiaryLine.objects.get(pk=data["original_detail"]))
    if (recognition.case_id != request.case_id or str(recognition.public_id) != data["original_request"]
            or recognition.payload_checksum != data["original_payload_checksum"]
            or entry.fund_id != detail.entry.fund_id):
        raise ValidationError("The liquidation must retain its exact original advance, payee and fund.")
    expected = [(row["account_id"], Decimal(row["amount"]), Decimal("0")) for row in data["expenses"]]
    expected.append((detail.journal_line.account_id, Decimal("0"), money(data["amount"])))
    actual = [(line.account_id, line.debit, line.credit) for line in entry.lines.order_by("sequence")]
    if actual != expected or entry.lines.exclude(cash_flow_category="").exists():
        raise ValidationError("Liquidation financial lines differ from the retained accepted expenses and original advance.")
    for row in data["expenses"]:
        if not LedgerAccount.objects.filter(pk=row["account_id"], department_id=entry.department_id,
                code=row["account_code"], account_type="expense", is_active=True, allow_posting=True).exists():
            raise ValidationError("The retained expense account identity or classification changed before posting.")
    subsidiary = list(entry.subsidiary_lines.all())
    if (len(subsidiary) != 1 or subsidiary[0].category != JournalSubsidiaryLine.ADVANCE
            or subsidiary[0].reference_key != detail.reference_key
            or subsidiary[0].credit != money(data["amount"]) or subsidiary[0].debit
            or subsidiary[0].journal_line_id != entry.lines.order_by("sequence").last().pk
            or subsidiary[0].source_reference != str(request.public_id)
            or subsidiary[0].reference_label != detail.reference_label or subsidiary[0].source_code != detail.source_code
            or subsidiary[0].source_snapshot.get("advance_application") != data
            or subsidiary[0].source_snapshot.get("original_advance_detail") != detail.pk):
        raise ValidationError("Retain the original officer and advance on the liquidation subsidiary credit.")
    if check_capacity:
        capacity(detail, entry.entry_date, money(data["amount"]), exclude=request.pk)
    return request


@transaction.atomic
def materialize(request, actor):
    owner = department_for_user(actor)
    if not can_prepare_journals(actor) or owner is None or request.finance_department_id != owner.pk:
        raise PermissionDenied
    VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = Request.objects.select_for_update().get(pk=request.pk)
    if request.status == Request.CANCELLED:
        raise ValidationError("The liquidation request was withdrawn.")
    data = request.payload["advance_application"]
    if _digest(request.payload) != request.payload_checksum:
        raise ValidationError("The retained liquidation payload changed.")
    detail, _, _ = original(JournalSubsidiaryLine.objects.get(pk=data["original_detail"]))
    capacity(detail, request.jev_date, money(data["amount"]), exclude=request.pk)
    with transaction.atomic(using="finance"):
        Fund.objects.select_for_update().get(pk=detail.entry.fund_id)
        matches = list(JournalEntry.objects.filter(source_type="voucher", source_reference=str(request.public_id)).exclude(status=JournalEntry.VOIDED))
        if len(matches) > 1:
            raise ValidationError("Resolve duplicate liquidation journals before recovery.")
        if matches:
            entry = matches[0]
            validate(entry)
            created = False
        else:
            if JournalEntry.objects.filter(source_type="voucher", source_reference=str(request.public_id)).exists():
                raise ValidationError("Withdraw the discarded liquidation request before preparing its corrected successor.")
            period = AccountingPeriod.objects.filter(department_id=owner.pk, status=AccountingPeriod.OPEN,
                starts_on__lte=request.jev_date, ends_on__gte=request.jev_date).first()
            if period is None:
                raise ValidationError("Choose an open Accounting period for this liquidation.")
            entry = JournalEntry(department_id=owner.pk, department_label=owner.name, reference=request.jev_number,
                entry_date=request.jev_date, period=period, fund=detail.entry.fund, source_type="voucher",
                source_reference=str(request.public_id), description=f"Advance liquidation: {data['document_reference']}",
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username,
                source_snapshot={"voucher_case": str(request.case.public_id), "payload_checksum": request.payload_checksum,
                    "posting_rule_checksum": request.posting_rule_checksum, "advance_application": data})
            entry.full_clean(); entry.save()
            for index, row in enumerate(data["expenses"], 1):
                line = JournalLine(entry=entry, sequence=index, account_id=row["account_id"],
                    debit=money(row["amount"]), memo=row["document_reference"][:255])
                line.full_clean(); line.save()
            credit = JournalLine(entry=entry, sequence=len(data["expenses"])+1,
                account=detail.journal_line.account, credit=money(data["amount"]), memo="Apply original officer advance")
            credit.full_clean(); credit.save()
            subsidiary = JournalSubsidiaryLine(entry=entry, journal_line=credit, category=JournalSubsidiaryLine.ADVANCE,
                reference_key=detail.reference_key, reference_label=detail.reference_label, source_code=detail.source_code,
                source_reference=str(request.public_id), credit=credit.credit,
                source_snapshot={"original_advance_detail": detail.pk, "original_entry": str(detail.entry.public_id),
                    "advance_application": data, "transaction_type": detail.source_code})
            subsidiary.full_clean(); subsidiary.save()
            validate(entry)
            created = True
    if request.status != Request.POSTED:
        request.status = Request.MATERIALIZED
        request.accounting_entry_public_id = entry.public_id
        request.materialized_at = timezone.now()
        request.save()
    return entry, created


@transaction.atomic
def reconcile(entry, actor):
    entry = require_persisted_posting(entry, actor, source_type="voucher")
    request = Request.objects.get(public_id=entry.source_reference)
    VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = validate(entry, check_capacity=False)
    request.status, request.accounting_entry_public_id = Request.POSTED, entry.public_id
    request.posted_at = entry.posted_at
    request.save()
    return request


@transaction.atomic
def withdraw(request, actor, reason):
    owner = department_for_user(actor)
    if not can_post_journals(actor) or owner is None or owner.pk != request.finance_department_id:
        raise PermissionDenied
    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = Request.objects.select_for_update().get(pk=request.pk)
    if not request.payload.get("advance_application") or actor.pk == request.requested_by_id or not str(reason).strip():
        raise ValidationError("An independent Accounting reviewer must retain a withdrawal reason.")
    if request.status == Request.CANCELLED:
        return request
    with transaction.atomic(using="finance"):
        entries = list(JournalEntry.objects.select_for_update().filter(source_type="voucher", source_reference=str(request.public_id)))
        if request.status == Request.POSTED or any(entry.status != JournalEntry.VOIDED for entry in entries):
            raise ValidationError("Discard every unposted liquidation journal before withdrawing its reservation; posted applications need a governed correction.")
        request.status = Request.CANCELLED
        request.failure_reason = str(reason).strip()
        request.save()
        from .services import _event
        _event(case, actor, "advance_liquidation_withdrawn", case.current_stage, str(reason).strip(),
            {"posting_request": str(request.public_id), "payload_checksum": request.payload_checksum},
            f"advance-withdraw:{request.public_id}")
    return request
