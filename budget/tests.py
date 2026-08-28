from datetime import date
from decimal import Decimal
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import FiscalYear, Fund, LedgerAccount, ProgramActivityProject, ResponsibilityCenter
from departments.models import Department
from departments.services.internal_howto_seed import seed_finance_internal_howtos

from .models import (
    AllotmentMovement, AllotmentOrderLine, AllotmentReleaseOrder, AppropriationAuthorization,
    BudgetAuditEvent, BudgetCall, BudgetCeiling, BudgetProposalLine, BudgetVersion,
    ObligationMovement, ObligationRequest, ObligationRequestLine,
)
from .services import (
    allotment_line_balance, authorization_allotment_totals, compare_versions, consolidate_versions,
    obligation_line_balance, transition_allotment_order, transition_authorization, transition_call,
    transition_obligation_request, transition_version,
)


class AnnualBudgetPreparationTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.budget_office = Department.objects.create(name="Municipal Budget Office", slug="annual-budget")
        cls.accounting_office = Department.objects.create(name="Municipal Accounting Office", slug="annual-accounting")
        cls.requesting_office = Department.objects.create(name="General Services Office", slug="annual-gso")
        cls.other_office = Department.objects.create(name="Human Resources Office", slug="annual-hr")
        cls.preparer = cls.employee(cls.budget_office, "budget.preparer", "view_budget_workspace", "prepare_budget_calls", "prepare_budget_proposals", "view_allotment_control", "prepare_allotment_releases")
        cls.certifier = cls.employee(cls.budget_office, "budget.certifier", "view_budget_workspace", "view_obligation_registry", "certify_obligations")
        cls.reviewer = cls.employee(cls.budget_office, "budget.reviewer", "view_budget_workspace", "approve_budget_calls", "review_budget_proposals", "view_budget_audit")
        cls.authorizer = cls.employee(cls.budget_office, "budget.authorizer", "view_budget_workspace", "authorize_appropriations", "view_budget_audit", "view_allotment_control", "approve_allotment_releases")
        cls.outsider = cls.employee(cls.other_office, "budget.outsider", "view_budget_workspace", "prepare_budget_proposals", "view_allotment_control", "prepare_allotment_releases")
        cls.requester = cls.employee(cls.requesting_office, "gso.requester", "view_budget_workspace", "initiate_obligation_requests")
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

    def make_authorized_appropriation(self, amount="75000.00", suffix="201"):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call, "1000000")
        version = BudgetVersion.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call=call, fiscal_year=self.fiscal_year, kind=BudgetVersion.FINAL, version=1,
            title=f"FY 2027 operational budget {suffix}", change_explanation="Synthetic final version.",
            status=BudgetVersion.APPROVED, created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
        )
        self.add_line(version, amount)
        authorization = AppropriationAuthorization.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            version=version, authority_type=AppropriationAuthorization.ORDINANCE,
            ordinance_number=f"Synthetic Ordinance 2026-{suffix}", ordinance_date=date(2026, 12, 15),
            effectivity_date=date(2027, 1, 1), review_status=AppropriationAuthorization.FAVORABLE,
            review_reference=f"Synthetic favorable review {suffix}", review_date=date(2026, 12, 28),
            evidence_reference="Synthetic signed ordinance, review, and appropriation schedule references.",
            signed_control_total=Decimal(amount), created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        transition_authorization(authorization, "submit", self.preparer)
        return transition_authorization(authorization, "authorize", self.authorizer, "Independent synthetic acceptance.")

    def make_allotment_order(self, authorization, *, number="ARO-2027-001", kind=AllotmentReleaseOrder.INITIAL, total="60000.00", corrects=None):
        return AllotmentReleaseOrder.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            authorization=authorization, fiscal_year=self.fiscal_year, order_number=number, kind=kind,
            release_date=date(2027, 1, 5), effective_date=date(2027, 1, 5),
            authority_reference="Synthetic reviewed allotment authority",
            evidence_reference="Synthetic signed ARO/equivalent and schedule references.",
            purpose="Synthetic quarterly operating release.", signed_control_total=Decimal(total),
            corrects=corrects, created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
        )

    def add_allotment_line(self, order, amount, movement_type=AllotmentOrderLine.RELEASE):
        return AllotmentOrderLine.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            order=order, appropriation_line=order.authorization.schedule_lines.get(),
            movement_type=movement_type, amount=Decimal(amount), remarks="Synthetic reviewed schedule line.",
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

    def test_final_version_requires_exact_independent_authorization_snapshot(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        version = BudgetVersion.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call=call, fiscal_year=self.fiscal_year, kind=BudgetVersion.FINAL, version=1,
            title="FY 2027 final approved budget", change_explanation="Synthetic final deliberated version.",
            status=BudgetVersion.APPROVED, created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
        )
        self.add_line(version, "75000")
        authorization = AppropriationAuthorization.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            version=version, authority_type=AppropriationAuthorization.ORDINANCE,
            ordinance_number="Synthetic Ordinance 2026-101", ordinance_date=date(2026, 12, 15),
            effectivity_date=date(2027, 1, 1), review_status=AppropriationAuthorization.FAVORABLE,
            review_reference="Synthetic favorable review 2026-22", review_date=date(2026, 12, 28),
            evidence_reference="Synthetic signed ordinance, review, and appropriation schedule references.",
            signed_control_total=Decimal("75000"), created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        authorization = transition_authorization(authorization, "submit", self.preparer)
        with self.assertRaisesMessage(ValidationError, "cannot authorize"):
            transition_authorization(authorization, "authorize", self.preparer, "Self authorization")
        authorization = transition_authorization(
            authorization, "authorize", self.authorizer, "Verified ordinance, favorable review, effectivity, and signed total.",
        )
        self.assertEqual(authorization.status, AppropriationAuthorization.AUTHORIZED)
        self.assertEqual(authorization.schedule_lines.count(), 1)
        self.assertEqual(len(authorization.snapshot_checksum), 64)
        version.refresh_from_db()
        self.assertTrue(version.is_spendable_authority)
        authorization.evidence_reference = "Silently replaced evidence reference."
        with self.assertRaisesMessage(ValidationError, "immutable"):
            authorization.full_clean()

    def test_authorization_rejects_control_difference_and_exports_snapshot(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        version = BudgetVersion.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call=call, fiscal_year=self.fiscal_year, kind=BudgetVersion.FINAL, version=1,
            title="FY 2027 final export budget", change_explanation="Synthetic final version.",
            status=BudgetVersion.APPROVED, created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
        )
        self.add_line(version, "75000")
        item = AppropriationAuthorization.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name, version=version,
            authority_type=AppropriationAuthorization.ORDINANCE, ordinance_number="Synthetic Ordinance 2026-102",
            ordinance_date=date(2026, 12, 15), effectivity_date=date(2027, 1, 1),
            review_status=AppropriationAuthorization.FAVORABLE, review_reference="Synthetic review",
            review_date=date(2026, 12, 28), evidence_reference="Synthetic accepted references.",
            signed_control_total=Decimal("74999"), created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
        )
        with self.assertRaisesMessage(ValidationError, "must equal"):
            transition_authorization(item, "submit", self.preparer)
        item.signed_control_total = Decimal("75000"); item.save(update_fields=("signed_control_total",))
        transition_authorization(item, "submit", self.preparer)
        item = transition_authorization(item, "authorize", self.authorizer, "Independent synthetic acceptance.")
        self.client.force_login(self.authorizer)
        with tempfile.TemporaryDirectory() as directory, override_settings(GRAND_EXPORT_ROOT=directory):
            response = self.client.get(reverse("budget:authorization_export", args=(item.public_id,)))
            self.assertEqual(response.status_code, 200)
            self.assertIn(item.snapshot_checksum.encode(), response.content)
            from pathlib import Path
            self.assertEqual(len(list(Path(directory).rglob("*.manifest.json"))), 1)

    def test_allotment_release_posts_once_with_independent_control_and_exact_balances(self):
        authorization = self.make_authorized_appropriation()
        order = self.make_allotment_order(authorization)
        line = self.add_allotment_line(order, "60000")
        order = transition_allotment_order(order, "submit", self.preparer)
        self.assertEqual(order.status, AllotmentReleaseOrder.FOR_REVIEW)
        with self.assertRaisesMessage(ValidationError, "cannot post"):
            transition_allotment_order(order, "post", self.preparer, "Self posting")
        order = transition_allotment_order(order, "post", self.authorizer, "Matched signed ARO and schedule total.")
        self.assertEqual(order.status, AllotmentReleaseOrder.POSTED)
        self.assertEqual(len(order.snapshot_checksum), 64)
        movement = order.movements.get()
        self.assertEqual(movement.source_line_id, line.pk)
        self.assertEqual(movement.release_effect, Decimal("60000"))
        balance = allotment_line_balance(authorization.schedule_lines.get())
        self.assertEqual(balance, {
            "authorized": Decimal("75000"), "released": Decimal("60000"),
            "reserved": Decimal("0"), "deferred": Decimal("0"), "held": Decimal("0"),
            "unreleased": Decimal("15000"), "executable": Decimal("60000"),
        })
        totals = authorization_allotment_totals(authorization)
        self.assertEqual(totals["released"], Decimal("60000"))

    def test_allotment_rejects_control_difference_overrelease_and_excess_hold(self):
        authorization = self.make_authorized_appropriation()
        first = self.make_allotment_order(authorization)
        self.add_allotment_line(first, "60000")
        transition_allotment_order(first, "submit", self.preparer)
        transition_allotment_order(first, "post", self.authorizer, "Independent initial release review.")

        over = self.make_allotment_order(authorization, number="ARO-2027-002", kind=AllotmentReleaseOrder.LATER, total="20000")
        self.add_allotment_line(over, "20000")
        with self.assertRaisesMessage(ValidationError, "exceed the authorized appropriation"):
            transition_allotment_order(over, "submit", self.preparer)

        reserve = self.make_allotment_order(authorization, number="ARO-2027-R01", kind=AllotmentReleaseOrder.RESERVE, total="60000.01")
        self.add_allotment_line(reserve, "60000.01", AllotmentOrderLine.RESERVE)
        with self.assertRaisesMessage(ValidationError, "exceed released allotment"):
            transition_allotment_order(reserve, "submit", self.preparer)

        mismatch = self.make_allotment_order(authorization, number="ARO-2027-003", kind=AllotmentReleaseOrder.LATER, total="1000")
        self.add_allotment_line(mismatch, "500")
        with self.assertRaisesMessage(ValidationError, "signed allotment control total"):
            transition_allotment_order(mismatch, "submit", self.preparer)

    def test_reserve_release_and_linked_return_preserve_posted_history(self):
        authorization = self.make_authorized_appropriation()
        release = self.make_allotment_order(authorization)
        self.add_allotment_line(release, "60000")
        transition_allotment_order(release, "submit", self.preparer)
        release = transition_allotment_order(release, "post", self.authorizer, "Independent release review.")

        reserve = self.make_allotment_order(authorization, number="ARO-2027-R01", kind=AllotmentReleaseOrder.RESERVE, total="10000")
        self.add_allotment_line(reserve, "10000", AllotmentOrderLine.RESERVE)
        transition_allotment_order(reserve, "submit", self.preparer)
        transition_allotment_order(reserve, "post", self.authorizer, "Independent reserve review.")
        balance = allotment_line_balance(authorization.schedule_lines.get())
        self.assertEqual((balance["held"], balance["executable"]), (Decimal("10000"), Decimal("50000")))

        wrong_bucket_release = self.make_allotment_order(
            authorization, number="ARO-2027-D01", kind=AllotmentReleaseOrder.DEFERRAL, total="1000",
        )
        self.add_allotment_line(wrong_bucket_release, "1000", AllotmentOrderLine.DEFERRAL_RELEASE)
        with self.assertRaisesMessage(ValidationError, "lift more deferral"):
            transition_allotment_order(wrong_bucket_release, "submit", self.preparer)

        returned = self.make_allotment_order(
            authorization, number="ARO-2027-RET01", kind=AllotmentReleaseOrder.RETURN,
            total="5000", corrects=release,
        )
        self.add_allotment_line(returned, "5000", AllotmentOrderLine.RETURN)
        transition_allotment_order(returned, "submit", self.preparer)
        transition_allotment_order(returned, "post", self.authorizer, "Independent return review.")
        balance = allotment_line_balance(authorization.schedule_lines.get())
        self.assertEqual((balance["released"], balance["unreleased"], balance["executable"]), (
            Decimal("55000"), Decimal("20000"), Decimal("45000"),
        ))
        release.purpose = "Silently rewritten purpose"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            release.full_clean()
        movement = AllotmentMovement.objects.get(order=release)
        movement.amount = Decimal("1")
        with self.assertRaisesMessage(ValidationError, "append-only"):
            movement.save()

    def test_allotment_workspace_is_department_bounded_and_export_is_archived(self):
        authorization = self.make_authorized_appropriation()
        order = self.make_allotment_order(authorization)
        self.add_allotment_line(order, "60000")
        transition_allotment_order(order, "submit", self.preparer)
        order = transition_allotment_order(order, "post", self.authorizer, "Independent export release review.")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("budget:allotment_detail", args=(order.public_id,))).status_code, 404)
        self.client.force_login(self.authorizer)
        workspace = self.client.get(reverse("budget:allotment_workspace"))
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, "Authorized appropriation balances")
        self.assertContains(workspace, "60000.00")
        detail = self.client.get(reverse("budget:allotment_detail", args=(order.public_id,)))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Posted movements are immutable")
        with tempfile.TemporaryDirectory() as directory, override_settings(GRAND_EXPORT_ROOT=directory):
            response = self.client.get(reverse("budget:allotment_export", args=(order.public_id,)))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            self.assertIn(b"unreleased_balance", response.content)
            self.assertIn(order.snapshot_checksum.encode(), response.content)
            from pathlib import Path
            manifests = list(Path(directory).rglob("*.manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertIn("finance-allotment-releases", str(manifests[0]))

    def test_guided_draft_editing_closes_at_submission(self):
        authorization = self.make_authorized_appropriation()
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("budget:allotment_create"), {
            "authorization": authorization.pk, "order_number": "ARO-2027-EDIT",
            "kind": AllotmentReleaseOrder.INITIAL, "release_date": "2027-01-05",
            "effective_date": "2027-01-05", "authority_reference": "Synthetic edit authority",
            "evidence_reference": "Synthetic signed schedule reference", "purpose": "Edit-window test",
            "signed_control_total": "10000.00", "corrects": "",
        })
        self.assertEqual(response.status_code, 302)
        order = AllotmentReleaseOrder.objects.get(order_number="ARO-2027-EDIT")
        response = self.client.post(reverse("budget:allotment_line_create", args=(order.public_id,)), {
            "appropriation_line": authorization.schedule_lines.get().pk,
            "movement_type": AllotmentOrderLine.RELEASE, "amount": "10000.00", "remarks": "Original draft line",
        })
        self.assertEqual(response.status_code, 302)
        line = order.lines.get()
        response = self.client.post(reverse("budget:allotment_line_edit", args=(order.public_id, line.pk)), {
            "appropriation_line": authorization.schedule_lines.get().pk,
            "movement_type": AllotmentOrderLine.RELEASE, "amount": "9000.00", "remarks": "Corrected before submission",
        })
        self.assertEqual(response.status_code, 302)
        line.refresh_from_db()
        self.assertEqual(line.amount, Decimal("9000"))
        self.assertTrue(BudgetAuditEvent.objects.filter(target_id=str(order.public_id), action="allotment_line_edited").exists())
        order.signed_control_total = Decimal("9000")
        order.save(update_fields=("signed_control_total",))
        transition_allotment_order(order, "submit", self.preparer)
        self.assertEqual(self.client.get(reverse("budget:allotment_line_edit", args=(order.public_id, line.pk))).status_code, 404)

    def make_executable_authority(self, amount="75000.00", release="60000.00"):
        authorization = self.make_authorized_appropriation(amount)
        order = self.make_allotment_order(authorization, total=release)
        self.add_allotment_line(order, release)
        transition_allotment_order(order, "submit", self.preparer)
        transition_allotment_order(order, "post", self.authorizer, "Independent synthetic release review.")
        return authorization

    def make_obligation_request(self, authorization, *, reference="GSO-REQ-001", total="10000.00", kind=ObligationRequest.ORIGINAL, corrects=None):
        return ObligationRequest.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            authorization=authorization, fiscal_year=self.fiscal_year,
            requesting_department_id=self.requesting_office.pk,
            requesting_department_label=self.requesting_office.name,
            kind=kind, form_type=ObligationRequest.OBR, request_reference=reference,
            obligation_date=date(2027, 1, 15), claimant_payee="Synthetic Office Supplier",
            particulars="Synthetic accountable office supply obligation.",
            evidence_reference="Synthetic request and support references.",
            signed_control_total=Decimal(total), corrects=corrects,
            created_by_id=self.requester.pk, created_by_label=self.requester.username,
        )

    def add_obligation_line(self, request, amount="10000.00", movement=ObligationRequestLine.OBLIGATE):
        return ObligationRequestLine.objects.create(
            department_id=self.budget_office.pk, department_label=self.budget_office.name,
            request=request, appropriation_line=request.authorization.schedule_lines.get(),
            movement_type=movement, amount=Decimal(amount), remarks="Synthetic obligation schedule line.",
        )

    def test_requesting_office_submits_and_budget_certifies_exact_obligation_once(self):
        authorization = self.make_executable_authority()
        item = self.make_obligation_request(authorization)
        source = self.add_obligation_line(item)
        item = transition_obligation_request(item, "submit", self.requester)
        self.assertEqual(item.status, ObligationRequest.FOR_CERTIFICATION)
        with self.assertRaisesMessage(ValidationError, "owning Budget office"):
            transition_obligation_request(item, "certify", self.requester, "Self certification", "OBR-2027-0001")
        item = transition_obligation_request(
            item, "certify", self.certifier, "Matched authority, classification, support, and unobligated allotment.", "OBR-2027-0001",
        )
        self.assertEqual(item.status, ObligationRequest.CERTIFIED)
        self.assertEqual(len(item.snapshot_checksum), 64)
        movement = item.movements.get()
        self.assertEqual((movement.source_line_id, movement.obligation_effect), (source.pk, Decimal("10000")))
        balance = obligation_line_balance(authorization.schedule_lines.get())
        self.assertEqual((balance["executable"], balance["obligated"], balance["unobligated"]), (
            Decimal("60000"), Decimal("10000"), Decimal("50000"),
        ))
        with self.assertRaisesMessage(ValidationError, "unavailable"):
            transition_obligation_request(item, "certify", self.certifier, "Duplicate", "OBR-2027-0001")

    def test_obligation_rejects_control_difference_excess_and_duplicate_request(self):
        authorization = self.make_executable_authority(release="12000.00")
        mismatch = self.make_obligation_request(authorization, reference="GSO-MISMATCH", total="9000")
        self.add_obligation_line(mismatch, "10000")
        with self.assertRaisesMessage(ValidationError, "signed obligation control total"):
            transition_obligation_request(mismatch, "submit", self.requester)

        excess = self.make_obligation_request(authorization, reference="GSO-EXCESS", total="12000.01")
        self.add_obligation_line(excess, "12000.01")
        with self.assertRaisesMessage(ValidationError, "exceeds"):
            transition_obligation_request(excess, "submit", self.requester)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_obligation_request(authorization, reference="GSO-EXCESS", total="1")

    def test_linked_return_restores_balance_and_certified_history_is_immutable(self):
        authorization = self.make_executable_authority()
        original = self.make_obligation_request(authorization)
        self.add_obligation_line(original, "10000")
        transition_obligation_request(original, "submit", self.requester)
        original = transition_obligation_request(original, "certify", self.certifier, "Independent certification.", "OBR-2027-0001")

        unrelated = self.make_obligation_request(authorization, reference="GSO-REQ-OTHER", total="5000")
        self.add_obligation_line(unrelated, "5000")
        transition_obligation_request(unrelated, "submit", self.requester)
        transition_obligation_request(unrelated, "certify", self.certifier, "Independent unrelated certification.", "OBR-2027-OTHER")

        excessive_lineage_return = self.make_obligation_request(
            authorization, reference="GSO-RET-EXCESS", total="-11000", kind=ObligationRequest.RETURN, corrects=original,
        )
        self.add_obligation_line(excessive_lineage_return, "11000", ObligationRequestLine.REDUCE)
        with self.assertRaisesMessage(ValidationError, "linked correction lineage"):
            transition_obligation_request(excessive_lineage_return, "submit", self.requester)

        over_hold = self.make_allotment_order(
            authorization, number="ARO-2027-POST-OBL-HOLD", kind=AllotmentReleaseOrder.RESERVE, total="50000.01",
        )
        self.add_allotment_line(over_hold, "50000.01", AllotmentOrderLine.RESERVE)
        with self.assertRaisesMessage(ValidationError, "already certified obligations"):
            transition_allotment_order(over_hold, "submit", self.preparer)

        returned = self.make_obligation_request(
            authorization, reference="GSO-RET-001", total="-2500", kind=ObligationRequest.RETURN, corrects=original,
        )
        self.add_obligation_line(returned, "2500", ObligationRequestLine.REDUCE)
        transition_obligation_request(returned, "submit", self.requester)
        returned = transition_obligation_request(returned, "certify", self.certifier, "Reviewed pre-DV return.", "OBR-2027-0002")
        balance = obligation_line_balance(authorization.schedule_lines.get())
        self.assertEqual((balance["obligated"], balance["unobligated"]), (Decimal("12500"), Decimal("47500")))

        original.particulars = "Silently changed particulars"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            original.full_clean()
        movement = ObligationMovement.objects.get(request=original)
        movement.amount = Decimal("1")
        with self.assertRaisesMessage(ValidationError, "append-only"):
            movement.save()

    def test_later_issuance_boundary_blocks_obligation_only_correction(self):
        authorization = self.make_executable_authority()
        original = self.make_obligation_request(authorization)
        self.add_obligation_line(original)
        transition_obligation_request(original, "submit", self.requester)
        original = transition_obligation_request(original, "certify", self.certifier, "Independent certification.", "OBR-2027-0001")
        correction = self.make_obligation_request(
            authorization, reference="GSO-ADJ-001", total="-1000", kind=ObligationRequest.ADJUSTMENT, corrects=original,
        )
        self.add_obligation_line(correction, "1000", ObligationRequestLine.REDUCE)
        with patch("budget.services.downstream_issuance_boundary", return_value="disbursement voucher"):
            with self.assertRaisesMessage(ValidationError, "reversal or cancellation"):
                transition_obligation_request(correction, "submit", self.requester)

    def test_obligation_scope_guided_edit_and_tracesync_registry_export(self):
        authorization = self.make_executable_authority()
        seed_finance_internal_howtos()
        self.client.force_login(self.requester)
        response = self.client.post(reverse("budget:obligation_create"), {
            "authorization": authorization.pk, "kind": ObligationRequest.ORIGINAL,
            "form_type": ObligationRequest.OBR, "request_reference": "GSO-WEB-001",
            "obligation_date": "2027-01-15", "claimant_payee": "Synthetic Web Supplier",
            "particulars": "Synthetic web-created request.", "evidence_reference": "Synthetic support reference.",
            "signed_control_total": "5000.00", "corrects": "",
        })
        self.assertEqual(response.status_code, 302)
        item = ObligationRequest.objects.get(request_reference="GSO-WEB-001")
        detail = self.client.get(reverse("budget:obligation_detail", args=(item.public_id,)))
        self.assertContains(detail, "Prepare and submit an obligation request")
        self.assertContains(detail, "private step checklist")
        response = self.client.post(reverse("budget:obligation_line_create", args=(item.public_id,)), {
            "appropriation_line": authorization.schedule_lines.get().pk,
            "movement_type": ObligationRequestLine.OBLIGATE, "amount": "5000.00", "remarks": "Initial web line",
        })
        self.assertEqual(response.status_code, 302)
        line = item.lines.get()
        response = self.client.post(reverse("budget:obligation_line_edit", args=(item.public_id, line.pk)), {
            "appropriation_line": authorization.schedule_lines.get().pk,
            "movement_type": ObligationRequestLine.OBLIGATE, "amount": "5000.00", "remarks": "Guided correction",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BudgetAuditEvent.objects.filter(target_id=str(item.public_id), action="obligation_line_edited").exists())
        transition_obligation_request(item, "submit", self.requester)
        self.assertEqual(self.client.get(reverse("budget:obligation_line_edit", args=(item.public_id, line.pk))).status_code, 404)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("budget:obligation_detail", args=(item.public_id,))).status_code, 403)
        transition_obligation_request(item, "certify", self.certifier, "Independent web request review.", "OBR-2027-WEB1")
        self.client.force_login(self.certifier)
        workspace = self.client.get(reverse("budget:obligation_workspace"))
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, "RAAO-equivalent control totals")
        self.assertContains(workspace, "55000.00")
        self.assertContains(workspace, "Certify obligations and reconcile RAAO balances")
        with tempfile.TemporaryDirectory() as directory, override_settings(GRAND_EXPORT_ROOT=directory):
            response = self.client.get(reverse("budget:obligation_registry_export"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            self.assertIn(b"unobligated_balance", response.content)
            self.assertIn(item.snapshot_checksum.encode(), response.content)
            from pathlib import Path
            manifests = list(Path(directory).rglob("*.manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertIn("finance-obligation-registry", str(manifests[0]))
