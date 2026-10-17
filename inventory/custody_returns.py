"""Witnessed physical returns; independent verification is not employee clearance."""
import hashlib
from pathlib import Path
from uuid import UUID

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .access import asset_in_scope, in_gso_scope
from .models import Asset, AssetAuditEvent, AssetDisposalCase, AssetTransfer, AssetReturnEvent, AssetReturnEvidence
from .services import asset_snapshot, custody_source, _editable_data, _resolve_assigned_department


def can_manage_return(actor, action, asset=None):
    if action not in ("record", "verify") or not all(apps.is_installed(label) for label in ("profiles", "departments", "vouchers")):
        return False
    from vouchers.access import has_explicit_permission
    from vouchers.roles import is_finance_uat_viewer
    return bool(in_gso_scope(actor) and not is_finance_uat_viewer(actor)
        and has_explicit_permission(actor, f"inventory.{action}_asset_return")
        and (asset is None or asset_in_scope(actor, asset)))


def _require(actor, action, asset):
    if not can_manage_return(actor, action, asset):
        raise PermissionDenied


def _record(transfer, actor, action):
    snapshot = {name: getattr(transfer, name) for name in (
        "kind", "status", "state_version", "source_custodian_user_id", "source_employee_snapshot",
        "source_department_id", "source_department_label", "source_custodian", "destination_department_id",
        "destination_department_label", "destination_custodian", "reference", "reason", "return_condition",
        "return_review_note", "requested_by_id", "acknowledged_by_id", "cancelled_by_id", "cancellation_reason")}
    snapshot.update(public_id=str(transfer.public_id), asset_public_id=str(transfer.asset.public_id),
        transfer_date=transfer.transfer_date.isoformat(),
        evidence=list(transfer.return_evidence.values("id", "sha256", "size", "note", "original_filename", "uploaded_by_id")))
    snapshot.update({name: getattr(transfer, name).isoformat() if getattr(transfer, name) else None
        for name in ("requested_at", "acknowledged_at", "cancelled_at")})
    AssetReturnEvent.objects.create(transfer=transfer, actor=actor, action=action, snapshot=snapshot)


@transaction.atomic(using="default")
def record_return(*, actor, asset, data, request_id, expected_custody):
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    _require(actor, "record", asset)
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    data = _editable_data(data, {"transfer_date", "reference", "reason", "return_condition", "destination_custodian"})
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid return request identity.")
    existing = AssetTransfer.objects.filter(public_id=request_id).first()
    if existing:
        if (existing.kind != AssetTransfer.RETURN or existing.asset_id != asset.pk or existing.requested_by_id != actor.pk
            or any(str(getattr(existing, name)) != str(value).strip() for name, value in data.items())
            or set(data) != {"transfer_date", "reference", "reason", "return_condition", "destination_custodian"}):
            raise ValidationError("This request identity already belongs to different recorded content.")
        return existing
    if expected_custody != custody_source(asset):
        raise ValidationError("The recorded custody changed. Review the asset again before recording its return.")
    if (not asset.custodian_user_id or asset.custodian_snapshot.get("user_local_id") != asset.custodian_user_id):
        raise ValidationError("Reconcile the named custodian and original documents before recording this return.")
    if actor.pk == asset.custodian_user_id:
        raise PermissionDenied("A different GSO officer must witness and record your return.")
    if asset.status == Asset.RETIRED or asset.transfers.filter(status=AssetTransfer.PENDING).exists():
        raise ValidationError("Resolve the asset status or pending custody movement before recording a return.")
    if asset.disposal_cases.filter(status__in=(AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
            AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED)).exists():
        raise ValidationError("Resolve the open disposal case before recording a return.")
    owner = _resolve_assigned_department(asset.department_id)
    transfer = AssetTransfer(public_id=request_id, asset=asset, kind=AssetTransfer.RETURN,
        source_custodian_user_id=asset.custodian_user_id, source_employee_snapshot=asset.custodian_snapshot,
        source_department_id=asset.assigned_department_id, source_department_label=asset.assigned_department_label,
        source_custodian=asset.assigned_office, destination_department_id=owner.pk,
        destination_department_label=owner.name, requested_by=actor, **data)
    for field in ("reference", "reason", "destination_custodian"):
        value = getattr(transfer, field).strip()
        if not value:
            raise ValidationError("Record the return reference, receiving GSO location and witnessed facts.")
        setattr(transfer, field, value)
    transfer.full_clean()
    if transfer.transfer_date > timezone.localdate():
        raise ValidationError("The physical return date cannot be in the future.")
    transfer.save()
    _record(transfer, actor, "recorded")
    return transfer


def _locked(transfer, actor, action, expected_version):
    asset = Asset.objects.select_for_update().get(pk=transfer.asset_id)
    _require(actor, action, asset)
    transfer = AssetTransfer.objects.select_for_update().get(pk=transfer.pk, asset=asset, kind=AssetTransfer.RETURN)
    if (isinstance(expected_version, bool) or not isinstance(expected_version, int)
        or expected_version < 1 or transfer.state_version != expected_version):
        raise ValidationError("This return changed. Reload and review the current evidence.")
    if transfer.status != AssetTransfer.PENDING:
        raise ValidationError("This return has already been processed.")
    return asset, transfer


@transaction.atomic(using="default")
def attach_return_evidence(*, actor, transfer, expected_version, upload, note):
    from .forms import _validate_disposal_upload
    _, transfer = _locked(transfer, actor, "record", expected_version)
    if actor.pk == transfer.source_custodian_user_id:
        raise PermissionDenied("A GSO receiving officer must retain the witnessed evidence.")
    if not note.strip() or len(note.strip()) > 240:
        raise ValidationError("Describe the evidence in 1 to 240 characters.")
    if transfer.return_evidence.count() >= 20:
        raise ValidationError("A return supports at most 20 retained documents.")
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("Each file must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    if (transfer.return_evidence.aggregate(total=Sum("size"))["total"] or 0) + size > 100 * 1024 * 1024:
        raise ValidationError("Return documents cannot exceed 100 MB.")
    evidence = AssetReturnEvidence(transfer=transfer, file=upload, original_filename=Path(upload.name).name,
        sha256=digest.hexdigest(), size=size, note=note.strip(), uploaded_by=actor)
    evidence.full_clean()
    evidence.save()
    transfer.state_version += 1
    transfer.save(update_fields=("state_version",))
    _record(transfer, actor, "evidence_added")
    return evidence


def verify_return_evidence(transfer):
    rows = list(transfer.return_evidence.all())
    if not rows:
        raise ValidationError("Retain the witnessed return document before independent confirmation.")
    for row in rows:
        digest, size = hashlib.sha256(), 0
        root = Path(row.file.storage.location).resolve()
        path = root / row.file.name
        try:
            path.resolve().relative_to(root / "inventory" / "custody_returns" / str(transfer.public_id))
            if ".." in Path(row.file.name).parts or path.resolve() != path:
                raise ValueError
        except ValueError as error:
            raise ValidationError("Return evidence has an unsafe location. Investigate before confirmation.") from error
        try:
            with row.file.open("rb") as source:
                for block in source.chunks():
                    digest.update(block)
                    size += len(block)
        except OSError as error:
            raise ValidationError("Return evidence is unavailable. Restore or investigate before confirmation.") from error
        if digest.hexdigest() != row.sha256 or size != row.size:
            raise ValidationError("Return evidence failed its integrity check. Investigate before confirmation.")


@transaction.atomic(using="default")
def confirm_return(*, actor, transfer, expected_version, note):
    asset, transfer = _locked(transfer, actor, "verify", expected_version)
    if actor.pk in (transfer.requested_by_id, transfer.source_custodian_user_id) or transfer.return_evidence.filter(uploaded_by=actor).exists():
        raise PermissionDenied("An independent GSO officer must verify the witnessed return.")
    if not note.strip() or len(note.strip()) > 240:
        raise ValidationError("Record the verification basis in 1 to 240 characters.")
    if (asset.custodian_user_id != transfer.source_custodian_user_id
        or asset.custodian_snapshot != transfer.source_employee_snapshot
        or asset.assigned_department_id != transfer.source_department_id
        or asset.assigned_office != transfer.source_custodian
        or asset.department_id != transfer.destination_department_id or asset.status == Asset.RETIRED):
        raise ValidationError("The asset or its recorded custody changed. Reconcile the return before confirmation.")
    verify_return_evidence(transfer)
    asset.custodian_user = None
    asset.custodian_snapshot = {}
    asset.assigned_department_id = transfer.destination_department_id
    asset.assigned_department_label = transfer.destination_department_label
    asset.assigned_office = transfer.destination_custodian
    asset.last_custody_return = transfer
    asset.updated_by = actor
    asset.save(update_fields=("custodian_user", "custodian_snapshot", "assigned_department_id", "assigned_department_label",
        "assigned_office", "last_custody_return", "updated_by", "updated_at"))
    transfer.status, transfer.acknowledged_by, transfer.acknowledged_at = AssetTransfer.ACCEPTED, actor, timezone.now()
    transfer.return_review_note = note.strip()
    transfer.state_version += 1
    transfer.save(update_fields=("status", "acknowledged_by", "acknowledged_at", "return_review_note", "state_version"))
    snapshot = asset_snapshot(asset)
    snapshot.update(return_condition=transfer.return_condition, return_reference=transfer.reference)
    AssetAuditEvent.objects.create(asset=asset, department_id=asset.department_id, actor=actor,
        action=AssetAuditEvent.RETURNED, snapshot=snapshot)
    _record(transfer, actor, "confirmed")
    return transfer


@transaction.atomic(using="default")
def cancel_return(*, actor, transfer, expected_version, note):
    _, transfer = _locked(transfer, actor, "record", expected_version)
    if actor.pk == transfer.source_custodian_user_id:
        raise PermissionDenied("A different GSO officer must manage your witnessed return.")
    if not note.strip() or len(note.strip()) > 240:
        raise ValidationError("Explain the cancellation in 1 to 240 characters.")
    transfer.status, transfer.cancelled_by, transfer.cancelled_at = AssetTransfer.CANCELLED, actor, timezone.now()
    transfer.cancellation_reason = note.strip()
    transfer.state_version += 1
    transfer.save(update_fields=("status", "cancelled_by", "cancelled_at", "cancellation_reason", "state_version"))
    _record(transfer, actor, "cancelled")
    return transfer
