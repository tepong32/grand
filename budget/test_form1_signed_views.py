from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_signed_copies as fixtures, form1_signed_copies as signed
from .form1_signed_forms import SignedDecision
from .models import BudgetAuditEvent, Form1SignedReceipt as Receipt, Form1SignedReview as Review, Form1FinalIssue as Issue

RECORDER = 'Budget Form 1 Signed Copy Recorder'
ISSUER = 'Budget Form 1 Signed Copy Verifier and Issuer'


class Form1SignedViewTests(fixtures.Form1SignedFixture):
    def receipt_data(self,copy,*,latest=0,predecessor=None,missing=False):
        data = dict(expected_latest=latest,predecessor=str(predecessor.public_id) if predecessor else '',
            upload=self.signed_upload(copy),received_on=timezone.localtime().date().isoformat(),
            received_by='Synthetic on-site recipient',custody_reference='TEST physical handover',
            custody_location='TEST Budget custody cabinet',correction_reason='Synthetic declared paper return / scan correction')
        for number,_ in enumerate(signed.entities(copy)):
            for role in signed.signing.ROLES:
                data[f'entity{number}_{role}'] = '' if missing and number==0 and role=='treasurer' else timezone.localtime().date().isoformat()
        return data

    def decision_data(self,copy,*,action='verify_issue',incomplete=False):
        data = dict(action=action,note='Synthetic independent inspection, not actual LGU acceptance',
                    reference='Synthetic retained final issue')
        for number,(key,_) in enumerate(SignedDecision(copy=copy).findings):
            data[f'finding{number}_verified'] = 'false' if incomplete and key.endswith(':treasurer') else 'true'
            data[f'finding{number}_basis'] = 'Synthetic inspected original evidence for '+key
        return data

    def test_minimal_officers_capture_verify_issue_and_download_exact_audited_originals(self):
        copy = self.release_copy(self.unsigned_preparation())
        before = JournalEntry.objects.count()
        history = reverse('budget:form1_signed_history',args=[copy.public_id])
        self.copy_role_only(self.preparer,RECORDER)
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(reverse('budget:form1_signing_detail',args=[copy.preparation.public_id])),
                            'Signed returns and final issue history')
        entry = self.client.get(history)
        self.assertContains(entry,'Record a physical signed return')
        self.assertContains(entry,'SYNTHETIC TEST MUNICIPALITY - Peña')
        scope = f'Fund {copy.preparation.package.fund.code} · Budget year {copy.preparation.package.proposal.fiscal_year.year}'
        self.assertContains(entry,scope)
        guarded = Client(enforce_csrf_checks=True);guarded.force_login(self.preparer)
        self.assertEqual(guarded.post(history,self.receipt_data(copy)).status_code,403)
        response = self.client.post(history,self.receipt_data(copy))
        record = Receipt.objects.get(copy=copy)
        detail = reverse('budget:form1_signed_detail',args=[record.public_id])
        decision = reverse('budget:form1_signed_review',args=[record.public_id])
        self.assertRedirects(response,detail,fetch_redirect_response=False)
        self.assertEqual(self.client.post(decision,self.decision_data(copy)).status_code,403)
        self.assertEqual(self.client.get(decision).status_code,405)
        self.copy_role_only(self.reviewer,ISSUER)
        self.client.force_login(self.reviewer)
        pending = self.client.get(detail)
        self.assertContains(pending,'Verify signatures and issue package')
        self.assertContains(pending,'SYNTHETIC TEST MUNICIPALITY - Peña')
        self.assertContains(pending,scope)
        self.assertContains(self.client.get(history),'Awaiting independent signature verification')
        guarded.force_login(self.reviewer)
        self.assertEqual(guarded.post(decision,self.decision_data(copy)).status_code,403)
        data = self.decision_data(copy);data['reference'] = ''
        rejected = self.client.post(decision,data)
        self.assertEqual(rejected.status_code,409)
        self.assertContains(rejected,'final issuance reference',status_code=409)
        self.assertFalse(Review.objects.filter(receipt=record).exists())
        self.assertFalse(Issue.objects.exists())
        response = self.client.post(decision,self.decision_data(copy))
        self.assertRedirects(response,detail,fetch_redirect_response=False)
        issue = Issue.objects.get(receipt=record)
        self.assertContains(self.client.get(detail),'Download original final issued package')
        returned = self.client.get(reverse('budget:form1_signed_document',args=[record.public_id]))
        self.assertEqual(b''.join(returned.streaming_content),bytes(record.document))
        output = self.client.get(reverse('budget:form1_final_document',args=[issue.public_id]))
        content = b''.join(output.streaming_content)
        self.assertEqual(content,bytes(issue.archive))
        self.assertEqual(output['X-GRAND-Export-SHA256'],sha256(content).hexdigest())
        self.assertEqual(output['X-Content-Type-Options'],'nosniff')
        self.assertEqual(output['Cache-Control'],'private, no-store')
        with ZipFile(BytesIO(content)) as archive:
            self.assertEqual(archive.read('unsigned-form1.pdf'),bytes(copy.document))
            self.assertEqual(archive.read('signed-form1.pdf'),bytes(record.document))
        for action in ('form1_signed_return_exported','form1_final_package_exported'):
            self.assertTrue(BudgetAuditEvent.objects.filter(action=action,actor_id=self.reviewer.pk).exists())
        self.assertEqual(JournalEntry.objects.count(),before)
        self.assertIs(copy.payload['form_issued'],False)
        self.client.force_login(self.preparer)
        correction_entry = self.client.get(history)
        self.assertContains(correction_entry,scope)
        self.assertContains(correction_entry,'propose a correction to final issue version 1')

    def test_incomplete_return_and_explicit_scan_successor_preserve_prior_issued_history(self):
        copy = self.release_copy(self.unsigned_preparation())
        history = reverse('budget:form1_signed_history',args=[copy.public_id])
        self.copy_role_only(self.preparer,RECORDER);self.copy_role_only(self.reviewer,ISSUER)
        self.client.force_login(self.preparer)
        self.client.post(history,self.receipt_data(copy,missing=True))
        first = Receipt.objects.get(copy=copy)
        first_detail = reverse('budget:form1_signed_detail',args=[first.public_id])
        first_review = reverse('budget:form1_signed_review',args=[first.public_id])
        self.assertContains(self.client.get(first_detail),'Unknown — verification blocked')
        self.client.force_login(self.reviewer)
        denied = self.client.post(first_review,self.decision_data(copy))
        self.assertEqual(denied.status_code,409)
        self.assertFalse(Review.objects.exists())
        self.assertFalse(Issue.objects.exists())
        self.client.post(first_review,self.decision_data(copy,action='return',incomplete=True))
        self.assertContains(self.client.get(first_detail),'Returned for corrected evidence')
        self.client.force_login(self.preparer)
        self.client.post(history,self.receipt_data(copy,latest=1))
        second = Receipt.objects.get(copy=copy,version=2)
        self.client.force_login(self.reviewer)
        # Separate review and issuance remain possible with their separate grants.
        self.client.post(reverse('budget:form1_signed_review',args=[second.public_id]),
                         self.decision_data(copy,action='verify'))
        second_detail = reverse('budget:form1_signed_detail',args=[second.public_id])
        self.assertContains(self.client.get(second_detail),'Issue the independently verified package')
        issue_url = reverse('budget:form1_signed_issue',args=[second.public_id])
        self.assertEqual(self.client.get(issue_url).status_code,405)
        self.assertEqual(self.client.post(issue_url,{'reference':'Synthetic separate final issuance'}).status_code,302)
        issued = Issue.objects.get(receipt=second);original=bytes(issued.archive)
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(history),'propose a correction to final issue version 1')
        self.assertEqual(self.client.post(history,self.receipt_data(copy,latest=2)).status_code,409)
        self.assertEqual(Receipt.objects.count(),2)
        self.assertEqual(self.client.post(history,self.receipt_data(copy,latest=2,predecessor=issued)).status_code,302)
        third = Receipt.objects.get(copy=copy,version=3)
        self.assertEqual(third.predecessor_issue_id,issued.pk)
        self.assertContains(self.client.get(second_detail),'Download original final issued package')
        issued.refresh_from_db();self.assertEqual(bytes(issued.archive),original)
        self.assertEqual(Issue.objects.count(),1)
        # History re-fetches actual rows, rejects foreign identities and verifies
        # each receipt against the same authorized original copy.
        rows = signed.history(copy,[third.pk,first.pk],self.preparer)
        self.assertEqual([row.pk for row,_ in rows],[third.pk,first.pk])
        self.assertEqual(rows[0][1],signed.snapshot(third,self.preparer))
        with self.assertRaises(ValidationError): signed.history(copy,[third.pk,third.pk],self.preparer)
        with self.assertRaises(ValidationError): signed.history(copy,[999999999],self.preparer)

    def test_viewer_uat_revocation_and_corruption_cannot_mutate_or_export_unverified_bytes(self):
        copy = self.release_copy(self.unsigned_preparation())
        record = self.capture_return(copy);self.inspect_return(record);issued=self.issue_return(record)
        history = reverse('budget:form1_signed_history',args=[copy.public_id])
        detail = reverse('budget:form1_signed_detail',args=[record.public_id])
        review = reverse('budget:form1_signed_review',args=[record.public_id])
        issue = reverse('budget:form1_signed_issue',args=[record.public_id])
        pdf = reverse('budget:form1_signed_document',args=[record.public_id])
        archive = reverse('budget:form1_final_document',args=[issued.public_id])
        for actor,role in ((self.checker,'Accounting Form 1 Final Package Viewer'),
                           (self.treasurer,'Treasury Form 1 Final Package Viewer')):
            self.copy_role_only(actor,role);self.client.force_login(actor)
            self.assertEqual(self.client.get(history).status_code,200)
            self.assertEqual(self.client.get(detail).status_code,200)
            self.assertEqual(self.client.post(history,self.receipt_data(copy,latest=1,predecessor=issued)).status_code,403)
            self.assertEqual(self.client.post(review,self.decision_data(copy)).status_code,403)
            self.assertEqual(self.client.post(issue,{'reference':'Denied viewer issue'}).status_code,403)
            for url in (pdf,archive):
                response=self.client.get(url);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        # Operational grants do not transfer Budget ownership to another office.
        self.copy_role_only(self.checker,RECORDER);self.client.force_login(self.checker)
        self.assertEqual(self.client.post(history,self.receipt_data(copy,latest=1,predecessor=issued)).status_code,403)
        self.copy_role_only(self.checker,ISSUER)
        self.assertEqual(self.client.post(review,self.decision_data(copy)).status_code,403)
        self.assertEqual(self.client.post(issue,{'reference':'Denied foreign issuer'}).status_code,403)
        self.copy_role_only(self.checker,'Accounting Form 1 Final Package Viewer')
        permission = Permission.objects.get(content_type__app_label='budget',codename='export_budget_receipt_forecasts')
        self.checker.user_permissions.remove(permission)
        self.assertEqual(self.client.get(detail).status_code,200)
        self.assertEqual(self.client.get(pdf).status_code,403)
        self.assertEqual(self.client.get(archive).status_code,403)
        self.checker.user_permissions.add(permission)
        permission = Permission.objects.get(content_type__app_label='budget',codename='view_form1_signed_copies')
        self.checker.user_permissions.remove(permission)
        self.assertEqual(self.client.get(detail).status_code,403)
        response=self.client.get(pdf);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        self.checker.user_permissions.add(permission)
        group = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0]
        self.copy_role_only(self.preparer,RECORDER);self.preparer.groups.add(group)
        self.client.force_login(self.preparer)
        self.assertNotContains(self.client.get(history),'Record a physical signed return')
        self.assertEqual(self.client.post(history,self.receipt_data(copy,latest=1,predecessor=issued)).status_code,403)
        self.copy_role_only(self.reviewer,ISSUER);self.reviewer.groups.add(group)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(review,self.decision_data(copy)).status_code,403)
        self.assertEqual(self.client.post(issue,{'reference':'Denied UAT issue'}).status_code,403)
        self.assertEqual(self.client.get(detail).status_code,200)
        self.client.force_login(self.checker)
        before=BudgetAuditEvent.objects.filter(action='form1_signed_return_exported').count()
        Receipt.objects.filter(pk=record.pk).update(document=b'%PDF-corrupt')
        self.assertEqual(self.client.get(pdf).status_code,409)
        self.assertEqual(BudgetAuditEvent.objects.filter(action='form1_signed_return_exported').count(),before)
        Receipt.objects.filter(pk=record.pk).update(document=bytes(record.document))
        Issue.objects.filter(pk=issued.pk).update(archive=b'corrupt archive')
        self.assertEqual(self.client.get(archive).status_code,409)
