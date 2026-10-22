"""Retained paper-return declarations and independent, source-bound verification.

PDF parsing checks the file, not handwriting. Only an independent officer's
explicit findings establish the recorded verification; original copies stay unsigned.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import uuid
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from pypdf import PdfReader
from pypdf.errors import LimitReachedError, PdfReadError

from accounting.cash_classifications import checksum
from accounting.models import Fund
from accounting.summary_actuals import document, text
from .access import department_for_user, has_budget_permission
from .form1_integrity import operation
from .models import (BudgetVersion, Form1Package, Form1SigningPreparation as Preparation,
    Form1UnsignedCopy as Copy, Form1SignedReceipt as Receipt, Form1SignedReview as Review,
    Form1FinalIssue as Issue)
from . import form1_signing as signing, form1_unsigned_copies as copies, form1_packages as packages
from .services import record_event

CHECKS = ('complete_pages', 'financial_fields', 'physical_custody')


def access(actor, action, *, final=False):
    from vouchers.roles import is_finance_uat_viewer
    allowed = ('issue', 'view', 'export') if final else ('record', 'verify', 'view', 'export')
    suffix = '_form1_signed_packages' if final else '_form1_signed_copies'
    owner = department_for_user(actor)
    if (action not in allowed or not owner or not actor.is_active
            or not has_budget_permission(actor, action + suffix)
            or action not in ('view', 'export') and is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use explicit signed Form 1 authority and original office access.')
    if action not in ('view', 'export') and not has_budget_permission(actor, 'view' + suffix):
        raise PermissionDenied('This action also requires viewing its original evidence.')
    return owner


def _locked(copy, actor, action, *, final=False):
    owner = access(actor, action, final=final)
    stored = Copy.objects.select_related('preparation__package').get(pk=copy.pk)
    package = stored.preparation.package
    if owner.pk != package.department_id:
        raise PermissionDenied('Only the original Budget office records, verifies or issues this Form 1.')
    proposal = BudgetVersion.objects.select_for_update().get(pk=package.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=package.fund_id)
    package = Form1Package.objects.select_for_update().get(pk=package.pk, proposal=proposal, fund=fund)
    preparation = Preparation.objects.select_for_update().get(pk=stored.preparation_id, package=package)
    return Copy.objects.select_for_update().select_related('preparation__package').get(pk=stored.pk, preparation=preparation)


def _current(copy, actor):
    preparation = copy.preparation
    if (Preparation.objects.filter(package_id=preparation.package_id).aggregate(n=Max('version'))['n'] != preparation.version
            or not packages._current(preparation.package, actor)):
        raise ValidationError('Verify and issue only the latest preparation and current original sources.')


def _page_count(content):
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ValidationError('Use an unencrypted PDF of all returned signing pages.')
        count = len(reader.pages)
        if not count:
            raise ValidationError('The returned PDF must contain the actual signing pages.')
        return count
    except (PdfReadError, LimitReachedError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise ValidationError('Use a readable PDF of the complete returned Form 1.') from error


def entities(copy):
    return [row['entity_key'] for row in copy.preparation.package.payload['assembly']['payload']['members']]


def _facts(copy, signed_dates, received_on, received_by, custody_reference, custody_location, observed_on):
    day = signing._day(received_on)
    release_day = timezone.localtime(copy.released_at).date()
    if day < release_day or day > observed_on:
        raise ValidationError('Physical receipt must follow unsigned release and cannot be future-dated.')
    if not isinstance(signed_dates, dict) or set(signed_dates) != set(entities(copy)):
        raise ValidationError('Retain actual signing dates separately for every Form 1 entity.')
    dates = {}
    for entity, values in signed_dates.items():
        if not isinstance(values, dict) or set(values) != set(signing.ROLES):
            raise ValidationError('Retain all four certification dates and separate Chief Executive approval date.')
        row = {}
        for role, value in values.items():
            if value is None:
                row[role] = None
                continue
            signed = signing._day(value)
            authority = copy.preparation.payload['signatories'][role]
            if (signed < release_day or signed > day or signed < signing._day(authority['valid_from'])
                    or authority['valid_to'] is not None and signed > signing._day(authority['valid_to'])):
                raise ValidationError('Every actual signing date must follow release, precede receipt and have retained designation authority.')
            row[role] = signed.isoformat()
        certifications = [value for role, value in row.items() if role != 'chief_executive' and value is not None]
        if row['chief_executive'] is not None and certifications and row['chief_executive'] < max(certifications):
            raise ValidationError('Chief Executive approval cannot precede the four certifications.')
        dates[entity] = row
    return dict(signed_dates=dates, received_on=day.isoformat(),
        received_by=text(received_by, 'actual physical recipient name', 180),
        custody_reference=text(custody_reference, 'physical receipt/custody reference'),
        custody_location=text(custody_location, 'retained original paper location'))


def _previous(issue, copy):
    if issue is None:
        return None
    package = copy.preparation.package
    identity = issue.payload.get('identity') if isinstance(issue.payload,dict) else None
    pinned = dict(public_id=str(issue.public_id),version=issue.version,
                  proposal_id=issue.proposal_id,fund_id=issue.fund_id,department_id=issue.department_id)
    if (not isinstance(identity,dict) or any(identity.get(key) != value for key,value in pinned.items())
            or issue.proposal_id != package.proposal_id or issue.fund_id != package.fund_id
            or issue.department_id != package.department_id or checksum(issue.payload) != issue.payload_checksum
            or sha256(bytes(issue.archive)).hexdigest() != issue.archive_checksum):
        raise ValidationError('Use the exact previously issued Form 1 from this proposal, fund and Budget office.')
    # Bind the advertised row/payload to the actual original issuance envelope.
    # Read only this bounded member; do not recursively traverse prior sources.
    envelope = json.dumps(dict(payload=issue.payload,payload_checksum=issue.payload_checksum),
                          ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    try:
        with ZipFile(BytesIO(bytes(issue.archive))) as archive:
            if archive.namelist().count('issuance.json') != 1:
                raise ValidationError('Retain one original predecessor issuance envelope.')
            info = archive.getinfo('issuance.json')
            if info.flag_bits & 1 or info.file_size != len(envelope) or archive.read(info) != envelope:
                raise ValidationError('The predecessor row differs from its original issued archive.')
    except (BadZipFile,KeyError,ValueError,RuntimeError) as error:
        raise ValidationError('Use the readable original predecessor issuance envelope.') from error
    return dict(public_id=str(issue.public_id), version=issue.version, payload_checksum=issue.payload_checksum,
                archive_sha256=issue.archive_checksum)


def _head(copy):
    package = copy.preparation.package
    return Issue.objects.filter(proposal_id=package.proposal_id, fund_id=package.fund_id).order_by('-version').first()


def _identity(receipt):
    return dict(public_id=str(receipt.public_id), copy=str(receipt.copy.public_id),
        copy_checksum=receipt.copy.payload_checksum, department_id=receipt.department_id,
        department_label=receipt.department_label, version=receipt.version, captured_by=receipt.captured_by_id,
        captured_by_label=receipt.captured_by_label, captured_at=receipt.captured_at.isoformat())


def _review_identity(review, receipt):
    return dict(public_id=str(review.public_id), receipt=str(receipt.public_id),
        receipt_checksum=receipt.payload_checksum, approve=review.approve, actor_id=review.actor_id,
        actor_label=review.actor_label, actor_department_id=review.actor_department_id,
        decided_at=review.decided_at.isoformat())


def _checks(copy, supplied):
    keys = {*CHECKS, *(entity + ':' + role for entity in entities(copy) for role in signing.ROLES)}
    if not isinstance(supplied, dict) or set(supplied) != keys:
        raise ValidationError('Inspect all original pages, financial fields, custody and every entity’s five signing functions.')
    result = {}
    for key, row in supplied.items():
        if not isinstance(row, dict) or set(row) != {'verified', 'basis'} or type(row['verified']) is not bool:
            raise ValidationError('Record an explicit finding and evidence basis for every signing check.')
        result[key] = dict(verified=row['verified'], basis=text(row['basis'], 'independent signed-copy inspection basis'))
    return result


def _complete_dates(facts):
    return all(value is not None for row in facts['signed_dates'].values() for value in row.values())


def _verify(receipt, review=None):
    """Integrity only, after the caller authorizes the original copy and its sources."""
    try:
        data = receipt.payload
        facts = _facts(receipt.copy, **data['physical_return'], observed_on=timezone.localtime(receipt.captured_at).date())
        content = bytes(receipt.document)
        expected = dict(schema=1, kind='form1_signed_return', identity=_identity(receipt),
            physical_return=facts, document=data['document'], predecessor=_previous(receipt.predecessor_issue, receipt.copy),
            correction_reason=text(data['correction_reason'], 'receipt/version basis'),
            statutorily_certified=False, chief_executive_approved=False, form_issued=False, cash_available=False)
        if (checksum(data) != receipt.payload_checksum or data != expected
                or receipt.department_id != receipt.copy.department_id
                or receipt.department_label != receipt.copy.department_label
                or not content.startswith(b'%PDF-')
                or data['document'] != dict(name=text(data['document']['name'], 'returned PDF name', 180),
                    sha256=sha256(content).hexdigest(), size=len(content), pages=_page_count(content))
                or len(content) > 8 * 1024 * 1024
                or data['document']['pages'] < _page_count(bytes(receipt.copy.document))
                or receipt.captured_at < receipt.copy.released_at
                or any(data[key] is not False for key in
                       ('statutorily_certified', 'chief_executive_approved', 'form_issued', 'cash_available'))):
            raise ValidationError('Retain exact original signed-return declarations, copy identity and PDF bytes.')
        if review is not None:
            value = review.payload
            checked = _checks(receipt.copy, value['checks'])
            if (checksum(value) != review.payload_checksum or review.receipt_id != receipt.pk
                    or value != dict(schema=1, identity=_review_identity(review, receipt), checks=checked,
                        note=text(value['note'], 'signed-return decision basis'),
                        source_current_observed=True if review.approve else None)
                    or type(review.approve) is not bool or review.actor_department_id != receipt.department_id
                    or review.actor_id in (receipt.captured_by_id, receipt.copy.preparation.prepared_by_id,
                                           receipt.copy.preparation.package.prepared_by_id)
                    or review.decided_at < receipt.captured_at
                    or value['source_current_observed'] is not (True if review.approve else None)
                    or review.approve and (not _complete_dates(facts) or not all(row['verified'] for row in checked.values()))):
                raise ValidationError('Retain the exact independent inspection without inventing signatures.')
        return deepcopy(data)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained signed-return evidence.') from error


@transaction.atomic(using='finance')
@operation
def record(*, copy, actor, upload, signed_dates, received_on, received_by, custody_reference,
           custody_location, correction_reason, expected_latest, predecessor=None):
    stored = _locked(copy, actor, 'record')
    copies.snapshot(stored, actor)
    copies.snapshot(stored, actor, export=True)
    latest = Receipt.objects.filter(copy=stored).aggregate(n=Max('version'))['n'] or 0
    head = _head(stored)
    if (type(expected_latest) is not int or expected_latest != latest
            or (head.pk if head else None) != (predecessor.pk if predecessor else None)):
        raise ValidationError('Reload the latest signed-return and final-issue history before recording a successor.')
    previous = _previous(head, stored)
    facts = _facts(stored, signed_dates, received_on, received_by, custody_reference, custody_location,
                   timezone.localtime().date())
    content, metadata = document(upload, 'complete returned Form 1 PDF')
    if not content.startswith(b'%PDF-'):
        raise ValidationError('Use one PDF containing all returned Form 1 pages.')
    metadata.update(size=len(content), pages=_page_count(content))
    receipt = Receipt(public_id=uuid.uuid4(), copy=stored, predecessor_issue=head, version=latest+1,
        department_id=stored.department_id, department_label=stored.department_label,
        captured_by_id=actor.pk, captured_by_label=text(actor.get_full_name() or actor.username, 'receipt recorder', 160),
        captured_at=timezone.now(), document=content)
    receipt.payload = dict(schema=1, kind='form1_signed_return', identity=_identity(receipt), physical_return=facts,
        document=metadata, predecessor=previous, correction_reason=text(correction_reason, 'receipt/version basis'),
        statutorily_certified=False, chief_executive_approved=False, form_issued=False, cash_available=False)
    receipt.payload_checksum = checksum(receipt.payload)
    _verify(receipt)
    receipt.save()
    record_event(receipt, 'form1_signed_return_recorded', actor, receipt.payload['correction_reason'],
                 dict(payload_checksum=receipt.payload_checksum, document_sha256=metadata['sha256'], form_issued=False))
    return receipt


@transaction.atomic(using='finance')
@operation
def review(*, receipt, actor, approve, checks, note):
    original = Receipt.objects.select_related('copy').get(pk=receipt.pk)
    stored = _locked(original.copy, actor, 'verify')
    original = Receipt.objects.select_for_update().select_related('copy__preparation__package', 'predecessor_issue').get(pk=original.pk)
    snapshot(original, actor)
    snapshot(original, actor, export=True)
    if (type(approve) is not bool or Review.objects.filter(receipt=original).exists()
            or actor.pk in (original.captured_by_id, stored.preparation.prepared_by_id, stored.preparation.package.prepared_by_id)):
        raise ValidationError('A different Budget officer must decide a pending signed return exactly once.')
    checked = _checks(stored, checks)
    if approve:
        _current(stored, actor)
        head = _head(stored)
        if (Receipt.objects.filter(copy=stored).aggregate(n=Max('version'))['n'] != original.version
                or (head.pk if head else None) != original.predecessor_issue_id
                or not _complete_dates(original.payload['physical_return'])
                or not all(row['verified'] for row in checked.values())):
            raise ValidationError('Approve only the latest return, exact issue predecessor, actual signing dates and complete independently verified findings.')
    decision = Review(public_id=uuid.uuid4(), receipt=original, approve=approve, actor_id=actor.pk,
        actor_label=text(actor.get_full_name() or actor.username, 'independent inspector', 160),
        actor_department_id=original.department_id, decided_at=timezone.now())
    decision.payload = dict(schema=1, identity=_review_identity(decision, original), checks=checked,
        note=text(note, 'signed-return decision basis'), source_current_observed=True if approve else None)
    decision.payload_checksum = checksum(decision.payload)
    _verify(original, decision)
    decision.save()
    record_event(original, 'form1_signed_return_reviewed', actor, decision.payload['note'],
                 dict(review_checksum=decision.payload_checksum, approve=approve, form_issued=False))
    return decision


@operation
def snapshot(receipt, actor, *, export=False):
    access(actor, 'export' if export else 'view')
    stored = Receipt.objects.select_related('copy__preparation__package', 'predecessor_issue').get(pk=receipt.pk)
    copies.snapshot(stored.copy, actor, export=export)
    decision = Review.objects.filter(receipt=stored).first()
    return _state(stored, decision)


def _state(stored, decision):
    data = _verify(stored, decision)
    return dict(payload=data, payload_checksum=stored.payload_checksum,
        review=dict(payload=deepcopy(decision.payload), payload_checksum=decision.payload_checksum) if decision else None,
        status='verified' if decision and decision.approve else 'returned' if decision else 'unverified',
        statutorily_certified=bool(decision and decision.approve),
        chief_executive_approved=bool(decision and decision.approve), form_issued=False, cash_available=False)


@operation
def history(copy, record_ids, actor):
    """Authorize the one common original parent, then verify each actual receipt.

    This is bounded history delivery, not a cache of permissions or currentness.
    Never trust caller-supplied model fields as retained financial evidence.
    """
    access(actor, 'view')
    stored = Copy.objects.select_related('preparation__package').get(pk=copy.pk)
    copies.snapshot(stored, actor)
    ids = list(record_ids)
    if any(type(key) is not int or key <= 0 for key in ids) or len(set(ids)) != len(ids):
        raise ValidationError('Select distinct original signed-return identities.')
    rows = {row.pk: row for row in Receipt.objects.filter(copy=stored, pk__in=ids)
            .select_related('verification', 'predecessor_issue')}
    if set(rows) != set(ids):
        raise ValidationError('Every history row must belong to this exact original unsigned copy.')
    result = []
    for key in ids:
        row = rows[key]
        row.copy = stored
        result.append((row, _state(row, getattr(row, 'verification', None))))
    return result


def returned_document(receipt, actor):
    retained = snapshot(receipt, actor, export=True)
    content = bytes(Receipt.objects.get(pk=receipt.pk).document)
    if sha256(content).hexdigest() != retained['payload']['document']['sha256']:
        raise ValidationError('The downloaded PDF differs from its retained original.')
    return content, retained
