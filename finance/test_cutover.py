import csv
import io
import json
import tempfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from reporting.form_acceptance_services import checksum, file_checksum, form_snapshot
from reporting.models import FinanceLocalFormAcceptance

from .acceptance_services import build_field_acceptance_board
from .cutover_services import (
    REQUIRED_NONFUNCTIONAL_EXERCISES,
    REQUIRED_STAKEHOLDERS,
    build_cutover_evidence_package,
    cutover_readiness,
    decide_cutover,
    decide_stakeholder_acceptance,
    record_cutover_rollback,
    record_shadow_defect_escalation,
    review_cutover_readiness_exercise,
    review_cutover_readiness_plan,
    review_cutover_qualification_evidence,
    review_cutover_qualification_plan,
    review_shadow_cycle,
    review_reconciliation_plan,
    review_reconciliation_run,
    review_shadow_defect_resolution,
    review_shadow_source_drift,
    register_shadow_defect,
    schedule_cutover_readiness_exercise,
    open_next_reconciliation_run,
    stage_shadow_source_csv,
    start_shadow_cycle,
    submit_cutover_decision,
    submit_cutover_readiness_exercise,
    submit_cutover_readiness_plan,
    submit_cutover_qualification_evidence,
    submit_cutover_qualification_plan,
    submit_reconciliation_plan,
    submit_reconciliation_run,
    submit_shadow_cycle,
    submit_shadow_defect_resolution,
)
from .discovery_services import review_discovery_decision, submit_discovery_decision
from .models import (
    FinanceAuditEvent,
    FinanceCutoverDecision,
    FinanceCutoverQualificationEvidence,
    FinanceCutoverQualificationForm,
    FinanceCutoverQualificationPlan,
    FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan,
    FinanceDiscoveryDecision,
    FinanceRecoveryRehearsalEvidence,
    FinanceShadowComparison,
    FinanceShadowCycle,
    FinanceShadowDefect,
    FinanceShadowReconciliationPlan,
    FinanceShadowReconciliationRun,
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

    def _cycle(self, *, code="fy-2027-dv-pilot", predecessor=None, run_kind=FinanceShadowCycle.SHADOW):
        cycle = FinanceShadowCycle.objects.create(
            department=self.accounting,
            code=code,
            title="FY 2027 ordinary DV shadow pilot",
            fiscal_year=2027,
            enabled_scope="Engineering ordinary supplier DVs · General Fund · January 2027",
            source_system_label="Current signed register and redacted eGAPS export",
            source_extract_reference="Records packet SHADOW-001; redacted extract retained outside GRAND",
            source_checksum="a" * 64,
            source_schema_signature="b" * 64,
            run_kind=run_kind,
            planned_start=date(2027, 1, 4) if predecessor is None else date(2027, 2, 1),
            planned_end=date(2027, 1, 29) if predecessor is None else date(2027, 2, 26),
            predecessor=predecessor,
            created_by=self.manager,
        )
        self._approve_plan(cycle)
        return cycle

    def _unlocked_cycle(self, *, code="fy-2027-source-pilot", predecessor=None):
        cycle = FinanceShadowCycle.objects.create(
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
        self._approve_plan(cycle)
        return cycle

    def _approve_plan(self, cycle, *, minimum_runs=1, cadence=FinanceShadowReconciliationPlan.CALENDAR_DAILY):
        first_due = timezone.make_aware(datetime.combine(cycle.planned_start, time(17, 0)))
        plan = FinanceShadowReconciliationPlan.objects.create(
            cycle=cycle, cadence=cadence, first_due_at=first_due, grace_minutes=60,
            minimum_reviewed_runs=minimum_runs,
            enabled_transaction_types="Ordinary supplier DV controls in the cycle's written scope",
            local_authority_reference="Retained pilot direction PILOT-PLAN-001",
            local_acceptance_note="Accounting, Budget, and Treasury workshop accepted the synthetic cadence for UAT only.",
            critical_resolution_hours=4, critical_escalation_route="Finance process owner and municipal management",
            high_resolution_hours=8, high_escalation_route="Accounting reviewer and affected office head",
            medium_resolution_hours=24, medium_escalation_route="Finance configuration manager",
            low_resolution_hours=72, low_escalation_route="Assigned defect owner and team lead",
            created_by=self.manager,
        )
        submit_reconciliation_plan(plan, self.manager)
        review_reconciliation_plan(
            plan, self.reconciler, approve=True,
            reason="Reviewed synthetic cadence, minimum runs, correction targets, and named local escalation routes.",
        )
        return FinanceShadowReconciliationPlan.objects.get(pk=plan.pk)

    def _review_current_run(self, cycle):
        run = open_next_reconciliation_run(cycle, self.manager)
        submit_reconciliation_run(run, self.manager)
        review_reconciliation_run(
            run, self.reconciler, accept=True,
            reason="Compared current exact controls and registered exceptions against the retained run snapshot.",
        )
        return FinanceShadowReconciliationRun.objects.get(pk=run.pk)

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

    def _reconciled_cycle(self, *, code="fy-2027-dv-pilot", predecessor=None, run_kind=FinanceShadowCycle.SHADOW):
        cycle = self._cycle(code=code, predecessor=predecessor, run_kind=run_kind)
        start_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        self._matched_comparison(cycle)
        self._review_current_run(cycle)
        submit_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        review_shadow_cycle(cycle, self.reconciler, accept=True, reason="Exact total/count and retained reference independently reviewed.")
        cycle.refresh_from_db()
        return cycle

    def _approve_qualification(self, candidate, cycles):
        plan = FinanceCutoverQualificationPlan.objects.create(
            cycle=candidate,
            minimum_consecutive_cycles=2,
            require_parallel_cycle=True,
            local_authority_reference="Synthetic local field-qualification direction QUAL-PLAN-001.",
            accepted_rules_forms_reference="Locally accepted synthetic rules/forms register QUAL-FORMS-001.",
            field_evidence_basis="Retained field observation sheets, reconciled registers, and signed local attestations.",
            created_by=self.manager,
        )
        accepted_form = self._accepted_local_form()
        FinanceCutoverQualificationForm.objects.create(
            plan=plan, local_form=accepted_form, position=1,
            use_instructions="Prepare, review, print, and retain this exact accepted DV control form in every qualifying cycle.",
        )
        submit_cutover_qualification_plan(plan, self.manager)
        review_cutover_qualification_plan(
            plan, self.reconciler, approve=True,
            reason="Reviewed the editable threshold, parallel-run condition, accepted rules/forms, and evidence basis.",
        )
        plan.refresh_from_db()
        for sequence, cycle in enumerate(cycles, 1):
            item = FinanceCutoverQualificationEvidence.objects.create(
                plan=plan, cycle=cycle, sequence=sequence,
                field_execution_reference=f"Synthetic retained field packet FIELD-{sequence:03d}",
                rules_forms_reference="Accepted synthetic rules/forms register QUAL-FORMS-001",
                prepared_by=self.manager,
            )
            submit_cutover_qualification_evidence(item, self.manager)
            review_cutover_qualification_evidence(
                item, self.reconciler, accept=True,
                reason="Independently reviewed the retained field packet against the approved qualification basis.",
            )
        return plan

    def _accepted_local_form(self, *, code="ordinary-dv-control"):
        existing = FinanceLocalFormAcceptance.objects.filter(
            department=self.accounting, code=code, status=FinanceLocalFormAcceptance.ACCEPTED,
        ).first()
        if existing:
            return existing
        item = FinanceLocalFormAcceptance.objects.create(
            department=self.accounting, code=code, version=1,
            name="Ordinary disbursement voucher control form", form_number="DV-CONTROL-01",
            purpose="Carry the reviewed ordinary-DV controls through Budget, Accounting, and Treasury.",
            source_type=FinanceLocalFormAcceptance.SOURCE_UNMAPPED,
            authority_reference="Synthetic local acceptance basis FORM-AUTH-001.",
            local_acceptance_note="Independently accepted for synthetic cutover tests.",
            reference_kind="pdf",
            reference_file=SimpleUploadedFile(
                f"{code}.pdf", b"%PDF-1.4\nSynthetic blank local form\n%%EOF", content_type="application/pdf",
            ),
            delivery_mode=FinanceLocalFormAcceptance.DELIVERY_DIGITAL,
            signatory_instructions="Budget certifies; Accounting reviews; Treasury acknowledges payment handling.",
            recipient_instructions="Retain the controlled digital copy with the cycle evidence packet.",
            deadline_instructions="Complete before the voucher moves to the next Finance office.",
            retention_instructions="Retain under the synthetic Finance records packet.",
            pagination_instructions="Number every page and repeat the voucher reference.",
            overflow_instructions="Use a numbered continuation page linked to the voucher.",
            accessibility_instructions="Use labeled fields, readable text, and a tagged digital copy when available.",
            created_by=self.manager,
        )
        item.reference_checksum = file_checksum(item.reference_file)
        item.source_snapshot = {"source_type": "unmapped", "test_fixture": True}
        item.source_checksum = checksum(item.source_snapshot)
        item.submission_snapshot = form_snapshot(
            item, pinned_source=item.source_snapshot,
            pinned_reference_checksum=item.reference_checksum,
        )
        item.submission_checksum = checksum(item.submission_snapshot)
        item.status = FinanceLocalFormAcceptance.SUBMITTED
        item.submitted_by = self.manager
        item.submitted_at = timezone.now()
        item.save()
        item.status = FinanceLocalFormAcceptance.ACCEPTED
        item.reviewed_by = self.reconciler
        item.reviewed_at = timezone.now()
        item.review_note = "Synthetic independent acceptance after exact form review."
        item.save()
        return item

    def _accepted_stakeholders(self, cycle):
        self._approve_readiness_plan(cycle)
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
            self._pass_readiness_exercise(
                cycle, kind=FinanceCutoverReadinessExercise.ROLE_TRAINING,
                code=f"role-{kind}", owner=reviewer, witness=self.reconciler,
                stakeholder_acceptance=acceptance,
            )
            decide_stakeholder_acceptance(
                acceptance,
                reviewer,
                decision=FinanceStakeholderAcceptance.ACCEPTED,
                training_reference=f"{kind} role guide and supervisor exercise TRN-001",
                uat_reference=f"{kind} synthetic/redacted scenario UAT-001",
                signed_decision_reference=f"Retained attributed stakeholder decision DEC-{kind}",
                signed_decision_checksum="d" * 64,
            )
        for kind in sorted(REQUIRED_NONFUNCTIONAL_EXERCISES):
            self._pass_readiness_exercise(
                cycle, kind=kind, code=f"nfr-{kind}", owner=self.manager, witness=self.reconciler,
            )

    def _record_discovery_coverage(self, cycle, *, code="DEC-F0-COVERAGE"):
        decisions = [FinanceDiscoveryDecision.objects.create(
            department=cycle.department,
            cycle=cycle,
            code=code,
            phase="F0",
            coverage_kind=FinanceDiscoveryDecision.SCOPE_ACCEPTANCE,
            question="Has the LGU confirmed the exact Finance scope enabled for this candidate cycle?",
            proposed_outcome="Proceed only with the cycle's exact enabled scope under the retained local confirmation.",
            affected_scope=cycle.enabled_scope,
            evidence_label=FinanceDiscoveryDecision.LGU_CONFIRMED,
            authority_evidence_reference="Retained Finance discovery workshop and accountable-owner decision DISC-F0-001",
            evidence_needed="The cited workshop record and accountable-owner decision are sufficient for this exact cycle scope.",
            evidence_custody_reference="Restricted Finance discovery packet DISC/F0/001",
            acceptance_example_reference="Accepted exact-scope replay and decision record EXAMPLE-F0-001",
            blocks_affected_scope=False,
            owner=self.manager,
            reviewer=self.reconciler,
            created_by=self.manager,
        )]
        for index, coverage_kind in enumerate(sorted(FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS), 1):
            decisions.append(FinanceDiscoveryDecision.objects.create(
                department=cycle.department,
                cycle=cycle,
                code=f"{code[:30]}-{index}",
                phase="F0",
                coverage_kind=coverage_kind,
                question=f"Is the {coverage_kind} coverage complete for this candidate cycle?",
                proposed_outcome="Use the locally confirmed evidence for this coverage area within the candidate scope.",
                affected_scope=f"{coverage_kind} coverage within: {cycle.enabled_scope}",
                evidence_label=FinanceDiscoveryDecision.LGU_CONFIRMED,
                authority_evidence_reference=f"Retained Finance discovery evidence DISC-F0-{index:03d}",
                evidence_needed="The cited reviewed evidence is sufficient for this coverage area.",
                evidence_custody_reference=f"Restricted Finance discovery packet DISC/F0/{index:03d}",
                acceptance_example_reference=f"Accepted redacted example or no-case explanation EXAMPLE-F0-{index:03d}",
                blocks_affected_scope=False,
                owner=self.manager,
                reviewer=self.reconciler,
                created_by=self.manager,
            ))
        for item in decisions:
            submit_discovery_decision(item, self.manager)
            review_discovery_decision(
                item,
                self.reconciler,
                record=True,
                reason="Independently reviewed the retained LGU confirmation and acceptance example for this coverage area.",
            )
        return FinanceDiscoveryDecision.objects.get(pk=decisions[0].pk)

    def _approve_readiness_plan(self, cycle):
        existing = FinanceCutoverReadinessPlan.objects.filter(cycle=cycle).first()
        if existing:
            return existing
        plan = FinanceCutoverReadinessPlan.objects.create(
            cycle=cycle,
            curriculum_register_reference="Role curriculum register CURR-001 with Budget, Accounting, Treasury, requesting-office, IT, management, and audit sections.",
            quick_guides_reference="Published floating Internal How-Tos and controlled desk guides QUICK-001.",
            supervisor_runbook_reference="Supervisor observation, rerun, and sign-off runbook SUP-001.",
            support_owner=self.manager,
            support_channels_and_hours="Finance support desk, weekdays 8:00–17:00; backup channel retained in SUP-001.",
            support_escalation_procedure="Access to IT; data/control to Accounting and Budget; payment to Treasury; critical cutover issue to management.",
            local_acceptance_note="Synthetic UAT readiness workshop decision READY-PLAN-001.",
            created_by=self.manager,
        )
        submit_cutover_readiness_plan(plan, self.manager)
        review_cutover_readiness_plan(
            plan, self.reconciler, approve=True,
            reason="Reviewed role curricula, supervisor observation, support ownership, hours, and escalation boundaries.",
        )
        return FinanceCutoverReadinessPlan.objects.get(pk=plan.pk)

    def _pass_readiness_exercise(self, cycle, *, kind, code, owner, witness, stakeholder_acceptance=None):
        scheduled_for = timezone.make_aware(datetime.combine(cycle.planned_start, time(9, 0)))
        exercise = schedule_cutover_readiness_exercise(
            cycle, self.manager, kind=kind, code=code, title=f"{kind} synthetic readiness exercise",
            enabled_scope=cycle.enabled_scope,
            procedure="Follow the retained human-readable script with synthetic/redacted inputs and record observable controls.",
            expected_result="The named control completes without unexplained difference and the safe fallback remains usable.",
            owner=owner, witness=witness, scheduled_for=scheduled_for,
            due_at=scheduled_for + timedelta(hours=4), stakeholder_acceptance=stakeholder_acceptance,
        )
        submit_cutover_readiness_exercise(
            exercise, owner,
            actual_result="Completed the exact synthetic script; expected control and fallback result were observed.",
            evidence_reference=f"Redacted exercise packet {code.upper()}-EVIDENCE",
            recovery_evidence=(
                self._recovery_rehearsal_values(exercise)
                if kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE else None
            ),
        )
        review_cutover_readiness_exercise(
            exercise, witness, accept=True,
            reason="Independently observed the retained result and verified it against the stated pass condition.",
        )
        return FinanceCutoverReadinessExercise.objects.get(pk=exercise.pk)

    def _recovery_rehearsal_values(self, exercise, **overrides):
        interruption = exercise.scheduled_for
        values = {
            "backup_id": "20270104T083000000000Z-deadbeef",
            "manifest_sha256": "1" * 64,
            "default_artifact_sha256": "2" * 64,
            "finance_artifact_sha256": "3" * 64,
            "off_host_copy_reference": "Restricted off-host recovery set COPY-001",
            "off_host_copy_verified": True,
            "preflight_receipt_reference": "Non-secret live preflight receipt PREFLIGHT-001",
            "preflight_receipt_checksum": "4" * 64,
            "preflight_passed": True,
            "policy_reference": "Approved recovery, retention, RPO/RTO procedure RECOVERY-POLICY-001",
            "isolated_environment_reference": "Disposable isolated MySQL rehearsal host ISO-001",
            "release_reference": "GRAND test release and revision RELEASE-001",
            "database_versions": "Default and Finance: synthetic MySQL 8 compatible test stores",
            "restore_log_reference": "Restricted command and timing log RESTORE-LOG-001",
            "recovery_point_at": interruption - timedelta(minutes=30),
            "simulated_interruption_at": interruption,
            "restored_at": interruption + timedelta(minutes=45),
            "approved_rpo_minutes": 60,
            "approved_rto_minutes": 60,
            "default_store_restored": True,
            "finance_store_restored": True,
            "default_migrations_current": True,
            "finance_migrations_current": True,
            "control_totals_reconciled": True,
            "control_reconciliation_reference": "Two-store control worksheet CONTROL-001",
            "control_reconciliation_checksum": "5" * 64,
            "cross_store_case_verified": True,
            "cross_store_verification_reference": "Budget–Accounting–Treasury restored case CROSS-STORE-001",
            "cross_store_verification_checksum": "6" * 64,
            "runtime_files_checked": True,
            "runtime_files_verification_reference": "Required media/export reference check RUNTIME-001",
            "secure_disposal_completed": True,
            "secure_disposal_reference": "Approved isolated-data cleanup record DISPOSAL-001",
            "unresolved_exceptions": False,
            "exceptions_and_resolution": "No exceptions occurred in the synthetic rehearsal.",
        }
        values.update(overrides)
        return values

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
        self.assertEqual(payload["schema_version"], 9)
        self.assertEqual(payload["cycle"]["schema_version"], 3)
        self.assertEqual(payload["cycle"]["reconciliation_plan"]["status"], "approved")
        self.assertEqual(payload["cycle"]["source_versions"][0]["row_count"], 1)
        self.assertEqual(payload["cycle"]["source_versions"][0]["normalized_headers"], ["case_id", "amount", "status"])
        self.assertIsNone(payload["cutover_readiness_plan"])
        self.assertEqual(payload["cutover_readiness_exercises"], [])
        self.assertNotIn("SECRET-ROW-VALUE", content.decode("utf-8"))

    def test_scheduled_run_retains_exception_then_independent_defect_resolution_opens_final_gate(self):
        cycle = self._cycle()
        start_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        comparison = FinanceShadowComparison.objects.create(
            cycle=cycle, comparison_level=FinanceShadowComparison.CASE,
            control_code="case-rounding-001", label="Case amount and centavo precision",
            source_reference="Redacted source case SRC-ROUND-001", grand_reference="GRAND case GRAND-ROUND-001",
            source_amount=Decimal("100.00"), grand_amount=Decimal("99.99"),
            outcome=FinanceShadowComparison.OPEN_DEFECT,
            explanation="One-centavo difference in the synthetic source mapping.",
            evidence_reference="Comparison worksheet CMP-ROUND-001", defect_owner=self.manager,
            created_by=self.manager,
        )
        run = open_next_reconciliation_run(cycle, self.manager)
        defect = register_shadow_defect(
            comparison, self.manager, code="rounding-001", severity=FinanceShadowDefect.HIGH,
            summary="Centavo mapping difference", impact="The case and register totals disagree by one centavo.",
            owner=self.manager,
        )
        self.assertEqual(defect.escalation_route_snapshot, "Accounting reviewer and affected office head")
        self.assertGreater(defect.correction_due_at, timezone.now())
        record_shadow_defect_escalation(
            defect, self.manager,
            note="Accounting reviewer notified through retained UAT issue log ESC-001; correction requested before next run.",
        )
        submit_reconciliation_run(run, self.manager)
        review_reconciliation_run(
            run, self.reconciler, accept=True,
            reason="The exact difference and attributed open defect agree with retained worksheet CMP-ROUND-001.",
        )
        run.refresh_from_db()
        self.assertEqual(run.status, FinanceShadowReconciliationRun.REVIEWED_WITH_EXCEPTIONS)
        self.assertEqual(run.open_defect_count, 1)
        run.review_note = "Attempted rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            run.save()
        with self.assertRaisesMessage(ValidationError, "open defect"):
            submit_shadow_cycle(cycle, self.manager)

        submit_shadow_defect_resolution(
            defect, self.manager,
            note="Corrected the synthetic centavo mapping and reran the exact case control.",
            evidence_reference="Corrected rerun and worksheet CMP-ROUND-002",
        )
        with self.assertRaisesMessage(ValidationError, "submitter"):
            review_shadow_defect_resolution(defect, self.manager, accept=True, reason="Self-review attempt")
        review_shadow_defect_resolution(
            defect, self.reconciler, accept=True,
            reason="Verified corrected mapping, rerun evidence, and exact downstream register total.",
        )
        defect.refresh_from_db(); comparison.refresh_from_db()
        self.assertEqual(defect.status, FinanceShadowDefect.RESOLVED)
        self.assertEqual(comparison.outcome, FinanceShadowComparison.EXPLAINED)
        defect.resolution_note = "Attempted rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            defect.save()
        submit_shadow_cycle(cycle, self.manager)

    def test_cycle_cannot_start_without_independently_approved_local_cadence(self):
        cycle = FinanceShadowCycle.objects.create(
            department=self.accounting, code="missing-local-plan", title="Missing local reconciliation plan",
            fiscal_year=2027, enabled_scope="Synthetic ordinary-DV scope",
            source_extract_reference="Redacted packet PLAN-GAP-001",
            source_checksum="c" * 64, source_schema_signature="d" * 64,
            planned_start=date(2027, 3, 1), planned_end=date(2027, 3, 5), created_by=self.manager,
        )
        with self.assertRaisesMessage(ValidationError, "independently approve"):
            start_shadow_cycle(cycle, self.manager)

    def test_working_day_schedule_skips_weekend_and_minimum_run_gate_is_enforced(self):
        cycle = FinanceShadowCycle.objects.create(
            department=self.accounting, code="working-day-cadence", title="Working-day cadence pilot",
            fiscal_year=2027, enabled_scope="Synthetic working-day reconciliation scope",
            source_extract_reference="Redacted packet CADENCE-001",
            source_checksum="e" * 64, source_schema_signature="f" * 64,
            planned_start=date(2027, 1, 8), planned_end=date(2027, 1, 11), created_by=self.manager,
        )
        self._approve_plan(
            cycle, minimum_runs=2, cadence=FinanceShadowReconciliationPlan.BUSINESS_DAILY,
        )
        start_shadow_cycle(cycle, self.manager)
        comparison = self._matched_comparison(cycle)
        first = self._review_current_run(cycle)
        self.assertEqual(timezone.localtime(first.scheduled_for).date(), date(2027, 1, 8))
        with self.assertRaisesMessage(ValidationError, "at least 2"):
            submit_shadow_cycle(cycle, self.manager)
        second = self._review_current_run(cycle)
        self.assertEqual(timezone.localtime(second.scheduled_for).date(), date(2027, 1, 11))
        submit_shadow_cycle(cycle, self.manager)
        comparison.refresh_from_db()
        self.assertEqual(comparison.outcome, FinanceShadowComparison.MATCHED)

    def test_submission_locks_checksum_and_requires_an_independent_reconciler(self):
        cycle = self._cycle()
        start_shadow_cycle(cycle, self.manager)
        cycle.refresh_from_db()
        comparison = self._matched_comparison(cycle)
        self._review_current_run(cycle)
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
        self._approve_readiness_plan(cycle)
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
                signed_decision_reference="Retained decision DEC-WRONG", signed_decision_checksum="d" * 64,
            )
        with self.assertRaisesMessage(ValidationError, "independently witness"):
            decide_stakeholder_acceptance(
                acceptance, self.requesting_reviewer,
                decision=FinanceStakeholderAcceptance.ACCEPTED,
                training_reference="Private tutorial progress", uat_reference="UAT evidence",
                signed_decision_reference="Retained decision DEC-PRE", signed_decision_checksum="d" * 64,
            )
        exercise = self._pass_readiness_exercise(
            cycle, kind=FinanceCutoverReadinessExercise.ROLE_TRAINING,
            code="role-requesting-office", owner=self.requesting_reviewer,
            witness=self.reconciler, stakeholder_acceptance=acceptance,
        )
        decide_stakeholder_acceptance(
            acceptance, self.requesting_reviewer,
            decision=FinanceStakeholderAcceptance.ACCEPTED,
            training_reference="Supervisor-observed role exercise TRN-ENG-01",
            uat_reference="Redacted ordinary-DV scripts UAT-ENG-01 through 04",
            signed_decision_reference="Wet-signed stakeholder sheet DEC-ENG-01",
            signed_decision_checksum="d" * 64,
        )
        acceptance.refresh_from_db()
        self.assertEqual(acceptance.decided_by, self.requesting_reviewer)
        self.assertNotIn("tutorial", acceptance.training_evidence_reference.lower())
        self.assertEqual(exercise.status, FinanceCutoverReadinessExercise.PASSED)
        with self.assertRaisesMessage(ValidationError, "already recorded"):
            decide_stakeholder_acceptance(
                acceptance, self.requesting_reviewer,
                decision=FinanceStakeholderAcceptance.REJECTED,
                training_reference="Changed", uat_reference="Changed", reason="Overwrite attempt",
                signed_decision_reference="Changed", signed_decision_checksum="e" * 64,
            )

    def test_readiness_plan_and_exercise_require_independent_witness_and_retain_rerun_history(self):
        cycle = self._reconciled_cycle()
        plan = FinanceCutoverReadinessPlan.objects.create(
            cycle=cycle,
            curriculum_register_reference="Editable role curriculum register CURR-RERUN-001.",
            quick_guides_reference="Department floating guides and desk guide QUICK-RERUN-001.",
            supervisor_runbook_reference="Supervisor witness and rerun runbook SUP-RERUN-001.",
            support_owner=self.manager,
            support_channels_and_hours="Finance help desk weekdays 8:00–17:00 with named backup.",
            support_escalation_procedure="Access to IT; controls to Accounting; critical interruption to management.",
            local_acceptance_note="Synthetic readiness plan retained as READY-RERUN-001.",
            created_by=self.manager,
        )
        submit_cutover_readiness_plan(plan, self.manager)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_cutover_readiness_plan(plan, self.manager, approve=True, reason="Self approval")
        review_cutover_readiness_plan(
            plan, self.reconciler, approve=True,
            reason="Reviewed the local curricula, runbook, support ownership, and escalation route.",
        )
        plan.refresh_from_db()
        plan.learning_privacy_notice = "Tutorial progress may be used for evaluation."
        with self.assertRaisesMessage(ValidationError, "boundary cannot be changed"):
            plan.save()
        plan.refresh_from_db()
        plan.quick_guides_reference = "Attempted rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            plan.save()

        acceptance = FinanceStakeholderAcceptance.objects.create(
            cycle=cycle, stakeholder_kind=FinanceStakeholderAcceptance.REQUESTING_OFFICE,
            office=self.requesting, assigned_reviewer=self.requesting_reviewer,
            enabled_scope=cycle.enabled_scope, created_by=self.manager,
        )
        scheduled_for = timezone.make_aware(datetime.combine(cycle.planned_start, time(10, 0)))
        exercise = schedule_cutover_readiness_exercise(
            cycle, self.manager, kind=FinanceCutoverReadinessExercise.ROLE_TRAINING,
            code="role-rerun-001", title="Requesting-office ordinary-DV role exercise",
            enabled_scope=cycle.enabled_scope,
            procedure="Follow the controlled ordinary-DV synthetic script, use the floating guide if needed, and retain the result.",
            expected_result="The named reviewer completes the scoped case with exact control totals and knows the support route.",
            owner=self.requesting_reviewer, witness=self.reconciler,
            scheduled_for=scheduled_for, due_at=scheduled_for + timedelta(hours=2),
            stakeholder_acceptance=acceptance,
        )
        self.client.force_login(self.requesting_reviewer)
        response = self.client.get(reverse("finance:shadow_cycle_detail", args=(cycle.pk,)))
        self.assertContains(response, "role-rerun-001")
        self.assertContains(response, "Record result")
        submit_cutover_readiness_exercise(
            exercise, self.requesting_reviewer,
            actual_result="First run completed but the support escalation step was not demonstrated.",
            evidence_reference="Redacted observation sheet ROLE-RERUN-001-A",
        )
        self.client.force_login(self.reconciler)
        response = self.client.get(reverse("finance:shadow_cycle_detail", args=(cycle.pk,)))
        self.assertContains(response, "Witness pass")
        with self.assertRaisesMessage(PermissionDenied, "assigned witness"):
            review_cutover_readiness_exercise(exercise, self.manager, accept=True, reason="Wrong reviewer")
        review_cutover_readiness_exercise(
            exercise, self.reconciler, accept=False,
            reason="Rerun the support escalation step and retain the acknowledgement evidence.",
        )
        submit_cutover_readiness_exercise(
            exercise, self.requesting_reviewer,
            actual_result="Rerun completed including the named support escalation and acknowledgement step.",
            evidence_reference="Redacted observation sheet ROLE-RERUN-001-B and ticket acknowledgement",
        )
        review_cutover_readiness_exercise(
            exercise, self.reconciler, accept=True,
            reason="Independently observed the complete rerun and verified every stated pass condition.",
        )
        exercise.refresh_from_db()
        self.assertEqual(exercise.status, FinanceCutoverReadinessExercise.PASSED)
        exercise.actual_result = "Attempted rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            exercise.save()
        decide_stakeholder_acceptance(
            acceptance, self.requesting_reviewer,
            decision=FinanceStakeholderAcceptance.ACCEPTED,
            training_reference="Passed witnessed role exercise ROLE-RERUN-001",
            uat_reference="Synthetic/redacted ordinary-DV scenario UAT-RERUN-001",
            signed_decision_reference="Retained stakeholder decision DEC-RERUN-001",
            signed_decision_checksum="d" * 64,
        )
        readiness = cutover_readiness(cycle)
        self.assertFalse(readiness["ready"])
        self.assertIn(FinanceCutoverReadinessExercise.PRIVACY, readiness["missing_exercises"])
        content, _filename, _receipt = build_cutover_evidence_package(cycle, self.requesting_reviewer)
        payload = json.loads(content)
        self.assertEqual(payload["schema_version"], 9)
        self.assertEqual(payload["cutover_readiness_plan"]["status"], "approved")
        self.assertEqual(payload["cutover_readiness_exercises"][0]["status"], "passed")
        self.assertNotIn("progress_percent", content.decode("utf-8"))

    def test_recovery_exercise_requires_structured_two_store_evidence_and_objective_rerun(self):
        cycle = self._reconciled_cycle(code="fy-2027-recovery-structure")
        self._approve_readiness_plan(cycle)
        scheduled_for = timezone.make_aware(datetime.combine(cycle.planned_start, time(11, 0)))
        exercise = schedule_cutover_readiness_exercise(
            cycle, self.manager, kind=FinanceCutoverReadinessExercise.BACKUP_RESTORE,
            code="recovery-structured-001", title="Two-store isolated recovery rehearsal",
            enabled_scope=cycle.enabled_scope,
            procedure="Verify an off-host set, restore both stores in isolation, reconcile controls, test one cross-store case, and dispose securely.",
            expected_result="Both stores and migrations reconcile within approved RPO/RTO with no unresolved exception.",
            owner=self.manager, witness=self.reconciler, scheduled_for=scheduled_for,
            due_at=scheduled_for + timedelta(hours=3),
        )
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("finance:cutover_readiness_exercise_result", args=(exercise.pk,)),
        )
        self.assertContains(response, "Exact GRAND backup-set ID")
        self.assertContains(response, "Approved RPO")
        with self.assertRaisesMessage(ValidationError, "structured two-store"):
            submit_cutover_readiness_exercise(
                exercise, self.manager,
                actual_result="Narrative-only recovery claim.",
                evidence_reference="Narrative packet without structured controls",
            )

        missed_rto = self._recovery_rehearsal_values(
            exercise,
            restored_at=scheduled_for + timedelta(minutes=90),
            unresolved_exceptions=True,
            exceptions_and_resolution="Restore exceeded RTO; tuning and rerun are still required.",
        )
        submit_cutover_readiness_exercise(
            exercise, self.manager,
            actual_result="Both stores restored, but the first run exceeded RTO.",
            evidence_reference="Restricted recovery packet RECOVERY-STRUCTURED-001-A",
            recovery_evidence=missed_rto,
        )
        exercise.refresh_from_db()
        evidence = exercise.recovery_rehearsal
        self.assertEqual(evidence.actual_rpo_minutes, 30)
        self.assertEqual(evidence.actual_rto_minutes, 90)
        self.assertFalse(evidence.meets_control_objectives)
        with self.assertRaisesMessage(ValidationError, "actual RTO exceeded"):
            review_cutover_readiness_exercise(
                exercise, self.reconciler, accept=True,
                reason="Attempt to pass a missed recovery objective.",
            )
        review_cutover_readiness_exercise(
            exercise, self.reconciler, accept=False,
            reason="Tune the isolated restore, resolve the timing exception, and rerun within the approved RTO.",
        )
        exercise.refresh_from_db()
        submit_cutover_readiness_exercise(
            exercise, self.manager,
            actual_result="Rerun restored and reconciled both stores within approved RPO and RTO.",
            evidence_reference="Restricted recovery packet RECOVERY-STRUCTURED-001-B",
            recovery_evidence=self._recovery_rehearsal_values(exercise),
        )
        review_cutover_readiness_exercise(
            exercise, self.reconciler, accept=True,
            reason="Independently checked the exact backup hashes, both restored stores, timings, controls, case, and disposal record.",
        )
        exercise.refresh_from_db()
        evidence.refresh_from_db()
        self.assertEqual(exercise.status, FinanceCutoverReadinessExercise.PASSED)
        self.assertTrue(evidence.meets_control_objectives)
        self.assertEqual(len(evidence.evidence_checksum), 64)
        readiness = cutover_readiness(cycle)
        self.assertNotIn(FinanceCutoverReadinessExercise.BACKUP_RESTORE, readiness["missing_exercises"])
        evidence.restore_log_reference = "Attempted rewrite after witness pass"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            evidence.save()

        content, _filename, _receipt = build_cutover_evidence_package(cycle, self.manager)
        payload = json.loads(content)
        recovery_payload = payload["cutover_readiness_exercises"][0]["recovery_rehearsal"]
        self.assertEqual(payload["schema_version"], 9)
        self.assertEqual(recovery_payload["backup_id"], "20270104T083000000000Z-deadbeef")
        self.assertEqual(recovery_payload["actual_rto_minutes"], 45)
        self.assertTrue(recovery_payload["meets_control_objectives"])
        self.assertNotIn("password", content.decode("utf-8").lower())

    def test_cutover_requires_all_seven_acceptances_and_separate_authority_then_can_roll_back(self):
        predecessor = self._reconciled_cycle(code="fy-2027-dv-field-01")
        cycle = self._reconciled_cycle(
            code="fy-2027-dv-field-02", predecessor=predecessor, run_kind=FinanceShadowCycle.PARALLEL,
        )
        decision = FinanceCutoverDecision.objects.create(
            cycle=cycle,
            authority_matrix_reference="Signed authority matrix AUTH-001",
            enabled_scope=cycle.enabled_scope,
            cutover_at=timezone.now() + timedelta(days=30),
            opening_reconciliation_reference="Opening and in-flight reconciliation OPEN-001",
            rollback_criteria="Rollback on unexplained ledger difference, critical outage, or failed recovery test.",
            legacy_read_only_retention_plan="Keep historical eGAPS/current-process records read-only under Records plan RET-001.",
            backup_recovery_evidence="Restore and continuity exercise BCP-001",
            signed_authority_reference="Wet-signed cutover authority record AUTH-SIGNED-001",
            signed_authority_checksum="a" * 64,
            signature_custody_reference="TracePoint records packet CUTOVER-001 held by the Records custodian",
            prepared_by=self.manager,
        )
        with self.assertRaisesMessage(ValidationError, "every required stakeholder"):
            submit_cutover_decision(decision, self.manager)
        self._accepted_stakeholders(cycle)
        recovery = FinanceRecoveryRehearsalEvidence.objects.get(exercise__cycle=cycle)
        decision.recovery_rehearsal = recovery
        decision.save(update_fields=("recovery_rehearsal",))
        self._approve_qualification(cycle, [predecessor, cycle])
        self._record_discovery_coverage(cycle)
        self.assertTrue(cutover_readiness(cycle)["ready"])
        package_content, _package_name, _package_receipt = build_cutover_evidence_package(
            cycle, self.manager,
        )
        package = json.loads(package_content)
        self.assertEqual(package["schema_version"], 9)
        self.assertEqual(len(package["discovery_decisions"]), 9)
        self.assertEqual(
            {item["coverage_kind"] for item in package["discovery_decisions"]},
            FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS | {
                FinanceDiscoveryDecision.SCOPE_ACCEPTANCE,
            },
        )
        submit_cutover_decision(decision, self.manager)
        decision.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "preparer"):
            decide_cutover(decision, self.manager, authorize=True, reason="Self-authorization attempt")
        decide_cutover(decision, self.authority, authorize=True, reason="Named authority approved the exact scope and effective date.")
        decision.refresh_from_db()
        self.assertTrue(decision.makes_grand_authoritative)
        self.assertEqual(decision.recovery_rehearsal.backup_id, "20270104T083000000000Z-deadbeef")
        with self.assertRaisesMessage(ValidationError, "successor cycle"):
            FinanceDiscoveryDecision.objects.create(
                department=cycle.department,
                cycle=cycle,
                code="DEC-LATE-FINDING",
                phase="F0",
                question="Attempted late rewrite of accepted discovery evidence",
                proposed_outcome="This must be recorded against a successor cycle.",
                affected_scope=cycle.enabled_scope,
                evidence_label=FinanceDiscoveryDecision.UNRESOLVED,
                evidence_needed="Record the incident and use the governed rollback/successor route.",
                owner=self.manager,
                reviewer=self.reconciler,
                created_by=self.manager,
            )
        scheduled_for = timezone.make_aware(datetime.combine(cycle.planned_end, time(16, 0)))
        with self.assertRaisesMessage(ValidationError, "locked after the cutover record"):
            schedule_cutover_readiness_exercise(
                cycle, self.manager, kind=FinanceCutoverReadinessExercise.INCIDENT_RESPONSE,
                code="late-extra-exercise", title="Improper post-authorization exercise",
                enabled_scope=cycle.enabled_scope, procedure="Should not be accepted.",
                expected_result="Should not be accepted.", owner=self.manager, witness=self.reconciler,
                scheduled_for=scheduled_for, due_at=scheduled_for + timedelta(hours=1),
            )
        record_cutover_rollback(decision, self.authority, reason="Recovery exercise exposed the recorded critical restore criterion.")
        decision.refresh_from_db()
        self.assertEqual(decision.status, FinanceCutoverDecision.ROLLED_BACK)
        self.assertFalse(decision.makes_grand_authoritative)
        self.assertTrue(FinanceAuditEvent.objects.filter(action="finance_cutover_authorized").exists())
        self.assertTrue(FinanceAuditEvent.objects.filter(action="finance_cutover_rolled_back").exists())

    def test_cutover_discovery_gate_requires_exact_accepted_scope_and_no_current_blocker(self):
        cycle = self._reconciled_cycle(code="fy-2027-discovery-gate")
        readiness = cutover_readiness(cycle)
        discovery_check = next(
            check for check in readiness["checks"] if check["code"] == "discovery_scope_accepted"
        )
        self.assertFalse(discovery_check["passed"])
        self.assertEqual(readiness["discovery_decision_ids"], [])

        blocker = FinanceDiscoveryDecision.objects.create(
            department=cycle.department,
            cycle=cycle,
            code="DEC-F0-GATE",
            phase="F0",
            coverage_kind=FinanceDiscoveryDecision.SCOPE_ACCEPTANCE,
            question="Has the exact candidate scope been confirmed by the LGU?",
            proposed_outcome="Keep only this candidate scope blocked pending retained local confirmation.",
            affected_scope=cycle.enabled_scope,
            evidence_label=FinanceDiscoveryDecision.UNRESOLVED,
            evidence_needed="Retained accountable-owner workshop decision for this exact scope.",
            blocks_affected_scope=True,
            owner=self.manager,
            reviewer=self.reconciler,
            created_by=self.manager,
        )
        submit_discovery_decision(blocker, self.manager)
        review_discovery_decision(
            blocker,
            self.reconciler,
            record=True,
            reason="The unresolved local confirmation and exact blocked scope are accurately recorded.",
        )
        blocker.refresh_from_db()
        readiness = cutover_readiness(cycle)
        self.assertEqual(readiness["discovery_blocking_ids"], [blocker.pk])

        successor = FinanceDiscoveryDecision.objects.create(
            department=cycle.department,
            cycle=cycle,
            code=blocker.code,
            version=2,
            phase="F0",
            coverage_kind=FinanceDiscoveryDecision.SCOPE_ACCEPTANCE,
            question=blocker.question,
            proposed_outcome="Proceed only with the cycle's exact scope under the retained local confirmation.",
            affected_scope=cycle.enabled_scope,
            evidence_label=FinanceDiscoveryDecision.LGU_CONFIRMED,
            authority_evidence_reference="Retained accountable-owner workshop decision DISC-F0-GATE",
            evidence_needed="The cited decision and exact-scope replay are sufficient.",
            evidence_custody_reference="Restricted Finance discovery packet DISC/F0/GATE",
            acceptance_example_reference="Accepted exact-scope replay and decision record EXAMPLE-F0-GATE",
            blocks_affected_scope=False,
            owner=self.manager,
            reviewer=self.reconciler,
            predecessor=blocker,
            change_reason="The exact-scope local confirmation is now retained.",
            created_by=self.manager,
        )
        submit_discovery_decision(successor, self.manager)
        review_discovery_decision(
            successor,
            self.reconciler,
            record=True,
            reason="Independently matched the retained local confirmation to the exact enabled scope.",
        )
        readiness = cutover_readiness(cycle)
        discovery_check = next(
            check for check in readiness["checks"] if check["code"] == "discovery_scope_accepted"
        )
        self.assertTrue(discovery_check["passed"])
        self.assertEqual(readiness["discovery_blocking_ids"], [])
        self.assertEqual(readiness["discovery_coverage_ids"], [successor.pk])
        self.assertEqual(
            set(readiness["missing_discovery_kinds"]),
            FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS,
        )

    def test_field_qualification_rejects_short_or_misordered_chain_and_locks_accepted_evidence(self):
        predecessor = self._reconciled_cycle(code="fy-2027-chain-01")
        candidate = self._reconciled_cycle(
            code="fy-2027-chain-02", predecessor=predecessor, run_kind=FinanceShadowCycle.PARALLEL,
        )
        plan = FinanceCutoverQualificationPlan.objects.create(
            cycle=candidate, minimum_consecutive_cycles=2, require_parallel_cycle=True,
            local_authority_reference="Synthetic qualification direction QUAL-CHAIN-001",
            accepted_rules_forms_reference="Synthetic accepted local form register QUAL-FORMS-CHAIN-001",
            field_evidence_basis="Retained observation sheet plus independently reconciled cycle packet.",
            created_by=self.manager,
        )
        FinanceCutoverQualificationForm.objects.create(
            plan=plan, local_form=self._accepted_local_form(code="chain-dv-control"), position=1,
            use_instructions="Use this exact accepted control form for each cycle in the predecessor chain.",
        )
        submit_cutover_qualification_plan(plan, self.manager)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_cutover_qualification_plan(plan, self.manager, approve=True, reason="Self approval")
        review_cutover_qualification_plan(
            plan, self.reconciler, approve=True, reason="Reviewed local threshold and retained evidence basis.",
        )
        plan.refresh_from_db()
        plan.minimum_consecutive_cycles = 3
        with self.assertRaisesMessage(ValidationError, "immutable"):
            plan.save()
        plan.refresh_from_db()

        item = FinanceCutoverQualificationEvidence.objects.create(
            plan=plan, cycle=candidate, sequence=1,
            field_execution_reference="Synthetic field packet FIELD-CHAIN-002",
            rules_forms_reference="Synthetic accepted local form register QUAL-FORMS-CHAIN-001",
            prepared_by=self.manager,
        )
        submit_cutover_qualification_evidence(item, self.manager)
        review_cutover_qualification_evidence(
            item, self.reconciler, accept=True, reason="Reviewed retained synthetic field packet.",
        )
        item.refresh_from_db()
        item.field_execution_reference = "Attempted rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            item.save()
        readiness = cutover_readiness(candidate)
        chain_check = next(check for check in readiness["checks"] if check["code"] == "consecutive_field_cycles_accepted")
        self.assertFalse(chain_check["passed"])
        self.assertEqual(readiness["accepted_qualification_cycle_ids"], [candidate.pk])

    def test_qualification_plan_requires_exact_accepted_form_and_locks_its_lineage(self):
        candidate = self._reconciled_cycle(code="fy-2027-form-required")
        plan = FinanceCutoverQualificationPlan.objects.create(
            cycle=candidate, minimum_consecutive_cycles=2, require_parallel_cycle=False,
            local_authority_reference="Synthetic qualification direction QUAL-FORM-REQ-001",
            accepted_rules_forms_reference="Narrative reference alone must not satisfy this test.",
            field_evidence_basis="Retained field observation and reconciled cycle packets.",
            created_by=self.manager,
        )
        with self.assertRaisesMessage(ValidationError, "Select at least one"):
            submit_cutover_qualification_plan(plan, self.manager)
        row = FinanceCutoverQualificationForm.objects.create(
            plan=plan, local_form=self._accepted_local_form(code="required-dv-control"), position=1,
            use_instructions="Use this exact version at the Budget, Accounting, and Treasury handoffs.",
        )
        submit_cutover_qualification_plan(plan, self.manager)
        row.refresh_from_db()
        self.assertEqual(row.form_submission_checksum, row.local_form.submission_checksum)
        self.assertEqual(row.form_reference_checksum, row.local_form.reference_checksum)
        self.assertEqual(row.form_source_checksum, row.local_form.source_checksum)
        self.assertEqual(row.form_snapshot, row.local_form.submission_snapshot)
        with self.assertRaisesMessage(ValidationError, "cannot be deleted"):
            row.delete()

    def test_manager_can_add_an_accepted_form_with_plain_language_use_instructions(self):
        candidate = self._reconciled_cycle(code="fy-2027-form-ui")
        plan = FinanceCutoverQualificationPlan.objects.create(
            cycle=candidate, minimum_consecutive_cycles=2, require_parallel_cycle=False,
            local_authority_reference="Synthetic qualification direction QUAL-FORM-UI-001",
            accepted_rules_forms_reference="Retained local rules register.",
            field_evidence_basis="Retained field observation and reconciled cycle packets.",
            created_by=self.manager,
        )
        local_form = self._accepted_local_form(code="ui-dv-control")
        self.client.force_login(self.manager)
        url = reverse("finance:cutover_qualification_form_create", args=(plan.pk,))
        response = self.client.get(url)
        self.assertContains(response, local_form.name)
        response = self.client.post(url, {
            "local_form": local_form.pk,
            "position": 1,
            "use_instructions": "Budget certifies, Accounting verifies, and Treasury uses the retained copy.",
        })
        self.assertRedirects(response, reverse("finance:shadow_cycle_detail", args=(candidate.pk,)))
        row = plan.accepted_forms.get()
        self.assertEqual(row.local_form, local_form)
        response = self.client.get(reverse("finance:shadow_cycle_detail", args=(candidate.pk,)))
        self.assertContains(response, "Exact accepted forms used in every qualifying cycle")
        self.assertContains(response, "Treasury uses the retained copy")

    def test_superseded_accepted_form_invalidates_field_qualification_and_export_keeps_lineage(self):
        predecessor = self._reconciled_cycle(code="fy-2027-form-lineage-01")
        candidate = self._reconciled_cycle(
            code="fy-2027-form-lineage-02", predecessor=predecessor,
            run_kind=FinanceShadowCycle.PARALLEL,
        )
        plan = self._approve_qualification(candidate, [predecessor, candidate])
        readiness = cutover_readiness(candidate)
        self.assertTrue(next(
            check for check in readiness["checks"] if check["code"] == "accepted_local_forms_current"
        )["passed"])
        content, _filename, _receipt = build_cutover_evidence_package(candidate, self.manager)
        payload = json.loads(content)
        accepted_forms = payload["cutover_qualification_plan"]["accepted_forms"]
        self.assertEqual(len(accepted_forms), 1)
        self.assertEqual(accepted_forms[0]["submission_checksum"], plan.accepted_forms.get().form_submission_checksum)
        self.assertTrue(payload["cutover_qualification_evidence"][0]["accepted_forms_checksum"])

        local_form = plan.accepted_forms.get().local_form
        local_form.status = FinanceLocalFormAcceptance.SUPERSEDED
        local_form.save()
        readiness = cutover_readiness(candidate)
        self.assertFalse(readiness["ready"])
        self.assertFalse(next(
            check for check in readiness["checks"] if check["code"] == "accepted_local_forms_current"
        )["passed"])

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

    def test_field_acceptance_board_summarizes_existing_records_without_claiming_authority(self):
        cycle = self._cycle(code="fy-2027-acceptance-board")

        board = build_field_acceptance_board(cycle)

        self.assertEqual(board["total_count"], 10)
        self.assertFalse(board["authorized"])
        self.assertFalse(board["cutover_ready"])
        self.assertFalse(board["discovery_scope_accepted"])
        self.assertEqual(
            set(board["missing_discovery_kinds"]),
            FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS,
        )
        self.assertEqual(board["milestones"][-1]["state_label"], "Not started")
        source = next(item for item in board["milestones"] if item["code"] == "source_layout")
        self.assertFalse(source["passed"])
        self.assertIn("No governed current source version", source["evidence"])

        self.client.force_login(self.manager)
        response = self.client.get(reverse("finance:field_acceptance_board"), {"cycle": cycle.pk})
        self.assertContains(response, "Finance Field Acceptance Board")
        self.assertContains(response, cycle.enabled_scope)
        self.assertContains(response, "This board does not approve a phase")
        self.assertContains(response, "10. Cutover authority and rollback")

    def test_assigned_reviewer_can_export_only_a_visible_field_acceptance_board(self):
        cycle = self._cycle(code="fy-2027-acceptance-export")
        FinanceStakeholderAcceptance.objects.create(
            cycle=cycle,
            stakeholder_kind=FinanceStakeholderAcceptance.REQUESTING_OFFICE,
            office=self.requesting,
            assigned_reviewer=self.requesting_reviewer,
            enabled_scope=cycle.enabled_scope,
            created_by=self.manager,
        )
        hidden = self._cycle(code="fy-2027-hidden-acceptance")
        self.client.force_login(self.requesting_reviewer)

        response = self.client.get(
            reverse("finance:field_acceptance_board_export"), {"cycle": cycle.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("finance-field-acceptance", response["X-GRAND-Archive-Path"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("checkpoint_code", content)
        self.assertIn("source_layout", content)
        self.assertIn("grand_authorized", content)
        self.assertIn("missing_discovery_coverage", content)
        event = FinanceAuditEvent.objects.get(
            target_type="financeshadowcycle",
            target_id=str(cycle.pk),
            action="field_acceptance_board_exported",
        )
        self.assertFalse(event.snapshot["grand_authorized"])
        self.assertEqual(
            self.client.get(
                reverse("finance:field_acceptance_board"), {"cycle": hidden.pk},
            ).status_code,
            404,
        )

    def test_field_operation_triage_and_register_share_filters_scope_and_authority_boundary(self):
        candidate = self._cycle(code="fy-2027-register-candidate")
        FinanceShadowCycle.objects.filter(pk=candidate.pk).update(
            title="=FY 2027 field register formula-like title",
        )
        candidate.refresh_from_db()
        unlocked = self._unlocked_cycle(code="fy-2027-register-needs-source")
        FinanceStakeholderAcceptance.objects.create(
            cycle=candidate,
            stakeholder_kind=FinanceStakeholderAcceptance.REQUESTING_OFFICE,
            office=self.requesting,
            assigned_reviewer=self.requesting_reviewer,
            enabled_scope=candidate.enabled_scope,
            created_by=self.manager,
        )
        filters = {
            "attention": "ready_to_prepare", "status": FinanceShadowCycle.DRAFT,
            "run_kind": FinanceShadowCycle.SHADOW, "fiscal_year": "2027",
            "q": "field register formula",
        }

        self.client.force_login(self.manager)
        workspace = self.client.get(reverse("finance:shadow_workspace"), filters)
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, candidate.code)
        self.assertNotContains(workspace, unlocked.code)
        self.assertContains(workspace, "Open the Field Acceptance Board")
        self.assertContains(workspace, "Export these 1 cycles")
        self.assertContains(workspace, "do not accept a phase or authorize GRAND")
        self.assertEqual(workspace.context["visible_count"], 1)

        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            exported = self.client.get(reverse("finance:shadow_cycle_register_export"), filters)
            self.assertEqual(exported.status_code, 200)
            self.assertEqual(exported["X-GRAND-Export-Archived"], "true")
            self.assertEqual(exported["X-Content-Type-Options"], "nosniff")
            rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cycle_public_id"], str(candidate.public_id))
            self.assertEqual(rows[0]["title"], "'=FY 2027 field register formula-like title")
            self.assertEqual(rows[0]["accepted_checkpoints"], "0")
            self.assertEqual(rows[0]["total_checkpoints"], "10")
            self.assertEqual(rows[0]["grand_authorized"], "False")
            self.assertIn("Field Acceptance Board", rows[0]["next_action"])
            relative_path = exported["X-GRAND-Export-Relative-Path"]
            self.assertIn(
                f"{self.accounting.slug}/cutovermanager/finance-field-operation-register/",
                relative_path,
            )
            artifact = Path(export_root, *relative_path.split("/"))
            self.assertEqual(artifact.read_bytes(), exported.content)
            manifest = json.loads(Path(str(artifact) + ".manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["metadata"]["cycle_count"], 1)
            self.assertEqual(manifest["metadata"]["cycle_department_ids"], [self.accounting.pk])
            self.assertIn("do not accept a phase", manifest["metadata"]["authority_boundary"])
            self.assertEqual(manifest["sha256"], exported["X-GRAND-Export-SHA256"])
            self.assertTrue(FinanceAuditEvent.objects.filter(
                department=self.accounting, target_type="financeshadowcycle",
                target_id=str(candidate.pk), action="field_operation_register_exported",
                actor=self.manager,
            ).exists())

            invalid = self.client.get(
                reverse("finance:shadow_cycle_register_export"), {"attention": "unknown"},
            )
            self.assertEqual(
                len(list(csv.reader(io.StringIO(invalid.content.decode("utf-8-sig"))))), 1,
            )

            self.client.force_login(self.requesting_reviewer)
            reviewer_export = self.client.get(
                reverse("finance:shadow_cycle_register_export"), {"q": candidate.code},
            )
            reviewer_rows = list(csv.DictReader(
                io.StringIO(reviewer_export.content.decode("utf-8-sig")),
            ))
            self.assertEqual([row["cycle_code"] for row in reviewer_rows], [candidate.code])
            self.assertIn(
                f"{self.accounting.slug}/cutoverrequesting/finance-field-operation-register/",
                reviewer_export["X-GRAND-Export-Relative-Path"],
            )

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("finance:shadow_cycle_register_export")).status_code, 403,
        )
