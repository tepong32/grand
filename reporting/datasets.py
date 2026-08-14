from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from assistance.models import AssistanceRequest
from social_welfare.models import ProgramActivity, SocialWelfareProgram


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: str = "text"


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


DATASETS = (AssistanceVolumeDataset(), ProgramAccomplishmentDataset(), AttendanceReachDataset(), ActivityScheduleDataset(), DepartmentWorkloadDataset())
dataset_registry = {dataset.key: dataset for dataset in DATASETS}


def available_datasets(department):
    return tuple(dataset for dataset in DATASETS if dataset.supports_department(department))


def build_dataset(definition, period_start, period_end, parameters):
    adapter = dataset_registry[definition.dataset_key]
    if not adapter.supports_department(definition.department):
        raise ValueError("This approved dataset is not available to the report's department.")
    rows = adapter.rows(definition.department, period_start, period_end, parameters)
    if hasattr(adapter, "normalize"):
        rows = [adapter.normalize(row) for row in rows]
    snapshot = (parameters or {}).get("_definition_snapshot", {})
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
    return adapter, rows, totals
