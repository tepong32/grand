from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import Client, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.models import Asset, AssetVerificationRecord, AssetVerificationEvent
from . import test_property_drafts as fixture


class RPCPPEDraftTests(TestCase):
    databases = {"default", "finance"}
    fields = staticmethod(fixture.PropertyDraftAccessTests.fields)

    @classmethod
    def setUpTestData(cls):
        fixture.PropertyDraftAccessTests.setUpTestData.__func__(cls)

    def url(self):
        return reverse("inventory:rpcppe-preparation")

    def copy_url(self, count):
        return reverse('inventory:asset-verification-reconcile', args=(count.pk,)).replace('/reconcile/', '/working-copy/')

    def count_fixture(self, *, accounting=True):
        from django.utils import timezone
        from inventory.models import AssetVerificationRound, AssetAccountingImport, AssetAccountingLine, AssetVerificationFinding
        count = AssetVerificationRound.objects.create(title='Synthetic count <review>', as_of_date=timezone.localdate(),
            department_id=self.gso.pk, department_label=self.gso.name, created_by=self.clerk)
        records = []
        for index, (tag, cost) in enumerate((('MATCH', Decimal('0.00')), ('UNKNOWN', None), ('DUP', None), ('DUP', None))):
            asset = Asset.objects.create(department_id=self.gso.pk, asset_name='Live register name ' + str(index))
            records.append(AssetVerificationRecord.objects.create(verification_round=count, asset=asset,
                property_tag_snapshot=tag, asset_name_snapshot='Count snapshot item ' + str(index),
                acquisition_cost_snapshot=cost, assigned_department_snapshot='Recorded office',
                result=AssetVerificationRecord.NOT_FOUND if index == 1 else AssetVerificationRecord.NOT_CHECKED,
                notes='Retained observation <script>alert(1)</script>', resolution_note='Review still outstanding'))
        if accounting:
            source = AssetAccountingImport.objects.create(verification_round=count, source_filename='Synthetic accounting.csv',
                source_sha256='0' * 64, line_count=3, imported_by=self.clerk)
            for number, tag in enumerate(('MATCH', 'ACCOUNTING-ONLY', 'DUP'), 1):
                AssetAccountingLine.objects.create(accounting_import=source, row_number=number,
                    property_tag=tag, asset_name='Accounting item ' + tag,
                    acquisition_cost=Decimal('0.00') if tag == 'MATCH' else None)
        AssetVerificationFinding.objects.create(verification_round=count, asset_name='Unregistered observed item',
            property_tag='FOUND', found_department='Observed office', found_office='Observed room',
            notes='Retained finding note', recorded_by=self.clerk)
        return count, records

    def test_count_working_copy_has_all_comparison_groups_and_preserves_unknown_zero(self):
        count, records = self.count_fixture()
        self.client.force_login(self.clerk)
        response = self.client.get(self.copy_url(count))
        self.assertEqual(response.status_code, 200)
        comparison = response.context['comparison']
        self.assertEqual([len(comparison[key]) for key in ('matched', 'register_only', 'accounting_only', 'ambiguous', 'findings')], [1, 3, 1, 1, 1])
        self.assertEqual(comparison['matched'][0]['record'].acquisition_cost_snapshot, Decimal('0.00'))
        self.assertIsNone(records[1].acquisition_cost_snapshot)
        for text in ('Recorded acquisition cost: 0.00', 'Recorded acquisition cost: Not recorded',
                     'Accounting item ACCOUNTING-ONLY', 'Unregistered observed item', 'Follow-up needed',
                     'Review still outstanding', 'not an official RPCPPE or approval'):
            self.assertContains(response, text)
        for row_type in ('matched', 'register_only', 'accounting_only', 'ambiguous_register_tag', 'found_but_unregistered'):
            self.assertContains(response, 'data-row-type="' + row_type + '"')

    def test_count_working_copy_reads_only_retained_default_sources(self):
        from inventory.models import AssetVerificationRound, AssetAccountingImport, AssetAccountingLine, AssetVerificationFinding
        count, records = self.count_fixture()
        models = (Asset, AssetVerificationRound, AssetVerificationRecord, AssetVerificationEvent,
                  AssetAccountingImport, AssetAccountingLine, AssetVerificationFinding)
        before = [list(model.objects.order_by('pk').values()) for model in models]
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
                response = self.client.get(self.copy_url(count))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(finance), 0)
            self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))
        self.assertEqual([list(model.objects.order_by('pk').values()) for model in models], before)

    def test_count_working_copy_requires_current_explicit_grants_and_owner_scope(self):
        from inventory.models import AssetVerificationRound
        count, records = self.count_fixture()
        url = self.copy_url(count)
        self.assertEqual(self.client.get(url).status_code, 302)
        for actor in (self.no_grant, self.super_no_grant, self.outsider):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(url).status_code, 403)
        self.clerk.user_permissions.clear()
        self.clerk.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='view_asset'))
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(url).status_code, 403)
        grant = Permission.objects.get(content_type__app_label='inventory', codename='record_asset_verification')
        self.clerk.user_permissions.add(grant)
        self.assertEqual(self.client.get(url).status_code, 200)
        foreign = AssetVerificationRound.objects.create(title='Other count', as_of_date=count.as_of_date,
            department_id=self.other.pk, department_label=self.other.name)
        self.assertEqual(self.client.get(self.copy_url(foreign)).status_code, 404)
        self.clerk.user_permissions.remove(grant)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_count_working_copy_without_accounting_retains_all_gso_findings(self):
        count, records = self.count_fixture(accounting=False)
        self.client.force_login(self.viewer)
        response = self.client.get(self.copy_url(count))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['accounting_import'])
        self.assertEqual(len(response.context['comparison']['register_only']), 4)
        self.assertContains(response, 'No Accounting snapshot selected')
        for record in records:
            self.assertContains(response, 'data-record-id="' + str(record.pk) + '"')
        self.assertContains(response, 'Unregistered observed item')

    def test_count_working_copy_keeps_every_record_beyond_one_hundred(self):
        count, records = self.count_fixture(accounting=False)
        for number in range(110):
            asset = Asset.objects.create(department_id=self.gso.pk, asset_name='Large count asset ' + str(number))
            AssetVerificationRecord.objects.create(verification_round=count, asset=asset,
                asset_name_snapshot='Large count snapshot ' + str(number), property_tag_snapshot='LARGE-' + str(number))
        self.client.force_login(self.clerk)
        response = self.client.get(self.copy_url(count), {'page': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['comparison']['register_only']), 114)
        self.assertContains(response, 'Large count snapshot 109')
        self.assertEqual(response.content.count(b'data-row-type="register_only"'), 114)

    def test_count_working_copy_uses_snapshots_and_escapes_observed_text(self):
        count, records = self.count_fixture()
        self.client.force_login(self.clerk)
        response = self.client.get(self.copy_url(count))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Count snapshot item 0')
        self.assertNotContains(response, 'Live register name')
        self.assertContains(response, 'Synthetic count &lt;review&gt;')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_count_working_copy_pins_one_latest_accounting_snapshot(self):
        from inventory.models import AssetAccountingImport, AssetAccountingLine
        count, records = self.count_fixture()
        newer = AssetAccountingImport.objects.create(verification_round=count, source_filename='New selected snapshot.csv',
            source_sha256='1' * 64, line_count=1, imported_by=self.clerk)
        AssetAccountingLine.objects.create(accounting_import=newer, row_number=1, property_tag='NEW-ONLY',
            asset_name='Only the selected source')
        self.client.force_login(self.clerk)
        response = self.client.get(self.copy_url(count))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['accounting_import'], newer)
        self.assertContains(response, 'New selected snapshot.csv')
        self.assertContains(response, 'Only the selected source')
        self.assertNotContains(response, 'Synthetic accounting.csv')
        self.assertNotContains(response, 'Accounting item ACCOUNTING-ONLY')

    def test_count_working_copy_is_private_get_head_only_and_never_certifies(self):
        count, records = self.count_fixture()
        self.client.force_login(self.clerk)
        response = self.client.get(self.copy_url(count))
        self.assertEqual(response.status_code, 200)
        for flag in ('private', 'no-store'):
            self.assertIn(flag, response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.client.head(self.copy_url(count)).status_code, 200)
        self.assertEqual(self.client.post(self.copy_url(count), {}).status_code, 405)
        self.assertContains(response, 'Print / Save as PDF')
        self.assertContains(response, 'Round open')
        self.assertNotContains(response, 'Certified Correct')
        self.assertContains(response, 'display:table-header-group')

    def test_count_comparison_links_to_its_working_copy(self):
        count, records = self.count_fixture()
        self.client.force_login(self.clerk)
        response = self.client.get(reverse('inventory:asset-verification-reconcile', args=(count.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Print working reconciliation')
        self.assertContains(response, self.copy_url(count))

    def test_authorized_entry_and_preview_never_write_sources_or_read_finance(self):
        models = (Asset, AssetVerificationRecord, AssetVerificationEvent)
        before = [list(model.objects.values()) for model in models]
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            with CaptureQueriesContext(connections["finance"]) as finance, CaptureQueriesContext(connections["default"]) as default:
                response = self.client.post(self.url(), self.fields(**{
                    "header-lgu": "Synthetic LGU", "lines-0-description": "Supplied equipment",
                    "lines-0-card_quantity": "2.125", "lines-0-counted_quantity": "1.000"}))
            self.assertTrue(response.context["ready"])
            self.assertEqual(response.context["print_lines"][0]["difference"], Decimal("-1.125"))
            self.assertEqual(len(finance), 0)
            self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in default))
        self.assertEqual([list(model.objects.values()) for model in models], before)

    def test_read_authority_is_explicit_and_current_without_requiring_export(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        for actor in (self.no_grant, self.super_no_grant, self.outsider):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.url()).status_code, 403)
            self.assertEqual(self.client.post(self.url(), self.fields()).status_code, 403)
        self.client.force_login(self.clerk)
        self.clerk.user_permissions.clear()
        self.clerk.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("view_asset", "view_property_determination")))
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.clerk.user_permissions.remove(Permission.objects.get(content_type__app_label="inventory", codename="view_property_determination"))
        self.assertEqual(self.client.post(self.url(), self.fields()).status_code, 403)

    def test_zero_unknown_and_supplied_value_are_distinct_without_automatic_valuation(self):
        self.client.force_login(self.clerk)
        response = self.client.post(self.url(), self.fields(**{
            "lines-0-description": "Counted zero", "lines-0-card_quantity": "1", "lines-0-counted_quantity": "0",
            "lines-0-unit_value": "25.00", "lines-0-difference_value": "-25.00",
            "lines-1-description": "Count not yet supplied", "lines-1-card_quantity": "3",
            "lines-1-unit_value": "0.00", "lines-2-description": "Overage",
            "lines-2-card_quantity": "1", "lines-2-counted_quantity": "2", "lines-2-unit_value": "99.99"}))
        self.assertTrue(response.context["ready"])
        rows = response.context["print_lines"]
        self.assertEqual(rows[0]["counted_quantity"], 0)
        self.assertEqual(rows[0]["difference"], -1)
        self.assertEqual(rows[0]["unit_value"], Decimal("25.00"))
        self.assertEqual(rows[0]["difference_value"], Decimal("-25.00"))
        self.assertIsNone(rows[1]["counted_quantity"])
        self.assertIsNone(rows[1]["difference"])
        self.assertIsNone(rows[1]["difference_value"])
        self.assertEqual(rows[1]["unit_value"], Decimal("0.00"))
        self.assertEqual(rows[2]["difference"], 1)
        self.assertIsNone(rows[2]["difference_value"])
        self.assertContains(response, "0.000")
        self.assertContains(response, "[Not supplied]")
        self.assertNotContains(response, "299.97")

    def test_private_blank_draft_has_editable_placeholders_and_no_official_certification(self):
        self.client.force_login(self.viewer)
        start = self.client.get(self.url())
        self.assertEqual(len(start.context["lines"].forms), 5)
        self.assertFalse(start.context["ready"])
        response = self.client.post(self.url(), self.fields())
        self.assertTrue(response.context["ready"])
        for text in ("DRAFT — FOR COMPLETION AND REVIEW", "[LGU / municipality]", "[As-of date]",
                     "Unsigned preparation", "Print / Save as PDF", "Count minus property card"):
            self.assertContains(response, text)
        self.assertNotContains(response, "Certified Correct")
        self.assertNotContains(response, "Appendix 73")
        self.assertNotContains(response, 'class="panel draft-editor" open')
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_invalid_supplied_facts_retain_input_and_do_not_offer_a_printable_result(self):
        self.client.force_login(self.clerk)
        cases = ({"header-as_of": "not-a-date"}, {"lines-0-counted_quantity": "-1"},
                 {"lines-0-card_quantity": "NaN"}, {"lines-0-unit_value": "Infinity"},
                 {"lines-0-difference_value": "0.001"}, {"lines-0-card_quantity": "1.0001"},
                 {"lines-0-unit_value": "-0.01"}, {"lines-0-description": "x" * 501})
        for invalid in cases:
            response = self.client.post(self.url(), self.fields(**{"header-lgu": "Retain my office", **invalid}))
            self.assertFalse(response.context["ready"], invalid)
            self.assertContains(response, "Retain my office")
            self.assertContains(response, "Check the highlighted fields")
            self.assertNotContains(response, 'onclick="window.print()"')

    def test_formset_bounds_missing_management_and_methods_fail_safely(self):
        self.client.force_login(self.clerk)
        forged = self.client.post(self.url(), {**self.fields(), "lines-TOTAL_FORMS": "6", "lines-5-description": "Cannot be silently omitted"})
        self.assertFalse(forged.context["ready"])
        self.assertTrue(forged.context["lines"].non_form_errors())
        self.assertFalse(self.client.post(self.url(), {}).context["ready"])
        self.assertEqual(self.client.put(self.url()).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.clerk)
        self.assertEqual(csrf.post(self.url(), self.fields()).status_code, 403)

    def test_print_text_is_escaped_and_register_has_a_reachable_entry(self):
        self.client.force_login(self.clerk)
        response = self.client.post(self.url(), self.fields(**{
            "header-lgu": "<script>unsafe()</script>", "lines-0-description": "<img src=x onerror=unsafe()>"}))
        self.assertContains(response, "&lt;script&gt;unsafe()&lt;/script&gt;")
        self.assertNotContains(response, "<script>unsafe()</script>")
        self.assertNotContains(response, "<img src=x onerror=unsafe()>")
        register = self.client.get(reverse("inventory:property-register"))
        self.assertContains(register, self.url())


class RPCPPEDraftArithmeticTests(SimpleTestCase):
    def test_exact_signed_and_zero_values_do_not_infer_a_rounding_rule(self):
        from inventory.rpcppe_drafts import RPCPPELineForm
        for card, count, unit, value, valid in (
            ("2.125", "1", "8.00", "-9.00", True),
            ("1", "2", "25.00", "25.00", True),
            ("1", "0", "0.00", "0.00", True),
            ("1", "0", "0.00", "-25.00", False),
            ("0", "0.125", "0.01", "0.00", False),
            ("0", "0.125", "0.01", "", True),
            ("999999999.999", "0", "9999999999999999.99", "-1.00", False),
        ):
            with self.subTest(card=card, count=count, unit=unit, value=value):
                form = RPCPPELineForm({"card_quantity": card, "counted_quantity": count,
                    "unit_value": unit, "difference_value": value})
                self.assertEqual(form.is_valid(), valid, form.errors)
