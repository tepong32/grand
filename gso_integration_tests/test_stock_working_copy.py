import csv
from io import StringIO

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.models import StockMovement
from . import test_stock_movement_history as fixture


class StockWorkingCopyTests(TestCase):
    databases = {"default", "finance"}
    movement = staticmethod(fixture.StockMovementHistoryTests.movement)

    @classmethod
    def setUpTestData(cls):
        fixture.StockMovementHistoryTests.setUpTestData.__func__(cls)

    def copy(self, data=None):
        return self.client.get(reverse("inventory:stock-working-copy"), data or {})

    def test_complete_filtered_copy_matches_csv_even_when_opened_from_later_page(self):
        self.client.force_login(self.clerk)
        for number in range(52):
            self.movement(self.item, "issue", f"Printable issue {number}", self.office.pk)
        response = self.copy({"kind": "issue", "page": 2})
        self.assertEqual(response.status_code, 200)
        rows = response.context["movements"]
        self.assertEqual(len(rows), 54)
        csv_response = self.client.get(reverse("inventory:stock-export"), {"kind": "issue"})
        exported = list(csv.reader(StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertEqual([str(m.public_id) for m in rows], [r[-1] for r in exported[1:]])
        self.assertContains(response, "Printable issue 0")
        self.assertContains(response, "Printable issue 51")
        self.assertNotContains(response, "Opening delivery")
        self.assertNotContains(response, "Foreign owned issue")

    def test_export_authority_is_required_independently_from_read_and_uat(self):
        self.assertEqual(self.copy().status_code, 302)
        for actor in (self.reader, self.no_grant, self.super_no_grant):
            self.client.force_login(actor)
            self.assertEqual(self.copy().status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.copy().status_code, 200)
        self.assertEqual(self.client.post(reverse("inventory:stock-working-copy")).status_code, 405)
        grant = Permission.objects.get(content_type__app_label="inventory", codename="export_stock_register")
        self.clerk.user_permissions.remove(grant)
        self.client.force_login(self.clerk)
        self.assertEqual(self.copy().status_code, 403)
        self.assertNotContains(self.client.get(reverse("inventory:stock-history")), "Open printable copy")
        self.clerk.user_permissions.add(grant)
        self.clerk.user_permissions.remove(Permission.objects.get(content_type__app_label="inventory", codename="view_consumableitem"))
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(reverse("inventory:stock-history")).status_code, 403)
        response = self.copy()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="' + reverse("inventory:stock-history"))
        self.assertNotContains(response, 'href="' + reverse("inventory:consumable-list"))

    def test_invalid_filter_does_not_print_unfiltered_rows(self):
        self.client.force_login(self.clerk)
        for query in ({"kind": "unknown"}, {"from_date": "bad"},
                      {"from_date": "2026-10-02", "to_date": "2026-10-01"}):
            with self.subTest(query=query):
                response = self.copy(query)
                self.assertEqual(response.status_code, 400)
                self.assertNotContains(response, "Office issue", status_code=400)
                self.assertNotIn("Content-Disposition", response)

    def test_copy_is_private_read_only_and_keeps_its_filter_return_path(self):
        self.client.force_login(self.clerk)
        before = list(StockMovement.objects.values())
        with CaptureQueriesContext(connections["finance"]) as finance:
            response = self.copy({"kind": "issue"})
        self.assertEqual(len(finance), 0)
        self.assertEqual(list(StockMovement.objects.values()), before)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertContains(response, reverse("inventory:stock-history") + "?kind=issue")
        self.assertContains(self.client.get(reverse("inventory:stock-history"), {"kind": "issue"}),
                            reverse("inventory:stock-working-copy") + "?kind=issue")

    def test_source_text_is_escaped_and_empty_selection_is_not_a_stock_certification(self):
        self.client.force_login(self.clerk)
        row = self.movement(self.item, "issue", "<script>unsafe()</script>", self.office.pk)
        response = self.copy({"kind": "issue"})
        self.assertContains(response, "&lt;script&gt;unsafe()&lt;/script&gt;")
        self.assertNotContains(response, "<script>unsafe()</script>")
        self.assertContains(response, str(row.public_id))
        self.assertContains(response, "Not an official RSMI/SSMI")
        self.assertContains(response, "GRAND recording dates")
        self.assertNotContains(response, "Certified Correct")
        empty = self.copy({"kind": "return"})
        self.assertContains(empty, "does not certify zero stock")
