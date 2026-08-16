from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from departments.models import Department

from .credentials import CredentialError, digest_token, issue_daily_credential, resolve_daily_credential, revoke_daily_credential
from .models import DailyEmployeeCredential, EmployeeCredentialEvent, TrackedPacket
from .qr import QRPayloadError, employee_qr_payload, packet_qr_payload, render_qr_png
from .services import create_packet


class TracePointCredentialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(name="Municipal Social Welfare and Development Office", slug="mswd-qr")
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="accounting-qr")
        users = get_user_model()
        cls.preparer = users.objects.create_user(username="qr-preparer", email="qr-preparer@example.gov", password="test-password")
        cls.employee = users.objects.create_user(username="qr-employee", email="qr-employee@example.gov", password="test-password")
        cls.supervisor = users.objects.create_user(username="qr-supervisor", email="qr-supervisor@example.gov", password="test-password")
        cls.outsider = users.objects.create_user(username="qr-outsider", email="qr-outsider@example.gov", password="test-password")
        for user, department in (
            (cls.preparer, cls.mswd),
            (cls.employee, cls.accounting),
            (cls.supervisor, cls.accounting),
            (cls.outsider, cls.mswd),
        ):
            user.employeeprofile.assigned_department = department
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.preparer.user_permissions.add(Permission.objects.get(codename="prepare_tracked_packets"))
        cls.supervisor.user_permissions.add(Permission.objects.get(codename="revoke_employee_credentials"))

    def _packet(self):
        return create_packet(
            actor=self.preparer,
            title="Synthetic voucher packet",
            contents_manifest="Synthetic pages only",
            final_destination_department=self.accounting,
            final_destination_employee=self.employee,
        )

    def test_daily_token_is_random_hash_only_and_expires_at_next_local_day(self):
        issued = issue_daily_credential(employee=self.employee)

        self.assertNotEqual(issued.token, issued.credential.token_digest)
        self.assertEqual(issued.credential.token_digest, digest_token(issued.token))
        self.assertNotIn(self.employee.username, issued.token)
        self.assertEqual(issued.credential.valid_on, timezone.localdate())
        self.assertEqual(timezone.localtime(issued.credential.expires_at).date(), timezone.localdate() + timedelta(days=1))
        self.assertTrue(issued.credential.is_valid)
        self.assertEqual(resolve_daily_credential(issued.token), issued.credential)
        self.assertTrue(issued.credential.events.filter(action="issued").exists())

    def test_second_code_requires_explicit_replacement_and_invalidates_first(self):
        first = issue_daily_credential(employee=self.employee)
        with self.assertRaisesMessage(CredentialError, "already exists"):
            issue_daily_credential(employee=self.employee)

        second = issue_daily_credential(employee=self.employee, replace=True, replacement_reason="Badge screenshot exposed")
        first.credential.refresh_from_db()
        self.assertEqual(first.credential.replaced_by, second.credential)
        self.assertEqual(first.credential.revocation_reason, "Badge screenshot exposed")
        self.assertFalse(first.credential.is_valid)
        with self.assertRaises(CredentialError):
            resolve_daily_credential(first.token)
        self.assertEqual(resolve_daily_credential(second.token), second.credential)
        self.assertEqual(DailyEmployeeCredential.objects.filter(employee=self.employee, revoked_at__isnull=True).count(), 1)

    def test_self_or_authorized_department_supervisor_can_revoke(self):
        issued = issue_daily_credential(employee=self.employee)
        with self.assertRaisesMessage(CredentialError, "not allowed"):
            revoke_daily_credential(credential=issued.credential, actor=self.outsider, reason="Not my department")

        revoke_daily_credential(credential=issued.credential, actor=self.supervisor, reason="Employee reported code loss")
        self.assertFalse(issued.credential.is_valid)
        event = EmployeeCredentialEvent.objects.get(credential=issued.credential, action="revoked")
        self.assertEqual(event.actor, self.supervisor)

    def test_disabled_or_unassigned_employee_code_stops_resolving(self):
        issued = issue_daily_credential(employee=self.employee)
        self.employee.is_active = False
        self.employee.save(update_fields=("is_active",))
        with self.assertRaises(CredentialError):
            resolve_daily_credential(issued.token)

        self.employee.is_active = True
        self.employee.save(update_fields=("is_active",))
        self.employee.employeeprofile.assigned_department = None
        self.employee.employeeprofile.save(update_fields=("assigned_department",))
        with self.assertRaises(CredentialError):
            resolve_daily_credential(issued.token)

    def test_packet_qr_is_stable_and_contains_no_descriptive_or_personal_data(self):
        packet = self._packet()
        first = packet_qr_payload(packet, base_url="https://grand.example.gov/")
        second = packet_qr_payload(packet, base_url="https://grand.example.gov")

        self.assertEqual(first, second)
        self.assertIn(str(packet.public_id), first)
        self.assertNotIn(packet.title, first)
        self.assertNotIn(self.preparer.username, first)
        self.assertTrue(render_qr_png(first).startswith(b"\x89PNG\r\n\x1a\n"))

    def test_employee_qr_contains_only_opaque_token_and_safe_portal_path(self):
        issued = issue_daily_credential(employee=self.employee)
        payload = employee_qr_payload(issued.token, base_url="https://grand.example.gov")

        self.assertIn(issued.token, payload)
        self.assertNotIn(self.employee.username, payload)
        self.assertNotIn(self.employee.email, payload)
        self.assertTrue(render_qr_png(payload).startswith(b"\x89PNG\r\n\x1a\n"))
        with self.assertRaises(QRPayloadError):
            packet_qr_payload(self._packet(), base_url="javascript:alert(1)")
