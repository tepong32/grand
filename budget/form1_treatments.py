"""Source-bound interpretation history, separate from numeric presentation approval."""
from copy import deepcopy
from hashlib import sha256
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting.models import Fund
from accounting.summary_actuals import document, text
from .access import department_for_user, has_budget_permission
from .models import (BudgetVersion, Form1Package, Form1TreatmentProposal as Proposal,
    Form1TreatmentAttachment as Attachment, Form1TreatmentDecision as Decision)
from . import form1_packages as packages, form1_package_reviews as reviews, form1_philhealth as ph
from .services import record_event

FIELDS = {'part', 'finding', 'basis', 'funding_reference', 'lineage_reference'}
CHECKS = {
    'budget': ('entity_period_scope', 'whole_source_coverage', 'funding_authority'),
    'accounting': ('signed_source_lineage', 'counterpart_identity', 'shared_source_capacity'),
    'treasury': ('restriction_identity', 'fund_transfer_route', 'cash_timing'),
}
RELATED = ('package__proposal__fiscal_year', 'package__fund', 'package__spa_review', 'predecessor')


def draft(original, findings, documents):
    """Pure factual proposal. No finding, including confirmation, supplies an offset."""
    try:
        body = ph.verify(original)
        parts = {row['key']: row for row in body['parts']}
        if not isinstance(findings, list) or set(documents) != {'authority', 'reconciliation'}:
            raise ValidationError('Retain the complete original-part findings and both document declarations.')
        for metadata in documents.values():
            if (not isinstance(metadata, dict) or set(metadata) != {'name', 'sha256'}
                or not isinstance(metadata['sha256'], str) or len(metadata['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in metadata['sha256'])):
                raise ValidationError('Retain original treatment authority and reconciliation document hashes.')
            text(metadata['name'], 'original treatment filename', 180)
        selected = []
        seen = set()
        for row in findings:
            if not isinstance(row, dict) or set(row) != FIELDS:
                raise ValidationError('Use exact original-part finding fields; amounts are not editable.')
            part = parts.get(row['part'])
            if part is None or row['part'] in seen:
                raise ValidationError('Select every original signed part exactly once.')
            kind = part['original_source']['kind']
            choices = (('reject_overlap', 'confirm_overlap', 'unresolved')
                if kind == 'receipt' and part['treatment'] == 'claimed_overlap'
                else ('deduct', 'unresolved') if kind == 'receipt'
                else ph.TREATMENTS[kind])
            if row['finding'] not in choices:
                raise ValidationError('A finding must address the original part kind and original claim.')
            item = {name: text(row[name], 'explicit treatment '+name, 2000)
                for name in ('basis', 'funding_reference', 'lineage_reference')}
            item.update(part=part['key'], finding=row['finding'], original_part=deepcopy(part))
            selected.append(item)
            seen.add(part['key'])
        if seen != set(parts):
            raise ValidationError('Retain findings over every original entity, column and signed part.')
        selected.sort(key=lambda row: row['part'])
        complete = (all(row['finding'] != 'unresolved' for row in selected)
            and all(row['coverage'] == 'complete' for row in body['coverage']))
        result = dict(schema=1, kind='form1_treatment_factual_proposal', original=deepcopy(original),
            findings=selected, documents=deepcopy(documents), factual_coverage_complete=complete,
            presentation_recipe=None, numeric_adjustment_approved=False, form_issued=False, cash_available=False)
        return dict(payload=result, checksum=checksum(result))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Retain the exact original PhilHealth interpretation evidence.') from error


def verify_draft(envelope):
    try:
        body = envelope['payload']
        inputs = [{name: row[name] for name in FIELDS} for row in body['findings']]
        if checksum(body) != envelope['checksum'] or draft(body['original'], inputs, body['documents']) != envelope:
            raise ValidationError('Treatment findings must reproduce every original source and signed amount.')
        return deepcopy(body)
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError('Invalid retained treatment proposal.') from error


def _identity(record):
    return dict(public_id=str(record.public_id), package_id=record.package_id, version=record.version,
        predecessor_id=record.predecessor_id, department_id=record.department_id,
        department_label=record.department_label,
        prepared_by_id=record.prepared_by_id, prepared_at=record.prepared_at.isoformat())


def verify(record, *, original_attachments=None, attachments=None):
    try:
        original = packages.verify(record.package, original_attachments)['philhealth_source']
        body = record.payload
        if (set(body) != {'schema', 'identity', 'package_checksum', 'predecessor', 'draft', 'reference'}
            or type(body['schema']) is not int or body['schema'] != 1
            or checksum(body['identity']) != checksum(_identity(record))
            or body['package_checksum'] != record.package.payload_checksum
            or checksum(body) != record.payload_checksum or record.department_id != record.package.department_id
            or record.department_label != record.package.department_label
            or type(record.version) is not int or record.version < 1
            or type(record.prepared_by_id) is not int or record.prepared_by_id <= 0
            or timezone.is_naive(record.prepared_at) or record.prepared_at < record.package.prepared_at):
            raise ValidationError('Retain the original package, maker, version and treatment identity.')
        predecessor = record.predecessor
        if record.version == 1:
            if predecessor is not None or body['predecessor'] is not None:
                raise ValidationError('The first treatment proposal has no predecessor.')
        elif (predecessor is None or predecessor.package_id != record.package_id
            or predecessor.version != record.version-1 or predecessor.prepared_at > record.prepared_at
            or checksum(predecessor.payload) != predecessor.payload_checksum
            or body['predecessor'] != dict(public_id=str(predecessor.public_id), checksum=predecessor.payload_checksum)):
            raise ValidationError('Retain the exact immediate treatment predecessor.')
        proposed = verify_draft(body['draft'])
        if proposed['original'] != original:
            raise ValidationError('A treatment proposal cannot substitute another package inventory.')
        text(body['reference'], 'treatment proposal reference')
        rows = list(record.attachments.all()) if attachments is None else list(attachments)
        if len(rows) != 2 or {row.key for row in rows} != {'authority', 'reconciliation'}:
            raise ValidationError('Retain both original treatment document byte records.')
        for row in rows:
            if row.proposal_id != record.pk or sha256(bytes(row.data)).hexdigest() != proposed['documents'][row.key]['sha256']:
                raise ValidationError('Retain exact original treatment document bytes.')
        return proposed
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained treatment source/version evidence.') from error


def _read(record, actor, *, export=False):
    record = Proposal.objects.select_related(*RELATED).prefetch_related('attachments', 'decisions').get(pk=record.pk)
    record.package = packages._read(record.package, actor, export=export)
    verify(record)
    return record


def _locks(record):
    source = record.package
    proposal = BudgetVersion.objects.select_for_update().get(pk=source.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=source.fund_id)
    package = Form1Package.objects.select_for_update().get(pk=source.pk, proposal=proposal, fund=fund)
    return package


@transaction.atomic(using='finance')
def prepare(package, actor, *, findings, authority, reconciliation, reference, expected_latest):
    owner = department_for_user(actor)
    from vouchers.roles import is_finance_uat_viewer
    if (not owner or not actor.is_active or owner.pk != package.department_id
        or not has_budget_permission(actor, 'prepare_form1_packages') or is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use the designated original Budget treatment preparer.')
    shell = Proposal(package=package)
    package = _locks(shell)
    package = packages._read(package, actor)
    if not packages._current(package, actor):
        raise ValidationError('Prepare treatment findings only against the current original package sources.')
    latest = Proposal.objects.filter(package=package).order_by('-version').first()
    if latest:
        verify(latest)
    if type(expected_latest) is not int or expected_latest != (latest.version if latest else 0):
        raise ValidationError('A newer treatment proposal exists; reload the retained history.')
    data, metadata = {}, {}
    for key, upload in (('authority', authority), ('reconciliation', reconciliation)):
        data[key], metadata[key] = document(upload, 'original treatment '+key)
    original = package.payload['assembly']['payload']['philhealth_source']
    envelope = draft(original, findings, metadata)
    record = Proposal(public_id=uuid.uuid4(), package=package, predecessor=latest,
        version=(latest.version+1 if latest else 1), department_id=package.department_id,
        department_label=package.department_label, prepared_by_id=actor.pk, prepared_at=timezone.now())
    record.payload = dict(schema=1, identity=_identity(record), package_checksum=package.payload_checksum,
        predecessor=dict(public_id=str(latest.public_id), checksum=latest.payload_checksum) if latest else None,
        draft=envelope, reference=text(reference, 'treatment proposal reference'))
    record.payload_checksum = checksum(record.payload)
    record.save()
    for key, content in data.items():
        Attachment.objects.create(proposal=record, key=key, data=content)
    verify(record)
    record_event(package, 'form1_treatment_proposed', actor, reference,
        dict(treatment=str(record.public_id), treatment_checksum=record.payload_checksum))
    return record


def _decision_identity(record, row):
    return dict(public_id=str(row.public_id), proposal=str(record.public_id), checksum=record.payload_checksum,
        role=row.role, actor_id=row.actor_id, actor_department_id=row.actor_department_id,
        approve=row.approve, decided_at=row.decided_at.isoformat())


def _state_checked(record, rows):
    draft_body = verify(record)
    required = reviews.required(record.package, record.package.payload['assembly']['payload'])
    actors, offices = set(), set()
    returned = []
    for row in rows:
        pair = (row.role, row.actor_department_id)
        if (pair not in required or pair in offices or row.actor_id in actors
            or type(row.actor_id) is not int or row.actor_id <= 0
            or type(row.actor_department_id) is not int or row.actor_department_id <= 0
            or row.actor_id in {record.prepared_by_id, record.package.prepared_by_id}
            or row.proposal_id != record.pk or type(row.approve) is not bool
            or timezone.is_naive(row.decided_at) or row.decided_at < record.prepared_at
            or checksum(row.payload) != row.payload_checksum
            or set(row.payload) != {'schema', 'identity', 'checks', 'authority', 'note', 'source_current'}
            or type(row.payload['schema']) is not int or row.payload['schema'] != 1
            or checksum(row.payload['identity']) != checksum(_decision_identity(record, row))
            or row.payload['source_current'] is not (True if row.approve else None)):
            raise ValidationError('Retain independent original office, actor, source and decision evidence.')
        checks = _checks(row.role, row.payload['checks'])
        if row.approve and (not draft_body['factual_coverage_complete'] or not all(c['verified'] for c in checks.values())):
            raise ValidationError('Review requires complete factual coverage and every designated check.')
        text(row.payload['authority'], 'treatment review designation')
        text(row.payload['note'], 'treatment finding decision reason')
        actors.add(row.actor_id)
        offices.add(pair)
        if not row.approve:
            returned.append(row)
    if len(returned) > 1 or returned and any(row.decided_at > returned[0].decided_at for row in rows):
        raise ValidationError('Retain the closed return boundary; prepare a successor for further decisions.')
    complete = offices == required and not returned
    return dict(proposal=str(record.public_id), checksum=record.payload_checksum,
        status='returned' if returned else 'reviewed' if complete else 'partially_reviewed' if rows else 'prepared',
        required_reviews=[dict(role=role, department_id=office) for role, office in sorted(required)],
        decisions=[dict(payload=deepcopy(row.payload), checksum=row.payload_checksum) for row in rows],
        factual_review_complete=complete, numeric_adjustment_approved=False, presentation_recipe=None,
        form_issued=False, cash_available=False)


def _state(record, rows):
    try:
        return _state_checked(record, rows)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained treatment decision evidence.') from error


def _checks(role, supplied):
    if not isinstance(supplied, dict) or set(supplied) != set(CHECKS[role]):
        raise ValidationError('Retain every explicit treatment responsibility check.')
    for item in supplied.values():
        if not isinstance(item, dict) or set(item) != {'verified', 'basis'} or type(item['verified']) is not bool:
            raise ValidationError('Choose verified/not verified explicitly with an original-source basis.')
        text(item['basis'], 'independent treatment verification basis')
    return deepcopy(supplied)


@transaction.atomic(using='finance')
def review(record, actor, *, role, approve, checks, authority, note):
    package = _locks(record)
    record = Proposal.objects.select_for_update().select_related(*RELATED).get(pk=record.pk, package=package)
    owner = department_for_user(actor)
    from vouchers.roles import is_finance_uat_viewer
    if (not isinstance(role, str) or role not in CHECKS or not owner or not actor.is_active
        or not has_budget_permission(actor, 'review_form1_package_'+role) or is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use the designated original office treatment reviewer.')
    record = _read(record, actor)
    rows = list(record.decisions.all())
    state = _state(record, rows)
    if (type(approve) is not bool or state['status'] in ('reviewed', 'returned')
        or actor.pk in {record.prepared_by_id, record.package.prepared_by_id}
        or (role, owner.pk) not in reviews.required(package, package.payload['assembly']['payload'])):
        raise ValidationError('A distinct designated officer must decide a pending treatment version.')
    checked = _checks(role, checks)
    if approve and (not packages._current(record.package, actor)
        or Proposal.objects.filter(package=package).order_by('-version').first().pk != record.pk
        or not all(item['verified'] for item in checked.values())):
        raise ValidationError('Review only the latest complete factual proposal with current original sources.')
    row = Decision(proposal=record, role=role, actor_id=actor.pk, actor_department_id=owner.pk,
        approve=approve, decided_at=timezone.now())
    row.payload = dict(schema=1, identity=_decision_identity(record, row), checks=checked,
        authority=text(authority, 'treatment review designation'), note=text(note, 'treatment finding decision reason'),
        source_current=True if approve else None)
    row.payload_checksum = checksum(row.payload)
    _state(record, [*rows, row])
    row.save()
    record_event(package, 'form1_treatment_'+role+'_decided', actor, note,
        dict(treatment=str(record.public_id), decision=str(row.public_id), decision_checksum=row.payload_checksum))
    return row


def snapshot(record, actor, *, export=False):
    record = _read(record, actor, export=export)
    return dict(payload=deepcopy(record.payload), checksum=record.payload_checksum,
        review=_state(record, list(record.decisions.all())))


@transaction.atomic(using='finance')
def export(record, actor, *, kind):
    """Capture original bytes and one decision set under the owning source locks."""
    from . import form1_package_exports as outputs
    if kind not in ('json', 'zip'):
        raise ValidationError('Choose complete findings data or original-document ZIP.')
    package = _locks(record)
    record = Proposal.objects.select_for_update().get(pk=record.pk, package=package)
    record = _read(record, actor, export=True)
    original, files = outputs.capture(record.package, actor)
    retained = dict(payload=deepcopy(record.payload), checksum=record.payload_checksum,
        review=_state(record, list(record.decisions.all())))
    documents = []
    for row in record.attachments.all():
        metadata = record.payload['draft']['payload']['documents'][row.key]
        data = bytes(row.data)
        path = 'treatment-documents/'+row.key+outputs._extension(data)
        files[path] = data
        documents.append(dict(key=row.key, path=path, original=deepcopy(metadata),
            size=len(data), sha256=sha256(data).hexdigest()))
    body = dict(schema=1, kind='form1_treatment_findings_export',
        original_package=original, treatment=retained, documents=documents,
        numeric_adjustment_approved=False, form_issued=False, cash_available=False)
    envelope = dict(payload=body, checksum=checksum(body))
    return (outputs.json_bytes(envelope) if kind == 'json' else outputs._zip(envelope, files)), envelope
