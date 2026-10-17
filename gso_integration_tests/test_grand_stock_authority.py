from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from inventory.access import can_stock
from inventory.models import ConsumableItem
from inventory.services import record_stock_movement, update_consumable
from . import test_grand_maintenance


class GrandStockAuthorityTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_consumableitem", "add_consumableitem", "change_consumableitem", "receive_stock",
            "issue_stock", "adjust_stock", "export_stock_register"))
        for actor in (cls.clerk, cls.outsider, cls.viewer):
            actor.user_permissions.add(*permissions)
        cls.item = ConsumableItem.objects.create(department_id=cls.gso.pk, name="GRAND supplies", unit="ream")

    def test_explicit_grants_owner_scope_and_uat_gate_mutations(self):
        for actor in (self.outsider, self.viewer, self.no_grant, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                record_stock_movement(actor=actor, item=self.item, kind="receipt", quantity="1")
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                update_consumable(actor=actor, item=self.item, data={"notes": "Unauthorized"})
        for action in ("add", "change", "receive", "issue", "adjust"):
            self.assertFalse(can_stock(self.viewer, action))
        self.assertTrue(can_stock(self.viewer, "view"))
        self.assertTrue(can_stock(self.viewer, "export"))
        self.assertEqual(self.item.movements.count(), 0)

    def test_authorized_stock_uses_actual_department_without_finance_queries(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            record_stock_movement(actor=self.clerk, item=self.item, kind="receipt", quantity="2.125")
            issue = record_stock_movement(actor=self.clerk, item=self.item, kind="issue", quantity="0.125",
                department_id=self.other.pk, department_label="Untrusted label", recipient="Receiving clerk")
        self.assertEqual(len(finance), 0)
        self.assertEqual(issue.department_label, self.other.name)
        self.assertEqual(self.item.on_hand, 2)

    def test_signed_http_stock_retry_preserves_single_movement_and_denies_uat_replay(self):
        from django.urls import reverse
        self.client.force_login(self.clerk)
        url = reverse("inventory:stock-receive", args=(self.item.pk,))
        response = self.client.get(url)
        token = response.context["form"].initial["request_token"]
        data = {"quantity": "5", "reference": "GRAND-RETRY", "request_token": token}
        with CaptureQueriesContext(connections["finance"]) as finance:
            self.assertEqual(self.client.post(url, data).status_code, 302)
            self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(len(finance), 0)
        self.assertEqual(self.item.on_hand, 5)
        self.assertEqual(self.item.movements.count(), 1)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.client.force_login(self.clerk)
        self.clerk.user_permissions.remove(Permission.objects.get(
            content_type__app_label="inventory", codename="receive_stock"))
        self.assertEqual(self.client.post(url, data).status_code, 403)
