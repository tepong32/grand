from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_attributions as service
from . import test_budget_native_sources as fixtures
from .models import BudgetExpenditureAttribution as Attribution, BudgetExpenditureAttributionHead as Head, ResponsibilityCenter


class BudgetAttributionTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.NativeBudgetSourceTests.setUpTestData.__func__)
    employee = classmethod(fixtures.NativeBudgetSourceTests.employee.__func__)
    make_call = fixtures.NativeBudgetSourceTests.make_call
    make_version = fixtures.NativeBudgetSourceTests.make_version
    add_line = fixtures.NativeBudgetSourceTests.add_line
    add_ceiling = fixtures.NativeBudgetSourceTests.add_ceiling
    grant = fixtures.NativeBudgetSourceTests.grant
    journal = fixtures.NativeBudgetSourceTests.journal
    capture = fixtures.NativeBudgetSourceTests.capture

    def setUp(self):
        fixtures.NativeBudgetSourceTests.setUp(self)
        self.attribute_grant(self.maker, "prepare", "view")
        self.attribute_grant(self.checker, "review", "view")
        self.entry = self.journal("ATTRIBUTION", date(2026, 6, 30), Decimal("100"))

    def attribute_grant(self, actor, *actions):
        actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="accounting",
            codename__in=[f"{action}_budget_attributions" for action in actions]))

    def rows(self, entry=None):
        entry = entry or self.entry
        lines = list(entry.lines.order_by("sequence"))
        return [dict(line_id=lines[0].pk, amount="100", disposition="include", purpose="expense_recognition",
            center_id=self.center.pk, expense_class="MOOE", basis="Retained accepted supplies evidence"),
            dict(line_id=lines[1].pk, amount="100", disposition="exclude", purpose="counterpart",
                 basis="Balancing counterpart, not a second expenditure")]

    def propose(self, rows=None, proposals=None):
        return service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 1, 1), period_end=date(2026, 6, 30),
            expected_source_checksum=self.capture()["checksum"],
            proposals=proposals or [dict(entry_id=self.entry.pk, expected_latest=0, allocations=rows or self.rows())],
            reason="Explicit office and object review", evidence_reference="SYN-ATTRIBUTION-REVIEW")

    def review(self, records, actor=None, approve=True):
        return service.review_batch(batch_id=records[0].batch_id, actor=actor or self.checker,
            approve=approve, note="Independent source and allocation review")

    def test_independent_batch_approval_joins_one_coherent_capture(self):
        before = self.capture()
        records = self.propose()
        self.assertEqual(Head.objects.count(), 0)
        self.review(records)
        with CaptureQueriesContext(connections["finance"]) as queries:
            after = self.capture()
            rows = service.reviewed_allocations(after)
        self.assertEqual(len(queries), 1)
        self.assertEqual(rows[0]["status"], "reviewed")
        self.assertEqual(rows[0]["allocations"][0]["signed_amount"], "100.00")
        self.assertNotEqual(before["checksum"], after["checksum"])
        self.assertEqual(service.reviewed_allocations(before)[0]["status"], "unreviewed")
        record = Attribution.objects.get(pk=records[0].pk)
        service.verify(record)
        record.reason = "Rewrite historical basis"
        with self.assertRaises(ValidationError):
            record.save()

    def test_complete_partition_prevents_two_offices_claiming_the_same_amount(self):
        second = ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code="ATTR-OTHER", name="Other office",
            office_id=self.budget_office.pk)
        rows = self.rows()
        duplicate = dict(rows[0], center_id=second.pk)
        with self.assertRaises(ValidationError):
            self.propose([*rows, duplicate])
        self.assertEqual(Attribution.objects.count(), 0)
        rows[0]["amount"] = "60"
        duplicate["amount"] = "40"
        self.review(self.propose([*rows, duplicate]))
        included = [row for row in service.reviewed_allocations(self.capture())[0]["allocations"] if row["disposition"] == "include"]
        self.assertEqual(sum(Decimal(row["signed_amount"]) for row in included), Decimal("100"))
        self.assertEqual({row["center_id"] for row in included}, {self.center.pk, second.pk})

    def test_stale_proposal_batch_is_atomic_and_can_be_returned(self):
        other = self.journal("OTHER", date(2026, 6, 30), Decimal("100"))
        first = self.propose(proposals=[dict(entry_id=entry.pk, expected_latest=0, allocations=self.rows(entry))
                                       for entry in (self.entry, other)])
        newer = self.propose(proposals=[dict(entry_id=other.pk, expected_latest=1, allocations=self.rows(other))])
        with self.assertRaises(ValidationError):
            self.review(first)
        self.assertEqual(Head.objects.count(), 0)
        self.assertEqual(Attribution.objects.filter(batch_id=first[0].batch_id, status="submitted").count(), 2)
        self.review(first, approve=False)
        self.review(newer)
        self.assertEqual(Head.objects.count(), 1)

    def test_self_review_uat_and_stale_submission_denied(self):
        records = self.propose()
        self.attribute_grant(self.maker, "review")
        with self.assertRaises(ValidationError):
            self.review(records, actor=self.maker)
        with self.assertRaises(ValidationError):
            self.propose()
        group, _ = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)
        self.checker.groups.add(group)
        with self.assertRaises(PermissionDenied):
            self.review(records)
        self.assertEqual(Head.objects.count(), 0)

    def test_unresolved_remains_explicit_and_evidence_tampering_fails(self):
        rows = self.rows()
        rows[0] = dict(line_id=rows[0]["line_id"], amount="100", disposition="unresolved",
                       purpose="unresolved", basis="Office and purpose need evidence")
        self.review(self.propose(rows))
        captured = self.capture()
        self.assertEqual(service.reviewed_allocations(captured)[0]["allocations"][0]["disposition"], "unresolved")
        record = Attribution.objects.get()
        broken = deepcopy(record.allocations)
        broken[0]["amount"] = "200.00"
        Attribution.objects.filter(pk=record.pk).update(allocations=broken)
        with self.assertRaises(ValidationError):
            service.reviewed_allocations(self.capture())
