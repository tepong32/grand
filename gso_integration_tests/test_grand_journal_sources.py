"""Actual GRAND two-store read boundary, using synthetic retained posting facts."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounting.models import AccountingPeriod, Fund, LedgerAccount, JournalEntry, JournalLine, AccountingAuditEvent
from vouchers.models import VoucherPostingRequest
from inventory_finance.journal_sources import inspect_recognition
from . import test_grand_attribution


class JournalSourceTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_attribution.AttributionTests.setUpTestData.__func__(cls)
        cls.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="accounting", codename="view_general_ledger"))
        owner = dict(department_id=cls.finance.pk, department_label=cls.finance.name)
        period = AccountingPeriod.objects.create(**owner, fiscal_year=2026, period_number=10,
            label="October", starts_on=date(2026, 10, 1), ends_on=date(2026, 10, 31))
        fund = Fund.objects.create(**owner, code="TEST", name="Synthetic fund")
        debit = LedgerAccount.objects.create(**owner, code="TEST-ASSET", title="Synthetic equipment",
            account_type="asset", normal_balance="debit")
        credit = LedgerAccount.objects.create(**owner, code="TEST-LIABILITY", title="Synthetic liability",
            account_type="liability", normal_balance="credit")
        payload = {"private": "DO-NOT-RENDER"}
        checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        cls.source = VoucherPostingRequest.objects.create(case=cls.case, kind="recognition", version=1,
            finance_department_id=cls.finance.pk, finance_department_label=cls.finance.name,
            jev_number="SYNTHETIC-JEV", jev_date=date(2026, 10, 17), requested_by=cls.reviewer,
            payload=payload, payload_checksum=checksum, status="posted", posted_at=timezone.now())
        cls.entry = JournalEntry.objects.create(**owner, reference=cls.source.jev_number,
            entry_date=cls.source.jev_date, period=period, fund=fund, source_type="voucher",
            source_reference=str(cls.source.public_id), description="Synthetic retained posting",
            source_snapshot={"payload_checksum": checksum, "voucher_case": str(cls.case.public_id)},
            created_by_id=cls.reviewer.pk, created_by_label="Synthetic", status="draft")
        JournalLine.objects.create(entry=cls.entry, sequence=1, account=debit, debit=Decimal("100"))
        JournalLine.objects.create(entry=cls.entry, sequence=2, account=credit, credit=Decimal("100"))
        JournalEntry.objects.filter(pk=cls.entry.pk).update(status="posted", posted_by_id=cls.reviewer.pk,
            posted_at=timezone.now())
        AccountingAuditEvent.objects.create(**owner, entry=cls.entry, action="posted", actor_id=cls.reviewer.pk,
            actor_label="Synthetic", snapshot={"debit": "100.00", "credit": "100.00"})
        VoucherPostingRequest.objects.filter(pk=cls.source.pk).update(accounting_entry_public_id=cls.entry.public_id)
        cls.source.refresh_from_db()

    def inspect(self):
        self.source.refresh_from_db()
        return inspect_recognition(self.source, actor=self.reviewer)

    def test_read_only_exact_binding_and_minimal_http_output(self):
        row = test_grand_attribution.AttributionTests.propose(self)
        with CaptureQueriesContext(connections["default"]) as default, CaptureQueriesContext(connections["finance"]) as finance:
            result = self.inspect()
        self.assertEqual(result["issue"], "")
        self.assertEqual([line.sequence for line in result["lines"]], [1])
        for query in [*default, *finance]:
            self.assertTrue(query["sql"].lstrip().upper().startswith("SELECT"), query["sql"])
        self.client.force_login(self.reviewer)
        url = reverse("inventory_finance:journal-sources", args=[row.public_id])
        response = self.client.get(url)
        self.assertContains(response, "TEST-ASSET")
        self.assertNotContains(response, "TEST-LIABILITY")
        self.assertNotContains(response, "DO-NOT-RENDER")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(url).status_code, 405)
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_owner_and_explicit_ledger_grant_required(self):
        for actor in (self.clerk, self.outsider, self.no_grant, self.viewer):
            with self.subTest(actor=actor.pk), self.assertRaises(PermissionDenied):
                inspect_recognition(self.source, actor=actor)
        self.reviewer.user_permissions.remove(Permission.objects.get(
            content_type__app_label="accounting", codename="view_general_ledger"))
        self.reviewer.is_superuser = True
        self.reviewer.save(update_fields=["is_superuser"])
        with self.assertRaises(PermissionDenied):
            self.inspect()

    def test_nonrecognition_unbound_and_changed_sources_hide_lines(self):
        for changes in ({"kind": "payment"}, {"status": "materialized"},
                        {"accounting_entry_public_id": None}, {"accounting_entry_public_id": uuid4()},
                        {"payload_checksum": "0" * 64}, {"jev_number": "CHANGED"}):
            with self.subTest(changes=changes):
                original = {key: getattr(self.source, key) for key in changes}
                VoucherPostingRequest.objects.filter(pk=self.source.pk).update(**changes)
                result = self.inspect()
                self.assertTrue(result["issue"])
                self.assertEqual(result["lines"], [])
                VoucherPostingRequest.objects.filter(pk=self.source.pk).update(**original)
                self.source.refresh_from_db()

    def test_draft_corrupt_posting_and_active_reversal_hide_lines(self):
        for changes in ({"status": "draft"}, {"posted_by_id": self.clerk.pk},
                        {"source_snapshot": {}}, {"source_reference": "different"}):
            with self.subTest(changes=changes):
                self.entry.refresh_from_db()
                original = {key: getattr(self.entry, key) for key in changes}
                JournalEntry.objects.filter(pk=self.entry.pk).update(**changes)
                self.assertTrue(self.inspect()["issue"])
                JournalEntry.objects.filter(pk=self.entry.pk).update(**original)
        reversal = JournalEntry.objects.create(department_id=self.finance.pk, department_label=self.finance.name,
            reference="REVERSAL", entry_date=self.source.jev_date, period=self.entry.period, fund=self.entry.fund,
            reversal_of=self.entry, created_by_id=self.reviewer.pk, created_by_label="Synthetic")
        self.assertIn("reversal", self.inspect()["issue"])
        JournalEntry.objects.filter(pk=reversal.pk).update(status="voided")
        self.assertEqual(self.inspect()["issue"], "")
        AccountingAuditEvent.objects.filter(entry=self.entry).update(snapshot={"debit": "NaN", "credit": "100"})
        self.assertTrue(self.inspect()["issue"])
