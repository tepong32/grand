from copy import deepcopy
from datetime import date
from io import BytesIO

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.utils import timezone
from django.urls import reverse
from django.test import Client
from reportlab.pdfgen import canvas

from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_ROLE_PERMISSIONS, FINANCE_UAT_VIEWER_GROUP
from . import form1_signing as service
from . import test_form1_package_reviews as fixtures
from .models import Form1SigningPreparation as Preparation, Form1SigningEvidence as Evidence, Form1SigningReview as Review


class Form1SigningFixture(fixtures.Form1PackageReviewFixture):
    def setUp(self):
        super().setUp()
        for actor, actions in ((self.preparer, ('prepare', 'view', 'export')),
                               (self.reviewer, ('review', 'view', 'export')),
                               (self.checker, ('view', 'export'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget',
                codename__in=[action+'_form1_signing_preparations' for action in actions]))

    def reviewed_package(self):
        package = self.retain()
        for role in self.reviewers: self.decide_package(package, role)
        return package

    def people(self):
        return {role: dict(name='Synthetic '+title, position=title,
            authority_reference='Synthetic designation authority for '+role,
            valid_from=date(2000,1,1), valid_to=None) for role,title in service.ROLES.items()}

    def designation_documents(self):
        result = {}
        for role in service.ROLES:
            buffer = BytesIO(); document = canvas.Canvas(buffer, invariant=1)
            document.drawString(30,750,'SYNTHETIC DESIGNATION TEST ONLY - '+role)
            document.save()
            result[role] = SimpleUploadedFile(role+'.pdf',buffer.getvalue(),content_type='application/pdf')
        return result

    def signing(self, package, **changes):
        args = dict(package=package, actor=self.preparer, document_date=timezone.localtime().date(),
            lgu='SYNTHETIC TEST MUNICIPALITY - Peña', signatories=self.people(), documents=self.designation_documents(),
            reference='Synthetic final-preparation prerequisite, not a signature or issued copy', expected_latest=0)
        args.update(changes)
        return service.prepare(**args)

    def checks(self):
        return {key: dict(verified=True,basis='Synthetic independently inspected '+key) for key in service.CHECKS}

    def decide_signing(self, preparation, **changes):
        args = dict(preparation=preparation,actor=self.reviewer,approve=True,checks=self.checks(),
                    note='Synthetic independent designation/source review; no statutory signing')
        args.update(changes)
        return service.review(**args)


class Form1SigningTests(Form1SigningFixture):
    def test_retains_exact_roles_documents_review_and_finance_isolation_without_issuance(self):
        package = self.reviewed_package(); original = deepcopy(package.payload)
        before = JournalEntry.objects.count()
        self.client.force_login(self.preparer)
        history_url = reverse('budget:form1_signing_history', args=[package.public_id])
        entry = self.client.get(history_url)
        self.assertContains(entry, 'Local Planning and Development Coordinator')
        self.assertContains(entry, 'class="form-control"')
        data = dict(expected_latest=0, document_date=timezone.localtime().date().isoformat(),
            lgu='SYNTHETIC TEST MUNICIPALITY - Peña', reference='Synthetic HTTP designation preparation')
        uploads = self.designation_documents()
        for role, person in self.people().items():
            data.update({role+'_'+key: value.isoformat() if type(value) is date else value or ''
                         for key, value in person.items()})
            data[role+'_document'] = uploads[role]
        response = self.client.post(history_url, data)
        preparation = Preparation.objects.get(package=package)
        detail_url = reverse('budget:form1_signing_detail', args=[preparation.public_id])
        self.assertRedirects(response, detail_url, fetch_redirect_response=False)
        detail = self.client.get(detail_url)
        self.assertContains(detail, 'No statutory signature')
        self.assertContains(detail, 'Awaiting independent preparation review')
        headings = [detail.content.index(('<h2 class="h5">'+title+'</h2>').encode()) for title in service.ROLES.values()]
        self.assertEqual(headings, sorted(headings))
        self.assertEqual(preparation._state.db,'finance')
        self.assertEqual(set(preparation.payload['signatories']),set(service.ROLES))
        self.assertEqual(preparation.evidence.count(),5)
        self.assertEqual(service.snapshot(preparation,self.preparer)['status'],'prepared')
        for role in service.ROLES:
            content,metadata = service.designation_document(preparation,role,self.checker)
            self.assertTrue(content.startswith(b'%PDF-'))
            self.assertEqual(len(content),metadata['size'])
        self.client.force_login(self.checker)
        downloaded = self.client.get(reverse('budget:form1_signing_document', args=[preparation.public_id, 'accountant']))
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(b''.join(downloaded.streaming_content), service.designation_document(preparation,'accountant',self.checker)[0])
        self.assertEqual(downloaded['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(downloaded['X-GRAND-Export-SHA256'], service.snapshot(preparation,self.checker)['payload']['signatories']['accountant']['evidence']['sha256'])
        # Exhausting Django's test-client stream already closes the response
        # with its connection-signal guard. A second close aborts MySQL atomics.
        self.client.force_login(self.reviewer)
        review_url = reverse('budget:form1_signing_review', args=[preparation.public_id])
        self.assertContains(self.client.get(detail_url), 'Approve preparation evidence')
        self.assertEqual(self.client.get(review_url).status_code, 405)
        guarded = Client(enforce_csrf_checks=True); guarded.force_login(self.reviewer)
        self.assertEqual(guarded.post(review_url, {}).status_code, 403)
        data = dict(action='approve', note='Synthetic independent HTTP designation evidence review')
        for key in service.CHECKS:
            data[key+'_verified'] = 'true'; data[key+'_basis'] = 'Synthetic inspected original '+key
        self.assertRedirects(self.client.post(review_url, data), detail_url, fetch_redirect_response=False)
        self.assertContains(self.client.get(detail_url), 'Retained independent review')
        decision = Review.objects.get(preparation=preparation)
        retained = service.snapshot(preparation,self.checker)
        self.assertEqual(retained['status'],'reviewed_preparation')
        for flag in service.FLAGS:
            self.assertIs(retained[flag],False)
            self.assertIs(retained['payload'][flag],False)
        self.assertEqual(decision._state.db,'finance')
        self.assertEqual(retained['payload']['source']['package_checksum'],package.payload_checksum)
        self.assertEqual(JournalEntry.objects.count(),before)
        package.refresh_from_db();self.assertEqual(package.payload,original)
        for item in (preparation,decision,preparation.evidence.first()):
            with self.assertRaises(ValidationError): item.save()
            with self.assertRaises(ValidationError): item.delete()
        finance_tables=connections['finance'].introspection.table_names()
        default_tables=connections['default'].introspection.table_names()
        for model in (Preparation,Evidence,Review):
            self.assertIn(model._meta.db_table,finance_tables)
            self.assertNotIn(model._meta.db_table,default_tables)

    def test_rejects_unreviewed_sources_form2_roles_invalid_dates_and_incomplete_checks(self):
        package = self.retain()
        with self.assertRaises(ValidationError): self.signing(package)
        for role in self.reviewers:self.decide_package(package,role)
        for changes in ({'lgu':'Guessed department label'}, {'expected_latest':True},
                        {'document_date':'not-a-date'}, {'document_date':date(1999,1,1)}):
            with self.assertRaises(ValidationError): self.signing(package,**changes)
        wrong=self.people();wrong['department_head']=wrong.pop('planning_coordinator')
        with self.assertRaises(ValidationError):self.signing(package,signatories=wrong)
        expired=self.people();expired['accountant']['valid_to']=date(2000,1,1)
        with self.assertRaises(ValidationError):self.signing(package,signatories=expired)
        documents=self.designation_documents();documents.pop('chief_executive')
        with self.assertRaises(ValidationError):self.signing(package,documents=documents)
        self.assertEqual(Preparation.objects.count(),0)
        self.assertEqual(Evidence.objects.count(),0)
        preparation=self.signing(package)
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',
            codename='review_form1_signing_preparations'))
        with self.assertRaises(ValidationError):self.decide_signing(preparation,actor=self.preparer)
        checks=self.checks();checks['authority_documents']['verified']=False
        with self.assertRaises(ValidationError):self.decide_signing(preparation,checks=checks)
        checks['authority_documents']['verified']='true'
        with self.assertRaises(ValidationError):self.decide_signing(preparation,checks=checks)
        self.assertFalse(Review.objects.exists())

    def test_mutation_uat_office_and_original_export_permissions_remain_separate(self):
        package=self.reviewed_package()
        group=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0]
        self.preparer.groups.add(group)
        with self.assertRaises(PermissionDenied):self.signing(package)
        self.preparer.groups.remove(group)
        preparation=self.signing(package)
        for action in ('prepare','review','view','export'):
            self.checker.user_permissions.add(Permission.objects.get(content_type__app_label='budget',
                codename=action+'_form1_signing_preparations'))
        with self.assertRaises(PermissionDenied):self.signing(package,actor=self.checker,expected_latest=1)
        with self.assertRaises(PermissionDenied):self.decide_signing(preparation,actor=self.checker)
        self.client.force_login(self.checker)
        self.assertEqual(self.client.post(reverse('budget:form1_signing_history',args=[package.public_id]),{}).status_code,403)
        self.reviewer.groups.add(group)
        with self.assertRaises(PermissionDenied):self.decide_signing(preparation)
        self.assertEqual(service.snapshot(preparation,self.reviewer)['status'],'prepared')
        self.client.force_login(self.reviewer)
        self.assertNotContains(self.client.get(reverse('budget:form1_signing_detail',args=[preparation.public_id])), 'Approve preparation evidence')
        self.reviewer.groups.remove(group)
        source_export=Permission.objects.get(content_type__app_label='budget',codename='export_budget_receipt_forecasts')
        self.checker.user_permissions.remove(source_export)
        self.assertEqual(service.snapshot(preparation,self.checker)['status'],'prepared')
        with self.assertRaises(PermissionDenied):service.snapshot(preparation,self.checker,export=True)
        with self.assertRaises(PermissionDenied):service.designation_document(preparation,'treasurer',self.checker)
        self.client.force_login(self.checker)
        self.assertEqual(self.client.get(reverse('budget:form1_signing_document',args=[preparation.public_id,'treasurer'])).status_code,403)
        self.checker.user_permissions.add(source_export)
        new_view=Permission.objects.get(content_type__app_label='budget',codename='view_form1_signing_preparations')
        self.checker.user_permissions.remove(new_view)
        with self.assertRaises(PermissionDenied):service.snapshot(preparation,self.checker)
        self.assertEqual(service.snapshot(preparation,self.checker,export=True)['status'],'prepared')
        self.assertFalse(Review.objects.exists())
        for role in ('Budget Form 1 Designation Preparer','Budget Form 1 Designation Reviewer',
                     'Accounting Form 1 Designation Viewer','Treasury Form 1 Designation Viewer'):
            grants=FINANCE_ROLE_PERMISSIONS[role]
            self.assertIn('budget.view_form1_signing_preparations',grants)
            if role.endswith('Viewer'):
                self.assertNotIn('budget.prepare_form1_signing_preparations',grants)
                self.assertNotIn('budget.review_form1_signing_preparations',grants)

    def test_successors_stale_sources_and_returns_retain_original_decisions(self):
        package=self.reviewed_package();first=self.signing(package)
        second=self.signing(package,expected_latest=1)
        with self.assertRaises(ValidationError):self.decide_signing(first)
        returned=self.decide_signing(first,approve=False,note='Superseded preparation; retain original designation evidence')
        self.assertEqual(service.snapshot(first,self.reviewer)['status'],'returned')
        self.assertIs(returned.payload['source_current_observed'],None)
        approved=self.decide_signing(second)
        original=service.snapshot(second,self.reviewer)
        with self.assertRaises(ValidationError):self.decide_signing(second)
        self.prepare_forecast(expected_latest=1)
        self.assertEqual(service.snapshot(second,self.reviewer),original)
        with self.assertRaises(ValidationError):self.signing(package,expected_latest=2)
        self.assertEqual(service.snapshot(second,self.reviewer)['review']['payload_checksum'],approved.payload_checksum)

    def test_corrupt_bytes_and_rehashed_role_or_review_changes_fail_closed(self):
        package=self.reviewed_package();preparation=self.signing(package)
        evidence=preparation.evidence.get(role='accountant');original=bytes(evidence.data)
        Evidence.objects.filter(pk=evidence.pk).update(data=b'corrupted original')
        with self.assertRaises(ValidationError):service.snapshot(preparation,self.reviewer)
        Evidence.objects.filter(pk=evidence.pk).update(data=original)
        payload=deepcopy(preparation.payload)
        changed=deepcopy(payload);changed['signatories']['accountant']['valid_to']='2000-01-01'
        Preparation.objects.filter(pk=preparation.pk).update(payload=changed,payload_checksum=checksum(changed))
        with self.assertRaises(ValidationError):service.snapshot(preparation,self.reviewer)
        Preparation.objects.filter(pk=preparation.pk).update(payload=payload,payload_checksum=checksum(payload))
        decision=self.decide_signing(preparation)
        changed=deepcopy(decision.payload);changed['identity']['actor_id']=self.preparer.pk
        Review.objects.filter(pk=decision.pk).update(actor_id=self.preparer.pk,payload=changed,payload_checksum=checksum(changed))
        with self.assertRaises(ValidationError):service.snapshot(preparation,self.reviewer)
