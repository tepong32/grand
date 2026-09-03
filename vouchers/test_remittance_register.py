from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceParty,
    FinancePostingRule, FinanceTransactionVariant,
)
from finance.work_tasks import finance_work_tasks
from profiles.models import EmployeeProfile

from .models import TreasuryRemittanceBatch, TreasuryRemittanceLine
from .remittance_register import remittance_action_queryset
from .remittances import (
    RemittanceWorkflowError, add_line, create_batch, release_batch, review_batch, submit_batch,
)
from .roles import FINANCE_UAT_VIEWER_GROUP


class RemittanceWorkRegisterTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="remit-register-accounting",
        )
        cls.treasury = Department.objects.create(
            name="Municipal Treasury Office", slug="remit-register-treasury",
        )
        cls.other = Department.objects.create(
            name="Other Treasury Office", slug="remit-register-other",
        )
        cls.preparer = cls._employee(
            "remit.register.preparer", cls.treasury,
            "view_remittance_workbench", "prepare_remittances", "approve_remittances",
            "release_remittances",
        )
        cls.reviewer = cls._employee(
            "remit.register.reviewer", cls.accounting,
            "view_remittance_workbench", "approve_remittances",
        )
        cls.outsider = cls._employee(
            "remit.register.outsider", cls.other,
            "view_remittance_workbench", "prepare_remittances", "release_remittances",
        )
        cls.uat = cls._employee(
            "remit.register.uat", cls.treasury,
            "view_remittance_workbench", "prepare_remittances", "approve_remittances",
            "release_remittances",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        cls.release = FinanceConfigurationRelease.objects.create(
            department=cls.accounting, code="remit-register-release", version=1,
            title="Synthetic remittance register release", fiscal_year=2026,
            status="active", effective_from=date(2026, 1, 1), created_by=cls.preparer,
        )
        cls.variant = FinanceTransactionVariant.objects.create(
            department=cls.accounting, release=cls.release, code="remit-register-variant",
            label="Synthetic withholding remittance", kind=FinanceTransactionVariant.ORDINARY_SUPPLIER,
            description="Synthetic remittance task route.", authority_reference="Synthetic reviewed authority.",
            effective_from=date(2026, 1, 1), status="active", created_by=cls.preparer,
        )
        cls.recipient = FinanceParty.objects.create(
            department=cls.accounting, release=cls.release, code="remit-register-agency", version=1,
            display_name="Synthetic Revenue Agency", party_type=FinanceParty.AGENCY,
            effective_from=date(2026, 1, 1), status="active", created_by=cls.preparer,
        )
        for category, code in (("fund", "GF"), ("bank_account", "GF-LBP")):
            FinanceConfigurationItem.objects.create(
                department=cls.accounting, release=cls.release, category=category,
                code=code, version=1, label=f"Synthetic {category}", status="active",
                effective_from=date(2026, 1, 1), created_by=cls.preparer,
            )
        cls.rule = FinancePostingRule.objects.create(
            variant=cls.variant, code="remit-register-rule", title="Synthetic remittance rule",
            event_kind=FinancePostingRule.REMITTANCE,
            recognition_point=FinancePostingRule.DEDUCTION_REMITTANCE,
            accounting_effect=FinancePostingRule.JOURNAL_ENTRY,
            description="Reduce withholding liabilities and credit the payment account.",
            authority_reference="Synthetic reviewed remittance basis.", created_by=cls.preparer,
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="remit-register-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _batch(self, reference, *, owner=None, status=TreasuryRemittanceBatch.DRAFT):
        owner = owner or self.treasury
        return TreasuryRemittanceBatch.objects.create(
            reference_code=reference, configuration_release=self.release,
            transaction_variant=self.variant, recipient_party=self.recipient,
            treasury_department=owner, finance_department_id=self.accounting.pk,
            finance_department_label=self.accounting.name, fund_code="GF",
            bank_account_code="GF-LBP", remittance_date=date(2026, 9, 3),
            payment_method="Electronic transfer", authority_reference="Synthetic authority.",
            evidence_reference="Synthetic retained schedule.", total_amount=Decimal("0.00"),
            status=status, created_by=self.preparer,
            submitted_by=self.preparer if status == TreasuryRemittanceBatch.FOR_REVIEW else None,
            posting_rule=self.rule if status in (
                TreasuryRemittanceBatch.FOR_REVIEW, TreasuryRemittanceBatch.APPROVED,
            ) else None,
            posting_rule_snapshot={"schema_version": 1} if status in (
                TreasuryRemittanceBatch.FOR_REVIEW, TreasuryRemittanceBatch.APPROVED,
            ) else {},
            posting_rule_checksum="a" * 64 if status in (
                TreasuryRemittanceBatch.FOR_REVIEW, TreasuryRemittanceBatch.APPROVED,
            ) else "",
        )

    def test_preparation_source_workspace_group_and_exact_task_share_office_scope(self):
        own = self._batch("REM-TASK-OWN")
        hidden = self._batch("REM-TASK-HIDDEN", owner=self.other)

        source, _selected, _spec = remittance_action_queryset(self.preparer, "preparation")
        self.client.force_login(self.preparer)
        workspace = self.client.get(
            reverse("vouchers:remittance_workspace"), {"attention": "preparation"},
        )
        my_work = self.client.get(reverse("finance_operations:my_work"))
        tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.treasury-remittance.preparation.v1"
        ]

        self.assertEqual(set(source), {own})
        self.assertEqual(set(workspace.context["batches"]), {own})
        group = next(row for row in my_work.context["groups"] if row["key"] == "remittance-preparation")
        self.assertEqual(group["count"], 1)
        self.assertEqual(len(tasks), 1)
        self.assertIn("Add at least one posted withholding balance", tasks[0]["action"])
        self.assertEqual(tasks[0]["state"], "Ready")

        TreasuryRemittanceBatch.objects.filter(pk=own.pk).update(total_amount=Decimal("0.01"))
        changed = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"treasury-remittance:{own.public_id}"
        )
        self.assertEqual(changed["task_id"], tasks[0]["task_id"])
        self.assertNotEqual(changed["source_version"], tasks[0]["source_version"])
        self.assertEqual(changed["state"], "Exception")
        self.assertIn("differ from the batch control total by -0.01", changed["exception"])

        cross_office_detail = self.client.get(hidden.get_absolute_url())
        self.assertEqual(cross_office_detail.status_code, 200)
        self.assertFalse(cross_office_detail.context["can_prepare"])
        self.assertFalse(cross_office_detail.context["can_release"])
        self.assertEqual(self.client.get(reverse(
            "vouchers:tax_filing_create", kwargs={"public_id": hidden.public_id},
        )).status_code, 403)

    def test_review_excludes_maker_but_allows_independent_cross_office_reviewer(self):
        batch = self._batch("REM-TASK-REVIEW", status=TreasuryRemittanceBatch.FOR_REVIEW)

        self.assertFalse(remittance_action_queryset(self.preparer, "review")[0].exists())
        self.assertEqual(set(remittance_action_queryset(self.reviewer, "review")[0]), {batch})
        task = next(
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["case_id"] == f"treasury-remittance:{batch.public_id}"
        )
        self.assertEqual(task["state"], "Exception")
        self.assertIn("Add at least one posted withholding balance", task["exception"])

    def test_direct_create_and_release_boundaries_reject_invalid_route_or_wrong_office(self):
        with self.assertRaisesMessage(RemittanceWorkflowError, "active fund and bank"):
            create_batch(
                actor=self.preparer, configuration_release=self.release,
                transaction_variant=self.variant, recipient_party=self.recipient,
                fund_code="GF", bank_account_code="NOT-CONFIGURED",
                remittance_date=date(2026, 9, 3), payment_method="Electronic transfer",
                authority_reference="Synthetic authority.", evidence_reference="Synthetic schedule.",
            )
        batch = self._batch("REM-TASK-RELEASE", status=TreasuryRemittanceBatch.APPROVED)
        with self.assertRaises(PermissionDenied):
            release_batch(
                batch=batch, actor=self.outsider, release_reference="BANK-REF",
                acknowledgement_reference="",
            )
        with self.assertRaises(PermissionDenied):
            submit_batch(batch=self._batch("REM-TASK-WRONG-SUBMIT"), actor=self.outsider)
        with self.assertRaises(PermissionDenied):
            add_line(
                batch=self._batch("REM-TASK-WRONG-LINE"), actor=self.outsider,
                choice_key="untrusted", amount=Decimal("1.00"), reason="Should be denied first.",
            )

    def test_missing_posted_liability_identity_stops_review_and_exact_task(self):
        batch = self._batch("REM-TASK-MISSING-LIABILITY", status=TreasuryRemittanceBatch.FOR_REVIEW)
        TreasuryRemittanceLine.objects.create(
            batch=batch, fund_code="GF", account_code="2-02-01",
            account_title="Synthetic tax payable", reference_key="missing-source",
            reference_label="Missing posted liability", deduction_code="EWT",
            source_as_of_date=batch.remittance_date,
            available_balance_snapshot=Decimal("1.00"), amount=Decimal("1.00"),
            source_checksum="b" * 64, change_reason="Synthetic stale-source fixture.",
            created_by=self.preparer,
        )
        TreasuryRemittanceBatch.objects.filter(pk=batch.pk).update(total_amount=Decimal("1.00"))
        batch.refresh_from_db()

        task = next(
            row for row in finance_work_tasks(self.reviewer)["tasks"]
            if row["case_id"] == f"treasury-remittance:{batch.public_id}"
        )
        self.assertEqual(task["state"], "Exception")
        self.assertIn("no longer exists", task["exception"])
        with self.assertRaisesMessage(RemittanceWorkflowError, "no longer exists"):
            review_batch(batch=batch, actor=self.reviewer, approve=True, reason="Synthetic review.")

    def test_uat_account_has_no_exact_remittance_actions(self):
        self._batch("REM-TASK-UAT")
        self.assertFalse(remittance_action_queryset(self.uat, "preparation")[0].exists())
        self.assertFalse(any(
            task["task_type"].startswith("finance.treasury-remittance.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))
