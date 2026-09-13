"""Exact, independently posted corrections of accepted expense liquidations."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from accounting.access import can_prepare_journals, department_for_user
from accounting.models import JournalEntry, JournalLine, JournalSubsidiaryLine, Fund, AccountingPeriod
from accounting.posted_evidence import verify_source_link, require_persisted_posting
from finance.models import FinanceNumberingSequence
from .models import VoucherCase, VoucherPostingRequest as Request
from .advance_sources import posted_request
from .remittances import _digest


def financial_rows(entry):
    return [{'line': row.pk, 'sequence': row.sequence, 'account': row.account_id,
        'debit': str(row.debit), 'credit': str(row.credit), 'cash_flow_category': row.cash_flow_category}
        for row in entry.lines.order_by('sequence', 'pk')]


def source_application(request, *, correction=None):
    from .advance_applications import validate as validate_application
    request = Request.objects.select_related('case', 'posting_rule').get(pk=request.pk)
    if not request.payload.get('advance_application'):
        raise ValidationError('Choose an original posted expense liquidation for correction.')
    entry = posted_request(request, allow_reversal_reference=correction.public_id if correction else None)
    validate_application(entry, check_capacity=False)
    return request, entry


def corrections(application):
    rows = []
    for request in application.case.posting_requests.filter(trigger_key__startswith='advance-liquidation-fix:'):
        data = request.payload.get('advance_application_correction')
        if (not data or _digest(request.payload) != request.payload_checksum
                or _digest(request.posting_rule_snapshot) != request.posting_rule_checksum):
            raise ValidationError('The retained liquidation correction evidence changed.')
        if request.status == Request.CANCELLED:
            event = application.case.events.filter(action='advance_liquidation_correction_withdrawn',
                metadata__posting_request=str(request.public_id)).first()
            if (not event or event.actor_id == request.requested_by_id or not event.reason
                    or JournalEntry.objects.filter(source_type='voucher', source_reference=str(request.public_id))
                    .exclude(status=JournalEntry.VOIDED).exists()):
                raise ValidationError('Retain the independently withdrawn unposted correction.')
            continue
        if data['original_request'] == str(application.public_id):
            rows.append(request)
    return rows


def restored_movements(application):
    rows = []
    for request in corrections(application):
        if request.status != Request.POSTED:
            continue
        entry = posted_request(request)
        validate(entry)
        rows.append((request.jev_date, -Decimal(request.payload['advance_application_correction']['amount'])))
    if len(rows) > 1:
        raise ValidationError('Resolve duplicate posted liquidation corrections.')
    return rows


@transaction.atomic
def prepare(*, application, actor, day, reason, key):
    owner = department_for_user(actor)
    if not can_prepare_journals(actor) or owner is None or application.finance_department_id != owner.pk:
        raise PermissionDenied
    case = VoucherCase.objects.select_for_update().get(pk=application.case_id)
    if not str(reason or '').strip() or not str(key or '').strip() or len(str(key)) > 100:
        raise ValidationError('Retain the correction reason and request identity.')
    trigger = f'advance-liquidation-fix:{key}'
    existing = case.posting_requests.filter(trigger_key=trigger).first()
    application, original = source_application(application, correction=existing)
    if not original.entry_date <= day <= timezone.localdate():
        raise ValidationError('Use an actual correction date on or after the original liquidation.')
    data = {'schema_version': 1, 'original_request': str(application.public_id),
        'original_payload_checksum': application.payload_checksum, 'original_entry': str(original.public_id),
        'original_jev_number': original.reference,
        'original_detail': application.payload['advance_application']['original_detail'],
        'original_subsidiary': original.subsidiary_lines.get().pk,
        'amount': application.payload['advance_application']['amount'], 'original_lines': financial_rows(original),
        'reason': str(reason).strip(), 'prepared_by': actor.pk}
    if existing:
        if _digest(existing.payload) != existing.payload_checksum:
            raise ValidationError('The retained correction request checksum changed.')
        if existing.status == Request.CANCELLED:
            raise ValidationError('The correction was withdrawn; use a fresh request identity.')
        if existing.jev_date != day or existing.payload.get('advance_application_correction') != data:
            raise ValidationError('This request identity belongs to another retained correction.')
        return existing
    if corrections(application):
        raise ValidationError('Resolve the existing correction of this liquidation first.')
    sequence = FinanceNumberingSequence.objects.select_for_update().filter(department_id=owner.pk,
        fiscal_year=day.year, document_type='journal-entry', status='active', release__status='active',
        release__effective_from__lte=day).filter(Q(release__effective_to__isnull=True) | Q(release__effective_to__gte=day)).first()
    if sequence is None:
        raise ValidationError('Configure the active Accounting JEV numbering sequence for this correction date.')
    payload = {'advance_application_correction': data, 'voucher_case_public_id': str(case.public_id),
        'voucher_reference': case.reference_code, 'dv_number': application.payload['dv_number'],
        'payee_key': application.payload['payee_key'], 'payee_name': application.payload['payee_name']}
    request = Request(case=case, kind=Request.LIQUIDATION,
        version=(case.posting_requests.filter(kind=Request.LIQUIDATION).aggregate(v=Max('version'))['v'] or 0)+1,
        trigger_key=trigger, jev_number=f'{sequence.prefix}{sequence.next_number:0{sequence.padding}d}', jev_date=day,
        finance_department_id=owner.pk, finance_department_label=owner.name,
        posting_rule=application.posting_rule, posting_rule_public_id_snapshot=application.posting_rule_public_id_snapshot,
        posting_rule_snapshot=application.posting_rule_snapshot, posting_rule_checksum=application.posting_rule_checksum,
        payload=payload, payload_checksum=_digest(payload), requested_by=actor)
    request.full_clean(); request.save()
    sequence.next_number += 1; sequence.save(update_fields=('next_number',))
    return request


def validate(entry):
    request = Request.objects.select_related('case').get(public_id=entry.source_reference)
    if request.status == Request.CANCELLED:
        raise ValidationError('The retained liquidation correction was withdrawn.')
    verify_source_link(request, entry, source_type='voucher')
    data = request.payload['advance_application_correction']
    application = Request.objects.get(public_id=data['original_request'], case_id=request.case_id)
    application, original = source_application(application, correction=request)
    if (entry.source_snapshot.get('advance_application_correction') != data
            or str(original.public_id) != data['original_entry']
            or original.reference != data['original_jev_number']
            or application.payload_checksum != data['original_payload_checksum']
            or data['original_detail'] != application.payload['advance_application']['original_detail']
            or Decimal(data['amount']) != Decimal(application.payload['advance_application']['amount'])
            or data['prepared_by'] != request.requested_by_id or entry.reversal_reason != data['reason']
            or request.posting_rule_checksum != application.posting_rule_checksum
            or financial_rows(original) != data['original_lines']
            or entry.reversal_of_id != original.pk or entry.fund_id != original.fund_id
            or entry.entry_date < original.entry_date):
        raise ValidationError('The correction must retain its exact original liquidation and immutable source.')
    expected = [(row.sequence, row.account_id, row.credit, row.debit, row.cash_flow_category)
                for row in original.lines.order_by('sequence', 'pk')]
    actual = [(row.sequence, row.account_id, row.debit, row.credit, row.cash_flow_category)
              for row in entry.lines.order_by('sequence', 'pk')]
    if actual != expected:
        raise ValidationError('The liquidation correction must exactly mirror every original financial line.')
    original_detail = original.subsidiary_lines.get()
    rows = list(entry.subsidiary_lines.all())
    if (len(rows) != 1 or original_detail.pk != data['original_subsidiary']
            or rows[0].category != JournalSubsidiaryLine.ADVANCE
            or rows[0].reference_key != original_detail.reference_key
            or rows[0].reference_label != original_detail.reference_label
            or rows[0].source_code != original_detail.source_code
            or rows[0].source_reference != str(request.public_id)
            or rows[0].debit != original_detail.credit or rows[0].credit != original_detail.debit
            or rows[0].journal_line_id != entry.lines.get(sequence=original_detail.journal_line.sequence).pk
            or rows[0].source_snapshot.get('advance_application_correction') != data):
        raise ValidationError('The correction must mirror its original officer subsidiary exactly.')
    return request


@transaction.atomic
def materialize(request, actor):
    owner = department_for_user(actor)
    if not can_prepare_journals(actor) or owner is None or owner.pk != request.finance_department_id:
        raise PermissionDenied
    VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = Request.objects.select_for_update().get(pk=request.pk)
    if request.status == Request.CANCELLED or _digest(request.payload) != request.payload_checksum:
        raise ValidationError('Retain the unchanged active liquidation correction request.')
    data = request.payload['advance_application_correction']
    application, original = source_application(Request.objects.get(public_id=data['original_request']), correction=request)
    with transaction.atomic(using='finance'):
        Fund.objects.select_for_update().get(pk=original.fund_id)
        original = JournalEntry.objects.select_for_update().get(pk=original.pk)
        entries = list(JournalEntry.objects.filter(source_type='voucher', source_reference=str(request.public_id)))
        if entries:
            if len(entries) != 1 or entries[0].status == JournalEntry.VOIDED:
                raise ValidationError('Withdraw the discarded correction before preparing a fresh corrected request.')
            entry, created = entries[0], False
        else:
            if original.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
                raise ValidationError('Resolve the existing liquidation reversal first.')
            period = AccountingPeriod.objects.get(department_id=owner.pk, status=AccountingPeriod.OPEN,
                starts_on__lte=request.jev_date, ends_on__gte=request.jev_date)
            entry = JournalEntry(department_id=owner.pk, department_label=owner.name, reference=request.jev_number,
                entry_date=request.jev_date, period=period, fund=original.fund, source_type='voucher',
                source_reference=str(request.public_id), reversal_of=original, reversal_reason=data['reason'],
                description=f"Correct liquidation {original.reference}: {data['reason']}",
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username,
                source_snapshot={'voucher_case':str(request.case.public_id), 'payload_checksum':request.payload_checksum,
                    'posting_rule_checksum':request.posting_rule_checksum, 'advance_application_correction':data})
            entry.full_clean(); entry.save()
            for row in original.lines.order_by('sequence', 'pk'):
                line = JournalLine(entry=entry, sequence=row.sequence, account=row.account,
                    debit=row.credit, credit=row.debit, cash_flow_category=row.cash_flow_category, memo=row.memo)
                line.full_clean(); line.save()
            original_detail = original.subsidiary_lines.get()
            row = JournalSubsidiaryLine(entry=entry,
                journal_line=entry.lines.get(sequence=original_detail.journal_line.sequence),
                category=original_detail.category, reference_key=original_detail.reference_key,
                reference_label=original_detail.reference_label, source_code=original_detail.source_code,
                source_reference=str(request.public_id), debit=original_detail.credit, credit=original_detail.debit,
                source_snapshot={'advance_application_correction':data, 'transaction_type':original_detail.source_code})
            row.full_clean(); row.save()
            created = True
        validate(entry)
    if request.status != Request.POSTED:
        request.status, request.accounting_entry_public_id = Request.MATERIALIZED, entry.public_id
        request.materialized_at = timezone.now(); request.save()
    return entry, created


@transaction.atomic
def reconcile(entry, actor):
    entry = require_persisted_posting(entry, actor, source_type='voucher')
    request = Request.objects.get(public_id=entry.source_reference)
    VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = validate(entry)
    request.status, request.posted_at, request.accounting_entry_public_id = Request.POSTED, entry.posted_at, entry.public_id
    request.save()
    return request
