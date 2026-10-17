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
from inventory import supply_returns as service
from inventory.models import SupplyReturn
from inventory.services import record_stock_movement
from . import test_grand_stock_authority


class GrandSupplyReturnTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_stock_authority.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_consumableitem", "record_supply_return", "review_supply_return", "receive_stock"))
        for actor in (cls.clerk, cls.outsider, cls.viewer, cls.no_grant):
            actor.user_permissions.add(*permissions)
        cls.reviewer = cls.no_grant
        record_stock_movement(actor=cls.clerk, item=cls.item, kind="receipt", quantity="5")
        cls.issue = record_stock_movement(actor=cls.clerk, item=cls.item, kind="issue", quantity="5",
            department_id=cls.other.pk, recipient="Original recipient")

    def setUp(self):
        files = TemporaryDirectory()
        self.addCleanup(files.cleanup)
        storage = patch.object(SupplyReturn._meta.get_field("file"), "storage", FileSystemStorage(location=files.name))
        storage.start()
        self.addCleanup(storage.stop)

    def record(self, actor=None):
        return service.record_return(actor=actor or self.clerk, issue=self.issue, request_id=uuid4(),
            expected_source=service.source_basis(self.issue), source_allocation_id=None, quantity="2",
            reference="GRAND-RETURN", returned_by="Returning clerk", observed_on=timezone.localdate(),
            condition_note="Unused and intact", cost_basis_note="No recorded issue cost",
            upload=SimpleUploadedFile("return.pdf", b"%PDF-synthetic return"))

    def test_actual_identities_review_and_return_do_not_touch_finance(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            case = self.record()
            case = service.decide_return(actor=self.reviewer, case=case, expected_version=1, action="accept",
                note="Checked serviceable goods", suitable_for_stock=True)
            service.verify_history(case)
        self.assertEqual(len(finance), 0)
        self.assertEqual(case.movement.department_id, self.other.pk)
        self.assertEqual(case.decided_by_id, self.reviewer.pk)
        self.assertEqual(self.item.on_hand, 2)
        self.assertIsNone(case.movement.unit_cost)

    def test_grants_scope_uat_and_revocation_apply_to_returns(self):
        for actor in (self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.record(actor)
        case = self.record()
        detail = reverse("inventory:supply-return-detail", args=(case.pk,))
        evidence = reverse("inventory:supply-return-evidence", args=(case.pk,))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(evidence).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertContains(self.client.get(detail), "GRAND-RETURN")
        self.assertEqual(self.client.post(detail, {"operation": "accept", "expected_version": 1,
            "accept-note": "No authority", "accept-suitable_for_stock": "on"}).status_code, 403)
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(reverse("inventory:consumable-detail", args=(self.item.pk,))), "Document return")
        self.client.force_login(self.reviewer)
        self.reviewer.user_permissions.remove(Permission.objects.get(content_type__app_label="inventory", codename="receive_stock"))
        self.assertEqual(self.client.post(detail, {"operation": "accept", "expected_version": 1,
            "accept-note": "Revoked", "accept-suitable_for_stock": "on"}).status_code, 403)
