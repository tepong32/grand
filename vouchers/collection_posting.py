"""Independent review and recoverable posting for collection/deposit sources."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.access import can_prepare_journals, department_for_user
from accounting.models import JournalEntry, JournalLine, AccountingPeriod, Fund
from accounting.posted_evidence import verify_source_link, require_persisted_posting
from departments.models import Department
from finance.models import FinanceNumberingSequence, FinancePostingRule
from finance.services import posting_rule_snapshot
from .models import TreasuryCollectionSource as Source, CollectionPostingRequest as Request
from .collections import require, remaining_receipts, posted_receipt, account, context
from .remittances import _digest


@transaction.atomic
def review_source(*, source, actor, approve, reason):
    owner = require(actor,'vouchers.review_collections')
    from .advance_refunds import lock_source_case, validate_source
    lock_source_case(source)
    Department.objects.select_for_update().get(pk=source.treasury_department_id)
    source = Source.objects.select_for_update().get(pk=source.pk)
    if owner.pk != source.finance_department_id:
        raise PermissionDenied
    if source.status != Source.PROPOSED or actor.pk == source.prepared_by_id or not str(reason or '').strip():
        raise ValidationError('An independent reviewer must decide this proposed collection/deposit with a retained basis.')
    if _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('The retained collection/deposit proposal changed.')
    if approve:
        validate_source(source)
        if source.kind == Source.CORRECTION:
            from .collection_corrections import validate_correction
            original,original_request=validate_correction(source)
            fund,rule,snapshot,checksum=original.fund,original_request.posting_rule,original_request.posting_rule_snapshot,original_request.posting_rule_checksum
        else:
            _,fund,rule,snapshot,checksum=context(source.transaction_variant,source.source_date,source.fund_code,source.kind)
        if str(rule.public_id) != source.proposal['posting_rule'] or fund.pk != source.proposal['fund_id']:
            raise ValidationError('Retain the proposed source fund and reviewed posting rule.')
        if snapshot != source.proposal['posting_rule_snapshot'] or checksum != source.proposal['posting_rule_checksum']:
            raise ValidationError('The reviewed posting recipe changed. Return the source for correction.')
        if source.kind == Source.DEPOSIT:
            balances=remaining_receipts(source.treasury_department_id,exclude=source.pk,as_of=source.source_date)
            for row in source.proposal['allocations']:
                receipt=Source.objects.get(public_id=row['receipt'])
                entry=posted_receipt(receipt)
                if (receipt.proposal_checksum != row['proposal_checksum'] or str(entry.public_id) != row['entry']
                        or Decimal(row['amount']) > balances.get(row['receipt'],Decimal('0'))):
                    raise ValidationError('The deposit no longer fits its retained posted receipt allocation.')
            from .receipt_banks import bank_snapshot
            if bank_snapshot(source,source.proposal['receiving_bank']['configuration_item'],source.source_date) != source.proposal['receiving_bank']:
                raise ValidationError('The receiving bank mapping changed before independent deposit review.')
        sequences=FinanceNumberingSequence.objects.select_for_update().filter(department_id=source.finance_department_id,
            fiscal_year=source.source_date.year,document_type='journal-entry',status='active')
        if source.kind != Source.CORRECTION:
            sequences=sequences.filter(release=source.configuration_release)
        sequence=sequences.first()
        if sequence is None:
            raise ValidationError('Configure the active Accounting journal numbering sequence for this source date.')
        value=sequence.next_number
        number=f'{sequence.prefix}{value:0{sequence.padding}d}'
        payload={'collection_source':str(source.public_id),'source_kind':source.kind,'source_date':source.source_date.isoformat(),
            'amount':str(source.amount),'prepared_by':source.prepared_by_id,'reviewed_by':actor.pk,'review_reason':reason.strip(),
            'proposal':source.proposal,'proposal_checksum':source.proposal_checksum,
            'numbering':{'sequence_id':sequence.pk,'numeric_value':value}}
        request=Request(source=source,version=(source.posting_requests.aggregate(v=Max('version'))['v'] or 0)+1,
            jev_number=number,jev_date=source.source_date,finance_department_id=source.finance_department_id,
            finance_department_label=source.finance_department_label,posting_rule=rule,posting_rule_snapshot=snapshot,
            posting_rule_checksum=checksum,payload=payload,payload_checksum=_digest(payload),requested_by=actor)
        request.full_clean();request.save()
        sequence.next_number+=1;sequence.save(update_fields=('next_number',))
    source.status=Source.APPROVED if approve else Source.REJECTED
    source.reviewed_by,source.reviewed_at,source.review_reason=actor,timezone.now(),reason.strip()
    source.save()
    return source


def validate_collection_journal(entry):
    retained=entry.source_snapshot.get('collection_payload') or {}
    if (not retained or entry.source_snapshot.get('payload_checksum') != _digest(retained)
            or entry.source_snapshot.get('collection_source') != retained.get('collection_source')):
        raise ValidationError('Retain the approved collection/deposit source in the journal.')
    rows=[{'account_id':line.account_id,'account_code':line.account.code,'debit':str(line.debit),'credit':str(line.credit),
        'cash_flow_category':line.cash_flow_category} for line in entry.lines.select_related('account').order_by('sequence','pk')]
    if rows != retained['proposal']['financial_rows']:
        raise ValidationError('The collection/deposit journal must reproduce its approved financial rows exactly.')
    if entry.source_type == 'collection_fix':
        from .collection_corrections import mirror_rows
        original=JournalEntry.objects.get(public_id=retained['proposal']['original_entry'])
        if entry.reversal_of_id != original.pk or rows != mirror_rows(original):
            raise ValidationError('The correction must exactly reverse its original source journal.')
    from .advance_refunds import validate_journal
    validate_journal(entry)


@transaction.atomic
def materialize(request,actor):
    if not can_prepare_journals(actor) or getattr(department_for_user(actor),'pk',None) != request.finance_department_id:
        raise PermissionDenied
    from .advance_refunds import lock_source_case, validate_source, attach
    lock_source_case(request.source)
    Department.objects.select_for_update().get(pk=request.source.treasury_department_id)
    source=Source.objects.select_for_update().get(pk=request.source_id)
    request=Request.objects.select_for_update().get(pk=request.pk)
    if (source.status != Source.APPROVED or request.status not in (Request.PENDING,Request.FAILED,Request.MATERIALIZED)
            or request.payload['proposal_checksum'] != source.proposal_checksum or request.payload['proposal'] != source.proposal
            or _digest(source.proposal) != source.proposal_checksum or _digest(request.payload) != request.payload_checksum):
        raise ValidationError('Retain the approved collection/deposit source and posting request.')
    source_type={Source.RECEIPT:'collection',Source.DEPOSIT:'deposit',Source.CORRECTION:'collection_fix'}[source.kind]
    validate_source(source)
    with transaction.atomic(using='finance'):
        fund=Fund.objects.select_for_update().get(pk=source.proposal['fund_id'],department_id=source.finance_department_id)
        existing=JournalEntry.objects.filter(source_type=source_type,source_reference=str(request.public_id)).first()
        if existing:
            verify_source_link(request,existing,source_type=source_type);validate_collection_journal(existing)
            if existing.status == existing.VOIDED:
                raise ValidationError('Retain the discarded journal in a posting successor before retrying.')
            entry,created=existing,False
        else:
            if request.accounting_entry_public_id:
                raise ValidationError('Investigate the missing retained collection/deposit journal.')
            if source.kind == Source.DEPOSIT:
                balances=remaining_receipts(source.treasury_department_id,exclude=source.pk,as_of=source.source_date)
                for row in source.proposal['allocations']:
                    original=JournalEntry.objects.select_for_update().get(public_id=row['entry'])
                    receipt=Source.objects.get(public_id=row['receipt'])
                    if posted_receipt(receipt).pk != original.pk or Decimal(row['amount']) > balances.get(row['receipt'],Decimal('0')):
                        raise ValidationError('The deposit must retain its available posted collection shares.')
            period=AccountingPeriod.objects.get(department_id=source.finance_department_id,status=AccountingPeriod.OPEN,
                starts_on__lte=request.jev_date,ends_on__gte=request.jev_date)
            original=None
            if source.kind == Source.CORRECTION:
                from .collection_corrections import validate_correction
                original=JournalEntry.objects.select_for_update().get(public_id=source.proposal['original_entry'])
                validate_correction(source)
                if original.reversal_entries.exclude(status=original.VOIDED).exists():
                    raise ValidationError('Resolve the existing original-source reversal before creating another.')
            entry=JournalEntry(department_id=source.finance_department_id,department_label=source.finance_department_label,
                reference=request.jev_number,entry_date=request.jev_date,period=period,fund=fund,source_type=source_type,
                source_reference=str(request.public_id),description=f'{source.get_kind_display()}: {source.document_reference}',
                source_snapshot={'collection_source':str(source.public_id),'payload_checksum':request.payload_checksum,
                    'posting_rule_checksum':request.posting_rule_checksum,'collection_payload':request.payload},
                created_by_id=actor.pk,created_by_label=actor.get_full_name() or actor.username,
                reversal_of=original,reversal_reason=source.proposal['evidence_reference'] if original else '')
            entry.full_clean();entry.save()
            for sequence,row in enumerate(source.proposal['financial_rows'],start=1):
                ledger=account(source.finance_department_id,row['account_code'])
                if ledger.pk != row['account_id']:
                    raise ValidationError('The approved collection/deposit ledger account changed.')
                line=JournalLine(entry=entry,sequence=sequence,account=ledger,debit=Decimal(row['debit']),
                    credit=Decimal(row['credit']),cash_flow_category=row['cash_flow_category'],memo=source.document_reference)
                line.full_clean();line.save()
            attach(entry, source, request)
            validate_collection_journal(entry)
            from accounting.services import record_event
            record_event(entry,'collection_source_materialized',actor,snapshot={'proposal_checksum':source.proposal_checksum})
            created=True
    request.status,request.accounting_entry_public_id=request.MATERIALIZED,entry.public_id
    request.materialized_at,request.failure_reason=timezone.now(),'';request.save()
    return entry,created


@transaction.atomic
def reconcile(entry,actor):
    entry=require_persisted_posting(entry,actor,source_type=entry.source_type)
    if entry.source_type not in ('collection','deposit','collection_fix'):
        raise ValidationError('Choose a posted collection/deposit journal.')
    request=Request.objects.select_related('source').get(public_id=entry.source_reference)
    from .advance_refunds import lock_source_case
    lock_source_case(request.source)
    Department.objects.select_for_update().get(pk=request.source.treasury_department_id)
    source=Source.objects.select_for_update().get(pk=request.source_id)
    request=Request.objects.select_for_update().get(pk=request.pk)
    verify_source_link(request,entry,source_type=entry.source_type);validate_collection_journal(entry)
    if source.status == Source.POSTED and request.status == Request.POSTED:
        return source
    if source.status != Source.APPROVED or request.status == Request.CANCELLED:
        raise ValidationError('The source no longer awaits this approved posting.')
    request.status,request.posted_at,request.accounting_entry_public_id=Request.POSTED,entry.posted_at,entry.public_id
    request.failure_reason='';request.save()
    source.status=Source.POSTED;source.save(update_fields=('status',))
    return source


@transaction.atomic
def withdraw_unposted(*, source, actor, reason):
    """Retire approval only after every possible Finance draft is safely discarded."""
    owner = require(actor, 'vouchers.review_collections')
    from .advance_refunds import lock_source_case
    lock_source_case(source)
    Department.objects.select_for_update().get(pk=source.treasury_department_id)
    source = Source.objects.select_for_update().get(pk=source.pk)
    if owner.pk != source.finance_department_id:
        raise PermissionDenied
    if source.status != Source.APPROVED or actor.pk == source.prepared_by_id or not str(reason or '').strip():
        raise ValidationError('An independent Accounting reviewer must withdraw an unposted approval with a reason.')
    if _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('Retain the unchanged approved source evidence.')
    requests = list(source.posting_requests.select_for_update().order_by('version'))
    if not requests or any(row.status == Request.POSTED for row in requests):
        raise ValidationError('Resolve the retained source posting before withdrawing approval.')
    source_type = {Source.RECEIPT:'collection',Source.DEPOSIT:'deposit',Source.CORRECTION:'collection_fix'}[source.kind]
    with transaction.atomic(using='finance'):
        Fund.objects.select_for_update().get(pk=source.proposal['fund_id'],department_id=source.finance_department_id)
        for posting in requests:
            if (_digest(posting.payload) != posting.payload_checksum
                    or posting.payload.get('proposal') != source.proposal
                    or posting.payload.get('proposal_checksum') != source.proposal_checksum):
                raise ValidationError('Retain every approved posting request and its original source evidence.')
            entries = list(JournalEntry.objects.select_for_update().filter(
                source_type=source_type,source_reference=str(posting.public_id)))
            if not entries and posting.accounting_entry_public_id:
                raise ValidationError('Investigate the missing retained source journal before withdrawal.')
            for entry in entries:
                verify_source_link(posting,entry,source_type=source_type)
                validate_collection_journal(entry)
                if entry.status != entry.VOIDED or not entry.audit_events.filter(action='draft_discarded').exists():
                    raise ValidationError('Discard every unposted source JEV in Accounting before withdrawing approval. Posted sources require correction.')
        for posting in requests:
            posting.status = Request.CANCELLED
            posting.save(update_fields=('status',))
        source.status = Source.WITHDRAWN
        source.withdrawn_by,source.withdrawn_at,source.withdrawal_reason = actor,timezone.now(),reason.strip()
        source.save(update_fields=('status','withdrawn_by','withdrawn_at','withdrawal_reason'))
    return source
