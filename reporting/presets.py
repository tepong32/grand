from django.contrib.auth import get_user_model
from django.utils import timezone

from departments.models import Department

from .datasets import dataset_registry
from .models import ReportDefinition, ReportTemplateVersion


MSWD_PRESETS = (
    {"name": "Assistance Request Volume and Status", "slug": "assistance-volume-status", "dataset_key": "mswd_assistance_volume", "description": "Request volume grouped by assistance type and workflow status for the covered period.", "fields": ["assistance_type", "status", "request_count"], "totals": ["request_count"]},
    {"name": "Program and Activity Accomplishment Report", "slug": "program-activity-accomplishment", "dataset_key": "mswd_program_accomplishment", "description": "Completed social welfare activities, recorded aggregate reach, venues, and outcome notes.", "fields": ["program_code", "program", "activity", "activity_date", "venue", "attendance", "outcome"], "totals": ["attendance"]},
    {"name": "Attendance and Aggregate Beneficiary Reach", "slug": "attendance-beneficiary-reach", "dataset_key": "mswd_attendance_reach", "description": "Aggregate attendance only; this report does not infer named beneficiaries from headcounts.", "fields": ["program", "completed_activities", "expected_attendance", "recorded_reach"], "totals": ["completed_activities", "expected_attendance", "recorded_reach"]},
    {"name": "Upcoming and Completed Activity Schedule", "slug": "activity-schedule", "dataset_key": "mswd_activity_schedule", "description": "Department activity calendar for coordination and accomplishment reporting.", "fields": ["activity", "program", "schedule", "venue", "status", "expected_attendance"], "totals": ["expected_attendance"]},
    {"name": "Department Workload Summary", "slug": "department-workload", "dataset_key": "mswd_department_workload", "description": "A factual summary of assistance and program work awaiting action, in progress, and completed.", "fields": ["workstream", "awaiting_action", "in_progress", "completed"], "totals": ["awaiting_action", "in_progress", "completed"]},
)


def seed_mswd_presets(actor=None):
    department = Department.objects.filter(slug__iexact="mswd").first()
    if not department:
        return []
    actor = actor or department.deptHead_or_oic or get_user_model().objects.filter(is_superuser=True).first()
    if not actor:
        return []
    created = []
    for preset in MSWD_PRESETS:
        definition, was_created = ReportDefinition.objects.get_or_create(
            department=department,
            slug=preset["slug"],
            defaults={"name": preset["name"], "description": preset["description"], "dataset_key": preset["dataset_key"], "selected_fields": preset["fields"], "totals": preset["totals"], "sort_by": [], "default_format": ReportDefinition.FORMAT_PDF, "created_by": actor, "updated_by": actor},
        )
        if was_created:
            definition.full_clean()
            definition.save()
        template, template_created = ReportTemplateVersion.objects.get_or_create(
            definition=definition,
            version=1,
            defaults={"title": preset["name"], "header_text": f"Municipal Social Welfare and Development Office", "certification_text": "We certify that this report was generated from the approved GRAND dataset for the covered period and reviewed through the official reporting workflow.", "footer_text": "GRAND controlled departmental output", "document_control_prefix": "MSWD-RPT", "signatories": [{"role": "Prepared by", "name": "Department reporting officer"}, {"role": "Reviewed by", "name": "MSWD Head / OIC"}], "layout_config": {"source": "native", "dataset": preset["dataset_key"]}, "created_by": actor, "approved_by": actor, "approved_at": timezone.now()},
        )
        created.append((definition, was_created or template_created))
    return created
