"""Operational repair history; recorded costs never change financial valuation."""
import hashlib
from pathlib import Path

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .access import in_gso_scope, asset_in_scope
from .models import (Asset, AssetAuditEvent, AssetDisposalCase, AssetTransfer,
                     AssetMaintenanceCase, AssetMaintenanceEvent, AssetMaintenanceEvidence)
from .services import asset_snapshot, _editable_data


def can_manage_maintenance(actor, asset=None):
    if apps.is_installed("vouchers"):
        from vouchers.roles import is_finance_uat_viewer
        from vouchers.access import has_explicit_permission
        granted = not is_finance_uat_viewer(actor) and has_explicit_permission(
            actor, "inventory.manage_assetmaintenancecase")
    else:
        granted = actor.has_perm("inventory.manage_assetmaintenancecase")
    return bool(in_gso_scope(actor) and granted and (asset is None or asset_in_scope(actor, asset)))


def _require(actor, asset):
    if not can_manage_maintenance(actor, asset):
        raise PermissionDenied


def require_no_open_maintenance(asset):
    # Call only after locking the asset, as all maintenance writers do.
    if asset.maintenance_cases.filter(status=AssetMaintenanceCase.OPEN).exists():
        raise ValidationError("Close the asset's maintenance case before editing, handoff or disposal.")


def _record(case, actor, action):
    fields = ("status", "state_version", "prior_asset_status", "reported_date", "problem", "provider",
              "work_performed", "documented_cost", "cost_reference", "finished_date",
              "resulting_asset_status", "closure_note", "opened_by_id", "closed_by_id", "closed_at")
    snapshot = {name: str(getattr(case, name)) if getattr(case, name) is not None else None for name in fields}
    snapshot.update(public_id=str(case.public_id), asset_public_id=str(case.asset.public_id),
                    evidence=list(case.evidence.values("id", "sha256", "size", "note", "original_filename")))
    AssetMaintenanceEvent.objects.create(case=case, actor=actor, action=action, snapshot=snapshot)


def _asset_status(case, actor, status, action):
    asset = case.asset
    asset.status, asset.updated_by = status, actor
    asset.save(update_fields=("status", "updated_by", "updated_at"))
    snapshot = asset_snapshot(asset)
    snapshot.update(maintenance_case=str(case.public_id), maintenance_action=action)
    AssetAuditEvent.objects.create(asset=asset, department_id=asset.department_id,
                                  actor=actor, action=AssetAuditEvent.UPDATED, snapshot=snapshot)


def _validate(case):
    if isinstance(case.documented_cost, (float, bool)):
        raise ValidationError("Record an exact decimal cost, or leave it unknown.")
    case.full_clean()
    if not case.problem.strip():
        raise ValidationError("Describe the reported problem.")
    if case.reported_date > timezone.localdate():
        raise ValidationError("The reported date cannot be in the future.")
    if case.finished_date and not case.reported_date <= case.finished_date <= timezone.localdate():
        raise ValidationError("The finish date must be between the report date and today.")


@transaction.atomic
def open_maintenance(*, actor, asset, data):
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    _require(actor, asset)
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    require_no_open_maintenance(asset)
    if asset.status == Asset.RETIRED:
        raise ValidationError("Retired assets cannot enter maintenance.")
    if asset.transfers.filter(status=AssetTransfer.PENDING).exists() or asset.disposal_cases.filter(
        status__in=(AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
                    AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED)
    ).exists():
        raise ValidationError("Resolve the open handoff or disposal case before maintenance.")
    data = _editable_data(data, {"reported_date", "problem", "provider"})
    case = AssetMaintenanceCase(asset=asset, opened_by=actor, prior_asset_status=asset.status, **data)
    _validate(case)
    case.save()
    _asset_status(case, actor, Asset.MAINTENANCE, "opened")
    _record(case, actor, "opened")
    return case


def _locked(case, actor, expected_version):
    # Consistent asset -> case lock order also serializes conflicting lifecycle starts.
    asset = Asset.objects.select_for_update().get(pk=case.asset_id)
    _require(actor, asset)
    case = AssetMaintenanceCase.objects.select_for_update().get(pk=case.pk, asset=asset)
    case.asset = asset
    if case.status != case.OPEN or case.state_version != expected_version:
        raise ValidationError("This maintenance case changed or closed. Reload before continuing.")
    if asset.status != Asset.MAINTENANCE:
        raise ValidationError("The asset status conflicts with its open case. Investigate before continuing.")
    return case


@transaction.atomic
def update_maintenance(*, actor, case, expected_version, data):
    case = _locked(case, actor, expected_version)
    for name, value in _editable_data(data, {"reported_date", "problem", "provider", "work_performed",
                                           "documented_cost", "cost_reference"}).items():
        setattr(case, name, value)
    _validate(case)
    case.state_version += 1
    case.save()
    _record(case, actor, "work_recorded")
    return case


def verify_maintenance_evidence(case):
    for row in case.evidence.all():
        digest, size = hashlib.sha256(), 0
        try:
            with row.file.open("rb") as source:
                for block in source.chunks():
                    digest.update(block)
                    size += len(block)
        except OSError as error:
            raise ValidationError("Retained evidence is unavailable. Restore or investigate before closing.") from error
        if digest.hexdigest() != row.sha256 or size != row.size:
            raise ValidationError("Retained evidence failed its integrity check. Investigate before closing.")


@transaction.atomic
def attach_maintenance_evidence(*, actor, case, expected_version, upload, note):
    from .forms import _validate_disposal_upload
    case = _locked(case, actor, expected_version)
    if not note.strip() or len(note.strip()) > 240:
        raise ValidationError("Describe the evidence in 1 to 240 characters.")
    if case.evidence.count() >= 20:
        raise ValidationError("A case supports at most 20 retained documents.")
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("Each file must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    if (case.evidence.aggregate(total=Sum("size"))["total"] or 0) + size > 100 * 1024 * 1024:
        raise ValidationError("Case documents cannot exceed 100 MB.")
    evidence = AssetMaintenanceEvidence(case=case, file=upload, original_filename=Path(upload.name).name,
                                        sha256=digest.hexdigest(), size=size, note=note.strip(), uploaded_by=actor)
    evidence.full_clean()
    evidence.save()
    case.state_version += 1
    case.save(update_fields=("state_version",))
    _record(case, actor, "evidence_added")
    return evidence


@transaction.atomic
def close_maintenance(*, actor, case, expected_version, action, finished_date, note, outcome=""):
    case = _locked(case, actor, expected_version)
    if action not in (case.COMPLETED, case.CANCELLED) or not note.strip():
        raise ValidationError("Choose completion or cancellation and explain the outcome.")
    if action == case.COMPLETED:
        if outcome not in (Asset.ACTIVE, Asset.MAINTENANCE) or not case.work_performed.strip():
            raise ValidationError("Record the work and choose returned to service or still unserviceable.")
        if case.documented_cost is not None and case.documented_cost > 0 and (
            not case.cost_reference.strip() or not case.evidence.exists()
        ):
            raise ValidationError("A positive recorded cost needs a reference and retained supporting document.")
        result = outcome
    else:
        # Cancelling does not pretend that work restored serviceability.
        result = case.prior_asset_status
    if not finished_date:
        raise ValidationError("Record the finish or cancellation date.")
    verify_maintenance_evidence(case)
    case.status, case.finished_date, case.closure_note = action, finished_date, note.strip()
    case.resulting_asset_status, case.closed_by, case.closed_at = result, actor, timezone.now()
    _validate(case)
    case.state_version += 1
    case.save()
    _asset_status(case, actor, result, action)
    _record(case, actor, action)
    return case
