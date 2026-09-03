from datetime import date
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile

from .close_services import (
    create_period_close_run, decide_period_close_policy, decide_period_close_run,
    decide_period_reopen, request_period_reopen, submit_period_close_policy,
    submit_period_close_run,
)
from .models import AccountingPeriod, Fund, JournalEntry, PeriodCloseEvent, PeriodClosePolicy, PeriodCloseRun


class GovernedPeriodCloseTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(name="Municipal Accounting Office", slug="accounting-close")
        cls.other_department = Department.objects.create(name="Other Office", slug="other-close")
        cls.preparer = cls._employee("close.preparer", cls.department)
        cls.reviewer = cls._employee("close.reviewer", cls.department)
        cls.policy_maker = cls._employee("close.policy.maker", cls.department)
        cls.policy_checker = cls._employee("close.policy.checker", cls.department)
        cls.outsider = cls._employee("close.outsider", cls.other_department)
        cls._grant(
            cls.preparer, "view_accounting_workspace", "prepare_period_close",
            "approve_period_close", "export_period_close",
        )
        cls._grant(cls.reviewer, "view_accounting_workspace", "approve_period_close", "reopen_period", "export_period_close")
        cls._grant(
            cls.policy_maker, "view_accounting_workspace", "manage_period_close_policies",
            "approve_period_close_policies",
        )
        cls._grant(cls.policy_checker, "view_accounting_workspace", "approve_period_close_policies")
        cls._grant(cls.outsider, "view_accounting_workspace", "prepare_period_close")
        owner = {"department_id": cls.department.pk, "department_label": cls.department.name}
        cls.january = AccountingPeriod.objects.create(
            **owner, fiscal_year=2028, period_number=1, label="January",
            starts_on=date(2028, 1, 1), ends_on=date(2028, 1, 31),
        )
        cls.february = AccountingPeriod.objects.create(
            **owner, fiscal_year=2028, period_number=2, label="February",
            starts_on=date(2028, 2, 1), ends_on=date(2028, 2, 29),
        )
        cls.fund = Fund.objects.create(**owner, code="GF", name="General Fund")

    @classmethod
    def _employee(cls, username, department):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="period-close-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    @classmethod
    def _grant(cls, user, *codenames):
        permissions = Permission.objects.filter(content_type__app_label="accounting", codename__in=codenames)
        if permissions.count() != len(codenames):
            raise AssertionError("Expected Accounting period-close permissions are missing.")
        user.user_permissions.add(*permissions)

    def _run(self, period=None):
        return create_period_close_run(
            period or self.january, self.department, self.preparer,
            adjustment_review_note="Reviewed the trial balance and adjusting entries; none are required.",
            evidence_reference="Accounting close binder / FY 2028 / period packet",
            preparer_note="Ready for independent review.",
        )

    def _close(self, period=None):
        run = self._run(period)
        submit_period_close_run(run, self.preparer)
        return decide_period_close_run(run, self.reviewer, approve=True, note="Evidence checked independently.")

    def test_observe_starter_explains_advisory_gaps_and_independent_approval_closes(self):
        run = self._run()
        self.assertTrue(run.checklist_snapshot["ready"])
        self.assertGreater(run.checklist_snapshot["warning_count"], 0)
        self.assertEqual(run.policy.status, PeriodClosePolicy.STARTER)
        with self.assertRaisesMessage(ValidationError, "cannot decide"):
            submit_period_close_run(run, self.preparer)
            decide_period_close_run(run, self.preparer, approve=True, note="Self approval")
        run.refresh_from_db()
        closed = decide_period_close_run(run, self.reviewer, approve=True, note="Evidence checked independently.")
        self.january.refresh_from_db()
        self.assertEqual(closed.status, PeriodCloseRun.CLOSED)
        self.assertEqual(self.january.status, AccountingPeriod.CLOSED)
        self.assertTrue(closed.checklist_checksum)
        self.assertTrue(closed.policy_checksum)

    def test_unposted_entry_blocks_submission_and_source_change_blocks_approval(self):
        run = self._run()
        submit_period_close_run(run, self.preparer)
        JournalEntry.objects.create(
            department_id=self.department.pk, department_label=self.department.name,
            reference="OPEN-JEV-1", entry_date=date(2028, 1, 15), period=self.january,
            fund=self.fund,
            description="Discovered adjustment", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        with self.assertRaisesMessage(ValidationError, "evidence changed"):
            decide_period_close_run(run, self.reviewer, approve=True, note="Attempt after source changed.")
        self.january.refresh_from_db()
        self.assertEqual(self.january.status, AccountingPeriod.OPEN)

    def test_reopen_is_independent_ordered_and_requires_successor_close_evidence(self):
        january_run = self._close(self.january)
        february_run = self._close(self.february)
        request_period_reopen(
            january_run, self.preparer, reason="A late adjustment was supported after close.",
            authority_reference="Municipal Accountant memo ACCT-2028-04 retained in close binder.",
        )
        with self.assertRaisesMessage(ValidationError, "later closed periods first"):
            decide_period_reopen(january_run, self.reviewer, approve=True, note="Reviewed the memo.")
        request_period_reopen(
            february_run, self.preparer, reason="February must reopen before January chronology can change.",
            authority_reference="Municipal Accountant memo ACCT-2028-05.",
        )
        decide_period_reopen(february_run, self.reviewer, approve=True, note="Chronology reviewed.")
        january_run.refresh_from_db()
        reopened = decide_period_reopen(january_run, self.reviewer, approve=True, note="Correction authority verified.")
        self.january.refresh_from_db()
        self.assertEqual(reopened.status, PeriodCloseRun.REOPENED)
        self.assertEqual(self.january.status, AccountingPeriod.OPEN)
        successor = self._run(self.january)
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.supersedes_id, january_run.pk)
        self.assertEqual(january_run.checklist_checksum, reopened.checklist_checksum)

    def test_enforced_policy_requires_local_acceptance_and_is_maker_checker_locked(self):
        starter_run = self._run()
        starter = starter_run.policy
        policy = PeriodClosePolicy.objects.create(
            department_id=self.department.pk, department_label=self.department.name,
            version=starter.version + 1, supersedes=starter,
            title="Locally reviewed mandatory close evidence", mode=PeriodClosePolicy.ENFORCE,
            description="Accepted period-close gates.",
            authority_reference="Local accounting close memorandum ACCT-2028-01.",
            local_acceptance_note="Accepted by the Municipal Accountant on 15 January 2028; signed copy in binder.",
            created_by_id=self.policy_maker.pk, created_by_label=self.policy_maker.username,
        )
        submit_period_close_policy(policy, self.policy_maker)
        with self.assertRaisesMessage(ValidationError, "cannot decide"):
            decide_period_close_policy(policy, self.policy_maker, approve=True, note="Self review")
        active = decide_period_close_policy(
            policy, self.policy_checker, approve=True, note="Authority and local acceptance checked.",
        )
        self.assertEqual(active.status, PeriodClosePolicy.ACTIVE)
        active.title = "Overwritten title"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            active.save()
        enforced_run = self._run(self.february)
        enforced = {item["code"]: item for item in enforced_run.checklist_snapshot["checks"]}
        self.assertEqual(enforced["subsidiary_control_reconciliation"]["status"], "failed")
        self.assertEqual(enforced["management_statements"]["status"], "failed")
        with self.assertRaisesMessage(ValidationError, "editable close checklist already exists"):
            self._run()

    def test_workspace_help_department_boundary_and_tracesync_export(self):
        run = self._close()
        self.client.force_login(self.preparer)
        workspace = self.client.get(reverse("accounting:period_close_workspace"))
        self.assertContains(workspace, "How to close an accounting period")
        self.assertContains(workspace, "data-target=\"#closeHelp\"")
        detail = self.client.get(reverse("accounting:period_close_detail", args=(run.public_id,)))
        self.assertContains(detail, "Pinned close checklist")
        self.client.force_login(self.outsider)
        hidden = self.client.get(reverse("accounting:period_close_detail", args=(run.public_id,)))
        self.assertEqual(hidden.status_code, 404)
        with tempfile.TemporaryDirectory() as export_root:
            with override_settings(GRAND_EXPORT_ROOT=Path(export_root)):
                self.client.force_login(self.preparer)
                response = self.client.get(reverse("accounting:period_close_export", args=(run.public_id,)))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-GRAND-Export-Archived"], "true")
                self.assertTrue((Path(export_root) / "GRAND_EXPORT_ROOT.json").exists())
                manifests = list(Path(export_root).rglob("*.manifest.json"))
                self.assertEqual(len(manifests), 1)
        self.assertTrue(PeriodCloseEvent.objects.filter(run=run, action="exported").exists())

    def test_close_attention_filter_and_my_work_use_the_same_source_records(self):
        submitted = self._run(self.january)
        submit_period_close_run(submitted, self.preparer)
        draft = self._run(self.february)
        self.client.force_login(self.preparer)

        source = self.client.get(
            reverse("accounting:period_close_workspace"), {"attention": "awaiting_review"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.context["selected_attention"], "awaiting_review")
        self.assertEqual(source.context["visible_count"], 1)
        self.assertEqual(list(source.context["runs"].values_list("pk", flat=True)), [submitted.pk])
        self.assertNotEqual(draft.pk, submitted.pk)
        group = next(item for item in work.context["groups"] if item["key"] == "period-close-review")
        self.assertEqual(group["count"], source.context["visible_count"])
        self.assertEqual(
            group["url"],
            f'{reverse("accounting:period_close_workspace")}?attention=awaiting_review',
        )
        self.assertContains(source, "does not assign work, close a period, or approve a reopen")
