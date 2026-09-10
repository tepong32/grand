"""Reviewed cash-flow metadata; never edits or creates financial journal entries."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from finance.cash_flows import CASH_FLOW_BY_CODE
from .access import can_view_accounting, department_for_user
from .models import CashFlowClassification, CashFlowClassificationHead, JournalEntry


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def can_prepare(user):
    from reporting.access import can_manage_statement_mappings
    return can_view_accounting(user) and can_manage_statement_mappings(user)


def can_review(user):
    from reporting.access import can_review_statement_mappings
    return can_view_accounting(user) and can_review_statement_mappings(user)


def _locked_entry(entry_id, actor, review=False):
    if not (can_review(actor) if review else can_prepare(actor)):
        raise PermissionDenied
    entry = JournalEntry.objects.select_for_update().select_related("fund").filter(
        pk=entry_id, department_id=department_for_user(actor).pk).first()
    if entry is None:
        raise PermissionDenied
    if entry.status != JournalEntry.POSTED:
        raise ValidationError("Cash classifications require an already posted journal.")
    if entry.statement_source_type == "opening":
        raise ValidationError("Opening entries establish balances; classify actual cash movements instead.")
    return entry


def cash_scope(department):
    from reporting.models import FinanceStatementMapping
    from reporting.statement_services import current_statement_mapping, statement_mapping_snapshot
    mapping = current_statement_mapping(department, FinanceStatementMapping.CASH_FLOW)
    if not mapping or mapping.status != FinanceStatementMapping.ACTIVE:
        raise ValidationError("Activate an independently reviewed Cash Flow account scope first.")
    return statement_mapping_snapshot(mapping)


def cash_codes(scope):
    return {code for line in scope.get("lines", []) for code in line.get("account_codes", [])}


def journal_snapshot(entry):
    return {"entry": str(entry.public_id), "department": entry.department_id,
        "reference": entry.reference, "date": entry.entry_date.isoformat(),
        "fund_id": entry.fund_id, "period_id": entry.period_id, "status": entry.status,
        "source_type": entry.source_type, "source_reference": entry.source_reference,
        "source_snapshot": entry.source_snapshot, "reversal_of_id": entry.reversal_of_id,
        "posted_at": entry.posted_at.isoformat() if entry.posted_at else None, "posted_by_id": entry.posted_by_id,
        "lines": [{"line_id": line.pk, "sequence": line.sequence, "account_id": line.account_id,
            "account": line.account.code, "account_type": line.account.account_type,
            "debit": str(line.debit), "credit": str(line.credit), "memo": line.memo,
            "responsibility_center_id": line.responsibility_center_id,
            "cash_flow_category": line.cash_flow_category}
            for line in entry.lines.select_related("account").order_by("sequence", "pk")]}


def normalize_allocations(source, scope, allocations):
    lines = {line["line_id"]: line for line in source["lines"] if line["account"] in cash_codes(scope)}
    if not lines:
        raise ValidationError("This journal has no lines in the reviewed cash scope.")
    if not isinstance(allocations, list) or not allocations:
        raise ValidationError("Allocate every posted cash line to its actual cash-flow purposes.")
    totals = {key: Decimal("0.00") for key in lines}
    normalized = []
    for item in allocations:
        try:
            line_id = int(str(item["line_id"]))
            amount = Decimal(str(item["amount"]))
            category = item["category"]
            if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
                raise ValueError
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise ValidationError("Use positive, exact two-decimal allocations on this journal's cash lines.")
        if line_id not in lines or not isinstance(category, str) or category not in CASH_FLOW_BY_CODE:
            raise ValidationError("Choose a cash line from this journal and a supported cash-flow purpose.")
        totals[line_id] += amount
        normalized.append({"line_id": line_id, "category": category, "amount": f"{amount:.2f}"})
    for line_id, line in lines.items():
        if line["account_type"] != "asset" or totals[line_id] != Decimal(line["debit"]) + Decimal(line["credit"]):
            raise ValidationError(f"Allocations for line {line['sequence']} must equal its posted cash amount exactly.")
    return sorted(normalized, key=lambda row: (row["line_id"], row["category"], Decimal(row["amount"])))


def current_version(entry):
    head = CashFlowClassificationHead.objects.select_related("classification").filter(entry_id=entry.pk).first()
    return head.classification.version if head else 0


def approval_payload(record):
    return {"public_id": str(record.public_id), "entry_id": record.entry_id, "version": record.version,
        "base_version": record.base_version, "source_checksum": record.source_checksum,
        "cash_scope": record.cash_scope_snapshot, "allocations": record.allocations,
        "reason": record.reason, "evidence_reference": record.evidence_reference,
        "proposed_by_id": record.proposed_by_id, "reviewed_by_id": record.reviewed_by_id,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "review_note": record.review_note}


@transaction.atomic(using="finance")
def propose_classification(entry, actor, allocations, *, reason, evidence_reference, expected_version):
    stored = _locked_entry(entry.pk, actor)
    if expected_version != current_version(stored):
        raise ValidationError("The approved classification changed. Reload before proposing its replacement.")
    if not reason.strip() or not evidence_reference.strip():
        raise ValidationError("Record the cash-purpose explanation and supporting evidence reference.")
    scope = cash_scope(department_for_user(actor))
    source = journal_snapshot(stored)
    normalized = normalize_allocations(source, scope, allocations)
    version = (stored.cash_classifications.aggregate(value=Max("version"))["value"] or 0) + 1
    return CashFlowClassification.objects.create(entry=stored, department_id=stored.department_id,
        department_label=stored.department_label, version=version, base_version=expected_version,
        source_snapshot=source, source_checksum=checksum(source), cash_scope_snapshot=scope,
        allocations=normalized, reason=reason.strip(), evidence_reference=evidence_reference.strip(),
        proposed_by_id=actor.pk, proposed_by_label=actor.get_full_name() or actor.username)


@transaction.atomic(using="finance")
def review_classification(record, actor, *, approve, note):
    identity = CashFlowClassification.objects.only("entry_id").get(pk=record.pk)
    entry = _locked_entry(identity.entry_id, actor, review=True)
    stored = CashFlowClassification.objects.select_for_update().get(pk=record.pk, entry=entry)
    if stored.status != CashFlowClassification.SUBMITTED:
        raise ValidationError("Only a submitted classification can be reviewed.")
    if stored.proposed_by_id == actor.pk:
        raise ValidationError("A different authorized reviewer must decide this classification.")
    if not note.strip():
        raise ValidationError("Record the review decision and its basis.")
    if approve:
        if stored.base_version != current_version(entry):
            raise ValidationError("Another classification was approved first. Return this stale proposal and prepare a successor.")
        source = journal_snapshot(entry)
        if checksum(source) != stored.source_checksum or source != stored.source_snapshot:
            raise ValidationError("The posted source no longer matches the proposed cash evidence.")
        if cash_scope(department_for_user(actor)) != stored.cash_scope_snapshot:
            raise ValidationError("The reviewed cash scope changed; submit a new proposal under the current scope.")
        normalize_allocations(source, stored.cash_scope_snapshot, stored.allocations)
    stored.status = CashFlowClassification.APPROVED if approve else CashFlowClassification.RETURNED
    stored.reviewed_by_id = actor.pk
    stored.reviewed_by_label = actor.get_full_name() or actor.username
    stored.reviewed_at = timezone.now()
    stored.review_note = note.strip()
    stored.approval_checksum = checksum(approval_payload(stored)) if approve else ""
    stored._review_transition = True
    stored.save()
    if approve:
        head = CashFlowClassificationHead.objects.filter(entry=entry).first()
        if head:
            head.classification = stored
            head.save(update_fields=("classification",))
        else:
            CashFlowClassificationHead.objects.create(entry=entry, classification=stored)
    return stored


def selected_classification(entry, heads=None):
    """Resolve an entry's own reviewed version, or a proved actual reversal's ancestor."""
    entry.statement_origin  # Validate cycle and owning-office boundaries.
    ancestor = entry
    while True:
        if heads is not None and ancestor.pk in heads:
            head = heads[ancestor.pk]
        else:
            head = CashFlowClassificationHead.objects.select_related("classification", "classification__entry").filter(entry=ancestor).first()
            if heads is not None:
                heads[ancestor.pk] = head
        if head:
            record = head.classification
            if (record.status != CashFlowClassification.APPROVED or record.entry_id != ancestor.pk
                    or not record.reviewed_at or not record.reviewed_by_id or record.reviewed_by_id == record.proposed_by_id
                    or checksum(approval_payload(record)) != record.approval_checksum
                    or checksum(journal_snapshot(ancestor)) != record.source_checksum
                    or checksum(record.source_snapshot) != record.source_checksum):
                raise ValidationError("Approved cash-classification evidence no longer reproduces its source and decision.")
            normalize_allocations(record.source_snapshot, record.cash_scope_snapshot, record.allocations)
            if ancestor.fund_id != entry.fund_id:
                raise ValidationError("Cash-classification reversal inheritance cannot cross funds.")
            return record
        if not ancestor.reversal_of_id:
            return None
        parent = ancestor.reversal_of
        child_lines = list(ancestor.lines.order_by("sequence").values_list(
            "sequence", "account_id", "debit", "credit", "responsibility_center_id"))
        mirrored_parent = [(sequence, account, credit, debit, center)
            for sequence, account, debit, credit, center in parent.lines.order_by("sequence").values_list(
                "sequence", "account_id", "debit", "credit", "responsibility_center_id")]
        if ancestor.fund_id != parent.fund_id or child_lines != mirrored_parent:
            raise ValidationError("Cash-classification inheritance requires an exact financial reversal.")
        ancestor = parent


def apply_to_report_sources(sources):
    """Attach retained allocations while leaving the original journal snapshot visible."""
    from django.urls import reverse
    from reporting.datasets import _snapshot_checksum
    journal_sources = [source for source in sources if source["source_model"] == "JournalEntry"]
    ids = [int(source["source_pk"]) for source in journal_sources]
    heads = dict.fromkeys(ids)
    heads.update({head.entry_id: head for head in CashFlowClassificationHead.objects.filter(entry_id__in=ids)
        .select_related("classification", "classification__entry")})
    eligible = [source for source in journal_sources if heads[int(source["source_pk"])]
        or source["snapshot"]["statement_origin_public_id"] != source["source_public_id"]]
    entries = {entry.pk: entry for entry in JournalEntry.objects.filter(pk__in=[int(source["source_pk"]) for source in eligible])
        .select_related("fund", "reversal_of")}
    retained = {}
    for source in eligible:
        entry = entries[int(source["source_pk"])]
        record = selected_classification(entry, heads)
        if record is None:
            continue
        original_lines = {line["line_id"]: line for line in record.source_snapshot["lines"]}
        current_lines = {line["sequence"]: line for line in source["snapshot"]["lines"]}
        allocations = {}
        for item in record.allocations:
            original = original_lines[item["line_id"]]
            line = current_lines.get(original["sequence"])
            if (line is None or line["account"] != original["account"]
                    or Decimal(line["debit"]) + Decimal(line["credit"]) != Decimal(original["debit"]) + Decimal(original["credit"])):
                raise ValidationError("The current cash line does not reproduce the approved classification source.")
            allocations.setdefault(original["sequence"], []).append({"category": item["category"], "amount": item["amount"]})
        for sequence, parts in allocations.items():
            current_lines[sequence]["cash_flow_allocations"] = parts
            current_lines[sequence]["cash_classification_public_id"] = str(record.public_id)
        source["snapshot"]["cash_classification"] = {"public_id": str(record.public_id), "version": record.version,
            "source_entry": record.source_snapshot["entry"], "approval_checksum": record.approval_checksum}
        source["source_checksum"] = _snapshot_checksum(source["snapshot"])
        retained[record.pk] = record
    for record in retained.values():
        sources.append({"source_app": "accounting", "source_model": "CashFlowClassification",
            "source_pk": str(record.pk), "source_public_id": str(record.public_id),
            "source_reference": f"{record.entry.reference} cash classification v{record.version}",
            "source_date": record.entry.entry_date, "control_group": "reviewed cash purposes",
            "amount": sum((Decimal(item["amount"]) for item in record.allocations), Decimal("0.00")),
            "source_checksum": record.approval_checksum,
            "source_url": reverse("accounting:cash_classification", kwargs={"public_id": record.entry.public_id})
                + f"#classification-{record.public_id}",
            "snapshot": {**approval_payload(record), "source_snapshot": record.source_snapshot}})
    return [record.reviewed_at for record in retained.values()]
