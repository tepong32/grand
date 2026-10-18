"""Append-only statements about closed work; never change its effective facts."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum

from . import maintenance
from .disposal_evidence import prepare_uploads
from .models import Asset, AssetMaintenanceCase, MaintenanceCorrectionNotice as Notice
from .property_determinations import checksum
from .private_evidence import open_checked_private_evidence

CASE_FIELDS = ('status', 'state_version', 'prior_asset_status', 'reported_date', 'problem', 'provider',
               'work_performed', 'documented_cost', 'cost_reference', 'finished_date',
               'resulting_asset_status', 'closure_note', 'opened_by_id', 'closed_by_id', 'closed_at')


def case_basis(case):
    """Observe the closed record/history metadata, not certification of source bytes."""
    if case.status not in (case.COMPLETED, case.CANCELLED) or not case.closed_at or not case.closed_by_id:
        raise ValidationError('Close the work record before adding a correction notice.')
    events = list(case.events.all())
    if len(events) != case.state_version or not events or events[-1].action != case.status:
        raise ValidationError('The closed history is incomplete. Investigate or restore it before continuing.')
    for version, entry in enumerate(events, 1):
        if (not isinstance(entry.snapshot, dict) or entry.snapshot.get('state_version') != str(version)
                or entry.snapshot.get('public_id') != str(case.public_id)
                or entry.snapshot.get('asset_public_id') != str(case.asset.public_id)):
            raise ValidationError('The retained history no longer matches this work record.')
    last = events[-1].snapshot
    for field in CASE_FIELDS:
        raw = getattr(case, field)
        if field == 'documented_cost':
            try:
                matches = (last.get(field) is None and raw is None) or (
                    raw is not None and Decimal(last.get(field)) == raw)
            except (TypeError, ValueError, InvalidOperation):
                matches = False
        else:
            matches = last.get(field) == (str(raw) if raw is not None else None)
        if not matches:
            raise ValidationError('The closed record differs from its retained outcome. Investigate before continuing.')
    evidence = list(case.evidence.values('id', 'sha256', 'size', 'note', 'original_filename'))
    if evidence != last.get('evidence'):
        raise ValidationError('The closed document metadata changed. Investigate before continuing.')
    return {'case_uuid': str(case.public_id), 'asset_uuid': str(case.asset.public_id),
            'state_version': case.state_version, 'status': case.status, 'evidence': evidence, 'closed_record': last,
            'events': [{'id': entry.pk, 'actor': entry.actor_id, 'action': entry.action,
                        'time': entry.occurred_at.isoformat(), 'checksum': checksum(entry.snapshot)} for entry in events]}


def payload(row):
    return dict(public_id=str(row.public_id), case_id=row.case_id, recorded_by_id=row.recorded_by_id,
        recorded_at=row.recorded_at.isoformat(), explanation=row.explanation, source_reference=row.source_reference,
        source_snapshot=row.source_snapshot, file=row.file.name or '', original_filename=row.original_filename,
        sha256=row.sha256, size=row.size)


def verify_notice(row):
    if not row.checksum or row.checksum != checksum(payload(row)):
        raise ValidationError('This correction notice failed its record-integrity check. Investigate or restore it.')


@transaction.atomic
def record_notice(*, actor, case, request_id, expected_source, explanation, source_reference, upload=None):
    located = AssetMaintenanceCase.objects.only('asset_id').get(pk=case.pk)
    asset = Asset.objects.select_for_update().get(pk=located.asset_id)
    maintenance._require(actor, asset)
    case = AssetMaintenanceCase.objects.select_for_update().get(pk=case.pk, asset=asset)
    case.asset = asset
    basis = case_basis(case)
    if checksum(basis) != expected_source:
        raise ValidationError('The source record changed. Reopen the notice form before continuing.')
    try:
        identity = UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError('The notice request is invalid. Reopen the form.') from error
    if not isinstance(explanation, str) or not isinstance(source_reference, str):
        raise ValidationError('Use text for the correction statement and source reference.')
    explanation, source_reference = explanation.strip(), source_reference.strip()
    if not explanation or not source_reference:
        raise ValidationError('Explain what needs correction and identify your basis or reference.')
    if len(explanation) > 4000 or len(source_reference) > 240:
        raise ValidationError('Keep the statement within 4,000 characters and the reference within 240 characters.')
    prepared = prepare_uploads([('notice', [upload])])[0] if upload else None
    digest, size = (prepared[2], prepared[3]) if prepared else ('', 0)
    original_name = Path(upload.name).name if upload else ''
    previous = Notice.objects.filter(public_id=identity).first()
    if previous:
        if (previous.case_id != case.pk or previous.recorded_by_id != actor.pk or
            previous.explanation != explanation or previous.source_reference != source_reference or
            previous.sha256 != digest or previous.size != size or previous.original_filename != original_name or
            previous.source_snapshot != basis):
            raise ValidationError('This request already belongs to different notice content. Reopen the form.')
        verify_notice(previous)
        if previous.file:
            try:
                with open_checked_private_evidence(previous, namespace=f'inventory/maintenance_notices/{case.public_id}'):
                    pass
            except (OSError, ValueError) as error:
                raise ValidationError('The retained notice file is unavailable. Investigate or restore it before retrying.') from error
        return previous
    if upload:
        notices = case.correction_notices
        corrections = case.reviewed_corrections
        if case.evidence.count() + notices.exclude(file='').count() + corrections.count() >= 20:
            raise ValidationError('This case already retains 20 documents. You can record a reference-only notice; arrange evidence storage review separately.')
        total = ((case.evidence.aggregate(total=Sum('size'))['total'] or 0)
            + (notices.aggregate(total=Sum('size'))['total'] or 0)
            + (corrections.aggregate(total=Sum('size'))['total'] or 0))
        if total + size > 100 * 1024 * 1024:
            raise ValidationError('Case documents cannot exceed 100 MB. Record a reference-only notice or arrange storage review.')
    row = Notice(public_id=identity, case=case, recorded_by=actor, explanation=explanation,
        source_reference=source_reference, source_snapshot=basis, file=upload or '',
        original_filename=original_name, sha256=digest, size=size)
    row.checksum = checksum(payload(row))
    row.full_clean(validate_unique=False)
    if upload:
        row.file.save(original_name, upload, save=False)
        row.checksum = checksum(payload(row))
    try:
        with transaction.atomic():
            row.save(force_insert=True)
    except IntegrityError as error:
        raise ValidationError('This notice request was already used. Reload the work record before retrying.') from error
    return row
