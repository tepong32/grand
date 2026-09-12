"""Treasury receipt capture and explicit allocation of collected cash to deposits."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Max
from django.utils import timezone

from accounting.models import Fund, LedgerAccount, JournalEntry
from departments.models import Department
from finance.models import FinanceConfigurationItem, FinanceTransactionVariant, FinancePostingRule as Rule, FinancePostingRuleLine as Line
from finance.services import posting_rule_snapshot
from .access import department_for_user, has_explicit_permission
from .models import TreasuryCollectionSource as Source
from .roles import is_finance_uat_viewer
from .remittances import _digest


def require(actor, permission):
    if is_finance_uat_viewer(actor) or not has_explicit_permission(actor, permission):
        raise PermissionDenied
    department = department_for_user(actor)
    if department is None:
        raise PermissionDenied
    return department


def amount(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0 or result > Decimal('9999999999999999.99') or result != result.quantize(Decimal('.01')):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Enter a positive amount with no more than two decimal places.')
    return result.quantize(Decimal('.01'))


def active(query, day):
    return query.filter(status='active', effective_from__lte=day).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))


def context(variant, day, fund_code, kind):
    if not isinstance(day, date) or day > timezone.localdate():
        raise ValidationError('Use the actual receipt or deposit date, no later than today.')
    variant = FinanceTransactionVariant.objects.select_related('release').get(pk=variant.pk)
    release = variant.release
    if (not active(FinanceTransactionVariant.objects.filter(pk=variant.pk), day).exists()
            or release.status != 'active' or release.effective_from > day
            or release.effective_to and release.effective_to < day or release.department_id != variant.department_id):
        raise ValidationError('Choose a transaction and approved Finance setup active for this date.')
    if not active(FinanceConfigurationItem.objects.filter(release=release, department_id=release.department_id,
            category='fund', code=fund_code), day).exists():
        raise ValidationError('Choose a fund from the approved Finance setup for this date.')
    fund = Fund.objects.filter(department_id=release.department_id, code__iexact=fund_code, is_active=True).first()
    if fund is None:
        raise ValidationError('The approved fund needs its active Accounting ledger counterpart.')
    event, point = (Rule.COLLECTION, Rule.COLLECTION_RECEIPT) if kind == Source.RECEIPT else (Rule.DEPOSIT, Rule.COLLECTION_DEPOSIT)
    rule = variant.posting_rules.filter(event_kind=event, recognition_point=point, accounting_effect=Rule.JOURNAL_ENTRY).first()
    if rule is None:
        raise ValidationError('Configure the reviewed collection/deposit posting rule for this transaction.')
    snapshot, checksum = posting_rule_snapshot(rule)
    return variant, fund, rule, snapshot, checksum


def account(owner_id, code):
    rows = list(LedgerAccount.objects.filter(department_id=owner_id, code__iexact=code, is_active=True, allow_posting=True))
    if len(rows) != 1:
        raise ValidationError('The reviewed posting rule needs one active posting account for each fixed code.')
    return rows[0]


def financial_row(ledger, value, side, purpose=''):
    return {'account_id':ledger.pk, 'account_code':ledger.code, 'debit':str(value if side == Line.DEBIT else Decimal('0.00')),
        'credit':str(value if side == Line.CREDIT else Decimal('0.00')), 'cash_flow_category':purpose}


def receipt_rows(owner_id, snapshot, total):
    instructions = snapshot['lines']
    if (len(instructions) != 2 or any(r['account_source'] != Line.FIXED_ACCOUNT or r['amount_source'] != Line.EVENT_AMOUNT for r in instructions)
            or {r['side'] for r in instructions} != {Line.DEBIT, Line.CREDIT}):
        raise ValidationError('A cash collection needs the reviewed cash debit and revenue/liability credit for the received amount.')
    rows = []
    for instruction in instructions:
        ledger = account(owner_id, instruction['ledger_account_code'])
        if ((instruction['side'] == Line.DEBIT and ledger.account_type != 'asset')
                or (instruction['side'] == Line.CREDIT and ledger.account_type not in ('revenue', 'liability'))):
            raise ValidationError('Use the reviewed cash asset and revenue/liability collection accounts.')
        purpose = instruction.get('cash_flow_category', '')
        if instruction['side'] == Line.DEBIT and (not purpose or purpose == 'internal'):
            raise ValidationError('Classify the external collection cash purpose in the reviewed rule.')
        if instruction['side'] == Line.CREDIT and purpose:
            raise ValidationError('The non-cash collection credit must not carry a cash-flow purpose.')
        rows.append(financial_row(ledger, total, instruction['side'], purpose))
    return rows


def new_source(*, actor, treasury, variant, fund, kind, book, reference, day, total, proposal, correction_of=None):
    book, reference = str(book or '').strip(), str(reference or '').strip()
    if not reference or len(reference) > 80 or len(book) > 80 or kind == Source.RECEIPT and not book:
        raise ValidationError('Retain the actual receipt book/number or deposit reference, up to 80 characters each.')
    prior = Source.objects.filter(treasury_department=treasury, kind=kind,
        book_reference__iexact=book, document_reference__iexact=reference).order_by('-version').first()
    corrected = prior and prior.corrections.filter(status=Source.POSTED,source_date__lte=day).exists()
    if corrected:
        from .collection_corrections import corrected_sources
        corrected = prior.pk in corrected_sources(treasury.pk,day)
    if prior and prior.status not in (Source.REJECTED, Source.WITHDRAWN) and not corrected:
        raise ValidationError('This receipt/deposit reference already has an active or posted source.')
    if prior and not corrected and prior.posting_requests.exclude(status='cancelled').exists():
        raise ValidationError('Resolve the prior posting request before correcting this source.')
    return Source.objects.create(treasury_department=treasury, configuration_release=variant.release,
        transaction_variant=variant, finance_department_id=variant.department_id,
        finance_department_label=variant.department.name, kind=kind, book_reference=book,
        document_reference=reference, version=prior.version + 1 if prior else 1, supersedes=prior, correction_of=correction_of,
        source_date=day, fund_code=fund.code, amount=total, proposal=proposal,
        proposal_checksum=_digest(proposal), prepared_by=actor)


@transaction.atomic
def record_receipt(*, actor, variant, received_on, fund_code, receipt_book, receipt_number, payer_reference, received_amount, evidence_reference):
    treasury = require(actor, 'vouchers.prepare_collections')
    treasury = Department.objects.select_for_update().get(pk=treasury.pk)
    variant, fund, rule, snapshot, checksum = context(variant, received_on, fund_code, Source.RECEIPT)
    total = amount(received_amount)
    if not str(payer_reference or '').strip() or not str(evidence_reference or '').strip():
        raise ValidationError('Record the payer/reference and actual collection evidence.')
    rows = receipt_rows(variant.department_id, snapshot, total)
    proposal = {'schema_version':1, 'payer_reference':str(payer_reference).strip(),
        'evidence_reference':str(evidence_reference).strip(), 'posting_rule':str(rule.public_id),
        'posting_rule_snapshot':snapshot, 'posting_rule_checksum':checksum, 'fund_id':fund.pk,
        'financial_rows':rows, 'cash_account_id':next(r['account_id'] for r in rows if Decimal(r['debit']) > 0)}
    return new_source(actor=actor, treasury=treasury, variant=variant, fund=fund, kind=Source.RECEIPT,
        book=receipt_book, reference=receipt_number, day=received_on, total=total, proposal=proposal)


def posted_receipt(receipt):
    if receipt.kind != Source.RECEIPT or receipt.status != Source.POSTED or _digest(receipt.proposal) != receipt.proposal_checksum:
        raise ValidationError('Deposit only an unchanged, reconciled posted collection receipt.')
    requests = list(receipt.posting_requests.filter(status='posted'))
    if len(requests) != 1:
        raise ValidationError('The receipt must retain one posted Accounting source.')
    source = requests[0]
    entry = JournalEntry.objects.get(public_id=source.accounting_entry_public_id)
    from accounting.posted_evidence import verify_source_link
    from .collection_posting import validate_collection_journal
    verify_source_link(source, entry, source_type='collection')
    validate_collection_journal(entry)
    if source.payload.get('proposal') != receipt.proposal or source.payload.get('proposal_checksum') != receipt.proposal_checksum:
        raise ValidationError('The posted receipt must reproduce the reviewed source evidence.')
    if (entry.status != entry.POSTED or entry.source_type != 'collection' or entry.source_reference != str(source.public_id)
            or entry.source_snapshot.get('payload_checksum') != source.payload_checksum or _digest(source.payload) != source.payload_checksum
            or not entry.posted_at or not entry.posted_by_id or entry.posted_by_id in (entry.created_by_id, entry.submitted_by_id, receipt.prepared_by_id)
            or not entry.audit_events.filter(action='posted', actor_id=entry.posted_by_id).exists()
            or entry.reversal_entries.exclude(status=entry.VOIDED).exists()):
        raise ValidationError('Retain the independently posted receipt journal and resolve any reversal first.')
    return entry


def remaining_receipts(treasury_id, *, exclude=None, as_of=None):
    from .collection_corrections import corrected_sources
    as_of = as_of or timezone.localdate()
    corrected = corrected_sources(treasury_id,as_of)
    held = Source.objects.filter(treasury_department_id=treasury_id,kind=Source.CORRECTION,
        correction_of__kind=Source.RECEIPT,status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).values_list('correction_of_id',flat=True)
    remaining = {str(r.public_id):r.amount for r in Source.objects.filter(
        treasury_department_id=treasury_id, kind=Source.RECEIPT, status=Source.POSTED).exclude(pk__in=held)}
    for deposit in Source.objects.filter(treasury_department_id=treasury_id, kind=Source.DEPOSIT,
            status__in=(Source.PROPOSED, Source.APPROVED, Source.POSTED)).exclude(pk=exclude).exclude(pk__in=corrected):
        if _digest(deposit.proposal) != deposit.proposal_checksum:
            raise ValidationError('The retained deposit allocation checksum changed.')
        for row in deposit.proposal['allocations']:
            key = row['receipt']
            if key not in remaining:
                raise ValidationError('An allocated receipt is missing from the reconciled collection register.')
            remaining[key] -= Decimal(row['amount'])
    return remaining


@transaction.atomic
def record_deposit(*, actor, variant, deposited_on, fund_code, deposit_reference, receiving_bank_id, allocations, evidence_reference):
    treasury = require(actor, 'vouchers.prepare_collection_deposits')
    treasury = Department.objects.select_for_update().get(pk=treasury.pk)
    variant, fund, rule, snapshot, checksum = context(variant, deposited_on, fund_code, Source.DEPOSIT)
    if not str(evidence_reference or '').strip():
        raise ValidationError('Retain the actual bank deposit evidence.')
    from .receipt_banks import bank_snapshot
    from types import SimpleNamespace
    bank = bank_snapshot(SimpleNamespace(finance_department_id=variant.department_id), receiving_bank_id, deposited_on)
    balances, retained, seen, credits = remaining_receipts(treasury.pk,as_of=deposited_on), [], set(), {}
    for supplied in allocations:
        key, value = str(supplied['receipt']), amount(supplied['amount'])
        receipt = Source.objects.filter(public_id=key, treasury_department=treasury, finance_department_id=variant.department_id,
            kind=Source.RECEIPT, fund_code=fund.code).first()
        if receipt is None or key in seen or receipt.source_date > deposited_on or value > balances.get(key, Decimal('0')):
            raise ValidationError('Each deposit share must fit a distinct posted receipt from this office/fund and date.')
        entry = posted_receipt(receipt)
        cash_id = receipt.proposal['cash_account_id']
        credit = credits.setdefault(cash_id, {'amount':Decimal('0'), 'code':entry.lines.get(account_id=cash_id, debit__gt=0).account.code})
        credit['amount'] += value
        retained.append({'receipt':key, 'amount':str(value), 'proposal_checksum':receipt.proposal_checksum,
            'entry':str(entry.public_id), 'cash_account_id':cash_id})
        seen.add(key)
    if not retained:
        raise ValidationError('Select at least one posted receipt amount for the actual deposit.')
    total = amount(sum((Decimal(r['amount']) for r in retained), Decimal('0')))
    instructions = snapshot['lines']
    if (len(instructions) != 2 or not any(r['side'] == Line.DEBIT and r['account_source'] == Line.BANK_MAPPING
            and r['amount_source'] == Line.EVENT_AMOUNT and not r['mapping_code'] for r in instructions)
            or not any(r['side'] == Line.CREDIT and r['account_source'] == Line.ALLOCATION_ACCOUNTS
                and r['amount_source'] == Line.EACH_ALLOCATION for r in instructions)
            or any(r.get('cash_flow_category') != 'internal' for r in instructions)):
        raise ValidationError('The deposit rule must transfer selected receipt cash to the selected bank, with both sides classified internal.')
    rows = [financial_row(account(variant.department_id, bank['ledger_account_code']), total, Line.DEBIT, 'internal')]
    for cash_id, credit in sorted(credits.items()):
        if cash_id == bank['ledger_account_id']:
            raise ValidationError('The deposit bank must differ from the source collection cash account.')
        rows.append(financial_row(account(variant.department_id, credit['code']), credit['amount'], Line.CREDIT, 'internal'))
    proposal = {'schema_version':1, 'evidence_reference':str(evidence_reference).strip(), 'posting_rule':str(rule.public_id),
        'posting_rule_snapshot':snapshot, 'posting_rule_checksum':checksum, 'fund_id':fund.pk,
        'receiving_bank':bank, 'allocations':sorted(retained,key=lambda r:r['receipt']), 'financial_rows':rows}
    return new_source(actor=actor, treasury=treasury, variant=variant, fund=fund, kind=Source.DEPOSIT,
        book='', reference=deposit_reference, day=deposited_on, total=total, proposal=proposal)
