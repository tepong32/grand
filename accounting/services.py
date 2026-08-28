import hashlib
import json
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from .access import can_approve_fiscal_readiness, can_manage_setup
from .models import (
    AccountingAuditEvent, AccountingPeriod, FiscalYear, FiscalYearReadinessApproval,
    Fund, FundingSource, JournalEntry, JournalLine, LedgerAccount,
    ProgramActivityProject, ResponsibilityCenter,
)


FINANCE_DB = "finance"


def actor_label(actor):
    return actor.get_full_name() or actor.username


def ensure_readiness_layers(fiscal_year):
    layers = []
    for code, _label in FiscalYearReadinessApproval.LAYER_CHOICES:
        layer, _created = FiscalYearReadinessApproval.objects.get_or_create(
            fiscal_year=fiscal_year,
            layer=code,
            defaults={
                "department_id": fiscal_year.department_id,
                "department_label": fiscal_year.department_label,
            },
        )
        layers.append(layer)
    return layers


def evaluate_fiscal_year_readiness(fiscal_year):
    structural = {
        FiscalYearReadinessApproval.TECHNICAL: (
            fiscal_year.periods.exists(),
            "At least one accounting period is linked to the typed fiscal year.",
        ),
        FiscalYearReadinessApproval.BUDGET: (
            fiscal_year.funding_sources.filter(is_active=True).exists()
            and fiscal_year.program_classifications.filter(is_active=True).exists(),
            "At least one active funding source and PPA/MFO/project/activity classification exist.",
        ),
        FiscalYearReadinessApproval.ACCOUNTING: (
            Fund.objects.filter(department_id=fiscal_year.department_id, is_active=True).exists()
            and LedgerAccount.objects.filter(
                department_id=fiscal_year.department_id, is_active=True, allow_posting=True,
            ).exists(),
            "An active fund and posting account exist for Accounting.",
        ),
        FiscalYearReadinessApproval.TREASURY: (
            True,
            "Treasury records its independent cash, bank, payment-method, and custody readiness evidence.",
        ),
        FiscalYearReadinessApproval.FORMS: (
            True,
            "The forms owner records independent template and output readiness evidence.",
        ),
    }
    results = []
    records = {layer.layer: layer for layer in fiscal_year.readiness_layers.all()}
    for layer_code, _label in FiscalYearReadinessApproval.LAYER_CHOICES:
        layer = records.get(layer_code)
        if layer is None:
            continue
        checks_passed, check_message = structural[layer.layer]
        results.append({
            "record": layer,
            "checks_passed": checks_passed,
            "check_message": check_message,
            "passed": checks_passed and layer.status == FiscalYearReadinessApproval.APPROVED,
        })
    return {
        "ready": len(results) == len(FiscalYearReadinessApproval.LAYER_CHOICES)
        and all(item["passed"] for item in results),
        "layers": results,
    }


@transaction.atomic(using=FINANCE_DB)
def transition_fiscal_year(fiscal_year, action, actor):
    locked = FiscalYear.objects.select_for_update().get(pk=fiscal_year.pk)
    if action == "submit":
        if not can_manage_setup(actor) or locked.status != FiscalYear.DRAFT:
            raise ValidationError("Only an authorized setup manager can submit a draft fiscal year.")
        locked.status = FiscalYear.FOR_REVIEW
        locked.submitted_by_id = actor.pk
        locked.submitted_by_label = actor_label(actor)
        locked.submitted_at = timezone.now()
        fields = ("status", "submitted_by_id", "submitted_by_label", "submitted_at", "state_version", "updated_at")
    elif action == "approve":
        if not can_approve_fiscal_readiness(actor) or locked.status != FiscalYear.FOR_REVIEW:
            raise ValidationError("Only an authorized setup approver can approve a submitted fiscal year.")
        if actor.pk in {locked.created_by_id, locked.submitted_by_id}:
            raise ValidationError("The fiscal-year approver must be different from its preparer and submitter.")
        locked.status = FiscalYear.APPROVED
        locked.approved_by_id = actor.pk
        locked.approved_by_label = actor_label(actor)
        locked.approved_at = timezone.now()
        fields = ("status", "approved_by_id", "approved_by_label", "approved_at", "state_version", "updated_at")
    elif action == "activate":
        if not can_approve_fiscal_readiness(actor) or locked.status != FiscalYear.APPROVED:
            raise ValidationError("Only an authorized setup approver can activate an approved fiscal year.")
        readiness = evaluate_fiscal_year_readiness(locked)
        if not readiness["ready"]:
            raise ValidationError("All five readiness layers and their structural checks must pass before activation.")
        FiscalYear.objects.select_for_update().filter(
            department_id=locked.department_id, status=FiscalYear.ACTIVE,
        ).exclude(pk=locked.pk).update(status=FiscalYear.APPROVED)
        locked.status = FiscalYear.ACTIVE
        fields = ("status", "state_version", "updated_at")
    else:
        raise ValidationError("Unsupported fiscal-year action.")
    locked.state_version += 1
    locked.full_clean()
    locked.save(update_fields=fields)
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id,
        department_label=locked.department_label,
        action=f"fiscal_year_{action}",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={"fiscal_year_id": str(locked.public_id), "year": locked.year, "state_version": locked.state_version},
    )
    ensure_readiness_layers(locked)
    return locked


@transaction.atomic(using=FINANCE_DB)
def decide_readiness_layer(layer, actor, *, decision, evidence_note):
    if not can_approve_fiscal_readiness(actor):
        raise ValidationError("You are not authorized to decide fiscal-year readiness.")
    if decision not in (FiscalYearReadinessApproval.APPROVED, FiscalYearReadinessApproval.RETURNED):
        raise ValidationError("Unsupported readiness decision.")
    evidence_note = evidence_note.strip()
    if not evidence_note:
        raise ValidationError("Record the decision basis or evidence.")
    locked = FiscalYearReadinessApproval.objects.select_for_update().select_related("fiscal_year").get(pk=layer.pk)
    if locked.fiscal_year.status == FiscalYear.ACTIVE:
        raise ValidationError("Active fiscal-year readiness is immutable; approve a successor setup instead.")
    readiness = evaluate_fiscal_year_readiness(locked.fiscal_year)
    current = next(item for item in readiness["layers"] if item["record"].pk == locked.pk)
    if decision == FiscalYearReadinessApproval.APPROVED and not current["checks_passed"]:
        raise ValidationError(current["check_message"])
    locked.status = decision
    locked.evidence_note = evidence_note
    locked.decided_by_id = actor.pk
    locked.decided_by_label = actor_label(actor)
    locked.decided_at = timezone.now()
    locked.state_version += 1
    locked.full_clean()
    locked.save()
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id,
        department_label=locked.department_label,
        action=f"readiness_{decision}",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        reason=evidence_note,
        snapshot={
            "fiscal_year_id": str(locked.fiscal_year.public_id),
            "layer": locked.layer,
            "state_version": locked.state_version,
        },
    )
    return locked


def _release_payload(release):
    items = list(release.items.order_by("category", "code", "version").values(
        "public_id", "category", "code", "version", "label", "description",
        "configuration", "effective_from", "effective_to",
    ))
    serializable = {
        "id": release.pk,
        "code": release.code,
        "version": release.version,
        "fiscal_year": release.fiscal_year,
        "title": release.title,
        "effective_from": release.effective_from,
        "effective_to": release.effective_to,
        "items": items,
    }
    encoded = json.dumps(serializable, sort_keys=True, default=str).encode("utf-8")
    return serializable, hashlib.sha256(encoded).hexdigest()


def _audit_snapshot(instance):
    values = model_to_dict(instance)
    values["pk"] = instance.pk
    values["model"] = instance._meta.label_lower
    return json.loads(json.dumps(values, default=str))


def _affected_fiscal_years(instance):
    if isinstance(instance, FiscalYear):
        return [instance]
    direct = getattr(instance, "fiscal_year", None)
    if isinstance(direct, FiscalYear):
        return [direct]
    period_year = getattr(instance, "fiscal_year_record", None)
    if isinstance(period_year, FiscalYear):
        return [period_year]
    return list(FiscalYear.objects.filter(
        department_id=instance.department_id,
        status__in=(FiscalYear.DRAFT, FiscalYear.FOR_REVIEW, FiscalYear.APPROVED, FiscalYear.ACTIVE),
    ))


def _affected_readiness_layers(instance):
    if isinstance(instance, LedgerAccount):
        return {FiscalYearReadinessApproval.ACCOUNTING, FiscalYearReadinessApproval.FORMS}
    if isinstance(instance, FundingSource):
        return {
            FiscalYearReadinessApproval.BUDGET, FiscalYearReadinessApproval.ACCOUNTING,
            FiscalYearReadinessApproval.TREASURY, FiscalYearReadinessApproval.FORMS,
        }
    if isinstance(instance, ProgramActivityProject):
        return {
            FiscalYearReadinessApproval.BUDGET, FiscalYearReadinessApproval.ACCOUNTING,
            FiscalYearReadinessApproval.FORMS,
        }
    return {code for code, _label in FiscalYearReadinessApproval.LAYER_CHOICES}


def foundation_modification_blockers(fiscal_year):
    """Read the core transaction store without creating a cross-database relation."""
    from django.db.models import Q
    from vouchers.models import VoucherCase

    release_scope = Q(
        configuration_release__department_id=fiscal_year.department_id,
        configuration_release__fiscal_year=fiscal_year.year,
    )
    if fiscal_year.source_release_id:
        release_scope |= Q(configuration_release_id=fiscal_year.source_release_id)
    cases = VoucherCase.objects.filter(release_scope)
    numbered_vouchers = cases.filter(
        Q(disbursement_voucher__isnull=False)
        | Q(number_issues__document_type__in=("disbursement-voucher", "dv"))
    ).distinct()
    issued_checks = cases.filter(payment_instruments__issued_at__isnull=False).distinct()
    return {
        "voucher_count": numbered_vouchers.count(),
        "check_count": issued_checks.count(),
        "voucher_references": list(numbered_vouchers.values_list("reference_code", flat=True)[:5]),
        "check_references": list(issued_checks.values_list("reference_code", flat=True)[:5]),
    }


def begin_foundation_amendment(instance, actor, reason):
    if not can_manage_setup(actor):
        raise ValidationError("Only an authorized setup manager can amend fiscal foundations.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Explain why this governed setup record is being changed.")
    fiscal_years = _affected_fiscal_years(instance)
    for fiscal_year in fiscal_years:
        blockers = foundation_modification_blockers(fiscal_year)
        if blockers["voucher_count"] or blockers["check_count"]:
            references = sorted(set(blockers["voucher_references"] + blockers["check_references"]))
            suffix = f" Affected cases: {', '.join(references)}." if references else ""
            raise ValidationError(
                "The guided modification window is closed because a disbursement voucher or check has already "
                f"been issued for FY {fiscal_year.year}.{suffix} Use a governed successor, return, reversal, "
                "cancellation, or replacement workflow instead."
            )
    return {
        "reason": reason,
        "before": _audit_snapshot(instance),
        "fiscal_year_ids": [fiscal_year.pk for fiscal_year in fiscal_years],
        "layers": sorted(_affected_readiness_layers(instance)),
    }


@transaction.atomic(using=FINANCE_DB)
def finalize_foundation_amendment(instance, actor, context):
    fiscal_years = list(FiscalYear.objects.select_for_update().filter(pk__in=context["fiscal_year_ids"]))
    readiness_before = {}
    for fiscal_year in fiscal_years:
        blockers = foundation_modification_blockers(fiscal_year)
        if blockers["voucher_count"] or blockers["check_count"]:
            raise ValidationError(
                f"The modification was not saved because a voucher or check was issued for FY {fiscal_year.year} during review."
            )
        ensure_readiness_layers(fiscal_year)
        affected = list(fiscal_year.readiness_layers.filter(layer__in=context["layers"]))
        readiness_before[str(fiscal_year.public_id)] = [
            {"layer": layer.layer, "status": layer.status, "evidence_note": layer.evidence_note,
             "decided_by_id": layer.decided_by_id, "decided_by_label": layer.decided_by_label,
             "decided_at": layer.decided_at.isoformat() if layer.decided_at else None,
             "state_version": layer.state_version}
            for layer in affected
        ]
        for layer in affected:
            layer.status = FiscalYearReadinessApproval.PENDING
            layer.evidence_note = ""
            layer.decided_by_id = None
            layer.decided_by_label = ""
            layer.decided_at = None
            layer.state_version += 1
            layer.save()
        if fiscal_year.status != FiscalYear.DRAFT:
            fiscal_year.status = FiscalYear.DRAFT
            fiscal_year.submitted_by_id = None
            fiscal_year.submitted_by_label = ""
            fiscal_year.submitted_at = None
            fiscal_year.approved_by_id = None
            fiscal_year.approved_by_label = ""
            fiscal_year.approved_at = None
            fiscal_year.state_version += 1
            fiscal_year.save(update_fields=(
                "status", "submitted_by_id", "submitted_by_label", "submitted_at",
                "approved_by_id", "approved_by_label", "approved_at", "state_version", "updated_at",
            ))
    if isinstance(instance, FiscalYear):
        instance.refresh_from_db()
    AccountingAuditEvent.objects.create(
        department_id=instance.department_id,
        department_label=instance.department_label,
        action="foundation_amended",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        reason=context["reason"],
        snapshot={
            "before": context["before"],
            "after": _audit_snapshot(instance),
            "fiscal_year_ids": [str(fiscal_year.public_id) for fiscal_year in fiscal_years],
            "reopened_layers": context["layers"],
            "prior_readiness": readiness_before,
            "modification_boundary": "no_disbursement_voucher_or_check_issued",
        },
    )
    return instance


@transaction.atomic(using=FINANCE_DB)
def adopt_configuration_release(release, actor, *, change_reason=""):
    """Copy an approved core setup release into the isolated Finance store using snapshots only."""
    if not can_manage_setup(actor):
        raise ValidationError("Only an authorized setup manager can adopt a configuration release.")
    if release.status not in {"approved", "scheduled", "active", "superseded"}:
        raise ValidationError("Only an approved configuration release can be adopted.")
    payload, checksum = _release_payload(release)
    starts_on = date(release.fiscal_year, 1, 1)
    ends_on = date(release.fiscal_year, 12, 31)
    fiscal_year, created = FiscalYear.objects.get_or_create(
        department_id=release.department_id,
        year=release.fiscal_year,
        defaults={
            "department_label": release.department.name,
            "label": f"FY {release.fiscal_year}",
            "starts_on": starts_on,
            "ends_on": ends_on,
            "business_date": max(starts_on, min(release.effective_from, ends_on)),
            "created_by_id": actor.pk,
            "created_by_label": actor_label(actor),
        },
    )
    amendment_context = None
    if (
        not created
        and fiscal_year.status in (FiscalYear.APPROVED, FiscalYear.ACTIVE, FiscalYear.CLOSED)
        and fiscal_year.source_checksum != checksum
    ):
        amendment_context = begin_foundation_amendment(fiscal_year, actor, change_reason)
        fiscal_year._governed_amendment = True
    fiscal_year.source_release_id = release.pk
    fiscal_year.source_release_code = release.code
    fiscal_year.source_release_version = release.version
    fiscal_year.source_checksum = checksum
    fiscal_year.full_clean()
    fiscal_year.save()
    counts = {"funds": 0, "centers": 0, "accounts": 0, "funding_sources": 0, "classifications": 0, "skipped": []}
    for item in payload["items"]:
        config = item["configuration"] or {}
        common = {
            "department_id": release.department_id,
            "department_label": release.department.name,
        }
        if item["category"] == "fund":
            _record, was_created = Fund.objects.get_or_create(
                department_id=release.department_id, code=item["code"],
                defaults={**common, "name": item["label"], "description": item["description"],
                          "category": str(config.get("category", "")), "effective_from": item["effective_from"],
                          "effective_to": item["effective_to"]},
            )
            counts["funds"] += int(was_created)
        elif item["category"] == "responsibility_center":
            office_id = config.get("office_id")
            if office_id is not None and not isinstance(office_id, int):
                counts["skipped"].append(f"center:{item['code']}:invalid office_id")
                continue
            _record, was_created = ResponsibilityCenter.objects.get_or_create(
                department_id=release.department_id, code=item["code"],
                defaults={**common, "name": item["label"], "description": item["description"],
                          "office_id": office_id, "office_code": str(config.get("office_code", "")),
                          "effective_from": item["effective_from"], "effective_to": item["effective_to"]},
            )
            counts["centers"] += int(was_created)
        elif item["category"] == "account_classification":
            account_type = config.get("account_type")
            normal_balance = config.get("normal_balance")
            if account_type not in dict(LedgerAccount.TYPE_CHOICES) or normal_balance not in dict(LedgerAccount.NORMAL_CHOICES):
                counts["skipped"].append(f"account:{item['code']}:missing account_type/normal_balance")
                continue
            _record, was_created = LedgerAccount.objects.get_or_create(
                department_id=release.department_id, code=item["code"],
                defaults={**common, "title": item["label"], "account_type": account_type,
                          "normal_balance": normal_balance, "government_account_code": str(config.get("government_account_code", "")),
                          "subsidiary_reference_type": str(config.get("subsidiary_reference_type", "")),
                          "effective_from": item["effective_from"], "effective_to": item["effective_to"]},
            )
            counts["accounts"] += int(was_created)
        elif item["category"] == "funding_source":
            kind = config.get("kind", "local")
            if kind not in dict(FundingSource.KIND_CHOICES):
                counts["skipped"].append(f"funding_source:{item['code']}:invalid kind")
                continue
            fund = Fund.objects.filter(department_id=release.department_id, code=config.get("fund_code", "")).first()
            _record, was_created = FundingSource.objects.get_or_create(
                department_id=release.department_id, fiscal_year=fiscal_year, code=item["code"],
                defaults={**common, "fund": fund, "name": item["label"], "kind": kind,
                          "authority_reference": str(config.get("authority_reference", "")),
                          "effective_from": item["effective_from"], "effective_to": item["effective_to"]},
            )
            counts["funding_sources"] += int(was_created)
        elif item["category"] in {"ppa_mfo", "project_activity"}:
            funding_source = FundingSource.objects.filter(
                department_id=release.department_id, fiscal_year=fiscal_year, code=config.get("funding_source_code", ""),
            ).first()
            center = ResponsibilityCenter.objects.filter(
                department_id=release.department_id, code=config.get("responsibility_center_code", ""),
            ).first()
            kind = config.get("kind", "ppa" if item["category"] == "ppa_mfo" else "activity")
            if kind not in dict(ProgramActivityProject.KIND_CHOICES):
                counts["skipped"].append(f"classification:{item['code']}:invalid kind")
                continue
            _record, was_created = ProgramActivityProject.objects.get_or_create(
                department_id=release.department_id, fiscal_year=fiscal_year, code=item["code"],
                defaults={**common, "name": item["label"], "kind": kind, "funding_source": funding_source,
                          "responsibility_center": center, "authority_reference": str(config.get("authority_reference", "")),
                          "effective_from": item["effective_from"], "effective_to": item["effective_to"]},
            )
            counts["classifications"] += int(was_created)
    for item in payload["items"]:
        if item["category"] not in {"ppa_mfo", "project_activity"}:
            continue
        parent_code = (item["configuration"] or {}).get("parent_code")
        if not parent_code:
            continue
        record = ProgramActivityProject.objects.filter(
            department_id=release.department_id, fiscal_year=fiscal_year, code=item["code"],
        ).first()
        parent = ProgramActivityProject.objects.filter(
            department_id=release.department_id, fiscal_year=fiscal_year, code=parent_code,
        ).first()
        if not record or not parent:
            counts["skipped"].append(f"classification:{item['code']}:missing parent {parent_code}")
            continue
        record.parent = parent
        record.full_clean()
        record.save(update_fields=("parent",))
    for period in AccountingPeriod.objects.filter(
        department_id=release.department_id, fiscal_year=release.fiscal_year, fiscal_year_record__isnull=True,
    ):
        period.fiscal_year_record = fiscal_year
        period.full_clean()
        period.save(update_fields=("fiscal_year_record",))
    ensure_readiness_layers(fiscal_year)
    AccountingAuditEvent.objects.create(
        department_id=release.department_id,
        department_label=release.department.name,
        action="configuration_release_adopted",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={"release_id": release.pk, "release_code": release.code, "release_version": release.version,
                  "checksum": checksum, "result": counts},
    )
    if amendment_context is not None:
        finalize_foundation_amendment(fiscal_year, actor, amendment_context)
    return fiscal_year, counts


def record_event(entry, action, actor, reason="", snapshot=None):
    return AccountingAuditEvent.objects.create(
        department_id=entry.department_id,
        department_label=entry.department_label,
        entry=entry,
        action=action,
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        reason=reason,
        snapshot=snapshot or {},
    )


def validate_entry_for_submission(entry):
    entry.full_clean()
    lines = list(entry.lines.select_related("account", "responsibility_center"))
    if len(lines) < 2:
        raise ValidationError("Add at least two journal lines before submitting.")
    for line in lines:
        line.full_clean()
    debit = sum((line.debit for line in lines), Decimal("0.00"))
    credit = sum((line.credit for line in lines), Decimal("0.00"))
    if debit <= 0 or debit != credit:
        raise ValidationError(f"The entry must balance before submission. Debits: {debit:,.2f}; credits: {credit:,.2f}.")
    if entry.period.status != AccountingPeriod.OPEN:
        raise ValidationError("The selected accounting period is closed.")
    return debit, credit


@transaction.atomic(using=FINANCE_DB)
def submit_entry(entry, actor):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.DRAFT:
        raise ValidationError("Only a draft journal can be submitted.")
    debit, credit = validate_entry_for_submission(locked)
    locked.status = JournalEntry.SUBMITTED
    locked.submitted_by_id = actor.pk
    locked.submitted_by_label = actor_label(actor)
    locked.submitted_at = timezone.now()
    locked.save(update_fields=("status", "submitted_by_id", "submitted_by_label", "submitted_at", "updated_at"))
    record_event(locked, "submitted", actor, snapshot={"debit": str(debit), "credit": str(credit)})
    return locked


@transaction.atomic(using=FINANCE_DB)
def post_entry(entry, actor):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.SUBMITTED:
        raise ValidationError("Only a submitted journal can be posted.")
    workflow_exemption = None
    if locked.created_by_id == actor.pk:
        from finance.exemptions import workflow_exemption_for, workflow_exemption_snapshot
        from finance.models import FinanceWorkflowExemption

        exemption = workflow_exemption_for(
            actor=actor,
            control_code=FinanceWorkflowExemption.JOURNAL_PREPARER_SELF_POSTING,
            department_id=locked.department_id,
        )
        if exemption is None:
            raise ValidationError(
                "Maker-checker control: the preparer cannot post the same journal entry unless an active "
                "administrator-authorized workflow exemption applies."
            )
        workflow_exemption = workflow_exemption_snapshot(exemption)
    debit, credit = validate_entry_for_submission(locked)
    locked.status = JournalEntry.POSTED
    locked.posted_by_id = actor.pk
    locked.posted_by_label = actor_label(actor)
    locked.posted_at = timezone.now()
    locked.save(update_fields=("status", "posted_by_id", "posted_by_label", "posted_at", "updated_at"))
    snapshot = {"debit": str(debit), "credit": str(credit)}
    if workflow_exemption:
        snapshot["workflow_exemption"] = workflow_exemption
    record_event(locked, "posted", actor, snapshot=snapshot)
    return locked


@transaction.atomic(using=FINANCE_DB)
def return_entry(entry, actor, reason):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.SUBMITTED:
        raise ValidationError("Only a submitted journal can be returned.")
    if not reason.strip():
        raise ValidationError("Explain what the preparer needs to correct.")
    locked.status = JournalEntry.DRAFT
    locked.submitted_by_id = None
    locked.submitted_by_label = ""
    locked.submitted_at = None
    locked.save(update_fields=("status", "submitted_by_id", "submitted_by_label", "submitted_at", "updated_at"))
    record_event(locked, "returned", actor, reason=reason.strip())
    return locked


@transaction.atomic(using=FINANCE_DB)
def discard_draft(entry, actor, reason=""):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if locked.status != JournalEntry.DRAFT:
        raise ValidationError("Only a draft journal can be discarded.")
    locked.status = JournalEntry.VOIDED
    locked.save(update_fields=("status", "updated_at"))
    record_event(locked, "draft_discarded", actor, reason=reason.strip())
    return locked


@transaction.atomic(using=FINANCE_DB)
def create_reversal(entry, actor, *, reference, entry_date, period, reason):
    """Prepare, but do not post, an exact reversing journal with immutable lineage."""
    locked = JournalEntry.objects.select_for_update().select_related("fund").get(pk=entry.pk)
    if locked.status != JournalEntry.POSTED:
        raise ValidationError("Only a posted journal can be reversed.")
    active_reversals = JournalEntry.objects.filter(reversal_of=locked).exclude(status=JournalEntry.VOIDED)
    if active_reversals.exists():
        raise ValidationError("A reversing journal has already been prepared for this entry.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Explain why this reversal is required.")
    if period.department_id != locked.department_id or period.status != AccountingPeriod.OPEN:
        raise ValidationError("Choose an open accounting period for the same department ledger.")
    if not (period.starts_on <= entry_date <= period.ends_on):
        raise ValidationError("The reversal date must fall inside the selected accounting period.")

    attempt_number = JournalEntry.objects.filter(reversal_of=locked).count() + 1
    reversal = JournalEntry(
        department_id=locked.department_id,
        department_label=locked.department_label,
        reference=reference.strip(),
        entry_date=entry_date,
        period=period,
        fund=locked.fund,
        source_type="reversal",
        source_reference=f"{locked.public_id}:{attempt_number}",
        source_snapshot={
            "original_entry": str(locked.public_id),
            "original_reference": locked.reference,
            "original_posted_at": locked.posted_at.isoformat() if locked.posted_at else None,
        },
        reversal_of=locked,
        reversal_reason=reason,
        description=f"Reversal of {locked.reference}: {reason}",
        created_by_id=actor.pk,
        created_by_label=actor_label(actor),
    )
    reversal.full_clean()
    reversal.save()
    for line in locked.lines.select_related("account", "responsibility_center").order_by("sequence", "pk"):
        reversed_line = JournalLine(
            entry=reversal,
            sequence=line.sequence,
            account=line.account,
            responsibility_center=line.responsibility_center,
            debit=line.credit,
            credit=line.debit,
            memo=f"Reversal: {line.memo}"[:255],
        )
        reversed_line.full_clean()
        reversed_line.save()
    record_event(
        locked, "reversal_prepared", actor, reason=reason,
        snapshot={"reversal_entry": str(reversal.public_id), "reversal_reference": reversal.reference},
    )
    record_event(
        reversal, "prepared_from_reversal", actor, reason=reason,
        snapshot={"original_entry": str(locked.public_id), "original_reference": locked.reference},
    )
    return reversal


@transaction.atomic(using=FINANCE_DB)
def close_period(period, actor):
    locked = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if locked.status != AccountingPeriod.OPEN:
        raise ValidationError("This accounting period is already closed.")
    unposted = locked.journal_entries.exclude(status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).count()
    if unposted:
        raise ValidationError(f"Close or discard {unposted} unposted journal entry/entries before closing this period.")
    locked.status = AccountingPeriod.CLOSED
    locked.closed_by_id = actor.pk
    locked.closed_by_label = actor_label(actor)
    locked.closed_at = timezone.now()
    locked.save(update_fields=("status", "closed_by_id", "closed_by_label", "closed_at"))
    AccountingAuditEvent.objects.create(
        department_id=locked.department_id,
        department_label=locked.department_label,
        action="period_closed",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={"fiscal_year": locked.fiscal_year, "period_number": locked.period_number},
    )
    return locked
