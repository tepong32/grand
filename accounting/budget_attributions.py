"""Reviewed office/purpose partitions over posted sources, not certification."""
import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .access import department_for_user, has_explicit_permission
from .budget_actuals import money
from .cash_classifications import checksum
from .models import (BudgetExpenditureAttribution as Attribution,
    BudgetExpenditureAttributionHead as Head, Fund, JournalEntry, ResponsibilityCenter)


# These are explicit review choices, never account-type inferences.
INCLUDED_PURPOSES = {
    "expense_recognition": {"expense"}, "expense_liquidation": {"expense"},
    "capital_acquisition": {"asset"}, "debt_principal": {"liability"},
    "financial_charge": {"expense"}, "other_expenditure": {"expense", "asset", "liability"},
}
EXCLUDED_PURPOSES = {"settlement", "advance", "refund", "transfer", "revenue",
    "counterpart", "opening", "closing", "direct_equity", "other_exclusion"}
PROPOSAL_FIELDS = ("public_id", "batch_id", "entry_id", "department_id", "version", "base_version",
    "period_start", "period_end", "source_checksum", "allocations", "reason", "evidence_reference",
    "prepared_by_id", "prepared_by_label", "prepared_at")
DECISION_FIELDS = ("public_id", "proposal_checksum", "status", "reviewed_by_id",
    "reviewed_by_label", "reviewed_at", "review_note")
CAPTURE_FIELDS = tuple(dict.fromkeys((*PROPOSAL_FIELDS, *DECISION_FIELDS, "decision_checksum", "dependencies")))


def json_value(value):
    return json.loads(json.dumps(value, default=lambda item:
        item.isoformat() if isinstance(item, (date, datetime)) else str(item)))


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return has_explicit_permission(actor, f"accounting.{action}_budget_attributions") and (
        action in ("view", "export") or not is_finance_uat_viewer(actor))


def projection(record):
    return projection_data({field: getattr(record, field) for field in CAPTURE_FIELDS})


def projection_data(data):
    result = json_value(data)
    if not result.get("dependencies"):
        result.pop("dependencies", None)
    return result


def proposal_payload(data):
    result = {field: data[field] for field in PROPOSAL_FIELDS}
    if data.get("dependencies"):
        result["dependencies"] = data["dependencies"]
    return result


def decision_payload(data):
    return {field: data[field] for field in DECISION_FIELDS}


def source_entries(payload):
    return {entry["id"]: entry for entry in (
        payload["journals"] + payload["lineage_sources"] + payload.get("claim_sources", []))}


def financial_source(payload, entry_id, *, entries=None, allocations=None, dependencies=None):
    if entries is None:
        entries = source_entries(payload)
    entry = entries.get(entry_id)
    if entry is None:
        raise ValidationError("Select a posted journal inside the captured period.")
    if dependencies is None:
        dependencies = (entry.get("attribution") or {}).get("dependencies", {})
    def financial(row):
        result = {key: value for key, value in row.items() if key not in ("attribution", "lineage")}
        if payload["schema"] >= 4:
            result["lines"] = [{key: value for key, value in line.items() if key != "retained_claim_attributions"}
                               for line in row["lines"]]
        return result
    source = {"fund": payload["scope"]["fund"], "journal": financial(entry),
        "lineage": entry["lineage"], "ancestors": [financial(entries[key])
            for key in sorted(set(entry["lineage"]["ancestor_ids"]))]}
    if entry["reversal_of_id"]:
        source["reversal_attributions"] = [{"entry_id": key,
            **({"proposal_dependency": dependencies[str(key)]} if str(key) in dependencies
               else {"attribution": entries[key].get("attribution")})}
            for key in sorted(set(entry["lineage"]["ancestor_ids"]))]
    if payload["schema"] >= 3:
        pending, retained = [entry_id], set()
        while pending:
            key = pending.pop()
            if key in retained:
                continue
            retained.add(key)
            pending.extend(entries[key].get("claim_evidence", {}).get("related_entry_ids", []))
            pending.extend(entries[key]["lineage"]["ancestor_ids"])
        source["claim_sources"] = [financial(entries[key]) for key in sorted(retained - {entry_id})]
        if payload["schema"] >= 4:
            from .budget_claim_sources import pinned_versions
            source["claim_pins"] = pinned_versions(entries, retained)
    if allocations is None:
        allocations = (entry.get("attribution") or {}).get("allocations", [])
    try:
        source_ids = {row["claim_component"]["source_line_id"] for row in allocations if "claim_component" in row}
        if source_ids:
            originals = {line["id"]: owner for owner in entries.values() for line in owner["lines"]}
            if any(type(key) is not int or key not in originals for key in source_ids):
                raise ValueError
            source["component_sources"] = [{"source_line_id": key, "entry_id": originals[key]["id"],
                "attribution": originals[key].get("attribution")} for key in sorted(source_ids)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Select exact captured source components for the application.") from exc
    return source


def normalize(source, rows, centers, *, reversal_reviewed=False):
    if not isinstance(rows, list) or not rows:
        raise ValidationError("Partition every financial line, including excluded and unresolved amounts.")
    lines = {line["id"]: line for line in source["journal"]["lines"]}
    totals = {key: Decimal("0.00") for key in lines}
    result = []
    for item in rows:
        try:
            line_id = int(str(item["line_id"]))
            line = lines[line_id]
            amount = money(item["amount"])
            disposition, purpose = item["disposition"], item["purpose"]
            basis = item["basis"]
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Use this journal's line, amount, disposition, purpose and evidence basis.")
        if not isinstance(disposition, str) or not isinstance(purpose, str) or not isinstance(basis, str):
            raise ValidationError("Use explicit text for disposition, purpose and supporting basis.")
        basis = basis.strip()
        origin = source["lineage"]["origin_source_type"]
        structural = {"opening", "closing", *JournalEntry.DIRECT_EQUITY_SOURCES}
        if source["lineage"]["issue"] and disposition != "unresolved":
            raise ValidationError("Keep invalid reversal lineage unresolved until its source is established.")
        if origin in structural and disposition == "include":
            raise ValidationError("Opening, closing and direct-equity movements cannot become period expenditure.")
        if source["journal"]["reversal_of_id"] and origin not in structural and disposition != "unresolved" and not reversal_reviewed:
            raise ValidationError("This reversal needs linked reviewed attribution; retain unresolved components for now.")
        debit, credit = money(line["debit"]), money(line["credit"])
        if amount <= 0 or (debit > 0) == (credit > 0) or not basis or len(basis) > 1000:
            raise ValidationError("Use positive components on valid one-sided financial lines with an explicit basis.")
        center, expense_class = None, ""
        if disposition == "include":
            if purpose not in INCLUDED_PURPOSES or line["account"]["account_type"] not in INCLUDED_PURPOSES[purpose]:
                raise ValidationError("The explicit expenditure purpose does not fit this financial account class.")
            try:
                center = centers[int(str(item["center_id"]))]
                expense_class = item["expense_class"]
            except (KeyError, TypeError, ValueError):
                raise ValidationError("Select an office-linked responsibility center in this ledger and an object class.")
            if not isinstance(expense_class, str) or not expense_class.strip() or len(expense_class) > 40 or not center["office_id"]:
                raise ValidationError("Retain an explicit office and expenditure object class.")
            expense_class = expense_class.strip()
        elif disposition == "exclude":
            if purpose not in EXCLUDED_PURPOSES:
                raise ValidationError("Choose an explicit exclusion purpose.")
        elif disposition != "unresolved" or purpose != "unresolved":
            raise ValidationError("Choose include, exclude or unresolved; do not guess missing purpose.")
        if disposition != "include" and (item.get("center_id") or item.get("expense_class")):
            raise ValidationError("Excluded and unresolved amounts cannot carry an expenditure allocation.")
        totals[line_id] += amount
        result.append({"line_id": line_id, "account_id": line["account_id"], "amount": str(amount),
            "signed_amount": str(amount if debit else -amount), "disposition": disposition, "purpose": purpose,
            "center_id": center["id"] if center else None, "center": center,
            "expense_class": expense_class, "basis": basis})
        if "claim_component_basis" in item:
            from .budget_claim_components import BASES
            component_basis = item["claim_component_basis"]
            if (not isinstance(component_basis, str) or component_basis not in BASES
                    or disposition != "exclude" or line["account"]["account_type"] != "liability"
                    or (not reversal_reviewed and (not credit or line["payable_origin_id"]
                        or source["journal"]["reversal_of_id"]))):
                raise ValidationError("Declare component basis only on an original excluded liability credit or its exact reviewed reversal.")
            # Source capacity and period expenditure are separate: an excluded
            # opening liability can evidence a later principal repayment. The
            # structural inclusion guard above still applies to this movement.
            result[-1]["claim_component_basis"] = component_basis
        if "claim_component" in item:
            reference = item["claim_component"]
            if (not isinstance(reference, dict) or set(reference) != {"source_line_id", "attribution_id", "component_key"}
                    or type(reference["source_line_id"]) is not int or reference["source_line_id"] <= 0
                    or not all(isinstance(reference[key], str) and reference[key].strip()
                        for key in ("attribution_id", "component_key"))
                    or disposition == "unresolved" or "claim_component_basis" in item):
                raise ValidationError("Retain an explicit original credit, approval and component identity for resolved applications.")
            result[-1]["claim_component"] = dict(reference)
        if item.get("reversal_source_line_id") is not None:
            if not reversal_reviewed:
                raise ValidationError("Line pairing requires a verified reviewed reversal source.")
            try:
                result[-1]["reversal_source_line_id"] = int(str(item["reversal_source_line_id"]))
            except (TypeError, ValueError):
                raise ValidationError("Select an exact original financial line for each reversal line.")
    if any(totals[key] != money(line["debit"]) + money(line["credit"]) for key, line in lines.items()):
        raise ValidationError("Every journal line must be partitioned exactly once across all offices and dispositions.")
    return sorted(result, key=lambda row: (row["line_id"], json.dumps(row, sort_keys=True)))


def _centers(owner_id):
    return {row["id"]: row for row in ResponsibilityCenter.objects.filter(department_id=owner_id).values(
        "id", "department_id", "code", "name", "office_id", "office_code")}


def verify(record):
    data = projection(record)
    if checksum(record.source_snapshot) != record.source_checksum or checksum(proposal_payload(data)) != record.proposal_checksum:
        raise ValidationError("Retained attribution proposal does not reproduce its evidence.")
    if record.status != Attribution.SUBMITTED and checksum(decision_payload(data)) != record.decision_checksum:
        raise ValidationError("Retained attribution decision does not reproduce its evidence.")
    return data


def reviewed_allocations(captured):
    """Use only the heads captured with financial evidence; never reread pointers."""
    from .budget_native_sources import verify as verify_capture
    payload = verify_capture(captured)
    if payload["schema"] >= 3:
        from .budget_component_usage import component_usage
        component_usage(captured)
        from .budget_claim_sources import verified_claims
        verified_claims(captured)
    entries = source_entries(payload)
    result = []
    for entry in payload["journals"]:
        data = _approved_head(payload, entry["id"], entries=entries)
        if data is None:
            result.append({"entry_id": entry["id"], "status": "unreviewed", "allocations": []})
            continue
        if payload["schema"] >= 3:
            from .budget_application_components import bind_application_rows
            bind_application_rows(captured, entry["id"], data["allocations"])
        result.append({"entry_id": entry["id"], "status": "reviewed",
            "version": data["public_id"], "allocations": data["allocations"]})
    return result


def _base_approved_head(payload, entry_id, *, entries=None):
    if entries is None:
        entries = source_entries(payload)
    entry = entries.get(entry_id)
    if entry is None:
        raise ValidationError("The exact source journal is absent from captured evidence.")
    data = entry.get("attribution")
    if data is None:
        return None
    if (data["status"] != Attribution.APPROVED or data["entry_id"] != entry_id
            or data["department_id"] != payload["scope"]["fund"]["department_id"]
            or not data["reviewed_at"] or not data["reviewed_by_id"]
            or data["reviewed_by_id"] == data["prepared_by_id"]
            or checksum(proposal_payload(data)) != data["proposal_checksum"]
            or checksum(decision_payload(data)) != data["decision_checksum"]
            or checksum(financial_source(payload, entry_id, entries=entries)) != data["source_checksum"]):
        raise ValidationError("Reviewed attribution no longer reproduces its source and independent decision.")
    return data


def _approved_head(payload, entry_id, *, entries=None):
    if entries is None:
        entries = source_entries(payload)
    data = _base_approved_head(payload, entry_id, entries=entries)
    if data is not None:
        from .budget_attribution_dependencies import verify_approved
        verify_approved(payload, data, entries)
    return data


def _paired_reversal_rows(payload, source, pairs=None, *, parent_data=None):
    """Suggest a proved mirror; ambiguous duplicate lines require explicit pairing."""
    if not source["journal"]["reversal_of_id"] or not source["lineage"]["exact_mirror"]:
        raise ValidationError("Use an exact financial reversal with complete source lineage.")
    parent_id = source["journal"]["reversal_of_id"]
    if parent_data is None:
        parent_data = _approved_head(payload, parent_id)
    if parent_data is None:
        raise ValidationError("Independently review the original attribution before inheriting it.")
    parent = next(entry for entry in source["ancestors"] if entry["id"] == parent_id)
    children = {line["id"]: line for line in source["journal"]["lines"]}
    originals = {line["id"]: line for line in parent["lines"]}
    def signature(line, reverse=False):
        return (line["account_id"], line["responsibility_center_id"], line["cash_flow_category"],
                line["credit"] if reverse else line["debit"], line["debit"] if reverse else line["credit"])
    if pairs is None:
        pairs = {}
        for line_id, line in children.items():
            matches = [key for key, original in originals.items() if signature(line) == signature(original, True)]
            if len(matches) != 1:
                raise ValidationError("Duplicate financial lines require explicit original-to-reversal pairing.")
            pairs[line_id] = matches[0]
    try:
        if not isinstance(pairs, dict):
            raise ValueError
        normalized = {int(str(key)): int(str(value)) for key, value in pairs.items()}
        if len(normalized) != len(pairs) or set(normalized) != set(children) or set(normalized.values()) != set(originals) or len(normalized) != len(set(normalized.values())):
            raise ValueError
        if any(signature(children[key]) != signature(originals[value], True) for key, value in normalized.items()):
            raise ValueError
    except (TypeError, ValueError, KeyError):
        raise ValidationError("Pair every reversed financial line exactly once with its matching original.")
    inverse = {original: child for child, original in normalized.items()}
    rows = [{**row, "line_id": inverse[row["line_id"]],
             "signed_amount": str(-money(row["signed_amount"])), "reversal_source_line_id": row["line_id"]}
            for row in parent_data["allocations"]]
    return sorted(rows, key=lambda row: (row["line_id"], json.dumps(row, sort_keys=True)))


def reversal_allocations(captured, entry_id, *, pairs=None):
    from .budget_native_sources import verify as verify_capture
    payload = verify_capture(captured)
    return _paired_reversal_rows(payload, financial_source(payload, entry_id), pairs)


def _normalize_reviewed(captured, source, rows, centers, *, parent_data=None):
    from .budget_application_components import bind_application_rows
    payload = captured["payload"]
    def bind(normalized):
        bind_application_rows(captured, source["journal"]["id"], normalized)
        return normalized
    parent_id = source["journal"]["reversal_of_id"]
    if not parent_id or not source["lineage"]["exact_mirror"]:
        return bind(normalize(source, rows, centers))
    parent = parent_data if parent_data is not None else _approved_head(payload, parent_id)
    if parent is None:
        return bind(normalize(source, rows, centers))
    pairs = {}
    try:
        for row in rows:
            line_id, original_id = int(str(row["line_id"])), int(str(row["reversal_source_line_id"]))
            if line_id in pairs and pairs[line_id] != original_id:
                raise ValueError
            pairs[line_id] = original_id
    except (KeyError, ValueError, TypeError):
        raise ValidationError("Retain the exact original line pairing for every reversed component.")
    expected = _paired_reversal_rows(payload, source, pairs, parent_data=parent)
    # Undo the pinned historical office allocation, not a later renamed/reassigned lookup.
    pinned_centers = {row["center_id"]: row["center"] for row in expected if row["center"]}
    normalized = normalize(source, rows, pinned_centers, reversal_reviewed=True)
    if normalized != expected:
        raise ValidationError("A reversal must mirror the original reviewed purpose, office, object and component amounts.")
    return bind(normalized)


def _fund(actor, fund_id, action):
    if not permitted(actor, action):
        raise PermissionDenied
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=department_for_user(actor).pk).first()
    if fund is None:
        raise PermissionDenied
    return fund


@transaction.atomic(using="finance")
def propose_batch(*, actor, fund_id, period_start, period_end, expected_source_checksum, proposals, reason, evidence_reference,
                  expected_centers=None):
    from .budget_native_sources import capture
    fund = _fund(actor, fund_id, "prepare")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 250:
        raise ValidationError("Select between one and 250 journals for this review batch.")
    if not isinstance(reason, str) or not reason.strip() or not isinstance(evidence_reference, str) or not evidence_reference.strip() or len(evidence_reference) > 255:
        raise ValidationError("Record the attribution explanation and supporting evidence reference.")
    captured = capture(actor=actor, fund_id=fund.pk, period_start=period_start, period_end=period_end)
    if captured["checksum"] != expected_source_checksum:
        raise ValidationError("Source coverage or reviewed attribution changed; reload before preparing this batch.")
    centers, seen, records = _centers(fund.department_id), set(), []
    if expected_centers is not None and centers != expected_centers:
        raise ValidationError("Office choices changed; reload before preparing this batch.")
    try:
        proposed_ids = {int(str(item["entry_id"])) for item in proposals}
    except (KeyError, TypeError, ValueError):
        raise ValidationError("Select explicit source journals for this batch.")
    selected = {entry["id"]: entry for entry in captured["payload"]["journals"]}
    if not proposed_ids <= selected.keys():
        raise ValidationError("Select journals inside the captured period.")
    if len(proposed_ids) != len(proposals):
        raise ValidationError("A journal may occur only once in a review batch.")
    for item in proposals:
        entry_id = int(str(item["entry_id"]))
        inherited = item.get("inherit_from")
        if inherited is not None:
            if (type(inherited) is not int or inherited not in proposed_ids
                    or inherited != selected[entry_id]["reversal_of_id"] or "allocations" in item):
                raise ValidationError("Explicitly inherit from the immediate predecessor proposal in this same batch.")
        elif proposed_ids.intersection(selected[entry_id]["lineage"]["ancestor_ids"]):
            raise ValidationError("Use explicit joint inheritance or review dependent reversals in a separate batch.")
    from .budget_claim_sources import verified_claims
    verified_claims(captured, entry_ids=proposed_ids)
    batch_id, now = uuid.uuid4(), timezone.now()
    prepared = {}
    ordered = sorted(proposals, key=lambda item: (
        len(selected[int(str(item["entry_id"]))]["lineage"]["ancestor_ids"]), int(str(item["entry_id"]))))
    for item in ordered:
        try:
            entry_id = int(str(item["entry_id"]))
            parent_data, dependencies = None, {}
            if item.get("inherit_from") is not None:
                from .budget_attribution_dependencies import manifest
                parent_data = projection(prepared[item["inherit_from"]])
                dependencies = manifest(parent_data)
                source = financial_source(captured["payload"], entry_id, allocations=[], dependencies=dependencies)
                rows = _paired_reversal_rows(captured["payload"], source, item.get("line_pairs"), parent_data=parent_data)
            else:
                rows = item["allocations"]
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Select explicit journals and their complete allocations.")
        if entry_id in seen:
            raise ValidationError("A journal may occur only once in a review batch.")
        seen.add(entry_id)
        source = financial_source(captured["payload"], entry_id, allocations=rows, dependencies=dependencies)
        if any(pin["entry_id"] in proposed_ids for pin in source.get("component_sources", [])):
            raise ValidationError("Review source components before preparing their dependent applications in a separate batch.")
        entry = JournalEntry.objects.get(pk=entry_id, fund=fund, department_id=fund.department_id, status=JournalEntry.POSTED)
        latest = entry.budget_attributions.aggregate(value=Max("version"))["value"] or 0
        if type(item.get("expected_latest")) is not int or item["expected_latest"] != latest:
            raise ValidationError("A newer proposal exists; reload its history before preparing a successor.")
        head = Head.objects.select_related("attribution").filter(entry=entry).first()
        record = Attribution(department_id=fund.department_id, department_label=fund.department_label,
            batch_id=batch_id, entry=entry, version=latest + 1,
            base_version=head.attribution.version if head else 0, period_start=period_start, period_end=period_end,
            source_snapshot=source, source_checksum=checksum(source), dependencies=dependencies,
            allocations=_normalize_reviewed(captured, source, rows, centers, parent_data=parent_data),
            reason=reason.strip(), evidence_reference=evidence_reference.strip(), prepared_by_id=actor.pk,
            prepared_by_label=(actor.get_full_name() or actor.username)[:160], prepared_at=now)
        record.proposal_checksum = checksum(proposal_payload(projection(record)))
        record.save()
        records.append(record)
        prepared[entry_id] = record
    return records


@transaction.atomic(using="finance")
def review_batch(*, batch_id, actor, approve, note):
    from .budget_native_sources import capture
    if not permitted(actor, "review"):
        raise PermissionDenied
    first = Attribution.objects.select_related("entry").filter(batch_id=batch_id,
        department_id=department_for_user(actor).pk).first()
    if first is None:
        raise PermissionDenied
    fund = _fund(actor, first.entry.fund_id, "review")
    records = list(Attribution.objects.select_for_update().filter(batch_id=batch_id).select_related("entry").order_by("entry_id"))
    proposed = {record.entry_id: record for record in records}
    if type(approve) is not bool or not isinstance(note, str) or not note.strip():
        raise ValidationError("Record an explicit independent review decision and its basis.")
    captured = capture(actor=actor, fund_id=fund.pk, period_start=first.period_start, period_end=first.period_end) if approve else None
    centers = _centers(fund.department_id) if approve else None
    if approve:
        from .budget_claim_sources import verified_claims
        verified_claims(captured, entry_ids=[record.entry_id for record in records])
    for record in records:
        verify(record)
        if (record.department_id != fund.department_id or record.entry.fund_id != fund.pk
                or record.period_start != first.period_start or record.period_end != first.period_end
                or record.status != Attribution.SUBMITTED or record.prepared_by_id == actor.pk):
            raise ValidationError("Review the complete pending batch with a different authorized reviewer.")
        if approve:
            latest = record.entry.budget_attributions.aggregate(value=Max("version"))["value"]
            head = Head.objects.select_related("attribution").filter(entry_id=record.entry_id).first()
            if latest != record.version or (head.attribution.version if head else 0) != record.base_version:
                raise ValidationError("A newer attribution exists; return this stale batch and prepare a successor.")
            from .budget_attribution_dependencies import pending_parent
            parent_data = pending_parent(record, proposed)
            source = financial_source(captured["payload"], record.entry_id, allocations=record.allocations,
                                      dependencies=record.dependencies)
            if checksum(source) != record.source_checksum or _normalize_reviewed(captured, source, record.allocations,
                    centers, parent_data=parent_data) != record.allocations:
                raise ValidationError("Financial source or office metadata changed; prepare fresh attribution evidence.")
    now = timezone.now()
    for record in records:
        record.status = Attribution.APPROVED if approve else Attribution.RETURNED
        record.reviewed_by_id = actor.pk
        record.reviewed_by_label = (actor.get_full_name() or actor.username)[:160]
        record.reviewed_at, record.review_note = now, note.strip()
        record.decision_checksum = checksum(decision_payload(projection(record)))
        record._decision_write = True
        record.save()
        if approve:
            Head.objects.update_or_create(entry_id=record.entry_id, defaults={"attribution": record})
    if approve and any(any("claim_component" in row or
            ("claim_component_basis" in row and record.entry.reversal_of_id)
            for row in record.allocations) for record in records):
        # Heads are now visible in this transaction, but still unpublished to
        # other writers. A failure rolls back the entire independent decision.
        from .budget_component_usage import component_usage
        after = capture(actor=actor, fund_id=fund.pk, period_start=first.period_start, period_end=first.period_end)
        component_usage(after, entry_ids=[record.entry_id for record in records])
    return records
