"""Security boundaries exercised through real staff and document workflows."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.http import Http404
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from assistance.files import document_response
from assistance.models import RequestDocument, RequestTimeline
from assistance.services import DocumentService
from assistance.test_citizen_mutations import CitizenMutationFixture
from departments.models import Department
from profiles.files import memo_response
from profiles.models import EmployeeProfile
from telegram_bot.services.notification_service import send_telegram_update


class DocumentAtomicityTests(CitizenMutationFixture, TestCase):
    def test_late_timeline_failure_restores_rows_and_removes_only_new_uploads(self):
        before_files = self.media_snapshot()
        before_rows = list(RequestDocument.objects.values())
        before_events = RequestTimeline.objects.count()
        for kind in ("birth_cert", "indigency"):
            with self.subTest(kind=kind):
                with patch("assistance.services.document_service.RequestTimeline.objects.create",
                           side_effect=RuntimeError("synthetic timeline interruption")):
                    with self.assertRaises(RuntimeError):
                        DocumentService.upload_or_replace(request_obj=self.req, document_type=kind,
                            uploaded_file=SimpleUploadedFile("new.txt", b"must roll back"), access_token=self.token)
                self.assertEqual(list(RequestDocument.objects.values()), before_rows)
                self.assertEqual(RequestTimeline.objects.count(), before_events)
                self.assertEqual(self.media_snapshot(), before_files)

    def test_insert_failure_after_storage_save_does_not_leave_an_orphan(self):
        before = self.media_snapshot()

        def reject_insert(execute, sql, params, many, context):
            if sql.lstrip().upper().startswith("INSERT INTO") and "assistance_requestdocument" in sql:
                raise IntegrityError("synthetic insert failure")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(reject_insert), self.assertRaises(IntegrityError):
            DocumentService.upload_or_replace(request_obj=self.req, document_type="indigency",
                uploaded_file=SimpleUploadedFile("new.txt", b"must roll back"), access_token=self.token)
        self.assertEqual(RequestDocument.objects.count(), 1)
        self.assertEqual(self.media_snapshot(), before)

    def test_reupload_after_removal_reuses_identity_and_preserves_removal_event(self):
        DocumentService.soft_delete_document(request_obj=self.req, document_id=self.doc.pk, access_token=self.token)
        removal_count = RequestTimeline.objects.count()
        with self.captureOnCommitCallbacks(execute=True):
            current = DocumentService.upload_or_replace(request_obj=self.req, document_type="birth_cert",
                uploaded_file=SimpleUploadedFile("renewed.txt", b"renewed evidence"), access_token=self.token)
        self.assertEqual(current.pk, self.doc.pk)
        self.assertFalse(current.is_removed)
        self.assertIsNone(current.removed_at)
        self.assertEqual(current.status, "pending")
        self.assertEqual(current.replacement_count, 1)
        self.assertEqual(RequestDocument.objects.count(), 1)
        self.assertEqual(RequestTimeline.objects.count(), removal_count + 1)

    def test_postcommit_cleanup_failure_never_deletes_current_replacement(self):
        with patch("assistance.services.document_service.default_storage.delete",
                   side_effect=NotImplementedError("synthetic storage error")), \
                self.assertLogs("assistance.services.document_service", level="ERROR"), \
                self.captureOnCommitCallbacks(execute=True):
            current = DocumentService.upload_or_replace(request_obj=self.req, document_type="birth_cert",
                uploaded_file=SimpleUploadedFile("next.txt", b"current evidence"), access_token=self.token)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.file.name, current.file.name)
        with self.doc.file.open("rb") as stored:
            self.assertEqual(stored.read(), b"current evidence")


class UnqualifiedStorageTests(SimpleTestCase):
    def test_unqualified_attachment_and_memo_storage_fail_before_open(self):
        class NoFilesystemRoot:
            @property
            def location(self):
                raise NotImplementedError("unqualified backend")

        for name, response in [("assistance_docs/example.txt", document_response),
                               ("users/legacy/memos/example.png", memo_response)]:
            with self.subTest(name=name):
                field = SimpleNamespace(name=name, storage=NoFilesystemRoot(), open=Mock())
                target = SimpleNamespace(file=field) if response is document_response else field
                with self.assertRaises(Http404):
                    response(target)
                field.open.assert_not_called()


@override_settings(TELEGRAM_BOT_TOKEN="synthetic-only", TELEGRAM_NOTIFICATIONS_ENABLED=True,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationCoordinationTests(CitizenMutationFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.office, _ = Department.objects.get_or_create(slug="mswd", defaults={"name": "MSWD"})
        self.staff = get_user_model().objects.create_user(username="notification-reviewer", email="staff@example.test")
        EmployeeProfile.objects.update_or_create(user=self.staff, defaults={"assigned_department": self.office})
        self.client.force_login(self.staff)
        self.req.telegram_chat_id = "12345"
        self.req.save(update_fields=["telegram_chat_id"])

    def test_presence_binding_or_self_asserted_qualification_cannot_enable_delivery(self):
        from telegram_bot.services.message_service import link_chat_to_request
        link_chat_to_request(self.req, 12345, chat_type="private", access_token=self.token)
        self.req.telegram_qualified = True
        with patch("telegram.Bot") as bot:
            self.assertFalse(send_telegram_update(self.req, "synthetic status"))
            self.req.telegram_chat_id = "-10012345"
            self.assertFalse(send_telegram_update(self.req, "synthetic group status"))
            bot.assert_not_called()

    def test_staff_status_caller_saves_decision_and_email_without_transport(self):
        with patch("telegram.Bot") as bot:
            response = self.client.post(reverse("assistance:mswd_request_detail", args=[self.req.reference_code]),
                                        {"status": "review", "remarks": "Synthetic staff review"})
            bot.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "review")
        self.assertEqual(self.req.remarks, "Synthetic staff review")
        self.assertEqual(len(mail.outbox), 1)

    def test_staff_document_caller_saves_review_and_email_without_transport(self):
        with patch("telegram.Bot") as bot:
            response = self.client.post(reverse("assistance:mswd_update_document_ajax", args=[self.doc.pk]),
                                        {"status": "approved", "remarks": "Synthetic document review"})
            bot.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, "approved")
        self.assertEqual(self.doc.remarks, "Synthetic document review")
        self.assertEqual(len(mail.outbox), 1)
