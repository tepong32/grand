"""Dated usage of reviewed components over the captured connected ledger sources."""
import json
from collections import defaultdict
from datetime import date

from django.core.exceptions import ValidationError

from .budget_actuals import money
from .budget_application_components import bind_application_rows
from .budget_attributions import _approved_head, source_entries
from .budget_claim_components import Movement, validate_usage
from .budget_native_sources import verify
from .budget_reviewed_components import source_components


def component_usage(captured, *, entry_ids=None, require_complete=False):
    """Check all connected entries, including earlier/later out-of-period sources.

    Incomplete attribution may be prepared incrementally, but missing/unresolved
    decisions never establish complete coverage. Stale decisions always fail.
    Call only with trusted server captures. This creates no financial reservation.
    """
    payload = verify(captured)
    entries = source_entries(payload)
    roots = [entry["id"] for entry in payload["journals"]] if entry_ids is None else list(entry_ids)
    graph = defaultdict(set)
    try:
        for key, entry in entries.items():
            for other in (*entry["claim_evidence"]["related_entry_ids"], *entry["lineage"]["ancestor_ids"]):
                if other not in entries:
                    raise ValueError
                graph[key].add(other)
                graph[other].add(key)
        selected, pending = set(), list(roots)
        while pending:
            key = pending.pop()
            if type(key) is not int or key not in entries:
                raise ValueError
            if key not in selected:
                selected.add(key)
                pending.extend(graph[key] - selected)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Retain the complete captured component dependency group.") from exc

    # Verify every connected head, not only the direct source of the candidate.
    heads = {key: _approved_head(payload, key, entries=entries) for key in sorted(selected)}
    missing = sorted(key for key, head in heads.items() if head is None)
    unresolved, components, movements, event_keys, event_components = set(), {}, [], {}, {}
    sources = {}

    def bind_source(line_id):
        if line_id not in sources:
            sources[line_id] = source_components(captured, line_id)
            components.update({item.key: item for item in sources[line_id].components})
            event_components.update({"origin:" + item.key: item.key for item in sources[line_id].components})
        return sources[line_id]

    def signature(row):
        return json.dumps({key: value for key, value in row.items()
            if key not in {"line_id", "signed_amount", "reversal_source_line_id"}}, sort_keys=True)

    # Ancestors precede their reversals; independent non-reversal journals may be
    # in any date order because the calculator checks every dated boundary.
    ordered = sorted(selected, key=lambda key: (len(entries[key]["lineage"]["ancestor_ids"]), key))
    for entry_id in ordered:
        head, entry = heads[entry_id], entries[entry_id]
        if head is None:
            continue
        bound = bind_application_rows(captured, entry_id, head["allocations"])
        unresolved.update(bound["unresolved_line_ids"])
        unresolved.update(row["line_id"] for row in head["allocations"] if row["disposition"] == "unresolved")
        for binding in bound["bindings"]:
            bind_source(binding["source_line_id"])
        parent_id = entry["reversal_of_id"]
        parent = heads.get(parent_id)
        pairs = defaultdict(list)
        if parent:
            for ordinal, row in enumerate(parent["allocations"]):
                pairs[(row["line_id"], signature(row))].append(ordinal)
        for ordinal, row in enumerate(head["allocations"]):
            reference = row.get("claim_component")
            capacity = "claim_component_basis" in row
            if not reference and not capacity:
                continue
            key = f"allocation:{head['public_id']}:{ordinal}"
            prior_key = None
            if parent_id:
                matches = pairs.get((row.get("reversal_source_line_id"), signature(row)), [])
                if not matches:
                    raise ValidationError("A component reversal must retain the exact reviewed predecessor row.")
                parent_ordinal = matches.pop(0)
                prior_key = event_keys.get((parent_id, parent_ordinal))
                if prior_key is None:
                    raise ValidationError("A component reversal cannot invent missing predecessor capacity or consumption.")
            if capacity:
                if not parent_id:
                    source = bind_source(row["line_id"])
                    component_key = f"{source.attribution_id}:{row['line_id']}:{ordinal}"
                    if component_key not in components:
                        raise ValidationError("Retain the exact original component identity.")
                    event_keys[(entry_id, ordinal)] = "origin:" + component_key
                    continue
                # The preceding event identifies the same original component
                # through any number of exact reversals.
                component_key = event_components[prior_key]
                movement = Movement(key, component_key, date.fromisoformat(entry["entry_date"]),
                    -money(row["signed_amount"]), kind="capacity", reverses=prior_key,
                    purpose="source_capacity")
            else:
                component_key = reference["component_key"]
                movement = Movement(key, component_key, date.fromisoformat(entry["entry_date"]),
                    money(row["signed_amount"]), reverses=prior_key,
                    disposition=row["disposition"], purpose=row["purpose"],
                    office_id=row["center"]["office_id"] if row["center"] else None,
                    object_class=row["expense_class"])
            movements.append(movement)
            event_keys[(entry_id, ordinal)] = key
            event_components[key] = component_key
    result = validate_usage(components.values(), movements)
    complete = not missing and not unresolved
    if require_complete and not complete:
        raise ValidationError("Resolve all unreviewed and unresolved component dependencies before certifying coverage.")
    return {"entry_ids": sorted(selected), "unreviewed_entry_ids": missing,
            "unresolved_line_ids": sorted(unresolved), "complete": complete, "components": result}
