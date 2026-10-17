from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import StockCountEvidence
from inventory.stock_counts import record_count, stock_basis, attach_count_evidence, decide_count
from . import test_grand_stock_authority


class GrandStockCountTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_stock_authority.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        count_permissions = Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("record_stock_count", "review_stock_count"))
        for actor in (cls.clerk, cls.outsider, cls.viewer, cls.no_grant):
            actor.user_permissions.add(*count_permissions)
        cls.reviewer = cls.no_grant
        cls.reviewer.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("view_consumableitem", "adjust_stock")))

    def setUp(self):
        self.files = TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        storage = patch.object(StockCountEvidence._meta.get_field("file"), "storage", FileSystemStorage(location=self.files.name))
        storage.start()
        self.addCleanup(storage.stop)

    def record(self, actor=None):
        return record_count(actor=actor or self.clerk, item=self.item, request_id=uuid4(),
            expected_basis=stock_basis(self.item), counted_on=timezone.localdate(), quantity="1.125",
            reference="GRAND-COUNT-1", note="Physical count observed")

    def evidence(self, count):
        evidence = attach_count_evidence(actor=self.clerk, count=count, expected_version=1,
            upload=SimpleUploadedFile("count.pdf", b"%PDF-1.4\nCount sheet\n%%EOF", content_type="application/pdf"), note="Signed count")
        count.refresh_from_db()
        return evidence

    def test_native_identity_review_and_surplus_do_not_touch_finance(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            count = self.record()
            self.evidence(count)
            count = decide_count(actor=self.reviewer, count=count, expected_version=2, action="approve", note="Independently checked")
        self.assertEqual(len(finance), 0)
        self.assertEqual(count.recorded_by_id, self.clerk.pk)
        self.assertEqual(count.decided_by_id, self.reviewer.pk)
        self.assertIsNone(count.adjustment.unit_cost)
        self.assertEqual(str(self.item.on_hand), "1.125")

    def test_owner_and_uat_scopes_apply_to_services_pages_and_private_files(self):
        for actor in (self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.record(actor)
        count = self.record()
        evidence = self.evidence(count)
        detail = reverse("inventory:stock-count-detail", args=[count.pk])
        download = reverse("inventory:stock-count-evidence", args=[evidence.pk])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(detail, {"operation":"approve", "expected_version":2, "approve-note":"UAT write"}).status_code, 403)
        self.client.force_login(self.clerk)
        response = self.client.get(download)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
        # The test client's streaming wrapper closes the file on exhaustion.
        Path(evidence.file.path).unlink()
        self.assertEqual(self.client.get(download).status_code, 404)
