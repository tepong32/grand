from time import time
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import AssetTransfer
from . import test_grand_custody_returns


class CustodyReturnHttpTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_custody_returns.CustodyReturnTests.setUpTestData.__func__(cls)

    def setUp(self):
        test_grand_custody_returns.CustodyReturnTests.setUp(self)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.clerk)
        self.url = reverse("inventory:custody-return-start", args=[self.asset.pk])

    def csrf(self):
        return self.client.cookies["csrftoken"].value

    def payload(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return dict(source_token=response.context["form"].initial["source_token"],
            transfer_date=timezone.localdate().isoformat(), destination_custodian="GSO storeroom", reference="RETURN-HTTP",
            return_condition="serviceable", reason="Witnessed receipt", csrfmiddlewaretoken=self.csrf())

    def test_record_evidence_independent_confirmation_and_private_download(self):
        payload = self.payload()
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        transfer = AssetTransfer.objects.get(kind=AssetTransfer.RETURN)
        detail = reverse("inventory:custody-return-detail", args=[transfer.pk])
        self.assertNotContains(self.client.get(detail), "Confirm return to GSO")
        self.assertEqual(self.client.post(detail, {"operation": "confirm", "expected_version": 1,
            "confirm-note": "Self review", "csrfmiddlewaretoken": self.csrf()}).status_code, 403)
        self.assertEqual(self.client.post(detail, {"operation": "evidence", "expected_version": 1,
            "evidence-note": "Signed receipt", "csrfmiddlewaretoken": self.csrf(),
            "evidence-upload": SimpleUploadedFile("receipt.pdf", b"%PDF-1.4\nreceipt\n%%EOF", content_type="application/pdf")}).status_code, 302)
        evidence = transfer.return_evidence.get()
        download = reverse("inventory:custody-return-evidence", args=[evidence.pk])
        response = self.client.get(download)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
        self.client.force_login(self.verifier)
        self.assertContains(self.client.get(detail), "Confirm return to GSO")
        self.assertEqual(self.client.post(detail, {"operation": "confirm", "expected_version": 2,
            "confirm-note": "Checked receipt and equipment", "csrfmiddlewaretoken": self.csrf()}).status_code, 302)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, AssetTransfer.ACCEPTED)
        returned = self.client.get(reverse("inventory:custody-review"), {"scope": "office", "mode": "returned"})
        self.assertContains(returned, "GRAND repair fixture")
        self.assertEqual(returned.context["legacy_count"], 0)
        self.assertContains(returned, "Last confirmed return")
        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(detail), "Confirmed by")
        self.assertEqual(self.client.post(detail, {"operation": "cancel", "expected_version": 3,
            "cancel-note": "Own return", "csrfmiddlewaretoken": self.csrf()}).status_code, 403)
        # Later custody does not confer access to the former employee's evidence.
        from inventory.employee_sources import resolve_employee_custodian
        from inventory.services import create_asset_transfer, acknowledge_asset_transfer
        from profiles.models import EmployeeProfile
        self.asset.refresh_from_db()
        source = resolve_employee_custodian(actor=self.clerk, user_id=self.verifier.pk)
        handoff = create_asset_transfer(actor=self.clerk, asset=self.asset, data={
            "destination_employee_id": self.verifier.pk, "employee_source_checksum": source["sha256"],
            "transfer_date": timezone.localdate(), "reference": "PAR-NEXT", "reason": "New assignment"})
        acknowledge_asset_transfer(actor=self.verifier, transfer=handoff)
        EmployeeProfile.objects.filter(user=self.verifier).update(assigned_department=self.other)
        self.client.force_login(self.verifier)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(download).status_code, 404)
        personal = self.client.get(reverse("inventory:custody-review"), {"scope": "mine"})
        self.assertContains(personal, "GRAND repair fixture")
        self.assertNotContains(personal, "Last confirmed return")

    def test_csrf_expiry_tampering_and_cross_owner_reads(self):
        payload = self.payload()
        no_csrf = {key: value for key, value in payload.items() if key != "csrfmiddlewaretoken"}
        self.assertEqual(self.client.post(self.url, no_csrf).status_code, 403)
        with patch("django.core.signing.time.time", return_value=time() + 1900):
            self.assertContains(self.client.post(self.url, payload), "expired or changed")
        tampered = dict(payload, source_token=payload["source_token"] + "changed")
        self.assertContains(self.client.post(self.url, tampered), "expired or changed")
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        transfer = AssetTransfer.objects.get(kind=AssetTransfer.RETURN)
        # A different GSO office with view authority cannot read an unrelated return.
        from profiles.models import EmployeeProfile
        EmployeeProfile.objects.filter(user=self.verifier).update(assigned_department=self.other)
        self.client.force_login(self.verifier)
        self.assertEqual(self.client.get(reverse("inventory:custody-return-detail", args=[transfer.pk])).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)
