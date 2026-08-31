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

FINANCE_PRESETS = {
    "budget": (
        {
            "name": "Quarterly Budget Accountability Schedule",
            "slug": "quarterly-budget-accountability",
            "dataset_key": "finance_budget_accountability",
            "description": (
                "Cumulative authorized appropriation, allotment, reserve/deferral, obligation, and "
                "remaining-balance controls through the selected period end. This starter is an "
                "LBAc Form No. 2-equivalent working layout, not an accepted official form until local confirmation."
            ),
            "fields": [
                "fiscal_year", "fund_code", "responsibility_center_code", "program_code",
                "account_code", "particulars", "appropriation", "released_allotment",
                "executable_allotment", "obligation", "unobligated_allotment",
            ],
            "totals": [
                "appropriation", "released_allotment", "executable_allotment",
                "obligation", "unobligated_allotment",
            ],
            "authority_reference": (
                "DBM Budget Operations Manual for Local Government Units: quarterly financial "
                "operations/accountability reporting guidance; exact current local form and routing remain to be confirmed."
            ),
            "header": "Municipal Budget Office",
            "prefix": "BUD-ACCTY",
            "signatories": [
                {"role": "Prepared by", "name": "Budget accountability report preparer"},
                {"role": "Reviewed by", "name": "Budget Officer / authorized reviewer"},
            ],
        },
    ),
    "accounting": (
        {
            "name": "Posted Trial Balance",
            "slug": "posted-trial-balance",
            "dataset_key": "finance_posted_trial_balance",
            "description": (
                "Posted journal debit and credit balances for the covered period, with exact balance "
                "control and source-JEV drill-through. The native layout is a controlled starter pending local form acceptance."
            ),
            "fields": [
                "fund_code", "account_code", "account_title", "account_type",
                "debit", "credit", "net_debit", "net_credit",
            ],
            "totals": ["debit", "credit", "net_debit", "net_credit"],
            "authority_reference": (
                "COA Government Accounting Manual, trial-balance and financial-statement preparation guidance; "
                "exact current LGU schedule, signatories, and submission route remain to be confirmed."
            ),
            "header": "Municipal Accounting Office",
            "prefix": "ACCTG-TB",
            "signatories": [
                {"role": "Prepared by", "name": "Accounting report preparer"},
                {"role": "Reviewed by", "name": "Municipal Accountant / authorized reviewer"},
            ],
        },
    ),
}


def _department_kind(department):
    identity = f"{department.slug or ''} {department.name or ''}".casefold()
    if "budget" in identity:
        return "budget"
    if any(term in identity for term in ("accounting", "acctg", "finance")):
        return "accounting"
    return ""


def _accountable_actor(department, actor=None):
    return actor or department.deptHead_or_oic or get_user_model().objects.filter(is_superuser=True).first()


def _seed_presets(department, presets, actor):
    results = []
    for preset in presets:
        definition, was_created = ReportDefinition.objects.get_or_create(
            department=department,
            slug=preset["slug"],
            defaults={
                "name": preset["name"], "description": preset["description"],
                "dataset_key": preset["dataset_key"], "selected_fields": preset["fields"],
                "totals": preset["totals"], "sort_by": [],
                "default_format": ReportDefinition.FORMAT_XLSX,
                "applicability_status": ReportDefinition.APPLICABILITY_CANDIDATE,
                "authority_reference": preset["authority_reference"],
                "created_by": actor, "updated_by": actor,
            },
        )
        if was_created:
            definition.full_clean()
            definition.save()
        template, template_created = ReportTemplateVersion.objects.get_or_create(
            definition=definition,
            version=1,
            defaults={
                "title": preset["name"], "header_text": preset["header"],
                "certification_text": (
                    "We certify that this controlled GRAND output agrees with its retained data and control "
                    "snapshots. Local applicability and exact official-form acceptance remain separately reviewable."
                ),
                "footer_text": "GRAND controlled Finance starter — local official-form acceptance pending",
                "document_control_prefix": preset["prefix"], "signatories": preset["signatories"],
                "layout_config": {
                    "source": "native", "dataset": preset["dataset_key"],
                    "starter_boundary": "human-editable controlled starter; not an automatically accepted official form",
                },
                "created_by": actor, "approved_by": actor, "approved_at": timezone.now(),
            },
        )
        results.append((definition, was_created or template_created))
    return results


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


def seed_finance_presets(actor=None):
    results = []
    for department in Department.objects.all().order_by("pk"):
        kind = _department_kind(department)
        presets = FINANCE_PRESETS.get(kind, ())
        accountable_actor = _accountable_actor(department, actor) if presets else None
        if presets and accountable_actor:
            results.extend(_seed_presets(department, presets, accountable_actor))
    return results


def seed_reporting_presets(actor=None):
    return {
        "mswd": seed_mswd_presets(actor),
        "finance": seed_finance_presets(actor),
    }
