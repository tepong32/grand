import json
import tempfile
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile

from .cutover_services import (
    REQUIRED_STAKEHOLDERS,
    build_cutover_evidence_package,
    cutover_readiness,
    decide_cutover,
    decide_stakeholder_acceptance,
    record_cutover_rollback,
    review_shadow_cycle,
    review_shadow_source_drift,
    stage_shadow_source_csv,
    start_shadow_cycle,
    submit_cutover_decision,
    submit_shadow_cycle,
)
from .models import (
    FinanceAuditEvent,
    FinanceCutoverDecision,
    FinanceShadowComparison,
    FinanceShadowCycle,
    FinanceShadowSourceVersion,
    FinanceStakeholderAcceptance,
)


EXPORT_ROOT = tempfile.mkdtemp(prefix="grand-cutover-export-tests-")
MEDIA_ROOT = tempfile.mkdtemp(prefix="grand-cutover-media-tests-")


@override_settings(GRAND_EXPORT_ROOT=EXPORT_ROOT, MEDIA_ROOT=MEDIA_ROOT)
class FinanceShadowCutoverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="accounting-cutover")
        cls.requesting = Department.objects.create(name="Engineering Office", slug="engineering-cutover")
        cls.manager = cls._employee("cutover.manager", cls.accounting)
        cls.reconciler = cls._employee("cutover.reconciler", cls.accounting)
        cls.authority = cls._employee("cutover.authority", cls.accounting)
        cls.requesting_reviewer = cls._employee("cutover.requesting", cls.requesting)
        cls.other_reviewer = cls._employee("cutover.stakeholder", cls.accounting)
        cls.outsider = cls._employee("cutover.outsider", cls.requesting)
        cls._grant(
            cls.manager, "manage_shadow_operation", "review_shadow_reconciliation",
            "authorize_finance_cutover", "view_finance_setup",
        )
        cls._grant(cls.reconciler, "review_shadow_reconciliation", "view_finance_setup")
        cls._grant(cls.authority, "authorize_finance_cutover", "view_finance_setup")

    @classmethod
    def _employee(cls, username, department):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="cutover-test-password",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    @classmethod
    def _grant(cls, user, *codenames):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="finance", codename__in=codenames))

    def _cycle(self):
        return FinanceShadowCycle.objects.create(
            department=self.accounting,
            code="fy-2027-dv-pilot",
            title="FY 2027 ordinary DV shadow pilot",
            fiscal_year=2027,
            enabled_scope="Engineering ordinary supplier DVs · General Fund · January 2027",
            source_system_label="Current signed register and redacted eGAPS export",
            source_extract_reference="Records packet SHADOW-001; redacted extract retained outside GRAND",
            source_checksum="a" * 64,
            source_schema_signature="b" * 64,
            planned_start=date(2027, 1, 4),
            planned_end=date(2027, 1, 29),
            created_by=self.manager,
        )

    def _unlocked_cycle(self, *, code="fy-2027-source-pilot", predecessor=None):
        return FinanceShadowCycle.objects.create(
            department=self.accounting,
            code=code,
            title="FY 2027 source staging pilot",
            fiscal_year=2027,
            enabled_scope="Redacted ordinary-DV comparison copy only",
            source_system_label="Current signed register and redacted export",
            source_extract_reference="Controlled comparison packet SRC-001",
            planned_start=date(2027, 2, 1),
            planned_end=date(2027, 2, 12),
            predecessor=predecessor,
            created_by=self.manager,
        )

    @staticmethod
    def _csv(name="source.csv", headings="case_id,amount,status", row="DV-001,1250.00,approved"):
        return SimpleUploadedFile(name, f"{headings}\n{row}\n".encode("utf-8"), content_type="text/csv")

    def _matched_comparison(self, cycle):
        comparison = FinanceShadowComparison(
            cycle=cycle,
            comparison_level=FinanceShadowComparison.REGISTER,
            control_code="dv-register-total",
            label="DV register total and case count",
            source_reference="Signed/redacted register SHADOW-001",
            grand_reference="GRAND pilot register run 17",
            source_amount=Decimal("125000.00"),
            grand_amount=Decimal("125000.00"),
            source_count=12,
            grand_count=12,
            outcome=FinanceShadowComparison.MATCHED,
            evidence_reference="Comparison worksheet CMP-001",
            created_by=self.manager,
        )
        comparison.full_clean(); comparison.save()
        return comparison

    def _reconciled_cycle(self):
        cycle = self._cycle()
        start_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        self._matched_comparison(cycle)
        submit_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        review_shadow_cycle(cycle, self.reconciler, accept=True, reason="Exact total/count and retained reference independently reviewed.")
        cycle.refresh_from_db()
        return cycle

    def _accepted_stakeholders(self, cycle):
        for kind in sorted(REQUIRED_STAKEHOLDERS):
            reviewer = self.requesting_reviewer if kind == FinanceStakeholderAcceptance.REQUESTING_OFFICE else self.other_reviewer
            acceptance = FinanceStakeholderAcceptance(
                cycle=cycle,
                stakeholder_kind=kind,
                office=self.requesting if kind == FinanceStakeholderAcceptance.REQUESTING_OFFICE else None,
                assigned_reviewer=reviewer,
                enabled_scope=cycle.enabled_scope,
                created_by=self.manager,
            )
            acceptance.full_clean(); acceptance.save()
            decide_stakeholder_acceptance(
                acceptance,
                reviewer,
                decision=FinanceStakeholderAcceptance.ACCEPTED,
                training_reference=f"{kind} role guide and supervisor exercise TRN-001",
                uat_reference=f"{kind} synthetic/redacted scenario UAT-001",
            )

    def test_comparisons_calculate_exact_differences_and_open_defects_block_submission(self):
        cycle = self._cycle()
        start_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        comparison = FinanceShadowComparison(
            cycle=cycle, comparison_level=FinanceShadowComparison.CASE,
            control_code="case-001", label="Case amount", source_reference="Source 1", grand_reference="GRAND 1",
            source_amount=Decimal("100.00"), grand_amount=Decimal("99.00"),
            outcome=FinanceShadowComparison.OPEN_DEFECT, explanation="One peso mapping difference under triage.",
            evidence_reference="DEF-001", defect_owner=self.manager, created_by=self.manager,
        )
        comparison.full_clean(); comparison.save()
        self.assertEqual(comparison.amount_difference, Decimal("-1.00"))
        with self.assertRaisesMessage(ValidationError, "open defect"):
            submit_shadow_cycle(cycle, self.manager)

        comparison.outcome = FinanceShadowComparison.MATCHED
        with self.assertRaisesMessage(ValidationError, "zero"):
            comparison.full_clean()

    def test_redacted_csv_is_versioned_and_grand_calculates_safe_metadata(self):
        cycle = self._unlocked_cycle()
        first = stage_shadow_source_csv(
            cycle, self.manager, self._csv(headings="case_id,payee_name,amount"),
            redaction_confirmed=True,
            redaction_note="Payee names replaced with controlled aliases; no bank details included.",
        )
        cycle.refresh_from_db()
        self.assertEqual(first.version, 1)
        self.assertEqual(first.row_count, 1)
        self.assertEqual(first.normalized_headers, ["case_id", "payee_name", "amount"])
        self.assertEqual(first.sensitive_header_warnings, ["payee_name"])
        self.assertEqual(len(first.source_checksum), 64)
        self.assertEqual(cycle.source_checksum, first.source_checksum)
        self.assertEqual(first.schema_comparison, FinanceShadowSourceVersion.BASELINE)
        with self.assertRaisesMessage(ValidationError, "Explain why"):
            stage_shadow_source_csv(
                cycle, self.manager, self._csv(name="replacement.csv"),
                redaction_confirmed=True, redaction_note="Still redacted.",
            )
        second = stage_shadow_source_csv(
            cycle, self.manager,
            self._csv(name="replacement.csv", headings="case_id,payee_name,amount", row="DV-002,Alias-2,900.00"),
            redaction_confirmed=True, redaction_note="Case IDs only; no direct identifiers retained.",
            change_reason="Corrected the locally approved extraction date and regenerated the copy.",
        )
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(second.version, 2)
        self.assertEqual(cycle.source_versions.count(), 2)
        start_shadow_cycle(cycle, self.manager)

    def test_malformed_or_unconfirmed_source_is_rejected(self):
        cycle = self._unlocked_cycle()
        with self.assertRaisesMessage(ValidationError, "Confirm redaction"):
            stage_shadow_source_csv(
                cycle, self.manager, self._csv(), redaction_confirmed=False, redaction_note="",
            )
        with self.assertRaisesMessage(ValidationError, "header defines"):
            stage_shadow_source_csv(
                cycle, self.manager,
                self._csv(headings="case_id,amount", row="DV-001,100.00,extra"),
                redaction_confirmed=True, redaction_note="Redacted comparison copy.",
            )
        self.assertFalse(cycle.source_versions.exists())

    def test_predecessor_schema_drift_blocks_start_until_independent_acceptance(self):
        predecessor = self._cycle()
        predecessor.status = FinanceShadowCycle.RECONCILED
        predecessor.save(update_fields=("status", "updated_at"))
        cycle = self._unlocked_cycle(code="fy-2027-drift-pilot", predecessor=predecessor)
        source = stage_shadow_source_csv(
            cycle, self.manager, self._csv(headings="case_id,amount,new_control_code"),
            redaction_confirmed=True,
            redaction_note="Direct identifiers removed; new control code contains no personal data.",
        )
        self.assertEqual(source.schema_comparison, FinanceShadowSourceVersion.DRIFT)
        self.assertEqual(source.review_status, FinanceShadowSourceVersion.PENDING)
        with self.assertRaisesMessage(ValidationError, "independent review"):
            start_shadow_cycle(cycle, self.manager)
        with self.assertRaisesMessage(ValidationError, "staged the source"):
            review_shadow_source_drift(source, self.manager, accept=True, reason="Self review")
        review_shadow_source_drift(
            source, self.reconciler, accept=True,
            reason="new_control_code maps to the reviewed DV classification and reconciles to retained control CMP-SCHEMA-01.",
        )
        start_shadow_cycle(cycle, self.manager)
        source.refresh_from_db()
        self.assertEqual(source.review_status, FinanceShadowSourceVersion.ACCEPTED)

    def test_evidence_export_includes_source_controls_but_not_csv_row_values(self):
        cycle = self._unlocked_cycle()
        stage_shadow_source_csv(
            cycle, self.manager, self._csv(row="SECRET-ROW-VALUE,1250.00,approved"),
            redaction_confirmed=True, redaction_note="Synthetic case identifier only.",
        )
        content, _filename, _receipt = build_cutover_evidence_package(cycle, self.manager)
        payload = json.loads(content)
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["cycle"]["schema_version"], 2)
        self.assertEqual(payload["cycle"]["source_versions"][0]["row_count"], 1)
        self.assertEqual(payload["cycle"]["source_versions"][0]["normalized_headers"], ["case_id", "amount", "status"])
        self.assertNotIn("SECRET-ROW-VALUE", content.decode("utf-8"))

    def test_submission_locks_checksum_and_requires_an_independent_reconciler(self):
        cycle = self._cycle()
        start_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        comparison = self._matched_comparison(cycle)
        submit_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, FinanceShadowCycle.RECONCILIATION_REVIEW)
        self.assertEqual(len(cycle.evidence_checksum), 64)
        with self.assertRaisesMessage(ValidationError, "preparer"):
            review_shadow_cycle(cycle, self.manager, accept=True, reason="Self-review is not allowed.")
        comparison.label = "Changed after submission"
        with self.assertRaisesMessage(ValidationError, "only while"):
            comparison.full_clean()
        review_shadow_cycle(cycle, self.reconciler, accept=True, reason="Independent zero-difference review complete.")
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, FinanceShadowCycle.RECONCILED)

    def test_only_named_stakeholder_can_decide_and_private_tutorial_progress_is_not_used(self):
        cycle = self._reconciled_cycle()
        acceptance = FinanceStakeholderAcceptance(
            cycle=cycle,
            stakeholder_kind=FinanceStakeholderAcceptance.REQUESTING_OFFICE,
            office=self.requesting,
            assigned_reviewer=self.requesting_reviewer,
            enabled_scope=cycle.enabled_scope,
            created_by=self.manager,
        )
        acceptance.full_clean(); acceptance.save()
        with self.assertRaises(PermissionDenied):
            decide_stakeholder_acceptance(
                acceptance, self.manager, decision=FinanceStakeholderAcceptance.ACCEPTED,
                training_reference="Training evidence", uat_reference="UAT evidence",
            )
        decide_stakeholder_acceptance(
            acceptance, self.requesting_reviewer,
            decision=FinanceStakeholderAcceptance.ACCEPTED,
            training_reference="Supervisor-observed role exercise TRN-ENG-01",
            uat_reference="Redacted ordinary-DV scripts UAT-ENG-01 through 04",
        )
        acceptance.refresh_from_db()
        self.assertEqual(acceptance.decided_by, self.requesting_reviewer)
        self.assertNotIn("tutorial", acceptance.training_evidence_reference.lower())
        with self.assertRaisesMessage(ValidationError, "already recorded"):
            decide_stakeholder_acceptance(
                acceptance, self.requesting_reviewer,
                decision=FinanceStakeholderAcceptance.REJECTED,
                training_reference="Changed", uat_reference="Changed", reason="Overwrite attempt",
            )

    def test_cutover_requires_all_seven_acceptances_and_separate_authority_then_can_roll_back(self):
        cycle = self._reconciled_cycle()
        decision = FinanceCutoverDecision.objects.create(
            cycle=cycle,
            authority_matrix_reference="Signed authority matrix AUTH-001",
            enabled_scope=cycle.enabled_scope,
            cutover_at=timezone.now() + timedelta(days=30),
            opening_reconciliation_reference="Opening and in-flight reconciliation OPEN-001",
            rollback_criteria="Rollback on unexplained ledger difference, critical outage, or failed recovery test.",
            legacy_read_only_retention_plan="Keep historical eGAPS/current-process records read-only under Records plan RET-001.",
            backup_recovery_evidence="Restore and continuity exercise BCP-001",
            prepared_by=self.manager,
        )
        with self.assertRaisesMessage(ValidationError, "every required stakeholder"):
            submit_cutover_decision(decision, self.manager)
        self._accepted_stakeholders(cycle)
        self.assertTrue(cutover_readiness(cycle)["ready"])
        submit_cutover_decision(decision, self.manager)
        decision.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "preparer"):
            decide_cutover(decision, self.manager, authorize=True, reason="Self-authorization attempt")
        decide_cutover(decision, self.authority, authorize=True, reason="Named authority approved the exact scope and effective date.")
        decision.refresh_from_db()
        self.assertTrue(decision.makes_grand_authoritative)
        record_cutover_rollback(decision, self.authority, reason="Recovery exercise exposed the recorded critical restore criterion.")
        decision.refresh_from_db()
        self.assertEqual(decision.status, FinanceCutoverDecision.ROLLED_BACK)
        self.assertFalse(decision.makes_grand_authoritative)
        self.assertTrue(FinanceAuditEvent.objects.filter(action="finance_cutover_authorized").exists())
        self.assertTrue(FinanceAuditEvent.objects.filter(action="finance_cutover_rolled_back").exists())

    def test_assigned_cross_office_reviewer_gets_read_only_cycle_access_and_export_is_archived(self):
        cycle = self._reconciled_cycle()
        acceptance = FinanceStakeholderAcceptance.objects.create(
            cycle=cycle,
            stakeholder_kind=FinanceStakeholderAcceptance.REQUESTING_OFFICE,
            office=self.requesting,
            assigned_reviewer=self.requesting_reviewer,
            enabled_scope=cycle.enabled_scope,
            created_by=self.manager,
        )
        self.client.force_login(self.requesting_reviewer)
        response = self.client.get(reverse("finance:shadow_cycle_detail", args=(cycle.pk,)))
        self.assertContains(response, cycle.enabled_scope)
        self.assertContains(response, "Record my decision")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("finance:shadow_cycle_detail", args=(cycle.pk,))).status_code, 403)

        content, filename, receipt = build_cutover_evidence_package(cycle, self.requesting_reviewer)
        payload = json.loads(content)
        self.assertEqual(filename, "fy-2027-dv-pilot-shadow-cutover-evidence.json")
        self.assertEqual(payload["cycle"]["code"], cycle.code)
        self.assertTrue(receipt["path"].exists())
        self.assertTrue(receipt["manifest_path"].exists())
        self.assertIn("finance-shadow-cutover", receipt["relative_path"])
        self.assertEqual(acceptance.decision, FinanceStakeholderAcceptance.PENDING)
