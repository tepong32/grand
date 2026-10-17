from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.receiving import (create_receipt, save_receipt_line, attach_receipt_evidence,
                                 submit_receipt, accept_receipt)
from inventory.receiving_followups import create_followup, source_basis
from inventory_finance.receipt_basis import receipt_basis
from inventory_finance.services import _receipt_support_limit
from . import test_grand_receiving_authority as fixture
from . import test_grand_attribution


class GrandFollowupTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixture.GrandReceivingAuthorityTests.setUpTestData.__func__)
    setUp = fixture.GrandReceivingAuthorityTests.setUp
    data = fixture.GrandReceivingAuthorityTests.data

    def finish(self, receipt):
        for kind in ("delivery", "inspection"):
            receipt.refresh_from_db()
            attach_receipt_evidence(actor=self.clerk, receipt=receipt,
                expected_version=receipt.state_version, kind=kind, note="Retained test packet",
                upload=SimpleUploadedFile("test.pdf", b"%PDF-1.4\nSynthetic\n%%EOF"))
        receipt.refresh_from_db()
        receipt = submit_receipt(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version)
        return accept_receipt(actor=self.reviewer, receipt=receipt,
            expected_version=receipt.state_version, note="Independent inspection")

    def test_native_followup_authority_and_retained_finance_basis(self):
        with CaptureQueriesContext(connections["finance"]) as queries:
            root = create_receipt(actor=self.clerk, data=self.data())
            line = save_receipt_line(actor=self.clerk, receipt=root, expected_version=1,
                data=dict(kind="asset", description="Printer", unit="unit", property_tag="FOLLOWUP-PRINTER",
                    delivered_quantity=1, accepted_quantity=0, rejected_quantity=0, unit_cost=Decimal("100")))
            root = self.finish(root)
            line.refresh_from_db()
            old_basis = receipt_basis(line)
            args = dict(source_line_id=line.pk, request_id=uuid4(), expected_basis=source_basis(line),
                inspection={key: self.data()[key] for key in
                    ("inspection_reference", "inspection_date", "inspector_label", "evidence_reference")},
                quantities=dict(accepted_quantity=Decimal("1"), rejected_quantity=Decimal("0"), unit_cost=Decimal("100")))
            for actor in (self.viewer, self.super_no_grant, self.outsider):
                with self.assertRaises(PermissionDenied):
                    create_followup(actor=actor, **args)
            self.client.force_login(self.viewer)
            self.assertEqual(self.client.get(reverse("inventory:receiving-followup", args=[line.pk])).status_code, 403)
            child = self.finish(create_followup(actor=self.clerk, **args))
            accepted = child.lines.get()
            self.assertIsNotNone(accepted.registered_asset_id)
            self.assertEqual(_receipt_support_limit(accepted), Decimal("100"))
            self.assertIn("followup", receipt_basis(accepted))
            line.refresh_from_db()
            self.assertEqual(receipt_basis(line), old_basis)
            self.assertNotIn("followup", old_basis)
        self.assertEqual(len(queries), 0)


class GrandFollowupClaimTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(test_grand_attribution.AttributionTests.setUpTestData.__func__)
    setUp = fixture.GrandReceivingAuthorityTests.setUp
    data = fixture.GrandReceivingAuthorityTests.data
    propose = test_grand_attribution.AttributionTests.propose
    approve = test_grand_attribution.AttributionTests.approve
    second_claim_proposal = test_grand_attribution.AttributionTests.second_claim_proposal

    def test_original_approved_support_survives_separately_reviewed_followup(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from profiles.models import EmployeeProfile
        from inventory.models import ConsumableItem
        from inventory_finance.receipt_basis import receipt_basis_current
        from inventory_finance.models import ReceiptClaimAttribution
        native_reviewer = get_user_model().objects.create_user(username="followup-gso-reviewer")
        EmployeeProfile.objects.filter(user=native_reviewer).update(assigned_department=self.gso)
        native_reviewer.refresh_from_db()
        grants = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_receivingreceipt", "add_receivingreceipt", "change_receivingreceipt",
            "submit_receivingreceipt", "review_receivingreceipt", "receive_stock"))
        self.clerk.user_permissions.add(*grants)
        native_reviewer.user_permissions.add(*grants)
        for name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.clerk.__dict__.pop(name, None)
        item = ConsumableItem.objects.create(department_id=self.gso.pk, name="Claim paper", unit="ream")

        def finish(receipt):
            for kind in ("delivery", "inspection"):
                receipt.refresh_from_db()
                attach_receipt_evidence(actor=self.clerk, receipt=receipt,
                    expected_version=receipt.state_version, kind=kind, note="Synthetic claim packet",
                    upload=SimpleUploadedFile("test.pdf", b"%PDF-1.4\nSynthetic\n%%EOF"))
            receipt.refresh_from_db()
            receipt = submit_receipt(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version)
            return accept_receipt(actor=native_reviewer, receipt=receipt,
                expected_version=receipt.state_version, note="Independent physical inspection")

        with CaptureQueriesContext(connections["finance"]) as queries:
            root = create_receipt(actor=self.clerk, data=self.data())
            original = save_receipt_line(actor=self.clerk, receipt=root, expected_version=1,
                data=dict(kind="supply", description="Claim paper", unit="ream", supply_item=item,
                    delivered_quantity=2, accepted_quantity=1, rejected_quantity=0, unit_cost=Decimal("100")))
            finish(root)
            original.refresh_from_db()
            self.receipt_line = original
            old = self.approve(self.propose())
            old_snapshot = old.receipt_snapshot
            child = create_followup(actor=self.clerk, source_line_id=original.pk, request_id=uuid4(),
                expected_basis=source_basis(original), inspection={key: self.data()[key] for key in
                    ("inspection_reference", "inspection_date", "inspector_label", "evidence_reference")},
                quantities=dict(accepted_quantity=Decimal("1"), rejected_quantity=Decimal("0"), unit_cost=Decimal("100")))
            child = finish(child)
            new_line = child.lines.get()
            new = self.approve(self.propose(amount="40.00", receipt_line_id=new_line.pk,
                expected_receipt_basis=receipt_basis(new_line)))
            old.refresh_from_db()
            self.assertTrue(receipt_basis_current(old))
            self.assertEqual(old.receipt_snapshot, old_snapshot)
            self.assertEqual(old.status, ReceiptClaimAttribution.APPROVED)
            self.assertEqual(new.receipt_line_id, new_line.pk)
            self.assertIn("followup", new.receipt_snapshot)
            self.assertEqual(old.amount + new.amount, Decimal("100.00"))
            self.assertEqual(item.on_hand, 2)
        self.assertEqual(len(queries), 0)
