from datetime import date
from decimal import Decimal
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import AccountingPeriod, FiscalYear, JournalEntry, JournalLine, LedgerAccount
from accounting.services import submit_entry, post_entry, create_reversal
from . import tests as fixtures
from .models import BudgetCall, BudgetVersion, BudgetAuditEvent, AppropriationAuthorization
from .planning_context import build_context, set_estimate, displayed_context
from .services import transition_version, consolidate_versions, transition_authorization


class PlanningContextTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.AnnualBudgetPreparationTests.setUpTestData.__func__)
    employee = classmethod(fixtures.AnnualBudgetPreparationTests.employee.__func__)
    make_call = fixtures.AnnualBudgetPreparationTests.make_call
    make_version = fixtures.AnnualBudgetPreparationTests.make_version
    add_line = fixtures.AnnualBudgetPreparationTests.add_line
    add_ceiling = fixtures.AnnualBudgetPreparationTests.add_ceiling
    make_authorized_appropriation = fixtures.AnnualBudgetPreparationTests.make_authorized_appropriation

    def setUp(self):
        self.clock = patch("django.utils.timezone.localdate", return_value=date(2026, 9, 18))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.call = self.make_call(BudgetCall.PUBLISHED)
        self.add_ceiling(self.call, "1000000")
        self.version = self.make_version(self.call)
        self.line = self.add_line(self.version, "1000")
        self.maker = self.employee(self.accounting_office, "history.maker")
        self.checker = self.employee(self.accounting_office, "history.checker")
        for user, code in ((self.maker, "prepare_journal_entries"), (self.checker, "post_journal_entries")):
            user.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename=code))
        self.offset = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code="HIST-OFFSET", title="Synthetic offset",
            account_type="equity", normal_balance="credit")

    def journal(self, reference, when, amount, source_type="manual"):
        owner = {"department_id": self.accounting_office.pk, "department_label": self.accounting_office.name}
        period, _ = AccountingPeriod.objects.get_or_create(**owner, fiscal_year=when.year, period_number=when.month,
            defaults={"label": "Synthetic history", "starts_on": when.replace(day=1), "ends_on": when})
        entry = JournalEntry.objects.create(**owner, period=period, fund=self.fund, reference=reference,
            entry_date=when, description="Synthetic dated historical expense", source_type=source_type,
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        JournalLine.objects.create(entry=entry, sequence=1, account=self.account, responsibility_center=self.center, debit=amount)
        JournalLine.objects.create(entry=entry, sequence=2, account=self.offset, credit=amount)
        submit_entry(entry, self.maker)
        return post_entry(entry, self.checker)

    def estimate(self, amount="40"):
        return set_estimate(version=self.version, line_id=self.line.pk, actor=self.preparer,
            amount=Decimal(amount), as_of=date(2026, 8, 1), basis="Synthetic department forecast reference")

    def test_dated_activity_grouping_closing_reversal_and_missing_states(self):
        self.journal("PAST", date(2025, 12, 31), Decimal("120"))
        current = self.journal("HALF", date(2026, 6, 30), Decimal("60"))
        closing = self.journal("CLOSING", date(2026, 6, 30), Decimal("500"), JournalEntry.CLOSING)
        reversal = create_reversal(closing, self.maker, reference="REOPEN", period=closing.period,
                                   entry_date=date(2026, 6, 30), reason="Synthetic reopen")
        submit_entry(reversal, self.maker); post_entry(reversal, self.checker)
        self.journal("LATER", date(2026, 9, 18), Decimal("900"))
        self.estimate()
        second = self.add_line(self.version, "2000")
        context = build_context(self.version, self.preparer)
        self.assertEqual(len(context["rows"]), 1)
        row = context["rows"][0]
        self.assertEqual(Decimal(row["prior_amount"]), Decimal("120"))
        self.assertEqual(Decimal(row["half_amount"]), Decimal("60"))
        self.assertEqual(Decimal(row["proposed"]), Decimal("3000"))
        self.assertIsNone(row["estimate"])
        self.assertIsNone(row["indicative_total"])
        self.assertEqual(len(row["excluded_sources"]), 2)
        self.assertEqual(row["half_sources"][0]["journal"], str(current.public_id))
        set_estimate(version=self.version, line_id=second.pk, actor=self.preparer, amount=Decimal("0"),
                     as_of=date(2026, 8, 1), basis="Explicit zero supported")
        self.assertEqual(Decimal(build_context(self.version, self.preparer)["rows"][0]["indicative_total"]), Decimal("100"))

    def test_submission_retains_context_and_export_after_later_posting(self):
        self.journal("BEFORE", date(2026, 6, 30), Decimal("60"))
        self.estimate()
        self.version = transition_version(self.version, "submit", self.preparer)
        captured = self.version.planning_context_snapshot
        self.journal("AFTER", date(2026, 6, 30), Decimal("90"))
        self.assertEqual(displayed_context(self.version, self.reviewer), captured)
        with self.assertRaises(ValidationError):
            self.estimate("41")
        self.version = transition_version(self.version, "approve", self.reviewer, "Reviewed context; actual certification remains separate")
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("budget:version_detail", args=[self.version.public_id]))
        self.assertContains(response, "Historical decision context")
        self.assertEqual(response.context["planning"], captured)
        with tempfile.TemporaryDirectory() as folder, override_settings(GRAND_EXPORT_ROOT=folder):
            exported = self.client.get(reverse("budget:planning_context_export", args=[self.version.public_id]))
            self.assertEqual(exported.status_code, 200)
            self.assertContains(exported, "BEFORE")
            self.assertNotContains(exported, "AFTER")
        consolidated = consolidate_versions(sources=[self.version], user=self.reviewer, title="Synthetic executive", change_explanation="Retain estimate basis")
        self.assertEqual(consolidated.lines.get().second_half_estimate, Decimal("40"))

    def test_empty_evidence_is_not_zero_and_legacy_approval_is_not_backfilled(self):
        row = build_context(self.version, self.preparer)["rows"][0]
        self.assertIsNone(row["prior_amount"])
        self.assertIsNone(row["half_amount"])
        self.assertIsNone(row["original_authority"])
        BudgetVersion.objects.filter(pk=self.version.pk).update(status=BudgetVersion.APPROVED)
        self.version.refresh_from_db()
        self.assertIsNone(displayed_context(self.version, self.preparer))

    def test_original_authority_is_dated_and_ambiguous_roots_are_not_added(self):
        self.fiscal_year = FiscalYear.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, year=2026, label="Current planning year",
            starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31), business_date=date(2026, 1, 1), status=FiscalYear.APPROVED)
        def authorize(reference, effective):
            version = self.make_version(self.make_call(BudgetCall.PUBLISHED))
            version.kind, version.status = BudgetVersion.FINAL, BudgetVersion.APPROVED
            version.save()
            self.add_line(version, "500")
            authority = AppropriationAuthorization.objects.create(department_id=self.budget_office.pk,
                department_label=self.budget_office.name, version=version, authority_type=AppropriationAuthorization.ORDINANCE,
                ordinance_number=reference, ordinance_date=date(2025, 12, 1), effectivity_date=effective,
                review_status=AppropriationAuthorization.FAVORABLE, review_reference="Synthetic dated review",
                review_date=date(2025, 12, 15), evidence_reference="Synthetic accepted ordinance",
                signed_control_total=Decimal("500"), created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
            authority = transition_authorization(authority, "submit", self.preparer)
            return transition_authorization(authority, "authorize", self.authorizer, "Independent synthetic authority")
        authorize("FUTURE", date(2026, 12, 31))
        self.assertIsNone(build_context(self.version, self.preparer)["rows"][0]["original_authority"])
        authority = authorize("CURRENT", date(2026, 1, 1))
        row = build_context(self.version, self.preparer)["rows"][0]
        self.assertEqual(Decimal(row["original_authority"]), Decimal("500"))
        self.assertEqual(row["authorities"][0]["id"], str(authority.public_id))
        authorize("SECOND-ROOT", date(2026, 1, 1))
        row = build_context(self.version, self.preparer)["rows"][0]
        self.assertIsNone(row["original_authority"])
        self.assertIn("Multiple", row["authority_state"])

    def test_invalid_estimates_scope_uat_and_tampered_submission(self):
        with self.assertRaises(PermissionDenied):
            build_context(self.version, self.outsider)
        with self.assertRaises(ValidationError):
            set_estimate(version=self.version, line_id=self.line.pk, actor=self.preparer,
                amount=Decimal("-1"), as_of=date(2026, 8, 1), basis="Invalid")
        with self.assertRaises(ValidationError):
            set_estimate(version=self.version, line_id=self.line.pk, actor=self.preparer,
                amount=Decimal("1"), as_of=date(2027, 8, 1), basis="Future")
        self.version = transition_version(self.version, "submit", self.preparer)
        BudgetVersion.objects.filter(pk=self.version.pk).update(planning_context_snapshot={})
        with self.assertRaisesMessage(ValidationError, "differs"):
            transition_version(self.version, "approve", self.reviewer, "Must not pass")
        self.version = transition_version(self.version, "return", self.reviewer, "Correct retained context")
        group, _ = Group.objects.get_or_create(name="Finance UAT Viewer")
        self.preparer.groups.add(group)
        with self.assertRaises(PermissionDenied):
            self.estimate()
