from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .access import (
    can_approve_period_close, can_approve_period_close_policies,
    can_manage_period_close_policies, can_prepare_period_close, can_reopen_period,
)
from .models import (
    AccountingAuditEvent, AccountingPeriod, BankStatementBatch, ControlAccountReconciliation,
    JournalEntry, JournalLine, PeriodCloseEvent, PeriodClosePolicy, PeriodCloseRun,
    PostingMapping,
)
from .services import FINANCE_DB, actor_label, close_period


def _json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True))


def _checksum(value):
    encoded = json.dumps(
        _json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def period_close_policy_snapshot(policy):
    return {
        "public_id": str(policy.public_id), "version": policy.version,
        "title": policy.title, "description": policy.description,
        "mode": policy.mode, "status": policy.status,
        "require_control_reconciliation": policy.require_control_reconciliation,
        "require_bank_reconciliation": policy.require_bank_reconciliation,
        "require_statement_reports": policy.require_statement_reports,
        "require_handoff_clearance": policy.require_handoff_clearance,
        "require_year_end_closing_entries": policy.require_year_end_closing_entries,
        "authority_reference": policy.authority_reference,
        "local_acceptance_note": policy.local_acceptance_note,
    }


def current_period_close_policy(department_id):
    policies = PeriodClosePolicy.objects.filter(department_id=department_id)
    return policies.filter(status=PeriodClosePolicy.ACTIVE).first() or policies.filter(
        status=PeriodClosePolicy.STARTER,
    ).first()


@transaction.atomic(using=FINANCE_DB)
def ensure_period_close_starter(department, actor):
    existing = current_period_close_policy(department.pk)
    if existing:
        return existing, False
    policy = PeriodClosePolicy.objects.create(
        department_id=department.pk, department_label=department.name, version=1,
        title="Monthly and year-end close checklist starter",
        description=(
            "Broad COA-informed working checklist for unposted JEVs, ordered periods, trial balance, "
            "subsidiary and bank reconciliations, management statements, handoffs, and year-end closing entries."
        ),
        mode=PeriodClosePolicy.OBSERVE, status=PeriodClosePolicy.DRAFT,
        authority_reference=(
            "COA accounting and financial-reporting guidance; exact current LGU close calendar, "
            "responsibilities, supporting schedules, and acceptance remain for local confirmation."
        ),
        created_by_id=actor.pk, created_by_label=actor_label(actor),
    )
    policy.status = PeriodClosePolicy.STARTER
    snapshot = period_close_policy_snapshot(policy)
    policy.snapshot_checksum = _checksum(snapshot)
    policy.save(update_fields=("status", "snapshot_checksum", "updated_at"))
    AccountingAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name,
        action="close_policy_starter_seeded", actor_id=actor.pk, actor_label=actor_label(actor),
        snapshot={"policy": snapshot, "checksum": policy.snapshot_checksum},
    )
    return policy, True


@transaction.atomic(using=FINANCE_DB)
def submit_period_close_policy(policy, actor):
    if not can_manage_period_close_policies(actor):
        raise PermissionDenied
    locked = PeriodClosePolicy.objects.select_for_update().get(pk=policy.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable close-policy draft can be submitted.")
    locked.status = PeriodClosePolicy.SUBMITTED
    locked.submitted_by_id = actor.pk
    locked.submitted_by_label = actor_label(actor)
    locked.submitted_at = timezone.now()
    locked.reviewed_by_id = None
    locked.reviewed_by_label = ""
    locked.reviewed_at = None
    locked.review_note = ""
    locked.save(update_fields=(
        "status", "submitted_by_id", "submitted_by_label", "submitted_at", "reviewed_by_id",
        "reviewed_by_label", "reviewed_at", "review_note", "updated_at",
    ))
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id, department_label=locked.department_label,
        action="close_policy_submitted", actor_id=actor.pk, actor_label=actor_label(actor),
        snapshot={"policy_public_id": str(locked.public_id), "version": locked.version},
    )
    return locked


@transaction.atomic(using=FINANCE_DB)
def decide_period_close_policy(policy, actor, *, approve, note):
    if not can_approve_period_close_policies(actor):
        raise PermissionDenied
    locked = PeriodClosePolicy.objects.select_for_update().get(pk=policy.pk)
    note = str(note or "").strip()
    if locked.status != PeriodClosePolicy.SUBMITTED:
        raise ValidationError("Only a submitted close policy can be reviewed.")
    if actor.pk in {locked.created_by_id, locked.submitted_by_id}:
        raise ValidationError("The close-policy preparer or submitter cannot decide the same version.")
    if not note:
        raise ValidationError("Record the independent review basis or required correction.")
    if not approve:
        locked.status = PeriodClosePolicy.RETURNED
        locked.reviewed_by_id = actor.pk
        locked.reviewed_by_label = actor_label(actor)
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        locked.save(update_fields=(
            "status", "reviewed_by_id", "reviewed_by_label", "reviewed_at", "review_note", "updated_at",
        ))
        action = "close_policy_returned"
    else:
        if not locked.authority_reference.strip() or not locked.local_acceptance_note.strip():
            raise ValidationError("Record the reviewed authority and local acceptance evidence before activation.")
        prior = PeriodClosePolicy.objects.select_for_update().filter(
            department_id=locked.department_id, status=PeriodClosePolicy.ACTIVE,
        ).exclude(pk=locked.pk).first()
        if prior:
            prior.status = PeriodClosePolicy.SUPERSEDED
            prior.save(update_fields=("status", "updated_at"))
        locked.status = PeriodClosePolicy.ACTIVE
        locked.reviewed_by_id = actor.pk
        locked.reviewed_by_label = actor_label(actor)
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        snapshot = period_close_policy_snapshot(locked)
        locked.snapshot_checksum = _checksum(snapshot)
        locked.full_clean()
        locked.save(update_fields=(
            "status", "reviewed_by_id", "reviewed_by_label", "reviewed_at", "review_note",
            "snapshot_checksum", "updated_at",
        ))
        action = "close_policy_activated"
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id, department_label=locked.department_label,
        action=action, actor_id=actor.pk, actor_label=actor_label(actor), reason=note,
        snapshot={"policy": period_close_policy_snapshot(locked), "checksum": locked.snapshot_checksum},
    )
    return locked


def _check(code, label, passed, required, message, evidence=None, *, applicable=True):
    if not applicable:
        status = "not_applicable"
    elif passed:
        status = "passed"
    elif required:
        status = "failed"
    else:
        status = "warning"
    return {
        "code": code, "label": label, "status": status, "required": bool(required),
        "message": message, "evidence": _json_safe(evidence or {}),
    }


def _policy_required(policy, flag):
    return policy.mode == PeriodClosePolicy.ENFORCE and bool(flag)


def evaluate_period_close(period, policy, *, adjustment_review_note=""):
    checks = []
    earlier_open = list(AccountingPeriod.objects.filter(
        department_id=period.department_id, fiscal_year=period.fiscal_year,
        period_number__lt=period.period_number, status=AccountingPeriod.OPEN,
    ).values_list("period_number", "label"))
    later_closed = list(AccountingPeriod.objects.filter(
        department_id=period.department_id, fiscal_year=period.fiscal_year,
        period_number__gt=period.period_number, status=AccountingPeriod.CLOSED,
    ).values_list("period_number", "label"))
    checks.append(_check(
        "period_open", "Target period is open", period.status == AccountingPeriod.OPEN, True,
        "The period is open and can enter close review." if period.status == AccountingPeriod.OPEN else "The target period is not open.",
        {"status": period.status},
    ))
    checks.append(_check(
        "period_sequence", "Earlier periods closed in order", not earlier_open and not later_closed, True,
        "Earlier periods are closed and no later period is closed ahead of this one."
        if not earlier_open and not later_closed else "Close earlier periods first and correct any later-period sequencing anomaly.",
        {"earlier_open": earlier_open, "later_closed": later_closed},
    ))

    unposted = list(period.journal_entries.exclude(
        status__in=(JournalEntry.POSTED, JournalEntry.VOIDED),
    ).values_list("reference", "status"))
    checks.append(_check(
        "unposted_journals", "All period JEVs resolved", not unposted, True,
        "Every JEV is posted or discarded." if not unposted else f"Resolve {len(unposted)} unposted JEV(s) before close.",
        {"unposted": unposted},
    ))

    totals = JournalLine.objects.filter(
        entry__period=period, entry__status=JournalEntry.POSTED,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    debit = totals["debit"] or Decimal("0.00")
    credit = totals["credit"] or Decimal("0.00")
    checks.append(_check(
        "trial_balance", "Posted period debit and credit agree", debit == credit, True,
        "Posted period debit and credit agree exactly." if debit == credit else "Posted period debit and credit do not agree.",
        {"debit": str(debit), "credit": str(credit), "difference": str(debit - credit)},
    ))
    adjustment_note = str(adjustment_review_note or "").strip()
    checks.append(_check(
        "adjustment_review", "Adjusting and closing-entry review recorded", bool(adjustment_note), True,
        "The preparer recorded the review of adjustments and applicable closing entries."
        if adjustment_note else "Explain the adjustments reviewed, entries posted, or why none are required.",
        {"note": adjustment_note},
    ))

    control_run = ControlAccountReconciliation.objects.filter(
        department_id=period.department_id, as_of_date=period.ends_on, is_balanced=True,
    ).order_by("-prepared_at", "-pk").first()
    control_required = _policy_required(policy, policy.require_control_reconciliation)
    checks.append(_check(
        "subsidiary_control_reconciliation", "Payable and withholding controls reconciled",
        bool(control_run), control_required,
        "A zero-difference control-account reconciliation exists at period end."
        if control_run else "Run the payable/withholding control reconciliation at the exact period end.",
        {
            "public_id": str(control_run.public_id) if control_run else "",
            "checksum": control_run.result_checksum if control_run else "",
            "prepared_at": control_run.prepared_at if control_run else None,
        },
    ))

    bank_codes = list(PostingMapping.objects.filter(
        department_id=period.department_id, category=PostingMapping.BANK, is_active=True,
    ).order_by("source_code").values_list("source_code", flat=True))
    reconciled_banks, missing_banks = [], []
    for code in bank_codes:
        batch = BankStatementBatch.objects.filter(
            department_id=period.department_id, bank_account_code__iexact=code,
            period_end=period.ends_on, status=BankStatementBatch.RECONCILED,
        ).order_by("-reconciled_at", "-pk").first()
        if batch:
            reconciled_banks.append({
                "code": code, "public_id": str(batch.public_id),
                "checksum": batch.reconciliation_checksum,
            })
        else:
            missing_banks.append(code)
    bank_required = _policy_required(policy, policy.require_bank_reconciliation)
    bank_passed = not missing_banks
    checks.append(_check(
        "bank_reconciliation", "Mapped bank accounts reconciled", bank_passed, bank_required,
        "Every active mapped bank account has a reconciled statement at period end."
        if bank_passed and bank_codes else (
            "No active bank-account posting mappings apply." if not bank_codes
            else "Reconcile the missing mapped bank account statement(s): " + ", ".join(missing_banks)
        ),
        {"reconciled": reconciled_banks, "missing": missing_banks}, applicable=bool(bank_codes),
    ))

    statement_evidence, missing_statements = [], []
    try:
        from reporting.models import ReportDefinition, ReportRun
        for dataset_key in ("finance_statement_position", "finance_statement_performance"):
            definition = ReportDefinition.objects.filter(
                department_id=period.department_id, dataset_key=dataset_key, is_active=True,
            ).first()
            run = None
            if definition:
                run = ReportRun.objects.filter(
                    definition=definition, period_start=period.starts_on, period_end=period.ends_on,
                    generated_at__isnull=False, control_status=ReportRun.CONTROL_RECONCILED,
                ).order_by("-generated_at", "-pk").first()
            if run:
                statement_evidence.append({
                    "dataset_key": dataset_key, "run_public_id": str(run.public_id),
                    "dataset_checksum": run.dataset_checksum, "control_checksum": run.control_checksum,
                    "generated_at": run.generated_at,
                })
            else:
                missing_statements.append(dataset_key)
    except Exception as exc:
        missing_statements = ["statement_evidence_unavailable"]
        statement_evidence = [{"error": type(exc).__name__}]
    statements_required = _policy_required(policy, policy.require_statement_reports)
    checks.append(_check(
        "management_statements", "Management statements generated and reconciled",
        not missing_statements, statements_required,
        "Financial position and performance runs for the exact period are reconciled and retained."
        if not missing_statements else "Generate reconciled financial-position and performance runs for the exact period.",
        {"runs": statement_evidence, "missing": missing_statements},
    ))

    pending_handoffs = []
    try:
        from vouchers.models import RemittancePostingRequest, VoucherPostingRequest
        voucher_requests = VoucherPostingRequest.objects.filter(
            finance_department_id=period.department_id, jev_date__range=(period.starts_on, period.ends_on),
        ).exclude(status__in=(
            VoucherPostingRequest.POSTED, VoucherPostingRequest.CANCELLED,
            VoucherPostingRequest.NOT_REQUIRED,
        )).values_list("public_id", "jev_number", "status")
        remittance_requests = RemittancePostingRequest.objects.filter(
            finance_department_id=period.department_id, jev_date__range=(period.starts_on, period.ends_on),
        ).exclude(status__in=(
            RemittancePostingRequest.POSTED, RemittancePostingRequest.CANCELLED,
        )).values_list("public_id", "jev_number", "status")
        pending_handoffs = [
            {"kind": "voucher", "public_id": str(public_id), "reference": reference or "", "status": status}
            for public_id, reference, status in voucher_requests
        ] + [
            {"kind": "remittance", "public_id": str(public_id), "reference": reference, "status": status}
            for public_id, reference, status in remittance_requests
        ]
    except Exception as exc:
        pending_handoffs = [{"kind": "unavailable", "status": type(exc).__name__}]
    handoff_required = _policy_required(policy, policy.require_handoff_clearance)
    checks.append(_check(
        "accounting_handoffs", "Voucher and remittance JEV handoffs resolved",
        not pending_handoffs, handoff_required,
        "All dated source-system Accounting handoffs are posted, cancelled, or governed as no-entry."
        if not pending_handoffs else f"Resolve {len(pending_handoffs)} source-system Accounting handoff(s).",
        {"pending": pending_handoffs},
    ))

    fiscal_start = period.fiscal_year_record.starts_on if period.fiscal_year_record_id else period.starts_on.replace(month=1, day=1)
    fiscal_end = period.fiscal_year_record.ends_on if period.fiscal_year_record_id else period.ends_on.replace(month=12, day=31)
    is_year_end = period.ends_on == fiscal_end or period.period_number == 13
    nominal_balances = []
    if is_year_end:
        grouped = JournalLine.objects.filter(
            entry__department_id=period.department_id, entry__status=JournalEntry.POSTED,
            entry__entry_date__range=(fiscal_start, period.ends_on),
            account__account_type__in=("revenue", "expense"),
        ).values("account__code", "account__normal_balance").annotate(
            debit=Sum("debit"), credit=Sum("credit"),
        )
        for row in grouped:
            debit_value = row["debit"] or Decimal("0.00")
            credit_value = row["credit"] or Decimal("0.00")
            balance = (
                debit_value - credit_value
                if row["account__normal_balance"] == "debit"
                else credit_value - debit_value
            )
            if balance:
                nominal_balances.append({"account_code": row["account__code"], "balance": str(balance)})
    closing_required = _policy_required(policy, policy.require_year_end_closing_entries)
    checks.append(_check(
        "year_end_closing_entries", "Year-end nominal accounts closed",
        not nominal_balances, closing_required,
        "Revenue and expense accounts have zero post-closing balances."
        if is_year_end and not nominal_balances else (
            "Post the independently reviewed closing JEVs before year-end close."
            if is_year_end else "This is not the fiscal-year closing period."
        ),
        {"nonzero_nominal_accounts": nominal_balances}, applicable=is_year_end,
    ))

    failed = [item for item in checks if item["status"] == "failed"]
    warnings = [item for item in checks if item["status"] == "warning"]
    return _json_safe({
        "period": {
            "public_id": period.pk, "fiscal_year": period.fiscal_year,
            "period_number": period.period_number, "label": period.label,
            "starts_on": period.starts_on, "ends_on": period.ends_on,
            "is_adjustment_period": period.is_adjustment_period, "is_year_end": is_year_end,
        },
        "policy": {"public_id": str(policy.public_id), "version": policy.version, "mode": policy.mode},
        "checks": checks, "ready": not failed,
        "required_failure_count": len(failed), "warning_count": len(warnings),
    })


def _record_close_event(run, action, actor, *, reason="", snapshot=None):
    return PeriodCloseEvent.objects.create(
        department_id=run.department_id, department_label=run.department_label, run=run,
        action=action, actor_id=actor.pk, actor_label=actor_label(actor),
        reason=str(reason or "").strip(), snapshot=snapshot or {},
    )


@transaction.atomic(using=FINANCE_DB)
def create_period_close_run(period, department, actor, *, adjustment_review_note, evidence_reference, preparer_note=""):
    if not can_prepare_period_close(actor):
        raise PermissionDenied
    policy = current_period_close_policy(department.pk)
    if not policy:
        policy, _created = ensure_period_close_starter(department, actor)
    locked_period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if locked_period.status != AccountingPeriod.OPEN:
        raise ValidationError("Only an open period can begin a close checklist.")
    latest = PeriodCloseRun.objects.filter(period=locked_period).order_by("-version").first()
    if latest and latest.status in (PeriodCloseRun.DRAFT, PeriodCloseRun.RETURNED):
        raise ValidationError("An editable close checklist already exists for this period.")
    snapshot = period_close_policy_snapshot(policy)
    checklist = evaluate_period_close(
        locked_period, policy, adjustment_review_note=adjustment_review_note,
    )
    run = PeriodCloseRun(
        department_id=department.pk, department_label=department.name, period=locked_period,
        version=(latest.version if latest else 0) + 1, supersedes=latest,
        policy=policy, policy_snapshot=snapshot, policy_checksum=_checksum(snapshot),
        checklist_snapshot=checklist, checklist_checksum=_checksum(checklist),
        adjustment_review_note=str(adjustment_review_note or "").strip(),
        evidence_reference=str(evidence_reference or "").strip(),
        preparer_note=str(preparer_note or "").strip(),
        prepared_by_id=actor.pk, prepared_by_label=actor_label(actor),
    )
    run.full_clean()
    run.save()
    _record_close_event(run, "checklist_prepared", actor, snapshot={
        "checklist_checksum": run.checklist_checksum, "ready": checklist["ready"],
        "warnings": checklist["warning_count"],
    })
    return run


@transaction.atomic(using=FINANCE_DB)
def refresh_period_close_run(run, actor, *, adjustment_review_note, evidence_reference, preparer_note=""):
    if not can_prepare_period_close(actor):
        raise PermissionDenied
    locked = PeriodCloseRun.objects.select_for_update().select_related("period", "policy").get(pk=run.pk)
    if not locked.is_editable:
        raise ValidationError("Only a draft or returned close checklist can be refreshed.")
    locked.adjustment_review_note = str(adjustment_review_note or "").strip()
    locked.evidence_reference = str(evidence_reference or "").strip()
    locked.preparer_note = str(preparer_note or "").strip()
    current_policy = current_period_close_policy(locked.department_id)
    if current_policy and current_policy.pk != locked.policy_id:
        raise ValidationError("A newer close policy is now current. Create a successor close checklist using it.")
    checklist = evaluate_period_close(
        locked.period, locked.policy, adjustment_review_note=locked.adjustment_review_note,
    )
    locked.checklist_snapshot = checklist
    locked.checklist_checksum = _checksum(checklist)
    locked.full_clean()
    locked.save(update_fields=(
        "adjustment_review_note", "evidence_reference", "preparer_note",
        "checklist_snapshot", "checklist_checksum", "updated_at",
    ))
    _record_close_event(locked, "checklist_refreshed", actor, snapshot={
        "checklist_checksum": locked.checklist_checksum, "ready": checklist["ready"],
        "warnings": checklist["warning_count"],
    })
    return locked


@transaction.atomic(using=FINANCE_DB)
def submit_period_close_run(run, actor):
    if not can_prepare_period_close(actor):
        raise PermissionDenied
    locked = PeriodCloseRun.objects.select_for_update().select_related("period", "policy").get(pk=run.pk)
    if not locked.is_editable:
        raise ValidationError("Only a draft or returned close checklist can be submitted.")
    current_policy = current_period_close_policy(locked.department_id)
    if not current_policy or current_policy.pk != locked.policy_id:
        raise ValidationError("The close policy changed. Create a successor checklist using the current version.")
    checklist = evaluate_period_close(
        locked.period, locked.policy, adjustment_review_note=locked.adjustment_review_note,
    )
    if not checklist["ready"]:
        failures = [item["message"] for item in checklist["checks"] if item["status"] == "failed"]
        raise ValidationError(failures)
    locked.checklist_snapshot = checklist
    locked.checklist_checksum = _checksum(checklist)
    locked.status = PeriodCloseRun.SUBMITTED
    locked.submitted_by_id = actor.pk
    locked.submitted_by_label = actor_label(actor)
    locked.submitted_at = timezone.now()
    locked.decided_by_id = None
    locked.decided_by_label = ""
    locked.decided_at = None
    locked.review_note = ""
    locked.state_version += 1
    locked.full_clean()
    locked.save()
    _record_close_event(locked, "submitted", actor, snapshot={
        "checklist_checksum": locked.checklist_checksum, "warning_count": checklist["warning_count"],
    })
    return locked


@transaction.atomic(using=FINANCE_DB)
def decide_period_close_run(run, actor, *, approve, note):
    if not can_approve_period_close(actor):
        raise PermissionDenied
    locked = PeriodCloseRun.objects.select_for_update().select_related("period", "policy").get(pk=run.pk)
    note = str(note or "").strip()
    if locked.status != PeriodCloseRun.SUBMITTED:
        raise ValidationError("Only a submitted close checklist can be reviewed.")
    if actor.pk in {locked.prepared_by_id, locked.submitted_by_id}:
        raise ValidationError("The close preparer or submitter cannot decide the same checklist.")
    if not note:
        raise ValidationError("Record the independent close review or correction basis.")
    if not approve:
        locked.status = PeriodCloseRun.RETURNED
        locked.decided_by_id = actor.pk
        locked.decided_by_label = actor_label(actor)
        locked.decided_at = timezone.now()
        locked.review_note = note
        locked.state_version += 1
        locked.save(update_fields=(
            "status", "decided_by_id", "decided_by_label", "decided_at", "review_note",
            "state_version", "updated_at",
        ))
        _record_close_event(locked, "returned", actor, reason=note)
        return locked
    current_policy = current_period_close_policy(locked.department_id)
    if not current_policy or current_policy.pk != locked.policy_id:
        raise ValidationError("The close policy changed after submission. Return and prepare a successor checklist.")
    current = evaluate_period_close(
        locked.period, locked.policy, adjustment_review_note=locked.adjustment_review_note,
    )
    current_checksum = _checksum(current)
    if current_checksum != locked.checklist_checksum:
        raise ValidationError("Close evidence changed after submission. Return, refresh, and resubmit the checklist.")
    if not current["ready"]:
        raise ValidationError("One or more required close gates no longer pass.")
    close_period(locked.period, actor, approved_run=locked)
    locked.status = PeriodCloseRun.CLOSED
    locked.decided_by_id = actor.pk
    locked.decided_by_label = actor_label(actor)
    locked.decided_at = timezone.now()
    locked.review_note = note
    locked.state_version += 1
    locked.save(update_fields=(
        "status", "decided_by_id", "decided_by_label", "decided_at", "review_note",
        "state_version", "updated_at",
    ))
    _record_close_event(locked, "period_closed", actor, reason=note, snapshot={
        "checklist_checksum": locked.checklist_checksum, "policy_checksum": locked.policy_checksum,
    })
    return locked


@transaction.atomic(using=FINANCE_DB)
def request_period_reopen(run, actor, *, reason, authority_reference):
    if not can_prepare_period_close(actor):
        raise PermissionDenied
    locked = PeriodCloseRun.objects.select_for_update().select_related("period").get(pk=run.pk)
    reason = str(reason or "").strip()
    authority_reference = str(authority_reference or "").strip()
    if locked.status != PeriodCloseRun.CLOSED or locked.period.status != AccountingPeriod.CLOSED:
        raise ValidationError("Only the current closed-period evidence can enter a reopen request.")
    if not reason or not authority_reference:
        raise ValidationError("Explain the correction and record the authority/evidence for reopening.")
    locked.status = PeriodCloseRun.REOPEN_REQUESTED
    locked.reopen_requested_by_id = actor.pk
    locked.reopen_requested_by_label = actor_label(actor)
    locked.reopen_requested_at = timezone.now()
    locked.reopen_reason = reason
    locked.reopen_authority_reference = authority_reference
    locked.state_version += 1
    locked.save(update_fields=(
        "status", "reopen_requested_by_id", "reopen_requested_by_label", "reopen_requested_at",
        "reopen_reason", "reopen_authority_reference", "state_version", "updated_at",
    ))
    _record_close_event(locked, "reopen_requested", actor, reason=reason, snapshot={
        "authority_reference": authority_reference,
    })
    return locked


@transaction.atomic(using=FINANCE_DB)
def decide_period_reopen(run, actor, *, approve, note):
    if not can_reopen_period(actor):
        raise PermissionDenied
    locked = PeriodCloseRun.objects.select_for_update().select_related("period").get(pk=run.pk)
    note = str(note or "").strip()
    if locked.status != PeriodCloseRun.REOPEN_REQUESTED:
        raise ValidationError("Only a submitted reopen request can be decided.")
    if actor.pk == locked.reopen_requested_by_id:
        raise ValidationError("The reopen requester cannot approve the same request.")
    if not note:
        raise ValidationError("Record the independent reopen decision basis.")
    if not approve:
        locked.status = PeriodCloseRun.CLOSED
        locked.reopen_review_note = note
        locked.state_version += 1
        locked.save(update_fields=("status", "reopen_review_note", "state_version", "updated_at"))
        _record_close_event(locked, "reopen_returned", actor, reason=note)
        return locked
    later_closed = AccountingPeriod.objects.filter(
        department_id=locked.department_id, fiscal_year=locked.period.fiscal_year,
        period_number__gt=locked.period.period_number, status=AccountingPeriod.CLOSED,
    ).exists()
    if later_closed:
        raise ValidationError("Reopen later closed periods first; period chronology cannot be broken.")
    period = AccountingPeriod.objects.select_for_update().get(pk=locked.period_id)
    period.status = AccountingPeriod.OPEN
    period.closed_by_id = None
    period.closed_by_label = ""
    period.closed_at = None
    period.save(update_fields=("status", "closed_by_id", "closed_by_label", "closed_at"))
    locked.status = PeriodCloseRun.REOPENED
    locked.reopened_by_id = actor.pk
    locked.reopened_by_label = actor_label(actor)
    locked.reopened_at = timezone.now()
    locked.reopen_review_note = note
    locked.state_version += 1
    locked.save(update_fields=(
        "status", "reopened_by_id", "reopened_by_label", "reopened_at", "reopen_review_note",
        "state_version", "updated_at",
    ))
    _record_close_event(locked, "period_reopened", actor, reason=note, snapshot={
        "reopen_reason": locked.reopen_reason,
        "authority_reference": locked.reopen_authority_reference,
    })
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id, department_label=locked.department_label,
        action="period_reopened", actor_id=actor.pk, actor_label=actor_label(actor), reason=note,
        snapshot={
            "period_id": period.pk, "fiscal_year": period.fiscal_year,
            "period_number": period.period_number, "close_run_public_id": str(locked.public_id),
        },
    )
    return locked
