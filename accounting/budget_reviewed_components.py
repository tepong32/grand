"""Bind classification capacity to a captured, independently reviewed source.

This establishes component identity, not application allocation or certification.
Use trusted server captures/retained artifacts; checksums do not authenticate input
received from an arbitrary client. No database reads or financial holds are added.
"""
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError

from .budget_actuals import money
from .budget_attributions import _approved_head, source_entries
from .budget_claim_components import BASES, Component
from .budget_claim_sources import verified_claims
from .budget_native_sources import verify


@dataclass(frozen=True)
class ReviewedComponents:
    source_line_id: int
    source_entry_id: int
    attribution_id: str
    decision_checksum: str
    components: tuple[Component, ...]


def source_components(captured, source_line_id, *, expected_attribution_id=None):
    """Require the full credit partition; never infer undeclared component basis.

    Keys use the immutable approval UUID and normalized allocation ordinal, so even
    equal-valued components remain distinct. A successor approval never silently
    reuses the old keys. An old retained capture still reproduces its original keys.
    """
    payload = verify(captured)
    if type(source_line_id) is not int or source_line_id <= 0:
        raise ValidationError("Select an exact original source credit.")
    entries = source_entries(payload)
    found = [(entry, line) for entry in entries.values() for line in entry["lines"]
             if line["id"] == source_line_id]
    if len(found) != 1:
        raise ValidationError("The original source credit is absent from this capture.")
    entry, line = found[0]
    if (entry["reversal_of_id"] or entry["lineage"]["issue"] or line["payable_origin_id"]
            or line["account"]["account_type"] != "liability"
            or money(line["debit"]) != 0 or money(line["credit"]) <= 0):
        raise ValidationError("Component capacity requires the original liability credit, not an application or reversal.")
    verified_claims(captured, entry_ids=[entry["id"]])
    approval = _approved_head(payload, entry["id"], entries=entries)
    if approval is None:
        raise ValidationError("Independently review the original component partition first.")
    if expected_attribution_id is not None and expected_attribution_id != approval["public_id"]:
        raise ValidationError("The reviewed source component version changed; retain the old evidence and review a new allocation.")
    components = []
    for ordinal, row in enumerate(approval["allocations"]):
        if row["line_id"] != source_line_id:
            continue
        basis = row.get("claim_component_basis")
        if (not isinstance(basis, str) or basis not in BASES or row["disposition"] != "exclude"
                or money(row["amount"]) <= 0 or money(row["signed_amount"]) != -money(row["amount"])):
            raise ValidationError("Every source-credit component needs its explicit independently reviewed basis.")
        components.append(Component(f"{approval['public_id']}:{source_line_id}:{ordinal}",
            date.fromisoformat(entry["entry_date"]), money(row["amount"]), basis))
    if not components or sum(item.amount for item in components) != money(line["credit"]):
        raise ValidationError("Reviewed components must reproduce the whole source credit exactly once.")
    return ReviewedComponents(source_line_id, entry["id"], approval["public_id"],
                              approval["decision_checksum"], tuple(components))
