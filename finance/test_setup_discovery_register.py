import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP

from .models import FinanceConfigurationRelease, FinanceDiscoveryDecision


EXPORT_ROOT = tempfile.mkdtemp(prefix="grand-setup-discovery-register-tests-")


@override_settings(GRAND_EXPORT_ROOT=EXPORT_ROOT)
class SetupAndDiscoveryWorkRegisterTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Accounting Office", slug="setup-discovery-accounting",
        )
        cls.other_accounting = Department.objects.create(
            name="Other Accounting Office", slug="setup-discovery-other-accounting",
        )
        cls.manager = cls._user(
            "setup.manager", cls.accounting,
            "finance.view_finance_setup", "finance.manage_finance_configuration",
            "finance.manage_finance_discovery",
        )
        cls.approver = cls._user(
            "setup.approver", cls.accounting,
            "finance.view_finance_setup", "finance.approve_finance_configuration",
        )
        cls.discovery_owner = cls._user("discovery.owner", cls.accounting)
        cls.discovery_reviewer = cls._user("discovery.reviewer", cls.other_accounting)
        cls.other_owner = cls._user("other.discovery.owner", cls.other_accounting)
        cls.other_reviewer = cls._user("other.discovery.reviewer", cls.other_accounting)
        cls.uat_user = cls._user(
            "setup.uat", cls.accounting,
            "finance.manage_finance_configuration", "finance.approve_finance_configuration",
        )
        cls.uat_user.groups.add(Group.objects.create(name=FINANCE_UAT_VIEWER_GROUP))

        today = timezone.localdate()
        cls.draft_release = cls._release("SETUP-DRAFT", cls.accounting, cls.manager, "draft", today)
        cls.hidden_draft_release = cls._release(
            "SETUP-HIDDEN-DRAFT", cls.other_accounting, cls.manager, "draft", today,
        )
        cls.submitted_release = cls._release(
            "SETUP-SUBMITTED", cls.accounting, cls.manager, "submitted", today,
        )
        cls.future_release = cls._release(
            "SETUP-FUTURE", cls.accounting, cls.manager, "approved", today + timedelta(days=30),
        )
        cls.current_approved_release = cls._release(
            "SETUP-CURRENT", cls.accounting, cls.manager, "approved", today,
        )
        cls.current_scheduled_release = cls._release(
            "SETUP-SCHEDULED", cls.accounting, cls.manager, "scheduled", today - timedelta(days=1),
        )
        cls.expired_release = cls._release(
            "SETUP-EXPIRED", cls.accounting, cls.manager, "approved",
            today - timedelta(days=30), effective_to=today - timedelta(days=1),
        )

        cls.draft_decision = cls._decision(
            "DISC-DRAFT", cls.accounting, cls.discovery_owner, cls.discovery_reviewer,
            FinanceDiscoveryDecision.DRAFT, cls.discovery_owner,
        )
        cls.returned_decision = cls._decision(
            "DISC-RETURNED", cls.accounting, cls.discovery_owner, cls.discovery_reviewer,
            FinanceDiscoveryDecision.RETURNED, cls.discovery_owner,
        )
        cls.review_decision = cls._decision(
            "DISC-REVIEW", cls.accounting, cls.discovery_owner, cls.discovery_reviewer,
            FinanceDiscoveryDecision.SUBMITTED, cls.discovery_owner,
            submitted_by=cls.discovery_owner,
        )
        cls.hidden_decision = cls._decision(
            "DISC-HIDDEN", cls.other_accounting, cls.other_owner, cls.other_reviewer,
            FinanceDiscoveryDecision.DRAFT, cls.other_owner,
        )
        cls.hidden_review = cls._decision(
            "DISC-HIDDEN-REVIEW", cls.other_accounting, cls.other_owner, cls.other_reviewer,
            FinanceDiscoveryDecision.SUBMITTED, cls.other_owner,
            submitted_by=cls.other_owner,
        )

    @staticmethod
    def _user(username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="test-password",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user = get_user_model().objects.get(pk=user.pk)
        for permission in permissions:
            app_label, codename = permission.split(".", 1)
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label=app_label, codename=codename,
            ))
        return user

    @staticmethod
    def _release(code, department, creator, status, effective_from, effective_to=None):
        return FinanceConfigurationRelease.objects.create(
            department=department, code=code.lower(), title=code, fiscal_year=2027,
            status=status, effective_from=effective_from, effective_to=effective_to,
            created_by=creator,
        )

    @staticmethod
    def _decision(code, department, owner, reviewer, status, creator, submitted_by=None):
        return FinanceDiscoveryDecision.objects.create(
            department=department, code=code, phase="F0",
            question=f"What evidence resolves {code}?",
            proposed_outcome="Keep only the named synthetic scope controlled.",
            affected_scope=f"Synthetic scope for {code}",
            evidence_label=FinanceDiscoveryDecision.UNRESOLVED,
            evidence_needed="Synthetic retained evidence.",
            blocks_affected_scope=True,
            owner=owner, reviewer=reviewer, status=status,
            created_by=creator, submitted_by=submitted_by,
            submitted_at=timezone.now() if submitted_by else None,
        )

    def test_setup_preparation_is_exact_and_office_scoped(self):
        self.client.force_login(self.manager)

        source = self.client.get(reverse("finance:workspace"), {"attention": "needs_preparation"})
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.context["visible_count"], 1)
        self.assertEqual(list(source.context["releases"]), [self.draft_release])
        group = next(item for item in work.context["groups"] if item["key"] == "setup-release-preparation")
        self.assertEqual(group["count"], source.context["visible_count"])
        self.assertEqual(group["url"], f'{reverse("finance:workspace")}?attention=needs_preparation')
        self.assertNotContains(source, "SETUP-HIDDEN-DRAFT")
        self.assertNotContains(source, "Submitted releases awaiting independent review")

    def test_setup_review_schedule_and_activation_are_separate_exact_queues(self):
        self.client.force_login(self.approver)

        expectations = {
            "awaiting_review": ("setup-release-review", 1, self.submitted_release),
            "ready_to_schedule": ("setup-release-scheduling", 1, self.future_release),
            "ready_to_activate": ("setup-release-activation", 2, None),
        }
        work = self.client.get(reverse("finance_operations:my_work"))
        groups = {item["key"]: item for item in work.context["groups"]}

        for attention, (key, count, expected_release) in expectations.items():
            source = self.client.get(reverse("finance:workspace"), {"attention": attention})
            self.assertEqual(source.context["visible_count"], count)
            self.assertEqual(groups[key]["count"], count)
            self.assertEqual(groups[key]["url"], f'{reverse("finance:workspace")}?attention={attention}')
            if expected_release:
                self.assertEqual(list(source.context["releases"]), [expected_release])
        activation = self.client.get(
            reverse("finance:workspace"), {"attention": "ready_to_activate"},
        )
        self.assertCountEqual(
            list(activation.context["releases"]),
            [self.current_approved_release, self.current_scheduled_release],
        )
        self.assertNotContains(activation, "SETUP-EXPIRED")

    def test_discovery_preparation_uses_owner_or_department_manager_scope(self):
        self.client.force_login(self.manager)

        source = self.client.get(
            reverse("finance:discovery_workspace"), {"attention": "needs_preparation"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertCountEqual(
            list(source.context["decisions"]), [self.draft_decision, self.returned_decision],
        )
        group = next(item for item in work.context["groups"] if item["key"] == "discovery-preparation")
        self.assertEqual(group["count"], len(source.context["decisions"]))
        self.assertEqual(
            group["url"],
            f'{reverse("finance:discovery_workspace")}?attention=needs_preparation',
        )
        self.assertNotContains(source, "DISC-HIDDEN")
        exported = self.client.get(
            reverse("finance:discovery_register_export"), {"attention": "needs_preparation"},
        ).content.decode("utf-8-sig")
        self.assertIn("DISC-DRAFT", exported)
        self.assertIn("DISC-RETURNED", exported)
        self.assertNotIn("DISC-REVIEW", exported)
        self.assertNotIn("DISC-HIDDEN", exported)

    def test_named_discovery_reviewer_gets_only_independently_actionable_submissions(self):
        self.client.force_login(self.discovery_reviewer)

        source = self.client.get(
            reverse("finance:discovery_workspace"), {"attention": "my_reviews"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertEqual(list(source.context["decisions"]), [self.review_decision])
        group = next(item for item in work.context["groups"] if item["key"] == "discovery-review")
        self.assertEqual(group["count"], 1)
        self.assertEqual(group["count"], len(source.context["decisions"]))
        self.assertContains(source, "assigned to the signed-in reviewer")
        self.assertNotContains(source, "DISC-HIDDEN-REVIEW")

    def test_uat_viewer_does_not_receive_setup_or_discovery_action_groups(self):
        self.client.force_login(self.uat_user)

        work = self.client.get(reverse("finance_operations:my_work"))
        setup = self.client.get(reverse("finance:workspace"), {"attention": "needs_preparation"})

        keys = {item["key"] for item in work.context["groups"]}
        self.assertFalse(any(key.startswith("setup-release-") for key in keys))
        self.assertFalse(any(key.startswith("discovery-") for key in keys))
        self.assertEqual(setup.context["visible_count"], 0)
