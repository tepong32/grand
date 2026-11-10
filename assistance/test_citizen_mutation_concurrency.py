"""Observe real InnoDB waits; event coordination, never timing-only races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from assistance.models import AssistanceRequest, RequestTimeline
from assistance.services import DocumentService, DocumentServiceError
from assistance.test_citizen_mutations import CitizenMutationFixture


@skipUnless(connection.vendor == "mysql", "Citizen mutation races require native MySQL/InnoDB")
class CitizenMutationConcurrencyTests(CitizenMutationFixture, TransactionTestCase):
    def worker(self, operation, ready, identity):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                identity.append(cursor.fetchone()[0])
            ready.set()
            return operation()
        finally:
            connections.close_all()

    def wait_for_owner_lock(self, identity, future):
        deadline = monotonic() + 15
        tick = Event()
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT COUNT(*) FROM performance_schema.data_lock_waits w
                    JOIN performance_schema.threads t ON t.THREAD_ID = w.REQUESTING_THREAD_ID
                    WHERE t.PROCESSLIST_ID = %s""", [identity])
                if cursor.fetchone()[0]:
                    self.assertFalse(future.done())
                    return
            if future.done():
                self.fail("Competing mutation completed without waiting for the authoritative request")
            tick.wait(.01)  # Poll an observed database condition, not a guessed interleaving.
        self.fail("No native owning-row wait observed")

    def race_staff_first(self, changes, operation):
        ready, identity = Event(), []
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                count = AssistanceRequest.objects.filter(pk=self.req.pk).update(**changes)
                self.assertEqual(count, 1)
                future = pool.submit(self.worker, operation, ready, identity)
                self.assertTrue(ready.wait(15))
                self.wait_for_owner_lock(identity[0], future)
            outcome = future.result(timeout=15)
        self.req.refresh_from_db()
        for name, value in changes.items():
            self.assertEqual(getattr(self.req, name), value)
        return outcome

    def citizen_edit(self):
        return Client().post(self.url, self.payload).status_code

    def test_staff_approval_wins_without_citizen_restoring_old_status(self):
        self.assertEqual(self.race_staff_first({"status": "approved"}, self.citizen_edit), 200)
        self.assert_original_contact()

    def test_staff_claim_wins_without_citizen_clearing_claim(self):
        self.assertEqual(self.race_staff_first({"claimed_at": timezone.now()}, self.citizen_edit), 200)
        self.assert_original_contact()

    def test_deactivation_wins_and_citizen_is_denied(self):
        self.assertEqual(self.race_staff_first({"is_active": False}, self.citizen_edit), 404)
        self.assert_original_contact()

    def test_credential_rotation_wins_and_citizen_is_denied(self):
        self.assertEqual(self.race_staff_first({"edit_code": "654321"}, self.citizen_edit), 404)
        self.assert_original_contact()

    def test_email_change_wins_without_restoring_old_credential_state(self):
        self.assertEqual(self.race_staff_first({"email": "new@example.test"}, self.citizen_edit), 404)
        self.assert_original_contact()

    def document_operation(self, kind):
        try:
            if kind == "delete":
                DocumentService.soft_delete_document(request_obj=self.req, document_id=self.doc.pk,
                                                     access_token=self.token)
            else:
                DocumentService.upload_or_replace(request_obj=self.req,
                    document_type="birth_cert" if kind == "replace" else "indigency",
                    uploaded_file=SimpleUploadedFile("blocked.txt", b"must not persist"), access_token=self.token)
        except DocumentServiceError:
            return "denied"
        return "allowed"

    def check_document_race(self, kind):
        before = self.media_snapshot()
        timeline = RequestTimeline.objects.count()
        outcome = self.race_staff_first({"status": "approved"}, lambda: self.document_operation(kind))
        self.assertEqual(outcome, "denied")
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_removed)
        self.assertEqual(self.doc.replacement_count, 0)
        self.assertEqual(RequestTimeline.objects.count(), timeline)
        self.assertEqual(self.media_snapshot(), before)

    def test_stale_document_removal_waits_and_rechecks_approval(self):
        self.check_document_race("delete")

    def test_stale_document_replacement_waits_and_rechecks_approval(self):
        self.check_document_race("replace")

    def test_stale_document_upload_waits_and_rechecks_approval(self):
        self.check_document_race("upload")

    @override_settings(ASSISTANCE_PRIVATE_LINK_SECONDS=5)
    def test_token_expiring_during_lock_wait_is_rejected(self):
        from django.urls import reverse
        clock = [1000]
        with patch("django.core.signing.time", SimpleNamespace(time=lambda: clock[0])):
            self.token = self.req.secure_edit_token
            self.url = reverse("assistance:edit_request", args=[self.token])
            ready, identity = Event(), []
            with ThreadPoolExecutor(max_workers=1) as pool:
                with transaction.atomic():
                    self.assertEqual(AssistanceRequest.objects.filter(pk=self.req.pk).update(remarks="staff note"), 1)
                    future = pool.submit(self.worker, self.citizen_edit, ready, identity)
                    self.assertTrue(ready.wait(15))
                    self.wait_for_owner_lock(identity[0], future)
                    clock[0] = 1006
                self.assertEqual(future.result(timeout=15), 404)
        self.assert_original_contact()
        self.assertEqual(self.req.remarks, "staff note")

    def test_citizen_first_preserves_contact_then_allows_staff_approval(self):
        from assistance.forms import AssistanceRequestEditForm
        original_save = AssistanceRequestEditForm.save
        held, release = Event(), Event()

        def pause_after_save(form, *args, **kwargs):
            result = original_save(form, *args, **kwargs)
            held.set()
            if not release.wait(20):
                raise AssertionError("Citizen release signal missing")
            return result

        def approve():
            return AssistanceRequest.objects.filter(pk=self.req.pk).update(status="approved")

        with patch.object(AssistanceRequestEditForm, "save", pause_after_save):
            with ThreadPoolExecutor(max_workers=2) as pool:
                citizen = pool.submit(self.worker, self.citizen_edit, Event(), [])
                try:
                    self.assertTrue(held.wait(15))
                    ready, identity = Event(), []
                    staff = pool.submit(self.worker, approve, ready, identity)
                    self.assertTrue(ready.wait(15))
                    self.wait_for_owner_lock(identity[0], staff)
                finally:
                    release.set()
                self.assertEqual(citizen.result(timeout=15), 302)
                self.assertEqual(staff.result(timeout=15), 1)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "approved")
        self.assertEqual(self.req.full_name, self.payload["full_name"])
        self.assertEqual(self.req.phone, self.payload["phone"])
