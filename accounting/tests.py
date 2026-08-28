from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connections
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile

from .access import can_post_journals, can_prepare_journals, can_view_accounting
from .models import (
    AccountingAuditEvent, AccountingPeriod, Fund, JournalEntry, JournalLine,
    LedgerAccount, ResponsibilityCenter,
)
from .services import post_entry, submit_entry


class StandaloneAccountingTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting_department = Department.objects.create(name="Municipal Accounting Office", slug="accounting")
        cls.other_department = Department.objects.create(name="Human Resources", slug="hr")
        cls.preparer = cls._employee("ledger.preparer", cls.accounting_department)
        cls.poster = cls._employee("ledger.poster", cls.accounting_department)
        cls.viewer = cls._employee("ledger.viewer", cls.accounting_department)
        cls.outsider = cls._employee("other.viewer", cls.other_department)
        cls.superuser = cls._employee("platform.admin", cls.accounting_department, is_superuser=True, is_staff=True)
        cls._grant(cls.preparer, "view_accounting_workspace", "prepare_journal_entries", "manage_accounting_setup")
        cls._grant(cls.poster, "view_accounting_workspace", "post_journal_entries", "view_general_ledger")
        cls._grant(cls.viewer, "view_accounting_workspace")
        cls._grant(cls.outsider, "view_accounting_workspace")

        owner = {"department_id": cls.accounting_department.pk, "department_label": cls.accounting_department.name}
        cls.period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2027, period_number=1, label="January", starts_on=date(2027, 1, 1), ends_on=date(2027, 1, 31),
        )
        cls.fund = Fund.objects.create(**owner, code="SYN-GF", name="Synthetic General Fund")
        cls.center = ResponsibilityCenter.objects.create(**owner, code="SYN-ACCT", name="Synthetic Accounting Office")
        cls.cash = LedgerAccount.objects.create(
            **owner, code="SYN-101", title="Synthetic Cash", account_type="asset", normal_balance="debit",
        )
        cls.revenue = LedgerAccount.objects.create(
            **owner, code="SYN-401", title="Synthetic Revenue", account_type="revenue", normal_balance="credit",
        )

    @classmethod
    def _employee(cls, username, department, **kwargs):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="accounting-test-password", **kwargs,
        )
        profile, _ = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    @classmethod
    def _grant(cls, user, *codenames):
        permissions = Permission.objects.filter(content_type__app_label="accounting", codename__in=codenames)
        if permissions.count() != len(codenames):
            raise AssertionError("Accounting permissions were not created in GRAND's core database.")
        user.user_permissions.add(*permissions)

    def _entry(self, *, reference="SYN-JEV-0001", balanced=True, creator=None):
        creator = creator or self.preparer
        entry = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference=reference,
            entry_date=date(2027, 1, 15),
            period=self.period,
            fund=self.fund,
            description="Synthetic standalone accounting test",
            created_by_id=creator.pk,
            created_by_label=creator.username,
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, responsibility_center=self.center,
            debit=Decimal("100.00"), credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=entry, sequence=2, account=self.revenue, responsibility_center=self.center,
            debit=Decimal("0.00"), credit=Decimal("100.00" if balanced else "90.00"),
        )
        return entry

    def test_accounting_models_are_routed_only_to_finance_database(self):
        self.assertEqual(JournalEntry.objects.db, "finance")
        self.assertEqual(AccountingPeriod.objects.db, "finance")
        self.assertEqual(Department.objects.db, "default")
        self.assertIn("accounting_journalentry", connections["finance"].introspection.table_names())
        self.assertNotIn("accounting_journalentry", connections["default"].introspection.table_names())

    def test_permissions_are_explicit_and_do_not_use_superuser_bypass(self):
        self.assertTrue(can_prepare_journals(self.preparer))
        self.assertFalse(can_post_journals(self.preparer))
        self.assertTrue(can_post_journals(self.poster))
        self.assertTrue(can_view_accounting(self.viewer))
        self.assertFalse(can_view_accounting(self.superuser))

    def test_balanced_entry_submits_and_independent_user_posts(self):
        entry = self._entry()
        submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.SUBMITTED)
        post_entry(entry, self.poster)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertEqual(entry.posted_by_id, self.poster.pk)
        self.assertEqual(list(entry.audit_events.values_list("action", flat=True)), ["posted", "submitted"])

    def test_unbalanced_entry_is_rejected_before_submission(self):
        entry = self._entry(reference="SYN-JEV-0002", balanced=False)
        with self.assertRaisesMessage(ValidationError, "must balance"):
            submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.DRAFT)
        self.assertFalse(AccountingAuditEvent.objects.filter(entry=entry).exists())

    def test_maker_checker_prevents_preparer_from_posting_own_entry(self):
        entry = self._entry(reference="SYN-JEV-0003")
        submit_entry(entry, self.preparer)
        with self.assertRaisesMessage(ValidationError, "preparer cannot post"):
            post_entry(entry, self.preparer)

    def test_posted_entry_and_lines_are_immutable(self):
        entry = self._entry(reference="SYN-JEV-0004")
        submit_entry(entry, self.preparer)
        post_entry(entry, self.poster)
        entry.description = "Attempted overwrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            entry.save()
        line = entry.lines.first()
        line.memo = "Attempted overwrite"
        with self.assertRaisesMessage(ValidationError, "only while the entry is a draft"):
            line.save()

    def test_workspace_and_entry_are_department_scoped(self):
        entry = self._entry(reference="SYN-JEV-0005")
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("accounting:workspace"))
        self.assertContains(response, entry.reference)
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("accounting:entry_detail", args=(entry.public_id,)))
        self.assertEqual(response.status_code, 404)

    def test_workflow_actions_are_post_only_and_role_bound(self):
        entry = self._entry(reference="SYN-JEV-0006")
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(reverse("accounting:entry_submit", args=(entry.public_id,))).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounting:entry_post", args=(entry.public_id,))).status_code, 403)

    def test_guided_forms_create_journal_and_line_in_finance_database(self):
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:entry_create"), {
            "reference": "SYN-JEV-FORM",
            "entry_date": "2027-01-20",
            "period": self.period.pk,
            "fund": self.fund.pk,
            "source_type": "manual",
            "description": "Synthetic form-created journal",
        })
        self.assertEqual(response.status_code, 302)
        entry = JournalEntry.objects.get(reference="SYN-JEV-FORM")
        response = self.client.post(reverse("accounting:line_create", args=(entry.public_id,)), {
            "sequence": 1,
            "account": self.cash.pk,
            "responsibility_center": self.center.pk,
            "debit": "25.00",
            "credit": "0.00",
            "memo": "Synthetic debit",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(entry.lines.filter(sequence=1, debit=Decimal("25.00")).exists())

    def test_period_close_is_blocked_until_unposted_work_is_cleared(self):
        self._entry(reference="SYN-JEV-OPEN")
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:period_close", args=(self.period.pk,)), follow=True)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, AccountingPeriod.OPEN)
        self.assertContains(response, "unposted journal")

    def test_ledger_shows_posted_entries_only(self):
        posted = self._entry(reference="SYN-JEV-POSTED")
        draft = self._entry(reference="SYN-JEV-DRAFT")
        submit_entry(posted, self.preparer)
        post_entry(posted, self.poster)
        self.client.force_login(self.poster)
        response = self.client.get(reverse("accounting:ledger"))
        self.assertContains(response, posted.reference)
        self.assertNotContains(response, draft.reference)
