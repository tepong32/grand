"""Scoped property sharing and native dimensions; writes only the default store."""
from datetime import date
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounting.access import can_view_ledger, department_for_user
from accounting.models import Fund, LedgerAccount, ResponsibilityCenter
from departments.models import Department
from vouchers.access import has_explicit_permission
from vouchers.models import VoucherCase
from vouchers.roles import is_finance_uat_viewer
from inventory import property_determinations as properties
from inventory.models import PropertyDetermination
from . import journal_mappings
from .models import PropertyFinanceLink as Link, PropertyFinanceLinkEvent as Event, ReceiptJournalMapping, ReceiptClaimAttribution


def granted(actor, action):
    return has_explicit_permission(actor, f"inventory_finance.{action}_propertyfinancelink")


def gso_allowed(actor, determination, action="view"):
    owner = department_for_user(actor)
    return bool(owner and owner.pk == determination.asset.department_id) and properties.can_act(actor, "view", determination.asset) and (
        any(granted(actor, a) for a in ("view", "request")) if action == "view" else
        granted(actor, "request") and not is_finance_uat_viewer(actor))


def finance_allowed(actor, owner_id, action="view"):
    owner = department_for_user(actor)
    return bool(owner and owner.pk == owner_id and can_view_ledger(actor) and (
        any(granted(actor, a) for a in ("view", "propose", "review")) if action == "view" else
        granted(actor, action) and not is_finance_uat_viewer(actor)))


def visible(actor):
    rows = Link.objects.all()
    owner = department_for_user(actor)
    if not owner:
        return rows.none()
    scope = Q(pk__in=[])
    if properties.can_act(actor, "view") and any(granted(actor, a) for a in ("view", "request")):
        scope |= Q(determination__asset__department_id=owner.pk)
    if finance_allowed(actor, owner.pk):
        scope |= Q(finance_department_id=owner.pk)
    return rows.filter(scope)


def identity(raw, *, optional=False):
    if optional and raw in (None, ""):
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("Select a valid source identity.") from error


def note(raw):
    result = str(raw or "").strip()
    if not result or len(result) > 1000:
        raise ValidationError("Record a documentary reason of 1 to 1,000 characters.")
    return result


def snapshot(row):
    result = {}
    for field in row._meta.concrete_fields:
        if field.primary_key or field.generated:
            continue
        raw = getattr(row, field.attname)
        result[field.attname] = str(raw) if isinstance(raw, UUID) else properties.value(raw)
    return result


def event(row, actor, action):
    data = snapshot(row)
    Event.objects.create(link=row, actor=actor, action=action, snapshot=data,
        checksum=properties.checksum({"actor": actor.pk, "action": action, "snapshot": data}))


def verify(row):
    events = list(row.events.all())
    if not events or len(events) != row.state_version:
        raise ValidationError("Property link history is incomplete.")
    for version, entry in enumerate(events, 1):
        if entry.snapshot.get("state_version") != version or entry.checksum != properties.checksum({
                "actor": entry.actor_id, "action": entry.action, "snapshot": entry.snapshot}):
            raise ValidationError("Property link history failed its integrity check.")
    if events[-1].snapshot != snapshot(row):
        raise ValidationError("The property link no longer reproduces its retained history.")


def property_basis(determination):
    properties.verify_history(determination)
    properties.verify_source(determination)
    latest = properties.latest_verified(determination.asset)
    if (determination.status != "verified" or not latest or latest.pk != determination.pk
            or determination.asset.quantity != 1
            or properties.source_basis(determination.asset) != determination.source_snapshot):
        raise ValidationError("Use the current verified property document on an unchanged source basis.")
    return properties.snapshot(determination)


@transaction.atomic(using="default", durable=True)
def request_link(*, actor, determination_id, finance_department_id, reason, request_id, expected_property, expected_predecessor):
    determination = PropertyDetermination.objects.select_related("asset").get(public_id=identity(determination_id))
    if not gso_allowed(actor, determination, "request"):
        raise PermissionDenied
    asset = properties.lock_asset(determination.asset_id)
    determination = PropertyDetermination.objects.select_for_update().get(pk=determination.pk)
    determination.asset = asset
    if not gso_allowed(actor, determination, "request"):
        raise PermissionDenied
    reason, request_id = note(reason), identity(request_id)
    owner = Department.objects.filter(pk=finance_department_id).exclude(name="---select one---").first()
    if not owner:
        raise ValidationError("Select the native department responsible for the Finance association.")
    existing = Link.objects.filter(public_id=request_id).first()
    if existing:
        verify(existing)
        if (existing.determination_id == determination.pk and existing.finance_department_id == owner.pk
                and existing.requested_by_id == actor.pk and existing.request_reason == reason
                and existing.property_snapshot == expected_property
                and (str(existing.predecessor.public_id) if existing.predecessor_id else None) == expected_predecessor):
            properties.verify_source(determination)
            return existing
        raise ValidationError("This request identity belongs to different property sharing content.")
    previous = determination.finance_links.order_by("-pk").first()
    for prior in determination.finance_links.all():
        verify(prior)
    if (expected_property != property_basis(determination)
            or expected_predecessor != (str(previous.public_id) if previous else None)):
        raise ValidationError("The property or prior request changed. Reopen the sharing preview.")
    if determination.finance_links.filter(status__in=("requested", "proposed", "approved")).exists():
        raise ValidationError("Withdraw or decide the existing link before requesting its replacement.")
    row = Link(determination=determination, finance_department=owner, predecessor=previous,
        public_id=request_id, property_snapshot=expected_property,
        owner_snapshot={"id": owner.pk, "slug": owner.slug, "name": owner.name}, request_reason=reason, requested_by=actor)
    row.full_clean()
    row.save()
    event(row, actor, "requested")
    return row


def _version(row, expected_version):
    if type(expected_version) is not int or expected_version != row.state_version:
        raise ValidationError("This link changed. Reload before deciding it.")


def _lock(actor, link_id, mapping_id=None):
    candidate = visible(actor).select_related("determination__asset").filter(public_id=identity(link_id)).first()
    if not candidate:
        raise PermissionDenied
    # Journal path prefixes the common receipt/asset locks with the voucher case.
    mapping = None
    selected = identity(mapping_id, optional=True) if mapping_id else None
    if selected or candidate.journal_mapping_id:
        mappings = journal_mappings.visible_mappings(actor)
        mapping = mappings.filter(public_id=selected).first() if selected else mappings.filter(pk=candidate.journal_mapping_id).first()
        if not mapping:
            raise PermissionDenied
        VoucherCase.objects.select_for_update().get(pk=mapping.claim.case_id)
    asset = properties.lock_asset(candidate.determination.asset_id)
    determination = PropertyDetermination.objects.select_for_update().get(pk=candidate.determination_id)
    determination.asset = asset
    row = Link.objects.select_for_update().get(pk=candidate.pk)
    row.determination = determination
    if not visible(actor).filter(pk=row.pk).exists():
        raise PermissionDenied
    verify(row)
    if mapping:
        ReceiptClaimAttribution.objects.select_for_update().get(pk=mapping.claim_id)
        mapping = ReceiptJournalMapping.objects.select_for_update().select_related("claim__receipt_line", "claim__case__configuration_release").get(pk=mapping.pk)
        if (mapping.status != mapping.APPROVED
                or mapping.claim.receipt_line.registered_asset_id != asset.pk
                or mapping.claim.finance_department_id != row.finance_department_id):
            raise ValidationError("Select a current approved recognition mapping for this exact asset and Finance owner.")
        journal_mappings._lock_source(mapping.claim, mapping.posting_request.public_id)
    return row, mapping


def dimensions(*, actor, owner_id, as_of, fund_id, account_id, center_id=None, lock=False):
    if not finance_allowed(actor, owner_id):
        raise PermissionDenied
    if type(as_of) is not date or as_of > timezone.localdate():
        raise ValidationError("Supply the documented association date, no later than today.")
    result = {}
    definitions = (
        ("fund", Fund, fund_id, ("name", "category")),
        ("account", LedgerAccount, account_id, ("title", "account_type", "normal_balance", "government_account_code", "subsidiary_reference_type", "allow_posting")),
        ("center", ResponsibilityCenter, center_id, ("name", "office_id", "office_code")),
    )
    for label, model, public_id, fields in definitions:
        public_id = identity(public_id, optional=label == "center")
        if public_id is None:
            result[label] = None
            continue
        rows = model.objects.select_for_update() if lock else model.objects.all()
        dimension = rows.filter(public_id=public_id, department_id=owner_id).first()
        if (not dimension or not dimension.is_active
                or dimension.effective_from and dimension.effective_from > as_of
                or dimension.effective_to and dimension.effective_to < as_of):
            raise ValidationError("Select active dimensions of the selected Finance owner effective on the supplied date.")
        if label == "account" and (not dimension.allow_posting or dimension.account_type not in ("asset", "expense")):
            raise ValidationError("Select a posting-enabled asset or expense account; this does not determine its proper treatment.")
        result[label] = {"uuid": str(dimension.public_id), "owner_id": dimension.department_id,
            "code": dimension.code, "is_active": dimension.is_active,
            "effective_from": properties.value(dimension.effective_from), "effective_to": properties.value(dimension.effective_to),
            **{field: getattr(dimension, field) for field in fields}}
    return result


def _property_current(row):
    if property_basis(row.determination) != row.property_snapshot:
        raise ValidationError("The shared property basis changed. Withdraw this link and request a replacement.")


def _mapping_basis(mapping, actor, dimension_basis):
    if not mapping:
        return None
    observed = journal_mappings.current(mapping, actor)
    source = observed["journal"]
    for key in ("fund", "account", "center"):
        if (source[key]["uuid"] if source[key] else None) != (dimension_basis[key]["uuid"] if dimension_basis[key] else None):
            raise ValidationError("Selected dimensions must match the exact retained recognition mapping.")
    return {"uuid": str(mapping.public_id), "version": mapping.state_version,
        "proposal_checksum": mapping.proposal_checksum, "evidence": observed}


def _save(row, actor, action):
    row.state_version += 1
    row._workflow_write = True
    try:
        row.save()
    finally:
        row._workflow_write = False
    event(row, actor, action)
    return row


@transaction.atomic(using="finance")
@transaction.atomic(using="default", durable=True)
def propose(*, actor, link_id, expected_version, as_of, fund_id, account_id, center_id=None,
            mapping_id=None, reason, expected_dimensions):
    row, mapping = _lock(actor, link_id, mapping_id)
    if not finance_allowed(actor, row.finance_department_id, "propose"):
        raise PermissionDenied
    _version(row, expected_version)
    if row.status != "requested":
        raise ValidationError("Only a requested link can receive a proposal.")
    _property_current(row)
    basis = dimensions(actor=actor, owner_id=row.finance_department_id, as_of=as_of,
        fund_id=fund_id, account_id=account_id, center_id=center_id, lock=True)
    if basis != expected_dimensions:
        raise ValidationError("The dimension preview changed. Inspect the current Finance source.")
    row.as_of, row.fund_public_id, row.account_public_id = as_of, identity(fund_id), identity(account_id)
    row.center_public_id, row.journal_mapping = identity(center_id, optional=True), mapping
    row.dimension_snapshot, row.mapping_snapshot = basis, _mapping_basis(mapping, actor, basis)
    row.proposal_reason, row.proposed_by, row.proposed_at = note(reason), actor, timezone.now()
    row.status = "proposed"
    return _save(row, actor, "proposed")


def current(row, actor):
    if not visible(actor).filter(pk=row.pk).exists():
        raise PermissionDenied
    row = Link.objects.select_related("determination__asset", "journal_mapping").get(pk=row.pk)
    verify(row)
    _property_current(row)
    if row.status != "approved":
        raise ValidationError("Only an approved association can supply current dimensions.")
    if not finance_allowed(actor, row.finance_department_id):
        raise PermissionDenied
    basis = dimensions(actor=actor, owner_id=row.finance_department_id, as_of=row.as_of,
        fund_id=row.fund_public_id, account_id=row.account_public_id, center_id=row.center_public_id)
    if basis != row.dimension_snapshot:
        raise ValidationError("The native dimensions changed. Review the retained association.")
    if row.journal_mapping_id:
        if not journal_mappings.visible_mappings(actor).filter(pk=row.journal_mapping_id).exists():
            raise PermissionDenied
        mapping = row.journal_mapping
        if mapping.status != mapping.APPROVED or _mapping_basis(mapping, actor, basis) != row.mapping_snapshot:
            raise ValidationError("The supporting recognition mapping changed.")
    return basis


@transaction.atomic(using="finance")
@transaction.atomic(using="default", durable=True)
def decide(*, actor, link_id, expected_version, action, reason):
    if action not in ("approve", "reject", "withdraw"):
        raise ValidationError("Choose approval, rejection or withdrawal.")
    # Withdrawal must remain possible when Finance sources are missing or access
    # to their optional mapping is revoked. It makes no current-source assertion.
    if action == "approve":
        row, mapping = _lock(actor, link_id)
    else:
        candidate = visible(actor).select_related("determination__asset").filter(public_id=identity(link_id)).first()
        if not candidate:
            raise PermissionDenied
        asset = properties.lock_asset(candidate.determination.asset_id)
        determination = PropertyDetermination.objects.select_for_update().get(pk=candidate.determination_id)
        determination.asset = asset
        row = Link.objects.select_for_update().get(pk=candidate.pk)
        row.determination = determination
        verify(row)
        mapping = None
    finance = finance_allowed(actor, row.finance_department_id, "review")
    if not (finance or action == "withdraw" and gso_allowed(actor, row.determination, "request")):
        raise PermissionDenied
    _version(row, expected_version)
    if row.status in ("withdrawn", "rejected") or action == "approve" and row.status != "proposed" or action == "reject" and row.status == "approved":
        raise ValidationError("This action is not available in the current link state.")
    if action != "withdraw" and actor.pk in (row.requested_by_id, row.proposed_by_id):
        raise PermissionDenied("A different officer must review the association.")
    if action == "approve":
        _property_current(row)
        basis = dimensions(actor=actor, owner_id=row.finance_department_id, as_of=row.as_of,
            fund_id=row.fund_public_id, account_id=row.account_public_id, center_id=row.center_public_id, lock=True)
        if basis != row.dimension_snapshot or _mapping_basis(mapping, actor, basis) != row.mapping_snapshot:
            raise ValidationError("The proposed Finance source changed. Reject or withdraw and replace this link.")
    row.status = {"approve": "approved", "reject": "rejected", "withdraw": "withdrawn"}[action]
    row.decided_by, row.decided_at, row.decision_note = actor, timezone.now(), note(reason)
    return _save(row, actor, row.status)
