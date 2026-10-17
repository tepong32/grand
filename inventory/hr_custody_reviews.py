"""Documented GSO custody findings; never an HR clearance or Finance instruction."""
import hashlib
import json
from pathlib import Path
from uuid import UUID

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .access import department_for_user, gso_department_for_user, has_inventory_permission
from .models import Asset, AssetTransfer, EmployeeCustodyReview as Review, EmployeeCustodyReviewEvent as Event


def can_act(actor, action, review=None):
    if action not in ("view", "record", "review") or not all(apps.is_installed(name)
            for name in ("profiles", "departments", "vouchers")):
        return False
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False):
        return False
    department = department_for_user(actor)
    owner = gso_department_for_user(actor)
    if not department or not owner or department.pk != owner.pk:
        return False
    actions = ("view", "record", "review") if action == "view" else (action,)
    return bool((review is None or review.department_id == owner.pk) and any(
        has_inventory_permission(actor, f"{name}_employeecustodyreview", mutation=action != "view")
        for name in actions))


def visible_reviews(actor):
    if not can_act(actor, "view"):
        return Review.objects.none()
    return Review.objects.filter(department_id=department_for_user(actor).pk)


def _require(actor, action, review=None):
    if not can_act(actor, action, review):
        raise PermissionDenied


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _text(value, maximum=4000):
    value = str(value or "").strip()
    if not value or len(value) > maximum:
        raise ValidationError(f"Record a value of 1 to {maximum:,} characters.")
    return value


def employee_label(*, actor, employee):
    """Minimal current directory identity, or explicitly linked historical custody."""
    _require(actor, "record")
    owner = department_for_user(actor)
    historical = Asset.objects.filter(department_id=owner.pk).filter(
        Q(custodian_user=employee) | Q(transfers__source_custodian_user=employee)
        | Q(transfers__destination_custodian_user=employee)).exists()
    from profiles.services.profile_service import can_view_profile
    if not historical and not (employee.is_active and can_view_profile(actor, employee)
            and department_for_user(employee)):
        raise PermissionDenied("Select a visible employee or an explicitly linked historical custodian.")
    # The user account remains the native identity. No payroll or HR document fields.
    return employee.get_full_name().strip() or employee.username


def _asset_ids(review):
    tracked = [row["id"] for row in review.source_snapshot.get("assets", [])]
    return set(Asset.objects.filter(department_id=review.department_id).filter(
        Q(pk__in=tracked) | Q(custodian_user_id=review.employee_id)
        | (Q(transfers__status=AssetTransfer.PENDING) & (
            Q(transfers__source_custodian_user_id=review.employee_id)
            | Q(transfers__destination_custodian_user_id=review.employee_id)))
    ).values_list("pk", flat=True))


def capture(review):
    """As-of observation. Mutation callers acquire the ordered source locks first."""
    ids = _asset_ids(review)
    old_ids = {row["id"]: row["public_id"] for row in review.source_snapshot.get("assets", [])}
    assets = list(Asset.objects.filter(pk__in=ids, department_id=review.department_id).order_by("pk"))
    if any(old_ids.get(asset.pk, str(asset.public_id)) != str(asset.public_id) for asset in assets) or not set(old_ids) <= ids:
        raise ValidationError("A tracked asset is missing or changed identity. Investigate the retained record.")
    rows = []
    for asset in assets:
        pending = list(asset.transfers.filter(status=AssetTransfer.PENDING).order_by("pk").values(
            "id", "public_id", "kind", "status", "state_version", "source_custodian_user_id",
            "destination_custodian_user_id", "reference"))
        for movement in pending:
            movement["public_id"] = str(movement["public_id"])
        rows.append({"id": asset.pk, "public_id": str(asset.public_id), "asset_name": asset.asset_name,
            "property_tag": asset.property_tag, "quantity": asset.quantity, "status": asset.status,
            "custodian_user_id": asset.custodian_user_id, "custodian_snapshot": asset.custodian_snapshot,
            "assigned_department_id": asset.assigned_department_id, "assigned_office": asset.assigned_office,
            "last_return_id": asset.last_custody_return_id, "pending": pending})
    return {"department_id": review.department_id, "employee_id": review.employee_id, "assets": rows}


def _outcome(snapshot):
    employee_id = snapshot["employee_id"]
    outstanding = any(row["custodian_user_id"] == employee_id or any(
        employee_id in (movement["source_custodian_user_id"], movement["destination_custodian_user_id"])
        for movement in row["pending"]) for row in snapshot["assets"])
    return "outstanding" if outstanding else "no_current_named_items"


def _snapshot(review):
    fields = ("department_id", "department_label", "employee_id", "employee_label", "reference", "request_kind",
        "original_filename", "sha256", "size", "findings", "coverage_note", "source_snapshot", "status",
        "outcome", "state_version", "created_by_id", "submitted_by_id", "reviewed_by_id", "review_note")
    result = {name: getattr(review, name) for name in fields}
    result.update(public_id=str(review.public_id), file=review.file.name)
    for name in ("request_date", "created_at", "submitted_at", "reviewed_at"):
        value = getattr(review, name)
        result[name] = value.isoformat() if value else None
    return result


def _record(review, actor, action):
    snapshot = _snapshot(review)
    payload = {"actor_id": actor.pk, "action": action, "snapshot": snapshot}
    Event.objects.create(review=review, actor=actor, action=action, snapshot=snapshot, checksum=_digest(payload))


def verify_history(review):
    events = list(review.events.order_by("pk"))
    if not events or len(events) != review.state_version:
        raise ValidationError("The review history is incomplete. Investigate before continuing.")
    for version, event in enumerate(events, 1):
        if event.snapshot.get("state_version") != version or event.checksum != _digest({
                "actor_id": event.actor_id, "action": event.action, "snapshot": event.snapshot}):
            raise ValidationError("The review history failed its integrity check.")
    if events[-1].snapshot != _snapshot(review):
        raise ValidationError("The review no longer reproduces its retained history.")


def verify_source(review):
    root = Path(review.file.storage.location).resolve()
    path = root / review.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "custody-reviews" / str(review.public_id))
        if ".." in Path(review.file.name).parts or path.resolve() != path:
            raise ValueError
    except ValueError as error:
        raise ValidationError("The HR request evidence has an unsafe location.") from error
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
    except OSError as error:
        raise ValidationError("The HR request evidence is unavailable; restore or investigate it.") from error
    if size != review.size or digest.hexdigest() != review.sha256:
        raise ValidationError("The HR request evidence failed its integrity check.")


@transaction.atomic(using="default")
def create_review(*, actor, employee, reference, request_date, request_kind, upload, request_id):
    from .forms import _validate_disposal_upload
    _require(actor, "record")
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid review request identity.")
    reference = _text(reference, 160)
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("The HR request document must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    owner = department_for_user(actor)
    # Serialize creation with named handoffs and competing open review requests.
    employee = get_user_model().objects.select_for_update().only(
        "pk", "username", "first_name", "middle_name", "last_name", "ext_name", "is_active").get(pk=employee.pk)
    label = employee_label(actor=actor, employee=employee)
    existing = Review.objects.filter(public_id=request_id).first()
    if existing:
        if (existing.created_by_id != actor.pk or existing.department_id != owner.pk
                or existing.employee_id != employee.pk or existing.reference != reference
                or str(existing.request_date) != str(request_date) or existing.request_kind != request_kind
                or existing.sha256 != digest.hexdigest() or existing.size != size):
            raise ValidationError("This request identity belongs to different recorded content.")
        verify_history(existing)
        verify_source(existing)
        return existing
    review = Review(public_id=request_id, department_id=owner.pk, department_label=owner.name,
        employee=employee, employee_label=label, reference=reference, request_date=request_date,
        request_kind=request_kind, file=upload, original_filename=Path(upload.name).name,
        sha256=digest.hexdigest(), size=size, created_by=actor)
    review.source_snapshot = capture(review)
    review.full_clean()
    if review.request_date > timezone.localdate():
        raise ValidationError("The supplied request date cannot be in the future.")
    # File storage is not transactional; retain any orphan for reconciliation if DB commit fails.
    review.save()
    _record(review, actor, "recorded")
    return review


def _locked(review, actor, action, expected_version, *, custody=False):
    _require(actor, action, review)
    if custody:
        review = Review.objects.get(pk=review.pk)
        ids = _asset_ids(review)
        list(Asset.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        get_user_model().objects.select_for_update().get(pk=review.employee_id)
    review = Review.objects.select_for_update().get(pk=review.pk)
    _require(actor, action, review)
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or review.state_version != expected_version:
        raise ValidationError("The review changed. Reload its current findings.")
    verify_history(review)
    if custody and ids != _asset_ids(review):
        raise ValidationError("The custody asset set changed while acquiring locks. Reload and retry.")
    return review


def _save(review, actor, action):
    review.state_version += 1
    review._workflow_write = True
    review.full_clean()
    review.save()
    _record(review, actor, action)
    return review


@transaction.atomic(using="default")
def edit_findings(*, actor, review, expected_version, findings, coverage_note):
    review = _locked(review, actor, "record", expected_version)
    if review.status != Review.DRAFT:
        raise ValidationError("Only a draft can be edited.")
    review.findings, review.coverage_note = _text(findings), _text(coverage_note)
    return _save(review, actor, "findings_saved")


@transaction.atomic(using="default")
def submit_review(*, actor, review, expected_version, expected_source):
    review = _locked(review, actor, "record", expected_version, custody=True)
    if review.status != Review.DRAFT or actor.pk == review.employee_id:
        raise ValidationError("A different GSO officer must submit draft findings.")
    _text(review.findings)
    _text(review.coverage_note)
    verify_source(review)
    source = capture(review)
    if source != expected_source:
        raise ValidationError("The custody findings changed. Review the current asset list before submitting.")
    review.source_snapshot = source
    review.submitted_by, review.submitted_at = actor, timezone.now()
    review.status, review.outcome = Review.SUBMITTED, _outcome(source)
    return _save(review, actor, "submitted")


@transaction.atomic(using="default")
def decide_review(*, actor, review, expected_version, action, note):
    if action not in ("review", "return", "cancel"):
        raise ValidationError("Choose a supported review action.")
    review = _locked(review, actor, "record" if action == "cancel" else "review", expected_version,
        custody=action == "review")
    if review.status not in (Review.DRAFT, Review.SUBMITTED) or (action != "cancel" and review.status != Review.SUBMITTED):
        raise ValidationError("This review is not open for that action.")
    if action != "cancel" and actor.pk in (review.created_by_id, review.submitted_by_id, review.employee_id):
        raise PermissionDenied("A different GSO officer must independently review these findings.")
    review.review_note = _text(note)
    if action == "review":
        verify_source(review)
        if capture(review) != review.source_snapshot:
            raise ValidationError("Custody changed since submission. Return the case for updated findings.")
        review.status = Review.REVIEWED
        review.reviewed_by, review.reviewed_at = actor, timezone.now()
    elif action == "return":
        review.status, review.outcome = Review.DRAFT, ""
        review.submitted_by, review.submitted_at = None, None
    else:
        review.status = Review.CANCELLED
    return _save(review, actor, action)
