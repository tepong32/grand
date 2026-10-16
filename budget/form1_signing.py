"""Immutable signing preparations and independent review; not signatures or issuance."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
from pathlib import PureWindowsPath
import re
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting.summary_actuals import document, text, MAX_EVIDENCE_BYTES
from accounting.models import Fund
from .access import department_for_user, has_budget_permission
from .models import (BudgetVersion, Form1Package, Form1SigningPreparation as Preparation,
                     Form1SigningEvidence as Evidence, Form1SigningReview as Review)
from . import form1_packages as packages, form1_package_reviews as package_reviews
from .services import record_event
from .form1_integrity import operation

ROLES = {
    'treasurer': 'Local Treasurer', 'budget_officer': 'Local Budget Officer',
    'planning_coordinator': 'Local Planning and Development Coordinator',
    'accountant': 'Local Accountant', 'chief_executive': 'Local Chief Executive',
}
CHECKS = ('source_identity', 'source_amounts', 'role_designations', 'authority_documents')
FLAGS = ('statutorily_certified', 'chief_executive_approved', 'unsigned_copy_issued',
         'form_issued', 'cash_available')


def _day(value):
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as error:
            raise ValidationError('Use an explicit calendar date.') from error
        if result.isoformat() == value:
            return result
    raise ValidationError('Use an explicit calendar date.')


def _capability(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    owner = department_for_user(actor)
    if (not owner or not getattr(actor, 'is_active', False)
            or not has_budget_permission(actor, action + '_form1_signing_preparations')
            or action in ('prepare', 'review') and is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use the explicit signing-preparation permission and original office scope.')
    if action in ('prepare', 'review') and not has_budget_permission(actor, 'view_form1_signing_preparations'):
        raise PermissionDenied('Preparation/review also requires original signing-preparation viewing authority.')
    return owner


def _locked_package(package, actor, action):
    owner = _capability(actor, action)
    stored = Form1Package.objects.get(pk=package.pk)
    if owner.pk != stored.department_id:
        raise PermissionDenied('Only the original Budget office prepares or reviews these designations.')
    proposal = BudgetVersion.objects.select_for_update().get(pk=stored.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=stored.fund_id)
    stored = Form1Package.objects.select_for_update().get(pk=stored.pk, proposal=proposal, fund=fund)
    return packages._read(stored, actor)


def _source(package):
    body = package.payload['assembly']['payload']
    state = package_reviews._state(package, body, list(package.decisions.all()))
    return dict(package=str(package.public_id), package_checksum=package.payload_checksum,
                assembly_checksum=package.payload['assembly']['checksum'],
                internal_review=state, internal_review_checksum=checksum(state))


def _lgu(package):
    body = package.payload['assembly']['payload']
    flow = body['philhealth_source']['payload']['inventory']['payload']['stock']['payload']['flow']['payload']
    parents = flow['sources']['reconciliations']
    names = []
    for member in body['members']:
        forms = [form for parent in parents if parent['payload']['entity_key'] == member['entity_key']
                 for form in parent['payload']['forms']]
        if not forms:
            raise ValidationError('Each entity needs its own explicit retained office LGU identification.')
        names.extend(text(form['payload'].get('lgu'), 'original office LGU identification', 200) for form in forms)
    if len(set(names)) != 1:
        raise ValidationError('Resolve conflicting original LGU names through their source successors.')
    return names[0]


def _signatories(supplied, document_date):
    if not isinstance(supplied, dict) or set(supplied) != set(ROLES):
        raise ValidationError('Retain all four Form 1 certification functions and separate Chief Executive approval.')
    result = {}
    for role, row in supplied.items():
        if not isinstance(row, dict) or set(row) != {'name', 'position', 'authority_reference', 'valid_from', 'valid_to', 'evidence'}:
            raise ValidationError('Retain each explicit role, named officer, designation dates and original evidence.')
        start, end = _day(row['valid_from']), _day(row['valid_to']) if row['valid_to'] is not None else None
        if document_date < start or end is not None and (end < start or document_date > end):
            raise ValidationError('Every designation must cover the intended document date.')
        evidence = row['evidence']
        if (not isinstance(evidence, dict) or set(evidence) != {'name', 'sha256', 'size'}
                or type(evidence['size']) is not int or not 0 < evidence['size'] <= MAX_EVIDENCE_BYTES
                or not isinstance(evidence['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', evidence['sha256'])
                or text(evidence['name'], 'designation document name', 180) != PureWindowsPath(evidence['name']).name):
            raise ValidationError('Retain exact original designation document names, lengths and hashes.')
        result[role] = dict(name=text(row['name'], ROLES[role] + ' name', 180),
            position=text(row['position'], 'actual designated position', 180),
            authority_reference=text(row['authority_reference'], 'designation authority reference'),
            valid_from=start.isoformat(), valid_to=end.isoformat() if end is not None else None,
            evidence=deepcopy(evidence))
    return result


def _checks(supplied):
    if not isinstance(supplied, dict) or set(supplied) != set(CHECKS):
        raise ValidationError('Record all independent signing-preparation checks.')
    result = {}
    for key, row in supplied.items():
        if not isinstance(row, dict) or set(row) != {'verified', 'basis'} or type(row['verified']) is not bool:
            raise ValidationError('Use an explicit verified/not-verified choice and evidence basis.')
        result[key] = dict(verified=row['verified'], basis=text(row['basis'], 'independent check basis'))
    return result


def _identity(preparation):
    return dict(public_id=str(preparation.public_id), package=str(preparation.package.public_id),
        department_id=preparation.department_id, version=preparation.version,
        document_date=preparation.document_date.isoformat(), prepared_by=preparation.prepared_by_id,
        prepared_by_label=preparation.prepared_by_label, prepared_at=preparation.prepared_at.isoformat())


def verify(preparation, package, evidence=None, review=None):
    """Integrity only; callers authorize original sources separately, including history."""
    try:
        data = preparation.payload
        source = _source(package)
        if source['internal_review']['status'] != 'reviewed' or not package.payload['assembly']['payload']['calculation_coverage_complete']:
            raise ValidationError('Retain an actually complete, internally reviewed source package.')
        source_reviewed_at = max(datetime.fromisoformat(row['payload']['identity']['decided_at'])
                                 for row in source['internal_review']['decisions'])
        if (set(data) != {'schema', 'kind', 'identity', 'source', 'lgu', 'signatories', 'reference', *FLAGS}
                or type(data['schema']) is not int or data['schema'] != 1 or data['kind'] != 'form1_signing_preparation'
                or checksum(data) != preparation.payload_checksum or preparation.package_id != package.pk
                or preparation.department_id != package.department_id or preparation.department_label != package.department_label
                or data['identity'] != _identity(preparation) or data['source'] != source
                or preparation.prepared_at < source_reviewed_at
                or preparation.document_date < timezone.localtime(source_reviewed_at).date()
                or data['lgu'] != _lgu(package) or any(data[flag] is not False for flag in FLAGS)
                or data['reference'] != text(data['reference'], 'signing preparation reference')
                or _signatories(data['signatories'], preparation.document_date) != data['signatories']):
            raise ValidationError('The signing preparation must reproduce its original package, roles and evidence.')
        rows = list(preparation.evidence.all()) if evidence is None else list(evidence)
        if len(rows) != len(ROLES) or {row.role for row in rows} != set(ROLES):
            raise ValidationError('Retain every original role designation document exactly once.')
        for row in rows:
            content = bytes(row.data); metadata = data['signatories'][row.role]['evidence']
            if (row.preparation_id != preparation.pk or len(content) != metadata['size']
                    or sha256(content).hexdigest() != metadata['sha256']
                    or not content.startswith((b'%PDF-', b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff'))):
                raise ValidationError('Original designation document bytes differ from the retained preparation.')
        if review is not None:
            value = review.payload
            expected = dict(public_id=str(review.public_id), preparation=str(preparation.public_id),
                preparation_checksum=preparation.payload_checksum, approve=review.approve,
                actor_id=review.actor_id, actor_label=review.actor_label,
                actor_department_id=review.actor_department_id, decided_at=review.decided_at.isoformat())
            if (set(value) != {'schema', 'identity', 'checks', 'note', 'source_current_observed'}
                    or type(value['schema']) is not int or value['schema'] != 1
                    or review.preparation_id != preparation.pk or value['identity'] != expected
                    or checksum(value) != review.payload_checksum or type(review.approve) is not bool
                    or review.actor_id in (preparation.prepared_by_id, package.prepared_by_id)
                    or review.actor_department_id != package.department_id
                    or review.decided_at < preparation.prepared_at
                    or _checks(value['checks']) != value['checks']
                    or value['note'] != text(value['note'], 'independent preparation-review note')
                    or value['source_current_observed'] is not (True if review.approve else None)
                    or review.approve and not all(row['verified'] for row in value['checks'].values())):
                raise ValidationError('Retain the exact independent preparation review without inferring signatures.')
        return deepcopy(data)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid original signing-preparation evidence.') from error


@transaction.atomic(using='finance')
@operation
def prepare(*, package, actor, document_date, lgu, signatories, documents, reference, expected_latest):
    package = _locked_package(package, actor, 'prepare')
    source = _source(package)
    if (source['internal_review']['status'] != 'reviewed'
            or not package.payload['assembly']['payload']['calculation_coverage_complete']
            or not packages._current(package, actor)):
        raise ValidationError('Prepare only the latest complete, internally reviewed package with current original sources.')
    latest = Preparation.objects.filter(package=package).aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or expected_latest != latest:
        raise ValidationError('A newer signing preparation exists; reload its history.')
    day = _day(document_date)
    last_source_decision = max(datetime.fromisoformat(row['payload']['identity']['decided_at'])
                               for row in source['internal_review']['decisions'])
    if day < timezone.localtime(last_source_decision).date():
        raise ValidationError('The intended document date cannot precede the retained whole-package review.')
    if text(lgu, 'LGU identification', 200) != _lgu(package):
        raise ValidationError('Use the exact original office-source LGU identification.')
    if (not isinstance(signatories, dict) or set(signatories) != set(ROLES)
            or not isinstance(documents, dict) or set(documents) != set(ROLES)):
        raise ValidationError('Supply every Form 1 role and its original designation document.')
    rows, contents = {}, {}
    for role, supplied in signatories.items():
        if not isinstance(supplied, dict) or set(supplied) != {'name', 'position', 'authority_reference', 'valid_from', 'valid_to'}:
            raise ValidationError('Do not substitute another form’s signatory tuple or supply derived evidence metadata.')
        content, metadata = document(documents[role], ROLES[role] + ' designation')
        contents[role] = content
        rows[role] = dict(supplied, evidence=dict(metadata, size=len(content)))
    people = _signatories(rows, day)
    label = text(actor.get_full_name() or actor.username, 'preparer label', 160)
    preparation = Preparation(public_id=uuid.uuid4(), package=package, version=latest+1,
        document_date=day, department_id=package.department_id, department_label=package.department_label,
        prepared_by_id=actor.pk, prepared_by_label=label, prepared_at=timezone.now())
    preparation.payload = dict(schema=1, kind='form1_signing_preparation', identity=_identity(preparation),
        source=source, lgu=lgu.strip(), signatories=people, reference=text(reference, 'signing preparation reference'),
        **{flag: False for flag in FLAGS})
    preparation.payload_checksum = checksum(preparation.payload)
    preparation.save()
    for role, content in contents.items(): Evidence.objects.create(preparation=preparation, role=role, data=content)
    verify(preparation, package)
    record_event(preparation, 'form1_signing_prepared', actor, preparation.payload['reference'],
                 dict(payload_checksum=preparation.payload_checksum, package_checksum=package.payload_checksum))
    return preparation


@transaction.atomic(using='finance')
@operation
def review(*, preparation, actor, approve, checks, note):
    stored = Preparation.objects.select_related('package').get(pk=preparation.pk)
    package = _locked_package(stored.package, actor, 'review')
    stored = Preparation.objects.select_for_update().select_related('package').get(pk=stored.pk, package=package)
    previous = Review.objects.filter(preparation=stored).first()
    verify(stored, package, review=previous)
    if (type(approve) is not bool or previous is not None
            or actor.pk in (stored.prepared_by_id, package.prepared_by_id)):
        raise ValidationError('A different Budget officer must decide a pending signing preparation once.')
    checked = _checks(checks)
    if approve and (not all(row['verified'] for row in checked.values())
            or Preparation.objects.filter(package=package).aggregate(n=Max('version'))['n'] != stored.version
            or not packages._current(package, actor)):
        raise ValidationError('Approve only the latest preparation with current sources and all checks verified.')
    decision = Review(preparation=stored, approve=approve, actor_id=actor.pk,
        actor_label=text(actor.get_full_name() or actor.username, 'reviewer label', 160),
        actor_department_id=department_for_user(actor).pk, decided_at=timezone.now())
    identity = dict(public_id=str(decision.public_id), preparation=str(stored.public_id),
        preparation_checksum=stored.payload_checksum, approve=approve, actor_id=actor.pk,
        actor_label=decision.actor_label, actor_department_id=decision.actor_department_id,
        decided_at=decision.decided_at.isoformat())
    decision.payload = dict(schema=1, identity=identity, checks=checked,
        note=text(note, 'independent preparation-review note'), source_current_observed=True if approve else None)
    decision.payload_checksum = checksum(decision.payload)
    decision.save()
    verify(stored, package, review=decision)
    record_event(stored, 'form1_signing_reviewed', actor, decision.payload['note'],
                 dict(review_checksum=decision.payload_checksum, approve=approve))
    return decision


@operation
def snapshot(preparation, actor, *, export=False):
    _capability(actor, 'export' if export else 'view')
    stored = Preparation.objects.select_related('package__proposal__fiscal_year', 'package__fund').prefetch_related('evidence').get(pk=preparation.pk)
    package = packages._read(stored.package, actor, export=export)
    decision = Review.objects.filter(preparation=stored).first()
    data = verify(stored, package, review=decision)
    return dict(payload=data, payload_checksum=stored.payload_checksum,
        review=dict(payload=deepcopy(decision.payload), payload_checksum=decision.payload_checksum) if decision else None,
        status='reviewed_preparation' if decision and decision.approve else 'returned' if decision else 'prepared',
        **{flag: False for flag in FLAGS})


def designation_document(preparation, role, actor):
    """Original attachment download; require both candidate and original-source export."""
    if role not in ROLES:
        raise ValidationError('Select an original Form 1 designation role.')
    retained = snapshot(preparation, actor, export=True)
    content = bytes(Evidence.objects.get(preparation_id=preparation.pk, role=role).data)
    metadata = retained['payload']['signatories'][role]['evidence']
    if len(content) != metadata['size'] or sha256(content).hexdigest() != metadata['sha256']:
        raise ValidationError('The downloaded document differs from its verified original.')
    return content, deepcopy(metadata)
