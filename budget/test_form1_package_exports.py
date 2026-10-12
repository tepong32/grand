from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_package_reviews as fixtures
from . import form1_package_exports as output, form1_package_reviews as reviews
from .models import Form1PackageAttachment


class Form1PackageExportTests(fixtures.Form1PackageReviewFixture):
    def url(self, record, kind='zip'):
        return reverse('budget:form1_package_export', args=(record.public_id, kind))

    def test_complete_reviewed_three_office_export_original_bytes_and_http_archive(self):
        record = self.retain(); original = deepcopy(record.payload)
        before = JournalEntry.objects.count()
        for role in self.reviewers:
            self.decide_package(record, role)
        content, envelope = output.export(record, self.treasurer, kind='zip')
        body = envelope['payload']
        self.assertEqual(checksum(body), envelope['checksum'])
        self.assertEqual(body['original_package'], dict(payload=original, checksum=record.payload_checksum))
        state = body['internal_review']['payload']
        self.assertEqual(state['status'], 'reviewed'); self.assertEqual(len(state['decisions']), 3)
        self.assertEqual(checksum(state), body['internal_review']['checksum'])
        for flag in ('source_freshness_certified', 'statutorily_certified', 'chief_executive_approved', 'form_issued', 'cash_available'):
            self.assertIs(body[flag], False)
        members = body['original_package']['payload']['assembly']['payload']['members']
        self.assertEqual(len(members[0]['receipt']['rows']), 21)
        self.assertEqual(len(members[0]['expenditure']['rows']), 5)
        self.assertEqual(len(members[0]['net_ending']), 5)
        originals = {row.key: bytes(row.data) for row in record.attachments.all()}
        originals.update({'source:spa': bytes(record.spa_review.evidence),
            'source:account': bytes(record.spa_review.account_review.evidence)})
        self.assertEqual(len(body['documents']), len(originals))
        with ZipFile(BytesIO(content)) as archive:
            self.assertEqual(json.loads(archive.read('package.json')), envelope)
            self.assertEqual(set(archive.namelist()), {'package.json', *(row['path'] for row in body['documents'])})
            for row in body['documents']:
                data = archive.read(row['path'])
                self.assertEqual(data, originals[row['key']])
                self.assertEqual(len(data), row['size'])
                self.assertEqual(sha256(data).hexdigest(), row['sha256'])
        for actor in self.reviewers.values():
            serialized, retained = output.export(record, actor, kind='json')
            self.assertEqual(json.loads(serialized), envelope); self.assertEqual(retained, envelope)
        client = Client(); client.force_login(self.treasurer)
        response = client.get(self.url(record))
        self.assertEqual(response.status_code, 200); self.assertEqual(response.content, content)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertEqual(response['X-GRAND-Export-SHA256'], sha256(content).hexdigest())
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(client.post(self.url(record)).status_code, 405)
        self.assertEqual(client.get(self.url(record, 'unknown')).status_code, 400)
        self.assertEqual(record.payload, original); self.assertEqual(JournalEntry.objects.count(), before)

    def test_unknown_returned_stale_history_export_only_uat_and_revoked_or_corrupt_sources(self):
        self.ph_source, self.documents = self.ph_draft(attach=False)
        self.envelope = self.assembled(); record = self.retain()
        self.decide_package(record, approve=False, note='Return missing policy; retain unknown financial controls')
        content, original = output.export(record, self.checker, kind='json')
        self.assertEqual(original['payload']['internal_review']['payload']['status'], 'returned')
        self.assertFalse(original['payload']['original_package']['payload']['assembly']['payload']['calculation_coverage_complete'])
        self.assertIsNone(original['payload']['original_package']['payload']['assembly']['payload']['members'][0]['net_ending']['proposed'])
        self.prepare_forecast(expected_latest=1)
        self.checker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='budget', codename='view_form1_packages'))
        with self.assertRaises(PermissionDenied): reviews.snapshot(record, self.checker)
        self.assertEqual(output.export(record, self.checker, kind='json')[0], content)
        client = Client(); client.force_login(self.checker)
        self.assertEqual(client.get(self.url(record, 'json')).content, content)
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='budget', codename='export_budget_receipt_forecasts'))
        with self.assertRaises(PermissionDenied): output.export(record, self.checker, kind='zip')
        self.assertEqual(client.get(self.url(record)).status_code, 403)
        with self.assertRaises(PermissionDenied): output.export(record, self.maker, kind='json')
        with self.assertRaises(ValidationError): output.export(record, self.treasurer, kind='../zip')
        row = record.attachments.first()
        Form1PackageAttachment.objects.filter(pk=row.pk).update(data=b'corrupted original')
        with self.assertRaises(ValidationError): output.export(record, self.treasurer, kind='zip')
        client.force_login(self.treasurer)
        self.assertEqual(client.get(self.url(record)).status_code, 409)
