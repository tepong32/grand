"""Citizen writes must use current authority without restoring workflow state."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceRequest, AssistanceType, RequestDocument, RequestTimeline
from assistance.services import DocumentService, DocumentServiceError
from assistance.services.access_service import locked_request_for_mutation


class CitizenMutationFixture:
    def setUp(self):
        super().setUp()
        runtime = tempfile.TemporaryDirectory(prefix="citizen-mutation-")
        self.addCleanup(runtime.cleanup)
        settings = override_settings(MEDIA_ROOT=runtime.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.media = Path(runtime.name)
        self.kind = AssistanceType.objects.create(name="Synthetic mutation program")
        self.req = AssistanceRequest.objects.create(
            reference_code="MUTATION-ONE", assistance_type=self.kind,
            full_name="Original Citizen", email="original@example.test",
            phone="09123456789", edit_code="123456")
        self.token = self.req.secure_edit_token
        self.url = reverse("assistance:edit_request", args=[self.token])
        self.payload = {"full_name": "Updated Citizen", "email": self.req.email,
                        "phone": "09987654321"}
        self.doc = RequestDocument.objects.create(
            request=self.req, document_type="birth_cert", status="wrong_file",
            file=SimpleUploadedFile("original.txt", b"original synthetic evidence"))

    def assert_original_contact(self):
        self.req.refresh_from_db()
        self.assertEqual(self.req.full_name, "Original Citizen")
        self.assertEqual(self.req.phone, "09123456789")

    def media_snapshot(self):
        return {p.relative_to(self.media).as_posix(): p.read_bytes()
                for p in self.media.rglob("*") if p.is_file()}


class CitizenMutationTests(CitizenMutationFixture, TestCase):
    def test_allowed_edit_changes_only_contact_fields(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.full_name, self.payload["full_name"])
        self.assertEqual(self.req.phone, self.payload["phone"])
        self.assertEqual(self.req.status, "submitted")
        self.assertTrue(self.req.is_active)
        self.assertIsNone(self.req.claimed_at)
        self.assertIsNone(self.req.citizen_id)
        self.assertIsNone(self.req.telegram_chat_id)
        self.assertEqual(self.req.edit_code, "123456")
        self.assertEqual(self.req.assistance_type_id, self.kind.pk)

    def test_workflow_ownership_and_unknown_fields_reject_the_entire_edit(self):
        for name, value in {"status": "approved", "claimed_at": "2026-01-01",
                "is_active": "False", "edit_code": "000000", "citizen": "123",
                "citizen_id": "123", "assistance_type": "999", "telegram_chat_id": "123",
                "approved_at": "2026-01-01", "remarks": "staff decision", "is_staff": "True"}.items():
            with self.subTest(field=name):
                before = AssistanceRequest.objects.values().get(pk=self.req.pk)
                response = self.client.post(self.url, {**self.payload, name: value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(AssistanceRequest.objects.values().get(pk=self.req.pk), before)

    def test_denied_edit_preserves_approved_claimed_and_revoked_states(self):
        claimed = timezone.now()
        for changes, expected in [({"status": "approved"}, 200),
                ({"status": "submitted", "claimed_at": claimed}, 200),
                ({"claimed_at": None, "is_active": False}, 404),
                ({"is_active": True, "edit_code": "654321"}, 404)]:
            with self.subTest(changes=changes):
                AssistanceRequest.objects.filter(pk=self.req.pk).update(**changes)
                response = self.client.post(self.url, self.payload)
                self.assertEqual(response.status_code, expected)
                self.assert_original_contact()
                for name, value in changes.items():
                    self.assertEqual(getattr(self.req, name), value)

    def test_missing_invalid_and_expired_tokens_do_not_mutate(self):
        from django.core import signing
        for token in ("invalid-token", self.token + "tampered"):
            with self.subTest(token=token):
                self.assertEqual(self.client.post(reverse("assistance:edit_request", args=[token]),
                                                 self.payload).status_code, 404)
        with patch("django.core.signing.TimestampSigner.unsign", side_effect=signing.SignatureExpired):
            self.assertEqual(self.client.post(self.url, self.payload).status_code, 404)
        self.assert_original_contact()
        AssistanceRequest.objects.filter(pk=self.req.pk).delete()
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 404)

    def test_invalid_form_and_database_contention_do_not_partially_write(self):
        self.assertEqual(self.client.post(self.url, {**self.payload, "email": "invalid"}).status_code, 200)
        self.assert_original_contact()
        with patch("assistance.views.public.locked_request_for_mutation",
                   side_effect=OperationalError("synthetic contention")):
            self.assertEqual(self.client.post(self.url, self.payload).status_code, 503)
        self.assert_original_contact()

    def test_unexpected_exception_rolls_back_request_mutation(self):
        with self.assertRaises(RuntimeError):
            with locked_request_for_mutation(token=self.token) as current:
                current.full_name = "Must roll back"
                current.save(update_fields=["full_name"])
                raise RuntimeError("synthetic interruption")
        self.assert_original_contact()

    def test_stale_document_services_recheck_workflow_before_storage_changes(self):
        before = self.media_snapshot()
        timeline = RequestTimeline.objects.count()
        AssistanceRequest.objects.filter(pk=self.req.pk).update(status="approved")
        with self.assertRaises(DocumentServiceError):
            DocumentService.upload_or_replace(request_obj=self.req, document_type="birth_cert",
                uploaded_file=SimpleUploadedFile("replacement.txt", b"must not persist"), access_token=self.token)
        with self.assertRaises(DocumentServiceError):
            DocumentService.soft_delete_document(request_obj=self.req, document_id=self.doc.pk,
                                                 access_token=self.token)
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_removed)
        self.assertEqual(self.doc.replacement_count, 0)
        self.assertEqual(RequestTimeline.objects.count(), timeline)
        self.assertEqual(self.media_snapshot(), before)

    def test_internal_document_caller_rejects_stale_credentials_and_inactivation(self):
        before = self.media_snapshot()
        for changes in ({"email": "changed@example.test"}, {"is_active": False}):
            AssistanceRequest.objects.filter(pk=self.req.pk).update(**changes)
            with self.assertRaises(Http404):
                DocumentService.soft_delete_document(request_obj=self.req, document_id=self.doc.pk)
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_removed)
        self.assertEqual(self.media_snapshot(), before)

    def test_allowed_document_replacement_and_deletion_preserve_request_scope(self):
        with self.captureOnCommitCallbacks(execute=True):
            replacement = DocumentService.upload_or_replace(request_obj=self.req,
                document_type="birth_cert", uploaded_file=SimpleUploadedFile("next.txt", b"next evidence"),
                access_token=self.token)
        self.assertEqual(replacement.pk, self.doc.pk)
        self.assertEqual(replacement.replacement_count, 1)
        other = AssistanceRequest.objects.create(reference_code="MUTATION-TWO", assistance_type=self.kind,
            full_name="Other", email="other@example.test", phone="09123456780")
        with self.assertRaises(Http404):
            DocumentService.soft_delete_document(request_obj=other, document_id=self.doc.pk,
                                                 access_token=self.token)
        DocumentService.soft_delete_document(request_obj=self.req, document_id=self.doc.pk,
                                             access_token=self.token)
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.is_removed)

    def test_revocation_between_http_lookup_and_document_service_is_rejected(self):
        from assistance.views.public import resolve_request_for_edit
        before = self.media_snapshot()

        def revoke_after_lookup(token):
            stale = resolve_request_for_edit(token)
            AssistanceRequest.objects.filter(pk=stale.pk).update(edit_code="654321")
            return stale

        with patch("assistance.views.public.resolve_request_for_edit", side_effect=revoke_after_lookup):
            response = self.client.post(reverse("assistance:delete_document"),
                {"doc_id": self.doc.pk, "access_token": self.token}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 404)
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_removed)
        self.assertEqual(self.media_snapshot(), before)
