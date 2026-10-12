from copy import deepcopy
from io import BytesIO

from django.contrib.auth.models import Permission,Group
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP,FINANCE_ROLE_PERMISSIONS
from . import test_form1_account_reviews as fixtures,test_form1_spa_proposals as proposals
from . import form1_spa_reviews as service
from .models import Form1SPAReview as Record


class Form1SPAReviewFixture(fixtures.Form1AccountReviewFixture):
    spa_inputs=proposals.Form1SPAProposalTests.spa_inputs

    def setup_spa(self):
        self.account_record=self.review_accounts(self.prepare_accounts())
        for actor,actions in ((self.preparer,('prepare_form1_spa_reviews',)),
            (self.reviewer,('review_form1_spa_budget',)),(self.checker,('review_form1_spa_accounting',))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget',
                codename__in=[*actions,'view_form1_spa_reviews','export_form1_spa_reviews',
                    'view_form1_account_reviews','export_form1_account_reviews']))
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=['view_native_budget_actuals','export_native_budget_actuals',
                    'view_budget_summary_actuals','export_budget_summary_actuals']))

    def setUp(self):
        super().setUp(); self.setup_spa()

    def spa_document(self):
        from reportlab.pdfgen import canvas
        stream=BytesIO(); page=canvas.Canvas(stream)
        page.drawString(30,790,'SYNTHETIC SPA source-share/subdivision coverage; not legal percentage compliance')
        page.save()
        return SimpleUploadedFile('synthetic-spa-authority.pdf',stream.getvalue(),content_type='application/pdf')

    def prepare_spa(self,**changes):
        _,parts,coverage=self.spa_inputs()
        args=dict(account_review=self.account_record,actor=self.preparer,parts=parts,coverage=coverage,
            coverage_reference='Synthetic explicit six-subdivision coverage',reference='Synthetic source authority',
            evidence=self.spa_document(),expected_latest=0)
        args.update(changes); return service.prepare(**args)

    def decide_spa(self,record,role='budget',**changes):
        args=dict(actor=self.reviewer if role=='budget' else self.checker,role=role,approve=True,
            treatment_verified=True,authority='Synthetic designated '+role,note='Independent original source/subdivision review')
        args.update(changes); return service.review(record,**args)

    def approve_spa(self,record):
        return self.decide_spa(self.decide_spa(record),role='accounting')


class Form1SPAReviewTests(Form1SPAReviewFixture):
    def test_two_distinct_decisions_original_evidence_pure_verify_and_no_posting(self):
        before=JournalEntry.objects.count(); record=self.prepare_spa(); original=deepcopy(record.payload)
        with self.assertRaises(ValidationError): self.decide_spa(record,treatment_verified=False)
        record=self.decide_spa(record)
        self.assertEqual(record.status,'partially_approved')
        self.assertFalse(service.snapshot(record,self.checker)['independently_reviewed'])
        record=self.decide_spa(record,role='accounting')
        self.assertTrue(service.is_current(record,self.reviewer))
        retained=service.snapshot(record,self.checker,export=True)
        self.assertTrue(retained['independently_reviewed']); self.assertFalse(retained['form_issued'])
        self.assertEqual({row['role'] for row in retained['decisions']},{'budget','accounting'})
        self.assertEqual(service.evidence_bytes(record,self.checker),bytes(record.evidence))
        loaded=Record.objects.select_related(*service.RELATED).prefetch_related('decisions').get(pk=record.pk)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'): service.verify(loaded)
        with self.assertRaises(ValidationError): self.decide_spa(record)
        row=loaded.decisions.all()[0]
        with self.assertRaises(ValidationError): row.save()
        with self.assertRaises(ValidationError): row.delete()
        record.payload['reference']='Rewrite original'
        with self.assertRaises(ValidationError): record.save()
        with self.assertRaises(ValidationError): record.delete()
        self.assertEqual(loaded.payload,original); self.assertEqual(JournalEntry.objects.count(),before)

    def test_explicit_office_roles_independence_uat_and_export_only_sources(self):
        record=self.prepare_spa()
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',codename='review_form1_spa_budget'))
        with self.assertRaises(ValidationError): self.decide_spa(record,actor=self.preparer)
        with self.assertRaises(PermissionDenied): self.decide_spa(record,role='accounting',actor=self.reviewer)
        with self.assertRaises(PermissionDenied): self.prepare_spa(actor=self.checker)
        self.checker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        service.snapshot(record,self.checker)
        with self.assertRaises(PermissionDenied): self.decide_spa(record,role='accounting')
        self.checker.user_permissions.remove(*Permission.objects.filter(content_type__app_label='budget',
            codename__in=['view_form1_spa_reviews','view_form1_account_reviews']))
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals'))
        service.snapshot(record,self.checker,export=True)
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker)
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='export_native_budget_actuals'))
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker,export=True)
        self.assertNotIn('budget.prepare_budget_proposals',FINANCE_ROLE_PERMISSIONS['Accounting Form 1 SPA Reviewer'])

    def test_pending_spa_and_account_successors_block_new_approval_preserve_old_downloads(self):
        first=self.approve_spa(self.prepare_spa()); retained=service.snapshot(first,self.checker)
        pending=self.prepare_spa(expected_latest=1)
        self.assertFalse(service.is_current(first,self.checker))
        self.assertEqual(service.snapshot(first,self.checker),retained)
        self.prepare_accounts(expected_latest=1)
        with self.assertRaises(ValidationError): self.decide_spa(pending)
        returned=self.decide_spa(pending,approve=False,treatment_verified=False)
        self.assertEqual(returned.status,'returned')
        with self.assertRaises(ValidationError): self.decide_spa(returned,role='accounting')
        with self.assertRaises(ValidationError): self.prepare_spa(expected_latest=2)
        self.assertEqual(Record.objects.count(),2)

    def test_missing_coverage_return_and_rehashed_source_actor_state_evidence_tampering(self):
        _,parts,coverage=self.spa_inputs(); coverage[0]['coverage']='missing'
        record=self.prepare_spa(parts=parts,coverage=coverage)
        with self.assertRaises(ValidationError): self.decide_spa(record)
        record=self.decide_spa(record,approve=False,treatment_verified=False)
        loaded=Record.objects.select_related(*service.RELATED).prefetch_related('decisions').get(pk=record.pk)
        service.verify(loaded)
        for label in ('source','actor','state','evidence'):
            changed=deepcopy(loaded); rows=deepcopy(list(loaded.decisions.all()))
            if label=='source': changed.payload['source_account_review']['decision']['authority']='Invent authority'
            elif label=='actor':
                rows[0].actor_department_id=changed.fund.department_id
                rows[0].decision_checksum=checksum(service.decision(rows[0],changed))
            elif label=='state': changed.status='approved'
            else: changed.evidence=b'changed original document'
            changed.payload_checksum=checksum(changed.payload)
            with self.subTest(label=label),self.assertRaises(ValidationError): service.verify(changed,rows)
