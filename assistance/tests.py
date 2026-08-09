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

        response = self.client.get(reverse("assistance:edit_request", args=[request_obj.edit_code]))
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
                "edit_code": request_obj.edit_code,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("reference_valid"), True)
        self.assertEqual(response.json().get("edit_valid"), True)

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
                "edit_code": request_obj.edit_code,
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
                "edit_code": request_obj.edit_code,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)


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
        upload_url = reverse("assistance:upload_document_ajax", args=[self.request_obj.edit_code])
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
                    "edit_code": self.request_obj.edit_code,
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertIn(response.status_code, [200, 400])

        blocked = self.client.post(
            delete_url,
            {
                "doc_id": doc_id,
                "edit_code": self.request_obj.edit_code,
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
