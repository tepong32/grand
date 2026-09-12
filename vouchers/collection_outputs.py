"""Freeze printable source records without claiming an unverified official layout."""
import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.template.loader import render_to_string
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from departments.models import Department
from .access import has_explicit_permission
from .models import TreasuryCollectionSource as Source, CollectionOutput
from .remittances import _digest


def permitted_source(user, source_id):
    from .collection_views import visible_sources
    if not has_explicit_permission(user,'finance.export_finance_work'):
        raise PermissionDenied
    source=visible_sources(user).filter(pk=source_id).first()
    if source is None:
        raise PermissionDenied
    return source


@transaction.atomic
def generate(*, source, actor):
    permitted_source(actor,source.pk)
    Department.objects.select_for_update().get(pk=source.treasury_department_id)
    source=Source.objects.select_for_update().get(pk=source.pk)
    if source.status != Source.POSTED or _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('Generate a retained printable copy only from an unchanged posted source.')
    postings=list(source.posting_requests.filter(status='posted'))
    if len(postings) != 1:
        raise ValidationError('Retain one posted source JEV before generating the printable copy.')
    posting=postings[0]
    entry=JournalEntry.objects.get(public_id=posting.accounting_entry_public_id)
    source_type={Source.RECEIPT:'collection',Source.DEPOSIT:'deposit',Source.CORRECTION:'collection_fix'}[source.kind]
    verify_source_link(posting,entry,source_type=source_type)
    from .collection_posting import validate_collection_journal
    validate_collection_journal(entry)
    if (entry.status != entry.POSTED or not entry.posted_at or not entry.posted_by_id
            or not entry.audit_events.filter(action='posted',actor_id=entry.posted_by_id).exists()
            or posting.payload.get('proposal') != source.proposal):
        raise ValidationError('Retain the actual posted JEV and original proposal before generating output.')
    version=(source.issued_outputs.aggregate(value=Max('version'))['value'] or 0)+1
    allocations=[]
    for row in source.proposal.get('allocations',[]):
        receipt=Source.objects.get(public_id=row['receipt'],treasury_department_id=source.treasury_department_id)
        allocations.append({'book':receipt.book_reference,'reference':receipt.document_reference,
            'date':receipt.source_date.isoformat(),'amount':row['amount']})
    snapshot={'schema_version':1,'source':str(source.public_id),'kind':source.get_kind_display(),
        'reference':source.document_reference,'book':source.book_reference,'source_version':source.version,
        'date':source.source_date.isoformat(),'fund':source.fund_code,'amount':str(source.amount),
        'payer':source.proposal.get('payer_reference',''),'evidence':source.proposal['evidence_reference'],
        'bank':source.proposal.get('receiving_bank',{}).get('bank_label',''),
        'allocations':allocations,'journal':posting.jev_number,'posted_at':entry.posted_at.isoformat(),
        'rows':source.proposal['financial_rows'],'prepared_by':source.prepared_by.get_username(),
        'reviewed_by':source.reviewed_by.get_username(),'review_reason':source.review_reason,
        'correction_of':str(source.correction_of.public_id) if source.correction_of_id else '',
        'corrections':[{'source':str(c.public_id),'date':c.source_date.isoformat(),'status':c.get_status_display()}
            for c in source.corrections.order_by('pk')],
        'source_checksum':source.proposal_checksum,'posting_checksum':posting.payload_checksum,
        'output_version':version,'generated_at':timezone.now().isoformat(),'generated_by':actor.get_username()}
    content=render_to_string('vouchers/collections/print.html',{'record':snapshot})
    return CollectionOutput.objects.create(source=source,version=version,snapshot=snapshot,
        snapshot_checksum=_digest(snapshot),html=content,checksum=hashlib.sha256(content.encode('utf-8')).hexdigest(),generated_by=actor)


def content(output, actor):
    permitted_source(actor,output.source_id)
    if (_digest(output.snapshot) != output.snapshot_checksum
            or hashlib.sha256(output.html.encode('utf-8')).hexdigest() != output.checksum):
        raise ValidationError('The retained printable copy failed its integrity check.')
    return output.html.encode('utf-8')
