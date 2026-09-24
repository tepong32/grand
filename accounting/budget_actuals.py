"""Adopt, never manufacture, external certification for Budget historical context."""
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import PureWindowsPath

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from .access import department_for_user, has_explicit_permission
from .cash_classifications import checksum
from .models import (AccountingAuditEvent, BudgetActualScope, BudgetActualVersion,
    Fund, LedgerAccount, ResponsibilityCenter)

MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return has_explicit_permission(actor, f"accounting.{action}_budget_actuals") and (
        action in ("view", "export") or not is_finance_uat_viewer(actor))


def can_read(actor, record):
    office = department_for_user(actor)
    if not office or not actor.is_active:
        return False
    if office.pk == record.department_id:
        return any(permitted(actor, action) for action in ("view", "prepare", "review", "export"))
    from budget.access import has_budget_permission
    return (record.status == BudgetActualVersion.APPROVED and office.pk == record.scope.budget_department_id
        and any(has_budget_permission(actor, code) for code in
            ("prepare_budget_proposals", "review_budget_proposals", "view_budget_audit")))


def scope_snapshot(scope):
    return {"department_id": scope.department_id, "budget_department_id": scope.budget_department_id,
        "fund_id": scope.fund_id, "fund_code": scope.fund.code,
        "center_id": scope.responsibility_center_id, "center_code": scope.responsibility_center.code,
        "office_id": scope.responsibility_center.office_id,
        "period_start": scope.period_start.isoformat(), "period_end": scope.period_end.isoformat()}


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal("10000000000000000") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError
        return amount.quantize(Decimal("0.01"))
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError("Use finite amounts with at most 16 whole digits and two decimal places.")


def normalize_rows(owner_id, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValidationError("Provide between one and 1,000 explicit certificate rows, including any certified zero.")
    result, seen = [], set()
    accounts = {item.pk: item for item in LedgerAccount.objects.filter(department_id=owner_id)}
    for row in rows:
        try:
            account_id = int(row["account_id"])
            account = accounts[account_id]
            expense_class, reference = str(row["expense_class"]).strip(), str(row["source_row"]).strip()
            amount = money(row["amount"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Each row needs an account in this ledger, expense class, amount and source page/row reference.")
        if account_id in seen or not expense_class or len(expense_class) > 40 or not reference or len(reference) > 255:
            raise ValidationError("Use one explicit amount per account with a class and source page/row reference; do not repeat subtotals.")
        seen.add(account_id)
        result.append({"account_id": account.pk, "account_code": account.code, "account_title": account.title,
            "expense_class": expense_class, "amount": str(amount), "source_row": reference})
    return sorted(result, key=lambda item: item["account_id"])


def decision_snapshot(record):
    return {"record": str(record.public_id), "payload_checksum": record.payload_checksum,
        "status": record.status, "reviewed_by": record.reviewed_by_id,
        "reviewed_by_label": record.reviewed_by_label,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "authority": record.review_authority, "note": record.review_note}


def verify(record):
    if checksum(record.payload) != record.payload_checksum or hashlib.sha256(bytes(record.evidence)).hexdigest() != record.evidence_sha256:
        raise ValidationError("Retained certificate evidence does not match its checksum.")
    payload = record.payload
    identity = {key: value for key, value in scope_snapshot(record.scope).items()
                if key not in ("fund_code", "center_code", "office_id")}
    if ({key: payload.get("scope", {}).get(key) for key in identity} != identity
            or payload.get("evidence_sha256") != record.evidence_sha256
            or payload.get("evidence_name") != record.evidence_name
            or payload.get("prepared_by") != record.prepared_by_id
            or payload.get("prepared_by_label") != record.prepared_by_label
            or payload.get("prepared_at") != record.prepared_at.isoformat()
            or payload.get("version") != record.version or payload.get("base_version") != record.base_version
            or record.department_id != record.scope.department_id):
        raise ValidationError("Retained certificate identity or scope no longer matches its evidence.")
    if record.status != BudgetActualVersion.SUBMITTED and record.decision_checksum != checksum(decision_snapshot(record)):
        raise ValidationError("Retained certificate adoption decision does not match its checksum.")
    return payload


def _event(record, action, actor, note=""):
    AccountingAuditEvent.objects.create(department_id=record.department_id, department_label=record.department_label,
        action=action, actor_id=actor.pk, actor_label=(actor.get_full_name() or actor.username)[:160], reason=note,
        snapshot={"actuals_version": str(record.public_id), "scope": str(record.scope.public_id),
            "version": record.version, "payload_checksum": record.payload_checksum,
            "decision_checksum": record.decision_checksum})


@transaction.atomic(using="finance")
def propose(*, actor, fund_id, center_id, budget_department_id, period_start, period_end,
            document, rows, reference, issuer, accountant_name, certified_on, certification_authority,
            coverage, signed_total, reason, expected_latest=0):
    from budget.models import BudgetCall
    if not permitted(actor, "prepare"):
        raise PermissionDenied
    owner = department_for_user(actor)
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=owner.pk).first()
    center = ResponsibilityCenter.objects.filter(pk=center_id, department_id=owner.pk).first()
    if not fund or not center or not center.office_id:
        raise ValidationError("Select this ledger's fund and an office-linked responsibility center.")
    if not BudgetCall.objects.filter(department_id=budget_department_id, fiscal_year__department_id=owner.pk).exists():
        raise ValidationError("Select a Budget office with an explicit Budget call linked to this Accounting ledger.")
    if (not isinstance(period_start, date) or not isinstance(period_end, date)
            or period_start != date(period_end.year, 1, 1)
            or (period_end.month, period_end.day) not in ((6, 30), (12, 31))
            or period_end > timezone.localdate()):
        raise ValidationError("Use a completed January–June or full calendar-year certificate period.")
    if not isinstance(certified_on, date) or not period_end <= certified_on <= timezone.localdate():
        raise ValidationError("The original certification date must cover the period and cannot be in the future.")
    texts = {"reference": reference, "issuer": issuer, "accountant_name": accountant_name,
        "certification_authority": certification_authority, "coverage": coverage, "reason": reason}
    if any(not isinstance(value, str) or not value.strip() or len(value) > 2000 for value in texts.values()):
        raise ValidationError("Retain the source reference, issuer, original Accountant/signatory authority, complete coverage and adoption reason.")
    data = document.read(MAX_EVIDENCE_BYTES + 1)
    if not data or len(data) > MAX_EVIDENCE_BYTES or not data.startswith((b"%PDF-", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
        raise ValidationError("Attach the original PDF, PNG or JPEG certificate, no larger than 8 MiB.")
    name = PureWindowsPath(getattr(document, "name", "certificate.pdf")).name[:180]
    normalized = normalize_rows(owner.pk, rows)
    total = money(signed_total)
    if sum((money(row["amount"]) for row in normalized), Decimal("0.00")) != total:
        raise ValidationError("The explicit certificate rows must equal its signed control total.")
    scope, _ = BudgetActualScope.objects.get_or_create(department_id=owner.pk, fund=fund,
        responsibility_center=center, period_start=period_start, period_end=period_end,
        defaults={"department_label": owner.name, "budget_department_id": budget_department_id})
    scope = BudgetActualScope.objects.select_for_update().select_related("fund", "responsibility_center", "current_version").get(pk=scope.pk)
    if scope.budget_department_id != int(budget_department_id):
        raise ValidationError("This retained scope belongs to another Budget office; do not redirect its evidence.")
    latest = scope.versions.aggregate(number=Max("version"))["number"] or 0
    if latest != expected_latest:
        raise ValidationError("This actuals scope already has a newer version. Open its history before submitting a successor.")
    now = timezone.now()
    digest = hashlib.sha256(data).hexdigest()
    base = scope.current_version.version if scope.current_version_id else 0
    payload = {"schema": 1, "basis": "adopted-external-office-expenditure", "scope": scope_snapshot(scope),
        **{key: value.strip() for key, value in texts.items()}, "certified_on": certified_on.isoformat(),
        "signed_total": str(total), "rows": normalized, "evidence_sha256": digest, "evidence_name": name,
        "prepared_by": actor.pk, "prepared_by_label": (actor.get_full_name() or actor.username)[:160],
        "prepared_at": now.isoformat(), "version": latest + 1, "base_version": base}
    record = BudgetActualVersion.objects.create(department_id=owner.pk, department_label=owner.name,
        scope=scope, version=latest + 1, base_version=base, payload=payload, payload_checksum=checksum(payload),
        evidence=data, evidence_name=name, evidence_sha256=digest,
        prepared_by_id=actor.pk, prepared_by_label=payload["prepared_by_label"], prepared_at=now)
    _event(record, "budget_actual_submitted", actor)
    return record


@transaction.atomic(using="finance")
def review(record, actor, *, approve, note, authority):
    if not permitted(actor, "review"):
        raise PermissionDenied
    stored = BudgetActualVersion.objects.select_related("scope").get(pk=record.pk)
    if stored.department_id != department_for_user(actor).pk:
        raise PermissionDenied
    Fund.objects.select_for_update().get(pk=stored.scope.fund_id)
    scope = BudgetActualScope.objects.select_for_update().select_related("current_version", "fund", "responsibility_center").get(pk=stored.scope_id)
    record = BudgetActualVersion.objects.select_for_update().get(pk=stored.pk)
    record.scope = scope
    if record.status != record.SUBMITTED or record.prepared_by_id == actor.pk:
        raise ValidationError("Only an independent reviewer may decide a submitted certificate adoption.")
    if not isinstance(note, str) or not isinstance(authority, str) or not note.strip() or not authority.strip() or len(authority) > 255:
        raise ValidationError("Record the review basis and your adoption-review designation or authority.")
    payload = verify(record)
    if approve:
        if (payload["scope"] != scope_snapshot(scope) or scope.fund.department_id != scope.department_id
                or scope.responsibility_center.department_id != scope.department_id):
            raise ValidationError("The retained scope classifications changed; prepare a fresh successor.")
        if record.version != scope.versions.aggregate(number=Max("version"))["number"]:
            raise ValidationError("A newer submitted version exists; review that evidence instead.")
        if record.base_version != (scope.current_version.version if scope.current_version_id else 0):
            raise ValidationError("The adopted base version changed; submit a fresh successor.")
        if normalize_rows(record.department_id, payload["rows"]) != payload["rows"]:
            raise ValidationError("The source classifications changed; return and prepare a successor.")
    record.status = record.APPROVED if approve else record.RETURNED
    record.reviewed_by_id, record.reviewed_by_label = actor.pk, (actor.get_full_name() or actor.username)[:160]
    record.reviewed_at, record.review_note, record.review_authority = timezone.now(), note.strip(), authority.strip()
    record.decision_checksum = checksum(decision_snapshot(record))
    record._decision_write = True
    record.save(update_fields=("status", "reviewed_by_id", "reviewed_by_label", "reviewed_at",
        "review_note", "review_authority", "decision_checksum"))
    if approve:
        scope.current_version = record
        scope._decision_write = True
        scope.save(update_fields=("current_version",))
    _event(record, "budget_actual_adopted" if approve else "budget_actual_returned", actor, note)
    return record


def planning_actuals(version, keys):
    """Capture each current approved version once for this proposal's exact source groups."""
    year = version.fiscal_year.year
    periods = {(date(year-2, 1, 1), date(year-2, 12, 31)): "prior",
               (date(year-1, 1, 1), date(year-1, 6, 30)): "half"}
    result = {}
    scopes = BudgetActualScope.objects.filter(department_id=version.fiscal_year.department_id,
        budget_department_id=version.department_id, fund_id__in={key[0] for key in keys},
        responsibility_center_id__in={key[1] for key in keys},
        period_start__in={key[0] for key in periods}, current_version__isnull=False,
    ).select_related("fund", "responsibility_center", "current_version")
    for scope in scopes:
        prefix = periods.get((scope.period_start, scope.period_end))
        if not prefix:
            continue
        record = scope.current_version
        record.scope = scope
        if record.status != record.APPROVED or record.scope_id != scope.pk:
            raise ValidationError("The adopted actuals pointer does not resolve to this scope's approved evidence.")
        payload = verify(record)
        if (scope.fund.department_id != scope.department_id or scope.responsibility_center.department_id != scope.department_id
                or payload["scope"]["office_id"] != scope.responsibility_center.office_id):
            raise ValidationError("Adopted actuals no longer match the proposal's ledger and office identity.")
        for row in payload["rows"]:
            key = (scope.fund_id, scope.responsibility_center_id, row["account_id"])
            if key in keys:
                result[(key, prefix)] = {**row, "certificate": str(record.public_id), "version": record.version,
                    "reference": payload["reference"], "certified_on": payload["certified_on"],
                    "accountant_name": payload["accountant_name"], "scope": payload["scope"],
                    **{name: payload[name] for name in ("basis", "issuer", "certification_authority",
                        "coverage", "signed_total", "evidence_name")},
                    "source_checksum": record.payload_checksum, "evidence_sha256": record.evidence_sha256,
                    "decision_checksum": record.decision_checksum, "adopted_by": record.reviewed_by_label,
                    "adopted_at": record.reviewed_at.isoformat(),
                    "url": reverse("accounting:budget_actual_detail", args=(record.public_id,))}
    return result
