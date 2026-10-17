"""Authenticated private downloads and disposal-only asset retirement."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import (Asset, AssetAuditEvent, AssetDisposalAttachment,
    AssetDisposalCase, AssetMaintenanceEvidence, ReceivingEvidence, ReceivingReceipt)
from inventory.maintenance import open_maintenance, attach_maintenance_evidence
from inventory.receiving import attach_receipt_evidence
from inventory import services
from . import test_grand_maintenance


class EvidenceRetirementTests(TestCase):
    databases = {"default", "finance"}
    payload = b"%PDF-synthetic retained source"

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        grants = Permission.objects.filter(content_type__app_label="inventory")
        for actor in (cls.clerk, cls.outsider, cls.viewer):
            actor.user_permissions.add(*grants)

    def setUp(self):
        self.files = TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        for model in (ReceivingEvidence, AssetMaintenanceEvidence, AssetDisposalAttachment):
            storage = patch.object(model._meta.get_field("file"), "storage",
                                   FileSystemStorage(location=self.files.name))
            storage.start()
            self.addCleanup(storage.stop)
        self.client.force_login(self.clerk)

    def upload(self):
        return SimpleUploadedFile("source.pdf", self.payload, content_type="application/pdf")

    def sources(self):
        receipt = ReceivingReceipt.objects.create(department_id=self.gso.pk,
            created_by=self.clerk, delivery_date=timezone.localdate(), inspection_date=timezone.localdate())
        receiving = attach_receipt_evidence(actor=self.clerk, receipt=receipt,
            expected_version=1, kind="delivery", upload=self.upload(), note="Source")
        case = open_maintenance(actor=self.clerk, asset=self.asset,
            data={"reported_date": timezone.localdate(), "problem": "Inspection"})
        maintenance = attach_maintenance_evidence(actor=self.clerk, case=case,
            expected_version=1, upload=self.upload(), note="Source")
        return [(receiving, "receiving-evidence"), (maintenance, "maintenance-evidence")]

    def download(self, row, route):
        response = self.client.get(reverse("inventory:" + route, args=[row.pk]))
        self.addCleanup(self.close_response, response)
        return response

    @staticmethod
    def close_response(response):
        # Consume Django's client wrapper: it closes the file while temporarily
        # disconnecting close_old_connections from request_finished. Calling
        # FileResponse.close() directly can close MySQL inside TestCase's atomic.
        if getattr(response, "streaming", False) and not response.closed:
            for _ in response.streaming_content:
                pass

    def assert_unavailable(self, row, route):
        response = self.download(row, route)
        try:
            self.assertEqual(response.status_code, 404)
        finally:
            self.close_response(response)

    def test_valid_downloads_keep_headers_and_uat_read_authority(self):
        for row, route in self.sources():
            for actor in (self.clerk, self.viewer):
                self.client.force_login(actor)
                response = self.download(row, route)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), self.payload)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response["Content-Type"], "application/octet-stream")
                self.assertIn('attachment;', response["Content-Disposition"])
                self.close_response(response)

    def test_downloads_deny_wrong_office_no_grant_and_anonymous(self):
        for row, route in self.sources():
            for actor, status in ((self.outsider, 404), (self.no_grant, 403)):
                self.client.force_login(actor)
                self.assertEqual(self.download(row, route).status_code, status)
            self.client.logout()
            self.assertEqual(self.download(row, route).status_code, 302)

    def test_same_size_corruption_is_rejected(self):
        for row, route in self.sources():
            Path(row.file.path).write_bytes(b"X" * len(self.payload))
            self.assert_unavailable(row, route)

    def test_size_mismatch_is_rejected(self):
        for row, route in self.sources():
            type(row).objects.filter(pk=row.pk).update(size=row.size + 1)
            self.assert_unavailable(row, route)

    def test_missing_files_are_rejected(self):
        for row, route in self.sources():
            Path(row.file.path).unlink()
            self.assert_unavailable(row, route)

    def test_unknown_hashes_are_not_verified(self):
        for row, route in self.sources():
            type(row).objects.filter(pk=row.pk).update(sha256="")
            self.assert_unavailable(row, route)

    def test_other_namespace_and_traversal_are_rejected_even_with_valid_bytes(self):
        for row, route in self.sources():
            original = row.file.name
            other = Path(self.files.name) / "unrelated.pdf"
            other.write_bytes(self.payload)
            for name in ("unrelated.pdf", "../outside.pdf", str(other)):
                type(row).objects.filter(pk=row.pk).update(file=name)
                self.assert_unavailable(row, route)
            type(row).objects.filter(pk=row.pk).update(file=original)

    def test_cross_record_path_is_rejected(self):
        for row, route in self.sources():
            path = Path(row.file.path)
            other = path.parent.parent / "different-record" / path.name
            other.parent.mkdir()
            other.write_bytes(self.payload)
            type(row).objects.filter(pk=row.pk).update(file=other.relative_to(self.files.name).as_posix())
            self.assert_unavailable(row, route)

    def test_redirected_directory_is_rejected(self):
        import os
        import subprocess
        for row, route in self.sources():
            path = Path(row.file.path)
            original = path.parent
            moved = original.with_name(original.name + "-moved")
            original.rename(moved)
            try:
                if os.name == "nt":
                    subprocess.run(["cmd", "/c", "mklink", "/J", str(original), str(moved)],
                                   check=True, capture_output=True)
                else:
                    original.symlink_to(moved, target_is_directory=True)
                self.assert_unavailable(row, route)
            finally:
                if original.is_symlink():
                    original.unlink()
                elif original.exists():
                    original.rmdir()  # Windows junction only; never recurse into its target.
                moved.rename(original)

    def test_stream_uses_the_single_verified_open(self):
        for row, route in self.sources():
            storage = row.file.storage
            with patch.object(storage, "open", wraps=storage.open) as opened:
                response = self.download(row, route)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(opened.call_count, 1)
                self.assertEqual(b"".join(response.streaming_content), self.payload)
                self.assertEqual(opened.call_count, 1)
                self.close_response(response)

    def test_create_cannot_start_retired(self):
        before = (Asset.objects.count(), AssetAuditEvent.objects.count())
        with self.assertRaises(ValidationError):
            services.create_asset(actor=self.clerk, data={"asset_name": "Bypass", "status": Asset.RETIRED})
        self.assertEqual((Asset.objects.count(), AssetAuditEvent.objects.count()), before)

    def test_update_cannot_retire_and_leaves_no_audit_event(self):
        before = AssetAuditEvent.objects.count()
        with self.assertRaises(ValidationError):
            services.update_asset(actor=self.clerk, asset=self.asset, data={"status": Asset.RETIRED})
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.ACTIVE)
        self.assertEqual(AssetAuditEvent.objects.count(), before)

    def test_ordinary_creation_edits_and_status_transitions_keep_history(self):
        asset = services.create_asset(actor=self.clerk, data={"asset_name": "Chair"})
        services.update_asset(actor=self.clerk, asset=asset, data={"notes": "Checked", "status": Asset.MAINTENANCE})
        services.update_asset(actor=self.clerk, asset=asset, data={"status": Asset.ACTIVE})
        asset.refresh_from_db()
        self.assertEqual((asset.notes, asset.status), ("Checked", Asset.ACTIVE))
        self.assertEqual(list(asset.audit_events.order_by("pk").values_list("action", flat=True)), ["created", "updated", "updated"])

    def test_evidenced_disposal_still_retires_and_retired_history_is_read_only(self):
        case = services.submit_asset_disposal_request(actor=self.clerk, asset=self.asset,
            data={"reason": "Unserviceable", "condition_details": "Inspected", "photos": [self.upload()], "signed_request": self.upload()})
        services.review_asset_disposal_case(actor=self.clerk, case=case, data={"action": "under_review"})
        with self.assertRaises(ValidationError):
            services.review_asset_disposal_case(actor=self.clerk, case=case, data={"action": "authorized"})
        services.review_asset_disposal_case(actor=self.clerk, case=case, data={"action": "authorized",
            "authority_reference": "Synthetic authority", "authority_document": self.upload()})
        completion = dict(action="disposed", disposal_method="destruction", disposal_date=timezone.localdate(),
                          completion_reference="Synthetic completion")
        with self.assertRaises(ValidationError):
            services.review_asset_disposal_case(actor=self.clerk, case=case, data=completion)
        services.review_asset_disposal_case(actor=self.clerk, case=case, data=dict(completion, completion_document=self.upload()))
        self.asset.refresh_from_db()
        case.refresh_from_db()
        self.assertEqual((self.asset.status, case.status), (Asset.RETIRED, AssetDisposalCase.DISPOSED))
        self.assertTrue(self.asset.audit_events.filter(action="disposed").exists())
        with self.assertRaises(PermissionDenied):
            services.update_asset(actor=self.clerk, asset=self.asset, data={"status": Asset.ACTIVE})
