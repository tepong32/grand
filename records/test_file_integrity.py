"""Authenticated regression coverage for retained, separately uploaded record files."""
import hashlib
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.storage import FileSystemStorage, Storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.http import FileResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from departments.models import Department
from .models import DepartmentRecord, RecordEvent, RecordFile
from .services import create_record


class RecordFileIntegrityTests(TestCase):
    databases = {"default", "finance"}
    payload = b"retained departmental evidence"

    @classmethod
    def setUpTestData(cls):
        cls.office = Department.objects.create(name="Records integrity office", slug="records-integrity")
        cls.other = Department.objects.create(name="Other integrity office", slug="other-integrity")
        users = get_user_model()
        cls.clerk = users.objects.create_user(username="file-integrity-clerk", email="file-integrity-clerk@example.test")
        cls.reader = users.objects.create_user(username="file-integrity-reader", email="file-integrity-reader@example.test")
        cls.outsider = users.objects.create_user(username="file-integrity-outsider", email="file-integrity-outsider@example.test")
        view = Permission.objects.get(content_type__app_label="records", codename="view_records_workspace")
        download = Permission.objects.get(content_type__app_label="records", codename="download_department_records")
        for actor, office in ((cls.clerk, cls.office), (cls.reader, cls.office), (cls.outsider, cls.other)):
            actor.employeeprofile.assigned_department = office
            actor.employeeprofile.save(update_fields=("assigned_department",))
            actor.user_permissions.add(view)
        cls.clerk.user_permissions.add(download)
        cls.outsider.user_permissions.add(download)

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.storage = FileSystemStorage(location=directory.name)
        storage_patch = patch.object(RecordFile._meta.get_field("file"), "storage", self.storage)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        self.record = create_record(
            department=self.office, actor=self.clerk, title="Synthetic correspondence",
            uploaded_file=SimpleUploadedFile("note.txt", self.payload, content_type="text/plain"),
        )
        self.item = self.record.files.get()
        self.path = Path(self.item.file.path)
        self.url = reverse("records:download_file", args=(self.record.public_id, self.item.pk))
        self.client.force_login(self.clerk)

    @staticmethod
    def close_response(response):
        # Client wraps the stream to close its file while isolating connection
        # signals. Exhaust that wrapper, including on an unexpected red response.
        if response.streaming:
            for _ in response.streaming_content:
                pass

    def assert_unavailable(self):
        before = RecordEvent.objects.filter(record=self.record).count()
        response = self.client.get(self.url)
        try:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(RecordEvent.objects.filter(record=self.record).count(), before)
        finally:
            self.close_response(response)

    def test_valid_file_streams_from_the_single_verified_handle_and_is_audited(self):
        opened = []
        original = self.storage.open
        def observe(*args, **kwargs):
            source = original(*args, **kwargs)
            opened.append(source)
            return source
        with patch.object(self.storage, "open", side_effect=observe) as opening, \
                patch("records.views.FileResponse", wraps=FileResponse) as responding:
            with CaptureQueriesContext(connections["finance"]) as finance:
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(opening.call_count, 1)
                self.assertIs(responding.call_args.args[0].file, opened[0])
                self.assertEqual(b"".join(response.streaming_content), self.payload)
            self.assertEqual(len(finance), 0)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(int(response["Content-Length"]), len(self.payload))
        self.assertIn('attachment; filename="note.txt"', response["Content-Disposition"])
        event = self.record.events.get(action="downloaded_file")
        self.assertEqual(event.actor, self.clerk)
        self.assertEqual(event.metadata, {"file_id": self.item.pk, "checksum": self.item.checksum})
        self.close_response(response)
        self.assertTrue(opened[0].closed)

    def test_same_size_corruption_is_rejected_without_a_download_event(self):
        self.path.write_bytes(b"X" * len(self.payload))
        self.assert_unavailable()

    def test_retained_size_and_hash_are_both_required(self):
        RecordFile.objects.filter(pk=self.item.pk).update(size_bytes=len(self.payload) + 1)
        self.assert_unavailable()
        RecordFile.objects.filter(pk=self.item.pk).update(size_bytes=len(self.payload), checksum="")
        self.assert_unavailable()

    def test_missing_file_is_an_unavailable_document_without_a_download_event(self):
        self.path.unlink()
        self.assert_unavailable()

    def test_other_record_and_unsafe_names_fail_before_storage_is_opened(self):
        original = self.item.file.name
        other = self.path.parent.parent / "00000000-0000-0000-0000-000000000000" / "note.txt"
        other.parent.mkdir()
        other.write_bytes(self.payload)
        variants = (other.relative_to(self.storage.location).as_posix(),
                    "unrelated.txt", "../outside.txt", str(self.path),
                    original.replace("/", "\\"),
                    original.replace("/note.txt", "/../note.txt"))
        for name in variants:
            with self.subTest(name=name):
                RecordFile.objects.filter(pk=self.item.pk).update(file=name)
                with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
                    self.assert_unavailable()
                self.assertEqual(opened.call_count, 0)

    def test_redirected_record_directory_is_rejected(self):
        original = self.path.parent
        moved = original.with_name(original.name + "-moved")
        original.rename(moved)
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(original), str(moved)],
                               check=True, capture_output=True)
            else:
                original.symlink_to(moved, target_is_directory=True)
            self.assert_unavailable()
        finally:
            if os.name == "nt":
                original.rmdir()
            else:
                original.unlink()
            moved.rename(original)

    def test_integrity_failure_closes_the_open_source(self):
        opened = []
        original = self.storage.open
        def observe(*args, **kwargs):
            source = original(*args, **kwargs)
            opened.append(source)
            return source
        self.path.write_bytes(b"corrupt")
        with patch.object(self.storage, "open", side_effect=observe):
            self.assert_unavailable()
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_read_failure_closes_the_open_source(self):
        opened = []
        original = self.storage.open
        def observe(*args, **kwargs):
            source = original(*args, **kwargs)
            opened.append(source)
            return source
        with patch.object(self.storage, "open", side_effect=observe), \
                patch("django.db.models.fields.files.FieldFile.chunks", side_effect=OSError("synthetic read failure")):
            self.assert_unavailable()
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_storage_without_a_qualified_filesystem_root_fails_closed(self):
        with patch.object(RecordFile._meta.get_field("file"), "storage", Storage()):
            self.assert_unavailable()

    def test_audit_failure_closes_the_verified_source(self):
        opened = []
        original = self.storage.open
        def observe(*args, **kwargs):
            source = original(*args, **kwargs)
            opened.append(source)
            return source
        with patch.object(self.storage, "open", side_effect=observe):
            with patch.object(RecordEvent.objects, "create", side_effect=RuntimeError("synthetic audit failure")):
                with self.assertRaisesMessage(RuntimeError, "synthetic audit failure"):
                    self.client.get(self.url)
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_existing_download_and_confidentiality_boundaries_precede_file_open(self):
        for actor, expected in ((None, 302), (self.reader, 403), (self.outsider, 404)):
            with self.subTest(actor=actor):
                self.client.logout()
                if actor:
                    self.client.force_login(actor)
                with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
                    self.assertEqual(self.client.get(self.url).status_code, expected)
                self.assertEqual(opened.call_count, 0)
        self.client.force_login(self.clerk)
        DepartmentRecord.objects.filter(pk=self.record.pk).update(confidentiality="restricted")
        self.assert_unavailable()
        grant = Permission.objects.get(content_type__app_label="records", codename="view_restricted_records")
        self.clerk.user_permissions.add(grant)
        self.client.force_login(get_user_model().objects.get(pk=self.clerk.pk))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.close_response(response)

    def test_current_office_and_disposition_and_active_file_are_rechecked(self):
        self.clerk.employeeprofile.assigned_department = self.other
        self.clerk.employeeprofile.save(update_fields=("assigned_department",))
        self.assert_unavailable()
        self.clerk.employeeprofile.assigned_department = self.office
        self.clerk.employeeprofile.save(update_fields=("assigned_department",))
        DepartmentRecord.objects.filter(pk=self.record.pk).update(status="disposed")
        with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(opened.call_count, 0)
        DepartmentRecord.objects.filter(pk=self.record.pk).update(status="draft")
        RecordFile.objects.filter(pk=self.item.pk).update(is_active=False)
        self.assert_unavailable()

    def test_department_slug_rename_preserves_the_original_file_namespace(self):
        self.office.slug = "renamed-records-office"
        self.office.save(update_fields=("slug",))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.payload)
        self.close_response(response)

    def test_retained_empty_file_is_distinct_from_a_missing_baseline(self):
        self.path.write_bytes(b"")
        RecordFile.objects.filter(pk=self.item.pk).update(size_bytes=0, checksum=hashlib.sha256(b"").hexdigest())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"")
        self.close_response(response)
