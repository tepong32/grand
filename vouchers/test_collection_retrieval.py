import csv
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.db import connections
from django.test.utils import CaptureQueriesContext

from .models import TreasuryCollectionSource as Source
from . import test_collection_workflow as fixtures


class CollectionRetrievalTests(TestCase):
    """Real HTTP retrieval over retained sources and a posted receipt/deposit chain."""
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.CollectionWorkflowTests.setUpTestData.__func__)
    employee = classmethod(fixtures.CollectionWorkflowTests.employee.__func__)
    setUp = fixtures.CollectionWorkflowTests.setUp
    receipt = fixtures.CollectionWorkflowTests.receipt
    capture = fixtures.CollectionWorkflowTests.capture
    deposit = fixtures.CollectionWorkflowTests.deposit
    post_source = fixtures.CollectionWorkflowTests.post_source

    def grant_read_export(self, user):
        for app, code in (("vouchers", "view_collection_register"), ("finance", "export_finance_work")):
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        self.client.force_login(user)

    def test_pages_search_and_export_cover_all_scoped_records(self):
        oldest = self.receipt(document_reference="OLD-REFERENCE", source_date=date(2026, 9, 1))
        for number in range(104):
            self.receipt(document_reference=f"VOLUME-{number:03}")
        hidden = self.receipt(treasury_department=self.requesting, finance_department_id=self.requesting.pk,
                              document_reference="HIDDEN", fund_code="hidden-fund")
        self.grant_read_export(self.treasury_user)
        url = reverse("vouchers:collection_register")
        seen = []
        for page in (1, 2, 3):
            response = self.client.get(url, {"page": page})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["page_obj"].paginator.count, 105)
            seen.extend(row["source"].pk for row in response.context["rows"])
            self.assertNotContains(response, "hidden-fund")
        self.assertEqual(len(set(seen)), 105)
        self.assertEqual(seen[-1], oldest.pk)
        response = self.client.get(url, {"q": "old-reference"})
        self.assertEqual([row["source"].pk for row in response.context["rows"]], [oldest.pk])
        exported = self.client.get(reverse("vouchers:collection_export"), {"page": 3})
        rows = list(csv.DictReader(io.StringIO(exported.content.decode())))
        self.assertEqual(len(rows), 105)
        self.assertNotIn(hidden.document_reference, [row["Reference"] for row in rows])
        for page in ("bad", "999", "-1"):
            self.assertEqual(self.client.get(url, {"page": page}).status_code, 200)

    def test_filtered_availability_keeps_outside_allocations_and_totals_separate(self):
        receipt = self.capture()
        self.post_source(receipt)
        deposit = self.deposit(receipt, "60", "DEPOSIT-OUTSIDE")
        self.grant_read_export(self.treasury_user)
        query = {"q": "Synthetic payer", "kind": Source.RECEIPT, "status": Source.POSTED,
                 "fund": "general-fund", "date_from": "2026-09-12", "date_to": "2026-09-12"}
        response = self.client.get(reverse("vouchers:collection_register"), query)
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0]["available"], Decimal("40"))
        self.assertEqual(response.context["totals"][0]["recorded_amount"], Decimal("100"))
        exported = self.client.get(reverse("vouchers:collection_export"), query)
        rows = list(csv.DictReader(io.StringIO(exported.content.decode())))
        self.assertEqual(len(rows), 1)
        self.assertEqual(Decimal(rows[0]["Available for deposit (after pending allocations)"]), Decimal("40"))
        self.assertNotIn(deposit.document_reference, [row["Reference"] for row in rows])
        all_rows = self.client.get(reverse("vouchers:collection_register"))
        totals = {(row["kind"], row["status"]): row["recorded_amount"] for row in all_rows.context["totals"]}
        self.assertEqual(totals, {(Source.RECEIPT, Source.POSTED): Decimal("100"), (Source.DEPOSIT, Source.PROPOSED): Decimal("60")})

    def test_invalid_filters_and_export_authority_fail_closed(self):
        self.capture()
        self.grant_read_export(self.treasury_user)
        for query in ({"date_from": "invalid"}, {"date_from": "2026-09-20", "date_to": "2026-09-01"},
                      {"fund": "not-visible"}, {"kind": "invalid"}, {"status": "invalid"}):
            response = self.client.get(reverse("vouchers:collection_register"), query)
            self.assertTrue(response.context["filters"].errors)
            self.assertEqual(response.context["page_obj"].paginator.count, 0)
            self.assertEqual(self.client.get(reverse("vouchers:collection_export"), query).status_code, 400)
        self.treasury_user.user_permissions.remove(Permission.objects.get(content_type__app_label="finance", codename="export_finance_work"))
        self.assertEqual(self.client.get(reverse("vouchers:collection_export")).status_code, 403)

    def test_printable_copy_contains_all_selected_pages_with_current_scope(self):
        for number in range(53):
            self.receipt(document_reference=f"PRINT-{number:03}")
        self.receipt(treasury_department=self.requesting, finance_department_id=self.requesting.pk,
                     document_reference="PRIVATE-OTHER-OFFICE", fund_code="hidden-fund")
        self.grant_read_export(self.treasury_user)
        query = {"q": "PRINT-", "page": 2}
        copy = self.client.get(reverse("vouchers:collection_working_copy"), query)
        self.assertEqual(copy.status_code, 200)
        expected = list(Source.objects.filter(document_reference__startswith="PRINT-").order_by('-source_date', '-pk'))
        self.assertEqual([row['source'].pk for row in copy.context['rows']], [source.pk for source in expected])
        for source in expected:
            self.assertContains(copy, str(source.public_id))
        self.assertNotContains(copy, "PRIVATE-OTHER-OFFICE")
        self.assertContains(copy, "53 matching source records")
        self.assertNotIn("page=", copy.context['page_query'])
        self.assertIn('no-store', copy['Cache-Control'])
        self.assertIn('private', copy['Cache-Control'])
        self.assertEqual(copy['X-Content-Type-Options'], 'nosniff')

    def test_printable_copy_preserves_available_amount_and_source_history_without_writes(self):
        receipt = self.capture()
        self.post_source(receipt)
        self.deposit(receipt, "60", "OUTSIDE-PRINT-FILTER")
        self.grant_read_export(self.treasury_user)
        before = list(Source.objects.values())
        with CaptureQueriesContext(connections['default']) as default, CaptureQueriesContext(connections['finance']) as finance:
            response = self.client.get(reverse('vouchers:collection_working_copy'), {'q': receipt.document_reference})
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['rows'][0]['available'], Decimal('40'))
        self.assertContains(response, '100.00')
        self.assertContains(response, 'not net collections or available cash')
        self.assertContains(response, 'A reserved JEV number does not prove posting')
        self.assertNotContains(response, 'OUTSIDE-PRINT-FILTER')
        for captured in (default, finance):
            self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in captured))
        self.assertEqual(before, list(Source.objects.values()))

    def test_printable_copy_rechecks_authority_filters_methods_and_escapes_text(self):
        self.receipt(document_reference='<script>unsafe()</script>')
        url = reverse('vouchers:collection_working_copy')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.grant_read_export(self.treasury_user)
        self.assertContains(self.client.get(url), '&lt;script&gt;unsafe()&lt;/script&gt;')
        self.assertNotContains(self.client.get(url), '<script>unsafe()</script>')
        for query in ({'status': 'bad'}, {'date_from': 'bad'}, {'fund': 'hidden-fund'},
                      {'date_from': '2026-10-02', 'date_to': '2026-10-01'}):
            self.assertEqual(self.client.get(url, query).status_code, 400)
        self.assertContains(self.client.get(url, {'q': 'absent'}), 'does not certify zero collections')
        self.assertEqual(self.client.post(url).status_code, 405)
        for app, code in (('finance', 'export_finance_work'), ('vouchers', 'view_collection_register')):
            grant = Permission.objects.get(content_type__app_label=app, codename=code)
            self.treasury_user.user_permissions.remove(grant)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.treasury_user.user_permissions.add(grant)
