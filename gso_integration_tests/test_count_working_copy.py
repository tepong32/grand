from uuid import uuid4

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import ConsumableItem, StockCount, StockCountEvent, StockCountEvidence, StockMovement
from inventory.stock_counts import stock_basis
from . import test_grand_stock_authority as fixture


class CountWorkingCopyTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        fixture.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        cls.other_item = ConsumableItem.objects.create(department_id=cls.other.pk, name="Foreign count item", unit="box")

    def observation(self, number=0, *, item=None, status="approved", reference="COUNT-SHEET", quantity="0.000"):
        item = item or self.item
        count = StockCount.objects.create(item=item, public_id=uuid4(), counted_on=timezone.localdate(),
            quantity=quantity, basis={**stock_basis(item), "balance": "2.125", "name": "Pinned supply name", "unit": "ream"},
            reference=reference, note=f"Observation {number}", status=status, recorded_by=self.clerk,
            decided_by=self.clerk if status != "pending" else None,
            decided_at=timezone.now() if status != "pending" else None, decision_note="Retained decision")
        return count

    def copy(self, query=None):
        return self.client.get(reverse("inventory:stock-count-working-copy"), query or {})

    def test_complete_selection_matches_every_list_page_without_collapsing_repeated_items(self):
        self.client.force_login(self.clerk)
        rows = [self.observation(i) for i in range(27)]
        self.observation(90, item=self.other_item)
        self.observation(91, status="cancelled", reference="Different sheet")
        query = {"status": "approved", "q": "COUNT-SHEET"}
        listed = self.client.get(reverse("inventory:stock-count-list"), {**query, "page": 2})
        self.assertEqual(len(listed.context["page"]), 2)
        response = self.copy({**query, "page": 2})
        expected = list(StockCount.objects.filter(pk__in=[r.pk for r in rows]).values_list("pk", flat=True))
        self.assertEqual([r.pk for r in response.context["counts"]], expected)
        self.assertEqual(len(response.context["counts"]), 27)
        for row in rows:
            self.assertContains(response, str(row.public_id))
        self.assertNotContains(response, "Foreign count item")
        self.assertNotContains(response, "Observation 90")
        self.assertNotContains(response, "Different sheet")
        self.assertContains(listed, reverse("inventory:stock-count-working-copy") + "?status=approved&amp;q=COUNT-SHEET")

    def test_requires_both_existing_read_and_export_grants_and_fresh_office_scope(self):
        self.assertEqual(self.copy().status_code, 302)
        for actor in (self.no_grant, self.super_no_grant):
            self.client.force_login(actor)
            self.assertEqual(self.copy().status_code, 403)
        own = self.observation(item=self.other_item)
        hidden = self.observation(status="cancelled")
        self.client.force_login(self.outsider)
        scoped = self.copy({"status": "all"})
        self.assertEqual(scoped.status_code, 200)
        self.assertContains(scoped, str(own.public_id))
        self.assertNotContains(scoped, str(hidden.public_id))
        read = Permission.objects.get(content_type__app_label="inventory", codename="view_consumableitem")
        export = Permission.objects.get(content_type__app_label="inventory", codename="export_stock_register")
        self.client.force_login(self.clerk)
        self.clerk.user_permissions.remove(export)
        self.assertEqual(self.copy().status_code, 403)
        self.assertNotContains(self.client.get(reverse("inventory:stock-count-list")), "Open printable copy")
        self.clerk.user_permissions.add(export)
        self.clerk.user_permissions.remove(read)
        self.assertEqual(self.copy().status_code, 403)
        self.clerk.user_permissions.add(read)
        self.assertEqual(self.copy().status_code, 200)
        count = self.observation(status="pending")
        for route, args in (("stock-count-list", []), ("stock-count-detail", [count.pk])):
            page = self.client.get(reverse("inventory:" + route, args=args))
            self.assertEqual(page.status_code, 200)
            self.assertNotContains(page, 'href="' + reverse("inventory:dashboard"))
            self.assertContains(page, 'href="' + reverse("department_dashboard"))
        self.item.department_id = self.other.pk
        self.item.save(update_fields=["department_id"])
        self.assertNotContains(self.copy(), str(count.public_id))

    def test_uat_is_read_only_copy_preserves_sources_and_makes_no_finance_queries(self):
        self.observation(status="pending")
        self.client.force_login(self.viewer)
        models = (ConsumableItem, StockMovement, StockCount, StockCountEvent, StockCountEvidence)
        before = [list(model.objects.values()) for model in models]
        with CaptureQueriesContext(connections["finance"]) as finance:
            response = self.copy()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(finance), 0)
        self.assertEqual([list(model.objects.values()) for model in models], before)
        self.assertEqual(self.client.post(reverse("inventory:stock-count-working-copy")).status_code, 405)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_unknown_status_fails_closed_on_list_and_copy_and_retains_search(self):
        self.observation()
        self.client.force_login(self.clerk)
        for route in ("stock-count-list", "stock-count-working-copy"):
            response = self.client.get(reverse("inventory:" + route), {"status": "approevd", "q": "COUNT-SHEET"})
            self.assertEqual(response.status_code, 400)
            self.assertNotContains(response, "Observation 0", status_code=400)
            self.assertNotContains(response, "Open printable copy", status_code=400)
        response = self.copy({"status": "all", "q": "COUNT-SHEET & <x>"})
        self.assertContains(response, "status=all&amp;q=COUNT-SHEET+%26+%3Cx%3E")

    def test_pinned_facts_zero_and_cancelled_status_are_distinct_and_text_is_escaped(self):
        first = self.observation(status="pending", reference="<script>unsafe()</script>")
        self.observation(2, status="cancelled", quantity="3.000")
        self.client.force_login(self.clerk)
        response = self.copy({"status": "all"})
        self.assertContains(response, "Pinned supply name")
        self.assertContains(response, "2.125 ream")
        self.assertContains(response, "0.000 ream")
        self.assertContains(response, "-2.125 ream")
        self.assertContains(response, "Awaiting independent review")
        self.assertContains(response, "Cancelled")
        self.assertContains(response, "&lt;script&gt;unsafe()&lt;/script&gt;")
        self.assertNotContains(response, "<script>unsafe()</script>")
        self.assertContains(response, str(first.item.public_id))
        self.assertContains(response, "Not an official RPCI")
        self.assertNotContains(response, "Certified Correct")
        self.assertContains(response, "does not establish a common inventory date")

    def test_empty_selection_does_not_certify_zero_stock(self):
        self.client.force_login(self.clerk)
        response = self.copy({"status": "approved"})
        self.assertContains(response, "No count records match")
        self.assertContains(response, "does not certify zero stock")
