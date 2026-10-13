"""Complete per-journal component bindings; cohort dated usage is a separate gate."""
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError

from .budget_actuals import money
from .budget_attributions import source_entries
from .budget_claim_links import application_links
from .budget_native_sources import verify
from .budget_reviewed_components import source_components


def bind_application_rows(captured, entry_id, rows):
    """Verify normalized rows against posted links and current captured approvals.

    Complete unresolved financial lines remain explicit. Exact source-capacity
    reversals retain their original basis and are not ordinary payment consumption.
    This does not assert that all journals sharing a component fit its dated capacity.
    """
    payload = verify(captured)
    entries = source_entries(payload)
    evidence = application_links(captured, entry_ids=[entry_id])
    links = evidence["links"]
    linked = defaultdict(dict)
    for link in links:
        linked[link["line_id"]][link["source_line_id"]] = link
    grouped = defaultdict(list)
    for ordinal, row in enumerate(rows):
        grouped[row["line_id"]].append((ordinal, row))
        if "claim_component" in row and row["line_id"] not in linked:
            raise ValidationError("Component allocations require the exact retained financial application link.")
    if payload['schema'] >= 7:
        for line in evidence['unlinked_liability_lines']:
            if any(row['disposition'] == 'include' for _, row in grouped.get(line['line_id'], [])):
                raise ValidationError(
                    'Review the exact original liability and application link before including this amount as expenditure. '
                    'Use historical claim review for an existing unlinked payment, or retain unresolved treatment.')
    bindings, unresolved, sources = [], [], {}
    for line_id, originals in linked.items():
        parts = grouped.get(line_id, [])
        total = sum((money(link["amount"]) for link in originals.values()), Decimal("0.00"))
        if not parts or sum((money(row["amount"]) for _, row in parts), Decimal("0.00")) != total:
            raise ValidationError("Classify the whole posted application exactly once.")
        if all(row["disposition"] == "unresolved" and "claim_component" not in row for _, row in parts):
            unresolved.append(line_id)
            continue
        if (entries[entry_id]["reversal_of_id"] and entries[entry_id]["lineage"]["exact_mirror"]
                and all("claim_component_basis" in row and "claim_component" not in row for _, row in parts)):
            # _normalize_reviewed proves the complete inherited predecessor rows.
            continue
        used = defaultdict(lambda: Decimal("0.00"))
        per_component = defaultdict(lambda: Decimal("0.00"))
        for ordinal, row in parts:
            reference = row.get("claim_component")
            if not reference or row["disposition"] == "unresolved":
                raise ValidationError("Resolve the entire application with explicit source components or retain the line as unresolved.")
            source_id = reference["source_line_id"]
            if source_id not in originals:
                raise ValidationError("The selected component does not belong to this posted application's original credit.")
            cache_key = (source_id, reference["attribution_id"])
            if cache_key not in sources:
                sources[cache_key] = source_components(captured, source_id,
                    expected_attribution_id=reference["attribution_id"])
            source = sources[cache_key]
            component = next((item for item in source.components if item.key == reference["component_key"]), None)
            if component is None:
                raise ValidationError("Select a component from the exact reviewed original-credit partition.")
            amount = money(row["amount"])
            expected_sign = 1 if money(originals[source_id]["signed_amount"]) > 0 else -1
            if amount <= 0 or money(row["signed_amount"]) != amount * expected_sign:
                raise ValidationError("Preserve the actual application amount and financial sign.")
            if row["disposition"] == "include":
                if component.basis != "loan_principal" or row["purpose"] != "debt_principal":
                    raise ValidationError("An already-recognized or non-expenditure component cannot become a second expenditure.")
            elif row["disposition"] != "exclude":
                raise ValidationError("Retain an explicit included or excluded component treatment.")
            used[source_id] += amount
            per_component[component.key] += amount
            if per_component[component.key] > component.amount:
                raise ValidationError("One application cannot borrow another component's capacity.")
            bindings.append({"row_ordinal": ordinal, "line_id": line_id, "source_line_id": source_id,
                "component_key": component.key, "attribution_id": source.attribution_id,
                "decision_checksum": source.decision_checksum, "amount": str(amount),
                "signed_amount": row["signed_amount"], "basis": component.basis})
        if any(used[key] != money(link["amount"]) for key, link in originals.items()):
            raise ValidationError("Component allocations must reproduce each original credit's actual application share.")
    return {"bindings": bindings, "unresolved_line_ids": unresolved}
