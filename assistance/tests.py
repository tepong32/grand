import tempfile
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone
from PIL import Image

from assistance.models import RequestLog
from departments.models import Department
from profiles.models import EmployeeProfile

from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from assistance.models import AssistanceRequest, AssistanceType, RequestDocument
from assistance.services import AssistanceRequestService, DocumentService, DocumentServiceError
from assistance.forms import get_valid_school_years


def _default_school_year():
    return get_valid_school_years()[0][0]


def _fake_upload_file(name="doc.pdf", content=b"pdf"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class AssistanceFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.assistance_type = AssistanceType.objects.create(
            name="General Assistance",
            description="desc",
            requirements="req",
            is_active=True,
        )

    def setUp(self):
        caches["default"].clear()

    def _build_submit_payload(self, *, suffix="1", email=None):
        return {
            "assistance_type": self.assistance_type.id,
            "period": _default_school_year(),
            "semester": "1st",
            "full_name": f"Test Person {suffix}",
            "email": email or f"person{suffix}@example.com",
            "phone": "09123456789",
        }

    def test_submit_lookup_and_resend_flow(self):
        response = self.client.post(
            reverse("assistance:submit_request"),
            data=self._build_submit_payload(suffix="submit"),
            follow=False,
        )
        self.assertIn(response.status_code, [200, 302])

        request_obj = (
            AssistanceRequest.objects.filter(reference_code__isnull=False, email="personsubmit@example.com")
            .order_by("-submitted_at")
            .first()
        )
        self.assertIsNotNone(request_obj, "Submission did not create an assistance request.")
        self.assertTrue(request_obj.reference_code)
        self.assertTrue(request_obj.edit_code)
        self.assertEqual(request_obj.assistance_type_id, self.assistance_type.id)

        response = self.client.get(reverse("assistance:track_request", args=[request_obj.reference_code]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("assistance:edit_request", args=[request_obj.secure_edit_token]))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("assistance:assistance_landing"),
            data={
                "form_type": "resend_codes",
                "email": request_obj.email,
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 200)

    def test_validate_codes_endpoint(self):
        request_obj = AssistanceRequestService.submit_request(
            assistance_type=self.assistance_type,
            period=_default_school_year(),
            semester="1st",
            full_name="Validation User",
            email="validate@example.com",
            phone="09998887777",
        )

        response = self.client.post(
            reverse("assistance:validate_codes"),
            data={
                "reference_code": request_obj.reference_code,
                "access_token": request_obj.secure_edit_token,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("reference_valid"), True)
        self.assertEqual(response.json().get("edit_valid"), False)

        response = self.client.post(
            reverse("assistance:validate_codes"),
            data={
                "reference_code": "BAD-CODE",
                "edit_code": "XXXXXX",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 404)

    def test_document_upload_replace_and_locked_rejection(self):
        request_obj = AssistanceRequestService.submit_request(
            assistance_type=self.assistance_type,
            period=_default_school_year(),
            semester="1st",
            full_name="Replace User",
            email="replace@example.com",
            phone="09112223333",
        )

        first_doc = DocumentService.upload_or_replace(
            request_obj=request_obj,
            document_type="birth_cert",
            uploaded_file=_fake_upload_file("first.pdf", b"first"),
        )
        first_doc.status = "wrong_file"
        first_doc.save(update_fields=["status"])

        replacement = DocumentService.upload_or_replace(
            request_obj=request_obj,
            document_type="birth_cert",
            uploaded_file=_fake_upload_file("second.pdf", b"second"),
        )
        self.assertEqual(replacement.id, first_doc.id)
        self.assertEqual(replacement.replacement_count, 1)

        request_obj.status = "approved"
        request_obj.save(update_fields=["status"])
        with self.assertRaises(DocumentServiceError):
            DocumentService.upload_or_replace(
                request_obj=request_obj,
                document_type="indigency",
                uploaded_file=_fake_upload_file("blocked.pdf", b"blocked"),
            )

    def test_document_delete_semantics(self):
        request_obj = AssistanceRequestService.submit_request(
            assistance_type=self.assistance_type,
            period=_default_school_year(),
            semester="1st",
            full_name="Delete User",
            email="delete@example.com",
            phone="09991112222",
        )

        document = DocumentService.upload_or_replace(
            request_obj=request_obj,
            document_type="grade_card",
            uploaded_file=_fake_upload_file("delete.pdf", b"delete"),
        )
        response = self.client.post(
            reverse("assistance:delete_document"),
            data={
                "doc_id": document.id,
                "access_token": request_obj.secure_edit_token,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "success")
        self.assertEqual(response.json().get("message"), "Document deleted.")

        document.refresh_from_db()
        self.assertTrue(document.is_removed)

        response = self.client.post(
            reverse("assistance:delete_document"),
            data={
                "doc_id": document.id,
                "access_token": request_obj.secure_edit_token,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)


    def prepare_private_access(self):
        self.kind = AssistanceType.objects.create(name="Private-link synthetic program", requirements="Synthetic only")
        self.mswd, _ = Department.objects.get_or_create(slug="mswd", defaults={"name": "MSWD"})
        self.other, _ = Department.objects.get_or_create(slug="private-link-other", defaults={"name": "Other office"})
        self.staff = get_user_model().objects.create_user(username="private-link-staff", email="private-staff@example.test")
        self.outsider = get_user_model().objects.create_user(username="private-link-outsider", email="private-other@example.test")
        for user, department in ((self.staff, self.mswd), (self.outsider, self.other)):
            EmployeeProfile.objects.update_or_create(user=user, defaults={"assigned_department": department})
        cache.clear()
        runtime = tempfile.TemporaryDirectory(prefix="grand-private-access-")
        self.addCleanup(runtime.cleanup)
        config = override_settings(MEDIA_ROOT=runtime.name, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
        config.enable()
        self.addCleanup(config.disable)
        self.req = AssistanceRequest.objects.create(
            reference_code="PRIVATE-ONE", assistance_type=self.kind, full_name="PRIVATE PERSON SENTINEL",
            email="registered@example.test", phone="09123456789", edit_code="314159")
        self.other_req = AssistanceRequest.objects.create(
            reference_code="PRIVATE-TWO", assistance_type=self.kind, full_name="OTHER PERSON SENTINEL",
            email="other-person@example.test", phone="09123456780", edit_code="314159")
        self.doc = RequestDocument.objects.create(request=self.req, document_type="birth_cert",
            file=SimpleUploadedFile("confidential.txt", b"synthetic current attachment", content_type="text/plain"))
        self.token = self.req.secure_edit_token

    def edit_url(self, token=None):
        return reverse("assistance:edit_request", args=[token or self.token])

    def file_url(self, token=None, doc=None):
        return reverse("assistance:citizen_document", args=[token or self.token, (doc or self.doc).pk])

    def finish(self, response):
        # Exhaust Django's closing iterator rather than sending request_finished
        # a second time with close(); native TestCase transactions must survive.
        if response.streaming and not response.closed:
            for _ in response.streaming_content:
                pass

    def test_legacy_code_never_opens_private_case_even_when_codes_collide(self):
        self.prepare_private_access()
        self.assertEqual(self.client.get(self.edit_url(self.req.edit_code)).status_code, 404)
        response = self.client.get(self.edit_url())
        self.assertContains(response, self.req.full_name)
        self.assertNotContains(response, self.other_req.full_name)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["Referrer-Policy"], "same-origin")

    def test_public_tracker_reveals_no_documents_contacts_or_free_text(self):
        self.prepare_private_access()
        RequestLog.objects.create(request=self.req, remarks="PRIVATE STAFF NOTE SENTINEL")
        response = self.client.get(self.req.get_track_url())
        self.assertContains(response, "Submitted")
        for secret in (self.req.full_name, self.req.email, self.req.phone, self.doc.file.name,
                       "confidential.txt", "PRIVATE STAFF NOTE SENTINEL", self.token, self.doc.file.url):
            self.assertNotContains(response, secret)

    def test_forged_wrong_purpose_and_malformed_links_fail_closed(self):
        self.prepare_private_access()
        for token in (self.token + "x", "314159", signing.dumps({"id": self.req.pk}), "x" * 513):
            with self.subTest(token=token[:10]):
                response = self.client.get(self.edit_url(token))
                self.assertEqual(response.status_code, 404)
                self.assertContains(response, "new private link", status_code=404)
                self.assertNotContains(response, self.req.email, status_code=404)

    def test_seven_day_expiry_applies_to_edit_qr_confirmation_file_and_mutation(self):
        self.prepare_private_access()
        with patch("django.core.signing.time.time", return_value=time.time() + 7 * 86400 + 2):
            urls = [self.edit_url(), self.file_url(),
                    reverse("assistance:confirmation_view", args=[self.req.reference_code, self.token]),
                    reverse("assistance:generate_qr", args=[self.req.reference_code, self.token])]
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 404)
            response = self.client.post(reverse("assistance:delete_document"),
                {"doc_id": self.doc.pk, "access_token": self.token}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 404)
        self.assertTrue(response.json()["access_unavailable"])
        self.assertIn("new private link", response.json()["message"])
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_removed)

    @override_settings(ASSISTANCE_PRIVATE_LINK_SECONDS=30)
    def test_lifetime_is_configurable_and_reads_do_not_renew_it(self):
        self.prepare_private_access()
        with patch("django.core.signing.time.time", return_value=time.time() + 20):
            self.assertEqual(self.client.get(self.edit_url()).status_code, 200)
        with patch("django.core.signing.time.time", return_value=time.time() + 32):
            self.assertEqual(self.client.get(self.edit_url()).status_code, 404)

    def test_inactive_and_changed_credential_state_revoke_links(self):
        self.prepare_private_access()
        for fields in ({"is_active": False}, {"edit_code": "271828"}, {"email": "changed@example.test"}):
            AssistanceRequest.objects.filter(pk=self.req.pk).update(**fields)
            self.assertEqual(self.client.get(self.edit_url()).status_code, 404)
            self.assertEqual(self.client.get(self.file_url()).status_code, 404)
            AssistanceRequest.objects.filter(pk=self.req.pk).update(is_active=True, edit_code="314159", email=self.req.email)

    def test_request_scoped_files_and_reference_bound_confirmation_qr(self):
        self.prepare_private_access()
        other_token = self.other_req.secure_edit_token
        self.assertEqual(self.client.get(self.file_url(other_token)).status_code, 404)
        for name in ("confirmation_view", "generate_qr"):
            self.assertEqual(self.client.get(reverse("assistance:" + name,
                args=[self.other_req.reference_code, self.token])).status_code, 404)
            self.assertEqual(self.client.get(reverse("assistance:" + name,
                args=[self.req.reference_code, self.req.edit_code])).status_code, 404)

    def test_current_attachment_stream_headers_and_removed_missing_paths(self):
        self.prepare_private_access()
        response = self.client.get(self.file_url())
        self.assertEqual(b"".join(response.streaming_content), b"synthetic current attachment")
        self.assertEqual(response["X-GRAND-File-Integrity"], "not-recorded")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.finish(response)
        Path(self.doc.file.path).unlink()
        self.assertEqual(self.client.get(self.file_url()).status_code, 404)
        RequestDocument.objects.filter(pk=self.doc.pk).update(is_removed=True)
        self.assertEqual(self.client.get(self.file_url()).status_code, 404)

    def test_document_paths_cannot_escape_namespace_or_follow_redirected_directory(self):
        self.prepare_private_access()
        for name in ("../outside.txt", "defaults/public.txt", "assistance_docs/../outside.txt", "assistance_docs\\file.txt"):
            RequestDocument.objects.filter(pk=self.doc.pk).update(file=name)
            self.assertEqual(self.client.get(self.file_url()).status_code, 404)
        # Portable mock of a redirected directory: the resolved target differs.
        RequestDocument.objects.filter(pk=self.doc.pk).update(file=self.doc.file.name)
        original = Path.resolve
        def redirected(path, *args, **kwargs):
            if path.name == "confidential.txt":
                return original(path, *args, **kwargs).parent.parent / "outside.txt"
            return original(path, *args, **kwargs)
        with patch("pathlib.Path.resolve", redirected):
            self.assertEqual(self.client.get(self.file_url()).status_code, 404)

    def test_real_redirected_attachment_directory_is_rejected(self):
        self.prepare_private_access()
        root = Path(self.doc.file.storage.location)
        target = root / "outside"
        target.mkdir()
        (target / "redirected.txt").write_bytes(b"not an authorized attachment")
        (root / "assistance_docs/link").symlink_to(target, target_is_directory=True)
        RequestDocument.objects.filter(pk=self.doc.pk).update(file="assistance_docs/link/redirected.txt")
        response = self.client.get(self.file_url())
        status = response.status_code
        self.finish(response)
        self.assertEqual(status, 404)

    def test_verified_image_preview_and_active_upload_forced_download(self):
        self.prepare_private_access()
        image = BytesIO()
        Image.new("RGB", (2, 2), "blue").save(image, format="PNG")
        self.doc.file.save("preview.png", SimpleUploadedFile("preview.png", image.getvalue()))
        response = self.client.get(self.file_url())
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.finish(response)
        with patch("PIL.Image.MAX_IMAGE_PIXELS", 1):
            response = self.client.get(self.file_url())
            self.assertEqual(response["Content-Type"], "application/octet-stream")
            self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
            self.finish(response)
        self.doc.file.save("unsafe.svg", SimpleUploadedFile("unsafe.svg", b"<svg onload='alert(1)'/>"))
        response = self.client.get(self.file_url())
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.finish(response)

    def test_staff_download_requires_existing_mswd_scope_and_current_case(self):
        self.prepare_private_access()
        url = reverse("assistance:mswd_document_download", args=[self.doc.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertEqual(b"".join(response.streaming_content), b"synthetic current attachment")
        self.finish(response)
        self.assertEqual(self.client.post(url).status_code, 405)
        AssistanceRequest.objects.filter(pk=self.req.pk).update(is_active=False)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_approved_and_claimed_cases_allow_read_but_not_edits_upload_or_removal(self):
        self.prepare_private_access()
        for fields in ({"status": "approved"}, {"status": "submitted", "claimed_at": timezone.now()}):
            AssistanceRequest.objects.filter(pk=self.req.pk).update(**fields)
            self.assertContains(self.client.get(self.edit_url()), "can no longer be edited")
            self.client.post(self.edit_url(), {"full_name": "FORBIDDEN CHANGE"})
            response = self.client.get(self.file_url())
            self.assertEqual(response.status_code, 200)
            self.finish(response)
            self.assertEqual(self.client.post(reverse("assistance:delete_document"),
                {"doc_id": self.doc.pk, "access_token": self.token}, HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 400)
            self.assertEqual(self.client.post(reverse("assistance:upload_document_ajax", args=[self.token]),
                {"document_type": "indigency", "file": SimpleUploadedFile("blocked.txt", b"x")},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 400)
        self.req.refresh_from_db()
        self.doc.refresh_from_db()
        self.assertEqual(self.req.full_name, "PRIVATE PERSON SENTINEL")
        self.assertFalse(self.doc.is_removed)

    def test_upload_and_remove_require_strong_scope_not_legacy_pin(self):
        self.prepare_private_access()
        upload = reverse("assistance:upload_document_ajax", args=[self.req.edit_code])
        self.assertEqual(self.client.post(upload, {"document_type": "indigency", "file": SimpleUploadedFile("new.txt", b"x")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 404)
        for data in ({"edit_code": self.req.edit_code}, {"access_token": self.other_req.secure_edit_token}):
            response = self.client.post(reverse("assistance:delete_document"), {"doc_id": self.doc.pk, **data},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertIn(response.status_code, (400, 404))
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_removed)

    def test_authorized_edit_preserves_details_and_revokes_prior_email_link(self):
        self.prepare_private_access()
        response = self.client.post(self.edit_url(), {
            "full_name": "Updated synthetic person", "email": "updated@example.test", "phone": "09123456789"})
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.full_name, "Updated synthetic person")
        self.assertEqual(self.req.edit_code, "314159")
        self.assertEqual(self.client.get(self.edit_url()).status_code, 404)
        self.assertEqual(response.url, reverse("assistance:assistance_landing"))
        self.assertNotIn("Updated synthetic person", self.client.get(response.url).content.decode())

    def test_ordinary_edit_keeps_original_token_and_expiry(self):
        self.prepare_private_access()
        response = self.client.post(self.edit_url(), {
            "full_name": "Updated synthetic person", "email": self.req.email, "phone": self.req.phone})
        self.assertEqual(response.url, self.edit_url())
        self.assertContains(self.client.get(response.url), "Updated synthetic person")
        with patch("django.core.signing.time.time", return_value=time.time() + 7 * 86400 + 2):
            self.assertEqual(self.client.get(response.url).status_code, 404)

    def test_valid_token_upload_replace_and_remove_keep_current_document_history(self):
        self.prepare_private_access()
        url = reverse("assistance:upload_document_ajax", args=[self.token])
        RequestDocument.objects.filter(pk=self.doc.pk).update(status="clearer_copy")
        response = self.client.post(url, {"document_type": "birth_cert",
            "file": SimpleUploadedFile("replacement.txt", b"replacement", content_type="text/plain")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.replacement_count, 1)
        self.assertEqual(self.req.timeline.filter(event_type="document_replaced").count(), 1)
        response = self.client.post(reverse("assistance:delete_document"),
            {"doc_id": self.doc.pk, "access_token": self.token}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.req.timeline.filter(event_type="document_removed").count(), 1)
        self.assertEqual(self.client.get(self.file_url()).status_code, 404)

    def test_csrf_and_method_requirements_remain(self):
        self.prepare_private_access()
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.edit_url(), {"full_name": "blocked"}).status_code, 403)
        self.assertEqual(client.post(reverse("assistance:delete_document"),
            {"doc_id": self.doc.pk, "access_token": self.token}, HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 403)
        self.assertEqual(self.client.get(reverse("assistance:resend_codes")).status_code, 405)
        self.assertEqual(self.client.get(reverse("assistance:upload_document_ajax", args=[self.token])).status_code, 405)

    def test_email_renewal_is_generic_and_uses_only_registered_recipient(self):
        self.prepare_private_access()
        bodies = []
        for address in ("absent@example.test", "registered@éxample.test", self.req.email):
            response = self.client.post(reverse("assistance:resend_codes"),
                {"email": address, "to_email": "attacker@example.test"}, follow=True)
            bodies.append([str(message) for message in response.context["messages"]])
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[1], bodies[2])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.req.email])
        self.assertNotIn(self.req.edit_code, mail.outbox[0].body)
        self.assertIn("/assistance/edit/", mail.outbox[0].body)
        self.assertNotIn("attacker@example.test", mail.outbox[0].body)

    def test_recovery_limit_covers_legacy_landing_and_endpoint_together(self):
        self.prepare_private_access()
        for index in range(3):
            cache.clear()  # Clearing process-local state cannot reset the DB cap.
            url = reverse("assistance:assistance_landing" if index % 2 else "assistance:resend_codes")
            response = self.client.post(url, {"form_type": "resend_codes", "email": self.req.email})
            self.assertIn(response.status_code, (200, 302))
        response = self.client.post(reverse("assistance:resend_codes"), {"email": self.req.email.upper()})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "3600")
        self.assertEqual(len(mail.outbox), 3)
        from django.db import DatabaseError
        with patch("assistance.views.public.consume_attempt", side_effect=DatabaseError("synthetic outage")):
            response = self.client.post(reverse("assistance:resend_codes"), {"email": "absent@example.test"})
            self.assertEqual(response.status_code, 503)
        self.assertEqual(len(mail.outbox), 3)

    def test_legacy_validation_and_landing_never_mint_private_access(self):
        self.prepare_private_access()
        response = self.client.post(reverse("assistance:validate_codes"),
            {"reference_code": self.req.reference_code, "edit_code": self.req.edit_code})
        self.assertFalse(response.json()["edit_valid"])
        response = self.client.post(reverse("assistance:assistance_landing"),
            {"form_type": "track_edit", "reference_code": self.req.reference_code, "edit_code": self.req.edit_code})
        self.assertEqual(response.url, self.req.get_track_url())

    def test_bot_linking_rejects_pin_expiry_inactive_and_wrong_request(self):
        self.prepare_private_access()
        from telegram_bot.services.message_service import find_request_by_reference
        self.assertIsNone(find_request_by_reference(self.req.reference_code, self.req.edit_code))
        self.assertEqual(find_request_by_reference(self.req.reference_code, self.token).pk, self.req.pk)
        self.assertIsNone(find_request_by_reference(self.other_req.reference_code, self.token))
        with patch("django.core.signing.time.time", return_value=time.time() + 7 * 86400 + 2):
            self.assertIsNone(find_request_by_reference(self.req.reference_code, self.token))
        AssistanceRequest.objects.filter(pk=self.req.pk).update(is_active=False)
        self.assertIsNone(find_request_by_reference(self.req.reference_code, self.token))

    @override_settings(DEBUG=True)
    def test_raw_media_denied_for_reviewed_namespaces_public_images_remain(self):
        # static() is evaluated at URLconf import time, while Django's test
        # runner starts with DEBUG=False. Rebuild the actual reviewed URLconf
        # under DEBUG=True, isolated from every other test's cached routes.
        self.prepare_private_access()
        import importlib
        from types import ModuleType
        import src.urls
        previous = src.urls.urlpatterns
        try:
            routes = list(importlib.reload(src.urls).urlpatterns)
        finally:
            src.urls.urlpatterns = previous
        urlconf = ModuleType("synthetic_debug_media_urls")
        urlconf.urlpatterns = routes
        config = override_settings(ROOT_URLCONF=urlconf)
        config.enable()
        self.addCleanup(config.disable)
        root = Path(self.doc.file.storage.location)
        for name in ("records/test.txt", "reporting/outputs/test.txt", "vouchers/test.txt", "assistance_docs/test.txt"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"private synthetic bytes")
            response = self.client.get("/media/" + name)
            status = response.status_code
            self.finish(response)
            self.assertEqual(status, 404)
            response = self.client.get("/media/" + name.upper())
            status = response.status_code
            self.finish(response)
            self.assertEqual(status, 404)
        public = root / "defaults/test.txt"
        public.parent.mkdir(exist_ok=True)
        public.write_bytes(b"public synthetic asset")
        response = self.client.get("/media/defaults/test.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"public synthetic asset")
        self.finish(response)
        for path in ("defaults/../assistance_docs/test.txt", "defaults/%2e%2e/assistance_docs/test.txt",
                     "assistance_docs%5ctest.txt", "./assistance_docs/test.txt", "reporting//outputs/test.txt"):
            self.assertEqual(self.client.get("/media/" + path).status_code, 404)
        (root / "defaults/redirected").symlink_to(root / "assistance_docs", target_is_directory=True)
        response = self.client.get("/media/defaults/redirected/test.txt")
        status = response.status_code
        self.finish(response)
        self.assertEqual(status, 404)

    def test_pdf_preview_keeps_same_origin_frames_and_uses_the_opened_bytes(self):
        self.prepare_private_access()
        payload = b"%PDF-1.4\nsynthetic header test only"
        self.doc.file.save("preview.pdf", SimpleUploadedFile("preview.pdf", payload))
        response = self.client.get(self.file_url())
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertEqual(b"".join(response.streaming_content), payload)

class AssistanceRateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.assistance_type = AssistanceType.objects.create(
            name="Rate Limit Program",
            description="desc",
            requirements="req",
            is_active=True,
        )
        cls.request_obj = AssistanceRequestService.submit_request(
            assistance_type=cls.assistance_type,
            period=_default_school_year(),
            semester="1st",
            full_name="Rate User",
            email="rate@example.com",
            phone="09110000000",
        )

        # Prepare an uploadable document to keep upload endpoint replacements allowed.
        cls.seed_doc = RequestDocument.objects.create(
            request=cls.request_obj,
            document_type="birth_cert",
            file=_fake_upload_file("seed.pdf", b"seed"),
            status="clearer_copy",
        )

    def setUp(self):
        caches["default"].clear()

    def test_submit_rate_limit_blocks_abuse(self):
        submit_url = reverse("assistance:submit_request")
        for index in range(5):
            response = self.client.post(
                submit_url,
                data=self._build_submit_payload(index=index),
            )
            self.assertEqual(response.status_code, 302)

        blocked = self.client.post(
            submit_url,
            data=self._build_submit_payload(index=6),
        )
        self.assertIn(blocked.status_code, [403, 429])

    def test_validate_rate_limit_blocks_abuse(self):
        validate_url = reverse("assistance:validate_codes")
        for _ in range(10):
            response = self.client.post(
                validate_url,
                data={
                    "reference_code": self.request_obj.reference_code,
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            validate_url,
            data={"reference_code": self.request_obj.reference_code},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIn(blocked.status_code, [403, 429])

    def test_upload_rate_limit_blocks_abuse(self):
        upload_url = reverse("assistance:upload_document_ajax", args=[self.request_obj.secure_edit_token])
        for index in range(12):
            response = self.client.post(
                upload_url,
                {
                    "document_type": "birth_cert",
                    "file": _fake_upload_file(f"doc{index}.pdf", b"file"),
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 200)
            RequestDocument.objects.filter(request=self.request_obj, document_type="birth_cert").update(
                status="clearer_copy"
            )

        blocked = self.client.post(
            upload_url,
            {
                "document_type": "birth_cert",
                "file": _fake_upload_file("blocked.pdf", b"file"),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIn(blocked.status_code, [403, 429])

    def test_delete_rate_limit_blocks_abuse(self):
        doc_id = self.seed_doc.id
        delete_url = reverse("assistance:delete_document")
        for _ in range(12):
            response = self.client.post(
                delete_url,
                {
                    "doc_id": doc_id,
                    "access_token": self.request_obj.secure_edit_token,
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertIn(response.status_code, [200, 400])

        blocked = self.client.post(
            delete_url,
            {
                "doc_id": doc_id,
                "access_token": self.request_obj.secure_edit_token,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIn(blocked.status_code, [403, 429])

    @staticmethod
    def _build_submit_payload(index=0):
        return {
            "assistance_type": AssistanceRateLimitTests.assistance_type.id,
            "period": get_valid_school_years()[0][0],
            "semester": "1st",
            "full_name": f"Spam User {index}",
            "email": f"spam{index}@example.com",
            "phone": "09990000000",
        }
