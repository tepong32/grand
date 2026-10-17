from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import connections, IntegrityError, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory import maintenance, maintenance_notices as service
from inventory.models import AssetMaintenanceEvidence, MaintenanceCorrectionNotice as Notice
from inventory.property_determinations import checksum
from inventory.services import asset_snapshot
from . import test_grand_maintenance


class MaintenanceNoticeTests(TestCase):
    databases = {'default', 'finance'}
    body = b'%PDF-synthetic correction source'

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='view_assetmaintenancecase'))

    def setUp(self):
        self.files = TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        for model in (AssetMaintenanceEvidence, Notice):
            replacement = patch.object(model._meta.get_field('file'), 'storage', FileSystemStorage(location=self.files.name))
            replacement.start()
            self.addCleanup(replacement.stop)
        self.case = maintenance.open_maintenance(actor=self.clerk, asset=self.asset,
            data={'reported_date': timezone.localdate(), 'problem': 'Repair concern'})
        self.case = maintenance.update_maintenance(actor=self.clerk, case=self.case, expected_version=1,
            data={'work_performed': 'Tested original work', 'documented_cost': '0'})
        self.case = maintenance.close_maintenance(actor=self.clerk, case=self.case, expected_version=2,
            action='completed', finished_date=timezone.localdate(), note='Original outcome', outcome='active')
        self.case.refresh_from_db()
        self.client.force_login(self.clerk)

    def upload(self):
        return SimpleUploadedFile('correction.pdf', self.body)

    def record(self, **changes):
        values = dict(actor=self.clerk, case=self.case, request_id=uuid4(),
            expected_source=checksum(service.case_basis(self.case)), explanation='Provider spelling needs checking.',
            source_reference='GSO recorded observation')
        values.update(changes)
        return service.record_notice(**values)

    def test_statement_changes_no_closed_fields_events_asset_or_finance(self):
        self.asset.refresh_from_db()
        before = service.case_basis(self.case), asset_snapshot(self.asset), self.asset.audit_events.count()
        with CaptureQueriesContext(connections['finance']) as finance:
            row = self.record()
        self.case.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual((service.case_basis(self.case), asset_snapshot(self.asset), self.asset.audit_events.count()), before)
        self.assertEqual(len(finance), 0)
        service.verify_notice(row)
        self.assertFalse(row.file)
        self.assertIn(Notice._meta.db_table, connections['default'].introspection.table_names())
        self.assertNotIn(Notice._meta.db_table, connections['finance'].introspection.table_names())
        self.assertFalse(Permission.objects.filter(content_type__app_label='inventory', content_type__model='maintenancecorrectionnotice').exists())

    def test_retry_is_exact_and_preserves_one_file(self):
        identity = uuid4()
        original = self.record(request_id=identity, upload=self.upload())
        retry = self.record(request_id=identity, upload=self.upload())
        self.assertEqual(original.pk, retry.pk)
        self.assertEqual(Notice.objects.count(), 1)
        self.assertEqual(len([p for p in Path(self.files.name).rglob('*') if p.is_file()]), 1)
        with self.assertRaises(ValidationError):
            self.record(request_id=identity, explanation='Different statement', upload=self.upload())
        Path(original.file.path).write_bytes(b'%PDF-broken source')
        with self.assertRaises(ValidationError):
            self.record(request_id=identity, upload=self.upload())
        Path(original.file.path).unlink()
        with self.assertRaises(ValidationError):
            self.record(request_id=identity, upload=self.upload())

    def test_direct_services_require_explicit_scope_and_deny_uat(self):
        for actor in (self.viewer, self.no_grant, self.super_no_grant, self.outsider):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.record(actor=actor)
        self.assertEqual(Notice.objects.count(), 0)

    def test_open_stale_and_corrupted_history_sources_fail_before_creating_notice(self):
        digest = checksum(service.case_basis(self.case))
        with self.assertRaises(ValidationError):
            self.record(expected_source='changed')
        last = self.case.events.last()
        self.case.events.filter(pk=last.pk).update(snapshot=[])
        with self.assertRaises(ValidationError):
            service.record_notice(actor=self.clerk, case=self.case, request_id=uuid4(), expected_source=digest,
                explanation='Do not accept bad source', source_reference='Observation')
        self.assertEqual(Notice.objects.count(), 0)

    def test_notices_are_immutable_and_metadata_constraint_is_enforced(self):
        row = self.record()
        row.explanation = 'Replace history'
        with self.assertRaises(ValidationError):
            row.save()
        with self.assertRaises(ValidationError):
            row.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notice.objects.filter(pk=row.pk).update(sha256='1'*64)

    def test_post_closed_notice_can_coexist_with_later_work_without_changing_it(self):
        later = maintenance.open_maintenance(actor=self.clerk, asset=self.asset,
            data={'reported_date': timezone.localdate(), 'problem': 'Later real work'})
        self.record()
        self.asset.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(self.asset.status, 'maintenance')
        self.assertEqual(later.status, 'open')
        with self.assertRaises(ValidationError):
            service.record_notice(actor=self.clerk, case=later, request_id=uuid4(), expected_source='',
                                  explanation='Not closed', source_reference='Observation')

    def test_authenticated_post_and_readonly_history_keep_original_cost_and_warn(self):
        url = reverse('inventory:maintenance-notice-new', args=[self.case.pk])
        response = self.client.get(url)
        token = response.context['form'].initial['source_token']
        self.assertEqual(self.client.post(url, {'source_token': token, 'explanation': '<script>correction</script>',
            'source_reference': 'Observation'}).status_code, 302)
        self.client.force_login(self.viewer)
        detail = self.client.get(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        self.assertContains(detail, 'Correction notices are recorded below.')
        self.assertContains(detail, '&lt;script&gt;correction&lt;/script&gt;')
        self.assertNotContains(detail, '<script>correction</script>')
        self.assertContains(detail, '0.00')
        self.assertNotContains(detail, 'Record a correction notice</a>')
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_tampered_notice_is_not_rendered_as_a_valid_statement_or_downloaded(self):
        row = self.record(upload=self.upload())
        Notice.objects.filter(pk=row.pk).update(explanation='FORGED CONTENT')
        detail = self.client.get(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        self.assertContains(detail, 'record-integrity check')
        self.assertNotContains(detail, 'FORGED CONTENT')
        response = self.client.get(reverse('inventory:maintenance-notice-evidence', args=[row.pk]))
        self.assertEqual(response.status_code, 404)

    def test_valid_download_checks_and_streams_same_file_and_rejects_damage(self):
        row = self.record(upload=self.upload())
        url = reverse('inventory:maintenance-notice-evidence', args=[row.pk])
        storage = Notice._meta.get_field('file').storage
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            response = self.client.get(url)
            self.assertEqual(b''.join(response.streaming_content), self.body)
            self.assertEqual(opened.call_count, 1)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('attachment', response['Content-Disposition'])
        Path(row.file.path).write_bytes(b'x' * len(self.body))
        self.assertEqual(self.client.get(url).status_code, 404)
        Path(row.file.path).unlink()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_recovery_checker_handles_optional_files_orphans_and_notice_corruption(self):
        self.record()
        row = self.record(upload=self.upload())
        output = StringIO()
        call_command('check_maintenance_notices', stdout=output)
        self.assertIn('"checked": 1', output.getvalue())
        orphan = Path(row.file.path).parent / 'orphan.pdf'
        orphan.write_bytes(self.body)
        with self.assertRaises(CommandError):
            call_command('check_maintenance_notices', stdout=StringIO())
        orphan.unlink()
        Notice.objects.filter(pk=row.pk).update(explanation='FORGED')
        with self.assertRaises(CommandError):
            call_command('check_maintenance_notices', stdout=StringIO())

    def test_invalid_and_oversized_statements_do_not_leave_files(self):
        for changes in ({'explanation': ''}, {'source_reference': ''}, {'explanation': 'x'*4001},
                        {'source_reference': 'x'*241}):
            with self.assertRaises(ValidationError):
                self.record(upload=self.upload(), **changes)
        self.assertEqual(Notice.objects.count(), 0)
        self.assertEqual(len([p for p in Path(self.files.name).rglob('*') if p.is_file()]), 0)

    def test_consistent_metadata_cannot_redirect_download_outside_its_case_namespace(self):
        row = self.record(upload=self.upload())
        source = Path(row.file.path)
        foreign = Path(self.files.name) / 'inventory/maintenance_notices' / str(uuid4()) / 'other.pdf'
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(self.body)
        for name in (foreign.relative_to(self.files.name).as_posix(), str(source),
                     'inventory/maintenance_notices/../outside.pdf'):
            row.file.name = name
            row.checksum = checksum(service.payload(row))
            Notice.objects.filter(pk=row.pk).update(file=name, checksum=row.checksum)
            response = self.client.get(reverse('inventory:maintenance-notice-evidence', args=[row.pk]))
            self.assertEqual(response.status_code, 404)

    def test_reference_notice_remains_possible_when_document_budget_is_full(self):
        aggregate = self.case.evidence
        # Budget queries are exercised separately under native competing writers.
        with patch.object(type(aggregate), 'count', return_value=20):
            with self.assertRaises(ValidationError):
                self.record(upload=self.upload())
            row = self.record()
        self.assertFalse(row.file)

    def test_signed_form_rejects_changed_expired_and_wrong_actor_tokens(self):
        from inventory.maintenance_notice_views import SALT
        url = reverse('inventory:maintenance-notice-new', args=[self.case.pk])
        token = self.client.get(url).context['form'].initial['source_token']
        fields = {'explanation': 'Observed correction', 'source_reference': 'Clerk observation'}
        self.assertContains(self.client.post(url, dict(fields, source_token=token+'changed')), 'expired or changed')
        data = signing.loads(token, salt=SALT)
        # Age only this form's signature; replacing signing.loads would also
        # invalidate the authenticated session before the form is reached.
        with patch.object(signing.TimestampSigner, 'timestamp', return_value=signing.b62_encode(int(time())-1801)):
            expired = signing.dumps(data, salt=SALT)
        self.assertContains(self.client.post(url, dict(fields, source_token=expired)), 'expired or changed')
        data['actor'] = self.viewer.pk
        response = self.client.post(url, dict(fields, source_token=signing.dumps(data, salt=SALT)))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Notice.objects.count(), 0)

    def test_notice_on_cancelled_case_does_not_reopen_or_restore_asset_twice(self):
        later = maintenance.open_maintenance(actor=self.clerk, asset=self.asset,
            data={'reported_date': timezone.localdate(), 'problem': 'Cancelled inspection'})
        later = maintenance.close_maintenance(actor=self.clerk, case=later, expected_version=1,
            action='cancelled', finished_date=timezone.localdate(), note='No work required')
        self.record(case=later, expected_source=checksum(service.case_basis(later)))
        later.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual(later.status, 'cancelled')
        self.assertEqual(later.events.count(), 2)
        self.assertEqual(self.asset.status, 'active')
