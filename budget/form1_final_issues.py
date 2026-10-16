"""Immutable original Form 1 issue bundles and explicit correction successors."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import uuid
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting.summary_actuals import text
from . import form1_signed_copies as signed, form1_unsigned_copies as unsigned
from .form1_integrity import operation
from .models import Form1SignedReceipt as Receipt, Form1FinalIssue as Issue
from .services import record_event


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _identity(issue):
    return dict(public_id=str(issue.public_id), receipt=str(issue.receipt.public_id),
        receipt_checksum=issue.receipt.payload_checksum, proposal_id=issue.proposal_id, fund_id=issue.fund_id,
        department_id=issue.department_id, department_label=issue.department_label, version=issue.version,
        issued_by=issue.issued_by_id, issued_by_label=issue.issued_by_label, issued_at=issue.issued_at.isoformat())


def _members(copy, receipt, copy_snapshot, signed_snapshot):
    return {'unsigned-copy.json': _json(copy_snapshot), 'signed-evidence.json': _json(signed_snapshot),
            'unsigned-form1.pdf': bytes(copy.document), 'signed-form1.pdf': bytes(receipt.document)}


def _manifest(members):
    return {name: dict(size=len(data), sha256=sha256(data).hexdigest()) for name, data in members.items()}


def _verify(issue, copy_snapshot, signed_snapshot):
    try:
        receipt = issue.receipt
        copy = receipt.copy
        package = copy.preparation.package
        review = signed_snapshot['review']
        previous = issue.predecessor
        expected = dict(schema=1, kind='form1_final_issue', identity=_identity(issue),
            predecessor=signed._previous(previous, copy), review_checksum=review['payload_checksum'] if review else None,
            reference=text(issue.payload['reference'], 'final issuance reference'),
            statutorily_certified=True, chief_executive_approved=True, form_issued=True, cash_available=False,
            source_current_observed=True,
            members=_manifest(_members(copy, receipt, copy_snapshot, signed_snapshot)))
        if (issue.payload != expected or checksum(issue.payload) != issue.payload_checksum
                or issue.proposal_id != package.proposal_id or issue.fund_id != package.fund_id
                or issue.department_id != package.department_id or issue.department_label != package.department_label
                or issue.predecessor_id != receipt.predecessor_issue_id
                or issue.version != (previous.version + 1 if previous else 1)
                or signed_snapshot['status'] != 'verified' or not review
                or issue.issued_by_id in (receipt.captured_by_id, copy.preparation.prepared_by_id, package.prepared_by_id)
                or issue.issued_at < receipt.captured_at
                or issue.issued_at < datetime.fromisoformat(review['payload']['identity']['decided_at'])
                or previous is not None and issue.issued_at < previous.issued_at
                or any(issue.payload[key] is not True for key in
                       ('statutorily_certified', 'chief_executive_approved', 'form_issued', 'source_current_observed'))
                or issue.payload['cash_available'] is not False):
            raise ValidationError('Retain the exact independently verified final issue and correction lineage.')
        content = bytes(issue.archive)
        if sha256(content).hexdigest() != issue.archive_checksum:
            raise ValidationError('The final issued archive differs from its retained original.')
        expected_members = _members(copy, receipt, copy_snapshot, signed_snapshot)
        expected_members['issuance.json'] = _json(dict(payload=issue.payload, payload_checksum=issue.payload_checksum))
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) != len(expected_members) or {info.filename for info in entries} != set(expected_members):
                raise ValidationError('Retain exactly the original five issued bundle members.')
            for info in entries:
                original = expected_members[info.filename]
                if info.flag_bits & 1 or info.file_size != len(original) or archive.read(info) != original:
                    raise ValidationError('An issued bundle member differs from its retained source evidence.')
        return deepcopy(issue.payload)
    except (KeyError, TypeError, ValueError, AttributeError, BadZipFile, RuntimeError) as error:
        raise ValidationError('Invalid retained final Form 1 issue evidence.') from error


@transaction.atomic(using='finance')
@operation
def issue(*, receipt, actor, reference):
    original = Receipt.objects.select_related('copy').get(pk=receipt.pk)
    copy = signed._locked(original.copy, actor, 'issue', final=True)
    original = Receipt.objects.select_for_update().select_related('copy__preparation__package', 'predecessor_issue').get(pk=original.pk)
    # Issuance packages the actual originals, so both read and export grants
    # are required independently of the action permission.
    signed.snapshot(original, actor)
    retained = signed.snapshot(original, actor, export=True)
    source = unsigned.snapshot(copy, actor, export=True)
    signed._current(copy, actor)
    head = signed._head(copy)
    package = copy.preparation.package
    if (retained['status'] != 'verified' or Issue.objects.filter(receipt=original).exists()
            or Receipt.objects.filter(copy=copy).aggregate(n=Max('version'))['n'] != original.version
            or (head.pk if head else None) != original.predecessor_issue_id
            or actor.pk in (original.captured_by_id, copy.preparation.prepared_by_id, package.prepared_by_id)):
        raise ValidationError('Independently issue the latest verified receipt once over the exact current final predecessor.')
    record = Issue(public_id=uuid.uuid4(), receipt=original, proposal_id=package.proposal_id, fund_id=package.fund_id,
        predecessor=head, version=head.version+1 if head else 1, department_id=package.department_id,
        department_label=package.department_label, issued_by_id=actor.pk,
        issued_by_label=text(actor.get_full_name() or actor.username, 'final issuance officer', 160), issued_at=timezone.now())
    members = _members(copy, original, source, retained)
    record.payload = dict(schema=1, kind='form1_final_issue', identity=_identity(record), predecessor=signed._previous(head, copy),
        review_checksum=retained['review']['payload_checksum'], reference=text(reference, 'final issuance reference'),
        statutorily_certified=True, chief_executive_approved=True, form_issued=True, cash_available=False,
        source_current_observed=True, members=_manifest(members))
    record.payload_checksum = checksum(record.payload)
    members['issuance.json'] = _json(dict(payload=record.payload, payload_checksum=record.payload_checksum))
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    record.archive = buffer.getvalue()
    record.archive_checksum = sha256(bytes(record.archive)).hexdigest()
    _verify(record, source, retained)
    record.save()
    record_event(record, 'form1_final_package_issued', actor, record.payload['reference'],
                 dict(payload_checksum=record.payload_checksum, archive_sha256=record.archive_checksum,
                      receipt_checksum=original.payload_checksum, predecessor=record.payload['predecessor']))
    return record


@transaction.atomic(using='finance')
@operation
def verify_and_issue(*, receipt, actor, checks, note, reference):
    """One clerk action, with both authorities and one atomic source-locked decision."""
    signed.access(actor, 'issue', final=True)
    signed.review(receipt=receipt, actor=actor, approve=True, checks=checks, note=note)
    return issue(receipt=receipt, actor=actor, reference=reference)


@operation
def snapshot(record, actor, *, export=False):
    signed.access(actor, 'export' if export else 'view', final=True)
    stored = Issue.objects.select_related('receipt__copy__preparation__package', 'predecessor').get(pk=record.pk)
    retained = signed.snapshot(stored.receipt, actor, export=export)
    source = unsigned.snapshot(stored.receipt.copy, actor, export=export)
    data = _verify(stored, source, retained)
    return dict(payload=data, payload_checksum=stored.payload_checksum, archive_sha256=stored.archive_checksum,
        statutorily_certified=True, chief_executive_approved=True, form_issued=True, cash_available=False)


def document(record, actor):
    retained = snapshot(record, actor, export=True)
    content = bytes(Issue.objects.get(pk=record.pk).archive)
    if sha256(content).hexdigest() != retained['archive_sha256']:
        raise ValidationError('Downloaded issued bytes differ from their verified original.')
    return content, retained
