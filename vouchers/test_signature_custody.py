from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from departments.models import Department
from profiles.models import EmployeeProfile
from .access import can_view_workbench
from .models import VoucherCase, WetSignatureTask
from .services import VoucherWorkflowError, record_signature_return


class SignatureTaskAuthorityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.office = Department.objects.create(name="Accounting custody", slug="signature-boundary-accounting")
        cls.other_office = Department.objects.create(name="Other custody", slug="signature-boundary-other")
        cls.operator = cls._operator("signature.first", cls.office)
        cls.second_operator = cls._operator("signature.second", cls.office)
        cls.other_operator = cls._operator("signature.other", cls.other_office)

    @classmethod
    def _operator(cls, username, department):
        user = get_user_model().objects.create_user(username=username, email=f"{username}@example.test")
        profile, _ = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(Permission.objects.get(content_type__app_label="vouchers", codename="track_wet_signatures"))
        return get_user_model().objects.get(pk=user.pk)

    def _case(self, reference, *, foreign=False):
        department = self.other_office if foreign else self.office
        return VoucherCase.objects.create(
            reference_code=reference, requesting_department=department, current_department=department,
            current_stage=VoucherCase.AWAITING_SIGNATURES, payee_name="Synthetic payee",
            particulars="Isolated signature custody boundary test.",
            created_by=self.other_operator if foreign else self.operator,
        )

    def _task(self, case, sequence):
        return WetSignatureTask.objects.create(case=case, round_number=1, sequence=sequence,
            role_code=f"role-{sequence}", signatory_name_snapshot=f"Synthetic signatory {sequence}")

    def _record(self, case, task, *, actor=None, key="record", note="Retained physical return"):
        return record_signature_return(case=case, task=task, actor=actor or self.operator,
            note=note, expected_version=case.state_version, idempotency_key=key)

    def test_stale_pending_instance_cannot_overwrite_recorded_return(self):
        case = self._case("SIG-STALE")
        first = self._task(case, 1)
        self._task(case, 2)
        stale = WetSignatureTask.objects.get(pk=first.pk)
        self._record(case, first, key="original-return")
        case.refresh_from_db(); first.refresh_from_db()
        before = (first.recorded_by_id, first.recorded_at, first.note, case.state_version, case.events.count())
        with self.assertRaises(VoucherWorkflowError):
            self._record(case, stale, actor=self.second_operator, key="overwrite-attempt", note="Must not replace prior custody")
        case.refresh_from_db(); first.refresh_from_db()
        self.assertEqual((first.recorded_by_id, first.recorded_at, first.note, case.state_version, case.events.count()), before)

    def test_altered_case_link_cannot_write_another_cases_task(self):
        case = self._case("SIG-AUTHORIZED")
        self._task(case, 1)
        foreign = self._case("SIG-FOREIGN", foreign=True)
        foreign_task = self._task(foreign, 1)
        supplied = WetSignatureTask.objects.get(pk=foreign_task.pk)
        supplied.case_id = case.pk
        with self.assertRaises(VoucherWorkflowError):
            self._record(case, supplied, key="foreign-task-attempt")
        case.refresh_from_db(); foreign_task.refresh_from_db()
        self.assertEqual(foreign_task.case_id, foreign.pk)
        self.assertEqual(foreign_task.status, WetSignatureTask.PENDING)
        self.assertIsNone(foreign_task.recorded_by_id)
        self.assertEqual((case.state_version, case.events.count(), foreign.events.count()), (0, 0, 0))

    def test_altered_sequence_cannot_skip_the_stored_order(self):
        case = self._case("SIG-ORDER")
        self._task(case, 1)
        second = self._task(case, 2)
        second.sequence = 0
        with self.assertRaises(VoucherWorkflowError):
            self._record(case, second, key="skip-order-attempt")
        second.refresh_from_db(); case.refresh_from_db()
        self.assertEqual((second.sequence, second.status), (2, WetSignatureTask.PENDING))
        self.assertEqual((case.state_version, case.events.count()), (0, 0))

    def test_normal_order_and_same_key_retry_preserve_custody(self):
        case = self._case("SIG-NORMAL")
        first = self._task(case, 1)
        second = self._task(case, 2)
        self._record(case, first, key="first")
        first.refresh_from_db(); case.refresh_from_db()
        original = (first.recorded_by_id, first.recorded_at, first.note)
        self._record(case, first, key="first", note="Retry must not replace evidence")
        first.refresh_from_db(); case.refresh_from_db()
        self.assertEqual((first.recorded_by_id, first.recorded_at, first.note), original)
        self.assertEqual(case.events.count(), 1)
        self._record(case, second, key="second")
        case.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(second.status, WetSignatureTask.SIGNED_RETURNED)
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_VALIDATION)
        self.assertEqual(case.events.count(), 2)

    def test_uat_with_combined_signature_permission_remains_read_only(self):
        case = self._case("SIG-UAT")
        task = self._task(case, 1)
        self.operator.groups.add(Group.objects.get_or_create(name="Finance UAT Viewer")[0])
        self.assertTrue(can_view_workbench(self.operator))
        with self.assertRaises(PermissionDenied):
            self._record(case, task, key="uat-return")
        task.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(task.status, WetSignatureTask.PENDING)
        self.assertEqual((case.state_version, case.events.count()), (0, 0))
