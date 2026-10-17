from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep
from unittest import skipUnless
from uuid import uuid4
import hashlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from profiles.models import EmployeeProfile
from inventory_finance import journal_mappings as service
from inventory_finance.models import ReceiptJournalMapping as Mapping
from inventory_finance.services import close_attribution
from accounting.models import JournalEntry
from inventory.models import ReceivingEvidence
from . import test_grand_journal_sources, test_grand_attribution


class MappingTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_journal_sources.JournalSourceTests.setUpTestData.__func__(cls)
        for kind in ("delivery", "inspection"):
            data = b"%PDF-1.4\nSynthetic retained source\n%%EOF"
            ReceivingEvidence.objects.create(receipt=cls.receipt, kind=kind, note="Synthetic source",
                file=SimpleUploadedFile(kind+".pdf", data), original_filename=kind+".pdf",
                size=len(data), sha256=hashlib.sha256(data).hexdigest(), uploaded_by=cls.clerk)
        cls.mapping_reviewer = get_user_model().objects.create_user(username="mapping-reviewer", email="mapping@example.test")
        EmployeeProfile.objects.filter(user=cls.mapping_reviewer).update(assigned_department=cls.finance)
        cls.mapping_reviewer.refresh_from_db()
        for actor in (cls.reviewer, cls.mapping_reviewer):
            for app, names in (("inventory_finance", ("propose_receiptjournalmapping", "review_receiptjournalmapping", "review_receiptclaimattribution")),
                               ("accounting", ("view_general_ledger",)), ("vouchers", ("view_voucher_workbench",))):
                actor.user_permissions.add(*Permission.objects.filter(content_type__app_label=app, codename__in=names))
        fixture = cls()
        cls.claim = test_grand_attribution.AttributionTests.propose(fixture, amount="100.00")
        cls.claim = test_grand_attribution.AttributionTests.approve(fixture, cls.claim)

    def propose(self, amount="60.00", **changes):
        evidence = service.capture(actor=self.reviewer, claim=self.claim, posting_request_id=self.source.public_id, sequence=1)
        args = dict(actor=self.reviewer, claim_id=self.claim.public_id, posting_request_id=self.source.public_id,
            sequence=1, amount=amount, basis="Invoice equipment recognition", request_id=uuid4(), expected_basis=evidence)
        args.update(changes)
        return service.propose(**args)

    def decide(self, row, action="approve", **changes):
        args = dict(actor=self.mapping_reviewer, mapping_id=row.public_id, expected_version=row.state_version,
            action=action, note="Reviewed retained documents")
        args.update(changes)
        return service.decide(**args)

    def test_review_withdraw_and_finance_read_only(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            row = self.propose()
            row = self.decide(row)
            service.current(row, self.mapping_reviewer)
            with self.assertRaisesMessage(ValidationError, "recognition mappings"):
                close_attribution(actor=self.reviewer, attribution_id=self.claim.public_id,
                    expected_version=self.claim.state_version, action="withdraw", reason="Correction")
            review = row.reviewed_at
            row = self.decide(row, "withdraw")
            self.assertEqual(row.reviewed_at, review)
            service.verify(row)
        self.assertFalse(any(query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for query in finance))
        self.assertEqual(list(row.events.values_list("action", flat=True)), ["proposed", "approved", "withdrawn"])
        self.assertEqual(self.receipt_line.unit_cost, 100)
        close_attribution(actor=self.reviewer, attribution_id=self.claim.public_id,
            expected_version=self.claim.state_version, action="withdraw", reason="Correction")

    def test_independence_capacity_and_replay(self):
        row = self.propose()
        self.assertEqual(self.propose(request_id=row.public_id).pk, row.pk)
        with self.assertRaises(ValidationError):
            self.propose("61", request_id=row.public_id)
        with self.assertRaises(PermissionDenied):
            self.decide(row, actor=self.reviewer)
        self.decide(row)
        other = self.propose("50")
        with self.assertRaisesMessage(ValidationError, "exceed"):
            self.decide(other)
        with self.assertRaises(ValidationError):
            self.decide(row)
        for amount in ("0", "-1", "1.001", "NaN", 1.2, True, "101"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.propose(amount)

    def test_source_change_and_corrupt_history_are_not_current(self):
        row = self.propose()
        JournalEntry.objects.filter(pk=self.entry.pk).update(source_reference="changed")
        with self.assertRaises(ValidationError):
            self.decide(row)
        # Withdrawal remains possible without reproducing a broken journal.
        row = self.decide(row, "withdraw")
        Mapping.objects.filter(pk=row.pk).update(amount="59")
        row.refresh_from_db()
        with self.assertRaises(ValidationError):
            service.verify(row)

    def test_signed_http_preview_scope_and_csrf(self):
        url = reverse("inventory_finance:journal-mappings", args=[self.claim.public_id])
        self.client.force_login(self.reviewer)
        response = self.client.post(url, {"action": "preview", "posting_request": self.source.pk,
            "sequence": 1, "amount": "60.00", "basis": "Documented equipment"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["preview"])
        token = response.context["confirmation"].initial["proposal_token"]
        response = self.client.post(url, {"action": "confirm", "proposal_token": token + "changed"})
        self.assertContains(response, "preview expired or changed")
        self.assertEqual(Mapping.objects.count(), 0)
        self.client.force_login(self.mapping_reviewer)
        self.assertEqual(self.client.post(url, {"action": "confirm", "proposal_token": token}).status_code, 403)
        self.client.force_login(self.reviewer)
        response = self.client.post(url, {"action": "confirm", "proposal_token": token})
        self.assertEqual(response.status_code, 302)
        row = Mapping.objects.get()
        detail = reverse("inventory_finance:mapping-detail", args=[row.public_id])
        self.client.force_login(self.mapping_reviewer)
        response = self.client.post(detail, {"expected_version": 1, "action": "approve", "note": "Independent review"})
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, row.APPROVED)
        self.assertIn("no-store", self.client.get(detail)["Cache-Control"])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.mapping_reviewer)
        self.assertEqual(csrf.post(detail, {"action": "withdraw"}).status_code, 403)
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(url, {"action": "preview"}).status_code, 403)

    def test_immutability_and_stale_receipt(self):
        row = self.propose()
        row.basis = "overwrite"
        with self.assertRaises(ValidationError):
            row.save()
        self.receipt.state_version += 1
        self.receipt.save(update_fields=["state_version"])
        with self.assertRaises(ValidationError):
            self.decide(row)

    def test_uat_explicit_grants_and_non_debit_sources(self):
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        for sequence in (2, 0, True, "1.5"):
            with self.subTest(sequence=sequence), self.assertRaises(ValidationError):
                service.capture(actor=self.reviewer, claim=self.claim,
                    posting_request_id=self.source.public_id, sequence=sequence)
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            self.propose()
        self.reviewer.groups.clear()
        self.reviewer.user_permissions.remove(Permission.objects.get(
            content_type__app_label="inventory_finance", codename="propose_receiptjournalmapping"))
        self.reviewer.is_superuser = True
        self.reviewer.save(update_fields=["is_superuser"])
        with self.assertRaises(PermissionDenied):
            self.propose()

    def test_missing_private_document_blocks_review_but_not_withdrawal(self):
        from pathlib import Path
        row = self.propose()
        evidence = self.receipt.evidence.first()
        path = Path(evidence.file.path)
        original = path.read_bytes()
        try:
            path.unlink()
            with self.assertRaisesMessage(ValidationError, "unavailable"):
                self.decide(row)
            path.write_bytes(b"Changed retained document")
            with self.assertRaisesMessage(ValidationError, "integrity"):
                self.decide(row)
            self.decide(row, "withdraw")
        finally:
            path.write_bytes(original)


@skipUnless(connection.vendor == "mysql", "Requires native row locking")
class MappingRaceTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        MappingTests.setUpTestData.__func__(type(self))

    def test_caller_cannot_defer_default_commit_past_finance_lock(self):
        with transaction.atomic(using="default"):
            with self.assertRaisesMessage(RuntimeError, "durable"):
                MappingTests.propose(self)

    def test_competing_approvals_cannot_exceed_recognition_debit(self):
        first = MappingTests.propose(self, "60")
        second = MappingTests.propose(self, "60")
        barrier = Barrier(2)

        def approve(pk):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.mapping_reviewer.pk)
                barrier.wait(timeout=10)
                try:
                    service.decide(actor=actor, mapping_id=pk, expected_version=1, action="approve", note="Concurrent review")
                    return "approved"
                except ValidationError as exc:
                    self.assertIn("exceed", str(exc))
                    return "capacity"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(approve, (first.public_id, second.public_id)))
        self.assertCountEqual(results, ["approved", "capacity"])
        self.assertEqual(Mapping.objects.filter(status=Mapping.APPROVED).count(), 1)

    def test_waiting_approval_rechecks_actual_reversal(self):
        from accounting.services import create_reversal
        row = MappingTests.propose(self)
        started, reader_connection = Event(), []

        def review():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.mapping_reviewer.pk)
                with connections["finance"].cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = 8")
                    cursor.execute("SELECT CONNECTION_ID()")
                    reader_connection.append(cursor.fetchone()[0])
                started.set()
                try:
                    service.decide(actor=actor, mapping_id=row.public_id, expected_version=1,
                                   action="approve", note="Concurrent review")
                    return "unexpected approval"
                except ValidationError as exc:
                    return str(exc)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic(using="finance"):
                JournalEntry.objects.select_for_update().get(pk=self.entry.pk)
                self.entry.refresh_from_db()
                create_reversal(self.entry, self.reviewer, reference="MAPPING-REVERSAL",
                    entry_date=self.entry.entry_date, period=self.entry.period, reason="Correct recognition")
                future = executor.submit(review)
                self.assertTrue(started.wait(3))
                deadline, blocked = monotonic()+3, False
                while monotonic() < deadline:
                    with connections["finance"].cursor() as cursor:
                        cursor.execute("""SELECT 1 FROM performance_schema.data_lock_waits w
                            JOIN performance_schema.threads t ON t.THREAD_ID=w.REQUESTING_THREAD_ID
                            WHERE t.PROCESSLIST_ID=%s""", [reader_connection[0]])
                        blocked = cursor.fetchone() is not None
                    if blocked or future.done():
                        break
                    sleep(0.02)
                self.assertTrue(blocked, "Mapping approval did not wait on original journal")
            self.assertIn("reversal", future.result(timeout=10))
        row.refresh_from_db()
        self.assertEqual(row.status, row.PROPOSED)
        self.assertEqual(row.events.count(), 1)
