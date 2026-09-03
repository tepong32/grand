import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile

from .discovery_services import review_discovery_decision, submit_discovery_decision
from .models import FinanceAuditEvent, FinanceDiscoveryDecision, FinanceShadowCycle


EXPORT_ROOT = tempfile.mkdtemp(prefix="grand-discovery-export-tests-")


@override_settings(GRAND_EXPORT_ROOT=EXPORT_ROOT)
class FinanceDiscoveryDecisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="accounting-discovery",
        )
        cls.budget = Department.objects.create(
            name="Municipal Budget Office", slug="budget-discovery",
        )
        cls.manager = cls._employee("discovery.manager", cls.accounting)
        cls.owner = cls._employee("discovery.owner", cls.budget)
        cls.reviewer = cls._employee("discovery.reviewer", cls.accounting)
        cls.outsider = cls._employee("discovery.outsider", cls.budget)
        cls.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="finance",
            codename__in=("manage_finance_discovery", "view_finance_setup"),
        ))

    @classmethod
    def _employee(cls, username, department):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="discovery-password",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    def _decision(self, **overrides):
        values = {
            "department": self.accounting,
            "code": "DEC-101",
            "version": 1,
            "phase": "F5",
            "question": "Which documentary route applies to emergency supplier claims?",
            "proposed_outcome": "Remain blocked until the current local authority and redacted route are reviewed.",
            "affected_scope": "Emergency supplier claims for the General Fund in FY 2027 only",
            "evidence_label": FinanceDiscoveryDecision.UNRESOLVED,
            "evidence_needed": "Current local emergency-procurement authority, document route, and accountable owner decision.",
            "blocks_affected_scope": True,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "due_date": date(2027, 1, 15),
            "created_by": self.manager,
        }
        values.update(overrides)
        return FinanceDiscoveryDecision.objects.create(**values)

    def test_unresolved_decision_can_be_independently_recorded_but_stays_scope_blocking(self):
        item = self._decision()

        submit_discovery_decision(item, self.owner)
        item.refresh_from_db()
        self.assertEqual(item.status, FinanceDiscoveryDecision.SUBMITTED)
        self.assertEqual(len(item.evidence_checksum), 64)
        review_discovery_decision(
            item,
            self.reviewer,
            record=True,
            reason="The missing authority is accurately stated; keep only the named emergency-claim scope blocked.",
        )
        item.refresh_from_db()

        self.assertEqual(item.status, FinanceDiscoveryDecision.RECORDED)
        self.assertTrue(item.is_current_blocker)
        self.assertEqual(item.reviewed_by, self.reviewer)
        item.affected_scope = "Attempted wider block"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            item.save()

    def test_recorded_successor_supersedes_without_rewriting_predecessor(self):
        predecessor = self._decision(code="DEC-102")
        submit_discovery_decision(predecessor, self.owner)
        review_discovery_decision(
            predecessor, self.reviewer, record=True,
            reason="Initial unresolved scope and evidence need independently recorded.",
        )
        predecessor.refresh_from_db()
        original_checksum = predecessor.evidence_checksum
        successor = self._decision(
            code=predecessor.code,
            version=2,
            predecessor=predecessor,
            change_reason="The retained local issuance and approved route are now available.",
            evidence_label=FinanceDiscoveryDecision.LGU_CONFIRMED,
            authority_evidence_reference="Approved local procedure FIN-PROC-2027-04",
            evidence_custody_reference="Records index FIN/2027/PROC/04",
            evidence_needed="The cited approval and redacted replay are sufficient for this exact scope.",
            proposed_outcome="Use the approved emergency supplier route for the exact FY 2027 scope.",
            blocks_affected_scope=False,
        )
        submit_discovery_decision(successor, self.owner)
        review_discovery_decision(
            successor, self.reviewer, record=True,
            reason="Reviewed the retained approval and exact affected-scope replay.",
        )
        predecessor.refresh_from_db()
        successor.refresh_from_db()

        self.assertEqual(predecessor.status, FinanceDiscoveryDecision.SUPERSEDED)
        self.assertEqual(predecessor.evidence_checksum, original_checksum)
        self.assertEqual(successor.status, FinanceDiscoveryDecision.RECORDED)
        self.assertFalse(successor.is_current_blocker)

    def test_lgu_confirmed_coverage_requires_a_retained_acceptance_example(self):
        with self.assertRaisesMessage(ValidationError, "acceptance example"):
            item = self._decision(
                code="DEC-EXAMPLE-REQ",
                coverage_kind=FinanceDiscoveryDecision.STEP,
                evidence_label=FinanceDiscoveryDecision.LGU_CONFIRMED,
                authority_evidence_reference="Retained local decision DISC-EXAMPLE-001",
                evidence_custody_reference="Restricted packet DISC/EXAMPLE/001",
                blocks_affected_scope=False,
            )
            submit_discovery_decision(item, self.owner)

    def test_owner_and_reviewer_have_narrow_workflow_access_and_outsider_does_not(self):
        item = self._decision(code="DEC-103")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("finance:discovery_workspace"))
        self.assertContains(response, item.code)
        self.assertNotContains(response, "Finance Setup Center")
        response = self.client.post(
            reverse("finance:discovery_decision_action", args=(item.public_id, "submit")),
        )
        self.assertRedirects(response, reverse("finance:discovery_decision_detail", args=(item.public_id,)))
        item.refresh_from_db()
        self.assertEqual(item.status, FinanceDiscoveryDecision.SUBMITTED)

        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse("finance:discovery_decision_action", args=(item.public_id, "record")),
            {"reason": "Named independent review confirms the scope must remain blocked."},
        )
        self.assertRedirects(response, reverse("finance:discovery_decision_detail", args=(item.public_id,)))
        item.refresh_from_db()
        self.assertEqual(item.status, FinanceDiscoveryDecision.RECORDED)

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("finance:discovery_decision_detail", args=(item.public_id,))).status_code,
            403,
        )

    def test_visible_decision_export_is_tracesync_archived_and_audited(self):
        item = self._decision(code="DEC-104")
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("finance:discovery_decision_export", args=(item.public_id,)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("finance-discovery-decisions", response["X-GRAND-Archive-Path"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("affected_scope", content)
        self.assertIn("Portable decision evidence", content)
        event = FinanceAuditEvent.objects.get(
            target_type="financediscoverydecision",
            target_id=str(item.pk),
            action="discovery_decision_exported",
        )
        self.assertEqual(event.snapshot["sha256"], response["X-GRAND-Archive-SHA256"])

    def test_manager_exports_filtered_department_register_without_cross_office_rows(self):
        included = self._decision(
            code="DEC-REGISTER-F5",
            proposed_outcome="=UNSAFE_SPREADSHEET_FORMULA()",
        )
        self._decision(code="DEC-REGISTER-F0", phase="F0")
        self._decision(
            department=self.budget,
            code="DEC-REGISTER-OTHER",
            owner=self.outsider,
            reviewer=self.owner,
            created_by=self.outsider,
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("finance:discovery_register_export"),
            {"phase": "F5", "status": FinanceDiscoveryDecision.DRAFT},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("finance-discovery-register", response["X-GRAND-Archive-Path"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("coverage_area", content)
        self.assertIn(included.code, content)
        self.assertIn("'=UNSAFE_SPREADSHEET_FORMULA()", content)
        self.assertNotIn("DEC-REGISTER-F0", content)
        self.assertNotIn("DEC-REGISTER-OTHER", content)
        event = FinanceAuditEvent.objects.get(
            target_type="financediscoveryregister",
            target_id=str(self.accounting.pk),
            action="discovery_register_exported",
        )
        self.assertEqual(event.snapshot["record_count"], 1)
        self.assertEqual(event.snapshot["phase_filter"], "F5")
        self.assertEqual(event.snapshot["sha256"], response["X-GRAND-Archive-SHA256"])

    def test_cross_office_assignee_cannot_bulk_export_department_register(self):
        self._decision(code="DEC-REGISTER-NARROW")
        self.client.force_login(self.owner)

        response = self.client.get(reverse("finance:discovery_register_export"))

        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_plain_language_draft_and_reasoned_successor_in_ui(self):
        self.client.force_login(self.manager)
        create_response = self.client.post(
            reverse("finance:discovery_decision_create"),
            {
                "cycle": "",
                "code": "dec-ui-105",
                "phase": "F0",
                "coverage_kind": FinanceDiscoveryDecision.GENERAL,
                "question": "Has the exact ordinary-DV discovery scope been confirmed?",
                "proposed_outcome": "Keep the named ordinary-DV scope blocked until the local workshop record is retained.",
                "affected_scope": "Ordinary supplier DVs for the General Fund in FY 2027 only",
                "evidence_label": FinanceDiscoveryDecision.UNRESOLVED,
                "authority_evidence_reference": "",
                "evidence_needed": "Retained workshop decision and accountable-owner confirmation.",
                "evidence_custody_reference": "",
                "blocks_affected_scope": "on",
                "owner": self.manager.pk,
                "reviewer": self.reviewer.pk,
                "due_date": "2027-01-20",
            },
        )
        item = FinanceDiscoveryDecision.objects.get(code="DEC-UI-105", version=1)
        self.assertRedirects(
            create_response,
            reverse("finance:discovery_decision_detail", args=(item.public_id,)),
        )
        submit_discovery_decision(item, self.manager)
        review_discovery_decision(
            item,
            self.reviewer,
            record=True,
            reason="The open question and limited scope are accurately recorded.",
        )
        item.refresh_from_db()

        successor_response = self.client.post(
            reverse("finance:discovery_decision_successor", args=(item.public_id,)),
            {
                "cycle": "",
                "phase": "F0",
                "coverage_kind": FinanceDiscoveryDecision.GENERAL,
                "question": item.question,
                "proposed_outcome": "Use the locally confirmed ordinary-DV route for this exact scope.",
                "affected_scope": item.affected_scope,
                "evidence_label": FinanceDiscoveryDecision.LGU_CONFIRMED,
                "authority_evidence_reference": "Retained workshop decision DISC-UI-105",
                "evidence_needed": "The cited workshop decision is sufficient for this exact scope.",
                "evidence_custody_reference": "Restricted Finance discovery packet DISC/UI/105",
                "owner": self.manager.pk,
                "reviewer": self.reviewer.pk,
                "due_date": "2027-01-21",
                "change_reason": "The named local confirmation has now been retained and reviewed.",
            },
        )
        successor = FinanceDiscoveryDecision.objects.get(code=item.code, version=2)
        self.assertRedirects(
            successor_response,
            reverse("finance:discovery_decision_detail", args=(successor.public_id,)),
        )
        self.assertEqual(successor.predecessor, item)
        self.assertEqual(successor.status, FinanceDiscoveryDecision.DRAFT)
        self.assertEqual(successor.change_reason, "The named local confirmation has now been retained and reviewed.")

    def test_coverage_starter_set_is_editable_complete_and_idempotent(self):
        cycle = FinanceShadowCycle.objects.create(
            department=self.accounting,
            code="fy-2027-discovery-starters",
            title="FY 2027 discovery coverage preparation",
            fiscal_year=2027,
            enabled_scope="General Fund ordinary supplier DVs for Engineering in January 2027",
            source_system_label="Current locally authoritative process",
            source_extract_reference="Restricted discovery packet DISC-START-001",
            planned_start=date(2027, 1, 4),
            planned_end=date(2027, 1, 29),
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("finance:discovery_coverage_starters"),
            {
                "cycle": cycle.pk,
                "owner": self.manager.pk,
                "reviewer": self.reviewer.pk,
                "due_date": "2027-01-12",
            },
        )
        self.assertRedirects(response, reverse("finance:discovery_workspace"))
        rows = FinanceDiscoveryDecision.objects.filter(cycle=cycle)
        self.assertEqual(rows.count(), 9)
        self.assertEqual(
            set(rows.values_list("coverage_kind", flat=True)),
            FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS | {
                FinanceDiscoveryDecision.SCOPE_ACCEPTANCE,
            },
        )
        self.assertTrue(all(item.status == FinanceDiscoveryDecision.DRAFT for item in rows))
        self.assertTrue(all(item.is_current_blocker for item in rows))
        self.assertEqual(
            FinanceAuditEvent.objects.filter(action="discovery_coverage_starter_created").count(),
            9,
        )
        workspace = self.client.get(reverse("finance:discovery_workspace"))
        self.assertContains(workspace, "Candidate-cycle discovery coverage")
        self.assertContains(workspace, "0 / 8")
        self.assertContains(workspace, "Whole scope")

        response = self.client.post(
            reverse("finance:discovery_coverage_starters"),
            {
                "cycle": cycle.pk,
                "owner": self.manager.pk,
                "reviewer": self.reviewer.pk,
            },
        )
        self.assertRedirects(response, reverse("finance:discovery_workspace"))
        self.assertEqual(FinanceDiscoveryDecision.objects.filter(cycle=cycle).count(), 9)
