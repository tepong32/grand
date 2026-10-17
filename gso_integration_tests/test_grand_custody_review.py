from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from inventory.models import Asset, AssetTransfer
from inventory.employee_sources import resolve_employee_custodian
from inventory.services import create_asset_transfer, acknowledge_asset_transfer
from . import test_grand_employee_custody


class CustodyReviewTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_employee_custody.GrandEmployeeCustodyTests.setUpTestData.__func__(cls)
        source = resolve_employee_custodian(actor=cls.clerk, user_id=cls.outsider.pk)
        transfer = create_asset_transfer(actor=cls.clerk, asset=cls.asset, data={
            "destination_employee_id": cls.outsider.pk, "employee_source_checksum": source["sha256"],
            "transfer_date": timezone.localdate(), "reference": "PAR-REVIEW", "reason": "Retained assignment"})
        acknowledge_asset_transfer(actor=cls.outsider, transfer=transfer)
        cls.asset.refresh_from_db()
        cls.legacy = Asset.objects.create(asset_name="Unlinked paper register", department_id=cls.gso.pk,
                                          assigned_office="repair-outsider")
        cls.hidden = Asset.objects.create(asset_name="Other office confidential record", department_id=cls.other.pk)
        cls.url = reverse("inventory:custody-review")

    def test_owner_review_retains_legacy_separately_without_finance_or_mutation(self):
        before = list(Asset.objects.order_by("pk").values())
        self.client.force_login(self.clerk)
        with CaptureQueriesContext(connections["finance"]) as finance:
            response = self.client.get(self.url)
        self.assertEqual(len(finance), 0)
        self.assertContains(response, "GRAND repair fixture")
        self.assertContains(response, "1 unlinked legacy record")
        self.assertNotContains(response, "Other office confidential record")
        self.assertNotContains(response, "Unlinked paper register")
        legacy = self.client.get(self.url, {"scope": "office", "mode": "legacy"})
        self.assertContains(legacy, "Unlinked paper register")
        self.assertNotContains(legacy, "GRAND repair fixture")
        self.assertEqual(before, list(Asset.objects.order_by("pk").values()))
        self.assertEqual(AssetTransfer.objects.count(), 1)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)

    def test_personal_history_survives_hr_move_without_expanding_office_write_scope(self):
        moved = Department.objects.create(name="Engineering", slug="engineering")
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=moved)
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, {"scope": "mine"})
        self.assertContains(response, "GRAND repair fixture")
        self.assertContains(response, "HR department differs")
        self.assertNotContains(response, reverse("inventory:asset-detail", args=[self.asset.pk]))
        self.assertNotContains(response, "Unlinked paper register")
        self.assertNotContains(response, "Other office confidential record")
        self.assertEqual(self.client.get(self.url, {"scope": "office"}).status_code, 403)
        self.assertEqual(self.client.get(self.url, {"scope": "mine", "mode": "legacy"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("inventory:asset-edit", args=[self.asset.pk])).status_code, 403)

    def test_inactive_or_missing_profile_does_not_erase_retained_records(self):
        type(self.outsider).objects.filter(pk=self.outsider.pk).update(is_active=False)
        self.client.force_login(self.clerk)
        response = self.client.get(self.url)
        self.assertContains(response, "GRAND repair fixture")
        self.assertContains(response, "Current HR record unavailable")
        EmployeeProfile.objects.filter(user=self.outsider).delete()
        response = self.client.get(self.url)
        self.assertContains(response, "GRAND repair fixture")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk)
        self.assertEqual(self.asset.custodian_snapshot["username"], "repair-outsider")

    def test_pending_incoming_is_separate_from_current_custody_and_empty_is_not_clearance(self):
        source = resolve_employee_custodian(actor=self.clerk, user_id=self.no_grant.pk)
        create_asset_transfer(actor=self.clerk, asset=self.asset, data={
            "destination_employee_id": self.no_grant.pk, "employee_source_checksum": source["sha256"],
            "transfer_date": timezone.localdate(), "reference": "PAR-PENDING-REVIEW", "reason": "Pending receipt"})
        self.client.force_login(self.no_grant)
        response = self.client.get(self.url, {"scope": "mine"})
        self.assertContains(response, "No matching retained assignments")
        self.assertContains(response, "PAR-PENDING-REVIEW")
        self.assertContains(response, "This does not establish clearance")
        self.assertEqual(response.context["named_count"], 0)
        self.assertEqual(response.context["pending_page"].paginator.count, 1)

    def test_grand_department_and_explicit_view_permission_gates_are_preserved(self):
        self.client.force_login(self.super_no_grant)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=None)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url, {"scope": "mine"}).status_code, 403)
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(self.url), "No current HR department")
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=self.other)
        self.client.force_login(self.outsider)
        self.outsider.user_permissions.remove(Permission.objects.get(codename="view_asset", content_type__app_label="inventory"))
        self.assertEqual(self.client.get(self.url, {"scope": "mine"}).status_code, 403)

    def test_search_uses_retained_identity_without_matching_another_owners_record(self):
        Asset.objects.filter(pk=self.asset.pk).update(assigned_office="Recorded employee name")
        type(self.outsider).objects.filter(pk=self.outsider.pk).update(username="renamed-employee")
        Asset.objects.filter(pk=self.hidden.pk).update(custodian_user=self.outsider,
            custodian_snapshot=self.asset.custodian_snapshot)
        self.client.force_login(self.clerk)
        response = self.client.get(self.url, {"q": "repair-outsider"})
        self.assertContains(response, "GRAND repair fixture")
        self.assertContains(response, "Employee identity or office label changed")
        self.assertNotContains(response, "Other office confidential record")
        self.assertEqual(response.context["page"].paginator.count, 1)
