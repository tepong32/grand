import hashlib
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from profiles.models import EmployeeProfile
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from inventory.models import ReceivingEvidence, ReceiptCostAmendment, ReceivingReceipt
from inventory.receipt_amendments import amendment_basis, record_amendment, decide_amendment
from inventory_finance.receipt_basis import receipt_basis_current
from inventory_finance.services import close_attribution
from . import test_grand_attribution


class GrandReceiptAmendmentTests(TestCase):
    databases = {"default", "finance"}
    propose = test_grand_attribution.AttributionTests.propose
    approve = test_grand_attribution.AttributionTests.approve

    @classmethod
    def setUpTestData(cls):
        test_grand_attribution.AttributionTests.setUpTestData.__func__(cls)
        cls.cost_reviewer = get_user_model().objects.create_user(username="cost-reviewer", email="cost@example.test")
        cls.cost_uat = get_user_model().objects.create_user(username="cost-uat", email="cost-uat@example.test")
        grants = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_receivingreceipt", "record_receiptcostamendment", "review_receiptcostamendment"))
        for actor in (cls.clerk, cls.cost_reviewer, cls.cost_uat):
            EmployeeProfile.objects.filter(user=actor).update(assigned_department=cls.gso)
            actor.refresh_from_db()
            actor.user_permissions.add(*grants)
        cls.cost_uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for model in (ReceivingEvidence, ReceiptCostAmendment):
            storage = patch.object(model._meta.get_field("file"), "storage", FileSystemStorage(location=directory.name))
            storage.start()
            self.addCleanup(storage.stop)
        content = b"%PDF-1.4\nSynthetic source\n%%EOF"
        for kind in ("delivery", "inspection"):
            ReceivingEvidence.objects.create(receipt=self.receipt, kind=kind,
                file=SimpleUploadedFile(kind+".pdf", content), original_filename=kind+".pdf",
                sha256=hashlib.sha256(content).hexdigest(), size=len(content), note="Synthetic accepted fixture",
                uploaded_by=self.clerk)
        self.receipt_line.refresh_from_db()

    def correction(self, cost="50.00", actor=None):
        self.receipt_line.refresh_from_db()
        return record_amendment(actor=actor or self.clerk, line=self.receipt_line, request_id=uuid4(),
            expected_basis=amendment_basis(self.receipt_line), unit_cost=cost,
            reference="Invoice correction", reason="Corrected documented cost",
            upload=SimpleUploadedFile("correction.pdf", b"%PDF-1.4\nCorrection\n%%EOF"))

    def decide(self, row):
        return decide_amendment(actor=self.cost_reviewer, amendment=row,
            expected_version=1, action="approve", note="Independent documentary check")

    def test_lower_correction_invalidates_prior_support_without_rewriting_finance(self):
        original = self.approve(self.propose())
        retained = original.receipt_snapshot
        with CaptureQueriesContext(connections["finance"]) as finance:
            amendment = self.decide(self.correction())
            original.refresh_from_db()
            self.assertFalse(receipt_basis_current(original))
            with self.assertRaises(ValidationError):
                self.propose(amount="51.00")
            replacement = self.propose(amount="40.00")
            with self.assertRaisesMessage(ValidationError, "stale or missing receipt basis"):
                self.approve(replacement)
            close_attribution(actor=self.reviewer, attribution_id=original.public_id,
                expected_version=original.state_version, action="withdraw", reason="Documentary correction reviewed")
            replacement = self.approve(replacement)
        self.assertEqual(len(finance), 0)
        self.assertEqual(original.receipt_snapshot, retained)
        self.assertEqual(replacement.receipt_snapshot["line"]["unit_cost"], "100.00")
        self.assertEqual(replacement.receipt_snapshot["documentary_amendment"]["unit_cost"], "50.00")
        self.assertEqual(replacement.receipt_snapshot["documentary_amendment"]["uuid"], str(amendment.public_id))
        self.receipt_line.refresh_from_db()
        self.assertEqual(self.receipt_line.unit_cost, Decimal("100.00"))

    def test_uat_cannot_correct_and_unknown_cost_cannot_support_claim(self):
        with self.assertRaises(PermissionDenied):
            self.correction(actor=self.cost_uat)
        row = self.correction(cost=None)
        with self.assertRaises(PermissionDenied):
            decide_amendment(actor=self.cost_uat, amendment=row, expected_version=1, action="approve", note="UAT attempt")
        self.decide(row)
        with self.assertRaisesMessage(ValidationError, "positive documented unit cost"):
            self.propose(amount="1.00")


from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction


@skipUnless(connection.vendor == "mysql", "Requires native MySQL locks and separate connections")
class ReceiptAmendmentConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        GrandReceiptAmendmentTests.setUpTestData.__func__(type(self))
        GrandReceiptAmendmentTests.setUp(self)

    propose = GrandReceiptAmendmentTests.propose
    correction = GrandReceiptAmendmentTests.correction
    decide = GrandReceiptAmendmentTests.decide

    def test_waiting_review_reloads_receipt_facts_after_amendment_commits(self):
        row = test_grand_attribution.AttributionTests.propose(self)
        amendment = self.correction()
        started, reader_connection = Event(), []

        def review():
            from inventory_finance.services import approve_attribution
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.reviewer.pk)
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = 8")
                    cursor.execute("SELECT CONNECTION_ID()")
                    reader_connection.append(cursor.fetchone()[0])
                started.set()
                try:
                    approve_attribution(actor=actor, attribution_id=row.public_id,
                        expected_version=1, note="Concurrent receipt review")
                except ValidationError as error:
                    return str(error)
                return "unexpectedly approved stale receipt facts"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            # Real amendment commits while an independent claim reviewer waits.
            with transaction.atomic(using="default"):
                ReceivingReceipt.objects.select_for_update().get(pk=self.receipt.pk)
                self.decide(amendment)
                future = executor.submit(review)
                self.assertTrue(started.wait(3))
                deadline, blocked = monotonic()+3, False
                while monotonic() < deadline:
                    with connections["default"].cursor() as cursor:
                        cursor.execute("""SELECT 1 FROM performance_schema.data_lock_waits w
                            JOIN performance_schema.threads t ON t.THREAD_ID=w.REQUESTING_THREAD_ID
                            WHERE t.PROCESSLIST_ID=%s""", [reader_connection[0]])
                        blocked = cursor.fetchone() is not None
                    if blocked or future.done():
                        break
                    sleep(0.02)
                self.assertTrue(blocked, "Review did not wait on the receipt lock")
            self.assertIn("receipt basis changed", future.result(timeout=10))
        row.refresh_from_db()
        self.assertEqual(row.status, row.PROPOSED)
        self.assertEqual(row.events.count(), 1)
