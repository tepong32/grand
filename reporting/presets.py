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
        {
            "name": "Budget versus Posted Actual Schedule",
            "slug": "budget-versus-posted-actual",
            "dataset_key": "finance_budget_vs_posted_actual",
            "description": (
                "Authorized appropriation, executable allotment, certified obligation, and posted "
                "Accounting expense compared only through exact fiscal-year, fund, responsibility-center, and account keys. "
                "Unmatched or ambiguous actuals remain visible control exceptions."
            ),
            "fields": [
                "fiscal_year", "fund_code", "responsibility_center_code", "program_code",
                "account_code", "particulars", "appropriation", "executable_allotment",
                "obligation", "posted_actual", "balance_vs_actual", "actual_utilization_percent",
                "mapping_status",
            ],
            "totals": [
                "appropriation", "executable_allotment", "obligation", "posted_actual",
                "balance_vs_actual",
            ],
            "authority_reference": (
                "DBM/COA budget-accountability and posted-expenditure comparison guidance; exact local "
                "schedule, classification bridge, signatories, and routing remain to be confirmed."
            ),
            "header": "Municipal Budget Office",
            "prefix": "BUD-ACTUAL",
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
        {
            "name": "Posted General Ledger",
            "slug": "posted-general-ledger",
            "dataset_key": "finance_posted_general_ledger",
            "description": (
                "Line-level posted JEV register for the covered period with fund, responsibility center, "
                "account, source, debit/credit control, and source-entry drill-through."
            ),
            "fields": [
                "entry_date", "jev_reference", "source_type", "source_reference", "fund_code",
                "responsibility_center_code", "account_code", "account_title", "debit", "credit",
                "memo", "description",
            ],
            "totals": ["debit", "credit"],
            "authority_reference": (
                "COA Government Accounting Manual general-ledger and journal reporting guidance; exact "
                "current local layout, pagination, signatories, and submission route remain to be confirmed."
            ),
            "header": "Municipal Accounting Office",
            "prefix": "ACCTG-GL",
            "signatories": [
                {"role": "Prepared by", "name": "Accounting report preparer"},
                {"role": "Reviewed by", "name": "Municipal Accountant / authorized reviewer"},
            ],
        },
        {
            "name": "Posted Accounts Payable Subsidiary Schedule",
            "slug": "posted-payable-subsidiary",
            "dataset_key": "finance_posted_payable_schedule",
            "description": (
                "Payee-level posted payable balances through the selected end date, controlled to the "
                "mapped general-ledger payable accounts by fund."
            ),
            "fields": [
                "fund_code", "account_code", "account_title", "reference_key",
                "reference_label", "source_code", "debit", "credit", "balance",
            ],
            "totals": ["debit", "credit", "balance"],
            "authority_reference": (
                "COA Government Accounting Manual subsidiary-ledger/control-account guidance; exact local "
                "schedule, ageing treatment, signatories, and routing remain to be confirmed."
            ),
            "header": "Municipal Accounting Office",
            "prefix": "ACCTG-AP",
            "signatories": [
                {"role": "Prepared by", "name": "Accounting subsidiary-ledger preparer"},
                {"role": "Reviewed by", "name": "Municipal Accountant / authorized reviewer"},
            ],
        },
        {
            "name": "Posted Withholding Liability Schedule",
            "slug": "posted-withholding-liability",
            "dataset_key": "finance_posted_withholding_schedule",
            "description": (
                "Agency/deduction-level posted withholding balances through the selected end date, controlled "
                "to mapped general-ledger liability accounts. This is not a BIR return or attachment."
            ),
            "fields": [
                "fund_code", "account_code", "account_title", "reference_key",
                "reference_label", "source_code", "debit", "credit", "balance",
            ],
            "totals": ["debit", "credit", "balance"],
            "authority_reference": (
                "COA subsidiary-liability guidance and locally applicable BIR withholding requirements; "
                "current tax classification, return/attachment, deadline, signatory, and filing acceptance remain open."
            ),
            "header": "Municipal Accounting Office",
            "prefix": "ACCTG-WHT",
            "signatories": [
                {"role": "Prepared by", "name": "Accounting withholding-schedule preparer"},
                {"role": "Reviewed by", "name": "Municipal Accountant / authorized reviewer"},
            ],
        },
        {
            "name": "Management Statement of Financial Position",
            "slug": "management-statement-financial-position",
            "dataset_key": "finance_statement_position",
            "description": (
                "Posted as-of balances composed through a versioned statement mapping, with exact account "
                "coverage and the visible equation Assets = Liabilities + Equity + unclosed operating result."
            ),
            "fields": [
                "section_title", "line_code", "line_title", "amount",
                "source_account_count", "mapping_basis",
            ],
            "totals": [],
            "authority_reference": (
                "COA Government Accounting Manual financial-statement preparation guidance; the broad GRAND "
                "starter remains a management comparison until the current signed local statement and account mapping are accepted."
            ),
            "header": "Municipal Accounting Office",
            "prefix": "ACCTG-SFP",
            "signatories": [
                {"role": "Prepared by", "name": "Accounting statement preparer"},
                {"role": "Reviewed by", "name": "Municipal Accountant / authorized reviewer"},
            ],
        },
        {
            "name": "Management Statement of Financial Performance",
            "slug": "management-statement-financial-performance",
            "dataset_key": "finance_statement_performance",
            "description": (
                "Posted revenue, expense, and derived surplus or deficit for the covered period, composed "
                "through a versioned mapping with exact non-zero account coverage."
            ),
            "fields": [
                "section_title", "line_code", "line_title", "amount",
                "source_account_count", "mapping_basis",
            ],
            "totals": [],
            "authority_reference": (
                "COA Government Accounting Manual financial-performance guidance; the broad GRAND starter "
                "remains a management comparison until the current signed local statement and account mapping are accepted."
            ),
            "header": "Municipal Accounting Office",
            "prefix": "ACCTG-SFPERF",
            "signatories": [
                {"role": "Prepared by", "name": "Accounting statement preparer"},
                {"role": "Reviewed by", "name": "Municipal Accountant / authorized reviewer"},
            ],
        },
    ),
    "treasury": (
        {
            "name": "Payment Instrument and Disbursement Register",
            "slug": "payment-instrument-disbursement-register",
            "dataset_key": "finance_payment_instrument_register",
            "description": (
                "Issued, advised, released, returned, cancelled, and replacement instrument activity for "
                "the covered period with voucher, advice, claimant receipt, and exception evidence."
            ),
            "fields": [
                "case_reference", "dv_number", "voucher_date", "payee", "fund_code",
                "bank_account_code", "check_number", "amount", "status", "operational_status",
                "issued_at", "advice_number", "advice_status", "released_at", "released_to",
                "receipt_reference", "cancelled_at", "cancellation_reason", "replacement_number",
            ],
            "totals": ["amount"],
            "authority_reference": (
                "COA cash/disbursement-register guidance and locally approved Treasury custody procedure; "
                "exact register layout, instrument scope, signatories, copies, and recipients remain to be confirmed."
            ),
            "header": "Municipal Treasury Office",
            "prefix": "TRSY-DISB",
            "signatories": [
                {"role": "Prepared by", "name": "Treasury disbursement-register preparer"},
                {"role": "Reviewed by", "name": "Municipal Treasurer / authorized reviewer"},
            ],
        },
    ),
}


def _department_kind(department):
    identity = f"{department.slug or ''} {department.name or ''}".casefold()
    if "budget" in identity:
        return "budget"
    if "treasury" in identity:
        return "treasury"
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
            if kind == "accounting":
                from .statement_services import seed_statement_starters
                seed_statement_starters(department, accountable_actor)
    return results


def seed_reporting_presets(actor=None):
    return {
        "mswd": seed_mswd_presets(actor),
        "finance": seed_finance_presets(actor),
    }
