from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.text import slugify

from accounting.models import FiscalYear, Fund, LedgerAccount, ProgramActivityProject, ResponsibilityCenter
from departments.models import Department
from departments.services.internal_howto_seed import seed_finance_internal_howtos
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceDocumentRule, FinanceNumberingSequence, FinanceParty,
    FinanceTransactionVariant,
)
from vouchers.models import PayableDocumentEvidence, PayableIntake, VoucherCase
from vouchers.services import (
    add_payable_obligation_allocation,
    create_payable_case_from_obligation, prepare_voucher, record_payable_document_evidence,
    payable_relationship_summary, revise_payable_claim_control,
    reconcile_authoritative_obligation, revise_payable_obligation_allocation,
    review_payable_intake, submit_payable_intake,
)

from .models import (
    AllotmentMovement, AllotmentOrderLine, AllotmentReleaseOrder, AppropriationAuthorization,
    BudgetAuditEvent, BudgetCall, BudgetCeiling, BudgetProposalLine, BudgetVersion,
    ObligationMovement, ObligationRequest, ObligationRequestLine, PayableObligationAllocation,
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

    def test_annual_workspace_filters_versions_by_status_kind_and_next_action(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        draft = self.make_version(call, 1)
        review = self.make_version(call, 2)
        review.status = BudgetVersion.FOR_REVIEW
        review.save(update_fields=("status", "updated_at"))
        BudgetCall.objects.create(
            department_id=self.budget_office.pk,
            department_label=self.budget_office.name,
            fiscal_year=self.fiscal_year,
            title="Second FY 2027 call",
            authority_reference="Synthetic supplemental call basis",
            instructions="Prove fiscal-year filtering remains unambiguous.",
            proposal_opens_on=date(2026, 10, 1),
            proposal_due_on=date(2026, 10, 31),
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )

        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("budget:workspace"), {
            "fiscal_year": self.fiscal_year.pk,
            "kind": BudgetVersion.DEPARTMENT,
            "attention": "awaiting_proposal_review",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, review.title)
        self.assertNotContains(response, draft.title)
        self.assertContains(response, "Independent reviewer: approve or return")
        self.assertContains(response, "1 visible version")

        response = self.client.get(reverse("budget:workspace"), {
            "status": BudgetVersion.DRAFT,
            "attention": "awaiting_proposal_review",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, draft.title)
        self.assertNotContains(response, review.title)

        other_year = FiscalYear.objects.create(
            department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name,
            year=2028,
            label="FY 2028 outside Budget scope",
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
            business_date=date(2028, 1, 1),
            status=FiscalYear.APPROVED,
        )
        BudgetCall.objects.create(
            department_id=self.other_office.pk,
            department_label=self.other_office.name,
            fiscal_year=other_year,
            title="Other office FY 2028 call",
            authority_reference="Synthetic other-office authority",
            instructions="Not in the current Budget office.",
            proposal_opens_on=date(2027, 8, 1),
            proposal_due_on=date(2027, 9, 30),
            created_by_id=self.outsider.pk,
            created_by_label=self.outsider.username,
        )
        response = self.client.get(reverse("budget:workspace"), {"fiscal_year": other_year.pk})
        self.assertEqual(response.status_code, 404)

    def test_filtered_annual_register_archives_audits_and_preserves_authority_boundary(self):
        call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(call)
        self.make_version(call, 1)
        version = BudgetVersion.objects.create(
            department_id=self.budget_office.pk,
            department_label=self.budget_office.name,
            budget_call=call,
            fiscal_year=self.fiscal_year,
            kind=BudgetVersion.FINAL,
            version=1,
            title="=FY 2027 final awaiting authority",
            change_explanation="Synthetic final version for filtered export.",
            status=BudgetVersion.APPROVED,
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        self.add_line(version, "75000")
        authorization = AppropriationAuthorization.objects.create(
            department_id=self.budget_office.pk,
            department_label=self.budget_office.name,
            version=version,
            authority_type=AppropriationAuthorization.ORDINANCE,
            ordinance_number="Synthetic Ordinance 2026-TRIAGE",
            ordinance_date=date(2026, 12, 15),
            effectivity_date=date(2027, 1, 1),
            review_status=AppropriationAuthorization.FAVORABLE,
            review_reference="Synthetic favorable review",
            review_date=date(2026, 12, 28),
            evidence_reference="Synthetic signed references.",
            signed_control_total=Decimal("75000"),
            status=AppropriationAuthorization.FOR_REVIEW,
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
            submitted_by_id=self.preparer.pk,
            submitted_by_label=self.preparer.username,
        )

        self.client.force_login(self.reviewer)
        with tempfile.TemporaryDirectory() as directory, override_settings(GRAND_EXPORT_ROOT=directory):
            response = self.client.get(reverse("budget:annual_register_export"), {
                "fiscal_year": self.fiscal_year.pk,
                "attention": "awaiting_authorization",
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            exported = response.content.decode("utf-8-sig")
            self.assertIn("'=FY 2027 final awaiting authority", exported)
            self.assertIn("Independent authorizer: authorize or return", exported)
            self.assertIn(authorization.ordinance_number, exported)
            self.assertNotIn("GSO proposal v1", exported)
            artifacts = list(Path(directory).rglob("*.csv"))
            self.assertEqual(len(artifacts), 1)
            self.assertIn(self.budget_office.slug, artifacts[0].parts)
            self.assertIn(slugify(self.reviewer.username), artifacts[0].parts)
            manifest = json.loads(Path(str(artifacts[0]) + ".manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"], response["X-GRAND-Export-SHA256"])
            self.assertEqual(manifest["metadata"]["attention_filter"], "awaiting_authorization")
            self.assertEqual(manifest["metadata"]["version_count"], 1)
            event = BudgetAuditEvent.objects.get(action="annual_register_exported")
            self.assertEqual(event.actor_id, self.reviewer.pk)
            self.assertEqual(event.snapshot["sha256"], response["X-GRAND-Export-SHA256"])

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

    def test_certified_obligation_opens_one_recoverable_payable_case_without_second_budget_certification(self):
        authorization = self.make_executable_authority()
        item = self.make_obligation_request(authorization)
        self.add_obligation_line(item, "10000")
        transition_obligation_request(item, "submit", self.requester)
        item = transition_obligation_request(
            item, "certify", self.certifier, "Independent certification.", "OBR-2027-PAYABLE",
        )
        self.requester.user_permissions.add(Permission.objects.get(
            content_type__app_label="vouchers", codename="initiate_payable_case",
        ))
        accountant = self.employee(self.accounting_office, "payable.accountant")
        accountant.user_permissions.add(Permission.objects.get(
            content_type__app_label="vouchers", codename="prepare_disbursement_voucher",
        ))
        review_permission = Permission.objects.get(
            content_type__app_label="vouchers", codename="review_payable_intake",
        )
        accountant.user_permissions.add(review_permission)
        release = FinanceConfigurationRelease.objects.create(
            department=self.accounting_office, code="f5-payable-test", version=1,
            title="Synthetic F5 payable setup", fiscal_year=2026, status="active",
            effective_from=date(2026, 1, 1), created_by=accountant,
            activated_by=accountant,
        )
        FinanceConfigurationItem.objects.create(
            department=self.accounting_office, release=release, category="transaction_type",
            code="ordinary-supplier-claim", version=1, label="Ordinary supplier claim",
            status="active", effective_from=date(2026, 1, 1), created_by=accountant,
        )
        variant = FinanceTransactionVariant.objects.create(
            department=self.accounting_office, release=release, code="ordinary-supplier-claim",
            label="Ordinary supplier claim", kind=FinanceTransactionVariant.ORDINARY_SUPPLIER,
            description="Synthetic one-to-one supplier payable readiness route.",
            authority_reference="Synthetic reviewed COA/DBM/local applicability decision.",
            effective_from=date(2026, 1, 1), status="active", created_by=accountant,
        )
        required_rule = FinanceDocumentRule.objects.create(
            variant=variant, code="invoice", label="Invoice / billing",
            evidence_kind=FinanceDocumentRule.INVOICE, required=True, waiver_allowed=False,
            authority_reference="Synthetic reviewed invoice requirement.", created_by=accountant,
        )
        conditional_rule = FinanceDocumentRule.objects.create(
            variant=variant, code="inspection", label="Inspection and acceptance",
            evidence_kind=FinanceDocumentRule.INSPECTION, required=False, waiver_allowed=False,
            condition_description="Applicable only when goods or completed work require inspection.",
            authority_reference="Synthetic reviewed conditional inspection rule.", created_by=accountant,
        )
        party = FinanceParty.objects.create(
            department=self.accounting_office, release=release, code="f5-supplier", version=1,
            display_name="Synthetic Office Supplier", party_type=FinanceParty.SUPPLIER,
            effective_from=date(2026, 1, 1), status="active", created_by=accountant,
        )
        case = create_payable_case_from_obligation(
            actor=self.requester, authoritative_obligation=item, payee=party,
            transaction_type="ordinary-supplier-claim", claim_reference="CLAIM-2027-001",
            invoice_number="INV-001", invoice_date=date(2027, 1, 16), claim_amount=Decimal("10000"),
            procurement_reference="PO-001", delivery_reference="DR-001",
            inspection_acceptance_reference="IAR-001", evidence_reference="Synthetic packet references.",
            duplicate_review_note="", idempotency_key="f5-payable-create",
        )
        item.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(item.linked_voucher_case_public_id, case.public_id)
        self.assertEqual(case.obligation_binding_status, VoucherCase.BINDING_LINKED)
        self.assertEqual(case.current_stage, VoucherCase.PAYABLE_PREPARATION)
        self.assertEqual(case.obligation.source_kind, "authoritative_f4_projection")
        self.assertEqual(case.obligation.certified_amount, Decimal("10000"))
        self.assertEqual(PayableIntake.objects.get(case=case).claim_reference, "CLAIM-2027-001")
        self.assertEqual(item.movements.count(), 1)
        with self.assertRaisesMessage(ValidationError, "Resolve every documentary rule"):
            submit_payable_intake(
                case=case, actor=self.requester, expected_version=case.state_version,
                idempotency_key="premature-payable-submit",
            )
        invoice = case.payable_document_evidence.get(source_rule=required_rule)
        record_payable_document_evidence(
            case=case, evidence=invoice, actor=self.requester, status=PayableDocumentEvidence.PRESENT,
            evidence_reference="Synthetic invoice INV-001", decision_note="",
            expected_version=case.state_version, idempotency_key="payable-invoice-present",
        )
        case.refresh_from_db()
        inspection = case.payable_document_evidence.get(source_rule=conditional_rule)
        record_payable_document_evidence(
            case=case, evidence=inspection, actor=self.requester,
            status=PayableDocumentEvidence.NOT_APPLICABLE, evidence_reference="",
            decision_note="Synthetic service did not involve inspectable goods.",
            expected_version=case.state_version, idempotency_key="payable-inspection-na",
        )
        case.refresh_from_db()
        accountant.user_permissions.remove(review_permission)
        with self.assertRaisesMessage(ValidationError, "No active Accounting payable reviewer"):
            submit_payable_intake(
                case=case, actor=self.requester, expected_version=case.state_version,
                idempotency_key="payable-submit-without-reviewer",
            )
        accountant.user_permissions.add(review_permission)
        submit_payable_intake(
            case=case, actor=self.requester, expected_version=case.state_version,
            idempotency_key="payable-submit",
        )
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.PAYABLE_REVIEW)
        self.assertEqual(case.current_department, self.accounting_office)
        review_payable_intake(
            case=case, actor=accountant, decision=PayableIntake.RETURNED,
            reason="Clarify the synthetic inspection not-applicable decision.",
            expected_version=case.state_version, idempotency_key="payable-return",
        )
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.PAYABLE_PREPARATION)
        self.assertEqual(case.current_department, self.requesting_office)
        self.assertEqual(case.payable_intake.status, PayableIntake.RETURNED)
        submit_payable_intake(
            case=case, actor=self.requester, expected_version=case.state_version,
            idempotency_key="payable-resubmit",
        )
        case.refresh_from_db()
        self.assertIsNone(case.payable_intake.reviewed_by)
        self.assertIsNone(case.payable_intake.reviewed_at)
        self.assertEqual(case.payable_intake.decision_reason, "")
        review_payable_intake(
            case=case, actor=accountant, decision=PayableIntake.READY,
            reason="Independent synthetic review of obligation, claim, and documentary rules.",
            expected_version=case.state_version, idempotency_key="payable-ready",
        )
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)
        self.assertEqual(case.payable_intake.status, PayableIntake.READY)
        correction = self.make_obligation_request(
            authorization, reference="GSO-PAYABLE-ADJ", total="-1000",
            kind=ObligationRequest.ADJUSTMENT, corrects=item,
        )
        self.add_obligation_line(correction, "1000", ObligationRequestLine.REDUCE)
        transition_obligation_request(correction, "submit", self.requester)
        transition_obligation_request(
            correction, "certify", self.certifier, "Reviewed pre-DV final-claim adjustment.", "OBR-2027-PAY-ADJ",
        )
        with self.assertRaisesMessage(ValidationError, "changed through a governed pre-DV correction"):
            prepare_voucher(
                case=case, actor=accountant, voucher_date=date(2027, 1, 20),
                gross_amount=Decimal("10000"), deductions=[], line_description="Synthetic claim",
                line_account_code="5-02-03", document_codes=[], expected_version=case.state_version,
                idempotency_key="stale-payable-dv",
            )

    def test_payable_relationships_recognition_modification_window_and_portable_export(self):
        authorization = self.make_executable_authority()
        first = self.make_obligation_request(
            authorization, reference="GSO-REL-001", total="10000",
        )
        self.add_obligation_line(first, "10000")
        transition_obligation_request(first, "submit", self.requester)
        first = transition_obligation_request(
            first, "certify", self.certifier, "Independent first relationship certification.", "OBR-2027-REL-001",
        )
        second = self.make_obligation_request(
            authorization, reference="GSO-REL-002", total="5000",
        )
        self.add_obligation_line(second, "5000")
        transition_obligation_request(second, "submit", self.requester)
        second = transition_obligation_request(
            second, "certify", self.certifier, "Independent second relationship certification.", "OBR-2027-REL-002",
        )

        self.requester.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_voucher_workbench", "initiate_payable_case", "view_voucher_audit"),
        ))
        accountant = self.employee(self.accounting_office, "relationship.accountant")
        accountant.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_voucher_workbench", "review_payable_intake", "prepare_disbursement_voucher"),
        ))
        release = FinanceConfigurationRelease.objects.create(
            department=self.accounting_office, code="f53-relationship-test", version=1,
            title="Synthetic F5.3 relationship setup", fiscal_year=2026, status="active",
            effective_from=date(2026, 1, 1), created_by=accountant, activated_by=accountant,
        )
        FinanceConfigurationItem.objects.create(
            department=self.accounting_office, release=release, category="transaction_type",
            code="ordinary-supplier-claim", version=1, label="Ordinary supplier claim",
            status="active", effective_from=date(2026, 1, 1), created_by=accountant,
        )
        variant = FinanceTransactionVariant.objects.create(
            department=self.accounting_office, release=release, code="ordinary-supplier-claim",
            label="Ordinary supplier claim", kind=FinanceTransactionVariant.ORDINARY_SUPPLIER,
            description="Synthetic governed multi-obligation and progress/final relationship route.",
            authority_reference="Synthetic reviewed COA/DBM/local relationship decision.",
            effective_from=date(2026, 1, 1), status="active", created_by=accountant,
        )
        rule = FinanceDocumentRule.objects.create(
            variant=variant, code="billing", label="Reviewed billing packet",
            evidence_kind=FinanceDocumentRule.INVOICE, required=True, waiver_allowed=False,
            authority_reference="Synthetic locally reviewed billing rule.", created_by=accountant,
        )
        party = FinanceParty.objects.create(
            department=self.accounting_office, release=release, code="f53-supplier", version=1,
            display_name="Synthetic Relationship Supplier", party_type=FinanceParty.SUPPLIER,
            effective_from=date(2026, 1, 1), status="active", created_by=accountant,
        )
        FinanceNumberingSequence.objects.create(
            department=self.accounting_office, release=release, fiscal_year=2026,
            document_type="disbursement-voucher", prefix="DV-F53-", padding=4,
            next_number=1, status="active", created_by=accountant,
        )

        invalid_final = create_payable_case_from_obligation(
            actor=self.requester, authoritative_obligation=second, payee=party,
            transaction_type="ordinary-supplier-claim", claim_reference="CLAIM-F53-INVALID-FINAL",
            invoice_number="", invoice_date=None, claim_amount=Decimal("4000"),
            initial_allocation_amount=Decimal("4000"), initial_relationship_type=PayableIntake.FINAL,
            procurement_reference="", delivery_reference="", inspection_acceptance_reference="",
            evidence_reference="Synthetic attempted final claim.", duplicate_review_note="",
            idempotency_key="f53-invalid-final",
        )
        invalid_final.refresh_from_db()
        self.assertEqual(invalid_final.obligation_binding_status, VoucherCase.BINDING_FAILED)
        self.assertIn("exact remaining", invalid_final.obligation_binding_error)
        self.assertFalse(PayableObligationAllocation.objects.filter(
            voucher_case_public_id=invalid_final.public_id, status=PayableObligationAllocation.ACTIVE,
        ).exists())

        partial_case = create_payable_case_from_obligation(
            actor=self.requester, authoritative_obligation=first, payee=party,
            transaction_type="ordinary-supplier-claim", claim_reference="CLAIM-F53-PARTIAL",
            invoice_number="INV-F53-A", invoice_date=date(2027, 1, 16), claim_amount=Decimal("4000"),
            initial_allocation_amount=Decimal("4000"), initial_relationship_type=PayableIntake.PARTIAL,
            procurement_reference="PO-F53", delivery_reference="DR-F53-A",
            inspection_acceptance_reference="", evidence_reference="Synthetic first partial packet.",
            duplicate_review_note="", idempotency_key="f53-partial-case",
        )
        consolidated = create_payable_case_from_obligation(
            actor=self.requester, authoritative_obligation=first, payee=party,
            transaction_type="ordinary-supplier-claim", claim_reference="CLAIM-F53-CONSOLIDATED",
            invoice_number="INV-F53-B", invoice_date=date(2027, 1, 17), claim_amount=Decimal("11000"),
            initial_allocation_amount=Decimal("6000"), initial_relationship_type=PayableIntake.FINAL,
            procurement_reference="PO-F53", delivery_reference="DR-F53-B",
            inspection_acceptance_reference="IAR-F53", evidence_reference="Synthetic consolidated packet.",
            duplicate_review_note="Different billing and delivery packet reviewed.",
            idempotency_key="f53-consolidated-case",
        )
        add_payable_obligation_allocation(
            case=consolidated, obligation=second, allocation_amount=Decimal("5000"),
            relationship_type=PayableIntake.FULL,
            reason="The second certified obligation supports the same consolidated billing packet.",
            actor=self.requester, expected_version=consolidated.state_version,
            idempotency_key="f53-add-second-obligation",
        )
        consolidated.refresh_from_db()
        summary = payable_relationship_summary(consolidated)
        self.assertEqual((summary["allocated_total"], summary["difference"]), (Decimal("11000"), Decimal("0")))
        self.assertTrue(summary["many_to_one"])
        self.assertTrue(summary["one_to_many"])
        self.assertEqual(consolidated.obligation.certified_amount, Decimal("11000"))
        self.assertEqual(consolidated.obligation.source_kind, "authoritative_f4_relationship_projection")
        self.assertEqual(
            PayableObligationAllocation.objects.filter(
                obligation=first, status=PayableObligationAllocation.ACTIVE,
            ).count(),
            2,
        )
        first.refresh_from_db()
        self.assertEqual(first.linked_voucher_case_public_id, partial_case.public_id)

        second_allocation = PayableObligationAllocation.objects.get(
            obligation=second, voucher_case_public_id=consolidated.public_id,
            status=PayableObligationAllocation.ACTIVE,
        )
        with self.assertRaises(IntegrityError), transaction.atomic(using="finance"):
            PayableObligationAllocation.objects.create(
                department_id=second.department_id, department_label=second.department_label,
                obligation=second, voucher_case_public_id=consolidated.public_id,
                voucher_reference_snapshot=consolidated.reference_code,
                relationship_type=PayableObligationAllocation.PARTIAL,
                allocated_amount=Decimal("1"), obligation_amount_snapshot=Decimal("5000"),
                obligation_checksum_snapshot=second_allocation.obligation_checksum_snapshot,
                version=99, status=PayableObligationAllocation.ACTIVE,
                change_reason="Synthetic race duplicate.", recorded_by_id=self.requester.pk,
                recorded_by_label=self.requester.username,
            )
        revise_payable_obligation_allocation(
            case=consolidated, allocation_public_id=second_allocation.public_id,
            revised_amount=Decimal("4000"), relationship_type=PayableIntake.PARTIAL,
            reason="Reviewed billing excludes one thousand while leaving capacity for a later claim.",
            actor=self.requester, expected_version=consolidated.state_version,
            idempotency_key="f53-revise-second-allocation",
        )
        consolidated.refresh_from_db()
        revise_payable_claim_control(
            case=consolidated, claim_amount=Decimal("10000"),
            reason="Claim control reconciled to the reviewed bill after allocation revision.",
            actor=self.requester, expected_version=consolidated.state_version,
            idempotency_key="f53-revise-claim",
        )
        consolidated.refresh_from_db()
        revised = PayableObligationAllocation.objects.get(
            obligation=second, voucher_case_public_id=consolidated.public_id,
            status=PayableObligationAllocation.ACTIVE,
        )
        second_allocation.refresh_from_db()
        self.assertEqual((second_allocation.status, revised.version, revised.allocated_amount), (
            PayableObligationAllocation.SUPERSEDED, 2, Decimal("4000"),
        ))
        self.assertEqual(payable_relationship_summary(consolidated)["difference"], Decimal("0"))
        revised.allocated_amount = Decimal("1")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            revised.full_clean()
        with self.assertRaisesMessage(ValidationError, "cannot be deleted"):
            revised.delete()

        pre_dv_adjustment = self.make_obligation_request(
            authorization, reference="GSO-REL-PRE-DV", total="1000",
            kind=ObligationRequest.ADJUSTMENT, corrects=second,
        )
        self.add_obligation_line(pre_dv_adjustment, "1000", ObligationRequestLine.OBLIGATE)
        transition_obligation_request(pre_dv_adjustment, "submit", self.requester)
        transition_obligation_request(
            pre_dv_adjustment, "certify", self.certifier,
            "Reviewed pre-DV increase while later claim capacity remains.", "OBR-2027-REL-PRE-DV",
        )
        with self.assertRaisesMessage(ValidationError, "changed through a governed pre-DV correction"):
            submit_payable_intake(
                case=consolidated, actor=self.requester, expected_version=consolidated.state_version,
                idempotency_key="f53-stale-before-reconcile",
            )
        reconcile_authoritative_obligation(
            case=consolidated, actor=self.requester, expected_version=consolidated.state_version,
            idempotency_key="f53-reconcile-adjustment",
        )
        consolidated.refresh_from_db()
        reconciled = PayableObligationAllocation.objects.get(
            obligation=second, voucher_case_public_id=consolidated.public_id,
            status=PayableObligationAllocation.ACTIVE,
        )
        self.assertEqual((reconciled.version, reconciled.obligation_amount_snapshot), (3, Decimal("6000")))
        self.assertEqual(payable_relationship_summary(consolidated)["difference"], Decimal("0"))

        evidence = consolidated.payable_document_evidence.get(source_rule=rule)
        record_payable_document_evidence(
            case=consolidated, evidence=evidence, actor=self.requester,
            status=PayableDocumentEvidence.PRESENT, evidence_reference="Synthetic reviewed bill INV-F53-B",
            decision_note="", expected_version=consolidated.state_version,
            idempotency_key="f53-evidence",
        )
        consolidated.refresh_from_db()
        submit_payable_intake(
            case=consolidated, actor=self.requester, expected_version=consolidated.state_version,
            idempotency_key="f53-submit",
        )
        consolidated.refresh_from_db()
        review_payable_intake(
            case=consolidated, actor=accountant, decision=PayableIntake.READY,
            reason="Independent review found a zero-difference relationship and complete evidence.",
            recognition_decision=PayableIntake.ACCRUE_BEFORE_SETTLEMENT,
            recognition_basis="Synthetic accepted accrual timing for this UAT variant.",
            obligation_adjustment_decision=PayableIntake.BALANCE_RETAINED,
            obligation_adjustment_basis="The second obligation retains one thousand for a later supported claim.",
            expected_version=consolidated.state_version, idempotency_key="f53-ready",
        )
        consolidated.refresh_from_db()
        self.assertEqual(consolidated.payable_intake.recognition_decision, PayableIntake.ACCRUE_BEFORE_SETTLEMENT)
        self.assertEqual(consolidated.payable_intake.obligation_adjustment_decision, PayableIntake.BALANCE_RETAINED)

        self.client.force_login(self.requester)
        with tempfile.TemporaryDirectory() as directory, override_settings(GRAND_EXPORT_ROOT=directory):
            response = self.client.get(reverse("vouchers:transaction_export", args=(consolidated.public_id,)))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            self.assertIn(b"obligation_allocation", response.content)
            self.assertIn(b"accrue_before_settlement", response.content)
            manifests = list(Path(directory).rglob("*.manifest.json"))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"], response["X-GRAND-Export-SHA256"])
            self.assertEqual(manifest["metadata"]["case_public_id"], str(consolidated.public_id))
            self.assertIn("finance-payable-transactions", manifest["relative_path"])

        prepare_voucher(
            case=consolidated, actor=accountant, voucher_date=date(2027, 1, 20),
            gross_amount=Decimal("10000"), deductions=[], line_description="Synthetic consolidated claim",
            line_account_code="5-02-03", document_codes=[], expected_version=consolidated.state_version,
            idempotency_key="f53-prepare-dv",
        )
        consolidated.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "DV or check has already been issued"):
            revise_payable_claim_control(
                case=consolidated, claim_amount=Decimal("9999"), reason="Too late.",
                actor=self.requester, expected_version=consolidated.state_version,
                idempotency_key="f53-too-late",
            )
        post_dv_correction = self.make_obligation_request(
            authorization, reference="GSO-REL-POST-DV", total="-1",
            kind=ObligationRequest.ADJUSTMENT, corrects=first,
        )
        self.add_obligation_line(post_dv_correction, "1", ObligationRequestLine.REDUCE)
        with self.assertRaisesMessage(ValidationError, "issued disbursement voucher"):
            transition_obligation_request(post_dv_correction, "submit", self.requester)

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
