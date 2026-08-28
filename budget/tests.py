from datetime import date
from decimal import Decimal
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import FiscalYear, Fund, LedgerAccount, ProgramActivityProject, ResponsibilityCenter
from departments.models import Department

from .models import BudgetCall, BudgetCeiling, BudgetProposalLine, BudgetVersion
from .services import compare_versions, consolidate_versions, transition_call, transition_version


class AnnualBudgetPreparationTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.budget_office = Department.objects.create(name="Municipal Budget Office", slug="annual-budget")
        cls.accounting_office = Department.objects.create(name="Municipal Accounting Office", slug="annual-accounting")
        cls.requesting_office = Department.objects.create(name="General Services Office", slug="annual-gso")
        cls.other_office = Department.objects.create(name="Human Resources Office", slug="annual-hr")
        cls.preparer = cls.employee(cls.budget_office, "budget.preparer", "view_budget_workspace", "prepare_budget_calls", "prepare_budget_proposals")
        cls.reviewer = cls.employee(cls.budget_office, "budget.reviewer", "view_budget_workspace", "approve_budget_calls", "review_budget_proposals", "view_budget_audit")
        cls.outsider = cls.employee(cls.other_office, "budget.outsider", "view_budget_workspace", "prepare_budget_proposals")
        owner = {"department_id": cls.accounting_office.pk, "department_label": cls.accounting_office.name}
        cls.fiscal_year = FiscalYear.objects.create(
            **owner, year=2027, label="FY 2027", starts_on=date(2027, 1, 1), ends_on=date(2027, 12, 31),
            business_date=date(2027, 1, 1), status=FiscalYear.APPROVED,
        )
        cls.fund = Fund.objects.create(**owner, code="GF", name="General Fund")
        cls.center = ResponsibilityCenter.objects.create(**owner, code="GSO", name="General Services Office", office_id=cls.requesting_office.pk)
        cls.account = LedgerAccount.objects.create(**owner, code="5-02-03", title="Office supplies", account_type="expense", normal_balance="debit")
        cls.program = ProgramActivityProject.objects.create(
            **owner, fiscal_year=cls.fiscal_year, code="GSO-OPS", name="GSO Operations", kind="activity",
            responsibility_center=cls.center, effective_from=date(2027, 1, 1),
        )

    @classmethod
    def employee(cls, department, username, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="budget-test-password",
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="budget", codename__in=permissions))
        return get_user_model().objects.get(pk=user.pk)

    def make_call(self, status=BudgetCall.DRAFT):
        return BudgetCall.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            fiscal_year=self.fiscal_year, title="FY 2027 Annual Budget Call", authority_reference="Synthetic local budget call",
            instructions="Use governed classifications and reviewed targets.", proposal_opens_on=date(2026, 8, 1),
            proposal_due_on=date(2026, 9, 30), status=status, created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )

    def add_ceiling(self, call, amount="100000.00"):
        return BudgetCeiling.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name, budget_call=call,
            requesting_department_id=self.requesting_office.pk, requesting_department_label=self.requesting_office.name,
            fund=self.fund, expense_class="MOOE", amount=Decimal(amount), basis="Synthetic reviewed ceiling schedule.",
        )

    def make_version(self, call, version=1):
        return BudgetVersion.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name, budget_call=call,
            fiscal_year=self.fiscal_year, kind=BudgetVersion.DEPARTMENT, version=version,
            title=f"GSO proposal v{version}", requesting_department_id=self.requesting_office.pk,
            requesting_department_label=self.requesting_office.name, change_explanation="Initial synthetic proposal.",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
        )

    def add_line(self, version, amount="75000.00", account=None):
        return BudgetProposalLine.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name, version=version,
            fund=self.fund, responsibility_center=self.center, program=self.program, account=account or self.account,
            expense_class="MOOE", particulars="Synthetic office supplies program", performance_target="Serve 12 monthly cycles",
            amount=Decimal(amount), change_explanation="Supported by synthetic work plan.",
        )

    def test_call_requires_ceiling_and_independent_publication(self):
        call = self.make_call()
        with self.assertRaisesMessage(ValidationError, "at least one"):
            transition_call(call, "submit", self.preparer)
        self.add_ceiling(call)
        call = transition_call(call, "submit", self.preparer)
        self.assertEqual(call.status, BudgetCall.FOR_REVIEW)
        with self.assertRaisesMessage(ValidationError, "cannot approve"):
            transition_call(call, "publish", self.preparer)
        call = transition_call(call, "publish", self.reviewer, "Reviewed synthetic ceiling schedule.")
        self.assertEqual(call.status, BudgetCall.PUBLISHED)
        ceiling = call.ceilings.get()
        ceiling.amount = Decimal("90000")
        with self.assertRaisesMessage(ValidationError, "editable only"):
            ceiling.full_clean()

    def test_approved_proposal_stays_nonspendable_and_within_ceiling(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        version = self.make_version(call)
        self.add_line(version)
        version = transition_version(version, "submit", self.preparer)
        self.assertEqual(version.status, BudgetVersion.FOR_REVIEW)
        with self.assertRaisesMessage(ValidationError, "cannot approve"):
            transition_version(version, "approve", self.preparer, "Self review")
        version = transition_version(version, "approve", self.reviewer, "Compared to ceiling and work target.")
        self.assertEqual(version.status, BudgetVersion.APPROVED)
        self.assertFalse(version.is_spendable_authority)
        line = version.lines.get()
        line.amount = Decimal("80000")
        with self.assertRaisesMessage(ValidationError, "editable only"):
            line.full_clean()

    def test_over_ceiling_proposal_cannot_be_submitted(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call, "50000")
        version = self.make_version(call)
        self.add_line(version, "50000")
        self.add_line(version, "0.01")
        with self.assertRaisesMessage(ValidationError, "exceeds"):
            transition_version(version, "submit", self.preparer)

    def test_comparison_uses_governed_classification_keys(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        left, right = self.make_version(call, 1), self.make_version(call, 2)
        self.add_line(left, "50000")
        self.add_line(right, "62000")
        rows = compare_versions(left, right)
        self.assertEqual(rows[0]["change"], Decimal("12000"))
        self.assertEqual(rows[0]["key"][:2], ("GF", "GSO"))

    def test_consolidation_copies_approved_sources_without_overwriting_them(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        source = self.make_version(call)
        self.add_line(source, "64000")
        source.status = BudgetVersion.APPROVED
        source.save(update_fields=("status",))
        target = consolidate_versions(
            sources=[source], user=self.reviewer, title="FY 2027 executive proposal",
            change_explanation="First traceable executive consolidation.",
        )
        self.assertEqual(target.kind, BudgetVersion.EXECUTIVE)
        self.assertEqual(target.status, BudgetVersion.DRAFT)
        self.assertFalse(target.is_spendable_authority)
        self.assertEqual(target.total_amount, Decimal("64000"))
        self.assertEqual(target.source_links.get().source_version, source)
        self.assertEqual(BudgetVersion.objects.get(pk=source.pk).status, BudgetVersion.APPROVED)

    def test_workspace_is_department_bounded_and_export_is_archived(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        version = self.make_version(call)
        self.add_line(version)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("budget:version_detail", args=(version.public_id,))).status_code, 404)
        self.client.force_login(self.preparer)
        detail = self.client.get(reverse("budget:version_detail", args=(version.public_id,)))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Not spendable authority")
        self.assertContains(detail, "Add resource estimate")
        with tempfile.TemporaryDirectory() as directory, override_settings(GRAND_EXPORT_ROOT=directory):
            response = self.client.get(reverse("budget:version_export", args=(version.public_id,)))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            self.assertIn(b"spendable_authority", response.content)
            self.assertIn(b",no,", response.content)
            from pathlib import Path
            self.assertEqual(len(list(Path(directory).rglob("*.manifest.json"))), 1)
