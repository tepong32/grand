from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse

from assistance.models import AssistanceRequest
from departments.models import Department
from social_welfare.models import ProgramActivity, SocialWelfareProgram


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: str = "text"


@dataclass
class DatasetPayload:
    rows: list[dict]
    sources: list[dict] = field(default_factory=list)
    control_totals: dict = field(default_factory=dict)
    control_status: str = "not_applicable"
    control_message: str = "This dataset does not require a Finance control-total gate."
    control_gate_required: bool = False
    freshness_at: object | None = None


class ApprovedDataset:
    key = ""
    label = ""
    columns: tuple[Column, ...] = ()
    department_slugs: tuple[str, ...] = ()

    @property
    def column_keys(self):
        return tuple(column.key for column in self.columns)

    def rows(self, department, period_start, period_end, parameters):
        raise NotImplementedError

    def payload(self, department, period_start, period_end, parameters):
        return DatasetPayload(rows=self.rows(department, period_start, period_end, parameters))

    def labels_for(self, selected_fields):
        labels = {column.key: column.label for column in self.columns}
        return [labels[key] for key in selected_fields]

    def supports_department(self, department):
        slug = (getattr(department, "slug", "") or "").strip().lower()
        return not self.department_slugs or slug in self.department_slugs


class AssistanceVolumeDataset(ApprovedDataset):
    key = "mswd_assistance_volume"
    label = "Assistance request volume and status"
    department_slugs = ("mswd",)
    columns = (
        Column("assistance_type", "Assistance type"), Column("status", "Status"),
        Column("request_count", "Requests", "integer"),
    )

    def rows(self, department, period_start, period_end, parameters):
        queryset = AssistanceRequest.objects.filter(submitted_at__date__range=(period_start, period_end))
        return list(queryset.values("assistance_type__name", "status").annotate(request_count=Count("id")).order_by("assistance_type__name", "status"))

    def normalize(self, row):
        return {"assistance_type": row["assistance_type__name"], "status": dict(AssistanceRequest.STATUS_CHOICES).get(row["status"], row["status"]), "request_count": row["request_count"]}


class ProgramAccomplishmentDataset(ApprovedDataset):
    key = "mswd_program_accomplishment"
    label = "Program and activity accomplishment"
    department_slugs = ("mswd",)
    columns = (
        Column("program_code", "Program code"), Column("program", "Program"), Column("activity", "Completed activity"),
        Column("activity_date", "Activity date", "date"), Column("venue", "Venue"), Column("attendance", "Recorded reach", "integer"),
        Column("outcome", "Outcome notes"),
    )

    def rows(self, department, period_start, period_end, parameters):
        activities = ProgramActivity.objects.filter(program__department=department, status=ProgramActivity.STATUS_COMPLETED, starts_at__date__range=(period_start, period_end)).select_related("program").order_by("starts_at")
        return [{"program_code": item.program.code, "program": item.program.name, "activity": item.title, "activity_date": item.starts_at.date(), "venue": item.venue, "attendance": item.actual_attendance or 0, "outcome": item.outcome_notes} for item in activities]


class AttendanceReachDataset(ApprovedDataset):
    key = "mswd_attendance_reach"
    label = "Attendance and aggregate beneficiary reach"
    department_slugs = ("mswd",)
    columns = (
        Column("program", "Program"), Column("completed_activities", "Completed activities", "integer"),
        Column("expected_attendance", "Expected attendance", "integer"), Column("recorded_reach", "Recorded aggregate reach", "integer"),
    )

    def rows(self, department, period_start, period_end, parameters):
        queryset = SocialWelfareProgram.objects.filter(department=department).annotate(
            completed_activities=Count("activities", filter=Q(activities__status=ProgramActivity.STATUS_COMPLETED, activities__starts_at__date__range=(period_start, period_end))),
            expected=Coalesce(Sum("activities__expected_attendance", filter=Q(activities__status=ProgramActivity.STATUS_COMPLETED, activities__starts_at__date__range=(period_start, period_end))), 0),
            reach=Coalesce(Sum("activities__actual_attendance", filter=Q(activities__status=ProgramActivity.STATUS_COMPLETED, activities__starts_at__date__range=(period_start, period_end))), 0),
        ).order_by("name")
        return [{"program": item.name, "completed_activities": item.completed_activities, "expected_attendance": item.expected, "recorded_reach": item.reach} for item in queryset if item.completed_activities]


class ActivityScheduleDataset(ApprovedDataset):
    key = "mswd_activity_schedule"
    label = "Upcoming and completed activity schedule"
    department_slugs = ("mswd",)
    columns = (
        Column("activity", "Activity"), Column("program", "Program"), Column("schedule", "Schedule", "datetime"),
        Column("venue", "Venue"), Column("status", "Status"), Column("expected_attendance", "Expected attendance", "integer"),
    )

    def rows(self, department, period_start, period_end, parameters):
        activities = ProgramActivity.objects.filter(program__department=department, starts_at__date__range=(period_start, period_end)).select_related("program").order_by("starts_at")
        statuses = dict(ProgramActivity.STATUS_CHOICES)
        return [{"activity": item.title, "program": item.program.name, "schedule": item.starts_at, "venue": item.venue, "status": statuses[item.status], "expected_attendance": item.expected_attendance} for item in activities]


class DepartmentWorkloadDataset(ApprovedDataset):
    key = "mswd_department_workload"
    label = "Department workload summary"
    department_slugs = ("mswd",)
    columns = (Column("workstream", "Workstream"), Column("awaiting_action", "Awaiting action", "integer"), Column("in_progress", "In progress", "integer"), Column("completed", "Completed", "integer"))

    def rows(self, department, period_start, period_end, parameters):
        requests = AssistanceRequest.objects.filter(submitted_at__date__range=(period_start, period_end))
        activities = ProgramActivity.objects.filter(program__department=department, starts_at__date__range=(period_start, period_end))
        return [
            {"workstream": "Assistance requests", "awaiting_action": requests.filter(status__in=("submitted", "pending")).count(), "in_progress": requests.filter(status="review").count(), "completed": requests.filter(status__in=("approved", "denied")).count()},
            {"workstream": "Programs and activities", "awaiting_action": activities.filter(status="planned").count(), "in_progress": activities.filter(status="ongoing").count(), "completed": activities.filter(status="completed").count()},
        ]


def _department_identity(department):
    return f"{getattr(department, 'slug', '') or ''} {getattr(department, 'name', '') or ''}".casefold()


def _latest_datetime(values):
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _snapshot_checksum(value):
    encoded = json.dumps(
        value, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BudgetAccountabilityDataset(ApprovedDataset):
    key = "finance_budget_accountability"
    label = "Budget accountability schedule (LBAc Form No. 2-equivalent; local confirmation pending)"
    columns = (
        Column("fiscal_year", "Fiscal year", "integer"),
        Column("authority_reference", "Appropriation authority"),
        Column("fund_code", "Fund"),
        Column("responsibility_center_code", "Office / responsibility center"),
        Column("program_code", "PPA"),
        Column("account_code", "Account"),
        Column("expense_class", "Expense class"),
        Column("particulars", "Particulars"),
        Column("appropriation", "Authorized appropriation", "decimal"),
        Column("released_allotment", "Released allotment", "decimal"),
        Column("reserve", "Reserve / withholding", "decimal"),
        Column("deferral", "Deferral", "decimal"),
        Column("executable_allotment", "Executable allotment", "decimal"),
        Column("obligation", "Obligation", "decimal"),
        Column("unreleased_appropriation", "Unreleased appropriation", "decimal"),
        Column("unobligated_allotment", "Unobligated allotment", "decimal"),
    )

    def supports_department(self, department):
        return "budget" in _department_identity(department)

    def payload(self, department, period_start, period_end, parameters):
        from budget.models import (
            AllotmentMovement, AllotmentOrderLine, AppropriationAuthorization,
            AuthorizedAppropriationLine, ObligationMovement,
        )

        lines = list(
            AuthorizedAppropriationLine.objects.filter(
                department_id=department.pk,
                authorization__status=AppropriationAuthorization.AUTHORIZED,
                authorization__effectivity_date__lte=period_end,
                authorization__version__fiscal_year__starts_on__lte=period_end,
                authorization__version__fiscal_year__ends_on__gte=period_start,
            ).select_related("authorization", "authorization__version__fiscal_year")
        )
        line_ids = [line.pk for line in lines]
        allotments = list(
            AllotmentMovement.objects.filter(
                department_id=department.pk, appropriation_line_id__in=line_ids,
                effective_date__lte=period_end,
            ).select_related("order", "appropriation_line")
        )
        obligations = list(
            ObligationMovement.objects.filter(
                department_id=department.pk, appropriation_line_id__in=line_ids,
                effective_date__lte=period_end,
            ).select_related("request", "appropriation_line")
        )
        movements_by_line = {line_id: [] for line_id in line_ids}
        obligations_by_line = {line_id: [] for line_id in line_ids}
        for movement in allotments:
            movements_by_line.setdefault(movement.appropriation_line_id, []).append(movement)
        for movement in obligations:
            obligations_by_line.setdefault(movement.appropriation_line_id, []).append(movement)

        rows, sources = [], []
        controls = {
            key: Decimal("0.00") for key in (
                "appropriation", "released_allotment", "reserve", "deferral",
                "executable_allotment", "obligation", "unreleased_appropriation",
                "unobligated_allotment",
            )
        }
        exception_rows = 0
        for line in lines:
            line_allotments = movements_by_line.get(line.pk, [])
            released = sum((item.release_effect for item in line_allotments), Decimal("0.00"))
            reserve = sum((item.hold_effect for item in line_allotments if item.movement_type in (
                AllotmentOrderLine.RESERVE, AllotmentOrderLine.RESERVE_RELEASE,
            )), Decimal("0.00"))
            deferral = sum((item.hold_effect for item in line_allotments if item.movement_type in (
                AllotmentOrderLine.DEFERRAL, AllotmentOrderLine.DEFERRAL_RELEASE,
            )), Decimal("0.00"))
            obligated = sum((item.obligation_effect for item in obligations_by_line.get(line.pk, [])), Decimal("0.00"))
            executable = released - reserve - deferral
            row = {
                "fiscal_year": line.authorization.version.fiscal_year.year,
                "authority_reference": line.authorization.ordinance_number,
                "fund_code": line.fund_code,
                "responsibility_center_code": line.responsibility_center_code,
                "program_code": line.program_code,
                "account_code": line.account_code,
                "expense_class": line.expense_class,
                "particulars": line.particulars,
                "appropriation": line.amount,
                "released_allotment": released,
                "reserve": reserve,
                "deferral": deferral,
                "executable_allotment": executable,
                "obligation": obligated,
                "unreleased_appropriation": line.amount - released,
                "unobligated_allotment": executable - obligated,
            }
            if any(row[key] < 0 for key in (
                "released_allotment", "reserve", "deferral", "executable_allotment",
                "obligation", "unreleased_appropriation", "unobligated_allotment",
            )) or released > line.amount:
                exception_rows += 1
            for key in controls:
                controls[key] += row[key]
            rows.append(row)
            sources.append({
                "source_app": "budget", "source_model": "AuthorizedAppropriationLine",
                "source_pk": str(line.pk), "source_public_id": str(line.authorization.public_id),
                "source_reference": line.authorization.ordinance_number,
                "source_date": line.authorization.effectivity_date, "control_group": "appropriation",
                "amount": line.amount, "source_checksum": line.authorization.snapshot_checksum,
                "source_url": reverse("budget:authorization_detail", kwargs={"public_id": line.authorization.public_id}),
                "snapshot": {
                    "fund": line.fund_code, "responsibility_center": line.responsibility_center_code,
                    "program": line.program_code, "account": line.account_code,
                    "particulars": line.particulars, "authority_type": line.authorization.authority_type,
                },
            })
        for movement in allotments:
            sources.append({
                "source_app": "budget", "source_model": "AllotmentMovement",
                "source_pk": str(movement.pk), "source_public_id": str(movement.order.public_id),
                "source_reference": movement.order_number_snapshot, "source_date": movement.effective_date,
                "control_group": "allotment", "amount": movement.release_effect,
                "source_checksum": movement.order.snapshot_checksum,
                "source_url": reverse("budget:allotment_detail", kwargs={"public_id": movement.order.public_id}),
                "snapshot": {
                    "movement_type": movement.movement_type, "gross_amount": str(movement.amount),
                    "release_effect": str(movement.release_effect), "hold_effect": str(movement.hold_effect),
                    "authority_reference": movement.authority_reference_snapshot,
                },
            })
        for movement in obligations:
            sources.append({
                "source_app": "budget", "source_model": "ObligationMovement",
                "source_pk": str(movement.pk), "source_public_id": str(movement.request.public_id),
                "source_reference": movement.obligation_number_snapshot, "source_date": movement.effective_date,
                "control_group": "obligation", "amount": movement.obligation_effect,
                "source_checksum": movement.request.snapshot_checksum,
                "source_url": reverse("budget:obligation_detail", kwargs={"public_id": movement.request.public_id}),
                "snapshot": {
                    "requesting_department": movement.requesting_department_snapshot,
                    "claimant_payee": movement.claimant_payee_snapshot,
                    "particulars": movement.particulars_snapshot,
                    "movement_type": movement.movement_type, "gross_amount": str(movement.amount),
                },
            })
        controls["control_exception_rows"] = exception_rows
        status = "reconciled" if lines and exception_rows == 0 else "exception"
        message = (
            "Cumulative authorized appropriation, posted allotment, holds, and certified obligation controls agree through the period end."
            if status == "reconciled"
            else "No authorized schedule lines were available, or one or more cumulative Budget controls are negative or exceed authority."
        )
        freshness = _latest_datetime(
            [line.authorization.updated_at for line in lines]
            + [item.created_at for item in allotments]
            + [item.created_at for item in obligations]
        )
        return DatasetPayload(
            rows=rows, sources=sources, control_totals=controls, control_status=status,
            control_message=message, control_gate_required=True, freshness_at=freshness,
        )


class PostedTrialBalanceDataset(ApprovedDataset):
    key = "finance_posted_trial_balance"
    label = "Posted trial balance for the covered period"
    columns = (
        Column("fund_code", "Fund"), Column("account_code", "Account code"),
        Column("account_title", "Account title"), Column("account_type", "Account type"),
        Column("debit", "Debit", "decimal"), Column("credit", "Credit", "decimal"),
        Column("net_debit", "Net debit", "decimal"), Column("net_credit", "Net credit", "decimal"),
    )

    def supports_department(self, department):
        identity = _department_identity(department)
        return any(term in identity for term in ("accounting", "acctg", "finance"))

    def payload(self, department, period_start, period_end, parameters):
        from accounting.models import JournalEntry, JournalLine

        lines = list(
            JournalLine.objects.filter(
                entry__department_id=department.pk, entry__status=JournalEntry.POSTED,
                entry__entry_date__range=(period_start, period_end),
            ).select_related("entry", "entry__fund", "account").order_by(
                "entry__fund__code", "account__code", "entry__entry_date", "entry_id", "sequence",
            )
        )
        grouped = {}
        entries = {}
        for line in lines:
            key = (line.entry.fund.code, line.account.code, line.account.title, line.account.account_type)
            row = grouped.setdefault(key, {
                "fund_code": key[0], "account_code": key[1], "account_title": key[2],
                "account_type": key[3], "debit": Decimal("0.00"), "credit": Decimal("0.00"),
            })
            row["debit"] += line.debit
            row["credit"] += line.credit
            entry = entries.setdefault(line.entry_id, {"entry": line.entry, "debit": Decimal("0.00"), "credit": Decimal("0.00")})
            entry["debit"] += line.debit
            entry["credit"] += line.credit
        rows = []
        for row in grouped.values():
            net = row["debit"] - row["credit"]
            row["net_debit"] = net if net > 0 else Decimal("0.00")
            row["net_credit"] = -net if net < 0 else Decimal("0.00")
            rows.append(row)
        total_debit = sum((row["debit"] for row in rows), Decimal("0.00"))
        total_credit = sum((row["credit"] for row in rows), Decimal("0.00"))
        difference = total_debit - total_credit
        controls = {
            "debit": total_debit, "credit": total_credit, "difference": difference,
            "posted_entry_count": len(entries), "posted_line_count": len(lines),
        }
        status = "reconciled" if difference == 0 else "exception"
        message = (
            "Posted debit and credit control totals agree exactly for the covered period."
            if status == "reconciled"
            else "Posted debit and credit totals do not agree; the report cannot advance to official review."
        )
        sources = []
        for item in entries.values():
            entry = item["entry"]
            sources.append({
                "source_app": "accounting", "source_model": "JournalEntry",
                "source_pk": str(entry.pk), "source_public_id": str(entry.public_id),
                "source_reference": entry.reference, "source_date": entry.entry_date,
                "control_group": "posted journal", "amount": item["debit"],
                "source_checksum": "",
                "source_url": reverse("accounting:entry_detail", kwargs={"public_id": entry.public_id}),
                "snapshot": {
                    "fund": entry.fund.code, "source_type": entry.source_type,
                    "source_reference": entry.source_reference or "", "description": entry.description,
                    "debit": str(item["debit"]), "credit": str(item["credit"]),
                    "posted_by": entry.posted_by_label, "posted_at": entry.posted_at.isoformat() if entry.posted_at else "",
                },
            })
        freshness = _latest_datetime([item["entry"].posted_at or item["entry"].updated_at for item in entries.values()])
        return DatasetPayload(
            rows=rows, sources=sources, control_totals=controls, control_status=status,
            control_message=message, control_gate_required=True, freshness_at=freshness,
        )


class PostedGeneralLedgerDataset(ApprovedDataset):
    key = "finance_posted_general_ledger"
    label = "Posted general ledger for the covered period"
    columns = (
        Column("entry_date", "Date", "date"), Column("jev_reference", "JEV reference"),
        Column("source_type", "Source type"), Column("source_reference", "Source reference"),
        Column("fund_code", "Fund"), Column("responsibility_center_code", "Responsibility center"),
        Column("account_code", "Account code"), Column("account_title", "Account title"),
        Column("debit", "Debit", "decimal"), Column("credit", "Credit", "decimal"),
        Column("memo", "Line memo"), Column("description", "JEV description"),
    )

    def supports_department(self, department):
        identity = _department_identity(department)
        return any(term in identity for term in ("accounting", "acctg", "finance"))

    def payload(self, department, period_start, period_end, parameters):
        from accounting.models import JournalEntry, JournalLine

        lines = list(
            JournalLine.objects.filter(
                entry__department_id=department.pk, entry__status=JournalEntry.POSTED,
                entry__entry_date__range=(period_start, period_end),
            ).select_related(
                "entry", "entry__fund", "account", "responsibility_center",
            ).order_by("entry__entry_date", "entry__reference", "sequence", "pk")
        )
        source_labels = dict(JournalEntry.SOURCE_CHOICES)
        rows = [{
            "entry_date": line.entry.entry_date,
            "jev_reference": line.entry.reference,
            "source_type": source_labels.get(line.entry.source_type, line.entry.source_type),
            "source_reference": line.entry.source_reference or "",
            "fund_code": line.entry.fund.code,
            "responsibility_center_code": line.responsibility_center.code if line.responsibility_center else "",
            "account_code": line.account.code,
            "account_title": line.account.title,
            "debit": line.debit,
            "credit": line.credit,
            "memo": line.memo,
            "description": line.entry.description,
        } for line in lines]
        entries = {}
        for line in lines:
            item = entries.setdefault(line.entry_id, {
                "entry": line.entry, "debit": Decimal("0.00"), "credit": Decimal("0.00"), "lines": [],
            })
            item["debit"] += line.debit
            item["credit"] += line.credit
            item["lines"].append({
                "sequence": line.sequence, "account": line.account.code,
                "responsibility_center": line.responsibility_center.code if line.responsibility_center else "",
                "debit": str(line.debit), "credit": str(line.credit), "memo": line.memo,
            })
        total_debit = sum((line.debit for line in lines), Decimal("0.00"))
        total_credit = sum((line.credit for line in lines), Decimal("0.00"))
        difference = total_debit - total_credit
        sources = []
        for item in entries.values():
            entry = item["entry"]
            snapshot = {
                "fund": entry.fund.code, "source_type": entry.source_type,
                "source_reference": entry.source_reference or "", "description": entry.description,
                "debit": str(item["debit"]), "credit": str(item["credit"]),
                "posted_by": entry.posted_by_label, "posted_at": entry.posted_at,
                "lines": item["lines"],
            }
            sources.append({
                "source_app": "accounting", "source_model": "JournalEntry",
                "source_pk": str(entry.pk), "source_public_id": str(entry.public_id),
                "source_reference": entry.reference, "source_date": entry.entry_date,
                "control_group": "posted general ledger", "amount": item["debit"],
                "source_checksum": _snapshot_checksum(snapshot),
                "source_url": reverse("accounting:entry_detail", kwargs={"public_id": entry.public_id}),
                "snapshot": snapshot,
            })
        controls = {
            "debit": total_debit, "credit": total_credit, "difference": difference,
            "posted_entry_count": len(entries), "posted_line_count": len(lines),
        }
        status = "reconciled" if difference == 0 else "exception"
        message = (
            "Every posted JEV in the covered period is represented and debit and credit totals agree exactly."
            if status == "reconciled"
            else "Posted general-ledger debit and credit totals do not agree; review cannot proceed."
        )
        freshness = _latest_datetime([
            item["entry"].posted_at or item["entry"].updated_at for item in entries.values()
        ])
        return DatasetPayload(
            rows=rows, sources=sources, control_totals=controls, control_status=status,
            control_message=message, control_gate_required=True, freshness_at=freshness,
        )


class PostedSubsidiaryScheduleDataset(ApprovedDataset):
    category = ""
    control_group = ""

    columns = (
        Column("fund_code", "Fund"), Column("account_code", "Control account"),
        Column("account_title", "Control account title"), Column("reference_key", "Reference key"),
        Column("reference_label", "Payee / agency"), Column("source_code", "Source code"),
        Column("debit", "Debit movements", "decimal"), Column("credit", "Credit movements", "decimal"),
        Column("balance", "Credit balance", "decimal"),
    )

    def supports_department(self, department):
        identity = _department_identity(department)
        return any(term in identity for term in ("accounting", "acctg", "finance"))

    def payload(self, department, period_start, period_end, parameters):
        from accounting.models import JournalEntry, JournalSubsidiaryLine
        from accounting.services import control_reconciliation_snapshot, subsidiary_schedule_rows

        rows = subsidiary_schedule_rows(department.pk, self.category, period_end)
        reconciliation, _checksum = control_reconciliation_snapshot(department.pk, period_end)
        control_rows = [row for row in reconciliation["rows"] if row["category"] == self.category]
        configured = self.category in reconciliation["configured_categories"]
        absolute_difference = sum(
            (abs(Decimal(row["difference"])) for row in control_rows), Decimal("0.00"),
        )
        details = list(
            JournalSubsidiaryLine.objects.filter(
                entry__department_id=department.pk, entry__status=JournalEntry.POSTED,
                entry__entry_date__lte=period_end, category=self.category,
            ).select_related(
                "entry", "entry__fund", "journal_line", "journal_line__account",
            ).order_by("entry__entry_date", "entry__reference", "journal_line__sequence")
        )
        sources = []
        for detail in details:
            snapshot = {
                "category": detail.category, "fund": detail.entry.fund.code,
                "account": detail.journal_line.account.code,
                "reference_key": detail.reference_key, "reference_label": detail.reference_label,
                "source_code": detail.source_code, "source_reference": detail.source_reference,
                "debit": str(detail.debit), "credit": str(detail.credit),
                "source_snapshot": detail.source_snapshot,
            }
            sources.append({
                "source_app": "accounting", "source_model": "JournalSubsidiaryLine",
                "source_pk": str(detail.pk), "source_public_id": str(detail.entry.public_id),
                "source_reference": detail.entry.reference, "source_date": detail.entry.entry_date,
                "control_group": self.control_group,
                "amount": detail.credit - detail.debit,
                "source_checksum": _snapshot_checksum(snapshot),
                "source_url": reverse("accounting:entry_detail", kwargs={"public_id": detail.entry.public_id}),
                "snapshot": snapshot,
            })
        total_debit = sum((row["debit"] for row in rows), Decimal("0.00"))
        total_credit = sum((row["credit"] for row in rows), Decimal("0.00"))
        total_balance = sum((row["balance"] for row in rows), Decimal("0.00"))
        gl_balance = sum((Decimal(row["gl_balance"]) for row in control_rows), Decimal("0.00"))
        controls = {
            "debit": total_debit, "credit": total_credit, "subsidiary_balance": total_balance,
            "gl_control_balance": gl_balance, "difference": gl_balance - total_balance,
            "absolute_difference": absolute_difference, "configured_mapping_count": len(control_rows),
            "source_line_count": len(details),
        }
        status = "reconciled" if configured and absolute_difference == 0 else "exception"
        if not configured:
            message = "The required payable/withholding control-account mapping is not configured."
        elif absolute_difference:
            message = "Posted subsidiary detail does not agree with its mapped general-ledger control account."
        else:
            message = "Posted subsidiary detail agrees exactly with its mapped general-ledger control account."
        freshness = _latest_datetime([
            detail.entry.posted_at or detail.entry.updated_at for detail in details
        ])
        return DatasetPayload(
            rows=rows, sources=sources, control_totals=controls, control_status=status,
            control_message=message, control_gate_required=True, freshness_at=freshness,
        )


class PostedPayableScheduleDataset(PostedSubsidiaryScheduleDataset):
    key = "finance_posted_payable_schedule"
    label = "Posted accounts-payable subsidiary schedule"
    category = "payable"
    control_group = "payable subsidiary"


class PostedWithholdingScheduleDataset(PostedSubsidiaryScheduleDataset):
    key = "finance_posted_withholding_schedule"
    label = "Posted withholding-liability schedule (working schedule; BIR form acceptance pending)"
    category = "withholding"
    control_group = "withholding subsidiary"


class BudgetVersusPostedActualDataset(ApprovedDataset):
    key = "finance_budget_vs_posted_actual"
    label = "Budget versus posted actual schedule"
    columns = (
        Column("fiscal_year", "Fiscal year", "integer"), Column("fund_code", "Fund"),
        Column("responsibility_center_code", "Office / responsibility center"),
        Column("program_code", "PPA"), Column("account_code", "Account"),
        Column("particulars", "Particulars"),
        Column("appropriation", "Authorized appropriation", "decimal"),
        Column("executable_allotment", "Executable allotment", "decimal"),
        Column("obligation", "Certified obligation", "decimal"),
        Column("posted_actual", "Posted actual expense", "decimal"),
        Column("balance_vs_actual", "Executable balance after actual", "decimal"),
        Column("actual_utilization_percent", "Actual utilization %", "decimal"),
        Column("mapping_status", "Actual mapping status"),
    )

    def supports_department(self, department):
        return "budget" in _department_identity(department)

    def payload(self, department, period_start, period_end, parameters):
        from accounting.models import JournalEntry, JournalLine

        budget_payload = BudgetAccountabilityDataset().payload(
            department, period_start, period_end, parameters,
        )
        accounting_departments = [
            item for item in Department.objects.all()
            if (
                any(term in _department_identity(item) for term in ("accounting", "acctg"))
                or (
                    "finance" in _department_identity(item)
                    and "budget" not in _department_identity(item)
                    and "treasury" not in _department_identity(item)
                )
            )
        ]
        accounting_department = accounting_departments[0] if len(accounting_departments) == 1 else None
        budget_years = sorted({row["fiscal_year"] for row in budget_payload.rows})
        actual_lines = []
        if accounting_department:
            actual_period_filter = (
                Q(entry__period__fiscal_year__in=budget_years, entry__entry_date__lte=period_end)
                if budget_years
                else Q(entry__entry_date__range=(period_start, period_end))
            )
            actual_lines = list(
                JournalLine.objects.filter(
                    actual_period_filter,
                    entry__department_id=accounting_department.pk,
                    entry__status=JournalEntry.POSTED,
                    account__account_type="expense",
                ).select_related(
                    "entry", "entry__fund", "entry__period", "account", "responsibility_center",
                ).order_by("entry__entry_date", "entry__reference", "sequence")
            )
        budget_key_counts = {}
        for row in budget_payload.rows:
            key = (
                row["fiscal_year"], row["fund_code"],
                row["responsibility_center_code"], row["account_code"],
            )
            budget_key_counts[key] = budget_key_counts.get(key, 0) + 1
        actual_by_key = {}
        for line in actual_lines:
            key = (
                line.entry.period.fiscal_year,
                line.entry.fund.code,
                line.responsibility_center.code if line.responsibility_center else "",
                line.account.code,
            )
            actual_by_key[key] = actual_by_key.get(key, Decimal("0.00")) + line.debit - line.credit
        rows = []
        mapped_keys = set()
        ambiguous_keys = set()
        for source_row in budget_payload.rows:
            row = dict(source_row)
            key = (
                row["fiscal_year"], row["fund_code"],
                row["responsibility_center_code"], row["account_code"],
            )
            actual = Decimal("0.00")
            if budget_key_counts[key] == 1:
                actual = actual_by_key.get(key, Decimal("0.00"))
                mapped_keys.add(key)
                row["mapping_status"] = "Exact fund / responsibility center / account match"
            elif key in actual_by_key:
                ambiguous_keys.add(key)
                row["mapping_status"] = "Ambiguous: more than one Budget line shares the actual key"
            else:
                row["mapping_status"] = "No posted actual activity for this Budget line"
            row["posted_actual"] = actual
            row["balance_vs_actual"] = row["executable_allotment"] - actual
            row["actual_utilization_percent"] = (
                (actual / row["executable_allotment"] * Decimal("100.00"))
                if row["executable_allotment"] else Decimal("0.00")
            )
            rows.append(row)
        unmapped_keys = set(actual_by_key) - mapped_keys - ambiguous_keys
        entry_totals = {}
        for line in actual_lines:
            item = entry_totals.setdefault(line.entry_id, {
                "entry": line.entry, "actual": Decimal("0.00"), "lines": [],
            })
            amount = line.debit - line.credit
            item["actual"] += amount
            item["lines"].append({
                "fund": line.entry.fund.code,
                "fiscal_year": line.entry.period.fiscal_year,
                "responsibility_center": line.responsibility_center.code if line.responsibility_center else "",
                "account": line.account.code, "net_expense": str(amount),
            })
        actual_sources = []
        for item in entry_totals.values():
            entry = item["entry"]
            snapshot = {
                "source_type": entry.source_type, "source_reference": entry.source_reference or "",
                "description": entry.description, "posted_actual": str(item["actual"]),
                "posted_by": entry.posted_by_label, "posted_at": entry.posted_at,
                "expense_lines": item["lines"],
            }
            actual_sources.append({
                "source_app": "accounting", "source_model": "JournalEntry",
                "source_pk": str(entry.pk), "source_public_id": str(entry.public_id),
                "source_reference": entry.reference, "source_date": entry.entry_date,
                "control_group": "posted actual expense", "amount": item["actual"],
                "source_checksum": _snapshot_checksum(snapshot),
                "source_url": reverse("accounting:entry_detail", kwargs={"public_id": entry.public_id}),
                "snapshot": snapshot,
            })
        actual_total = sum(actual_by_key.values(), Decimal("0.00"))
        mapped_total = sum((actual_by_key[key] for key in mapped_keys), Decimal("0.00"))
        ambiguous_total = sum((actual_by_key[key] for key in ambiguous_keys), Decimal("0.00"))
        unmapped_total = sum((actual_by_key[key] for key in unmapped_keys), Decimal("0.00"))
        mapping_exception_count = len(ambiguous_keys) + len(unmapped_keys)
        if not accounting_department:
            mapping_exception_count += 1
        controls = dict(budget_payload.control_totals)
        controls.update({
            "posted_actual": actual_total, "mapped_actual": mapped_total,
            "ambiguous_actual": ambiguous_total, "unmapped_actual": unmapped_total,
            "mapping_exception_count": mapping_exception_count,
            "accounting_department_count": len(accounting_departments),
            "actual_basis": "fiscal-year-to-date posted expense through the selected period end",
        })
        status = (
            "reconciled"
            if budget_payload.control_status == "reconciled" and mapping_exception_count == 0
            else "exception"
        )
        if not accounting_department:
            message = "Exactly one Accounting department is required before posted actuals can be mapped."
        elif mapping_exception_count:
            message = "One or more posted expense keys are unmatched or ambiguous; no amount was silently allocated."
        elif budget_payload.control_status != "reconciled":
            message = budget_payload.control_message
        else:
            message = "Budget authority and posted actual expenses reconcile through exact fund, responsibility-center, and account keys."
        freshness = _latest_datetime(
            [budget_payload.freshness_at]
            + [item["entry"].posted_at or item["entry"].updated_at for item in entry_totals.values()]
        )
        return DatasetPayload(
            rows=rows, sources=budget_payload.sources + actual_sources,
            control_totals=controls, control_status=status, control_message=message,
            control_gate_required=True, freshness_at=freshness,
        )


class PaymentInstrumentRegisterDataset(ApprovedDataset):
    key = "finance_payment_instrument_register"
    label = "Payment instrument and disbursement register"
    columns = (
        Column("case_reference", "Case reference"), Column("dv_number", "DV number"),
        Column("voucher_date", "Voucher date", "date"), Column("payee", "Payee"),
        Column("fund_code", "Fund"), Column("bank_account_code", "Bank account code"),
        Column("check_number", "Check / instrument number"), Column("amount", "Amount", "decimal"),
        Column("status", "Instrument status"), Column("operational_status", "Exception status"),
        Column("issued_at", "Issued at", "datetime"), Column("advice_number", "Current advice"),
        Column("advice_status", "Advice status"), Column("released_at", "Released at", "datetime"),
        Column("released_to", "Released to"), Column("receipt_reference", "Receipt reference"),
        Column("cancelled_at", "Cancelled at", "datetime"), Column("cancellation_reason", "Cancellation reason"),
        Column("replacement_number", "Replacement number"),
    )

    def supports_department(self, department):
        return "treasury" in _department_identity(department)

    def payload(self, department, period_start, period_end, parameters):
        from vouchers.models import PaymentInstrument

        instruments = list(
            PaymentInstrument.objects.filter(
                Q(issued_at__date__range=(period_start, period_end))
                | Q(released_at__date__range=(period_start, period_end))
                | Q(cancelled_at__date__range=(period_start, period_end))
            ).select_related(
                "case", "case__disbursement_voucher", "current_advice_batch",
            ).order_by("issued_at", "bank_account_code", "check_number", "pk").distinct()
        )
        replacements = {
            item.replaces_id: item.check_number
            for item in PaymentInstrument.objects.filter(
                replaces_id__in=[instrument.pk for instrument in instruments],
            ).only("replaces_id", "check_number")
        }
        statuses = dict(PaymentInstrument.STATUS_CHOICES)
        operational_statuses = dict(PaymentInstrument.OPERATIONAL_STATUS_CHOICES)
        rows, sources = [], []
        exception_count = 0
        issued_amount = released_amount = cancelled_amount = Decimal("0.00")
        for instrument in instruments:
            voucher = getattr(instrument.case, "disbursement_voucher", None)
            advice = instrument.current_advice_batch
            row_exceptions = []
            if voucher is None:
                row_exceptions.append("missing disbursement voucher")
            if instrument.status == PaymentInstrument.DRAFT:
                row_exceptions.append("draft instrument has reportable activity evidence")
            if not instrument.issued_at or not instrument.issued_by_id:
                row_exceptions.append("missing issue evidence")
            if not instrument.fund_code or not instrument.bank_account_code or not instrument.check_number:
                row_exceptions.append("incomplete instrument identity")
            if instrument.status == PaymentInstrument.RELEASED and (
                not instrument.released_at or not instrument.released_by_id
                or not instrument.receipt_reference.strip()
                or not (instrument.released_to.strip() or instrument.released_to_claimant_id)
            ):
                row_exceptions.append("incomplete release evidence")
            if instrument.status == PaymentInstrument.CANCELLED and (
                not instrument.cancelled_at or not instrument.cancelled_by_id
                or not instrument.cancellation_reason.strip()
            ):
                row_exceptions.append("incomplete cancellation evidence")
            if instrument.status in (PaymentInstrument.ADVISED, PaymentInstrument.RELEASED) and not advice:
                row_exceptions.append("missing retained advice link")
            if (
                instrument.status in (PaymentInstrument.ADVISED, PaymentInstrument.RELEASED)
                and advice
                and advice.status not in (advice.ACKNOWLEDGED, advice.FINALIZED)
            ):
                row_exceptions.append("current advice is not bank-acknowledged")
            exception_count += len(row_exceptions)
            if instrument.issued_at and period_start <= instrument.issued_at.date() <= period_end:
                issued_amount += instrument.amount
            if instrument.released_at and period_start <= instrument.released_at.date() <= period_end:
                released_amount += instrument.amount
            if instrument.cancelled_at and period_start <= instrument.cancelled_at.date() <= period_end:
                cancelled_amount += instrument.amount
            row = {
                "case_reference": instrument.case.reference_code,
                "dv_number": voucher.dv_number if voucher else "",
                "voucher_date": voucher.voucher_date if voucher else None,
                "payee": instrument.case.payee_name,
                "fund_code": instrument.fund_code, "bank_account_code": instrument.bank_account_code,
                "check_number": instrument.check_number, "amount": instrument.amount,
                "status": statuses.get(instrument.status, instrument.status),
                "operational_status": operational_statuses.get(
                    instrument.operational_status, instrument.operational_status,
                ),
                "issued_at": instrument.issued_at,
                "advice_number": advice.advice_number if advice else "",
                "advice_status": advice.get_status_display() if advice else "",
                "released_at": instrument.released_at, "released_to": instrument.released_to,
                "receipt_reference": instrument.receipt_reference,
                "cancelled_at": instrument.cancelled_at,
                "cancellation_reason": instrument.cancellation_reason,
                "replacement_number": replacements.get(instrument.pk, ""),
            }
            rows.append(row)
            snapshot = dict(row)
            snapshot.update({
                "public_id": str(instrument.public_id), "case_public_id": str(instrument.case.public_id),
                "exceptions": row_exceptions,
            })
            sources.append({
                "source_app": "vouchers", "source_model": "PaymentInstrument",
                "source_pk": str(instrument.pk), "source_public_id": str(instrument.public_id),
                "source_reference": instrument.check_number,
                "source_date": instrument.issued_at.date() if instrument.issued_at else None,
                "control_group": "payment instrument", "amount": instrument.amount,
                "source_checksum": _snapshot_checksum(snapshot),
                "source_url": reverse("vouchers:case_detail", kwargs={"public_id": instrument.case.public_id}),
                "snapshot": snapshot,
            })
        controls = {
            "instrument_count": len(instruments), "issued_amount": issued_amount,
            "released_amount": released_amount, "cancelled_amount": cancelled_amount,
            "evidence_exception_count": exception_count,
        }
        status = "reconciled" if exception_count == 0 else "exception"
        message = (
            "Every included instrument has complete issue and applicable advice, release, or cancellation evidence."
            if status == "reconciled"
            else "One or more included instruments have incomplete retained control evidence."
        )
        freshness = _latest_datetime([
            max(filter(None, (item.issued_at, item.released_at, item.cancelled_at)), default=None)
            for item in instruments
        ])
        return DatasetPayload(
            rows=rows, sources=sources, control_totals=controls, control_status=status,
            control_message=message, control_gate_required=True, freshness_at=freshness,
        )


DATASETS = (
    AssistanceVolumeDataset(), ProgramAccomplishmentDataset(), AttendanceReachDataset(),
    ActivityScheduleDataset(), DepartmentWorkloadDataset(), BudgetAccountabilityDataset(),
    PostedTrialBalanceDataset(), PostedGeneralLedgerDataset(), PostedPayableScheduleDataset(),
    PostedWithholdingScheduleDataset(), BudgetVersusPostedActualDataset(),
    PaymentInstrumentRegisterDataset(),
)
dataset_registry = {dataset.key: dataset for dataset in DATASETS}


def available_datasets(department):
    return tuple(dataset for dataset in DATASETS if dataset.supports_department(department))


def _build_dataset(definition, period_start, period_end, parameters):
    snapshot = (parameters or {}).get("_definition_snapshot", {})
    adapter = dataset_registry[snapshot.get("dataset_key", definition.dataset_key)]
    if not adapter.supports_department(definition.department):
        raise ValueError("This approved dataset is not available to the report's department.")
    payload = adapter.payload(definition.department, period_start, period_end, parameters)
    rows = payload.rows
    if hasattr(adapter, "normalize"):
        rows = [adapter.normalize(row) for row in rows]
    configured_filters = snapshot.get("filters", definition.filters or {})
    configured_group_by = snapshot.get("group_by", definition.group_by or [])
    configured_totals = snapshot.get("totals", definition.totals or [])
    configured_sort = snapshot.get("sort_by", definition.sort_by or [])
    selected = snapshot.get("selected_fields", definition.selected_fields)
    for filter_key, expected in configured_filters.items():
        field, _, operator = filter_key.partition("__")
        operator = operator or "exact"
        def matches(row):
            actual = row.get(field)
            if operator == "contains":
                return str(expected).casefold() in str(actual or "").casefold()
            if operator == "in":
                return actual in expected or str(actual) in {str(item) for item in expected}
            return str(actual).casefold() == str(expected).casefold()
        rows = [row for row in rows if matches(row)]
    if configured_group_by:
        grouped = {}
        for row in rows:
            bucket_key = tuple(row.get(key) for key in configured_group_by)
            bucket = grouped.setdefault(bucket_key, {key: row.get(key) for key in configured_group_by})
            for total_key in configured_totals:
                bucket[total_key] = (bucket.get(total_key) or 0) + (row.get(total_key) or 0)
        rows = list(grouped.values())
    rows = [{key: row.get(key, "") for key in selected} for row in rows]
    for sort_key in reversed(configured_sort):
        reverse = sort_key.startswith("-")
        key = sort_key.lstrip("-")
        rows.sort(key=lambda row: (row.get(key) is None, str(row.get(key, ""))), reverse=reverse)
    totals = {key: sum((row.get(key) or 0) for row in rows if isinstance(row.get(key), (int, float))) for key in configured_totals}
    for key in configured_totals:
        if key not in totals or totals[key] == 0:
            totals[key] = sum((row.get(key) or 0 for row in rows if isinstance(row.get(key), Decimal)), Decimal("0.00"))
    evidence = {
        "sources": payload.sources,
        "control_totals": payload.control_totals,
        "control_status": payload.control_status,
        "control_message": payload.control_message,
        "control_gate_required": payload.control_gate_required,
        "freshness_at": payload.freshness_at,
    }
    return adapter, rows, totals, evidence


def build_dataset(definition, period_start, period_end, parameters):
    adapter, rows, totals, _evidence = _build_dataset(definition, period_start, period_end, parameters)
    return adapter, rows, totals


def build_dataset_with_evidence(definition, period_start, period_end, parameters):
    return _build_dataset(definition, period_start, period_end, parameters)
