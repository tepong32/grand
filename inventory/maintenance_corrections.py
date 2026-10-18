"""Independently reviewed documentary successors; never mutate original work."""
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Sum
from django.utils import timezone

from . import maintenance, maintenance_notices
from .access import has_inventory_permission
from .disposal_evidence import prepare_uploads
from .maintenance_correction_forms import CorrectionValuesForm
from .maintenance_views import can_view_maintenance
from .models import Asset, AssetMaintenanceCase, MaintenanceCorrection as Correction, MaintenanceCorrectionEvent as Event
from .private_evidence import open_checked_private_evidence
from .property_determinations import checksum, value

FIELDS = tuple(CorrectionValuesForm.base_fields)


def can_review(actor, asset):
    return (can_view_maintenance(actor) and maintenance.asset_in_scope(actor, asset)
            and has_inventory_permission(actor, 'review_maintenance_correction', mutation=True))


def content(row):
    return dict(public_id=str(row.public_id), case_id=row.case_id, revision=row.revision,
        predecessor_id=row.predecessor_id, proposed_by_id=row.proposed_by_id,
        proposed_at=row.proposed_at.isoformat(), source_snapshot=row.source_snapshot,
        corrected_values=row.corrected_values, reason=row.reason, source_reference=row.source_reference,
        file=row.file.name, original_filename=row.original_filename, sha256=row.sha256, size=row.size)


def event_snapshot(row, event):
    return dict(correction=str(row.public_id), version=event.version, action=event.action,
        actor=event.actor_id, time=event.occurred_at.isoformat(), note=event.note, content_checksum=row.content_checksum)


def verify(row, *, files=True):
    if not row.content_checksum or row.content_checksum != checksum(content(row)):
        raise ValidationError('The correction content failed verification. Investigate or restore it.')
    events = list(row.events.all())
    expected = 1 if row.status == 'proposed' else 2 if row.status in ('approved', 'rejected') else 0
    if not expected or row.state_version != expected or len(events) != expected:
        raise ValidationError('The correction decision history is incomplete.')
    for version, event in enumerate(events, 1):
        if (event.version != version or event.action != ('proposed' if version == 1 else row.status)
                or event.snapshot != event_snapshot(row, event) or event.checksum != checksum(event.snapshot)
                or (version == 1 and event.actor_id != row.proposed_by_id)
                or (version == 2 and event.actor_id == row.proposed_by_id)):
            raise ValidationError('The retained independent decision no longer matches this correction.')
    if files:
        try:
            with open_checked_private_evidence(row, namespace=f'inventory/maintenance_corrections/{row.case.public_id}'):
                pass
        except (OSError, ValueError) as error:
            raise ValidationError('The retained correction evidence is unavailable.') from error


def _reference(row):
    if row is None:
        return None
    return {'id': row.pk, 'public_id': str(row.public_id), 'content_checksum': row.content_checksum,
            'decision_checksum': list(row.events.all())[-1].checksum}


def basis(case):
    original = {'record': maintenance_notices.case_basis(case), 'owner_id': case.asset.department_id}
    try:
        for evidence in case.evidence.all():
            with open_checked_private_evidence(evidence, namespace=f'inventory/maintenance/{case.public_id}'):
                pass
    except (OSError, ValueError) as error:
        raise ValidationError('The original work evidence is unavailable. Investigate or restore it.') from error
    head = None
    # Inspect every decision chain before selecting approved successors. Filtering
    # first would let a changed status hide an earlier approval and restore old facts.
    for row in case.reviewed_corrections.select_related('case').prefetch_related('events'):
        verify(row, files=row.status == 'approved')
        if row.status != 'approved':
            continue
        if row.source_snapshot != {'original': original, 'approved': _reference(head)} or row.predecessor_id != (head.pk if head else None):
            raise ValidationError('The approved correction lineage differs from its original sources.')
        head = row
    return {'original': original, 'approved': _reference(head)}, head


def clean_values(case, data):
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        raise ValidationError('Supply the complete documented work fields; custody and status changes are not corrections.')
    if any(isinstance(raw, (float, bool)) for raw in data.values()):
        raise ValidationError('Use exact documented values, not approximate amounts.')
    form = CorrectionValuesForm(data)
    if not form.is_valid():
        raise ValidationError([f'{name}: {message}' for name, messages in form.errors.items() for message in messages])
    values = form.cleaned_data
    if not values['reported_date'] <= values['finished_date'] <= timezone.localdate():
        raise ValidationError('The documented finish date must be between the report date and today.')
    if case.status == case.COMPLETED and not values['work_performed']:
        raise ValidationError('Describe the documented work for a completed case.')
    if values['documented_cost'] and not values['cost_reference']:
        raise ValidationError('Enter Cost reference (the invoice or cost document) for this positive cost.')
    return {name: value(raw) for name, raw in values.items()}


def _locked_case(case, actor, *, review=False):
    located = AssetMaintenanceCase.objects.only('asset_id').get(pk=case.pk)
    asset = Asset.objects.select_for_update().get(pk=located.asset_id)
    if review:
        if not can_review(actor, asset):
            raise PermissionDenied
    else:
        maintenance._require(actor, asset)
    case = AssetMaintenanceCase.objects.select_for_update().get(pk=case.pk, asset=asset)
    case.asset = asset
    return case


def _text(raw, name, maximum):
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > maximum:
        raise ValidationError(f'{name} must contain 1 to {maximum} characters.')
    return raw.strip()


def _event(row, actor, note):
    event = Event(correction=row, actor=actor, version=row.state_version, action=row.status, note=note)
    event.snapshot = event_snapshot(row, event)
    event.checksum = checksum(event.snapshot)
    event.full_clean()
    event.save(force_insert=True)


@transaction.atomic
def propose(*, actor, case, request_id, expected_source, data, reason, source_reference, upload):
    case = _locked_case(case, actor)
    values = clean_values(case, data)
    reason, source_reference = _text(reason, 'Reason', 4000), _text(source_reference, 'Source reference', 240)
    try:
        identity = UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Reopen the correction form to obtain a valid request.') from error
    if upload is None:
        raise ValidationError('Retain the document supporting this correction.')
    prepared = prepare_uploads([('correction', [upload])])[0]
    digest, size, original_name = prepared[2], prepared[3], Path(upload.name).name
    previous = Correction.objects.filter(public_id=identity).select_related('case').first()
    if previous:
        if (previous.case_id != case.pk or previous.proposed_by_id != actor.pk
                or previous.corrected_values != values or previous.reason != reason
                or previous.source_reference != source_reference or previous.sha256 != digest
                or previous.size != size or previous.original_filename != original_name
                or checksum(previous.source_snapshot) != expected_source):
            raise ValidationError('This request already belongs to different correction content.')
        verify(previous)
        return previous
    source, head = basis(case)
    if checksum(source) != expected_source:
        raise ValidationError('The original record or approved correction changed. Reopen the form.')
    current = head.corrected_values if head else clean_values(case, {name: getattr(case, name) for name in FIELDS})
    if values == current:
        raise ValidationError('No documented field changed. Use a correction notice for an additional statement.')
    groups = (case.evidence, case.correction_notices.exclude(file=''), case.reviewed_corrections)
    if sum(rows.count() for rows in groups) >= 20:
        raise ValidationError('This work record already retains 20 documents. Arrange evidence storage review.')
    if sum(rows.aggregate(total=Sum('size'))['total'] or 0 for rows in groups) + size > 100 * 1024 * 1024:
        raise ValidationError('Case documents cannot exceed 100 MB.')
    revision = (case.reviewed_corrections.aggregate(last=Max('revision'))['last'] or 0) + 1
    row = Correction(public_id=identity, case=case, revision=revision, predecessor=head, proposed_by=actor,
        source_snapshot=source, corrected_values=values, reason=reason, source_reference=source_reference,
        file=upload, original_filename=original_name, sha256=digest, size=size)
    row.content_checksum = checksum(content(row))
    row.full_clean(validate_unique=False)
    row.file.save(original_name, upload, save=False)
    row.content_checksum = checksum(content(row))
    try:
        with transaction.atomic():
            row.save(force_insert=True)
            _event(row, actor, reason)
    except IntegrityError as error:
        raise ValidationError('This request was already used. Reload the work record before retrying.') from error
    return row


@transaction.atomic
def decide(*, actor, row, expected_version, action, note):
    case = _locked_case(row.case, actor, review=True)
    row = Correction.objects.select_for_update().select_related('case').get(pk=row.pk, case=case)
    note = _text(note, 'Independent findings', 4000)
    verify(row, files=action == 'approved')
    if actor.pk == row.proposed_by_id:
        raise ValidationError('A different authorized person must review this correction.')
    if type(expected_version) is not int or expected_version != row.state_version or row.status != 'proposed':
        raise ValidationError('This proposal changed or was already decided. Reload it before reviewing.')
    if action not in ('approved', 'rejected'):
        raise ValidationError('Choose approval or rejection.')
    if action == 'approved':
        source, head = basis(case)
        if row.source_snapshot != source or row.predecessor_id != (head.pk if head else None):
            raise ValidationError('An original source or approved predecessor changed. Propose a fresh correction.')
    row.status, row.state_version = action, row.state_version + 1
    row.save(update_fields=('status', 'state_version'))
    _event(row, actor, note)
    return row
