"""Maintenance uses GRAND identities, explicit grants and its actual router."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from inventory.models import Asset
from inventory.maintenance import open_maintenance, update_maintenance, close_maintenance


class GrandMaintenanceTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.gso = Department.objects.create(name="General Services Office", slug="gso")
        cls.other = Department.objects.create(name="General Services", slug="other-gso")
        permission = Permission.objects.get(content_type__app_label="inventory", codename="manage_assetmaintenancecase")
        def actor(name, department, grant=True, superuser=False):
            user = get_user_model().objects.create_user(username=name, email=f"{name}@example.test",
                                                        is_superuser=superuser)
            EmployeeProfile.objects.filter(user=user).update(assigned_department=department)
            if grant:
                user.user_permissions.add(permission)
            user.refresh_from_db()
            return user
        cls.clerk = actor("repair-clerk", cls.gso)
        cls.outsider = actor("repair-outsider", cls.other)
        cls.no_grant = actor("repair-ungranted", cls.gso, grant=False)
        cls.super_no_grant = actor("repair-super-ungranted", cls.gso, grant=False, superuser=True)
        cls.viewer = actor("repair-uat", cls.gso)
        cls.viewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        cls.asset = Asset.objects.create(department_id=cls.gso.pk, asset_name="GRAND repair fixture",
                                         assigned_department_id=cls.other.pk, assigned_office="Original custodian")

    def start(self, actor=None):
        return open_maintenance(actor=actor or self.clerk, asset=self.asset,
                                 data={"reported_date": timezone.localdate(), "problem": "Inspection"})

    def test_real_profile_grants_and_router_preserve_finance_and_custody(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            case = self.start()
            case = update_maintenance(actor=self.clerk, case=case, expected_version=1,
                                       data={"work_performed": "Tested brakes", "documented_cost": "0.00"})
            case = close_maintenance(actor=self.clerk, case=case, expected_version=2, action="completed",
                finished_date=timezone.localdate(), note="Passed", outcome="active")
        self.assertEqual(len(finance), 0)
        self.assertEqual(case.events.count(), 3)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_department_id, self.other.pk)
        self.assertEqual(case.opened_by_id, self.clerk.pk)

    def test_explicit_grant_owner_and_uat_controls_are_required(self):
        for actor in (self.outsider, self.no_grant, self.super_no_grant, self.viewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.start(actor)
        self.assertEqual(self.asset.maintenance_cases.count(), 0)

    def test_http_scope_uses_grand_employee_profile(self):
        case = self.start()
        url = reverse("inventory:maintenance-detail", args=(case.pk,))
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(url), "GRAND repair fixture")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(url, {"operation": "close"}).status_code, 403)
