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
from inventory import requisitions as service
from inventory.models import SupplyRequisition
from inventory.services import record_stock_movement
from . import test_grand_stock_authority


class GrandRequisitionTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_stock_authority.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_consumableitem", "record_supply_requisition", "review_supply_requisition", "issue_stock"))
        for actor in (cls.clerk, cls.outsider, cls.viewer, cls.no_grant):
            actor.user_permissions.add(*permissions)
        cls.reviewer = cls.no_grant

    def setUp(self):
        files = TemporaryDirectory()
        self.addCleanup(files.cleanup)
        storage = patch.object(SupplyRequisition._meta.get_field("file"), "storage", FileSystemStorage(location=files.name))
        storage.start()
        self.addCleanup(storage.stop)

    def create(self, actor=None):
        return service.create_request(actor=actor or self.clerk, request_id=uuid4(), requesting_department_id=self.other.pk,
            reference="GRAND-RIS", requested_on=timezone.localdate(), purpose="Office use",
            upload=SimpleUploadedFile("ris.pdf", b"%PDF-supplied approval"), lines=[{"item_id": self.item.pk, "quantity": "3"}])

    def test_native_grants_department_and_issue_link_do_not_touch_finance(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            record_stock_movement(actor=self.clerk, item=self.item, kind="receipt", quantity="5")
            record = self.create()
            record = service.decide_request(actor=self.reviewer, request=record, expected_version=1, action="approve", note="Document checked")
            row = service.fulfill(actor=self.clerk, request=record, expected_version=2, line_id=record.lines.get().pk,
                outcome="issued", quantity="3", recipient="Actual recipient", note="Handed over")
            record.refresh_from_db()
            service.verify_history(record)
        self.assertEqual(len(finance), 0)
        self.assertEqual(record.status, "fulfilled")
        self.assertEqual(row.movement.department_id, self.other.pk)
        self.assertEqual(self.item.on_hand, 2)
        self.assertEqual(row.actor_id, self.clerk.pk)

    def test_grand_owner_uat_and_ungranted_superuser_denied(self):
        for actor in (self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.create(actor)
        record = self.create()
        detail = reverse("inventory:requisition-detail", args=(record.pk,))
        evidence = reverse("inventory:requisition-evidence", args=(record.pk,))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(evidence).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertContains(self.client.get(detail), "GRAND-RIS")
        self.assertEqual(self.client.post(detail, {"operation": "approve", "expected_version": 1, "approve-note": "No authority"}).status_code, 403)
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(reverse("inventory:consumable-list")), "Supplied requisitions")
        self.clerk.user_permissions.clear()
        self.assertEqual(self.client.post(detail, {"operation": "close", "expected_version": 1, "close-note": "Revoked"}).status_code, 404)
