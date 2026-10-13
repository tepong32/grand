"""Detached claim evidence for Budget preparation; no expenditure inference."""
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError

from .cash_classifications import checksum


HEAD_POINTER = "posted__lines__claim_attribution_head__attribution_id"
HEAD_PREFIX = "posted__lines__claim_attributions__"
CLAIM_FIELDS = ("id", "public_id", "department_id", "source_id", "shared_proposal_id",
    "application_amounts", "version", "base_version", "party_key", "claim_reference",
    "allocation_checksum", "applications", "source_snapshot", "source_checksum",
    "evidence_reference", "reason", "status", "proposed_by_id", "proposed_by_label",
    "proposed_at", "reviewed_by_id", "reviewed_by_label", "reviewed_at", "review_note",
    "approval_checksum")
SLICE_FIELDS = ("key", "party_key", "claim_reference", "recognized", "applications")
SHARED_FIELDS = ("id", "public_id", "department_id", "fund_id", "source_ids",
    "application_ids", "source_set_checksum", "version", "base_approvals", "allocations",
    "source_snapshot", "source_checksum", "evidence_reference", "reason", "proposed_by_id",
    "proposed_by_label", "proposed_at", "proposal_checksum")
GROUPS = (("", (HEAD_POINTER,)), (HEAD_PREFIX, CLAIM_FIELDS), (HEAD_PREFIX + "invoice_slices__", SLICE_FIELDS),
          (HEAD_PREFIX + "shared_proposal__", SHARED_FIELDS))


def merge_line(line, row):
    """A joined invoice row may repeat a financial line, never its financial amount."""
    def part(prefix, fields):
        return {field: row[prefix + field] for field in fields}
    versions = line.setdefault("_claim_versions", {})
    line["_claim_head_id"] = row[HEAD_POINTER]
    record_id = row[HEAD_PREFIX + "id"]
    if record_id is not None:
        if record_id not in versions:
            record = part(HEAD_PREFIX, CLAIM_FIELDS)
            shared = part(HEAD_PREFIX + "shared_proposal__", SHARED_FIELDS)
            record["shared_proposal"] = shared if shared["id"] is not None else None
            record["invoice_slices"] = []
            versions[record_id] = record
        record = versions[record_id]
        invoice = part(HEAD_PREFIX + "invoice_slices__", SLICE_FIELDS)
        if invoice["key"] is not None and not any(item["key"] == invoice["key"] for item in record["invoice_slices"]):
            record["invoice_slices"].append(invoice)
            record["invoice_slices"].sort(key=lambda item: str(item["key"]))


def retain_versions(lines):
    """Select current and actually pinned versions from the same joined read.

    Join versions and their slices once, instead of multiplying independent current
    and historical invoice joins. Unreferenced drafts/history do not enter outputs.
    Retained envelopes still require separate source/approval/posting verification.
    """
    required = defaultdict(dict)
    by_public = {str(record["public_id"]): record for line in lines.values()
                 for record in line["_claim_versions"].values()}
    for line in lines.values():
        line["claim_attribution"] = line["_claim_versions"].get(line["_claim_head_id"])
        line["claim_capture_issues"] = []
        if line["_claim_head_id"] is not None and line["claim_attribution"] is None:
            line["claim_capture_issues"].append("missing_or_mismatched_current_claim_head")
    for line in lines.values():
        envelope = line["payable_allocation"]
        if not envelope:
            continue
        try:
            if not isinstance(envelope, dict):
                raise ValueError
            if "sources" in envelope:
                if not isinstance(envelope["sources"], dict):
                    raise ValueError
                members = []
                for key, member in envelope["sources"].items():
                    if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key:
                        raise ValueError
                    members.append((int(key), member))
            else:
                members = [(line["payable_origin_id"], envelope)]
            for source_id, member in members:
                record = by_public.get(member["attribution"]["public_id"])
                if (type(source_id) is not int or source_id not in lines or record is None
                        or record["source_id"] != source_id):
                    raise ValueError
                required[source_id][record["id"]] = record
                shared = record["shared_proposal"]
                if shared:
                    for other_id in shared["source_ids"]:
                        matches = [item for item in lines[other_id]["_claim_versions"].values()
                                   if item["shared_proposal_id"] == shared["id"]]
                        if len(matches) != 1:
                            raise ValueError
                        required[other_id][matches[0]["id"]] = matches[0]
        except (KeyError, TypeError, ValueError):
            line["claim_capture_issues"].append("missing_or_malformed_pinned_claim_version")
    for key, line in lines.items():
        line["retained_claim_attributions"] = sorted(required[key].values(), key=lambda item: item["version"])
        del line["_claim_versions"], line["_claim_head_id"]


def pinned_versions(entries, entry_ids):
    """Only pins used by this directed source dependency, plus complete old groups."""
    references = set()
    available = {}
    for entry in entries.values():
        for line in entry["lines"]:
            for record in line.get("retained_claim_attributions", []):
                available[record["public_id"]] = record
            if entry["id"] not in entry_ids:
                continue
            envelope = line["payable_allocation"]
            if not isinstance(envelope, dict):
                continue  # Capture issues are independently rejected by verification.
            members = envelope.get("sources", {"single": envelope})
            if isinstance(members, dict):
                for member in members.values():
                    evidence = member.get("attribution", {}) if isinstance(member, dict) else {}
                    if isinstance(evidence, dict) and isinstance(evidence.get("public_id"), str):
                        references.add(evidence["public_id"])
    groups = {record["shared_proposal_id"] for key, record in available.items()
              if key in references and record["shared_proposal_id"]}
    return sorted([record for key, record in available.items()
                   if key in references or record["shared_proposal_id"] in groups],
                  key=lambda record: (record["source_id"], record["version"]))


def dependency_graph(entries):
    """Connect retained claim sources/applications without treating them as expenditure.

    Undirected components retain all members of a reviewed claim, including shared
    groups and native applications outside the selected period. Missing or foreign
    references remain explicit evidence issues; no later query fills a snapshot.
    """
    lines = {line["id"]: entry["id"] for entry in entries.values() for line in entry["lines"]}
    graph, issues, dependencies = defaultdict(set), defaultdict(set), defaultdict(set)
    def connect(entry_id, line_id, *, historical_application=False):
        if type(line_id) is not int or line_id <= 0:
            issues[entry_id].add("invalid_claim_line_identity")
            return
        other = lines.get(line_id)
        if other is None:
            issues[entry_id].add("missing_or_out_of_scope_claim_line:" + str(line_id))
        else:
            graph[entry_id].add(other)
            graph[other].add(entry_id)
            dependencies[entry_id].add(other)
            if historical_application:
                dependencies[other].add(entry_id)
    for entry in entries.values():
        for line in entry["lines"]:
            issues[entry["id"]].update(line.get("claim_capture_issues", []))
            if line["payable_origin_id"]:
                connect(entry["id"], line["payable_origin_id"])
            allocation = line["payable_allocation"]
            if isinstance(allocation, dict) and isinstance(allocation.get("sources"), dict):
                for key in allocation["sources"]:
                    if isinstance(key, str) and key.isdecimal() and str(int(key)) == key:
                        connect(entry["id"], int(key))
                    else:
                        issues[entry["id"]].add("invalid_shared_claim_source")
            records = [line["claim_attribution"]] if line.get("claim_attribution") else []
            records.extend(line.get("retained_claim_attributions", []))
            for record in records:
                connect(entry["id"], record["source_id"])
                ids = record["applications"]
                if not isinstance(ids, list):
                    issues[entry["id"]].add("invalid_claim_application_list")
                    ids = []
                shared = record["shared_proposal"]
                if shared:
                    for name in ("source_ids", "application_ids"):
                        if isinstance(shared[name], list):
                            ids = [*ids, *shared[name]]
                        else:
                            issues[entry["id"]].add("invalid_shared_claim_line_list")
                for line_id in ids:
                    connect(entry["id"], line_id, historical_application=True)
    return graph, issues, dependencies


def related(entry_ids, graph):
    found, pending = set(entry_ids), deque(entry_ids)
    while pending:
        for entry_id in graph.get(pending.popleft(), ()):
            if entry_id not in found:
                found.add(entry_id)
                pending.append(entry_id)
    return found


def scoped_entries(payload, entry_ids=None):
    from .budget_attributions import source_entries
    entries = source_entries(payload)
    if entry_ids is None:
        return entries
    try:
        selected, pending = set(), list(entry_ids)
        while pending:
            key = pending.pop()
            if type(key) is not int or key not in entries:
                raise ValueError
            if key in selected:
                continue
            selected.add(key)
            pending.extend(entries[key]["claim_evidence"]["related_entry_ids"])
            pending.extend(entries[key]["lineage"]["ancestor_ids"])
        return {key: entries[key] for key in selected}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Select captured journals with complete claim dependencies.") from exc


def verified_claims(captured, *, entry_ids=None):
    """Verify captured current approvals without reading live claim pointers.

    This verifies retained evidence, not the authenticity of an arbitrary client's
    checksummed object. Callers must supply a trusted server capture or retained
    artifact. It neither selects an expenditure basis nor certifies a statement.
    """
    from .budget_native_sources import verify
    from . import claim_attributions as history
    from . import shared_claim_proposals as shared_service
    payload = verify(captured)
    if payload["schema"] < 3:
        raise ValidationError("Recapture claim evidence before using native Budget settlement links.")
    entries = scoped_entries(payload, entry_ids)
    if any(entry["claim_evidence"]["issues"] for entry in entries.values()):
        raise ValidationError("Resolve missing or malformed claim source references before attribution review.")
    lines = {line["id"]: (entry, line) for entry in entries.values() for line in entry["lines"]}
    fund = payload["scope"]["fund"]

    def journal(entry):
        # Reproduce cash_classifications.journal_snapshot's established contract.
        return {"entry": entry["public_id"], "department": entry["department_id"],
            "reference": entry["reference"], "date": entry["entry_date"],
            "fund_id": fund["id"], "period_id": entry["period_id"], "status": "posted",
            "source_type": entry["source_type"], "source_reference": entry["source_reference"],
            "source_snapshot": entry["source_snapshot"], "reversal_of_id": entry["reversal_of_id"],
            "posted_at": entry["posted_at"], "posted_by_id": entry["posted_by_id"],
            "lines": [{"line_id": line["id"], "sequence": line["sequence"],
                "account_id": line["account_id"], "account": line["account"]["code"],
                "account_type": line["account"]["account_type"],
                **{key: line[key] for key in ("debit", "credit", "memo", "responsibility_center_id", "cash_flow_category")}}
                for line in entry["lines"]]}

    def snapshot(source_id, applications):
        selected = [lines[key] for key in sorted({source_id, *applications})]
        selected_entries = {entry["id"]: entry for entry, _ in selected}
        subsidiaries = [{"pk": line["subsidiary"]["id"], "journal_line_id": line["id"],
            **{key: value for key, value in line["subsidiary"].items() if key != "id"}}
            for _, line in selected if line["subsidiary"]]
        result = {"source_line": source_id, "application_lines": sorted(applications),
            "claim_fields": [{"pk": line["id"], **{key: line[key] for key in (
                "payable_origin_id", "payable_reservation_id", "payable_party_key", "payable_claim_reference")}}
                for _, line in selected],
            "journals": [journal(selected_entries[key]) for key in sorted(selected_entries)],
            "subsidiaries": sorted(subsidiaries, key=lambda row: row["pk"])}
        allocations = [{"line": line["id"], "allocation": line["payable_allocation"]}
                       for _, line in selected if line["payable_allocation"]]
        if allocations:
            result["invoice_allocations"] = allocations
        return result

    try:
        records = {key: line["claim_attribution"] for key, (_, line) in lines.items() if line["claim_attribution"]}
        versions = {record["public_id"]: record for record in records.values()}
        versions.update({record["public_id"]: record for record in pinned_versions(entries, set(entries))})
        for record in versions.values():
            source_id = record["source_id"]
            if source_id not in lines:
                raise ValidationError("A retained approval's original credit is absent from this capture.")
            invoices = record["invoice_slices"]
            shared = record["shared_proposal"]
            adapter = SimpleNamespace(**{**record,
                "reviewed_at": datetime.fromisoformat(record["reviewed_at"]) if record["reviewed_at"] else None,
                "is_split": bool(record["allocation_checksum"]),
                "shared_proposal": SimpleNamespace(**shared) if shared else None})
            if (record["source_id"] != source_id or record["department_id"] != fund["department_id"]
                    or record["status"] != "approved" or not record["reviewed_by_id"] or not record["reviewed_at"]
                    or record["reviewed_by_id"] == record["proposed_by_id"]
                    or bool(record["shared_proposal_id"]) != bool(shared)
                    or (adapter.is_split and (record["party_key"] or record["claim_reference"]
                        or len(invoices) < (1 if shared else 2) or checksum(invoices) != record["allocation_checksum"]))
                    or (not adapter.is_split and invoices)
                    or checksum(history.approval_payload(adapter, allocations=invoices)) != record["approval_checksum"]
                    or checksum(record["source_snapshot"]) != record["source_checksum"]
                    or snapshot(source_id, record["applications"]) != record["source_snapshot"]):
                raise ValidationError("Captured claim evidence does not reproduce its source and independent approval.")
        checked_shared = set()
        for record in records.values():
            shared = record["shared_proposal"]
            if shared and any(records[key]["shared_proposal_id"] != shared["id"] for key in shared["source_ids"]):
                raise ValidationError("The current captured shared claim group is incomplete.")
        for record in versions.values():
            shared = record["shared_proposal"]
            if not shared or shared["id"] in checked_shared:
                continue
            checked_shared.add(shared["id"])
            if (shared["id"] != record["shared_proposal_id"] or shared["fund_id"] != fund["id"]
                    or shared["department_id"] != fund["department_id"]
                    or checksum(shared["source_ids"]) != shared["source_set_checksum"]
                    or checksum(shared_service.proposal_payload(SimpleNamespace(**shared))) != shared["proposal_checksum"]
                    or checksum(shared["source_snapshot"]) != shared["source_checksum"]
                    or {str(key): snapshot(key, shared["application_ids"]) for key in shared["source_ids"]} != shared["source_snapshot"]):
                raise ValidationError("Captured shared proposal differs from its retained source evidence.")
            allocations = {row["source_id"]: row for row in shared["allocations"]}
            if set(allocations) != set(shared["source_ids"]) or len(allocations) != len(shared["allocations"]):
                raise ValidationError("Retain every original credit in the captured shared proposal.")
            family = {member["source_id"]: member for member in versions.values()
                      if member["shared_proposal_id"] == shared["id"]}
            if set(family) != set(shared["source_ids"]):
                raise ValidationError("Retain the complete older shared decision, without substituting current heads.")
            for key in shared["source_ids"]:
                member, allocation = family[key], allocations[key]
                if (member["shared_proposal_id"] != shared["id"] or member["shared_proposal"] != shared
                        or member["base_version"] != ((shared["base_approvals"][str(key)] or {}).get("version", 0))
                        or member["version"] <= member["base_version"]
                        or any(member[name] != shared[name] for name in ("evidence_reference", "reason", "proposed_by_id"))
                        or any(member[name] != record[name] for name in ("reviewed_by_id", "reviewed_at", "review_note"))
                        or not member["review_note"].strip()
                        or member["application_amounts"] != allocation["applications"]
                        or member["applications"] != sorted(int(pk) for pk in allocation["applications"])
                        or member["invoice_slices"] != allocation["invoices"]):
                    raise ValidationError("Captured shared claim decisions are incomplete or inconsistent.")
        if any(line["payable_allocation"] for _, line in lines.values()):
            if payload["schema"] < 5:
                raise ValidationError("Recapture original posting evidence before using native invoice allocations.")
            _verify_native_envelopes(entries, lines, records, versions)
        return deepcopy(records)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Captured claim evidence is incomplete or malformed; recapture and resolve its source.") from exc


def _verify_native_envelopes(entries, lines, current, versions):
    """Mirror retained_allocation/shared validation using only captured evidence."""
    from .claim_attributions import attribution_evidence
    from .claim_splits import _shares
    for entry, line in lines.values():
        envelope = line["payable_allocation"]
        if not envelope:
            continue
        shared = isinstance(envelope, dict) and "sources" in envelope
        if shared:
            if (set(envelope) != {"sources"} or not isinstance(envelope["sources"], dict)
                    or len(envelope["sources"]) < 2 or line["payable_origin_id"]
                    or line["payable_reservation_id"] or line["payable_party_key"] or line["payable_claim_reference"]):
                raise ValidationError("Retain complete shared invoice sources without a single-claim override.")
            members = {int(key): value for key, value in envelope["sources"].items()}
            if any(str(key) not in envelope["sources"] for key in members):
                raise ValidationError("Use canonical original-credit identities in shared allocations.")
        else:
            members = {line["payable_origin_id"]: envelope}
        total, group, selected_rows = Decimal("0.00"), None, {}
        for source_id, member in members.items():
            if not isinstance(member, dict) or set(member) != {"attribution", "shares"}:
                raise ValidationError("Retain the exact approval and invoice shares for every original credit.")
            source_entry, source = lines[source_id]
            old = versions[member["attribution"]["public_id"]]
            head = current[source_id]
            adapter = SimpleNamespace(**old, _verified_allocations=old["invoice_slices"])
            shares = _shares(adapter, member["shares"])
            if (old["source_id"] != source_id or not old["allocation_checksum"]
                    or attribution_evidence(adapter) != member["attribution"]
                    or old["invoice_slices"] != head["invoice_slices"] or shares != member["shares"]
                    or source["account_id"] != line["account_id"] or source["account"]["account_type"] != "liability"
                    or source["payable_origin_id"] or Decimal(source["credit"]) <= 0 or Decimal(source["debit"]) != 0
                    or entry["entry_date"] < source_entry["entry_date"]):
                raise ValidationError("Native invoice allocation differs from its original approval and compatible current schedule.")
            if shared:
                if not old["shared_proposal_id"] or (group is not None and group != old["shared_proposal_id"]):
                    raise ValidationError("A shared reversal must retain one complete older decision group.")
                group = old["shared_proposal_id"]
            total += sum((Decimal(value) for value in shares.values()), Decimal("0.00"))
            selected_rows[source_id] = old
        debit, credit = Decimal(line["debit"]), Decimal(line["credit"])
        if (debit > 0) == (credit > 0) or min(debit, credit) < 0 or total != debit + credit:
            raise ValidationError("Retained invoice shares must equal the whole one-sided financial line.")
        events = entry["posting_evidence"]
        evidence = {"source": line["payable_origin_id"], "allocation": envelope,
                    "debit": line["debit"], "credit": line["credit"]}
        if (len(events) != 1 or events[0]["actor_id"] != entry["posted_by_id"]
                or events[0]["snapshot"].get("invoice_allocations", {}).get(str(line["id"])) != evidence):
            raise ValidationError("Native invoice allocation differs from its original independent posting evidence.")
        if entry["reversal_of_id"]:
            parent = entries[entry["reversal_of_id"]]
            prior = next((item for item in parent["lines"] if item["sequence"] == line["sequence"]), None)
            if (not entry["lineage"]["exact_mirror"] or prior is None
                    or prior["account_id"] != line["account_id"]
                    or prior["responsibility_center_id"] != line["responsibility_center_id"]
                    or prior["debit"] != line["credit"] or prior["credit"] != line["debit"]
                    or entry["entry_date"] < parent["entry_date"]):
                raise ValidationError("Retain the exact posted predecessor for a native invoice reversal.")
            if prior["payable_allocation"]:
                if prior["payable_allocation"] != envelope:
                    raise ValidationError("A native reversal must preserve the predecessor's complete retained invoice envelope.")
            else:
                for source_id, old in selected_rows.items():
                    expected = {row["key"]: (row["recognized"] if prior["id"] == source_id else
                        row["applications"].get(str(prior["id"]), "0.00")) for row in old["invoice_slices"]}
                    expected = {key: amount for key, amount in expected.items() if Decimal(amount) > 0}
                    if expected != members[source_id]["shares"]:
                        raise ValidationError("A historical reversal must retain the exact original invoice shares.")
        elif shared or credit:
            raise ValidationError("Shared or restoring invoice applications require exact posted reversal lineage.")
