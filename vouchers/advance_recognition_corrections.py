"""Governed correction of an unpaid original advance, retaining issued evidence."""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.access import can_prepare_journals, can_post_journals, department_for_user
from accounting.models import AccountingPeriod, Fund, JournalEntry, JournalLine, JournalSubsidiaryLine
from accounting.posted_evidence import require_persisted_posting, verify_source_link
from .advance_sources import posted_request
from .models import VoucherCase, VoucherPostingRequest as Request
from .remittances import _digest

KEY = 'advance_recognition_correction'


def rows(entry):
    return [{'sequence': x.sequence, 'account': x.account_id, 'center': x.responsibility_center_id,
             'debit': str(x.debit), 'credit': str(x.credit), 'cash': x.cash_flow_category}
            for x in entry.lines.order_by('sequence', 'pk')]


def subsidiaries(entry):
    return [{'line': x.journal_line.sequence, 'category': x.category, 'key': x.reference_key,
             'label': x.reference_label, 'code': x.source_code, 'debit': str(x.debit),
             'credit': str(x.credit), 'snapshot': x.source_snapshot, 'id': x.pk}
            for x in entry.subsidiary_lines.select_related('journal_line').order_by('journal_line__sequence', 'pk')]


def unpaid(case, *, exclude=None):
    if case.payment_instruments.exists():
        raise ValidationError('Resolve the issued payment cycle before correcting original advance recognition.')
    pending = case.posting_requests.filter(status__in=(Request.PENDING, Request.MATERIALIZED, Request.FAILED))
    if exclude:
        pending = pending.exclude(pk=exclude)
    if pending.exists():
        raise ValidationError('Resolve other pending source postings before correcting the original advance.')


def no_payable_use(source):
    from accounting.models import PayableClaimReservation
    credits = source.lines.filter(credit__gt=0).values_list('pk', flat=True)
    if (JournalLine.objects.filter(payable_origin_id__in=credits).exclude(entry__status=JournalEntry.VOIDED).exists()
            or PayableClaimReservation.objects.filter(source_id__in=credits, released_at__isnull=True).exists()):
        raise ValidationError('Resolve linked payable applications and reservations before correcting the original advance.')
    from accounting.claim_attributions import current
    if any(current(line) for line in source.lines.filter(credit__gt=0)):
        raise ValidationError('Resolve reviewed historical claim attribution before correcting this original advance.')


def validate(entry):
    request = Request.objects.select_related('case').get(public_id=entry.source_reference)
    if request.status == Request.CANCELLED:
        raise ValidationError('This original advance correction was withdrawn.')
    verify_source_link(request, entry, source_type='voucher')
    data = request.payload[KEY]
    original = Request.objects.get(case_id=request.case_id, public_id=data['original_request'], kind=Request.RECOGNITION)
    source = posted_request(original, allow_reversal_reference=request.public_id)
    no_payable_use(source)
    if (not original.payload.get('advance_recognition') or original.payload_checksum != data['original_checksum']
            or original.posting_rule_checksum != data['original_rule_checksum']
            or str(source.public_id) != data['original_entry'] or rows(source) != data['lines']
            or subsidiaries(source) != data['subsidiaries'] or data['prepared_by'] != request.requested_by_id
            or entry.source_snapshot.get(KEY) != data or entry.reversal_of_id != source.pk
            or entry.fund_id != source.fund_id or entry.entry_date < source.entry_date
            or entry.reversal_reason != data['reason']):
        raise ValidationError('Retain the exact original advance, financial lines and officer evidence.')
    expected = [dict(x, debit=x['credit'], credit=x['debit']) for x in data['lines']]
    if rows(entry) != expected:
        raise ValidationError('The advance correction must exactly mirror every original financial line.')
    actual = list(entry.subsidiary_lines.select_related('journal_line').order_by('journal_line__sequence', 'pk'))
    if len(actual) != len(data['subsidiaries']):
        raise ValidationError('Retain every original advance and payable subsidiary in the correction.')
    for x, old in zip(actual, data['subsidiaries']):
        if (x.journal_line.sequence != old['line'] or x.category != old['category']
                or x.reference_key != old['key'] or x.reference_label != old['label'] or x.source_code != old['code']
                or x.debit != Decimal(old['credit']) or x.credit != Decimal(old['debit'])
                or x.source_reference != str(request.public_id)
                or x.source_snapshot != {'original_subsidiary': old['id'], 'original_snapshot': old['snapshot'], KEY: data}):
            raise ValidationError('The corrected officer/payable subsidiary differs from the original evidence.')
    return request


def corrected_request_ids(case):
    result = set()
    for request in case.posting_requests.filter(status=Request.POSTED, payload__has_key=KEY):
        entry = posted_request(request)
        validate(entry)
        result.update((str(request.public_id), request.payload[KEY]['original_request']))
    return result


def correction_window(case):
    """Read-only proof for an issued-DV exception; callers retain their normal locks."""
    if case.current_stage not in (VoucherCase.PAYABLE_PREPARATION, VoucherCase.PAYABLE_REVIEW, VoucherCase.ACCOUNTING_PREPARATION):
        return False
    if case.payment_instruments.exists():
        return False
    corrected = corrected_request_ids(case)
    originals = list(case.posting_requests.filter(kind=Request.RECOGNITION, status=Request.POSTED))
    return bool(originals) and all(str(x.public_id) in corrected for x in originals)


def check_replacement_date(case, day):
    corrections = list(case.posting_requests.filter(status=Request.POSTED, payload__has_key=KEY))
    if corrections:
        corrected_request_ids(case)
        if day < max(x.jev_date for x in corrections):
            raise ValidationError('The corrected DV and recognition cannot predate the original advance correction.')


def replacement_evidence(case):
    request = case.posting_requests.filter(status=Request.POSTED, payload__has_key=KEY).order_by('-pk').first()
    if request is None:
        return {}
    corrected_request_ids(case)
    return {'advance_replacement': {'correction_request':str(request.public_id),
        'correction_entry':str(request.accounting_entry_public_id), 'correction_checksum':request.payload_checksum,
        'original_request':request.payload[KEY]['original_request']}}


@transaction.atomic
def prepare(*, detail, actor, day, reason, key):
    from .advance_sources import original as read_original
    from .services import _advance, _consume_sequence_number
    owner = department_for_user(actor)
    if not can_prepare_journals(actor) or owner is None or detail.entry.department_id != owner.pk:
        raise PermissionDenied
    original = Request.objects.filter(public_id=detail.source_reference, kind=Request.RECOGNITION).first()
    if original is None:
        raise ValidationError('Select the original governed advance recognition debit.')
    case = VoucherCase.objects.select_for_update().get(pk=original.case_id)
    existing = case.posting_requests.filter(trigger_key=f'advance-recognition-fix:{key}').first()
    if existing:
        if (_digest(existing.payload) != existing.payload_checksum or existing.status == Request.CANCELLED
                or existing.jev_date != day or existing.payload[KEY]['reason'] != str(reason).strip()
                or existing.payload[KEY]['original_request'] != str(original.public_id)
                or existing.requested_by_id != actor.pk):
            raise ValidationError('This request identity belongs to another retained advance correction.')
        return existing
    if not str(key).strip() or len(str(key)) > 100 or not str(reason).strip():
        raise ValidationError('Retain the correction reason and request identity.')
    if case.current_stage != VoucherCase.TREASURY_CHECK_PREPARATION:
        raise ValidationError('Correct an original unpaid advance before check preparation proceeds.')
    unpaid(case)
    detail, original, payable = read_original(detail)
    source = detail.entry
    if not source.entry_date <= day <= timezone.localdate():
        raise ValidationError('Use the actual correction date on or after original recognition.')
    if JournalLine.objects.filter(payable_origin_id=payable.pk).exclude(entry__status=JournalEntry.VOIDED).exists():
        raise ValidationError('Resolve linked payable applications before correcting the original advance.')
    from accounting.models import PayableClaimReservation
    if PayableClaimReservation.objects.filter(source_id=payable.pk, released_at__isnull=True).exists():
        raise ValidationError('Resolve linked payable reservations before correcting the original advance.')
    data = {'original_request': str(original.public_id), 'original_entry': str(source.public_id),
            'original_checksum': original.payload_checksum, 'original_rule_checksum': original.posting_rule_checksum,
            'original_detail': detail.pk, 'lines': rows(source), 'subsidiaries': subsidiaries(source),
            'reason': str(reason).strip(), 'prepared_by': actor.pk}
    version = (case.posting_requests.filter(kind=Request.REVERSAL).aggregate(v=Max('version'))['v'] or 0) + 1
    number = _consume_sequence_number(case, actor, 'journal-entry', f'advance-recognition-correction-{version}')
    request = Request(case=case, kind=Request.REVERSAL, version=version, jev_number=number, jev_date=day,
        origin_stage=case.current_stage, resume_stage=VoucherCase.ACCOUNTING_PREPARATION,
        trigger_key=f'advance-recognition-fix:{key}', finance_department_id=owner.pk,
        finance_department_label=owner.name, payload={KEY:data}, payload_checksum=_digest({KEY:data}), requested_by=actor)
    request.full_clean(); request.save()
    _advance(case, actor, VoucherCase.ACCOUNTING_EVENT_POSTING, 'advance_recognition_correction_requested',
        f'advance-recognition-fix:{request.public_id}', data['reason'], {'posting_request':str(request.public_id)})
    return request


@transaction.atomic
def materialize(request, actor):
    owner = department_for_user(actor)
    if not can_prepare_journals(actor) or owner is None or owner.pk != request.finance_department_id:
        raise PermissionDenied
    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = Request.objects.select_for_update().get(pk=request.pk)
    if request.status == Request.CANCELLED or _digest(request.payload) != request.payload_checksum:
        raise ValidationError('Retain an active unchanged original advance correction request.')
    unpaid(case, exclude=request.pk)
    data = request.payload[KEY]
    original = Request.objects.get(case=case, public_id=data['original_request'])
    source = posted_request(original, allow_reversal_reference=request.public_id)
    with transaction.atomic(using='finance'):
        Fund.objects.select_for_update().get(pk=source.fund_id)
        source = JournalEntry.objects.select_for_update().get(pk=source.pk)
        list(source.lines.select_for_update().order_by('pk'))
        retained = list(JournalEntry.objects.filter(source_type='voucher', source_reference=str(request.public_id)))
        if retained:
            if len(retained) != 1 or retained[0].status == JournalEntry.VOIDED:
                raise ValidationError('Withdraw the discarded correction before preparing a fresh request.')
            entry, created = retained[0], False
        else:
            period = AccountingPeriod.objects.get(department_id=owner.pk, status=AccountingPeriod.OPEN,
                starts_on__lte=request.jev_date, ends_on__gte=request.jev_date)
            entry = JournalEntry(department_id=owner.pk, department_label=owner.name, reference=request.jev_number,
                entry_date=request.jev_date, period=period, fund=source.fund, source_type='voucher',
                source_reference=str(request.public_id), reversal_of=source, reversal_reason=data['reason'],
                description=f'Correct original advance {source.reference}: {data["reason"]}',
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username,
                source_snapshot={'voucher_case':str(case.public_id), 'payload_checksum':request.payload_checksum,
                                 'posting_rule_checksum':'', KEY:data})
            entry.full_clean(); entry.save()
            for old in source.lines.order_by('sequence', 'pk'):
                line = JournalLine(entry=entry, sequence=old.sequence, account=old.account,
                    responsibility_center=old.responsibility_center, debit=old.credit, credit=old.debit,
                    cash_flow_category=old.cash_flow_category, memo=old.memo)
                line.full_clean(); line.save()
            for old in data['subsidiaries']:
                row = JournalSubsidiaryLine(entry=entry, journal_line=entry.lines.get(sequence=old['line']),
                    category=old['category'], reference_key=old['key'], reference_label=old['label'], source_code=old['code'],
                    source_reference=str(request.public_id), debit=Decimal(old['credit']), credit=Decimal(old['debit']),
                    source_snapshot={'original_subsidiary':old['id'], 'original_snapshot':deepcopy(old['snapshot']), KEY:data})
                row.full_clean(); row.save()
            from accounting.services import record_event
            record_event(source, 'reversal_prepared', actor, reason=data['reason'],
                snapshot={'reversal_entry':str(entry.public_id), 'correction_request':str(request.public_id)})
            record_event(entry, 'prepared_from_reversal', actor, reason=data['reason'],
                snapshot={'original_entry':str(source.public_id), 'correction_request':str(request.public_id)})
            created = True
        validate(entry)
    if request.status != Request.POSTED:
        request.status, request.accounting_entry_public_id, request.materialized_at = Request.MATERIALIZED, entry.public_id, timezone.now()
        request.save()
    return entry, created


@transaction.atomic
def reconcile(entry, actor):
    from .services import _apply_case_return
    entry = require_persisted_posting(entry, actor, source_type='voucher')
    request = Request.objects.get(public_id=entry.source_reference)
    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = validate(entry)
    if request.status == Request.POSTED:
        return request
    unpaid(case, exclude=request.pk)
    request.status, request.accounting_entry_public_id, request.posted_at = Request.POSTED, entry.public_id, entry.posted_at
    request.save()
    _apply_case_return(case, actor, VoucherCase.ACCOUNTING_PREPARATION, request.payload[KEY]['reason'],
                       f'advance-recognition-corrected:{request.public_id}')
    if hasattr(case, 'payable_intake'):
        _apply_case_return(case, actor, VoucherCase.PAYABLE_PREPARATION, request.payload[KEY]['reason'],
                           f'advance-recognition-payable:{request.public_id}')
    return request


@transaction.atomic
def withdraw(request, actor, reason):
    from .services import _advance
    owner = department_for_user(actor)
    if not can_post_journals(actor) or owner is None or owner.pk != request.finance_department_id:
        raise PermissionDenied
    case = VoucherCase.objects.select_for_update().get(pk=request.case_id)
    request = Request.objects.select_for_update().get(pk=request.pk)
    if KEY not in request.payload or actor.pk == request.requested_by_id or not str(reason).strip():
        raise ValidationError('An independent Accounting reviewer must retain the withdrawal reason.')
    if request.status == Request.CANCELLED:
        return request
    if request.status == Request.POSTED or JournalEntry.objects.filter(source_type='voucher',
            source_reference=str(request.public_id)).exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError('Discard every unposted correction draft before withdrawing; posted corrections remain retained.')
    request.status, request.failure_reason = Request.CANCELLED, str(reason).strip()
    request.save()
    _advance(case, actor, VoucherCase.TREASURY_CHECK_PREPARATION, 'advance_recognition_correction_withdrawn',
             f'advance-recognition-withdraw:{request.public_id}', str(reason).strip(), {'posting_request':str(request.public_id)})
    return request
