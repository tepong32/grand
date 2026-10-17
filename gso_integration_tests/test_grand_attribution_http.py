from unittest.mock import patch
from time import time

from django.contrib.auth.models import Permission
from django.core import signing
from django.test import Client, TestCase
from django.urls import reverse

from inventory_finance.models import ReceiptClaimAttribution
from vouchers.models import VoucherCase
from . import test_grand_attribution


class AttributionHttpTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_attribution.AttributionTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.clerk)
        self.url = reverse("inventory_finance:propose", args=[self.case.public_id])

    def csrf(self):
        return self.client.cookies["csrftoken"].value

    def preview(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(self.url, {
            "action": "preview", "receipt_line": self.receipt_line.pk, "source_line": self.line.pk,
            "amount": "60.00", "basis": "Invoice and accepted delivery", "csrfmiddlewaretoken": self.csrf(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["preview"])
        return response.context["confirmation"].initial["proposal_token"]

    def confirm(self, token):
        return self.client.post(self.url, {"action": "confirm", "proposal_token": token,
                                         "csrfmiddlewaretoken": self.csrf()})

    def test_preview_confirm_retry_and_independent_review(self):
        page = self.client.get(reverse("inventory_finance:workbench"))
        self.assertEqual(page.status_code, 200)
        token = self.preview()
        self.assertEqual(ReceiptClaimAttribution.objects.count(), 0)
        self.assertEqual(self.confirm(token).status_code, 302)
        row = ReceiptClaimAttribution.objects.get()
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(row.events.count(), 1)
        detail = reverse("inventory_finance:detail", args=[row.public_id])
        self.assertEqual(self.client.post(detail, {"action": "approve", "expected_version": 1,
            "note": "Self review", "csrfmiddlewaretoken": self.csrf()}).status_code, 403)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(detail).status_code, 200)
        response = self.client.post(detail, {"action": "approve", "expected_version": 1,
            "note": "Reviewed source documents", "csrfmiddlewaretoken": self.csrf()})
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, row.APPROVED)
        self.assertEqual(self.client.get(detail).context["form"].fields["action"].choices,
                         [("withdraw", "Withdraw link")])

    def test_csrf_tampering_expiry_and_changed_source_do_not_create_links(self):
        token = self.preview()
        self.assertEqual(self.client.post(self.url, {"action": "confirm", "proposal_token": token}).status_code, 403)
        self.assertEqual(self.confirm(token + "changed").status_code, 200)
        # Expire only this payload; mocking signing.loads would also invalidate
        # Django session decoding and test a login redirect instead of our form.
        payload = signing.loads(token, salt="gso-receipt-claim-proposal-v1")
        with patch("django.core.signing.time.time", return_value=time() - 1900):
            expired = signing.dumps(payload, salt="gso-receipt-claim-proposal-v1")
        self.assertContains(self.confirm(expired), "preview expired")
        VoucherCase.objects.filter(pk=self.case.pk).update(state_version=1)
        self.assertContains(self.confirm(token), "source changed")
        self.assertEqual(ReceiptClaimAttribution.objects.count(), 0)

    def test_signed_preview_cannot_be_submitted_by_another_authorized_actor(self):
        token = self.preview()
        self.no_grant.user_permissions.add(
            Permission.objects.get(content_type__app_label="inventory_finance", codename="propose_receiptclaimattribution"),
            Permission.objects.get(content_type__app_label="vouchers", codename="view_voucher_workbench"))
        self.client.force_login(self.no_grant)
        self.client.get(self.url)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.assertEqual(ReceiptClaimAttribution.objects.count(), 0)

    def test_outsider_cannot_read_record_or_case_form(self):
        self.confirm(self.preview())
        row = ReceiptClaimAttribution.objects.get()
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("inventory_finance:detail", args=[row.public_id])).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
