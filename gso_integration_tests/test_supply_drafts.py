from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import Client, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.models import ConsumableItem, StockMovement, StockCount, StockCountEvent, StockCountEvidence
from . import test_grand_stock_authority as fixture


class SupplyDraftTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        fixture.GrandStockAuthorityTests.setUpTestData.__func__(cls)
        cls.other.name, cls.other.slug = "Engineering", "engineering"
        cls.other.save(update_fields=["name", "slug"])
        read = Permission.objects.get(content_type__app_label="inventory", codename="view_consumableitem")
        for actor in (cls.clerk, cls.viewer):
            actor.user_permissions.clear()
            actor.user_permissions.add(read)

    @staticmethod
    def fields(**values):
        return {"lines-TOTAL_FORMS": "5", "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "5", **values}

    def url(self, kind):
        return reverse(f"inventory:{kind}-preparation")

    def test_minimal_stock_reader_and_uat_can_prepare_both_without_asset_or_export_grants(self):
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            for kind in ("rpci", "rsmi"):
                response = self.client.get(self.url(kind))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context["lines"].forms), 5)
                self.assertFalse(response.context["header"].initial)
                self.assertTrue(self.client.post(self.url(kind), self.fields()).context["ready"])
                self.assertNotContains(response, 'href="' + reverse("inventory:dashboard"))
                self.assertContains(response, 'href="' + reverse("inventory:consumable-list"))

    def test_current_authority_office_and_anonymous_boundaries_apply_to_get_and_post(self):
        for kind in ("rpci", "rsmi"):
            self.client.logout()
            self.assertEqual(self.client.get(self.url(kind)).status_code, 302)
            self.assertEqual(self.client.post(self.url(kind), self.fields()).status_code, 302)
            for actor in (self.no_grant, self.super_no_grant, self.outsider):
                self.client.force_login(actor)
                self.assertEqual(self.client.get(self.url(kind)).status_code, 403)
                self.assertEqual(self.client.post(self.url(kind), self.fields()).status_code, 403)
            self.client.force_login(self.clerk)
            grant = Permission.objects.get(content_type__app_label="inventory", codename="view_consumableitem")
            self.clerk.user_permissions.remove(grant)
            self.assertEqual(self.client.post(self.url(kind), self.fields()).status_code, 403)
            self.clerk.user_permissions.add(grant)

    def test_drafts_never_change_stock_count_evidence_or_finance(self):
        models = (ConsumableItem, StockMovement, StockCount, StockCountEvent, StockCountEvidence)
        before = [list(model.objects.values()) for model in models]
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            for kind in ("rpci", "rsmi"):
                with CaptureQueriesContext(connections["finance"]) as finance, CaptureQueriesContext(connections["default"]) as default:
                    response = self.client.post(self.url(kind), self.fields(**{"lines-0-description": "Supplied draft only"}))
                self.assertTrue(response.context["ready"])
                self.assertEqual(len(finance), 0)
                self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in default))
        self.assertEqual([list(model.objects.values()) for model in models], before)

    def test_asset_or_export_only_permissions_do_not_grant_stock_draft_access(self):
        self.no_grant.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("view_asset", "view_property_determination", "export_stock_register")))
        self.client.force_login(self.no_grant)
        for kind in ("rpci", "rsmi"):
            self.assertEqual(self.client.get(self.url(kind)).status_code, 403)
            self.assertEqual(self.client.post(self.url(kind), self.fields()).status_code, 403)

    def test_changed_current_office_is_rechecked_on_preview(self):
        from profiles.models import EmployeeProfile
        self.client.force_login(self.clerk)
        for kind in ("rpci", "rsmi"):
            self.assertEqual(self.client.get(self.url(kind)).status_code, 200)
        EmployeeProfile.objects.filter(user=self.clerk).update(assigned_department=self.other)
        for kind in ("rpci", "rsmi"):
            self.assertEqual(self.client.post(self.url(kind), self.fields()).status_code, 403)

    def test_rpci_zero_negative_difference_and_unknown_are_kept_separate(self):
        self.client.force_login(self.clerk)
        response = self.client.post(self.url("rpci"), self.fields(**{
            "lines-0-stock_number": "SUPPLIED-1", "lines-0-card_quantity": "1", "lines-0-counted_quantity": "0",
            "lines-0-unit_value": "25.00", "lines-0-difference_value": "-25.00",
            "lines-1-description": "Unknown physical count", "lines-1-card_quantity": "3", "lines-1-unit_value": "0.00"}))
        self.assertTrue(response.context["ready"])
        rows = response.context["print_lines"]
        self.assertEqual(rows[0]["counted_quantity"], 0)
        self.assertEqual(rows[0]["difference"], -1)
        self.assertEqual(rows[0]["difference_value"], Decimal("-25.00"))
        self.assertIsNone(rows[1]["counted_quantity"])
        self.assertIsNone(rows[1]["difference"])
        self.assertIsNone(rows[1]["difference_value"])
        self.assertContains(response, "0.000")
        self.assertContains(response, "0.00")
        self.assertContains(response, "Count minus stock card")
        self.assertNotContains(response, "Property number")
        self.assertNotContains(response, "property card")

    def test_rsmi_preserves_source_dates_supplied_zero_and_unknown_without_calculating_amounts(self):
        self.client.force_login(self.clerk)
        response = self.client.post(self.url("rsmi"), self.fields(**{
            "header-period_start": "2026-09-01", "header-period_end": "2026-09-30", "header-number": "LOCAL-SUPPLIED",
            "lines-0-source_date": "2026-09-10", "lines-0-reference": "RIS-1", "lines-0-recipient_office": "Health",
            "lines-0-quantity": "2.125", "lines-0-unit_cost": "0.00", "lines-0-amount": "0.00",
            "lines-1-description": "Amount not supplied", "lines-1-quantity": "3", "lines-1-unit_cost": "99.99"}))
        self.assertTrue(response.context["ready"])
        rows = response.context["print_lines"]
        self.assertEqual(rows[0]["quantity"], Decimal("2.125"))
        self.assertEqual(rows[0]["amount"], 0)
        self.assertIsNone(rows[1]["amount"])
        self.assertContains(response, "2026-09-10")
        self.assertContains(response, "LOCAL-SUPPLIED")
        self.assertContains(response, "RIS-1")
        self.assertNotContains(response, "299.97")

    def test_invalid_facts_keep_inputs_and_never_offer_a_print_control(self):
        self.client.force_login(self.clerk)
        cases = {"rpci": ({"lines-0-card_quantity": "-1"}, {"lines-0-unit_value": "NaN"},
                          {"lines-0-card_quantity": "1", "lines-0-counted_quantity": "0", "lines-0-unit_value": "25", "lines-0-difference_value": "-24"}),
                 "rsmi": ({"lines-0-quantity": "-1"}, {"lines-0-unit_cost": "Infinity"}, {"lines-0-amount": "-1"},
                          {"header-period_start": "2026-09-30", "header-period_end": "2026-09-01"},
                          {"lines-0-quantity": "2", "lines-0-unit_cost": "3", "lines-0-amount": "7"})}
        for kind, entries in cases.items():
            for invalid in entries:
                with self.subTest(kind=kind, invalid=invalid):
                    response = self.client.post(self.url(kind), self.fields(**{"header-office": "Retain office", **invalid}))
                    self.assertFalse(response.context["ready"])
                    self.assertContains(response, "Retain office")
                    self.assertContains(response, "Check the highlighted fields")
                    self.assertNotContains(response, 'onclick="window.print()"')

    def test_form_bounds_missing_management_methods_and_csrf_remain_enforced(self):
        self.client.force_login(self.clerk)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.clerk)
        for kind in ("rpci", "rsmi"):
            bad = self.client.post(self.url(kind), {**self.fields(), "lines-TOTAL_FORMS": "6", "lines-5-description": "Must not be silently omitted"})
            self.assertFalse(bad.context["ready"])
            self.assertTrue(bad.context["lines"].non_form_errors())
            self.assertFalse(self.client.post(self.url(kind), {}).context["ready"])
            self.assertEqual(self.client.put(self.url(kind)).status_code, 405)
            self.assertEqual(protected.post(self.url(kind), self.fields()).status_code, 403)

    def test_private_escaped_preview_does_not_invent_approval_or_report_totals(self):
        self.client.force_login(self.clerk)
        for kind in ("rpci", "rsmi"):
            response = self.client.post(self.url(kind), self.fields(**{
                "header-lgu": "<script>unsafe()</script>", "lines-0-description": "<img src=x onerror=unsafe()>"}))
            self.assertContains(response, "&lt;script&gt;unsafe()&lt;/script&gt;")
            self.assertNotContains(response, "<script>unsafe()</script>")
            self.assertNotContains(response, "<img src=x onerror=unsafe()>")
            self.assertContains(response, "DRAFT — FOR COMPLETION AND REVIEW")
            self.assertContains(response, "Unsigned preparation")
            self.assertContains(response, "No unlike-item quantity or value total")
            self.assertNotContains(response, "Certified Correct")
            self.assertNotContains(response, "NGAS Annex")
            self.assertIn("private", response["Cache-Control"])
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_supplies_entry_and_brand_do_not_require_asset_dashboard_access(self):
        self.client.force_login(self.clerk)
        page = self.client.get(reverse("inventory:consumable-list"))
        self.assertEqual(page.status_code, 200)
        for kind in ("rpci", "rsmi"):
            self.assertContains(page, self.url(kind))
        self.assertNotContains(page, 'href="' + reverse("inventory:dashboard"))
        self.assertEqual(self.client.get(reverse("department_dashboard")).status_code, 200)
        self.client.force_login(self.outsider)
        ordinary = self.client.get(reverse("inventory:consumable-list"))
        self.assertEqual(ordinary.status_code, 200)
        self.assertNotContains(ordinary, self.url("rpci"))
        self.assertNotContains(ordinary, self.url("rsmi"))


class SupplyDraftArithmeticTests(SimpleTestCase):
    def test_rpci_uses_stock_terms_and_preserves_exact_shared_arithmetic(self):
        from inventory.supply_drafts import RPCILineForm
        form = RPCILineForm({"card_quantity": "2.125", "counted_quantity": "1", "unit_value": "8", "difference_value": "-9"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("property_number", form.fields)
        self.assertIn("stock_number", form.fields)
        invalid = RPCILineForm({"card_quantity": "1", "counted_quantity": "0", "unit_value": "1", "difference_value": "1"})
        self.assertFalse(invalid.is_valid())
        self.assertIn("stock card", str(invalid.errors))
        self.assertNotIn("property card", str(invalid.errors))

    def test_rsmi_exact_zero_unknown_fractional_and_large_values_do_not_infer_rounding(self):
        from inventory.supply_drafts import RSMILineForm
        for quantity, unit, amount, valid in (("2.125", "8", "17.00", True), ("0", "25", "0", True),
            ("1", "", "", True), ("0.125", "0.01", "0.00", False), ("0.125", "0.01", "", True),
            ("999999999.999", "9999999999999999.99", "1", False), ("1.0001", "1", "1", False),
            ("1", "-1", "0", False), ("NaN", "1", "0", False), ("1", "1", "0.001", False)):
            with self.subTest(quantity=quantity, unit=unit, amount=amount):
                form = RSMILineForm({"quantity": quantity, "unit_cost": unit, "amount": amount})
                self.assertEqual(form.is_valid(), valid, form.errors)
