"""Receiving must respect GRAND's explicit grants and read-only UAT role."""
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import ReceivingEvidence, ReceivingReceipt, Asset
from inventory.receiving import (require_receiving, create_receipt, update_receipt,
    save_receipt_line, attach_receipt_evidence, submit_receipt, accept_receipt)
from . import test_grand_maintenance


class GrandReceivingAuthorityTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_receivingreceipt", "add_receivingreceipt", "change_receivingreceipt",
            "submit_receivingreceipt", "review_receivingreceipt", "add_asset", "change_asset", "view_asset"))
        for actor in (cls.clerk, cls.outsider, cls.viewer, cls.no_grant):
            actor.user_permissions.add(*permissions)
        cls.reviewer = cls.no_grant

    def setUp(self):
        files = TemporaryDirectory()
        self.addCleanup(files.cleanup)
        storage = patch.object(ReceivingEvidence._meta.get_field("file"), "storage", FileSystemStorage(location=files.name))
        storage.start()
        self.addCleanup(storage.stop)

    def data(self):
        return dict(supplier="Synthetic supplier", delivery_reference="AUTH-RECEIPT",
            delivery_date=timezone.localdate(), inspection_reference="AUTH-INSPECTION",
            inspection_date=timezone.localdate(), inspector_label="Synthetic inspector",
            evidence_reference="Synthetic private documents")

    def test_implicit_superuser_and_uat_writes_are_denied(self):
        for action in ("view", "add", "change", "submit", "review"):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                require_receiving(self.super_no_grant, action)
        for action in ("add", "change", "submit", "review"):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                require_receiving(self.viewer, action)
        self.assertEqual(require_receiving(self.viewer, "view"), self.gso)
        with self.assertRaises(PermissionDenied):
            create_receipt(actor=self.viewer, data=self.data())
        self.assertEqual(ReceivingReceipt.objects.count(), 0)

    def test_scoped_uat_reads_hide_controls_and_reject_direct_posts(self):
        receipt = create_receipt(actor=self.clerk, data=self.data())
        detail = reverse("inventory:receiving-detail", args=[receipt.pk])
        self.client.force_login(self.viewer)
        page = self.client.get(detail)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Save corrections")
        self.assertNotContains(page, "Submit for independent review")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertNotContains(self.client.get(reverse("inventory:receiving-list")),
                               'href="' + reverse("inventory:receiving-create") + '"')
        self.assertEqual(self.client.post(detail, dict(self.data(), action="header", expected_version=1)).status_code, 403)
        self.assertEqual(self.client.get(reverse("inventory:receiving-create")).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        with self.assertRaises(PermissionDenied):
            update_receipt(actor=self.outsider, receipt=receipt, expected_version=1, data=self.data())
        receipt.refresh_from_db()
        self.assertEqual(receipt.state_version, 1)
        self.assertEqual(receipt.events.count(), 1)

    def test_granted_receiving_acceptance_and_private_read_preserve_finance(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            receipt = create_receipt(actor=self.clerk, data=self.data())
            save_receipt_line(actor=self.clerk, receipt=receipt, expected_version=1,
                data=dict(kind="asset", description="Received printer", unit="unit", delivered_quantity=1,
                    accepted_quantity=1, rejected_quantity=0, property_tag="AUTH-PRINTER", unit_cost="100.00"))
            receipt.refresh_from_db()
            for kind in ("delivery", "inspection"):
                evidence = attach_receipt_evidence(actor=self.clerk, receipt=receipt,
                    expected_version=receipt.state_version, kind=kind, note="Synthetic signed source",
                    upload=SimpleUploadedFile(kind+".pdf", b"%PDF-1.4\nSynthetic\n%%EOF", content_type="application/pdf"))
                receipt.refresh_from_db()
            receipt = submit_receipt(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version)
            with self.assertRaises(PermissionDenied):
                accept_receipt(actor=self.viewer, receipt=receipt, expected_version=receipt.state_version, note="UAT attempt")
            with self.assertRaises(PermissionDenied):
                accept_receipt(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version, note="Self review")
            receipt = accept_receipt(actor=self.reviewer, receipt=receipt, expected_version=receipt.state_version,
                                     note="Independently checked source documents")
            from inventory.services import update_asset
            from inventory.forms import AssetForm
            asset = receipt.lines.get().registered_asset
            with self.assertRaisesMessage(ValidationError, "Retain the accepted receipt"):
                update_asset(actor=self.clerk, asset=asset, data={"unit_cost": 1})
            self.client.force_login(self.clerk)
            edit_url = reverse("inventory:asset-edit", args=[asset.pk])
            page = self.client.get(edit_url)
            self.assertEqual(page.status_code, 200)
            self.assertTrue(page.context["form"].fields["unit_cost"].disabled)
            form = AssetForm(instance=asset)
            payload = {key: value for key, value in form.initial.items() if value is not None}
            payload.update(unit_cost="1.00", supplier="Forged", notes="Legitimate description update")
            self.assertEqual(self.client.post(edit_url, payload).status_code, 302)
            asset.refresh_from_db()
            self.assertEqual(asset.unit_cost, 100)
            self.assertEqual(asset.supplier, "Synthetic supplier")
            self.assertEqual(asset.notes, "Legitimate description update")
        self.assertEqual(len(finance), 0)
        self.assertEqual(receipt.status, receipt.ACCEPTED)
        self.assertEqual(Asset.objects.filter(property_tag="AUTH-PRINTER").count(), 1)
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("inventory:receiving-evidence", args=[evidence.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("inventory:receiving-evidence", args=[evidence.pk])).status_code, 404)
