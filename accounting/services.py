import hashlib
import json
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.dateparse import parse_date

from .access import (
    can_approve_bank_reconciliation, can_approve_fiscal_readiness, can_approve_opening_balances, can_manage_setup,
    can_post_journals, can_post_opening_balances, can_prepare_journals,
    can_prepare_opening_balances, can_reconcile_controls, can_prepare_bank_reconciliation,
    department_for_user,
)
from .models import (
    AccountingAuditEvent, AccountingPeriod, ControlAccountReconciliation, FiscalYear,
    FiscalYearReadinessApproval, Fund, FundingSource, JournalEntry, JournalLine,
    JournalSubsidiaryLine, LedgerAccount,
    BankOutstandingItem, BankReconciliationEvent, BankStatementBatch, BankStatementMatch, BankStatementRow,
    OpeningBalanceBatch, OpeningBalanceEvent, OpeningBalancePosting, OpeningBalanceRow,
    PostingMapping, ProgramActivityProject, ResponsibilityCenter,
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
            ).exists()
            and fiscal_year.opening_balance_batches.filter(status=OpeningBalanceBatch.RECONCILED).exists(),
            "An active fund/posting account and an approved, posted, zero-difference opening batch exist for Accounting.",
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


def foundation_modification_blockers_for_scope(*, department_id, fiscal_year, source_release_id=None):
    """Read one exact office/year scope without creating a cross-database relation."""
    from django.db.models import Q
    from vouchers.models import VoucherCase

    release_scope = Q(
        configuration_release__department_id=department_id,
        configuration_release__fiscal_year=fiscal_year,
    )
    if source_release_id:
        release_scope |= Q(configuration_release_id=source_release_id)
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


def foundation_modification_blockers(fiscal_year):
    """Read the core transaction store without creating a cross-database relation."""

    return foundation_modification_blockers_for_scope(
        department_id=fiscal_year.department_id,
        fiscal_year=fiscal_year.year,
        source_release_id=fiscal_year.source_release_id,
    )


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
        "issuance_scopes": [
            {"department_id": fiscal_year.department_id, "fiscal_year": fiscal_year.year}
            for fiscal_year in fiscal_years
        ],
        "layers": sorted(_affected_readiness_layers(instance)),
    }


def extend_foundation_amendment_context(context, instance):
    """Add any proposed fiscal-year scope introduced by a validated edit form."""

    proposed_years = _affected_fiscal_years(instance)
    for fiscal_year in proposed_years:
        blockers = foundation_modification_blockers(fiscal_year)
        if blockers["voucher_count"] or blockers["check_count"]:
            references = sorted(set(blockers["voucher_references"] + blockers["check_references"]))
            suffix = f" Affected cases: {', '.join(references)}." if references else ""
            raise ValidationError(
                "The guided modification window is closed because a disbursement voucher or check has already "
                f"been issued for FY {fiscal_year.year}.{suffix} Use a governed successor, return, reversal, "
                "cancellation, or replacement workflow instead."
            )
    context["fiscal_year_ids"] = sorted({
        *context["fiscal_year_ids"],
        *(fiscal_year.pk for fiscal_year in proposed_years),
    })
    scopes = {
        (scope["department_id"], scope["fiscal_year"])
        for scope in context["issuance_scopes"]
    }
    scopes.update((fiscal_year.department_id, fiscal_year.year) for fiscal_year in proposed_years)
    context["issuance_scopes"] = [
        {"department_id": department_id, "fiscal_year": fiscal_year}
        for department_id, fiscal_year in sorted(scopes)
    ]
    context["layers"] = sorted({
        *context["layers"],
        *_affected_readiness_layers(instance),
    })
    return context


def lock_foundation_amendment_boundaries(context):
    """Hold transaction-store issuance locks across the Finance-store amendment."""

    from vouchers.issuance_boundaries import lock_foundation_issuance_boundaries

    return lock_foundation_issuance_boundaries(context["issuance_scopes"])


@transaction.atomic(using=FINANCE_DB)
def finalize_foundation_amendment(instance, actor, context):
    fiscal_years = list(FiscalYear.objects.select_for_update().filter(pk__in=context["fiscal_year_ids"]))
    readiness_before = {}
    for scope in context["issuance_scopes"]:
        blockers = foundation_modification_blockers_for_scope(
            department_id=scope["department_id"],
            fiscal_year=scope["fiscal_year"],
        )
        if blockers["voucher_count"] or blockers["check_count"]:
            raise ValidationError(
                "The modification was not saved because a voucher or check was issued for "
                f"FY {scope['fiscal_year']} during review."
            )
    for fiscal_year in fiscal_years:
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
            "issuance_boundary_scopes": context["issuance_scopes"],
        },
    )
    return instance


@transaction.atomic(using="default")
@transaction.atomic(using=FINANCE_DB)
def adopt_configuration_release(release, actor, *, change_reason=""):
    """Copy an approved core setup release into the isolated Finance store using snapshots only."""
    if not can_manage_setup(actor):
        raise ValidationError("Only an authorized setup manager can adopt a configuration release.")
    if release.status not in {"approved", "scheduled", "active", "superseded"}:
        raise ValidationError("Only an approved configuration release can be adopted.")
    from vouchers.issuance_boundaries import lock_foundation_issuance_boundary

    lock_foundation_issuance_boundary(
        department_id=release.department_id,
        fiscal_year=release.fiscal_year,
    )
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


OPENING_COLUMNS = (
    "fund_code", "account_code", "responsibility_center_code", "debit", "credit",
    "subsidiary_reference", "memo",
)
OPENING_REQUIRED_COLUMNS = {"fund_code", "account_code", "debit", "credit"}
OPENING_MAX_BYTES = 5 * 1024 * 1024


def record_opening_event(batch, action, actor, *, reason="", snapshot=None):
    return OpeningBalanceEvent.objects.create(
        department_id=batch.department_id,
        department_label=batch.department_label,
        batch=batch,
        action=action,
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        reason=reason.strip(),
        snapshot=snapshot or {},
    )


def _opening_money(raw_value):
    raw_value = str(raw_value or "").replace(",", "").strip()
    if not raw_value:
        return Decimal("0.00")
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValidationError(f"'{raw_value}' is not a valid amount.") from exc
    if not value.is_finite() or value < 0 or value.as_tuple().exponent < -2:
        raise ValidationError(f"'{raw_value}' must be a non-negative amount with at most two decimal places.")
    return value.quantize(Decimal("0.01"))


@transaction.atomic(using=FINANCE_DB)
def stage_opening_csv(batch, actor, uploaded_file):
    if not can_prepare_opening_balances(actor):
        raise ValidationError("You are not authorized to stage opening balances.")
    locked = OpeningBalanceBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status not in (OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED):
        raise ValidationError("Return the opening batch to staging before replacing its source rows.")
    if locked.is_zero_balance_declaration:
        raise ValidationError("A zero-balance declaration does not accept a source row file.")
    content = uploaded_file.read(OPENING_MAX_BYTES + 1)
    if len(content) > OPENING_MAX_BYTES:
        raise ValidationError("The opening CSV exceeds the 5 MB staging limit.")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Use a UTF-8 CSV file.") from exc
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    fieldnames = {str(name or "").strip() for name in (reader.fieldnames or [])}
    missing = sorted(OPENING_REQUIRED_COLUMNS - fieldnames)
    if missing:
        raise ValidationError(f"Missing required CSV column(s): {', '.join(missing)}.")
    staged = []
    for source_row_number, source in enumerate(reader, start=2):
        normalized = {key: str(source.get(key, "") or "").strip() for key in OPENING_COLUMNS}
        if not any(normalized.values()):
            continue
        staged.append(OpeningBalanceRow(
            batch=locked,
            row_number=source_row_number,
            raw_fund_code=normalized["fund_code"],
            raw_account_code=normalized["account_code"],
            raw_responsibility_center_code=normalized["responsibility_center_code"],
            raw_debit=normalized["debit"],
            raw_credit=normalized["credit"],
            subsidiary_reference=normalized["subsidiary_reference"],
            memo=normalized["memo"],
        ))
    prior = {"row_count": locked.rows.count(), "source_checksum": locked.source_checksum}
    locked.rows.all().delete()
    OpeningBalanceRow.objects.bulk_create(staged)
    locked.source_filename = str(getattr(uploaded_file, "name", "opening-balances.csv"))[:255]
    locked.source_checksum = hashlib.sha256(content).hexdigest()
    locked.status = OpeningBalanceBatch.DRAFT
    locked.validation_summary = {"imported_row_count": len(staged)}
    locked.submitted_by_id = None
    locked.submitted_by_label = ""
    locked.submitted_at = None
    locked.approved_by_id = None
    locked.approved_by_label = ""
    locked.approved_at = None
    locked.state_version += 1
    locked.full_clean()
    locked.save()
    record_opening_event(
        locked,
        "source_staged",
        actor,
        snapshot={
            "before": prior,
            "source_filename": locked.source_filename,
            "source_checksum": locked.source_checksum,
            "imported_row_count": len(staged),
            "schema_version": locked.import_schema_version,
        },
    )
    return validate_opening_batch(locked, actor)


@transaction.atomic(using=FINANCE_DB)
def validate_opening_batch(batch, actor):
    if not can_prepare_opening_balances(actor):
        raise ValidationError("You are not authorized to validate opening balances.")
    locked = OpeningBalanceBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status not in (
        OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED, OpeningBalanceBatch.VALIDATED,
    ):
        raise ValidationError("Only staged or returned opening balances can be validated.")
    rows = list(locked.rows.order_by("row_number", "pk"))
    funds = {item.code: item for item in Fund.objects.filter(department_id=locked.department_id, is_active=True)}
    accounts = {
        item.code: item for item in LedgerAccount.objects.filter(
            department_id=locked.department_id, is_active=True, allow_posting=True,
        )
    }
    centers = {
        item.code: item for item in ResponsibilityCenter.objects.filter(
            department_id=locked.department_id, is_active=True,
        )
    }
    valid_count = 0
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    fund_totals = {}
    for row in rows:
        errors = []
        fund = funds.get(row.raw_fund_code)
        account = accounts.get(row.raw_account_code)
        center = centers.get(row.raw_responsibility_center_code) if row.raw_responsibility_center_code else None
        if fund is None:
            errors.append(f"Unknown or inactive fund code: {row.raw_fund_code or '(blank)' }.")
        if account is None:
            errors.append(f"Unknown, inactive, or non-posting account code: {row.raw_account_code or '(blank)'}.")
        if row.raw_responsibility_center_code and center is None:
            errors.append(f"Unknown or inactive responsibility-center code: {row.raw_responsibility_center_code}.")
        try:
            debit = _opening_money(row.raw_debit)
        except ValidationError as exc:
            debit = Decimal("0.00")
            errors.extend(exc.messages)
        try:
            credit = _opening_money(row.raw_credit)
        except ValidationError as exc:
            credit = Decimal("0.00")
            errors.extend(exc.messages)
        if (debit > 0) == (credit > 0):
            errors.append("Enter a positive debit or credit, not both.")
        row.fund = fund
        row.account = account
        row.responsibility_center = center
        row.debit = debit
        row.credit = credit
        row.validation_errors = errors
        row.validation_status = OpeningBalanceRow.ERROR if errors else OpeningBalanceRow.VALID
        row._validation_update = True
        row.full_clean()
        row.save()
        if not errors:
            valid_count += 1
            debit_total += debit
            credit_total += credit
            totals = fund_totals.setdefault(fund.code, {"debit": Decimal("0.00"), "credit": Decimal("0.00"), "rows": 0})
            totals["debit"] += debit
            totals["credit"] += credit
            totals["rows"] += 1
    errors = []
    if locked.is_zero_balance_declaration:
        if rows:
            errors.append("A zero-balance declaration cannot contain staged rows.")
    else:
        if not locked.source_checksum:
            errors.append("Stage the source CSV before validation.")
        if len(rows) != locked.expected_row_count:
            errors.append(f"Row-count difference: staged {len(rows)}, declared {locked.expected_row_count}.")
        if debit_total != locked.expected_debit:
            errors.append(f"Debit control difference: staged {debit_total:.2f}, declared {locked.expected_debit:.2f}.")
        if credit_total != locked.expected_credit:
            errors.append(f"Credit control difference: staged {credit_total:.2f}, declared {locked.expected_credit:.2f}.")
        if debit_total != credit_total:
            errors.append(f"Staged debits {debit_total:.2f} do not equal credits {credit_total:.2f}.")
        for fund_code, totals in sorted(fund_totals.items()):
            if totals["debit"] != totals["credit"]:
                errors.append(
                    f"Fund {fund_code} is not balanced: debit {totals['debit']:.2f}, credit {totals['credit']:.2f}."
                )
    error_count = len(rows) - valid_count
    serialized_funds = {
        code: {"debit": str(values["debit"]), "credit": str(values["credit"]), "rows": values["rows"]}
        for code, values in fund_totals.items()
    }
    locked.status = OpeningBalanceBatch.VALIDATED if not errors and not error_count else OpeningBalanceBatch.DRAFT
    locked.validation_summary = {
        "valid": locked.status == OpeningBalanceBatch.VALIDATED,
        "row_count": len(rows),
        "valid_row_count": valid_count,
        "error_row_count": error_count,
        "debit": str(debit_total),
        "credit": str(credit_total),
        "batch_errors": errors,
        "fund_totals": serialized_funds,
        "source_checksum": locked.source_checksum,
    }
    locked.state_version += 1
    locked.full_clean()
    locked.save(update_fields=("status", "validation_summary", "state_version", "updated_at"))
    record_opening_event(
        locked,
        "validated" if locked.status == OpeningBalanceBatch.VALIDATED else "validation_failed",
        actor,
        snapshot=locked.validation_summary,
    )
    return locked


@transaction.atomic(using=FINANCE_DB)
def correct_opening_row(row, actor, *, values, reason):
    if not can_prepare_opening_balances(actor):
        raise ValidationError("You are not authorized to correct staged opening rows.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Explain the staged-row correction and cite its source evidence.")
    locked = OpeningBalanceRow.objects.select_for_update().select_related("batch").get(pk=row.pk)
    if locked.batch.status not in (OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED):
        raise ValidationError("Only draft or returned rows can be corrected.")
    before = _audit_snapshot(locked)
    for field in (
        "raw_fund_code", "raw_account_code", "raw_responsibility_center_code", "raw_debit", "raw_credit",
        "subsidiary_reference", "memo",
    ):
        setattr(locked, field, str(values.get(field, "") or "").strip())
    locked.validation_status = OpeningBalanceRow.PENDING
    locked.validation_errors = []
    locked.fund = None
    locked.account = None
    locked.responsibility_center = None
    locked.debit = Decimal("0.00")
    locked.credit = Decimal("0.00")
    locked.correction_version += 1
    locked.save()
    batch = locked.batch
    batch.status = OpeningBalanceBatch.DRAFT
    batch.validation_summary = {}
    batch.submitted_by_id = None
    batch.submitted_by_label = ""
    batch.submitted_at = None
    batch.approved_by_id = None
    batch.approved_by_label = ""
    batch.approved_at = None
    batch.state_version += 1
    batch.save()
    record_opening_event(
        batch,
        "row_corrected",
        actor,
        reason=reason,
        snapshot={"row_number": locked.row_number, "before": before, "after": _audit_snapshot(locked)},
    )
    return locked


@transaction.atomic(using=FINANCE_DB)
def correct_opening_batch(batch, actor, *, values, reason):
    if not can_prepare_opening_balances(actor):
        raise ValidationError("You are not authorized to correct opening controls.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Explain the control-total or source-reference correction.")
    locked = OpeningBalanceBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status not in (OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED):
        raise ValidationError("Only a draft or returned opening batch can be corrected.")
    if values.get("is_zero_balance_declaration") and locked.rows.exists():
        raise ValidationError("A staged row schedule cannot be converted in place to a zero-balance declaration. Create a new declaration batch.")
    before = _audit_snapshot(locked)
    for field in (
        "fiscal_year", "period", "title", "source_reference", "expected_row_count",
        "expected_debit", "expected_credit", "is_zero_balance_declaration",
    ):
        setattr(locked, field, values[field])
    locked.status = OpeningBalanceBatch.DRAFT
    locked.validation_summary = {}
    locked.submitted_by_id = None
    locked.submitted_by_label = ""
    locked.submitted_at = None
    locked.approved_by_id = None
    locked.approved_by_label = ""
    locked.approved_at = None
    locked.state_version += 1
    locked.full_clean()
    locked.save()
    record_opening_event(
        locked,
        "controls_corrected",
        actor,
        reason=reason,
        snapshot={"before": before, "after": _audit_snapshot(locked)},
    )
    return locked


@transaction.atomic(using=FINANCE_DB)
def submit_opening_batch(batch, actor):
    if not can_prepare_opening_balances(actor):
        raise ValidationError("You are not authorized to submit opening balances.")
    locked = OpeningBalanceBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status != OpeningBalanceBatch.VALIDATED or not locked.validation_summary.get("valid"):
        raise ValidationError("Resolve every row and control-total difference, then validate again before submission.")
    locked.status = OpeningBalanceBatch.FOR_REVIEW
    locked.submitted_by_id = actor.pk
    locked.submitted_by_label = actor_label(actor)
    locked.submitted_at = timezone.now()
    locked.state_version += 1
    locked.save()
    record_opening_event(locked, "submitted", actor, snapshot=locked.validation_summary)
    return locked


@transaction.atomic(using=FINANCE_DB)
def decide_opening_batch(batch, actor, *, decision, evidence_note):
    if not can_approve_opening_balances(actor):
        raise ValidationError("You are not authorized to approve opening balances.")
    note = evidence_note.strip()
    if not note:
        raise ValidationError("Record the approval or return basis and supporting evidence.")
    locked = OpeningBalanceBatch.objects.select_for_update().get(pk=batch.pk)
    if decision == OpeningBalanceBatch.APPROVED and locked.status != OpeningBalanceBatch.FOR_REVIEW:
        raise ValidationError("Only an opening batch under review can be approved.")
    if decision == OpeningBalanceBatch.RETURNED and locked.status not in (
        OpeningBalanceBatch.FOR_REVIEW, OpeningBalanceBatch.APPROVED,
    ):
        raise ValidationError("Only an opening batch under review or approved-but-unposted can be returned.")
    if actor.pk in {locked.created_by_id, locked.submitted_by_id}:
        raise ValidationError("The opening-balance approver must be different from its preparer and submitter.")
    if decision == OpeningBalanceBatch.APPROVED:
        locked.status = OpeningBalanceBatch.APPROVED
        locked.approved_by_id = actor.pk
        locked.approved_by_label = actor_label(actor)
        locked.approved_at = timezone.now()
    elif decision == OpeningBalanceBatch.RETURNED:
        locked.status = OpeningBalanceBatch.RETURNED
        locked.approved_by_id = None
        locked.approved_by_label = ""
        locked.approved_at = None
    else:
        raise ValidationError("Unsupported opening-balance decision.")
    locked.state_version += 1
    locked.save()
    record_opening_event(locked, decision, actor, reason=note, snapshot=locked.validation_summary)
    return locked


@transaction.atomic(using=FINANCE_DB)
def post_opening_batch(batch, actor):
    if not can_post_opening_balances(actor):
        raise ValidationError("You are not authorized to post opening balances.")
    locked = OpeningBalanceBatch.objects.select_for_update().select_related("fiscal_year", "period").get(pk=batch.pk)
    if locked.status != OpeningBalanceBatch.APPROVED:
        raise ValidationError("Only an independently approved opening batch can be posted.")
    if actor.pk in {locked.created_by_id, locked.submitted_by_id}:
        raise ValidationError("The opening-balance preparer cannot post the same batch.")
    if locked.period.status != AccountingPeriod.OPEN:
        raise ValidationError("The selected opening accounting period is closed.")
    if locked.fiscal_year.status not in (FiscalYear.APPROVED, FiscalYear.ACTIVE):
        raise ValidationError("Approve the fiscal-year definition before posting opening balances.")
    grouped = {}
    for row in locked.rows.select_related("fund", "account", "responsibility_center").order_by("row_number"):
        if row.validation_status != OpeningBalanceRow.VALID or not row.fund_id or not row.account_id:
            raise ValidationError("The approved batch contains a row that is no longer valid.")
        grouped.setdefault(row.fund, []).append(row)
    postings = []
    for fund, rows in grouped.items():
        reference = f"OPEN-{locked.fiscal_year.year}-{locked.pk}-{fund.code}"[:60]
        entry = JournalEntry.objects.create(
            department_id=locked.department_id,
            department_label=locked.department_label,
            reference=reference,
            entry_date=locked.period.starts_on,
            period=locked.period,
            fund=fund,
            source_type="opening",
            source_reference=f"opening:{locked.public_id}:{fund.public_id.hex[:12]}",
            source_snapshot={
                "opening_batch": str(locked.public_id),
                "source_reference": locked.source_reference,
                "source_checksum": locked.source_checksum,
                "expected_debit": str(locked.expected_debit),
                "expected_credit": str(locked.expected_credit),
                "fund_code": fund.code,
            },
            description=f"Opening balances: {locked.title} ({fund.code})",
            created_by_id=locked.submitted_by_id or locked.created_by_id,
            created_by_label=locked.submitted_by_label or locked.created_by_label,
        )
        for sequence, row in enumerate(rows, start=1):
            memo = row.memo
            if row.subsidiary_reference:
                memo = f"{memo} · Subsidiary: {row.subsidiary_reference}" if memo else f"Subsidiary: {row.subsidiary_reference}"
            line = JournalLine(
                entry=entry,
                sequence=sequence,
                account=row.account,
                responsibility_center=row.responsibility_center,
                debit=row.debit,
                credit=row.credit,
                memo=memo[:255],
            )
            line.full_clean()
            line.save()
        debit, credit = validate_entry_for_submission(entry)
        entry.status = JournalEntry.SUBMITTED
        entry.submitted_by_id = locked.submitted_by_id
        entry.submitted_by_label = locked.submitted_by_label
        entry.submitted_at = locked.submitted_at
        entry.save(update_fields=("status", "submitted_by_id", "submitted_by_label", "submitted_at", "updated_at"))
        AccountingAuditEvent.objects.create(
            department_id=entry.department_id,
            department_label=entry.department_label,
            entry=entry,
            action="opening_submitted",
            actor_id=locked.submitted_by_id,
            actor_label=locked.submitted_by_label,
            snapshot={"opening_batch": str(locked.public_id), "debit": str(debit), "credit": str(credit)},
        )
        post_entry(entry, actor)
        posting = OpeningBalancePosting.objects.create(
            batch=locked, fund=fund, entry=entry, debit=debit, credit=credit, row_count=len(rows),
        )
        postings.append(posting)
    locked.status = OpeningBalanceBatch.POSTED
    locked.posted_by_id = actor.pk
    locked.posted_by_label = actor_label(actor)
    locked.posted_at = timezone.now()
    locked.state_version += 1
    locked.save()
    record_opening_event(
        locked,
        "posted",
        actor,
        snapshot={
            "journal_entries": [str(item.entry.public_id) for item in postings],
            "posting_count": len(postings),
            "zero_balance_declaration": locked.is_zero_balance_declaration,
        },
    )
    return locked


@transaction.atomic(using=FINANCE_DB)
def reconcile_opening_batch(batch, actor):
    if not can_post_opening_balances(actor):
        raise ValidationError("You are not authorized to reconcile opening balances.")
    locked = OpeningBalanceBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status != OpeningBalanceBatch.POSTED:
        raise ValidationError("Only a posted opening batch can be reconciled.")
    postings = list(locked.postings.select_related("entry"))
    posted_debit = Decimal("0.00")
    posted_credit = Decimal("0.00")
    posted_rows = 0
    details = []
    for posting in postings:
        debit, credit = posting.entry.totals
        posted_debit += debit
        posted_credit += credit
        posted_rows += posting.row_count
        details.append({
            "entry": str(posting.entry.public_id), "reference": posting.entry.reference,
            "debit": str(debit), "credit": str(credit), "row_count": posting.row_count,
        })
    summary = {
        "expected_debit": str(locked.expected_debit),
        "expected_credit": str(locked.expected_credit),
        "expected_row_count": locked.expected_row_count,
        "posted_debit": str(posted_debit),
        "posted_credit": str(posted_credit),
        "posted_row_count": posted_rows,
        "debit_difference": str(posted_debit - locked.expected_debit),
        "credit_difference": str(posted_credit - locked.expected_credit),
        "row_difference": posted_rows - locked.expected_row_count,
        "postings": details,
    }
    reconciled = (
        posted_debit == locked.expected_debit
        and posted_credit == locked.expected_credit
        and posted_rows == locked.expected_row_count
    )
    if reconciled:
        locked.status = OpeningBalanceBatch.RECONCILED
        locked.reconciled_by_id = actor.pk
        locked.reconciled_by_label = actor_label(actor)
        locked.reconciled_at = timezone.now()
        locked.state_version += 1
        locked.save()
    record_opening_event(
        locked,
        "reconciled" if reconciled else "reconciliation_failed",
        actor,
        snapshot=summary,
    )
    summary["reconciled"] = reconciled
    return locked, summary


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
    department = department_for_user(actor)
    if not can_prepare_journals(actor) or department is None or department.pk != locked.department_id:
        raise PermissionDenied
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
    department = department_for_user(actor)
    if not can_post_journals(actor) or department is None or department.pk != locked.department_id:
        raise PermissionDenied
    if locked.status != JournalEntry.SUBMITTED:
        raise ValidationError("Only a submitted journal can be posted.")
    workflow_exemption = None
    if actor.pk in {locked.created_by_id, locked.submitted_by_id}:
        from finance.exemptions import workflow_exemption_for, workflow_exemption_snapshot
        from finance.models import FinanceWorkflowExemption

        exemption = workflow_exemption_for(
            actor=actor,
            control_code=FinanceWorkflowExemption.JOURNAL_PREPARER_SELF_POSTING,
            department_id=locked.department_id,
        )
        if exemption is None:
            raise ValidationError(
                "Maker-checker control: the preparer or submitter cannot post the same journal entry unless an active "
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
    department = department_for_user(actor)
    if not can_post_journals(actor) or department is None or department.pk != locked.department_id:
        raise PermissionDenied
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
        original_subsidiary = JournalSubsidiaryLine.objects.filter(journal_line=line).first()
        if original_subsidiary:
            reversed_subsidiary = JournalSubsidiaryLine(
                entry=reversal,
                journal_line=reversed_line,
                category=original_subsidiary.category,
                reference_key=original_subsidiary.reference_key,
                reference_label=original_subsidiary.reference_label,
                source_code=original_subsidiary.source_code,
                source_reference=str(reversal.public_id),
                debit=original_subsidiary.credit,
                credit=original_subsidiary.debit,
                source_snapshot={
                    "reversal_of_subsidiary_line": original_subsidiary.pk,
                    "original_entry": str(locked.public_id),
                    "original_source_reference": original_subsidiary.source_reference,
                    "tax_reporting": (original_subsidiary.source_snapshot or {}).get("tax_reporting") or {},
                },
            )
            reversed_subsidiary.full_clean()
            reversed_subsidiary.save()
    record_event(
        locked, "reversal_prepared", actor, reason=reason,
        snapshot={"reversal_entry": str(reversal.public_id), "reversal_reference": reversal.reference},
    )
    record_event(
        reversal, "prepared_from_reversal", actor, reason=reason,
        snapshot={"original_entry": str(locked.public_id), "original_reference": locked.reference},
    )
    return reversal


def subsidiary_schedule_rows(department_id, category, as_of_date):
    """Aggregate posted immutable subsidiary details by fund, control account, and reference."""
    if category not in dict(JournalSubsidiaryLine.CATEGORY_CHOICES):
        raise ValidationError("Choose a supported subsidiary schedule.")
    rows = JournalSubsidiaryLine.objects.filter(
        entry__department_id=department_id,
        entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=as_of_date,
        category=category,
    ).values(
        "entry__fund__code", "journal_line__account__code", "journal_line__account__title",
        "reference_key", "reference_label", "source_code",
    ).annotate(
        debit_total=Sum("debit"), credit_total=Sum("credit"),
    ).order_by(
        "entry__fund__code", "journal_line__account__code", "reference_label", "reference_key",
    )
    result = []
    for row in rows:
        debit = row["debit_total"] or Decimal("0.00")
        credit = row["credit_total"] or Decimal("0.00")
        result.append({
            "fund_code": row["entry__fund__code"],
            "account_code": row["journal_line__account__code"],
            "account_title": row["journal_line__account__title"],
            "reference_key": row["reference_key"],
            "reference_label": row["reference_label"],
            "source_code": row["source_code"],
            "debit": debit,
            "credit": credit,
            "balance": credit - debit,
        })
    return result


def control_reconciliation_snapshot(department_id, as_of_date):
    """Compare posted GL control accounts with posted subsidiary detail by fund and category."""
    category_map = {
        PostingMapping.PAYABLE: JournalSubsidiaryLine.PAYABLE,
        PostingMapping.DEDUCTION: JournalSubsidiaryLine.WITHHOLDING,
    }
    mappings = list(PostingMapping.objects.filter(
        department_id=department_id,
        category__in=category_map,
    ).select_related("account"))
    pairs = {}
    for mapping in mappings:
        fund_ids = JournalLine.objects.filter(
            entry__department_id=department_id,
            entry__status=JournalEntry.POSTED,
            entry__entry_date__lte=as_of_date,
            account_id=mapping.account_id,
        ).values_list("entry__fund_id", flat=True).distinct()
        for fund_id in fund_ids:
            key = (category_map[mapping.category], mapping.account_id, fund_id)
            pair = pairs.setdefault(key, {"mapping_codes": set()})
            pair["mapping_codes"].add(mapping.source_code)
    subsidiary_pairs = JournalSubsidiaryLine.objects.filter(
        entry__department_id=department_id,
        entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=as_of_date,
    ).values_list("category", "journal_line__account_id", "entry__fund_id", "source_code")
    for category, account_id, fund_id, source_code in subsidiary_pairs:
        pair = pairs.setdefault((category, account_id, fund_id), {"mapping_codes": set()})
        pair["mapping_codes"].add(source_code)

    account_ids = {key[1] for key in pairs}
    fund_ids = {key[2] for key in pairs}
    accounts = {item.pk: item for item in LedgerAccount.objects.filter(pk__in=account_ids)}
    funds = {item.pk: item for item in Fund.objects.filter(pk__in=fund_ids)}
    result_rows = []
    absolute_difference = Decimal("0.00")
    for (category, account_id, fund_id), pair in sorted(
        pairs.items(), key=lambda item: (funds[item[0][2]].code, item[0][0], accounts[item[0][1]].code),
    ):
        gl = JournalLine.objects.filter(
            entry__department_id=department_id,
            entry__status=JournalEntry.POSTED,
            entry__entry_date__lte=as_of_date,
            entry__fund_id=fund_id,
            account_id=account_id,
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
        subsidiary = JournalSubsidiaryLine.objects.filter(
            entry__department_id=department_id,
            entry__status=JournalEntry.POSTED,
            entry__entry_date__lte=as_of_date,
            entry__fund_id=fund_id,
            journal_line__account_id=account_id,
            category=category,
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
        gl_balance = (gl["credit"] or Decimal("0.00")) - (gl["debit"] or Decimal("0.00"))
        subsidiary_balance = (subsidiary["credit"] or Decimal("0.00")) - (subsidiary["debit"] or Decimal("0.00"))
        difference = gl_balance - subsidiary_balance
        absolute_difference += abs(difference)
        result_rows.append({
            "category": category,
            "category_label": dict(JournalSubsidiaryLine.CATEGORY_CHOICES)[category],
            "fund_id": fund_id,
            "fund_code": funds[fund_id].code,
            "account_id": account_id,
            "account_code": accounts[account_id].code,
            "account_title": accounts[account_id].title,
            "mapping_codes": sorted(pair["mapping_codes"]),
            "gl_balance": str(gl_balance),
            "subsidiary_balance": str(subsidiary_balance),
            "difference": str(difference),
            "balanced": difference == 0,
        })
    snapshot = {
        "schema_version": 1,
        "as_of_date": as_of_date.isoformat(),
        "balance_basis": "credit minus debit by fund and mapped control account",
        "configured": bool(mappings),
        "configured_categories": sorted({category_map[item.category] for item in mappings}),
        "rows": result_rows,
        "absolute_difference_total": str(absolute_difference),
        "balanced": bool(mappings) and absolute_difference == 0,
    }
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return snapshot, hashlib.sha256(encoded).hexdigest()


@transaction.atomic(using=FINANCE_DB)
def run_control_reconciliation(department, actor, as_of_date):
    if not can_reconcile_controls(actor):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    if as_of_date > timezone.localdate():
        raise ValidationError("The control reconciliation date cannot be in the future.")
    snapshot, checksum = control_reconciliation_snapshot(department.pk, as_of_date)
    run = ControlAccountReconciliation(
        department_id=department.pk,
        department_label=department.name,
        as_of_date=as_of_date,
        is_balanced=snapshot["balanced"],
        absolute_difference_total=Decimal(snapshot["absolute_difference_total"]),
        result_snapshot=snapshot,
        result_checksum=checksum,
        prepared_by_id=actor.pk,
        prepared_by_label=actor_label(actor),
    )
    run.full_clean()
    run.save()
    AccountingAuditEvent.objects.create(
        department_id=department.pk,
        department_label=department.name,
        action="control_reconciliation_run",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={
            "reconciliation_public_id": str(run.public_id),
            "as_of_date": as_of_date.isoformat(),
            "balanced": run.is_balanced,
            "absolute_difference_total": str(run.absolute_difference_total),
            "result_checksum": checksum,
        },
    )
    return run


@transaction.atomic(using=FINANCE_DB)
def close_period(period, actor, *, approved_run=None):
    locked = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if locked.status != AccountingPeriod.OPEN:
        raise ValidationError("This accounting period is already closed.")
    unposted = locked.journal_entries.exclude(status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).count()
    if unposted:
        raise ValidationError(f"Close or discard {unposted} unposted journal entry/entries before closing this period.")
    if (
        approved_run is None
        or approved_run.period_id != locked.pk
        or approved_run.status != approved_run.SUBMITTED
    ):
        raise ValidationError(
            "Use the governed period-close checklist and independent approval before closing this period."
        )
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
        snapshot={
            "fiscal_year": locked.fiscal_year,
            "period_number": locked.period_number,
            "close_run_public_id": str(approved_run.public_id),
            "checklist_checksum": approved_run.checklist_checksum,
            "policy_checksum": approved_run.policy_checksum,
        },
    )
    return locked


def _bank_event(batch, action, actor, *, reason="", snapshot=None):
    return BankReconciliationEvent.objects.create(
        department_id=batch.department_id,
        department_label=batch.department_label,
        batch=batch,
        action=action,
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        reason=str(reason or "").strip(),
        snapshot=snapshot or {},
    )


def record_bank_reconciliation_event(batch, action, actor, *, reason="", snapshot=None):
    return _bank_event(batch, action, actor, reason=reason, snapshot=snapshot)


def _bank_money(value, label):
    text = str(value or "").replace(",", "").strip()
    if not text:
        return Decimal("0.00")
    try:
        amount = Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{label} must be a valid amount.") from exc
    if amount < 0:
        raise ValidationError(f"{label} cannot be negative.")
    return amount


def _bank_account(batch):
    mapping = PostingMapping.objects.select_related("account").filter(
        department_id=batch.department_id,
        category=PostingMapping.BANK,
        source_code__iexact=batch.bank_account_code.strip(),
        is_active=True,
    ).first()
    if not mapping:
        raise ValidationError(
            f"No active bank-account posting mapping exists for {batch.bank_account_code}. "
            "Adopt or correct Finance Setup before reconciling this statement."
        )
    return mapping.account


def _bank_book_lines(batch):
    account = _bank_account(batch)
    return JournalLine.objects.select_related("entry", "account").filter(
        entry__department_id=batch.department_id,
        entry__fund_id=batch.fund_id,
        entry__status=JournalEntry.POSTED,
        entry__entry_date__lte=batch.period_end,
        account=account,
    ).order_by("entry__entry_date", "entry__reference", "sequence", "pk")


def _bank_lines(batch):
    """Return bank transaction lines, excluding the governed opening baseline."""

    return _bank_book_lines(batch).exclude(entry__opening_balance_posting__isnull=False)


def _match_snapshot(row, line):
    return {
        "statement": {
            "row_id": row.pk,
            "source_version": row.source_version,
            "row_number": row.row_number,
            "date": row.transaction_date.isoformat(),
            "reference": row.bank_reference,
            "description": row.description,
            "withdrawal": str(row.withdrawal),
            "deposit": str(row.deposit),
            "row_checksum": row.row_checksum,
        },
        "ledger": {
            "journal_line_id": line.pk,
            "entry_public_id": str(line.entry.public_id),
            "entry_reference": line.entry.reference,
            "entry_date": line.entry.entry_date.isoformat(),
            "source_type": line.entry.source_type,
            "source_reference": line.entry.source_reference,
            "account_code": line.account.code,
            "debit": str(line.debit),
            "credit": str(line.credit),
            "memo": line.memo,
        },
    }


def _snapshot_checksum(snapshot):
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic(using=FINANCE_DB)
def correct_bank_statement_batch(batch, actor, *, values, reason):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to correct bank reconciliation controls.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status not in (BankStatementBatch.DRAFT, BankStatementBatch.VALIDATED, BankStatementBatch.RETURNED):
        raise ValidationError("Only a pre-submission or returned bank reconciliation can be corrected.")
    note = str(reason or "").strip()
    if not note:
        raise ValidationError("Explain the authority or source for this correction.")
    fields = (
        "statement_reference", "bank_account_code", "bank_name", "account_number_masked", "fund",
        "period_start", "period_end", "received_on", "opening_balance", "closing_balance",
        "expected_row_count", "expected_deposits", "expected_withdrawals",
    )
    before = {field: getattr(locked, f"{field}_id", None) if field == "fund" else getattr(locked, field) for field in fields}
    for field in fields:
        if field in values:
            setattr(locked, field, values[field])
    locked.status = BankStatementBatch.DRAFT
    locked.validation_summary = {}
    locked.state_version += 1
    locked.full_clean()
    locked.save()
    now = timezone.now()
    active_matches = list(BankStatementMatch.objects.select_for_update().filter(
        batch=locked, status=BankStatementMatch.ACTIVE,
    ))
    _reopen_cleared_items_for_matches(
        active_matches, actor, reason=f"Statement control correction: {note}",
    )
    BankStatementMatch.objects.filter(pk__in=[match.pk for match in active_matches]).update(
        status=BankStatementMatch.SUPERSEDED, superseded_at=now,
    )
    BankOutstandingItem.objects.filter(batch=locked, status=BankOutstandingItem.ACTIVE).update(
        status=BankOutstandingItem.SUPERSEDED, superseded_at=now,
    )
    after = {field: getattr(locked, f"{field}_id", None) if field == "fund" else getattr(locked, field) for field in fields}
    safe_change = json.loads(json.dumps({"before": before, "after": after}, default=str))
    _bank_event(locked, "controls_corrected", actor, reason=note, snapshot=safe_change)
    return locked


@transaction.atomic(using=FINANCE_DB)
def stage_bank_statement_csv(batch, actor, uploaded_file, *, change_reason=""):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to stage bank statements.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status not in (BankStatementBatch.DRAFT, BankStatementBatch.VALIDATED, BankStatementBatch.RETURNED):
        raise ValidationError("Only a pre-submission or returned bank statement can be restaged.")
    if locked.source_version and not str(change_reason or "").strip():
        raise ValidationError("Explain why the staged bank statement is being replaced.")
    raw = uploaded_file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise ValidationError("The bank statement CSV exceeds the 5 MB staging limit.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Use a UTF-8 CSV bank statement.") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"transaction_date", "bank_reference", "description", "withdrawal", "deposit", "running_balance"}
    if not reader.fieldnames or not required.issubset({str(name or "").strip() for name in reader.fieldnames}):
        raise ValidationError(
            "Use CSV columns: transaction_date, bank_reference, description, withdrawal, deposit, running_balance."
        )
    source_version = locked.source_version + 1
    staged = []
    for row_number, source in enumerate(reader, start=1):
        if not any(str(value or "").strip() for value in source.values()):
            continue
        transaction_date = parse_date(str(source.get("transaction_date") or "").strip())
        if not transaction_date:
            raise ValidationError(f"Row {row_number}: transaction_date must use YYYY-MM-DD.")
        if not locked.period_start <= transaction_date <= locked.period_end:
            raise ValidationError(f"Row {row_number}: transaction date is outside the statement period.")
        withdrawal = _bank_money(source.get("withdrawal"), f"Row {row_number} withdrawal")
        deposit = _bank_money(source.get("deposit"), f"Row {row_number} deposit")
        if (withdrawal > 0) == (deposit > 0):
            raise ValidationError(f"Row {row_number}: enter a positive withdrawal or deposit, not both.")
        running_raw = str(source.get("running_balance") or "").replace(",", "").strip()
        try:
            running_balance = Decimal(running_raw).quantize(Decimal("0.01")) if running_raw else None
        except InvalidOperation as exc:
            raise ValidationError(f"Row {row_number}: running_balance must be a valid amount.") from exc
        evidence = {
            "source_version": source_version,
            "row_number": row_number,
            "transaction_date": transaction_date.isoformat(),
            "bank_reference": str(source.get("bank_reference") or "").strip(),
            "description": str(source.get("description") or "").strip(),
            "withdrawal": str(withdrawal),
            "deposit": str(deposit),
            "running_balance": str(running_balance) if running_balance is not None else "",
        }
        staged.append(BankStatementRow(
            batch=locked,
            source_version=source_version,
            row_number=row_number,
            transaction_date=transaction_date,
            bank_reference=evidence["bank_reference"][:120],
            description=evidence["description"][:255] or "Bank statement transaction",
            withdrawal=withdrawal,
            deposit=deposit,
            running_balance=running_balance,
            row_checksum=_snapshot_checksum(evidence),
        ))
    if not staged:
        raise ValidationError("The bank statement CSV contains no transaction rows.")
    now = timezone.now()
    if locked.source_version:
        active_matches = list(BankStatementMatch.objects.select_for_update().filter(
            batch=locked, statement_row__source_version=locked.source_version, status=BankStatementMatch.ACTIVE,
        ))
        _reopen_cleared_items_for_matches(
            active_matches, actor, reason=f"Statement source restaged: {change_reason}",
        )
        BankStatementMatch.objects.filter(pk__in=[match.pk for match in active_matches]).update(
            status=BankStatementMatch.SUPERSEDED, superseded_at=now,
        )
        BankOutstandingItem.objects.filter(batch=locked, status=BankOutstandingItem.ACTIVE).update(
            status=BankOutstandingItem.SUPERSEDED, superseded_at=now,
        )
    BankStatementRow.objects.bulk_create(staged)
    locked.source_version = source_version
    locked.source_filename = str(getattr(uploaded_file, "name", "bank-statement.csv"))[:255]
    locked.source_checksum = hashlib.sha256(raw).hexdigest()
    locked.status = BankStatementBatch.DRAFT
    locked.validation_summary = {}
    locked.state_version += 1
    locked.save(update_fields=(
        "source_version", "source_filename", "source_checksum", "status", "validation_summary",
        "state_version", "updated_at",
    ))
    _bank_event(
        locked,
        "statement_staged" if source_version == 1 else "statement_restaged",
        actor,
        reason=change_reason,
        snapshot={
            "source_version": source_version,
            "source_filename": locked.source_filename,
            "source_checksum": locked.source_checksum,
            "row_count": len(staged),
        },
    )
    return validate_bank_statement(locked, actor)


@transaction.atomic(using=FINANCE_DB)
def validate_bank_statement(batch, actor):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to validate bank statements.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status not in (BankStatementBatch.DRAFT, BankStatementBatch.RETURNED, BankStatementBatch.VALIDATED):
        raise ValidationError("Only draft, returned, or validated statement staging can be validated.")
    _bank_account(locked)
    rows = list(locked.rows.filter(source_version=locked.source_version).order_by("row_number"))
    deposits = sum((row.deposit for row in rows), Decimal("0.00"))
    withdrawals = sum((row.withdrawal for row in rows), Decimal("0.00"))
    computed_closing = locked.opening_balance + deposits - withdrawals
    running_errors = []
    running = locked.opening_balance
    for row in rows:
        running += row.deposit - row.withdrawal
        if row.running_balance is not None and row.running_balance != running:
            running_errors.append(row.row_number)
    errors = []
    if len(rows) != locked.expected_row_count:
        errors.append("Declared row count does not match the staged rows.")
    if deposits != locked.expected_deposits:
        errors.append("Declared deposits do not match the staged rows.")
    if withdrawals != locked.expected_withdrawals:
        errors.append("Declared withdrawals do not match the staged rows.")
    if computed_closing != locked.closing_balance:
        errors.append("Opening balance plus deposits less withdrawals does not equal the closing balance.")
    if running_errors:
        errors.append("Running balance differs on row(s): " + ", ".join(str(value) for value in running_errors[:20]))
    summary = {
        "valid": bool(rows) and not errors,
        "source_version": locked.source_version,
        "row_count": len(rows),
        "deposits": str(deposits),
        "withdrawals": str(withdrawals),
        "computed_closing": str(computed_closing),
        "errors": errors,
    }
    locked.status = BankStatementBatch.VALIDATED if summary["valid"] else BankStatementBatch.DRAFT
    locked.validation_summary = summary
    locked.state_version += 1
    locked.save(update_fields=("status", "validation_summary", "state_version", "updated_at"))
    _bank_event(
        locked, "statement_validated" if summary["valid"] else "statement_validation_failed", actor,
        snapshot=summary,
    )
    return locked


def _assert_bank_batch_editable(batch):
    if batch.status not in (BankStatementBatch.DRAFT, BankStatementBatch.VALIDATED, BankStatementBatch.RETURNED):
        raise ValidationError("Matching can change only before submission or after an independent return.")


def bank_outstanding_carry_candidates(batch):
    """Return the latest unresolved, approved prior-period item for each eligible ledger line."""
    eligible_line_ids = list(_bank_lines(batch).values_list("pk", flat=True))
    if not eligible_line_ids:
        return []
    current_line_ids = set(BankOutstandingItem.objects.filter(
        batch=batch, status=BankOutstandingItem.ACTIVE,
    ).values_list("journal_line_id", flat=True))
    matched_line_ids = set(BankStatementMatch.objects.filter(
        journal_line_id__in=eligible_line_ids, status=BankStatementMatch.ACTIVE,
    ).values_list("journal_line_id", flat=True))
    candidates = BankOutstandingItem.objects.filter(
        status=BankOutstandingItem.ACTIVE,
        batch__department_id=batch.department_id,
        batch__bank_account_code__iexact=batch.bank_account_code.strip(),
        batch__fund_id=batch.fund_id,
        batch__status=BankStatementBatch.RECONCILED,
        batch__period_end__lt=batch.period_start,
        journal_line_id__in=eligible_line_ids,
    ).exclude(
        journal_line_id__in=current_line_ids | matched_line_ids,
    ).select_related(
        "batch", "journal_line__entry", "journal_line__account", "carried_from__batch",
    ).order_by("journal_line_id", "-batch__period_end", "-created_at", "-pk")
    latest = {}
    for item in candidates:
        latest.setdefault(item.journal_line_id, item)
    return list(latest.values())


@transaction.atomic(using=FINANCE_DB)
def carry_forward_bank_outstanding(batch, actor):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to carry bank-reconciliation timing items.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    _assert_bank_batch_editable(locked)
    if not locked.validation_summary.get("valid"):
        raise ValidationError("Validate the current bank statement before carrying prior timing items.")
    source_candidates = bank_outstanding_carry_candidates(locked)
    if not source_candidates:
        return []
    source_ids = [item.pk for item in source_candidates]
    sources = BankOutstandingItem.objects.select_for_update().select_related(
        "batch", "journal_line__entry", "journal_line__account",
    ).filter(
        pk__in=source_ids,
        status=BankOutstandingItem.ACTIVE,
        batch__status=BankStatementBatch.RECONCILED,
    )
    source_map = {item.pk: item for item in sources}
    now = timezone.now()
    created = []
    for source_id in source_ids:
        source = source_map[source_id]
        if BankStatementMatch.objects.filter(
            journal_line_id=source.journal_line_id, status=BankStatementMatch.ACTIVE,
        ).exists() or BankOutstandingItem.objects.filter(
            batch=locked, journal_line_id=source.journal_line_id, status=BankOutstandingItem.ACTIVE,
        ).exists():
            continue
        snapshot = {
            "journal_line_id": source.journal_line_id,
            "entry_public_id": str(source.journal_line.entry.public_id),
            "entry_reference": source.journal_line.entry.reference,
            "entry_date": source.journal_line.entry.entry_date.isoformat(),
            "account_code": source.journal_line.account.code,
            "debit": str(source.journal_line.debit),
            "credit": str(source.journal_line.credit),
            "kind": source.kind,
            "expected_clearance_date": source.expected_clearance_date.isoformat(),
            "evidence_reference": source.evidence_reference,
            "carried_from_item_id": source.pk,
            "carried_from_batch_public_id": str(source.batch.public_id),
            "carried_from_statement_reference": source.batch.statement_reference,
            "carried_from_period_end": source.batch.period_end.isoformat(),
            "carried_from_checksum": source.source_checksum,
            "overdue_as_of_period_end": source.expected_clearance_date <= locked.period_end,
        }
        created.append(BankOutstandingItem.objects.create(
            batch=locked,
            journal_line=source.journal_line,
            kind=source.kind,
            explanation=source.explanation,
            evidence_reference=source.evidence_reference,
            expected_clearance_date=source.expected_clearance_date,
            source_snapshot=snapshot,
            source_checksum=_snapshot_checksum(snapshot),
            created_by_id=actor.pk,
            created_by_label=actor_label(actor),
            carried_from=source,
            carried_by_id=actor.pk,
            carried_by_label=actor_label(actor),
            carried_at=now,
        ))
    if created:
        locked.state_version += 1
        locked.save(update_fields=("state_version", "updated_at"))
        _bank_event(locked, "prior_outstanding_items_carried", actor, snapshot={
            "count": len(created),
            "item_checksums": [item.source_checksum for item in created],
            "source_statement_references": sorted({item.carried_from.batch.statement_reference for item in created}),
            "overdue_count": sum(item.expected_clearance_date <= locked.period_end for item in created),
        })
    return created


def _clear_outstanding_items_for_match(batch, match, actor):
    items = list(BankOutstandingItem.objects.select_for_update().select_related("batch").filter(
        status=BankOutstandingItem.ACTIVE,
        journal_line_id=match.journal_line_id,
        batch__department_id=batch.department_id,
        batch__bank_account_code__iexact=batch.bank_account_code.strip(),
        batch__fund_id=batch.fund_id,
        batch__period_end__lte=batch.period_end,
    ))
    now = timezone.now()
    for item in items:
        item._lineage_transition = True
        item.status = BankOutstandingItem.CLEARED
        item.cleared_by_match = match
        item.cleared_by_id = actor.pk
        item.cleared_by_label = actor_label(actor)
        item.cleared_at = now
        item.save(update_fields=(
            "status", "cleared_by_match", "cleared_by_id", "cleared_by_label", "cleared_at",
        ))
        _bank_event(item.batch, "outstanding_item_cleared", actor, reason=match.reason, snapshot={
            "item_checksum": item.source_checksum,
            "clearing_statement_reference": batch.statement_reference,
            "clearing_statement_row": match.statement_row.row_number,
            "clearing_match_checksum": match.source_checksum,
        })
    return items


def _reopen_cleared_items_for_matches(matches, actor, *, reason):
    match_ids = [match.pk for match in matches]
    if not match_ids:
        return []
    items = list(BankOutstandingItem.objects.select_for_update().select_related("batch").filter(
        status=BankOutstandingItem.CLEARED, cleared_by_match_id__in=match_ids,
    ))
    for item in items:
        prior_match_id = item.cleared_by_match_id
        item._lineage_transition = True
        item.status = BankOutstandingItem.ACTIVE
        item.cleared_by_match = None
        item.cleared_by_id = None
        item.cleared_by_label = ""
        item.cleared_at = None
        item.save(update_fields=(
            "status", "cleared_by_match", "cleared_by_id", "cleared_by_label", "cleared_at",
        ))
        _bank_event(item.batch, "outstanding_item_clearance_reopened", actor, reason=reason, snapshot={
            "item_checksum": item.source_checksum,
            "superseded_match_id": prior_match_id,
        })
    return items


@transaction.atomic(using=FINANCE_DB)
def match_bank_statement_row(row, line, actor, *, reason, method=BankStatementMatch.MANUAL):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to match bank statement rows.")
    locked_row = BankStatementRow.objects.select_for_update().select_related("batch").get(pk=row.pk)
    batch = BankStatementBatch.objects.select_for_update().get(pk=locked_row.batch_id)
    _assert_bank_batch_editable(batch)
    if locked_row.source_version != batch.source_version:
        raise ValidationError("Only the current staged statement version can be matched.")
    note = str(reason or "").strip()
    if not note:
        raise ValidationError("Record the match basis or supporting reference.")
    ledger_line = JournalLine.objects.select_related("entry", "account").get(pk=line.pk)
    if ledger_line not in _bank_lines(batch):
        raise ValidationError("Choose a posted bank-account journal line for this fund and statement period.")
    if locked_row.withdrawal != ledger_line.credit or locked_row.deposit != ledger_line.debit:
        raise ValidationError("The bank row amount and debit/credit direction must exactly match the journal line.")
    if BankStatementMatch.objects.filter(journal_line=ledger_line, status=BankStatementMatch.ACTIVE).exclude(
        statement_row=locked_row,
    ).exists():
        raise ValidationError("That journal line is already matched to another active bank row.")
    now = timezone.now()
    BankStatementMatch.objects.filter(statement_row=locked_row, status=BankStatementMatch.ACTIVE).update(
        status=BankStatementMatch.SUPERSEDED, superseded_at=now,
    )
    snapshot = _match_snapshot(locked_row, ledger_line)
    match = BankStatementMatch.objects.create(
        batch=batch,
        statement_row=locked_row,
        journal_line=ledger_line,
        method=method,
        reason=note,
        source_snapshot=snapshot,
        source_checksum=_snapshot_checksum(snapshot),
        created_by_id=actor.pk,
        created_by_label=actor_label(actor),
    )
    cleared_items = _clear_outstanding_items_for_match(batch, match, actor)
    batch.state_version += 1
    batch.save(update_fields=("state_version", "updated_at"))
    _bank_event(batch, "row_matched", actor, reason=note, snapshot={
        "statement_row": locked_row.row_number,
        "journal_line_id": ledger_line.pk,
        "entry_reference": ledger_line.entry.reference,
        "method": method,
        "match_checksum": match.source_checksum,
        "cleared_outstanding_item_checksums": [item.source_checksum for item in cleared_items],
    })
    return match


@transaction.atomic(using=FINANCE_DB)
def auto_match_bank_statement(batch, actor):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to match bank statements.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    _assert_bank_batch_editable(locked)
    rows = locked.rows.filter(source_version=locked.source_version).exclude(
        matches__status=BankStatementMatch.ACTIVE,
    ).order_by("row_number")
    available = list(_bank_lines(locked).exclude(bank_statement_matches__status=BankStatementMatch.ACTIVE).distinct())
    matched = 0
    for row in rows:
        reference = row.bank_reference.strip().casefold()
        if len(reference) < 3:
            continue
        candidates = []
        for line in available:
            haystack = " ".join((
                line.entry.reference, line.entry.source_reference or "", line.entry.description, line.memo,
            )).casefold()
            amount_ok = row.withdrawal == line.credit and row.deposit == line.debit
            if amount_ok and row.transaction_date == line.entry.entry_date and reference in haystack:
                candidates.append(line)
        if len(candidates) == 1:
            line = candidates[0]
            match_bank_statement_row(
                row, line, actor,
                reason="Unique exact date, reference, amount, and debit/credit-direction match.",
                method=BankStatementMatch.AUTO,
            )
            available.remove(line)
            matched += 1
    return matched


@transaction.atomic(using=FINANCE_DB)
def unmatch_bank_statement_row(row, actor, *, reason):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to correct bank matches.")
    locked_row = BankStatementRow.objects.select_for_update().select_related("batch").get(pk=row.pk)
    batch = BankStatementBatch.objects.select_for_update().get(pk=locked_row.batch_id)
    _assert_bank_batch_editable(batch)
    note = str(reason or "").strip()
    if not note:
        raise ValidationError("Explain why the match is being removed.")
    match = BankStatementMatch.objects.filter(
        statement_row=locked_row, status=BankStatementMatch.ACTIVE,
    ).first()
    if not match:
        raise ValidationError("This statement row has no active match.")
    reopened_items = _reopen_cleared_items_for_matches(
        [match], actor, reason=f"Match correction: {note}",
    )
    match._lineage_transition = True
    match.status = BankStatementMatch.SUPERSEDED
    match.superseded_at = timezone.now()
    match.save(update_fields=("status", "superseded_at"))
    batch.state_version += 1
    batch.save(update_fields=("state_version", "updated_at"))
    _bank_event(batch, "row_unmatched", actor, reason=note, snapshot={
        "statement_row": locked_row.row_number,
        "journal_line_id": match.journal_line_id,
        "prior_match_checksum": match.source_checksum,
        "reopened_outstanding_item_checksums": [item.source_checksum for item in reopened_items],
    })
    return batch


@transaction.atomic(using=FINANCE_DB)
def classify_bank_outstanding(batch, line, actor, *, explanation, evidence_reference, expected_clearance_date):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to classify outstanding bank items.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    _assert_bank_batch_editable(locked)
    note = str(explanation or "").strip()
    evidence = str(evidence_reference or "").strip()
    if not note or not evidence or not expected_clearance_date:
        raise ValidationError("Explanation, supporting reference, and expected clearance date are required.")
    if expected_clearance_date <= locked.period_end:
        raise ValidationError("Expected clearance must be after the statement end date.")
    ledger_line = JournalLine.objects.select_related("entry", "account").get(pk=line.pk)
    if ledger_line not in _bank_lines(locked):
        raise ValidationError("Choose an eligible posted bank-account journal line.")
    if BankStatementMatch.objects.filter(journal_line=ledger_line, status=BankStatementMatch.ACTIVE).exists():
        raise ValidationError("A matched journal line is not an outstanding item.")
    kind = (
        BankOutstandingItem.OUTSTANDING_DEPOSIT if ledger_line.debit > 0
        else BankOutstandingItem.OUTSTANDING_CHECK
    )
    now = timezone.now()
    prior_item = BankOutstandingItem.objects.select_for_update().select_related("carried_from").filter(
        batch=locked, journal_line=ledger_line, status=BankOutstandingItem.ACTIVE,
    ).first()
    if prior_item:
        prior_item._lineage_transition = True
        prior_item.status = BankOutstandingItem.SUPERSEDED
        prior_item.superseded_at = now
        prior_item.save(update_fields=("status", "superseded_at"))
    snapshot = {
        "journal_line_id": ledger_line.pk,
        "entry_public_id": str(ledger_line.entry.public_id),
        "entry_reference": ledger_line.entry.reference,
        "entry_date": ledger_line.entry.entry_date.isoformat(),
        "account_code": ledger_line.account.code,
        "debit": str(ledger_line.debit),
        "credit": str(ledger_line.credit),
        "kind": kind,
        "expected_clearance_date": expected_clearance_date.isoformat(),
        "evidence_reference": evidence,
        "replaces_item_checksum": prior_item.source_checksum if prior_item else "",
    }
    if prior_item and prior_item.carried_from_id:
        snapshot.update({
            "carried_from_item_id": prior_item.carried_from_id,
            "carried_from_checksum": prior_item.carried_from.source_checksum,
        })
    item = BankOutstandingItem.objects.create(
        batch=locked,
        journal_line=ledger_line,
        kind=kind,
        explanation=note,
        evidence_reference=evidence,
        expected_clearance_date=expected_clearance_date,
        source_snapshot=snapshot,
        source_checksum=_snapshot_checksum(snapshot),
        created_by_id=actor.pk,
        created_by_label=actor_label(actor),
        carried_from=prior_item.carried_from if prior_item and prior_item.carried_from_id else None,
        carried_by_id=prior_item.carried_by_id if prior_item and prior_item.carried_from_id else None,
        carried_by_label=prior_item.carried_by_label if prior_item and prior_item.carried_from_id else "",
        carried_at=prior_item.carried_at if prior_item and prior_item.carried_from_id else None,
    )
    locked.state_version += 1
    locked.save(update_fields=("state_version", "updated_at"))
    _bank_event(locked, "outstanding_item_classified", actor, reason=note, snapshot={
        "journal_line_id": ledger_line.pk,
        "kind": kind,
        "evidence_reference": evidence,
        "expected_clearance_date": expected_clearance_date.isoformat(),
        "item_checksum": item.source_checksum,
        "replaced_item_checksum": prior_item.source_checksum if prior_item else "",
    })
    return item


@transaction.atomic(using=FINANCE_DB)
def unclassify_bank_outstanding(batch, line, actor, *, reason):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to correct outstanding bank items.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    _assert_bank_batch_editable(locked)
    note = str(reason or "").strip()
    if not note:
        raise ValidationError("Explain why the timing-item classification is being removed.")
    item = BankOutstandingItem.objects.filter(
        batch=locked, journal_line=line, status=BankOutstandingItem.ACTIVE,
    ).first()
    if not item:
        raise ValidationError("This journal line has no active outstanding-item classification.")
    item._lineage_transition = True
    item.status = BankOutstandingItem.SUPERSEDED
    item.superseded_at = timezone.now()
    item.save(update_fields=("status", "superseded_at"))
    locked.state_version += 1
    locked.save(update_fields=("state_version", "updated_at"))
    _bank_event(locked, "outstanding_item_unclassified", actor, reason=note, snapshot={
        "journal_line_id": line.pk,
        "prior_item_checksum": item.source_checksum,
    })
    return locked


def bank_reconciliation_snapshot(batch):
    rows = list(batch.rows.filter(source_version=batch.source_version).order_by("row_number"))
    row_ids = [row.pk for row in rows]
    matches = list(BankStatementMatch.objects.filter(
        statement_row_id__in=row_ids, status=BankStatementMatch.ACTIVE,
    ).select_related("statement_row", "journal_line__entry"))
    book_lines = list(_bank_book_lines(batch))
    # A governed opening JEV establishes the book baseline represented by the
    # statement's opening balance. It belongs in the cumulative book balance,
    # but it is not a bank transaction row to match or classify as outstanding.
    transaction_lines = list(_bank_lines(batch))
    globally_matched_ids = set(BankStatementMatch.objects.filter(
        journal_line_id__in=[line.pk for line in transaction_lines],
        status=BankStatementMatch.ACTIVE,
        batch__period_end__lte=batch.period_end,
    ).values_list("journal_line_id", flat=True))
    unmatched_lines = [line for line in transaction_lines if line.pk not in globally_matched_ids]
    items = list(BankOutstandingItem.objects.filter(
        batch=batch, journal_line_id__in=[line.pk for line in unmatched_lines],
    ).filter(
        Q(status=BankOutstandingItem.ACTIVE)
        | Q(status=BankOutstandingItem.CLEARED, cleared_by_match__batch__period_end__gt=batch.period_end),
    ).select_related(
        "batch", "journal_line__entry", "carried_from__batch", "cleared_by_match__batch",
    ))
    item_line_ids = {item.journal_line_id for item in items}
    outstanding_deposits = sum((item.journal_line.debit for item in items), Decimal("0.00"))
    outstanding_checks = sum((item.journal_line.credit for item in items), Decimal("0.00"))
    book_balance = sum((line.debit - line.credit for line in book_lines), Decimal("0.00"))
    adjusted_bank_balance = batch.closing_balance + outstanding_deposits - outstanding_checks
    difference = adjusted_bank_balance - book_balance
    snapshot = {
        "schema_version": 2,
        "method": "adjusted_balance",
        "batch_public_id": str(batch.public_id),
        "bank_account_code": batch.bank_account_code,
        "fund_code": batch.fund.code,
        "period_start": batch.period_start.isoformat(),
        "period_end": batch.period_end.isoformat(),
        "source_version": batch.source_version,
        "source_checksum": batch.source_checksum,
        "statement_row_count": len(rows),
        "matched_row_count": len(matches),
        "unmatched_statement_row_count": len(rows) - len(matches),
        "unmatched_ledger_line_count": len(unmatched_lines),
        "classified_outstanding_count": len(items),
        "carried_forward_count": sum(bool(item.carried_from_id) for item in items),
        "overdue_outstanding_count": sum(item.expected_clearance_date <= batch.period_end for item in items),
        "unclassified_ledger_line_count": len([line for line in unmatched_lines if line.pk not in item_line_ids]),
        "statement_closing_balance": str(batch.closing_balance),
        "outstanding_deposits": str(outstanding_deposits),
        "outstanding_checks": str(outstanding_checks),
        "adjusted_bank_balance": str(adjusted_bank_balance),
        "book_balance": str(book_balance),
        "difference": str(difference),
        "matched_line_ids": sorted(match.journal_line_id for match in matches),
        "outstanding_item_checksums": sorted(item.source_checksum for item in items),
        "carry_forward_lineage": sorted(
            f"{item.carried_from_id}:{item.source_checksum}" for item in items if item.carried_from_id
        ),
    }
    snapshot["ready_for_review"] = bool(batch.validation_summary.get("valid")) and all((
        snapshot["unmatched_statement_row_count"] == 0,
        snapshot["unclassified_ledger_line_count"] == 0,
        difference == 0,
    ))
    return snapshot, _snapshot_checksum(snapshot), rows, matches, unmatched_lines, items


@transaction.atomic(using=FINANCE_DB)
def submit_bank_reconciliation(batch, actor):
    if not can_prepare_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to submit bank reconciliations.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status != BankStatementBatch.VALIDATED:
        raise ValidationError("Validate the current statement staging before submission.")
    snapshot, checksum, _rows, _matches, _lines, _items = bank_reconciliation_snapshot(locked)
    if not snapshot["ready_for_review"]:
        raise ValidationError(
            "Reconciliation is not ready: match every statement row, classify every unmatched ledger line, "
            "and resolve the adjusted-bank-to-book difference to zero."
        )
    locked.status = BankStatementBatch.FOR_REVIEW
    locked.submitted_by_id = actor.pk
    locked.submitted_by_label = actor_label(actor)
    locked.submitted_at = timezone.now()
    locked.state_version += 1
    locked.save(update_fields=(
        "status", "submitted_by_id", "submitted_by_label", "submitted_at", "state_version", "updated_at",
    ))
    _bank_event(locked, "submitted_for_review", actor, snapshot={**snapshot, "snapshot_checksum": checksum})
    return locked


@transaction.atomic(using=FINANCE_DB)
def decide_bank_reconciliation(batch, actor, *, decision, evidence_note):
    if not can_approve_bank_reconciliation(actor):
        raise ValidationError("You are not authorized to decide bank reconciliations.")
    locked = BankStatementBatch.objects.select_for_update().get(pk=batch.pk)
    note = str(evidence_note or "").strip()
    if not note:
        raise ValidationError("Record the reviewed BRS and supporting-evidence reference.")
    if decision == BankStatementBatch.RETURNED:
        if locked.status != BankStatementBatch.FOR_REVIEW:
            raise ValidationError("Only a reconciliation under review can be returned.")
        locked.status = BankStatementBatch.RETURNED
        locked.state_version += 1
        locked.save(update_fields=("status", "state_version", "updated_at"))
        _bank_event(locked, "returned_for_correction", actor, reason=note)
        return locked
    if decision != BankStatementBatch.RECONCILED or locked.status != BankStatementBatch.FOR_REVIEW:
        raise ValidationError("Only a reconciliation under review can be reconciled.")
    if actor.pk in (locked.created_by_id, locked.submitted_by_id):
        raise ValidationError("The independent bank-reconciliation reviewer must differ from its preparer and submitter.")
    snapshot, checksum, _rows, _matches, _lines, _items = bank_reconciliation_snapshot(locked)
    if not snapshot["ready_for_review"]:
        raise ValidationError("The reconciliation controls changed or no longer produce a zero difference.")
    locked.status = BankStatementBatch.RECONCILED
    locked.reconciled_by_id = actor.pk
    locked.reconciled_by_label = actor_label(actor)
    locked.reconciled_at = timezone.now()
    locked.reconciliation_checksum = checksum
    locked.state_version += 1
    locked.save(update_fields=(
        "status", "reconciled_by_id", "reconciled_by_label", "reconciled_at",
        "reconciliation_checksum", "state_version", "updated_at",
    ))
    _bank_event(locked, "reconciled", actor, reason=note, snapshot={**snapshot, "reconciliation_checksum": checksum})
    return locked
