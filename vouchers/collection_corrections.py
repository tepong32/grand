"""Exact posted-source corrections; original receipts and deposits remain intact."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from departments.models import Department
from .models import TreasuryCollectionSource as Source
from .collections import require, new_source
from .remittances import _digest


def corrected_sources(treasury_id, day):
    from .collection_posting import validate_collection_journal
    corrected=set()
    for source in Source.objects.filter(treasury_department_id=treasury_id,kind=Source.CORRECTION,
            status=Source.POSTED,source_date__lte=day):
        postings=list(source.posting_requests.filter(status='posted'))
        if len(postings) != 1 or _digest(source.proposal) != source.proposal_checksum:
            raise ValidationError('Retain one unchanged correction posting before releasing source allocations.')
        posting=postings[0]
        entry=JournalEntry.objects.get(public_id=posting.accounting_entry_public_id)
        verify_source_link(posting,entry,source_type='collection_fix')
        validate_collection_journal(entry)
        if (entry.status != entry.POSTED or not entry.posted_at or not entry.posted_by_id
                or not entry.audit_events.filter(action='posted',actor_id=entry.posted_by_id).exists()
                or posting.payload.get('proposal') != source.proposal):
            raise ValidationError('Retain the posted exact correction before releasing source allocations.')
        corrected.add(source.correction_of_id)
    return corrected


def original_journal(source):
    from .collection_posting import validate_collection_journal
    if source.status != Source.POSTED or source.kind not in (Source.RECEIPT,Source.DEPOSIT):
        raise ValidationError('Choose a posted receipt or deposit for correction.')
    postings = list(source.posting_requests.filter(status='posted'))
    if len(postings) != 1 or _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('Retain one unchanged posted source and its JEV.')
    posting = postings[0]
    entry = JournalEntry.objects.get(public_id=posting.accounting_entry_public_id)
    verify_source_link(posting,entry,source_type='collection' if source.kind == Source.RECEIPT else 'deposit')
    validate_collection_journal(entry)
    if (entry.status != entry.POSTED or not entry.posted_at or not entry.posted_by_id
            or not entry.audit_events.filter(action='posted',actor_id=entry.posted_by_id).exists()):
        raise ValidationError('Retain the original independent posting evidence.')
    return entry,posting


def validate_target(source, day, *, exclude=None):
    entry,posting = original_journal(source)
    if not isinstance(day,date) or not source.source_date <= day <= timezone.localdate():
        raise ValidationError('Use an actual correction date on or after the original source date, no later than today.')
    if source.corrections.filter(status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).exclude(pk=exclude).exists():
        raise ValidationError('Resolve the existing correction for this source.')
    if source.kind == Source.RECEIPT:
        corrected = corrected_sources(source.treasury_department_id,day)
        for deposit in Source.objects.filter(treasury_department_id=source.treasury_department_id,kind=Source.DEPOSIT,
                status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).exclude(pk__in=corrected):
            if any(row['receipt'] == str(source.public_id) for row in deposit.proposal['allocations']):
                raise ValidationError('Correct or withdraw all allocated deposits before correcting their receipt.')
    return entry,posting


def mirror_rows(entry):
    return [{'account_id':line.account_id,'account_code':line.account.code,
        'debit':str(line.credit),'credit':str(line.debit),'cash_flow_category':line.cash_flow_category}
        for line in entry.lines.select_related('account').order_by('sequence','pk')]


@transaction.atomic
def propose(*, original, actor, corrected_on, reason):
    office = require(actor,'vouchers.prepare_collections' if original.kind == Source.RECEIPT else 'vouchers.prepare_collection_deposits')
    if office.pk != original.treasury_department_id:
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=office.pk)
    original = Source.objects.select_for_update().get(pk=original.pk)
    entry,posting = validate_target(original,corrected_on)
    if not str(reason or '').strip():
        raise ValidationError('Explain the posted source error and required correction.')
    if entry.reversal_entries.exclude(status=entry.VOIDED).exists():
        raise ValidationError('Resolve the existing source reversal first.')
    proposal = {'schema_version':1,'original_source':str(original.public_id),'original_entry':str(entry.public_id),
        'original_proposal_checksum':original.proposal_checksum,'evidence_reference':reason.strip(),
        'posting_rule':str(posting.posting_rule.public_id),'posting_rule_snapshot':posting.posting_rule_snapshot,
        'posting_rule_checksum':posting.posting_rule_checksum,'fund_id':entry.fund_id,'financial_rows':mirror_rows(entry)}
    correction = new_source(actor=actor,treasury=office,variant=original.transaction_variant,fund=entry.fund,
        kind=Source.CORRECTION,book='',reference=str(original.public_id),day=corrected_on,total=original.amount,proposal=proposal,
        correction_of=original)
    return correction


def validate_correction(source):
    entry,posting = validate_target(source.correction_of,source.source_date,exclude=source.pk)
    if (str(entry.public_id) != source.proposal['original_entry']
            or source.correction_of.proposal_checksum != source.proposal['original_proposal_checksum']
            or mirror_rows(entry) != source.proposal['financial_rows']):
        raise ValidationError('Retain the exact original financial rows and source evidence for correction.')
    return entry,posting
