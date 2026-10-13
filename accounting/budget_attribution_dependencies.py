"""Explicit joint proposal dependencies, never fabricated predecessor approvals."""
from django.core.exceptions import ValidationError


def reference(data):
    return {"public_id": data["public_id"], "proposal_checksum": data["proposal_checksum"]}


def manifest(parent):
    inherited = parent.get("dependencies", {})
    if not isinstance(inherited, dict):
        raise ValidationError("Retain a complete explicit predecessor proposal map.")
    return {**inherited, str(parent["entry_id"]): reference(parent)}


def pending_parent(record, records):
    from .budget_attributions import projection, verify
    if not record.dependencies:
        return None
    parent = records.get(record.entry.reversal_of_id)
    if (parent is None or parent.status != parent.SUBMITTED or parent.batch_id != record.batch_id
            or parent.department_id != record.department_id or parent.entry.fund_id != record.entry.fund_id
            or parent.prepared_by_id != record.prepared_by_id or parent.prepared_at != record.prepared_at
            or parent.period_start != record.period_start or parent.period_end != record.period_end):
        raise ValidationError("Retain the actual predecessor proposal in this same pending review batch.")
    verify(parent)
    data = projection(parent)
    if record.dependencies != manifest(data):
        raise ValidationError("The joint proposal must retain its complete exact predecessor proposal chain.")
    return data


def verify_approved(payload, data, entries):
    from .budget_attributions import _base_approved_head
    dependencies = data.get("dependencies", {})
    if not dependencies:
        return
    parent_id = entries[data["entry_id"]]["reversal_of_id"]
    parent = _base_approved_head(payload, parent_id, entries=entries)
    if parent is None or dependencies != manifest(parent):
        raise ValidationError("The current joint predecessor no longer matches the retained proposal dependency.")
    try:
        for entry_id, expected in dependencies.items():
            if str(int(entry_id)) != entry_id:
                raise ValueError
            predecessor = _base_approved_head(payload, int(entry_id), entries=entries)
            if (predecessor is None or expected != reference(predecessor)
                    or predecessor["batch_id"] != data["batch_id"]
                    or predecessor["prepared_by_id"] != data["prepared_by_id"]
                    or predecessor["prepared_at"] != data["prepared_at"]
                    or predecessor["reviewed_by_id"] != data["reviewed_by_id"]
                    or predecessor["reviewed_at"] != data["reviewed_at"]):
                raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Each joint dependency requires the exact same independently approved batch decision.") from exc
