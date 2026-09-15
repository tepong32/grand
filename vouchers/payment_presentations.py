"""Record external presentation evidence without manufacturing a financial action."""
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .access import department_for_user, has_explicit_permission
from .models import PaymentInstrument, PaymentPresentationReport as Report, PaymentPresentationDecision as Decision, VoucherCase
from .roles import is_finance_uat_viewer
from .remittances import _digest


def can_act(user, permission):
    return not is_finance_uat_viewer(user) and has_explicit_permission(user, 'vouchers.' + permission)


def visible_reports(user):
    query = Report.objects.select_related('instrument__case', 'reported_by').prefetch_related('decisions__reviewed_by')
    if not has_explicit_permission(user, 'vouchers.view_bank_advice'):
        return query.none()
    department = department_for_user(user)
    return query.filter(Q(treasury_department=department) | Q(accounting_department=department))


def identity(instrument):
    return {'instrument': str(instrument.public_id), 'case': str(instrument.case.public_id),
            'bank': instrument.bank_account_code, 'fund': instrument.fund_code,
            'number': instrument.check_number, 'amount': str(instrument.amount),
            'issued_at': instrument.issued_at.isoformat() if instrument.issued_at else None}


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValidationError('Supply evidence and reasons of at most 4,000 characters.')
    return value.strip()


def _day(day, start):
    if type(day) is not date or not start <= day <= timezone.localdate():
        raise ValidationError('Use an actual date on or after the original event, no later than today.')


def verify(report):
    if report.checksum != _digest(report.snapshot) or report.snapshot.get('instrument') != identity(report.instrument):
        raise ValidationError('The original presentation evidence no longer matches the instrument.')
    expected = {'observed_on': report.observed_on.isoformat(), 'reason': report.reason,
                'evidence': report.evidence_reference, 'reporter': report.reported_by_id,
                'treasury': report.treasury_department_id, 'accounting': report.accounting_department_id}
    if any(report.snapshot.get(k) != v for k, v in expected.items()):
        raise ValidationError('The presentation report evidence has changed.')
    previous = report.checksum
    events = list(report.decisions.all())
    if report.state_version != len(events) + 1 or report.is_open != (not events or events[-1].outcome not in Decision.CLOSED_OUTCOMES):
        raise ValidationError('Presentation decision sequence or closure evidence is incomplete.')
    for sequence, event in enumerate(events, 1):
        if event.version != sequence:
            raise ValidationError('Presentation decisions must retain their complete sequence.')
        expected_event = {'report': str(report.public_id), 'version': event.version, 'outcome': event.outcome,
                          'date': event.effective_on.isoformat(), 'evidence': event.evidence_reference,
                          'reason': event.reason, 'next_action': event.next_action, 'reviewer': event.reviewed_by_id,
                          'previous': previous}
        if event.outcome in (Decision.PAID_RECONCILED, Decision.RETURN_LINKED):
            resolution = event.snapshot.get('resolution')
            if not isinstance(resolution, dict) or not resolution.get('request') or not resolution.get('payload_checksum'):
                raise ValidationError('Retain the completed financial source used to resolve the finding.')
            expected_event['resolution'] = resolution
        if event.snapshot != expected_event or event.checksum != _digest(expected_event):
            raise ValidationError('Presentation decision evidence has changed.')
        previous = event.checksum


@transaction.atomic
def capture(*, instrument, actor, observed_on, reason, evidence_reference):
    if not can_act(actor, 'record_payment_presentations'):
        raise PermissionDenied
    case = VoucherCase.objects.select_for_update().select_related('configuration_release').get(pk=instrument.case_id)
    instrument = PaymentInstrument.objects.select_for_update().get(pk=instrument.pk, case=case)
    if not instrument.issued_at or not case.configuration_release_id:
        raise ValidationError('Choose an issued cheque with retained Finance ownership.')
    issuance = case.events.filter(action__in=('check_issued', 'replacement_check_issued'),
                                 metadata__instrument_id=str(instrument.public_id)).first()
    if not issuance or issuance.actor_department_id != department_for_user(actor).pk:
        raise PermissionDenied('Only the original issuing Treasury office may record this report.')
    _day(observed_on, timezone.localdate(instrument.issued_at))
    reason, evidence_reference = _text(reason), _text(evidence_reference)
    if instrument.presentation_reports.filter(is_open=True).exists():
        raise ValidationError('This cheque already has an open presentation report.')
    snapshot = {'instrument': identity(instrument), 'observed_on': observed_on.isoformat(), 'reason': reason,
                'evidence': evidence_reference, 'reporter': actor.pk, 'treasury': issuance.actor_department_id,
                'accounting': case.configuration_release.department_id,
                'advice_id': str(instrument.current_advice_batch.public_id) if instrument.current_advice_batch_id else None,
                'advice_checksum': instrument.current_advice_batch.snapshot_checksum if instrument.current_advice_batch_id else None,
                'advice_status': instrument.current_advice_batch.status if instrument.current_advice_batch_id else None}
    return Report.objects.create(instrument=instrument, treasury_department_id=issuance.actor_department_id,
        accounting_department_id=case.configuration_release.department_id, observed_on=observed_on,
        reason=reason, evidence_reference=evidence_reference, snapshot=snapshot, checksum=_digest(snapshot), reported_by=actor)


@transaction.atomic
def decide(*, report, actor, expected_version, outcome, effective_on, evidence_reference, reason, next_action='', source_reference=''):
    if not can_act(actor, 'review_payment_presentations'):
        raise PermissionDenied
    VoucherCase.objects.select_for_update().get(pk=report.instrument.case_id)
    PaymentInstrument.objects.select_for_update().get(pk=report.instrument_id)
    report = Report.objects.select_for_update().select_related('instrument__case').get(pk=report.pk)
    if report.accounting_department_id != department_for_user(actor).pk or actor.pk == report.reported_by_id:
        raise PermissionDenied('An independent reviewer from the original Accounting office is required.')
    if not report.is_open or report.state_version != expected_version:
        raise ValidationError('Reload the current open report before recording a decision.')
    verify(report)
    if outcome not in dict(Decision.OUTCOMES):
        raise ValidationError('Choose a supported bank disposition.')
    _day(effective_on, timezone.localdate(report.instrument.issued_at))
    evidence_reference, reason = _text(evidence_reference), _text(reason)
    prior = report.decisions.last()
    # Payment/return cannot be undone by a generic dismissal or pending update.
    allowed = {Decision.PAID: (Decision.PAID, Decision.RETURNED, Decision.PAID_RECONCILED, Decision.RETURN_LINKED),
               Decision.RETURNED: (Decision.RETURNED, Decision.RETURN_LINKED)}
    if prior and prior.outcome in allowed and outcome not in allowed[prior.outcome]:
        raise ValidationError('Reconcile verified payment/return through its governed source route; a report cannot undo it.')
    resolution = None
    if outcome in (Decision.PAID_RECONCILED, Decision.RETURN_LINKED):
        if prior is None or prior.outcome not in allowed:
            raise ValidationError('Record the verified bank finding before linking its completed disposition.')
        from .presentation_resolution import evidence
        resolution = evidence(report, actor, outcome, source_reference)
    closing = outcome in Decision.CLOSED_OUTCOMES
    next_action = '' if closing else _text(next_action)
    snapshot = {'report': str(report.public_id), 'version': report.state_version, 'outcome': outcome,
                'date': effective_on.isoformat(), 'evidence': evidence_reference, 'reason': reason,
                'next_action': next_action, 'reviewer': actor.pk, 'previous': prior.checksum if prior else report.checksum}
    if resolution is not None:
        snapshot['resolution'] = resolution
    event = Decision.objects.create(report=report, version=report.state_version, outcome=outcome,
        effective_on=effective_on, evidence_reference=evidence_reference, reason=reason, next_action=next_action,
        snapshot=snapshot, checksum=_digest(snapshot), reviewed_by=actor)
    report.state_version += 1
    report.is_open = not closing
    report.save(update_fields=('state_version', 'is_open'))
    return event


def protect_instrument(instrument):
    """Caller holds the default case and instrument locks before financial mutation."""
    for report in instrument.presentation_reports.filter(is_open=True).select_related('instrument__case'):
        verify(report)
        if report.decisions.filter(outcome__in=(Decision.PAID, Decision.RETURNED)).exists():
            raise ValidationError('Verified bank payment/return requires Accounting reconciliation before another instrument action.')


def protect_case(case):
    # A late finding on a predecessor must also protect an already-issued replacement.
    for instrument in case.payment_instruments.all():
        protect_instrument(instrument)


@transaction.atomic
def export_evidence(report):
    VoucherCase.objects.select_for_update().get(pk=report.instrument.case_id)
    report = Report.objects.select_related('instrument__case').prefetch_related('decisions').get(pk=report.pk)
    verify(report)
    return {'report': str(report.public_id), 'source': report.snapshot, 'checksum': report.checksum,
        'recorded_at': report.reported_at.isoformat(), 'open': report.is_open, 'version': report.state_version,
        'decisions': [{'snapshot': event.snapshot, 'checksum': event.checksum,
                       'recorded_at': event.reviewed_at.isoformat()} for event in report.decisions.all()]}
