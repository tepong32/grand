import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import ConsumableItem, StockMovement
from inventory.supply_draft_sources import sign_selection
from inventory.count_drafts import TOKEN_SALT as COUNT_SALT
from profiles.models import EmployeeProfile
from . import test_stock_movement_history as fixture


class IssueDraftTests(TestCase):
    databases = {"default", "finance"}
    movement = staticmethod(fixture.StockMovementHistoryTests.movement)

    @classmethod
    def setUpTestData(cls):
        fixture.StockMovementHistoryTests.setUpTestData.__func__(cls)

    def start(self, **query):
        return self.client.get(reverse("inventory:issue-rsmi-preparation"), {"kind": "issue", **query})

    @staticmethod
    def entries(response, **changes):
        return {**response.context["lines"].data.dict(),
                "issue_source_token": response.context["issue_source_token"], **changes}

    def preview(self, data):
        return self.client.post(reverse("inventory:issue-rsmi-preparation"), data)

    def test_copy_original_issues_keeps_unknowns_recorded_costs_and_full_recipient(self):
        StockMovement.objects.filter(pk=self.issue.pk).update(unit_cost=Decimal("0.00"),
            department_label="D" * 160, recipient="R" * 160)
        self.movement(self.item, "return", "Returned supplies", self.office.pk)
        self.movement(self.item, "adjustment_out", "Adjustment", self.office.pk)
        self.client.force_login(self.clerk)
        start = self.start()
        self.assertEqual(start.status_code, 200)
        self.assertEqual({s["id"] for s in start.context["issue_sources"]}, {self.issue.pk, self.other_issue.pk})
        self.assertFalse(start.context["ready"])
        self.movement(self.item, "issue", "Later issue", self.office.pk)
        result = self.preview(self.entries(start))
        self.assertTrue(result.context["ready"])
        rows = result.context["print_lines"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["unit_cost"], 0)
        self.assertIsNone(rows[1]["unit_cost"])
        self.assertEqual(rows[0]["recipient_office"], "D" * 160 + " · " + "R" * 160)
        for row in rows:
            self.assertEqual(row["quantity"], 1)
            self.assertIsNone(row["amount"])
            self.assertIsNone(row["source_date"])
            self.assertFalse(row["stock_number"])
            self.assertIn("Recorded in GRAND", row["remarks"])
        self.assertIsNone(result.context["details"]["period_start"])
        self.assertIsNone(result.context["details"]["period_end"])
        self.assertContains(result, "Returns and adjustments are not netted")
        self.assertContains(result, "Recorded unit costs do not establish approved Accounting valuation")
        self.assertNotContains(result, "Foreign owned issue")
        self.assertIn("no-store", result["Cache-Control"])

    @override_settings(TIME_ZONE="Asia/Manila")
    def test_search_and_local_date_selection_match_history_csv_copy_and_starter(self):
        local = ZoneInfo("Asia/Manila")
        StockMovement.objects.filter(pk=self.issue.pk).update(occurred_at=datetime(2026, 10, 1, 23, 59, 59, tzinfo=local))
        StockMovement.objects.filter(pk=self.other_issue.pk).update(occurred_at=datetime(2026, 10, 2, 0, 0, tzinfo=local))
        self.client.force_login(self.clerk)
        query = {"kind": "issue", "q": "Office issue", "from_date": "2026-10-01", "to_date": "2026-10-01"}
        history = self.client.get(reverse("inventory:stock-history"), query)
        self.assertEqual([row.pk for row in history.context["page"]], [self.issue.pk])
        copy = self.client.get(reverse("inventory:stock-working-copy"), query)
        self.assertEqual([row.pk for row in copy.context["movements"]], [self.issue.pk])
        self.assertContains(copy, "Supply item / source reference search: Office issue")
        exported = self.client.get(reverse("inventory:stock-export"), query)
        rows = list(csv.reader(StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual([row[-1] for row in rows[1:]], [str(self.issue.public_id)])
        start = self.start(**query)
        self.assertEqual([s["id"] for s in start.context["issue_sources"]], [self.issue.pk])
        self.assertIn("2026-10-01T23:59:59+08:00", start.context["issue_sources"][0]["recorded_at"])
        by_item = self.start(q=self.item.name)
        self.assertEqual(len(by_item.context["issue_sources"]), 2)
        self.client.force_login(self.reader)
        self.assertFalse(self.client.get(reverse("inventory:stock-history"), {"q": "Private other"}).context["page"].object_list)

    def test_invalid_filters_and_oversized_cohorts_do_not_silently_select_other_rows(self):
        self.client.force_login(self.clerk)
        for selection in ({"kind": ""}, {"kind": "receipt"}, {"kind": "return"}, {"kind": "bad"},
                          {"from_date": "bad"}, {"from_date": "2026-10-02", "to_date": "2026-10-01"},
                          {"q": "z" * 101}, {"q": "No matching reference"}):
            result = self.start(**selection)
            self.assertEqual(result.status_code, 400)
            self.assertFalse(result.context["ready"])
            self.assertFalse(result.context["issue_sources"])
        for i in range(48):
            self.movement(self.item, "issue", f"Batch {i}", self.office.pk)
        self.assertEqual(len(self.start().context["lines"].forms), 50)
        self.movement(self.item, "issue", "Batch overflow", self.office.pk)
        result = self.start(page=2)
        self.assertContains(result, "More than 50 issues match", status_code=400)
        self.assertFalse(result.context["issue_sources"])
        self.assertEqual(len(self.start(q="Batch").context["lines"].forms), 49)
        for route in ("stock-history", "stock-working-copy", "stock-export"):
            self.assertEqual(self.client.get(reverse("inventory:" + route), {"q": "z" * 101}).status_code, 400)

    def test_tokens_source_mutation_and_permission_changes_fail_closed(self):
        self.client.force_login(self.clerk)
        start = self.start()
        values = self.entries(start, **{"header-office": "Preserve office", "lines-0-description": "Keep draft"})
        foreign_token = sign_selection(self.clerk, start.context["issue_sources"], salt=COUNT_SALT)
        for token in ("", "x" * 8001, values["issue_source_token"] + "x", foreign_token):
            result = self.preview({**values, "issue_source_token": token})
            self.assertEqual(result.status_code, 400)
            self.assertContains(result, "Keep draft", status_code=400)
            self.assertFalse(result.context["ready"])
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 9 * 3600):
            self.assertEqual(self.preview(values).status_code, 400)
        self.client.force_login(self.viewer)
        self.assertEqual(self.preview(values).status_code, 400)
        self.client.force_login(self.clerk)
        StockMovement.objects.filter(pk=self.issue.pk).update(reference="Changed source")
        self.assertEqual(self.preview(values).status_code, 400)
        StockMovement.objects.filter(pk=self.issue.pk).update(reference=self.issue.reference)
        for codename in ("view_consumableitem", "export_stock_register"):
            grant = Permission.objects.get(content_type__app_label="inventory", codename=codename)
            self.clerk.user_permissions.remove(grant)
            self.assertEqual(self.start().status_code, 403)
            self.assertEqual(self.preview(values).status_code, 403)
            self.clerk.user_permissions.add(grant)
        EmployeeProfile.objects.filter(user=self.clerk).update(assigned_department=self.office)
        self.assertEqual(self.preview(values).status_code, 403)
        EmployeeProfile.objects.filter(user=self.clerk).update(assigned_department=self.gso)
        ConsumableItem.objects.filter(pk=self.item.pk).update(department_id=self.other.pk)
        self.assertEqual(self.preview(values).status_code, 400)

    def test_edits_add_and_exclude_keep_originals_escaped_without_stock_or_finance_writes(self):
        StockMovement.objects.filter(pk=self.issue.pk).update(reference="<script>unsafe()</script>")
        before = list(StockMovement.objects.values())
        self.client.force_login(self.clerk)
        with CaptureQueriesContext(connections["finance"]) as finance, CaptureQueriesContext(connections["default"]) as default:
            start = self.start()
            added = self.preview(self.entries(start, action="add_lines", **{"lines-0-quantity": "-1"}))
            self.assertEqual(len(added.context["lines"].forms), 7)
            self.assertFalse(added.context["ready"])
            values = self.entries(added, action="preview", **{"lines-0-DELETE": "on"})
            result = self.preview(values)
            self.assertTrue(result.context["ready"])
            self.assertContains(result, "&lt;script&gt;unsafe()&lt;/script&gt;")
            self.assertNotContains(result, "<script>unsafe()</script>")
            self.assertEqual(result.context["issue_sources"][0]["quantity"], "1.000")
            values.pop("lines-0-DELETE")
            self.assertFalse(self.preview(values).context["ready"])
            values["lines-0-quantity"] = "3"
            self.assertEqual(self.preview(values).context["print_lines"][0]["quantity"], 3)
        self.assertEqual(len(finance), 0)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in default))
        self.assertEqual(before, list(StockMovement.objects.values()))

    def test_entry_method_csrf_and_read_export_boundaries(self):
        url = reverse("inventory:issue-rsmi-preparation")
        self.assertEqual(self.start().status_code, 302)
        self.assertEqual(self.preview({}).status_code, 302)
        for actor in (self.reader, self.no_grant, self.super_no_grant):
            self.client.force_login(actor)
            self.assertEqual(self.start().status_code, 403)
            self.assertEqual(self.preview({}).status_code, 403)
        self.client.force_login(self.viewer)
        self.assertTrue(self.preview(self.entries(self.start())).context["ready"])
        self.assertContains(self.client.get(reverse("inventory:stock-history"), {"kind": "issue"}), url)
        self.assertNotContains(self.client.get(reverse("inventory:stock-history"), {"kind": "return"}), url)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.viewer)
        self.assertEqual(protected.post(url, self.entries(self.start())).status_code, 403)
        self.assertEqual(self.client.put(url).status_code, 405)
