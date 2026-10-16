"""Independent immutable unsigned-copy release; no physical signature or final issuance."""
from copy import deepcopy
from hashlib import sha256
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting.models import Fund
from accounting.summary_actuals import text
from .access import department_for_user, has_budget_permission
from .models import BudgetVersion, Form1Package, Form1SigningPreparation as Preparation, Form1UnsignedCopy as Copy
from . import form1_signing as signing, form1_packages as packages, form1_package_reviews as reviews
from . import form1_package_exports as sources, form1_unsigned_output as output
from .form1_integrity import operation
from .services import record_event


def _access(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    owner = department_for_user(actor)
    if (not owner or not actor.is_active or action not in ('release', 'view', 'export')
            or not has_budget_permission(actor, action+'_form1_signing_copies')
            or action == 'release' and is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use the original office and explicit unsigned signing-copy authority.')
    if action == 'release' and not has_budget_permission(actor, 'view_form1_signing_copies'):
        raise PermissionDenied('Copy release also requires viewing authority over its original evidence.')
    return owner


def _identity(record):
    return dict(public_id=str(record.public_id), preparation=str(record.preparation.public_id),
        package=str(record.preparation.package.public_id), department_id=record.department_id,
        department_label=record.department_label, released_by=record.released_by_id,
        released_by_label=record.released_by_label, released_at=record.released_at.isoformat())


def _original(package):
    state = reviews._state(package, package.payload['assembly']['payload'], list(package.decisions.all()))
    return sources._retained(package, state)[0]


def verify(record, designation, original):
    envelope = dict(payload=record.payload, checksum=record.payload_checksum)
    data, _ = output.verify(envelope)
    if (record.department_id != record.preparation.department_id
            or record.department_label != record.preparation.department_label
            or data['identity'] != _identity(record) or data['designation'] != designation
            or data['original_package'] != original or not bytes(record.document).startswith(b'%PDF-')
            or sha256(bytes(record.document)).hexdigest() != record.document_checksum):
        raise ValidationError('Retain the original released bytes and exact source/designation decisions.')
    return deepcopy(data)


@transaction.atomic(using='finance')
@operation
def release(*, preparation, actor, reference):
    owner = _access(actor, 'release')
    stored = Preparation.objects.select_related('package').get(pk=preparation.pk)
    package = stored.package
    if owner.pk != package.department_id:
        raise PermissionDenied('Only the original Budget office releases this unsigned Form 1 copy.')
    if actor.pk in (stored.prepared_by_id, package.prepared_by_id):
        raise ValidationError('A different Budget officer must release the signing copy.')
    proposal = BudgetVersion.objects.select_for_update().get(pk=package.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=package.fund_id)
    package = Form1Package.objects.select_for_update().get(pk=package.pk, proposal=proposal, fund=fund)
    stored = Preparation.objects.select_for_update().select_related('package').get(pk=stored.pk, package=package)
    # Creation is itself an export of financial and designation data. Viewing
    # and original-source export authority must both be explicit.
    signing.snapshot(stored, actor)
    designation = signing.snapshot(stored, actor, export=True)
    if (Copy.objects.filter(preparation=stored).exists() or designation['status'] != 'reviewed_preparation'
            or Preparation.objects.filter(package=package).aggregate(n=Max('version'))['n'] != stored.version
            or not packages._current(package, actor)):
        raise ValidationError('Release once from the latest approved preparation and current complete original sources.')
    original = _original(package)
    record = Copy(public_id=uuid.uuid4(), preparation=stored, department_id=package.department_id,
        department_label=package.department_label, released_by_id=actor.pk,
        released_by_label=text(actor.get_full_name() or actor.username, 'copy release actor', 160),
        released_at=timezone.now())
    record.payload = dict(schema=1, kind='form1_unsigned_signing_copy', identity=_identity(record),
        original_package=original, designation=designation, reference=text(reference, 'signing-copy release reference'),
        source_current_observed=True, unsigned_copy_issued=True, **{key: False for key in output.FALSE_FLAGS})
    record.payload_checksum = checksum(record.payload)
    record.document = output.render_pdf(dict(payload=record.payload, checksum=record.payload_checksum))
    record.document_checksum = sha256(bytes(record.document)).hexdigest()
    verify(record, designation, original)
    record.save()
    record_event(record, 'form1_unsigned_copy_released', actor, record.payload['reference'],
                 dict(preparation_checksum=stored.payload_checksum, document_sha256=record.document_checksum,
                      output_checksum=record.payload_checksum, form_issued=False))
    return record


@operation
def snapshot(record, actor, *, export=False):
    _access(actor, 'export' if export else 'view')
    stored = Copy.objects.select_related('preparation__package').get(pk=record.pk)
    designation = signing.snapshot(stored.preparation, actor, export=export)
    package = packages._read(stored.preparation.package, actor, export=export)
    data = verify(stored, designation, _original(package))
    return dict(payload=data, payload_checksum=stored.payload_checksum, document_sha256=stored.document_checksum,
        unsigned_copy_issued=True, **{key: False for key in output.FALSE_FLAGS})


def document(record, actor):
    retained = snapshot(record, actor, export=True)
    content = bytes(Copy.objects.get(pk=record.pk).document)
    if sha256(content).hexdigest() != retained['document_sha256']:
        raise ValidationError('Downloaded bytes differ from the verified released copy.')
    return content, retained
