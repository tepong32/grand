from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_treatments as fixtures
from . import form1_treatments as service
from .models import Form1TreatmentProposal, Form1TreatmentDecision


# Keep fixture helpers on a non-discoverable base, rather than repeating the
# service tests under a new class name in complete CI discovery.
from .test_form1_package_reviews import Form1PackageReviewFixture


class Form1TreatmentHTTPTests(Form1PackageReviewFixture):
    retain_original_package = fixtures.Form1TreatmentTests.retain_original_package
    findings = fixtures.Form1TreatmentTests.findings
    prepare_treatment = fixtures.Form1TreatmentTests.prepare_treatment
    decide_treatment = fixtures.Form1TreatmentTests.decide_treatment

    def path(self, name, record, *args):
        return reverse('budget:form1_treatment_'+name, args=(record.public_id, *args))

    def preparation_data(self, package, expected=0):
        data = dict(expected_latest=expected, reference='Synthetic original source findings',
            authority=SimpleUploadedFile('finding-authority.pdf', b'%PDF-1.4\nSynthetic authority'),
            reconciliation=SimpleUploadedFile('finding-reconciliation.pdf', b'%PDF-1.4\nSynthetic reconciliation'))
        for index, row in enumerate(self.findings(package)):
            for key, value in row.items():
                data['part'+str(index)+'-'+key] = value
        return data

    def review_data(self, role, action='approve'):
        data = dict(action=action, authority='Synthetic actual designated office reviewer',
            note='Synthetic factual decision; no arithmetic or form issuance')
        for key in service.CHECKS[role]:
            data[key+'_verified'] = 'true'
            data[key+'_basis'] = 'Synthetic inspection of exact original '+key
        return data

    def test_normal_intake_three_office_decisions_and_original_package_link(self):
        package = self.retain_original_package(claim=True)
        original = deepcopy(package.payload)
        journals = JournalEntry.objects.count()
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(reverse('budget:form1_package_detail', args=(package.public_id,))),
            self.path('history', package))
        page = self.client.get(self.path('prepare', package))
        self.assertContains(page, 'Original signed amount:')
        self.assertContains(page, 'Confirm the claimed source linkage')
        for part in package.payload['assembly']['payload']['philhealth_source']['payload']['parts']:
            self.assertContains(page, '<strong>'+part['amount']+'</strong>')
            self.assertContains(page, 'Part '+part['key'])
        self.assertNotContains(page, 'name="amount"')
        self.assertEqual(self.client.post(self.path('prepare', package), self.preparation_data(package)).status_code, 302)
        record = Form1TreatmentProposal.objects.get(package=package)
        self.assertContains(self.client.get(self.path('detail', record)), 'Awaiting independent findings')
        for role, actor in self.reviewers.items():
            self.client.force_login(actor)
            self.assertContains(self.client.get(self.path('detail', record)), 'Your '+role.title()+' factual review')
            self.assertEqual(self.client.post(self.path('review', record, role), self.review_data(role)).status_code, 302)
        page = self.client.get(self.path('detail', record))
        self.assertContains(page, 'All required factual reviews are complete')
        self.assertFalse(service.snapshot(record, self.treasurer)['review']['numeric_adjustment_approved'])
        package.refresh_from_db()
        self.assertEqual(package.payload, original)
        self.assertEqual(JournalEntry.objects.count(), journals)

    def test_invalid_part_stale_version_csrf_uat_and_revoked_source_access(self):
        package = self.retain_original_package()
        self.client.force_login(self.preparer)
        data = self.preparation_data(package)
        data['part0-part'] = 'substituted-original-part'
        self.assertEqual(self.client.post(self.path('prepare', package), data).status_code, 409)
        self.assertEqual(Form1TreatmentProposal.objects.count(), 0)
        record = self.prepare_treatment(package)
        self.assertEqual(self.client.post(self.path('prepare', package), self.preparation_data(package)).status_code, 409)
        self.assertEqual(Form1TreatmentProposal.objects.count(), 1)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(csrf.post(self.path('review', record, 'budget'), self.review_data('budget')).status_code, 403)
        group, _ = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)
        self.reviewer.groups.add(group)
        self.client.force_login(self.reviewer)
        self.assertNotContains(self.client.get(self.path('detail', record)), 'Your Budget factual review')
        self.assertEqual(self.client.post(self.path('review', record, 'budget'), self.review_data('budget')).status_code, 403)
        self.reviewer.groups.remove(group)
        self.treasurer.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',
            codename='view_budget_receipt_forecasts'))
        self.client.force_login(self.treasurer)
        for url in (self.path('history', package), self.path('detail', record)):
            self.assertEqual(self.client.get(url).status_code, 403)
        # Source read and export remain independently authorized by GRAND's
        # existing contract; revoking one does not silently revoke the other.
        self.assertEqual(self.client.get(self.path('export', record, 'json')).status_code, 200)
        self.treasurer.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',
            codename='export_budget_receipt_forecasts'))
        self.assertEqual(self.client.get(self.path('export', record, 'json')).status_code, 403)
        self.assertEqual(self.client.post(self.path('review', record, 'treasury'), {}).status_code, 400)
        self.assertEqual(self.client.post(self.path('review', record, 'treasury'), self.review_data('treasury')).status_code, 403)
        self.assertEqual(Form1TreatmentDecision.objects.count(), 0)

    def test_history_return_successor_and_complete_original_document_exports(self):
        package = self.retain_original_package(claim=True)
        first = self.prepare_treatment(package)
        self.decide_treatment(first)
        self.decide_treatment(first, 'accounting', approve=False)
        second = self.prepare_treatment(package, expected_latest=1,
            findings=self.findings(package, 'reject_overlap'))
        self.client.force_login(self.checker)
        page = self.client.get(self.path('history', package))
        self.assertContains(page, self.path('detail', first))
        self.assertContains(page, self.path('detail', second))
        response = self.client.get(self.path('export', first, 'zip'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-GRAND-Export-SHA256'], sha256(response.content).hexdigest())
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        with ZipFile(BytesIO(response.content)) as archive:
            envelope = json.loads(archive.read('package.json'))
            body = envelope['payload']
            self.assertEqual(body['treatment']['review']['status'], 'returned')
            self.assertEqual(body['original_package']['payload']['original_package']['payload'], package.payload)
            self.assertFalse(body['numeric_adjustment_approved'])
            self.assertFalse(body['form_issued'])
            for entry in body['documents']:
                attachment = first.attachments.get(key=entry['key'])
                self.assertEqual(archive.read(entry['path']), bytes(attachment.data))
            for entry in body['original_package']['payload']['documents']:
                self.assertEqual(sha256(archive.read(entry['path'])).hexdigest(), entry['sha256'])
        retained = json.loads(self.client.get(self.path('export', first, 'json')).content)
        self.assertEqual(retained, envelope)
        self.assertEqual(self.client.get(self.path('export', first, 'pdf')).status_code, 409)
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',
            codename='export_budget_receipt_forecasts'))
        self.assertEqual(self.client.get(self.path('detail', first)).status_code, 200)
        self.assertEqual(self.client.get(self.path('export', first, 'zip')).status_code, 403)

    def test_source_successor_blocks_new_approval_but_preserves_return_and_history(self):
        package = self.retain_original_package()
        record = self.prepare_treatment(package)
        self.prepare_forecast(expected_latest=1)
        self.client.force_login(self.reviewer)
        response = self.client.post(self.path('review', record, 'budget'), self.review_data('budget'))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'current original sources', status_code=409)
        self.assertEqual(Form1TreatmentDecision.objects.count(), 0)
        self.assertEqual(self.client.post(self.path('review', record, 'budget'),
            self.review_data('budget', 'return')).status_code, 302)
        self.assertContains(self.client.get(self.path('detail', record)), 'Returned for a successor')
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.post(self.path('prepare', package), self.preparation_data(package, 1)).status_code, 409)
        self.assertEqual(Form1TreatmentProposal.objects.count(), 1)
