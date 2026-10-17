from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from profiles.models import EmployeeProfile
from inventory.models import ConsumableItem, ReceiptQuantityCorrection as Correction
from inventory.receiving import create_receipt, save_receipt_line, attach_receipt_evidence, submit_receipt, accept_receipt
from inventory.receipt_quantity_corrections import record, decide, source_basis
from inventory_finance.receipt_basis import receipt_basis
from inventory_finance.services import _receipt_support_limit, close_attribution
from . import test_grand_receiving_authority as authority
from . import test_grand_attribution as claims


class GrandQuantityCorrectionTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(claims.AttributionTests.setUpTestData.__func__)
    data = authority.GrandReceivingAuthorityTests.data
    propose = claims.AttributionTests.propose
    approve = claims.AttributionTests.approve

    def setUp(self):
        authority.GrandReceivingAuthorityTests.setUp(self)
        files = TemporaryDirectory()
        self.addCleanup(files.cleanup)
        storage = patch.object(Correction._meta.get_field("file"), "storage", FileSystemStorage(location=files.name))
        storage.start()
        self.addCleanup(storage.stop)
        self.gso_reviewer = get_user_model().objects.create_user(username="quantity-reviewer")
        EmployeeProfile.objects.filter(user=self.gso_reviewer).update(assigned_department=self.gso)
        self.gso_reviewer.refresh_from_db()
        grants = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_receivingreceipt", "add_receivingreceipt", "change_receivingreceipt",
            "submit_receivingreceipt", "review_receivingreceipt", "receive_stock", "adjust_stock",
            "record_receipt_quantity_correction", "review_receipt_quantity_correction"))
        for actor in (self.clerk, self.gso_reviewer, self.outsider, self.viewer):
            actor.user_permissions.add(*grants)
            for name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
                actor.__dict__.pop(name, None)
        item = ConsumableItem.objects.create(department_id=self.gso.pk, name="Correction paper", unit="ream", use_fifo=True)
        receipt = create_receipt(actor=self.clerk, data=self.data())
        self.receipt_line = save_receipt_line(actor=self.clerk, receipt=receipt, expected_version=1,
            data=dict(kind="supply", description="Correction paper", unit="ream", supply_item=item,
                      delivered_quantity=2, accepted_quantity=2, rejected_quantity=0, unit_cost=Decimal("50")))
        for kind in ("delivery", "inspection"):
            receipt.refresh_from_db()
            attach_receipt_evidence(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version,
                kind=kind, note="Synthetic original packet", upload=self.packet())
        receipt.refresh_from_db()
        receipt = submit_receipt(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version)
        accept_receipt(actor=self.gso_reviewer, receipt=receipt, expected_version=receipt.state_version,
                       note="Independent physical acceptance")
        self.receipt_line.refresh_from_db()

    def packet(self):
        return SimpleUploadedFile("source.pdf", b"%PDF-1.4\nSynthetic correction evidence\n%%EOF")

    def correction(self, actor=None):
        self.receipt_line.refresh_from_db()
        return record(actor=actor or self.clerk, line_id=self.receipt_line.pk, request_id=uuid4(),
            expected_basis=source_basis(self.receipt_line), quantity=Decimal("1"), reference="Clerical correction",
            reason="Both delivered and accepted were entered too high before use", upload=self.packet())

    def test_native_authority_pending_support_and_corrected_ceiling_without_finance_queries(self):
        with CaptureQueriesContext(connections["finance"]) as queries:
            baseline = receipt_basis(self.receipt_line)
            self.assertNotIn("quantity_correction", baseline)
            self.assertEqual(_receipt_support_limit(self.receipt_line), 100)
            for actor in (self.outsider, self.viewer, self.no_grant):
                with self.assertRaises(PermissionDenied):
                    self.correction(actor)
            row = self.correction()
            with self.assertRaisesMessage(ValidationError, "pending"):
                self.propose(amount="50")
            decide(actor=self.gso_reviewer, correction_id=row.pk, expected_version=1,
                   action="approve", note="Independently verified clerical case")
            self.receipt_line.refresh_from_db()
            self.assertEqual(_receipt_support_limit(self.receipt_line), 50)
            with self.assertRaisesMessage(ValidationError, "exceeds"):
                self.propose(amount="60")
            attribution = self.approve(self.propose(amount="50"))
            self.assertEqual(attribution.receipt_snapshot["quantity_correction"]["effective_accepted"], "1.000")
            self.assertEqual(self.receipt_line.accepted_quantity, 2)
        self.assertEqual(len(queries), 0)

    def test_withdrawn_finance_support_still_prevents_before_use_shortcut(self):
        row = self.approve(self.propose(amount="50"))
        close_attribution(actor=self.reviewer, attribution_id=row.public_id, expected_version=row.state_version,
                          action="withdraw", reason="Retain the original support history")
        with CaptureQueriesContext(connections["finance"]) as queries:
            with self.assertRaisesMessage(ValidationError, "Finance support history"):
                self.correction()
        self.assertEqual(len(queries), 0)
        self.assertEqual(Correction.objects.count(), 0)


@skipUnlessDBFeature("has_select_for_update")
class GrandQuantityCorrectionRaceTests(TransactionTestCase):
    databases = {"default", "finance"}
    data = GrandQuantityCorrectionTests.data
    packet = GrandQuantityCorrectionTests.packet
    propose = GrandQuantityCorrectionTests.propose
    correction = GrandQuantityCorrectionTests.correction

    def setUp(self):
        GrandQuantityCorrectionTests.setUpTestData.__func__(type(self))
        GrandQuantityCorrectionTests.setUp(self)

    def test_finance_proposal_and_correction_serialize_on_original_receipt(self):
        from inventory_finance.models import ReceiptClaimAttribution
        barrier = Barrier(2)
        actor_id = self.clerk.pk

        def run(operation):
            connections.close_all()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                operation(actor)
                return "recorded"
            except ValidationError:
                return "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, operation) for operation in (
                self.correction, lambda actor: self.propose(amount="50", actor=actor))]
            results = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(results, ["recorded", "conflict"])
        self.assertEqual(Correction.objects.count() + ReceiptClaimAttribution.objects.count(), 1)
        self.assertEqual(self.receipt_line.supply_item.on_hand, 2)
