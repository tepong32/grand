"""Explicit GRAND harness tests; use real shared identities and Finance models."""
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, connection, close_old_connections
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from profiles.models import EmployeeProfile
from vouchers.models import VoucherCase, VoucherLineItem, DisbursementVoucher
from inventory.models import ReceivingReceipt, ReceivingLine
from inventory.finance_sources import resolve_claim_line
from inventory_finance.access import visible_attributions
from inventory_finance.models import ReceiptClaimAttribution
from inventory_finance.services import propose_attribution, approve_attribution, close_attribution
from inventory_finance.receipt_basis import receipt_basis
from . import test_grand_claim_sources


class AttributionTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_claim_sources.GrandClaimSourceTests.setUpTestData.__func__(cls)
        cls.gso.name = "General Services Office"
        cls.gso.save(update_fields=("name",))
        cls.clerk.refresh_from_db()
        cls.clerk.user_permissions.add(Permission.objects.get(
            content_type__app_label="inventory_finance", codename="propose_receiptclaimattribution"))
        cls.reviewer = get_user_model().objects.create_user(username="attribution-reviewer", email="reviewer@example.test")
        EmployeeProfile.objects.filter(user=cls.reviewer).update(assigned_department=cls.finance)
        cls.reviewer.refresh_from_db()
        cls.reviewer.user_permissions.add(
            Permission.objects.get(content_type__app_label="vouchers", codename="view_voucher_workbench"),
            Permission.objects.get(content_type__app_label="inventory_finance", codename="review_receiptclaimattribution"))
        cls.receipt = ReceivingReceipt.objects.create(department_id=cls.gso.pk, department_label=cls.gso.name,
            supplier="Synthetic supplier", delivery_reference="SYNTHETIC", delivery_date="2026-10-16",
            inspection_reference="SYNTHETIC", inspection_date="2026-10-16", inspector_label="Synthetic",
            evidence_reference="Synthetic accepted fixture", status=ReceivingReceipt.ACCEPTED, created_by=cls.clerk)
        cls.receipt_line = ReceivingLine.objects.create(receipt=cls.receipt, sequence=1, kind=ReceivingLine.ASSET,
            description="Synthetic equipment", unit="unit", delivered_quantity=1, accepted_quantity=1,
            unit_cost=Decimal("100.00"))

    def propose(self, amount="60.00", **overrides):
        source = resolve_claim_line(actor=self.clerk, case_public_id=self.case.public_id, line_id=self.line.pk)
        args = dict(actor=self.clerk, receipt_line_id=self.receipt_line.pk, case_public_id=self.case.public_id,
                    source_line_id=self.line.pk, source_checksum=source["sha256"], amount=amount,
                    basis="Documented invoice support", request_id=uuid4(),
                    expected_receipt_basis=receipt_basis(ReceivingLine.objects.select_related("receipt").get(pk=self.receipt_line.pk)))
        args.update(overrides)
        return propose_attribution(**args)

    def approve(self, row, actor=None):
        return approve_attribution(actor=actor or self.reviewer, attribution_id=row.public_id,
                                   expected_version=row.state_version, note="Reviewed against accepted receipt")

    def second_claim_proposal(self):
        case = VoucherCase.objects.create(reference_code="SECOND-SYNTHETIC-CLAIM",
            requesting_department=self.gso, current_department=self.finance,
            configuration_release=self.case.configuration_release, payee=self.case.payee,
            payee_name=self.case.payee_name, particulars="Second claim", created_by=self.clerk,
            current_stage=self.case.current_stage)
        voucher = DisbursementVoucher.objects.create(case=case, dv_number="SECOND-SYNTHETIC-DV",
            voucher_date=self.voucher.voucher_date, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"),
            prepared_by=self.clerk, prepared_at=self.voucher.prepared_at)
        line = VoucherLineItem.objects.create(voucher=voucher, description="Other claim", amount=Decimal("100.00"))
        source = resolve_claim_line(actor=self.clerk, case_public_id=case.public_id, line_id=line.pk)
        return self.propose(amount="60.00", case_public_id=case.public_id,
                            source_line_id=line.pk, source_checksum=source["sha256"])

    def test_propose_approve_withdraw_preserves_history_and_router(self):
        with CaptureQueriesContext(connections["finance"]) as queries:
            row = self.propose()
            row = self.approve(row)
            original_review = row.reviewed_at
            row = close_attribution(actor=self.reviewer, attribution_id=row.public_id,
                expected_version=row.state_version, action="withdraw", reason="Corrected allocation required")
        self.assertEqual(len(queries), 0)
        self.assertEqual(row.status, row.WITHDRAWN)
        self.assertEqual(row.reviewed_at, original_review)
        self.assertEqual(list(row.events.values_list("action", flat=True)), ["proposed", "approved", "withdrawn"])
        self.assertEqual(visible_attributions(self.outsider).count(), 0)
        self.assertEqual(visible_attributions(self.clerk).get().pk, row.pk)

    def test_retry_does_not_duplicate_and_different_payload_cannot_reuse_identity(self):
        request_id = uuid4()
        row = self.propose(request_id=request_id)
        self.assertEqual(row.pk, self.propose(request_id=request_id).pk)
        self.assertEqual(row.events.count(), 1)
        with self.assertRaises(ValidationError):
            self.propose(amount="61.00", request_id=request_id)

    def test_amount_validation_and_approved_capacity(self):
        for amount in ("0", "-1", "1.001", "NaN", "Infinity", 1.2, True, "101.00"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.propose(amount=amount)
        self.approve(self.propose(amount="60.00"))
        other = self.propose(amount="50.00")
        with self.assertRaisesMessage(ValidationError, "exceed"):
            self.approve(other)
        other.refresh_from_db()
        self.assertEqual(other.status, other.PROPOSED)
        self.assertEqual(other.events.count(), 1)

    def test_unaccepted_receipt_and_wrong_office_cannot_propose(self):
        ReceivingReceipt.objects.filter(pk=self.receipt.pk).update(status=ReceivingReceipt.DRAFT)
        with self.assertRaises(ValidationError):
            self.propose()
        with self.assertRaises(PermissionDenied):
            self.propose(actor=self.no_grant)

    def test_uat_and_self_review_are_denied_even_with_explicit_review_grant(self):
        grant = Permission.objects.get(content_type__app_label="inventory_finance", codename="review_receiptclaimattribution")
        self.viewer.user_permissions.add(grant)
        row = self.propose()
        with self.assertRaises(PermissionDenied):
            self.approve(row, actor=self.viewer)
        EmployeeProfile.objects.filter(user=self.clerk).update(assigned_department=self.finance)
        self.clerk.refresh_from_db()
        self.clerk.user_permissions.add(grant)
        with self.assertRaises(PermissionDenied):
            self.approve(row, actor=self.clerk)

    def test_changed_version_blocks_approval_but_can_be_rejected(self):
        row = self.propose()
        VoucherCase.objects.filter(pk=self.case.pk).update(state_version=1)
        with self.assertRaisesMessage(ValidationError, "source changed"):
            self.approve(row)
        row = close_attribution(actor=self.reviewer, attribution_id=row.public_id,
            expected_version=row.state_version, action="reject", reason="Claim changed")
        self.assertEqual(row.status, row.REJECTED)

    def test_replacement_requires_withdrawal_of_old_approved_support(self):
        original = self.approve(self.propose(amount="100.00"))
        self.voucher.line_items.all().delete()
        self.line = VoucherLineItem.objects.create(voucher=self.voucher, description="Reprepared", amount=Decimal("100.00"))
        replacement = self.propose(amount="100.00")
        with self.assertRaisesMessage(ValidationError, "stale source"):
            self.approve(replacement)
        close_attribution(actor=self.reviewer, attribution_id=original.public_id,
            expected_version=original.state_version, action="withdraw", reason="DV line replaced")
        self.assertEqual(self.approve(replacement).status, ReceiptClaimAttribution.APPROVED)

    def test_stale_review_version_cannot_repeat_decision(self):
        row = self.propose()
        self.approve(row)
        with self.assertRaises(ValidationError):
            self.approve(row)

    def test_foreign_receipt_is_denied_before_status_validation(self):
        ReceivingReceipt.objects.filter(pk=self.receipt.pk).update(
            department_id=self.other.pk, status=ReceivingReceipt.DRAFT)
        with self.assertRaises(PermissionDenied):
            self.propose()

    def test_different_claims_share_receipt_value_capacity(self):
        self.approve(self.propose(amount="60.00"))
        row = self.second_claim_proposal()
        with self.assertRaisesMessage(ValidationError, "across claims"):
            self.approve(row)

    def test_unknown_or_zero_receipt_value_does_not_create_support(self):
        for cost in (None, Decimal("0.00")):
            ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(unit_cost=cost)
            with self.subTest(cost=cost), self.assertRaisesMessage(ValidationError, "documented unit cost"):
                self.propose()


@skipUnless(connection.vendor == "mysql", "Requires native MySQL locks and independent connections")
class AttributionConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    propose = AttributionTests.propose
    second_claim_proposal = AttributionTests.second_claim_proposal

    def setUp(self):
        AttributionTests.setUpTestData.__func__(type(self))

    def race(self, operation, arguments, actor_id):
        barrier = Barrier(2)

        def work(kwargs):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = 8")
                barrier.wait(timeout=5)
                try:
                    return ("ok", operation(actor=actor, **kwargs).pk)
                except ValidationError as exc:
                    return ("conflict", str(exc))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(work, kwargs) for kwargs in arguments]
            return [future.result(timeout=15) for future in futures]

    def test_competing_approvals_cannot_overallocate_source(self):
        rows = [self.propose(amount="60.00"), self.propose(amount="60.00")]
        results = self.race(approve_attribution, [dict(attribution_id=row.public_id,
            expected_version=1, note="Concurrent review") for row in rows], self.reviewer.pk)
        self.assertCountEqual([result[0] for result in results], ["ok", "conflict"])
        approved = ReceiptClaimAttribution.objects.filter(status=ReceiptClaimAttribution.APPROVED)
        self.assertEqual(approved.aggregate(total=Sum("amount"))["total"], Decimal("60.00"))
        self.assertEqual(ReceiptClaimAttribution.objects.filter(status=ReceiptClaimAttribution.PROPOSED).count(), 1)

    def test_same_proposal_cannot_be_approved_twice(self):
        row = self.propose()
        args = dict(attribution_id=row.public_id, expected_version=1, note="Concurrent review")
        results = self.race(approve_attribution, [args, args], self.reviewer.pk)
        self.assertCountEqual([result[0] for result in results], ["ok", "conflict"])
        self.assertEqual(row.events.filter(action="approved").count(), 1)

    def test_competing_different_claims_cannot_overallocate_one_receipt(self):
        rows = [self.propose(amount="60.00"), self.second_claim_proposal()]
        results = self.race(approve_attribution, [dict(attribution_id=row.public_id,
            expected_version=1, note="Concurrent different claims") for row in rows], self.reviewer.pk)
        self.assertCountEqual([result[0] for result in results], ["ok", "conflict"])
        self.assertEqual(ReceiptClaimAttribution.objects.filter(status=ReceiptClaimAttribution.APPROVED)
            .aggregate(total=Sum("amount"))["total"], Decimal("60.00"))

    def test_duplicate_proposal_request_has_one_record_and_event(self):
        source = resolve_claim_line(actor=self.clerk, case_public_id=self.case.public_id, line_id=self.line.pk)
        args = dict(receipt_line_id=self.receipt_line.pk, case_public_id=self.case.public_id,
            source_line_id=self.line.pk, source_checksum=source["sha256"], amount="60.00",
            basis="Concurrent retry", request_id=uuid4(),
            expected_receipt_basis=receipt_basis(ReceivingLine.objects.select_related("receipt").get(pk=self.receipt_line.pk)))
        results = self.race(propose_attribution, [args, args], self.clerk.pk)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], "ok")
        self.assertEqual(ReceiptClaimAttribution.objects.count(), 1)
        self.assertEqual(ReceiptClaimAttribution.objects.get().events.count(), 1)
