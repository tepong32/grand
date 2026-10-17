"""Use actual GRAND identities and authority; never substitute a local HR model."""
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from profiles.models import EmployeeProfile
from inventory.employee_sources import resolve_employee_custodian
from . import test_grand_maintenance


class GrandEmployeeSourceTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        permission = Permission.objects.get(content_type__app_label="inventory", codename="transfer_asset")
        cls.clerk.user_permissions.add(permission)
        cls.viewer.user_permissions.add(permission)
        EmployeeProfile.objects.filter(user=cls.outsider).update(tin="PRIVATE-TAX", address="PRIVATE-ADDRESS")

    def resolve(self, actor=None, user_id=None):
        return resolve_employee_custodian(actor=actor or self.clerk,
                                          user_id=self.outsider.pk if user_id is None else user_id)

    def test_snapshot_is_minimal_read_only_and_detects_department_change(self):
        with CaptureQueriesContext(connections["default"]) as default, CaptureQueriesContext(connections["finance"]) as finance:
            original = self.resolve()
        self.assertEqual(len(finance), 0)
        for query in default:
            self.assertFalse(query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")))
        self.assertEqual(original["source"]["user_local_id"], self.outsider.pk)
        self.assertEqual(original["source"]["department_local_id"], self.other.pk)
        self.assertEqual(set(original["source"]), {"schema", "user_local_id", "employee_profile_local_id",
            "username", "display_name", "department_local_id", "department_label", "account_active"})
        self.assertNotIn("PRIVATE", str(original))
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=self.gso)
        self.assertNotEqual(self.resolve()["sha256"], original["sha256"])

    def test_missing_grant_and_uat_are_denied_including_ungranted_superuser(self):
        for actor in (self.no_grant, self.super_no_grant, self.viewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.resolve(actor=actor)

    def test_disabled_account_and_missing_department_do_not_create_custody_or_exit_facts(self):
        self.outsider.is_active = False
        self.outsider.save(update_fields=("is_active",))
        with self.assertRaises(PermissionDenied):
            self.resolve()
        self.outsider.is_active = True
        self.outsider.save(update_fields=("is_active",))
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=None)
        with self.assertRaises(ValidationError):
            self.resolve()
        self.assertEqual(self.asset.maintenance_cases.count(), 0)

    def test_invalid_ids_fail_without_integer_coercion_or_overflow(self):
        for value in (True, 1.2, "01", "", -1, 2**64):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.resolve(user_id=value)
