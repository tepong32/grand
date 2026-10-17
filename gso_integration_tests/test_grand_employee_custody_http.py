from time import time
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from profiles.models import EmployeeProfile

from inventory.models import Asset, AssetTransfer
from inventory.services import cancel_asset_transfer
from . import test_grand_employee_custody


class EmployeeCustodyHttpTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_employee_custody.GrandEmployeeCustodyTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.clerk)
        self.url = reverse("inventory:employee-handoff", args=[self.asset.pk])

    def csrf(self):
        return self.client.cookies["csrftoken"].value

    def preview(self):
        response = self.client.get(self.url, {"q": "repair-out"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        response = self.client.post(self.url, {"action": "preview", "query": "repair-out",
            "employee_id": self.outsider.pk, "transfer_date": "2026-10-17",
            "reference": "PAR-HTTP-01", "reason": "Documented receipt",
            "csrfmiddlewaretoken": self.csrf()})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["preview"], response.content.decode())
        return response.context["confirmation"].initial["handoff_token"]

    def confirm(self, token):
        return self.client.post(self.url, {"action": "confirm", "handoff_token": token,
            "csrfmiddlewaretoken": self.csrf()})

    def test_preview_retry_and_named_recipient_in_another_gso_office(self):
        self.assertContains(self.client.get(reverse("inventory:asset-detail", args=[self.asset.pk])),
                            "Hand over to employee")
        token = self.preview()
        self.assertFalse(AssetTransfer.objects.exists())
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(self.confirm(token).status_code, 302)
        transfer = AssetTransfer.objects.get()
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("inventory:asset-transfer-list"))
        self.assertContains(response, "PAR-HTTP-01")
        self.assertContains(response, "Acknowledge receipt")
        self.assertNotContains(response, "Cancel handoff")
        self.assertEqual(self.client.post(reverse("inventory:asset-transfer-acknowledge", args=[transfer.pk]),
            {"csrfmiddlewaretoken": self.csrf()}).status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk)
        self.client.force_login(self.clerk)
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(AssetTransfer.objects.count(), 1)
        self.assertEqual(self.asset.audit_events.count(), 1)
        self.assertRedirects(self.client.get(reverse("inventory:asset-transfer-create", args=[self.asset.pk])),
                             self.url, fetch_redirect_response=False)

    def test_csrf_tampering_expiry_and_actor_binding(self):
        token = self.preview()
        self.assertEqual(self.client.post(self.url, {"action": "confirm", "handoff_token": token}).status_code, 403)
        self.assertContains(self.confirm(token + "changed"), "expired or changed")
        with patch("django.core.signing.time.time", return_value=time() + 1900):
            self.assertContains(self.confirm(token), "expired or changed")
        other_asset = Asset.objects.create(asset_name="Other asset", department_id=self.gso.pk)
        self.assertEqual(self.client.post(reverse("inventory:employee-handoff", args=[other_asset.pk]), {
            "action": "confirm", "handoff_token": token, "csrfmiddlewaretoken": self.csrf()}).status_code, 403)
        EmployeeProfile.objects.filter(user=self.no_grant).update(assigned_department=self.gso)
        self.client.force_login(self.no_grant)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.client.force_login(self.super_no_grant)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.assertFalse(AssetTransfer.objects.exists())

    def test_changed_asset_preview_and_cancelled_retry_do_not_create_new_handoff(self):
        token = self.preview()
        Asset.objects.filter(pk=self.asset.pk).update(assigned_office="Reconciled legacy custodian")
        self.assertEqual(self.confirm(token).status_code, 200)
        self.assertFalse(AssetTransfer.objects.exists())
        token = self.preview()
        self.assertEqual(self.confirm(token).status_code, 302)
        transfer = AssetTransfer.objects.get()
        cancel_asset_transfer(actor=self.clerk, transfer=transfer, reason="Review request")
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(AssetTransfer.objects.count(), 1)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, AssetTransfer.CANCELLED)
