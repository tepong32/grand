from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from pypdf import PdfReader

from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_account_reviews as fixtures
from . import form1_account_reviews as reviews, form1_flow_output as output


class Form1FlowOutputTests(fixtures.Form1AccountReviewFixture):
    def export(self, record, kind):
        return self.client.get(reverse('budget:form1_account_export', args=(record.public_id, kind)))

    def text(self, content):
        pages=PdfReader(BytesIO(content)).pages
        for page in pages:
            self.assertIn('INCOMPLETE DRAFT', page.extract_text())
        return '\n'.join(page.extract_text() for page in pages)

    def test_original_complete_http_exports_deterministic_bytes_and_no_posting(self):
        record=self.review_accounts(self.prepare_accounts())
        before=JournalEntry.objects.count(); original=deepcopy(record.payload)
        self.client.force_login(self.checker)
        snapshot=reviews.snapshot(record,self.checker,export=True)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            envelope=output.package(snapshot); content=output.render_pdf(envelope)
        response=self.export(record,'flow-json')
        self.assertEqual(response.status_code,200); self.assertEqual(json.loads(response.content),envelope)
        response=self.export(record,'flow-pdf')
        self.assertEqual(response.status_code,200); self.assertEqual(response.content,content)
        self.assertEqual(self.export(record,'flow-pdf').content,content)
        self.assertEqual(response['X-GRAND-Export-SHA256'],sha256(content).hexdigest())
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertIn('form1-flow-draft-',response['Content-Disposition'])
        text=self.text(content)
        self.assertIn('Source freshness is not certified',text)
        self.assertIn('SPA subdivisions',text)
        for row in record.payload['draft']['payload']['allocations']:
            self.assertIn(row['key'],text)
        self.assertEqual(JournalEntry.objects.count(),before)
        record.refresh_from_db(); self.assertEqual(record.payload,original)
        detail=self.client.get(reverse('budget:form1_account_detail',args=(record.public_id,)))
        self.assertContains(detail,'Download printable flow draft')
        self.assertContains(detail,'Download complete flow draft evidence')

    def test_unresolved_return_and_superseded_approval_keep_original_evidence(self):
        first=self.review_accounts(self.prepare_accounts())
        self.client.force_login(self.checker)
        retained=self.export(first,'flow-pdf').content
        pending=self.prepare_accounts(expected_latest=1,allocations=self.account_allocations())
        self.assertFalse(reviews.is_current(first,self.checker))
        self.assertEqual(self.export(first,'flow-pdf').content,retained)
        prepared=json.loads(self.export(pending,'flow-json').content)
        self.assertFalse(prepared['payload']['account_review']['independently_reviewed'])
        self.assertIn('Unresolved reporting selection',self.text(self.export(pending,'flow-pdf').content))
        returned=self.review_accounts(pending,approve=False,codes_verified=False)
        envelope=json.loads(self.export(returned,'flow-json').content)
        self.assertEqual(envelope['payload']['account_review']['decision']['status'],'returned')
        self.assertFalse(envelope['payload']['form_issued'])
        self.assertIn('decision returned',self.text(self.export(returned,'flow-pdf').content))

    def test_source_export_revocation_export_only_uat_and_button_visibility(self):
        record=self.prepare_accounts()
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.preparer.user_permissions.remove(*Permission.objects.filter(
            content_type__app_label='budget',codename='view_form1_account_reviews'))
        self.preparer.user_permissions.remove(*Permission.objects.filter(
            content_type__app_label='accounting',codename='view_native_budget_actuals'))
        self.client.force_login(self.preparer)
        for kind in ('flow-json','flow-pdf'):
            self.assertEqual(self.export(record,kind).status_code,200)
        self.preparer.user_permissions.remove(Permission.objects.get(
            content_type__app_label='accounting',codename='export_native_budget_actuals'))
        for kind in ('flow-json','flow-pdf'):
            self.assertEqual(self.export(record,kind).status_code,403)
        self.checker.user_permissions.remove(Permission.objects.get(
            content_type__app_label='accounting',codename='export_native_budget_actuals'))
        self.client.force_login(self.checker)
        detail=self.client.get(reverse('budget:form1_account_detail',args=(record.public_id,)))
        self.assertEqual(detail.status_code,200)
        self.assertNotContains(detail,'Download printable flow draft')

    def test_rehashed_projection_decision_and_unsupported_source_glyph_fail_closed(self):
        record=self.prepare_accounts()
        snapshot=reviews.snapshot(record,self.preparer,export=True)
        envelope=output.package(snapshot)
        changed=deepcopy(envelope)
        changed['payload']['itemization']['payload']['members'][0]['receipt']['totals']['estimate']='999.00'
        changed['payload']['itemization']['checksum']=checksum(changed['payload']['itemization']['payload'])
        changed['checksum']=checksum(changed['payload'])
        with self.assertRaises(ValidationError): output.render_pdf(changed)
        changed=deepcopy(snapshot); changed['independently_reviewed']=True
        with self.assertRaises(ValidationError): output.package(changed)
        # A real retained source may contain a glyph outside the bundled font.
        # Reject the print rather than replacing its evidence with an empty box.
        changed=deepcopy(snapshot); changed['payload']['code_reference']='Synthetic unsupported \U0001f600'
        changed['payload_checksum']=checksum(changed['payload'])
        changed['decision']['payload_checksum']=changed['payload_checksum']
        with self.assertRaises(ValidationError): output.render_pdf(output.package(changed))
