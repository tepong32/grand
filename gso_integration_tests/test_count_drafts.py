from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import ConsumableItem, StockCount, StockCountEvent, StockCountEvidence, StockMovement
from inventory.stock_counts import stock_basis
from profiles.models import EmployeeProfile
from . import test_grand_stock_authority as fixture


class CountDraftTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        fixture.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        cls.other.name, cls.other.slug = "Engineering", "engineering"
        cls.other.save(update_fields=["name", "slug"])
        cls.foreign = ConsumableItem.objects.create(department_id=cls.other.pk, name="Foreign item", unit="box")

    def observation(self, *, item=None, status="approved", reference="COUNT-SHEET", quantity="0.000"):
        item = item or self.item
        return StockCount.objects.create(item=item, counted_on=timezone.localdate(), quantity=quantity,
            basis={**stock_basis(item), "balance": "2.125", "name": "Original observation name"},
            reference=reference, note="Retained original observation", status=status,
            recorded_by=self.clerk, decided_by=self.no_grant if status == "approved" else None,
            decided_at=timezone.now() if status == "approved" else None, state_version=3)

    def start(self, **query):
        return self.client.get(reverse("inventory:count-rpci-preparation"),
                               {"status": "approved", "q": "COUNT-SHEET", **query})

    @staticmethod
    def entries(response, **changes):
        return {**response.context["lines"].data.dict(),
                "count_source_token": response.context["count_source_token"], **changes}

    def preview(self, data):
        return self.client.post(reverse("inventory:count-rpci-preparation"), data)

    def test_complete_selected_cohort_preserves_pinned_facts_and_unknowns(self):
        counts = [self.observation(quantity=str(i)) for i in range(27)]
        self.observation(item=self.foreign)
        self.observation(status="pending")
        self.observation(status="cancelled")
        self.observation(reference="OTHER-SHEET")
        self.client.force_login(self.clerk)
        response = self.start(page=2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["lines"].forms), 27)
        self.assertEqual({s["id"] for s in response.context["count_sources"]}, {c.pk for c in counts})
        self.assertFalse(response.context["header"].initial)
        self.assertFalse(response.context["ready"])
        values = self.entries(response)
        # Later matching observations do not silently expand a previously selected cohort.
        self.observation(quantity="99")
        preview = self.preview(values)
        self.assertTrue(preview.context["ready"])
        self.assertEqual(len(preview.context["print_lines"]), 27)
        self.assertEqual({r["counted_quantity"] for r in preview.context["print_lines"]}, set(map(Decimal, range(27))))
        for row in preview.context["print_lines"]:
            self.assertEqual(row["article"], "Original observation name")
            self.assertEqual(row["card_quantity"], Decimal("2.125"))
            self.assertIsNone(row["unit_value"])
            self.assertIsNone(row["difference_value"])
            self.assertFalse(row["stock_number"])
        self.assertIsNone(preview.context["details"]["as_of"])
        self.assertContains(preview, "Starting count records")
        self.assertContains(preview, "not establish a common inventory date")
        self.assertContains(preview, str(counts[0].public_id))
        self.assertIn("no-store", preview["Cache-Control"])

    def test_source_changes_invalid_tokens_and_expiry_retain_entries_without_print(self):
        count = self.observation()
        self.client.force_login(self.clerk)
        response = self.start()
        values = self.entries(response, **{"header-office": "Keep entered office", "lines-0-description": "My draft"})
        for token in ("", values["count_source_token"] + "x", "x" * 8001):
            result = self.preview({**values, "count_source_token": token})
            self.assertEqual(result.status_code, 400)
            self.assertContains(result, "Keep entered office", status_code=400)
            self.assertFalse(result.context["ready"])
            self.assertNotContains(result, 'onclick="window.print()"', status_code=400)
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 9 * 3600):
            self.assertEqual(self.preview(values).status_code, 400)
        self.client.force_login(self.viewer)
        self.assertEqual(self.preview(values).status_code, 400)
        self.client.force_login(self.clerk)
        for change in ({"note": "Changed original"}, {"status": "cancelled"}, {"state_version": 4}):
            StockCount.objects.filter(pk=count.pk).update(**change)
            result = self.preview(values)
            self.assertEqual(result.status_code, 400)
            self.assertFalse(result.context["ready"])
            self.assertContains(result, "My draft", status_code=400)
            StockCount.objects.filter(pk=count.pk).update(note=count.note, status=count.status, state_version=count.state_version)

    def test_current_permissions_office_and_item_ownership_rechecked_on_every_request(self):
        self.observation()
        url = reverse("inventory:count-rpci-preparation")
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(url).status_code, 302)
        for actor in (self.no_grant, self.super_no_grant, self.outsider):
            self.client.force_login(actor)
            self.assertEqual(self.start().status_code, 403)
            self.assertEqual(self.preview({}).status_code, 403)
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            values = self.entries(self.start())
            self.assertTrue(self.preview(values).context["ready"])
            for codename in ("export_stock_register", "view_consumableitem"):
                grant = Permission.objects.get(content_type__app_label="inventory", codename=codename)
                actor.user_permissions.remove(grant)
                self.assertEqual(self.start().status_code, 403)
                self.assertEqual(self.preview(values).status_code, 403)
                actor.user_permissions.add(grant)
        self.client.force_login(self.clerk)
        values = self.entries(self.start())
        EmployeeProfile.objects.filter(user=self.clerk).update(assigned_department=self.other)
        self.assertEqual(self.preview(values).status_code, 403)
        EmployeeProfile.objects.filter(user=self.clerk).update(assigned_department=self.gso)
        ConsumableItem.objects.filter(pk=self.item.pk).update(department_id=self.other.pk)
        result = self.preview(values)
        self.assertEqual(result.status_code, 400)
        self.assertFalse(result.context["count_sources"])

    def test_filter_and_cohort_bounds_reject_incomplete_or_empty_selection(self):
        self.client.force_login(self.clerk)
        for status in ("all", "pending", "cancelled", "unknown"):
            self.assertEqual(self.start(status=status).status_code, 400)
        self.assertEqual(self.start().status_code, 400)
        for i in range(50):
            self.observation()
        response = self.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["lines"].forms), 50)
        self.observation()
        result = self.start()
        self.assertContains(result, "More than 50 counts match", status_code=400)
        self.assertFalse(result.context["count_sources"])

    def test_edit_add_exclude_and_preview_do_not_rewrite_sources_or_touch_finance(self):
        self.observation(reference="COUNT-SHEET <script>unsafe()</script>")
        models = (ConsumableItem, StockMovement, StockCount, StockCountEvent, StockCountEvidence)
        before = [list(model.objects.values()) for model in models]
        self.client.force_login(self.clerk)
        with CaptureQueriesContext(connections["finance"]) as finance, CaptureQueriesContext(connections["default"]) as default:
            response = self.start()
            added = self.preview(self.entries(response, action="add_lines", **{"lines-0-counted_quantity": "-1"}))
            self.assertEqual(len(added.context["lines"].forms), 6)
            self.assertFalse(added.context["ready"])
            values = self.entries(added, action="preview", **{"lines-0-DELETE": "on", "lines-1-article": "Supplied addition"})
            result = self.preview(values)
            self.assertTrue(result.context["ready"])
            self.assertEqual(result.context["print_lines"][0]["article"], "Supplied addition")
            self.assertContains(result, "&lt;script&gt;unsafe()&lt;/script&gt;")
            self.assertNotContains(result, "<script>unsafe()</script>")
            values.pop("lines-0-DELETE")
            self.assertFalse(self.preview(values).context["ready"])
            values["lines-0-counted_quantity"] = "1"
            result = self.preview(values)
            self.assertTrue(result.context["ready"])
            self.assertEqual(result.context["print_lines"][0]["counted_quantity"], 1)
            self.assertEqual(result.context["count_sources"][0]["quantity"], "0.000")
        self.assertEqual(len(finance), 0)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in default))
        self.assertEqual(before, [list(model.objects.values()) for model in models])

    def test_navigation_csrf_and_method_boundaries(self):
        self.observation()
        self.client.force_login(self.clerk)
        url = reverse("inventory:count-rpci-preparation")
        for status in ("pending", "all", "cancelled"):
            self.assertNotContains(self.client.get(reverse("inventory:stock-count-list"), {"status": status}), url)
        self.assertContains(self.client.get(reverse("inventory:stock-count-list"), {"status": "approved"}), url)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.clerk)
        self.assertEqual(protected.post(url, self.entries(self.start())).status_code, 403)
        self.assertEqual(self.client.put(url).status_code, 405)
