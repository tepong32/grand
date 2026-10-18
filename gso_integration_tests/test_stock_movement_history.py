"""Clerks can select the same retained stock rows on screen and in CSV."""
import csv
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.models import ConsumableItem, StockMovement
from departments.models import Department
from profiles.models import EmployeeProfile
from . import test_grand_stock_authority


class StockMovementHistoryTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_stock_authority.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        cls.office = Department.objects.create(name="Health Office", slug="stock-history-health")
        cls.reader = get_user_model().objects.create_user(username="stock-history-reader", email="stock-reader@example.test")
        EmployeeProfile.objects.filter(user=cls.reader).update(assigned_department=cls.office)
        cls.reader.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("view_consumableitem", "export_stock_register")))
        cls.foreign = ConsumableItem.objects.create(department_id=cls.other.pk, name="Other office stock", unit="box")
        cls.receipt = cls.movement(cls.item, "receipt", "Opening delivery")
        cls.issue = cls.movement(cls.item, "issue", "Office issue", cls.office.pk)
        cls.other_issue = cls.movement(cls.item, "issue", "Private other recipient", cls.gso.pk)
        cls.foreign_issue = cls.movement(cls.foreign, "issue", "Foreign owned issue", cls.gso.pk)

    @staticmethod
    def movement(item, kind, reference, department_id=None, **extra):
        inbound = kind != "issue"
        return StockMovement.objects.create(item=item, kind=kind, quantity="1.000",
            signed_quantity="1.000" if inbound else "-1.000", reference=reference,
            department_id=department_id, department_label="Receiving office" if department_id else "",
            **extra)

    def history(self, data=None):
        return self.client.get(reverse("inventory:stock-history"), data or {})

    def exported(self, data=None):
        return self.client.get(reverse("inventory:stock-export"), data or {})

    def test_owner_and_department_views_keep_existing_visibility_without_finance_queries(self):
        self.client.force_login(self.clerk)
        before = list(StockMovement.objects.values())
        with CaptureQueriesContext(connections["finance"]) as finance:
            response = self.history()
        self.assertEqual(len(finance), 0)
        self.assertEqual({m.pk for m in response.context["page"]}, {self.receipt.pk, self.issue.pk, self.other_issue.pk})
        self.assertNotContains(response, "Foreign owned issue")
        # An ordinary department reader sees its own movements, not all movements of a shared item.
        self.client.force_login(self.reader)
        response = self.history()
        self.assertEqual([m.pk for m in response.context["page"]], [self.issue.pk])
        self.assertNotContains(response, "Private other recipient")
        self.assertNotContains(response, "Export selected movements")
        self.assertEqual(self.exported().status_code, 403)
        self.assertEqual(list(StockMovement.objects.values()), before)

    @override_settings(TIME_ZONE="Asia/Manila")
    def test_recorded_date_filters_include_both_local_boundaries(self):
        self.client.force_login(self.clerk)
        local = ZoneInfo("Asia/Manila")
        for movement, instant in ((self.receipt, datetime(2026, 10, 1, 0, 0, tzinfo=local)),
                                  (self.issue, datetime(2026, 10, 1, 23, 59, 59, 999999, tzinfo=local)),
                                  (self.other_issue, datetime(2026, 10, 2, 0, 0, tzinfo=local))):
            StockMovement.objects.filter(pk=movement.pk).update(occurred_at=instant)
        selection = {"from_date": "2026-10-01", "to_date": "2026-10-01"}
        response = self.history(selection)
        self.assertEqual({m.pk for m in response.context["page"]}, {self.receipt.pk, self.issue.pk})
        response = self.history({**selection, "kind": "issue"})
        self.assertEqual([m.pk for m in response.context["page"]], [self.issue.pk])
        rows = list(csv.reader(StringIO(self.exported({**selection, "kind": "issue"}).content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][-1], str(self.issue.public_id))

    def test_invalid_selection_fails_closed_on_screen_and_export(self):
        self.client.force_login(self.clerk)
        for selection in ({"kind": "invented"}, {"from_date": "not-a-date"},
                          {"from_date": "2026-10-02", "to_date": "2026-10-01"}):
            with self.subTest(selection=selection):
                exported = self.exported(selection)
                self.assertEqual(exported.status_code, 400)
                screen = self.history(selection)
                self.assertEqual(screen.status_code, 400)
                self.assertNotContains(screen, "Office issue", status_code=400)
                self.assertEqual(exported.status_code, 400)
                self.assertNotIn("Content-Disposition", exported)
                self.assertNotIn(str(self.issue.public_id), exported.content.decode())

    def test_paging_preserves_selection_and_csv_includes_every_selected_row(self):
        self.client.force_login(self.clerk)
        for number in range(52):
            self.movement(self.item, "issue", f"Batch {number}", self.other.pk)
        response = self.history({"kind": "issue"})
        self.assertEqual(response.context["page"].paginator.count, 54)
        self.assertEqual(len(response.context["page"]), 50)
        self.assertContains(response, "kind=issue&amp;page=2")
        second = self.history({"kind": "issue", "page": 2})
        self.assertEqual(len(second.context["page"]), 4)
        rows = list(csv.reader(StringIO(self.exported({"kind": "issue", "page": 2}).content.decode("utf-8-sig"))))
        ids = {row[-1] for row in rows[1:]}
        self.assertEqual(len(rows), 55)
        self.assertEqual(ids, {str(m.public_id) for m in list(response.context["page"]) + list(second.context["page"])})

    def test_explicit_read_and_export_grants_and_uat_read_only_are_preserved(self):
        self.assertEqual(self.history().status_code, 302)
        for actor in (self.no_grant, self.super_no_grant):
            self.client.force_login(actor)
            self.assertEqual(self.history().status_code, 403)
            self.assertEqual(self.exported().status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.history().status_code, 200)
        self.assertEqual(self.exported({"kind": "issue"}).status_code, 200)
        self.assertEqual(self.client.post(reverse("inventory:stock-history")).status_code, 405)
        self.assertEqual(self.client.post(reverse("inventory:stock-export")).status_code, 405)
        self.clerk.user_permissions.remove(Permission.objects.get(content_type__app_label="inventory", codename="export_stock_register"))
        self.client.force_login(self.clerk)
        response = self.history()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Export selected movements")
        self.assertEqual(self.exported().status_code, 403)

    def test_csv_keeps_unknown_zero_and_formula_safety_and_private_headers(self):
        self.client.force_login(self.clerk)
        zero = self.movement(self.item, "receipt", "=UNTRUSTED()", unit_cost="0.00")
        response = self.exported({"kind": "receipt"})
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        by_id = {row[-1]: row for row in rows[1:]}
        self.assertEqual(by_id[str(self.receipt.public_id)][11], "")
        self.assertEqual(by_id[str(zero.public_id)][11], "0.00")
        self.assertEqual(by_id[str(zero.public_id)][9], "'=UNTRUSTED()")
        for result in (response, self.history()):
            self.assertIn("private", result["Cache-Control"])
            self.assertIn("no-store", result["Cache-Control"])
            self.assertEqual(result["X-Content-Type-Options"], "nosniff")

    def test_register_entry_and_empty_selection_have_clear_next_steps(self):
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(reverse("inventory:consumable-list")), reverse("inventory:stock-history"))
        response = self.history({"kind": "return"})
        self.assertContains(response, "No movements match these filters")
        self.assertContains(response, "Clear filters")
        self.assertContains(response, "not an official RSMI")
