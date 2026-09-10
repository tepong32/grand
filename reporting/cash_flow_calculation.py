"""Direct-method cash movements from retained, classified posted journal evidence."""
from decimal import Decimal

from finance.cash_flows import CASH_FLOW_BY_CODE, CASH_FLOW_ROWS


def cash_flow_period(sources, cash_codes, start, end):
    zero = Decimal("0.00")
    values = {code: zero for code in CASH_FLOW_BY_CODE}
    opening = closing = zero
    missing = {}
    invalid_transfers = []
    for source in sources:
        if source["source_model"] != "JournalEntry" or source["source_date"] > end:
            continue
        snapshot = source["snapshot"]
        is_opening = (source["source_date"] < start or
            (source["source_date"] == start and snapshot["statement_source_type"] == "opening"))
        internal = zero
        for line in snapshot["lines"]:
            if line["account"] not in cash_codes:
                continue
            amount = Decimal(line["debit"]) - Decimal(line["credit"])
            closing += amount
            if is_opening:
                opening += amount
                continue
            category = line.get("cash_flow_category", "")
            if category not in CASH_FLOW_BY_CODE:
                key = (snapshot["statement_origin_public_id"], line["account"])
                group = missing.setdefault(key, {"amount": zero, "entries": set(), "references": []})
                group["amount"] += amount
                group["entries"].add(source["source_public_id"])
                group["references"].append(source["source_reference"])
                continue
            _activity, direction, _label = CASH_FLOW_BY_CODE[category]
            values[category] += amount if direction == "in" else -amount
            if category == "internal":
                internal += amount
        if internal:
            invalid_transfers.append(source["source_reference"])
    missing_references = sorted({reference for group in missing.values()
        if group["amount"] or len(group["entries"]) < 2 for reference in group["references"]})
    totals = {}
    for activity in ("operating", "investing", "financing"):
        for direction in ("in", "out"):
            totals[f"{activity}_{direction}"] = sum((values[code] for code, group, side, _label
                in CASH_FLOW_ROWS if group == activity and side == direction), zero)
        totals[f"{activity}_net"] = totals[f"{activity}_in"] - totals[f"{activity}_out"]
    net = sum((totals[f"{activity}_net"] for activity in ("operating", "investing", "financing")), zero)
    values.update(totals)
    values.update(opening=opening, closing=closing, net_change=net,
        difference=opening + net + values["exchange"] - closing)
    controls = {"opening_cash": opening, "closing_cash": closing,
        "net_cash_flows": net, "exchange_effect": values["exchange"],
        "reconciliation_difference": values["difference"],
        "unclassified_entries": missing_references, "invalid_internal_transfers": invalid_transfers}
    return values, controls
