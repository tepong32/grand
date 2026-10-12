"""Exact captured application amounts; no inferred Budget expenditure purpose."""
from decimal import Decimal

from django.core.exceptions import ValidationError

from .budget_native_sources import verify
from .budget_claim_sources import scoped_entries, verified_claims


def application_links(captured, *, entry_ids=None):
    payload = verify(captured)
    roots = [entry["id"] for entry in payload["journals"]] if entry_ids is None else list(entry_ids)
    records = verified_claims(captured, entry_ids=roots)
    entries = scoped_entries(payload, roots)
    lines = {line["id"]: (entry, line) for entry in entries.values() for line in entry["lines"]}
    historical = {}
    for source_id, record in records.items():
        for line_id in record["applications"]:
            historical.setdefault(line_id, []).append((source_id, record))
    links, unlinked = [], []

    def link(entry, line, source_id, amount, *, kind, shares=None, approval=None):
        source_entry, source = lines[source_id]
        debit, credit = Decimal(line["debit"]), Decimal(line["credit"])
        if (source_id == line["id"] or source["account_id"] != line["account_id"]
                or source["account"]["account_type"] != "liability" or source["payable_origin_id"]
                or Decimal(source["credit"]) <= 0 or Decimal(source["debit"]) != 0
                or entry["entry_date"] < source_entry["entry_date"]
                or amount <= 0 or (debit > 0) == (credit > 0) or min(debit, credit) < 0):
            raise ValidationError("Claim application does not match its exact original credit and dated financial line.")
        if (credit and not entry["reversal_of_id"]) or (entry["reversal_of_id"] and not entry["lineage"]["exact_mirror"]):
            raise ValidationError("Restoring claim amounts require complete exact reversal evidence.")
        return {"entry_id": entry["id"], "line_id": line["id"], "source_line_id": source_id,
            "source_entry_id": source_entry["id"], "amount": str(amount),
            "signed_amount": str(amount if debit else -amount), "kind": kind,
            "invoice_shares": shares or {}, "approval": approval,
            "reversal_of_id": entry["reversal_of_id"]}

    try:
        for entry_id in sorted(set(roots)):
            entry = entries[entry_id]
            for line in entry["lines"]:
                amount = Decimal(line["debit"]) + Decimal(line["credit"])
                envelope, source_id = line["payable_allocation"], line["payable_origin_id"]
                prior = historical.get(line["id"], [])
                rows = []
                if envelope or source_id:
                    if prior:
                        raise ValidationError("A native application cannot also acquire a second historical claim assignment.")
                    if envelope:
                        members = (envelope["sources"] if "sources" in envelope else {str(source_id): envelope})
                        for key, member in members.items():
                            shares = member["shares"]
                            allocated = sum((Decimal(value) for value in shares.values()), Decimal("0.00"))
                            rows.append(link(entry, line, int(key), allocated, kind="native_invoice",
                                shares=shares, approval=member["attribution"]))
                    else:
                        original = lines[source_id][1]
                        record = records.get(source_id)
                        if record and record["allocation_checksum"]:
                            raise ValidationError("An invoice application requires its exact retained invoice allocation.")
                        if not ((original["payable_party_key"] and original["payable_claim_reference"])
                                or (record and record["party_key"] and record["claim_reference"])):
                            raise ValidationError("An original whole claim needs its retained native or reviewed identity.")
                        if entry["reversal_of_id"]:
                            parent = entries[entry["reversal_of_id"]]
                            previous = next((item for item in parent["lines"] if item["sequence"] == line["sequence"]), None)
                            if (previous is None or previous["account_id"] != line["account_id"]
                                    or previous["debit"] != line["credit"] or previous["credit"] != line["debit"]
                                    or not (previous["id"] == source_id or previous["payable_origin_id"] == source_id
                                        or any(key == source_id for key, _ in historical.get(previous["id"], [])))):
                                raise ValidationError("A whole-claim reversal must retain the predecessor's original claim.")
                        rows.append(link(entry, line, source_id, amount, kind="native_whole"))
                elif prior:
                    for source_id, record in prior:
                        shares = {row["key"]: row["applications"][str(line["id"])]
                                  for row in record["invoice_slices"]
                                  if Decimal(row["applications"].get(str(line["id"]), "0.00")) > 0}
                        allocated = Decimal(record["application_amounts"][str(line["id"])]) if record["shared_proposal_id"] else amount
                        if shares and sum((Decimal(value) for value in shares.values()), Decimal("0.00")) != allocated:
                            raise ValidationError("Historical invoice shares do not reproduce their complete application amount.")
                        approval = {key: record[key] for key in ("public_id", "version", "approval_checksum", "source_checksum")}
                        rows.append(link(entry, line, source_id, allocated, kind="reviewed_historical",
                                         shares=shares, approval=approval))
                if rows:
                    if sum((Decimal(row["amount"]) for row in rows), Decimal("0.00")) != amount:
                        raise ValidationError("Claim links must reproduce the financial application exactly once.")
                    links.extend(rows)
                elif line["account"]["account_type"] == "liability":
                    unlinked.append({"entry_id": entry_id, "line_id": line["id"],
                        "debit": line["debit"], "credit": line["credit"], "reversal_of_id": entry["reversal_of_id"]})
        return {"links": links, "unlinked_liability_lines": unlinked}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Captured claim links are incomplete; resolve the exact source before classification.") from exc
