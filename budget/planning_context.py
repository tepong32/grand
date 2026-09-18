"""Dated proposal context, without pretending expense activity is certified expenditure."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine
from .access import department_for_user, has_budget_permission
from .models import AuthorizedAppropriationLine, AppropriationAuthorization, BudgetProposalLine, BudgetVersion


def can_read_context(user, version):
    office = department_for_user(user)
    return bool(office and office.pk == version.department_id and any(
        has_budget_permission(user, code) for code in
        ("prepare_budget_proposals", "review_budget_proposals", "view_budget_audit")
    ))


def displayed_context(version, user):
    if not can_read_context(user, version):
        raise PermissionDenied
    if version.status in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
        return build_context(version, user)
    return version.planning_context_snapshot or None


def build_context(version, user):
    if not can_read_context(user, version):
        raise PermissionDenied
    today = timezone.localdate()
    year = version.fiscal_year.year
    if year < 3:
        raise ValidationError("Historical planning context requires a valid comparison year.")
    groups = {}
    for line in version.lines.select_related("fund", "responsibility_center", "account", "program"):
        if any(item.department_id != version.fiscal_year.department_id for item in
               (line.fund, line.responsibility_center, line.account)):
            raise ValidationError("Proposal classifications no longer belong to the selected Finance ledger.")
        key = (line.fund_id, line.responsibility_center_id, line.account_id)
        row = groups.setdefault(key, {"fund": line.fund.code, "office": line.responsibility_center.code,
            "account": line.account.code, "account_title": line.account.title,
            "supports_expense_activity": line.account.account_type == "expense", "lines": [],
            "proposed": Decimal("0"), "estimate": Decimal("0"), "estimate_complete": True,
            "prior_sources": [], "half_sources": [], "excluded_sources": [], "authorities": []})
        row["proposed"] += line.amount
        row["estimate_complete"] &= line.second_half_estimate is not None
        row["estimate"] += line.second_half_estimate or Decimal("0")
        row["lines"].append({"id": line.pk, "program": line.program.code if line.program else "",
            "particulars": line.particulars, "proposed": str(line.amount),
            "estimate": str(line.second_half_estimate) if line.second_half_estimate is not None else None,
            "estimate_as_of": line.estimate_as_of.isoformat() if line.estimate_as_of else "",
            "estimate_basis": line.estimate_basis})
    if not groups:
        return {"schema": 1, "as_of": today.isoformat(), "budget_year": year,
                "prior_year": year-2, "current_year": year-1, "rows": [],
                "prior_period_complete": today >= date(year-2, 12, 31),
                "half_period_complete": today >= date(year-1, 6, 30)}
    ledger = version.fiscal_year.department_id
    activity = JournalLine.objects.filter(entry__department_id=ledger, entry__status=JournalEntry.POSTED,
        entry__entry_date__range=(date(year-2, 1, 1), min(date(year-1, 6, 30), today)),
        entry__fund_id__in={key[0] for key in groups}, responsibility_center_id__in={key[1] for key in groups},
        account_id__in={key[2] for key in groups}, account__account_type="expense",
    ).select_related("entry", "entry__reversal_of").order_by("entry__entry_date", "entry_id", "sequence")
    for line in activity:
        key = (line.entry.fund_id, line.responsibility_center_id, line.account_id)
        if key not in groups:
            continue
        row = groups[key]
        origin = line.entry.statement_source_type
        source = {"journal": str(line.entry.public_id), "reference": line.entry.reference,
            "line": line.pk, "date": line.entry.entry_date.isoformat(),
            "net_expense": str(line.debit-line.credit)}
        if origin in {JournalEntry.CLOSING, "opening", *JournalEntry.DIRECT_EQUITY_SOURCES}:
            row["excluded_sources"].append(source)
            continue
        bucket = "prior_sources" if line.entry.entry_date.year == year-2 else "half_sources"
        row[bucket].append(source)
    by_codes = {(row["fund"], row["office"], row["account"]): row for row in groups.values()}
    authority_lines = AuthorizedAppropriationLine.objects.filter(
        department_id=version.department_id, authorization__status=AppropriationAuthorization.AUTHORIZED,
        authorization__department_id=version.department_id,
        authorization__version__fiscal_year__year=year-1,
        authorization__version__fiscal_year__department_id=ledger,
        authorization__effectivity_date__lte=today,
        fund_code__in={key[0] for key in by_codes},
        responsibility_center_code__in={key[1] for key in by_codes},
        account_code__in={key[2] for key in by_codes},
    ).exclude(authorization__snapshot_checksum="").select_related("authorization__version")
    for line in authority_lines:
        row = by_codes.get((line.fund_code, line.responsibility_center_code, line.account_code))
        if row is not None:
            authority = line.authorization
            row["authorities"].append({"id": str(authority.public_id), "reference": authority.ordinance_number,
                "date": authority.effectivity_date.isoformat(), "kind": authority.version.kind,
                "successor": bool(authority.version.supersedes_id), "line": line.pk,
                "amount": str(line.amount), "checksum": authority.snapshot_checksum})
    rows = []
    for key, row in sorted(groups.items()):
        for prefix in ("prior", "half"):
            sources = row[prefix + "_sources"]
            row[prefix + "_amount"] = str(sum((Decimal(s["net_expense"]) for s in sources), Decimal("0"))) if sources else None
        originals = [item for item in row["authorities"] if item["kind"] == BudgetVersion.FINAL and not item["successor"]]
        ids = {item["id"] for item in originals}
        row["original_authority"] = str(sum((Decimal(item["amount"]) for item in originals), Decimal("0"))) if len(ids) == 1 else None
        row["authority_state"] = "Original authorized schedule" if len(ids) == 1 else (
            "Multiple original authorities: review sources" if ids else "No original authorized schedule located")
        row["proposed"] = str(row["proposed"])
        row["estimate"] = str(row["estimate"]) if row["estimate_complete"] else None
        row["indicative_total"] = str(Decimal(row["half_amount"])+Decimal(row["estimate"])) if (
            row["half_amount"] is not None and row["estimate"] is not None and today >= date(year-1, 6, 30)
        ) else None
        rows.append(row)
    return {"schema": 1, "as_of": today.isoformat(), "budget_year": year,
        "prior_year": year-2, "current_year": year-1, "rows": rows,
        "prior_period_complete": today >= date(year-2, 12, 31),
        "half_period_complete": today >= date(year-1, 6, 30)}


@transaction.atomic(using="finance")
def set_estimate(*, version, line_id, actor, amount, as_of, basis):
    from .services import _require_action, record_event
    version = BudgetVersion.objects.select_for_update().get(pk=version.pk)
    _require_action(actor, version, "prepare_budget_proposals")
    if version.status not in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
        raise ValidationError("Return the proposal before changing its planning estimate.")
    line = BudgetProposalLine.objects.select_for_update().get(pk=line_id, version=version)
    before = {"amount": str(line.second_half_estimate), "as_of": str(line.estimate_as_of), "basis": line.estimate_basis}
    line.second_half_estimate, line.estimate_as_of, line.estimate_basis = amount, as_of, basis.strip()
    line.full_clean()
    line.save(update_fields=("second_half_estimate", "estimate_as_of", "estimate_basis"))
    record_event(version, "planning_estimate_changed", actor, snapshot={"line": line.pk, "before": before,
        "after": {"amount": str(amount), "as_of": str(as_of), "basis": line.estimate_basis}})
    return line
