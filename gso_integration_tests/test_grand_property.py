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
from inventory import property_determinations as service
from inventory.models import PropertyDetermination as Record
from . import test_grand_maintenance


class GrandPropertyTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        grants = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_asset", "record_property_determination", "review_property_determination"))
        for actor in (cls.clerk, cls.no_grant, cls.viewer, cls.outsider):
            actor.user_permissions.add(*grants)
        cls.reviewer = cls.no_grant

    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        storage = patch.object(Record._meta.get_field("file"), "storage", FileSystemStorage(location=root.name))
        storage.start()
        self.addCleanup(storage.stop)

    def record(self, actor=None):
        return service.record(actor=actor or self.clerk, asset=self.asset, request_id=uuid4(),
            expected_source=service.source_basis(self.asset), expected_predecessor=None,
            data=dict(treatment="semi_expendable", reference="GRAND-PROPERTY", source_date=timezone.localdate(),
                source_authority="Supplied authority", property_class="", fund_label="", useful_life=None,
                life_unit="", life_basis="", life_start=None, expires_on=None, reason="Source retention"),
            upload=SimpleUploadedFile("property.pdf", b"%PDF-native sources"))

    def test_native_identities_review_and_history_do_not_touch_finance(self):
        original = self.asset.assigned_department_id
        with CaptureQueriesContext(connections["finance"]) as finance:
            row = self.record()
            row = service.decide(actor=self.reviewer, row=row, expected_version=1, action="verify", note="Source checked")
            service.verify_history(row)
            self.client.force_login(self.clerk)
            self.assertContains(self.client.get(reverse("inventory:asset-detail", args=[self.asset.pk])), "Property documents and useful life")
            self.assertContains(self.client.get(reverse("inventory:property-detail", args=[row.pk])), "GRAND-PROPERTY")
        self.assertEqual(len(finance), 0)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_department_id, original)
        self.assertEqual(row.recorded_by_id, self.clerk.pk)
        self.assertEqual(row.decided_by_id, self.reviewer.pk)

    def test_owner_explicit_grants_uat_and_revocation(self):
        for actor in (self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.record(actor)
        row = self.record()
        detail = reverse("inventory:property-detail", args=[row.pk])
        source = reverse("inventory:property-evidence", args=[row.pk])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(source).status_code, 404)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertContains(self.client.get(detail), "GRAND-PROPERTY")
        self.assertEqual(self.client.post(detail, {"operation": "verify", "expected_version": 1, "verify-note": "Denied"}).status_code, 403)
        self.reviewer.user_permissions.remove(Permission.objects.get(content_type__app_label="inventory", codename="review_property_determination"))
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(detail, {"operation": "verify", "expected_version": 1, "verify-note": "Revoked"}).status_code, 403)

    def test_working_register_uses_native_scope_without_finance_queries(self):
        row = self.record()
        service.decide(actor=self.reviewer, row=row, expected_version=1, action="verify", note="Checked")
        url = reverse("inventory:property-register")
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            with CaptureQueriesContext(connections["finance"]) as queries:
                response = self.client.get(url)
            self.assertContains(response, "GRAND-PROPERTY")
            self.assertEqual(len(queries), 0)
            self.assertEqual(self.client.post(url).status_code, 405)
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(url), "GRAND-PROPERTY")
        self.client.force_login(self.super_no_grant)
        self.assertEqual(self.client.get(url).status_code, 403)
