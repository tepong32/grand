from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse

from assistance.models import AssistanceRequest
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


DATASETS = (
    AssistanceVolumeDataset(), ProgramAccomplishmentDataset(), AttendanceReachDataset(),
    ActivityScheduleDataset(), DepartmentWorkloadDataset(), BudgetAccountabilityDataset(),
    PostedTrialBalanceDataset(),
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
