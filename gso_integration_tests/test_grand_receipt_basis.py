"""Receipt-side evidence stays fixed even when future corrections change live facts."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import ConsumableItem, ReceivingLine, ReceivingReceipt
from inventory_finance.models import ReceiptClaimAttribution
from inventory_finance.receipt_basis import receipt_basis, receipt_basis_current
from inventory_finance.services import close_attribution
from . import test_grand_attribution, test_grand_attribution_http


class ReceiptBasisTests(TestCase):
    databases = {"default", "finance"}
    propose = test_grand_attribution.AttributionTests.propose
    approve = test_grand_attribution.AttributionTests.approve
    second_claim_proposal = test_grand_attribution.AttributionTests.second_claim_proposal

    @classmethod
    def setUpTestData(cls):
        test_grand_attribution.AttributionTests.setUpTestData.__func__(cls)

    def test_receipt_change_cannot_be_silently_approved_or_replace_recorded_facts(self):
        row = self.propose()
        basis = row.receipt_snapshot
        ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(description="Corrected description", unit_cost=Decimal("200.00"))
        with self.assertRaisesMessage(ValidationError, "receipt basis changed"):
            self.approve(row)
        row.refresh_from_db()
        self.assertEqual(row.receipt_snapshot, basis)
        self.assertEqual(row.events.get().snapshot["receipt"], basis)
        self.client.force_login(self.reviewer)
        page = self.client.get(reverse("inventory_finance:detail", args=[row.public_id]))
        self.assertContains(page, "Synthetic equipment")
        self.assertNotContains(page, "Corrected description")
        self.assertNotIn(("approve", "Approve support"), page.context["form"].fields["action"].choices)

    def test_old_cross_claim_support_requires_explicit_withdrawal_after_basis_change(self):
        original = self.approve(self.propose())
        ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(unit_cost=Decimal("200.00"))
        replacement = self.second_claim_proposal()
        with self.assertRaisesMessage(ValidationError, "stale or missing receipt basis"):
            self.approve(replacement)
        with CaptureQueriesContext(connections["finance"]) as finance:
            close_attribution(actor=self.reviewer, attribution_id=original.public_id,
                expected_version=original.state_version, action="withdraw", reason="Receipt correction reviewed")
            self.approve(replacement)
        self.assertEqual(len(finance), 0)
        original.refresh_from_db()
        self.assertEqual(original.receipt_snapshot["line"]["unit_cost"], "100.00")
        self.assertEqual(original.status, original.WITHDRAWN)

    def test_unknown_legacy_basis_blocks_review_and_capacity_but_retains_history(self):
        old = self.approve(self.propose())
        ReceiptClaimAttribution.objects.filter(pk=old.pk).update(receipt_snapshot=None)
        new = self.propose(amount="20.00")
        with self.assertRaisesMessage(ValidationError, "missing receipt basis"):
            self.approve(new)
        ReceiptClaimAttribution.objects.filter(pk=new.pk).update(receipt_snapshot=None)
        with self.assertRaisesMessage(ValidationError, "was not retained"):
            self.approve(new)
        old.refresh_from_db()
        self.assertFalse(receipt_basis_current(old))
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(reverse("inventory_finance:detail", args=[old.public_id])), "Not retained by this historical link")
        closed = close_attribution(actor=self.reviewer, attribution_id=old.public_id,
            expected_version=old.state_version, action="withdraw", reason="Historical basis cannot be established")
        self.assertIsNone(closed.receipt_snapshot)
        self.assertIsNotNone(closed.reviewed_at)

    def test_equal_value_and_header_changes_still_invalidate_receipt_basis(self):
        item = ConsumableItem.objects.create(department_id=self.gso.pk, name="Synthetic supply", unit="unit")
        ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(kind="supply", supply_item=item)
        row = self.propose()
        ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(delivered_quantity=2, accepted_quantity=2, unit_cost=Decimal("50.00"))
        with self.assertRaisesMessage(ValidationError, "receipt basis changed"):
            self.approve(row)
        ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(delivered_quantity=1, accepted_quantity=1, unit_cost=Decimal("100.00"))
        ReceivingReceipt.objects.filter(pk=self.receipt.pk).update(inspection_reference="Revised inspection")
        with self.assertRaisesMessage(ValidationError, "receipt basis changed"):
            self.approve(row)


class ReceiptBasisHttpTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(test_grand_attribution_http.AttributionHttpTests.setUpTestData.__func__)
    setUp = test_grand_attribution_http.AttributionHttpTests.setUp
    csrf = test_grand_attribution_http.AttributionHttpTests.csrf
    preview = test_grand_attribution_http.AttributionHttpTests.preview
    confirm = test_grand_attribution_http.AttributionHttpTests.confirm

    def test_preview_pins_receipt_and_old_payload_without_basis_fails_closed(self):
        from django.core import signing
        token = self.preview()
        payload = signing.loads(token, salt="gso-receipt-claim-proposal-v1")
        payload.pop("receipt_basis")
        self.assertContains(self.confirm(signing.dumps(payload, salt="gso-receipt-claim-proposal-v1")), "receipt source changed")
        ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(unit_cost=Decimal("200.00"))
        self.assertContains(self.confirm(token), "receipt source changed")
        self.assertEqual(ReceiptClaimAttribution.objects.count(), 0)
        self.assertEqual(self.confirm(self.preview()).status_code, 302)
        self.assertEqual(ReceiptClaimAttribution.objects.get().receipt_snapshot["line"]["unit_cost"], "200.00")


class ReceiptBasisMigrationTests(TransactionTestCase):
    databases = {"default", "finance"}

    def test_populated_upgrade_preserves_unknown_basis_and_all_existing_values(self):
        before = [("inventory_finance", "0001_initial")]
        after = [("inventory_finance", "0002_receipt_review_basis")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            test_grand_attribution.AttributionTests.setUpTestData.__func__(type(self))
            apps = executor.loader.project_state(before).apps
            Row = apps.get_model("inventory_finance", "ReceiptClaimAttribution")
            Event = apps.get_model("inventory_finance", "ReceiptClaimEvent")
            row = Row.objects.create(receipt_line_id=self.receipt_line.pk, case_id=self.case.pk,
                finance_department_id=self.finance.pk, source_line_id=self.line.pk,
                source_snapshot={"retained":"legacy"}, source_checksum="a"*64,
                amount=Decimal("50.00"), basis="Historical approval", status="approved",
                proposed_by_id=self.clerk.pk, reviewed_by_id=self.reviewer.pk, reviewed_at=timezone.now())
            Event.objects.create(attribution=row, actor_id=self.reviewer.pk, action="approved", snapshot={"retained":"original"})
            fields = [f.name for f in Row._meta.fields]
            old_rows = list(Row.objects.values(*fields))
            old_events = list(Event.objects.values())
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            current = executor.loader.project_state(after).apps
            Current = current.get_model("inventory_finance", "ReceiptClaimAttribution")
            self.assertEqual(list(Current.objects.values(*fields)), old_rows)
            self.assertIsNone(Current.objects.get().receipt_snapshot)
            self.assertEqual(list(current.get_model("inventory_finance", "ReceiptClaimEvent").objects.values()), old_events)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())


from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction


@skipUnless(connection.vendor == "mysql", "Requires native MySQL locks and separate connections")
class ReceiptBasisConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        test_grand_attribution.AttributionTests.setUpTestData.__func__(type(self))

    def test_waiting_review_reloads_receipt_facts_after_amendment_commits(self):
        row = test_grand_attribution.AttributionTests.propose(self)
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
            # Models a future amendment's receipt lock; not a cost-correction API.
            with transaction.atomic(using="default"):
                ReceivingReceipt.objects.select_for_update().get(pk=self.receipt.pk)
                ReceivingLine.objects.filter(pk=self.receipt_line.pk).update(unit_cost=Decimal("200.00"))
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
