from __future__ import annotations

import csv
import hashlib
import io
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from src.export_archive import archive_export

from .access import (
    can_manage_finance_discovery,
    can_prepare_finance_discovery_decision,
    can_review_finance_discovery_decision,
    can_view_finance_discovery_decision,
)
from .models import FinanceAuditEvent, FinanceDiscoveryDecision


def discovery_decision_snapshot(item):
    return {
        "public_id": str(item.public_id),
        "department_id": item.department_id,
        "cycle_id": item.cycle_id,
        "code": item.code,
        "version": item.version,
        "phase": item.phase,
        "coverage_kind": item.coverage_kind,
        "question": item.question,
        "proposed_outcome": item.proposed_outcome,
        "affected_scope": item.affected_scope,
        "evidence_label": item.evidence_label,
        "authority_evidence_reference": item.authority_evidence_reference,
        "evidence_needed": item.evidence_needed,
        "evidence_custody_reference": item.evidence_custody_reference,
        "acceptance_example_reference": item.acceptance_example_reference,
        "blocks_affected_scope": item.blocks_affected_scope,
        "owner_id": item.owner_id,
        "reviewer_id": item.reviewer_id,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "predecessor_id": item.predecessor_id,
        "change_reason": item.change_reason,
    }


def discovery_decision_checksum(snapshot):
    return hashlib.sha256(
        json.dumps(snapshot, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _event(item, actor, action, *, reason="", snapshot=None):
    FinanceAuditEvent.objects.create(
        department=item.department,
        target_type="financediscoverydecision",
        target_id=str(item.pk),
        action=action,
        actor=actor,
        reason=str(reason or "").strip(),
        snapshot=snapshot or {},
    )


COVERAGE_STARTERS = (
    (FinanceDiscoveryDecision.SCOPE_ACCEPTANCE, "SCOPE", "Has the LGU accepted this complete enabled scope after reviewing every coverage row?"),
    (FinanceDiscoveryDecision.STEP, "STEP", "Are all required process steps, gates, handoffs, and repeated visits identified?"),
    (FinanceDiscoveryDecision.FIELD, "FIELD", "Are all required fields, classifications, and source values identified?"),
    (FinanceDiscoveryDecision.BALANCE, "BAL", "Are all affected balances, equations, control totals, and reconciliation points identified?"),
    (FinanceDiscoveryDecision.CERTIFICATION, "CERT", "Are all certifications, approvals, and conditions for the next action identified?"),
    (FinanceDiscoveryDecision.SIGNATURE, "SIGN", "Are all accountable actors, signing orders, acting rules, and custody points identified?"),
    (FinanceDiscoveryDecision.NUMBER, "NUM", "Are all official numbers, assignment times, preserved identifiers, and replacement rules identified?"),
    (FinanceDiscoveryDecision.OUTPUT, "OUT", "Are all forms, registers, reports, print/layout needs, recipients, and retention outputs identified?"),
    (FinanceDiscoveryDecision.EXCEPTION, "EXC", "Are all returns, corrections, cancellations, reversals, reprints, replacements, downtime, and emergency paths identified?"),
)


@transaction.atomic
def create_discovery_coverage_starters(cycle, actor, *, owner, reviewer, due_date=None):
    cycle = type(cycle).objects.select_for_update().select_related("department").get(pk=cycle.pk)
    if not can_manage_finance_discovery(actor, cycle.department):
        raise PermissionDenied
    if owner.pk == reviewer.pk:
        raise ValidationError("Choose a reviewer other than the evidence owner.")
    if actor.pk == reviewer.pk:
        raise ValidationError("The person creating the starter set cannot review the same rows.")
    current_kinds = set(
        cycle.discovery_decisions.exclude(status=FinanceDiscoveryDecision.SUPERSEDED)
        .values_list("coverage_kind", flat=True)
    )
    created = []
    for coverage_kind, suffix, question in COVERAGE_STARTERS:
        if coverage_kind in current_kinds:
            continue
        base_code = f"F0-{cycle.pk}-{suffix}"
        code = base_code
        copy_number = 2
        while FinanceDiscoveryDecision.objects.filter(
            department=cycle.department, code=code, version=1,
        ).exists():
            code = f"{base_code[:35]}-{copy_number}"
            copy_number += 1
        item = FinanceDiscoveryDecision.objects.create(
            department=cycle.department,
            cycle=cycle,
            code=code,
            phase="F0",
            coverage_kind=coverage_kind,
            question=question,
            proposed_outcome=(
                "Keep this named coverage area unresolved until the retained local evidence, acceptance example, and accountable decision are reviewed."
            ),
            affected_scope=cycle.enabled_scope,
            evidence_label=FinanceDiscoveryDecision.UNRESOLVED,
            evidence_needed=(
                "Edit this starter to list the exact locally applicable items, then reference the retained authority, redacted example or accepted no-case explanation, and custody location."
            ),
            blocks_affected_scope=True,
            owner=owner,
            reviewer=reviewer,
            due_date=due_date,
            created_by=actor,
        )
        _event(item, actor, "discovery_coverage_starter_created", snapshot={
            "public_id": str(item.public_id),
            "code": item.code,
            "coverage_kind": item.coverage_kind,
            "cycle_id": cycle.pk,
            "affected_scope": item.affected_scope,
        })
        created.append(item)
    return created


@transaction.atomic
def submit_discovery_decision(item, actor):
    item = FinanceDiscoveryDecision.objects.select_for_update().select_related(
        "department", "owner", "reviewer", "predecessor",
    ).get(pk=item.pk)
    if not can_prepare_finance_discovery_decision(actor, item):
        raise PermissionDenied
    if item.status not in {FinanceDiscoveryDecision.DRAFT, FinanceDiscoveryDecision.RETURNED}:
        raise ValidationError("Only a draft or returned decision can be submitted.")
    if actor.pk == item.reviewer_id:
        raise ValidationError("The submitter cannot be the named reviewer.")
    if item.evidence_label == FinanceDiscoveryDecision.UNRESOLVED:
        if not item.blocks_affected_scope:
            raise ValidationError("An unresolved finding must keep only its named affected scope blocked.")
    elif not item.authority_evidence_reference.strip() or not item.evidence_custody_reference.strip():
        raise ValidationError("Reference the reviewed evidence and its custody location before submission.")
    if not item.evidence_needed.strip():
        raise ValidationError("Describe the evidence still needed or why the supplied evidence is sufficient.")
    snapshot = discovery_decision_snapshot(item)
    item.evidence_snapshot = snapshot
    item.evidence_checksum = discovery_decision_checksum(snapshot)
    item.status = FinanceDiscoveryDecision.SUBMITTED
    item.submitted_by = actor
    item.submitted_at = timezone.now()
    item.reviewed_by = None
    item.reviewed_at = None
    item.review_note = ""
    item.save()
    _event(item, actor, "discovery_decision_submitted", snapshot={
        "evidence_snapshot": snapshot,
        "evidence_checksum": item.evidence_checksum,
    })
    return item


@transaction.atomic
def review_discovery_decision(item, actor, *, record, reason):
    item = FinanceDiscoveryDecision.objects.select_for_update().select_related(
        "department", "owner", "reviewer", "predecessor",
    ).get(pk=item.pk)
    if not can_review_finance_discovery_decision(actor, item):
        raise PermissionDenied
    if item.status != FinanceDiscoveryDecision.SUBMITTED:
        raise ValidationError("This decision is not awaiting review.")
    if not str(reason or "").strip():
        raise ValidationError("Record the review basis or exact correction required.")
    current_snapshot = discovery_decision_snapshot(item)
    if current_snapshot != item.evidence_snapshot or discovery_decision_checksum(current_snapshot) != item.evidence_checksum:
        raise ValidationError("The submitted decision evidence changed. Return it and submit a fresh locked snapshot.")
    item.review_note = str(reason).strip()
    if record:
        item.status = FinanceDiscoveryDecision.RECORDED
        item.reviewed_by = actor
        item.reviewed_at = timezone.now()
        item.save()
        if item.predecessor_id and item.predecessor.status == FinanceDiscoveryDecision.RECORDED:
            predecessor = FinanceDiscoveryDecision.objects.select_for_update().get(pk=item.predecessor_id)
            predecessor.status = FinanceDiscoveryDecision.SUPERSEDED
            predecessor.save(update_fields=("status", "updated_at"))
        action = "discovery_decision_recorded"
    else:
        item.status = FinanceDiscoveryDecision.RETURNED
        item.reviewed_by = None
        item.reviewed_at = None
        item.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        action = "discovery_decision_returned"
    _event(item, actor, action, reason=reason, snapshot={
        "status": item.status,
        "evidence_checksum": item.evidence_checksum,
        "blocks_affected_scope": item.blocks_affected_scope,
        "evidence_label": item.evidence_label,
    })
    return item


def export_discovery_decision(item, actor):
    if not can_view_finance_discovery_decision(actor, item):
        raise PermissionDenied
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("field", "value"))
    rows = (
        ("decision", f"{item.code} v{item.version}"),
        ("phase", item.phase),
        ("coverage_area", item.get_coverage_kind_display()),
        ("status", item.get_status_display()),
        ("question", item.question),
        ("outcome_or_current_position", item.proposed_outcome),
        ("evidence_label", item.get_evidence_label_display()),
        ("affected_scope", item.affected_scope),
        ("scope_blocked", "yes" if item.blocks_affected_scope else "no"),
        ("authority_or_evidence_reference", item.authority_evidence_reference),
        ("evidence_needed_or_sufficiency", item.evidence_needed),
        ("evidence_custody", item.evidence_custody_reference),
        ("acceptance_example", item.acceptance_example_reference),
        ("owner", item.owner.get_full_name() or item.owner.username),
        ("reviewer", item.reviewer.get_full_name() or item.reviewer.username),
        ("due_date", item.due_date or ""),
        ("cycle", item.cycle.code if item.cycle_id else ""),
        ("predecessor", f"{item.predecessor.code} v{item.predecessor.version}" if item.predecessor_id else ""),
        ("change_reason", item.change_reason),
        ("review_basis", item.review_note),
        ("evidence_checksum", item.evidence_checksum),
        ("notice", "Portable decision evidence; it blocks or clears only the recorded affected scope and is not cutover authority."),
    )
    writer.writerows(rows)
    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    filename = f"{item.code.lower()}-v{item.version}-finance-decision.csv"
    receipt = archive_export(
        content=content,
        department=item.department,
        user=actor,
        category="finance-discovery-decisions",
        filename=filename,
        metadata={
            "decision_public_id": str(item.public_id),
            "decision_code": item.code,
            "decision_version": item.version,
            "status": item.status,
            "evidence_label": item.evidence_label,
            "scope_blocked": item.blocks_affected_scope,
            "evidence_checksum": item.evidence_checksum,
        },
    )
    _event(item, actor, "discovery_decision_exported", snapshot={
        "relative_path": receipt["relative_path"],
        "sha256": receipt["sha256"],
        "status": item.status,
    })
    return content, filename, receipt
