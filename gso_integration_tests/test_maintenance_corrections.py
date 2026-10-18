from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import Client, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from profiles.models import EmployeeProfile
from inventory import maintenance, maintenance_corrections as service
from inventory.models import MaintenanceCorrection as Correction
from inventory.property_determinations import checksum
from inventory.services import asset_snapshot
from . import test_maintenance_notices as fixtures


class MaintenanceCorrectionTests(TestCase):
    databases = {'default', 'finance'}
    upload = fixtures.MaintenanceNoticeTests.upload
    body = fixtures.MaintenanceNoticeTests.body

    @classmethod
    def setUpTestData(cls):
        fixtures.MaintenanceNoticeTests.setUpTestData.__func__(cls)
        cls.reviewer = get_user_model().objects.create_user(username='correction-reviewer', email='reviewer@example.test')
        EmployeeProfile.objects.filter(user=cls.reviewer).update(assigned_department=cls.gso)
        cls.review_permission = Permission.objects.get(content_type__app_label='inventory', codename='review_maintenance_correction')
        cls.reviewer.user_permissions.add(cls.review_permission, Permission.objects.get(
            content_type__app_label='inventory', codename='view_assetmaintenancecase'))
        # Profile assignment above uses a queryset update; clear the profile
        # cached by user creation so this direct-service actor matches a fresh login.
        cls.reviewer.refresh_from_db()

    def setUp(self):
        fixtures.MaintenanceNoticeTests.setUp(self)
        replacement = patch.object(Correction._meta.get_field('file'), 'storage', FileSystemStorage(location=self.files.name))
        replacement.start()
        self.addCleanup(replacement.stop)

    def values(self, **changes):
        return {**{name: getattr(self.case, name) for name in service.FIELDS}, 'provider': 'Corrected workshop', **changes}

    def propose(self, **changes):
        source, _ = service.basis(self.case)
        values = dict(actor=self.clerk, case=self.case, request_id=uuid4(), expected_source=checksum(source),
            data=self.values(), reason='Correct the documented workshop name.', source_reference='Retained service report',
            upload=self.upload())
        values.update(changes)
        return service.propose(**values)

    def approve(self, row, **changes):
        values = dict(actor=self.reviewer, row=row, expected_version=1, action='approved', note='Compared original and supplied correction.')
        values.update(changes)
        return service.decide(**values)

    def file_count(self):
        return len([p for p in Path(self.files.name).rglob('*') if p.is_file()])

    def test_approved_successor_changes_no_original_asset_custody_history_or_finance(self):
        self.asset.refresh_from_db()
        original = fixtures.service.case_basis(self.case), asset_snapshot(self.asset), self.asset.audit_events.count()
        with CaptureQueriesContext(connections['finance']) as finance:
            row = self.propose(data=self.values(documented_cost='12.34', cost_reference='Corrected invoice'))
            self.assertIsNone(service.basis(self.case)[1])
            row = self.approve(row)
            _, head = service.basis(self.case)
        self.case.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual((fixtures.service.case_basis(self.case), asset_snapshot(self.asset), self.asset.audit_events.count()), original)
        self.assertEqual(len(finance), 0)
        self.assertEqual(head.pk, row.pk)
        self.assertEqual(head.corrected_values['documented_cost'], '12.34')
        self.assertEqual(row.events.count(), 2)
        self.assertEqual(row.events.last().actor_id, self.reviewer.pk)
        self.assertIn(Correction._meta.db_table, connections['default'].introspection.table_names())
        self.assertNotIn(Correction._meta.db_table, connections['finance'].introspection.table_names())

    def test_review_requires_distinct_explicit_permission_and_independence(self):
        row = self.propose()
        with self.assertRaises(PermissionDenied):
            self.approve(row, actor=self.clerk)
        self.clerk.user_permissions.add(self.review_permission)
        with self.assertRaises(ValidationError):
            self.approve(row, actor=self.clerk)
        for actor in (self.outsider, self.no_grant, self.super_no_grant, self.viewer):
            actor.user_permissions.add(self.review_permission)
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.approve(row, actor=actor)
        row.refresh_from_db()
        self.assertEqual(row.status, 'proposed')
        self.assertEqual(row.events.count(), 1)

    def test_proposal_requires_existing_owner_grant_and_denies_uat(self):
        for actor in (self.outsider, self.no_grant, self.super_no_grant, self.viewer, self.reviewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.propose(actor=actor)
        self.assertEqual(Correction.objects.count(), 0)
        self.assertEqual(self.file_count(), 0)

    def test_exact_retry_retains_one_file_even_after_independent_decision(self):
        identity = uuid4()
        row = self.propose(request_id=identity)
        self.assertEqual(self.propose(request_id=identity).pk, row.pk)
        row = self.approve(row)
        retry = self.propose(request_id=identity, expected_source=checksum(row.source_snapshot), data=row.corrected_values)
        self.assertEqual(retry.pk, row.pk)
        self.assertEqual(Correction.objects.count(), 1)
        self.assertEqual(self.file_count(), 1)
        with self.assertRaises(ValidationError):
            self.propose(request_id=identity, reason='Different request content')

    def test_competing_proposal_is_stale_after_another_approval_but_can_be_rejected(self):
        first, second = self.propose(), self.propose(data=self.values(provider='Another proposed workshop'))
        self.approve(first)
        with self.assertRaises(ValidationError):
            self.approve(second)
        rejected = self.approve(second, action='rejected', note='Earlier approval changed the basis; submit a fresh proposal.')
        self.assertEqual(rejected.status, 'rejected')
        self.assertEqual(service.basis(self.case)[1].pk, first.pk)

    def test_successor_pins_prior_approval_without_rewriting_it(self):
        first = self.approve(self.propose())
        second = self.propose(data=self.values(provider='Latest supported workshop', documented_cost=None))
        self.assertEqual(second.predecessor_id, first.pk)
        second = self.approve(second)
        first.refresh_from_db()
        self.assertEqual(first.corrected_values['provider'], 'Corrected workshop')
        self.assertEqual(service.basis(self.case)[1].pk, second.pk)
        self.assertEqual(first.events.count(), 2)

    def test_zero_and_unknown_costs_remain_distinct(self):
        zero = self.approve(self.propose(data=self.values(documented_cost='0.00')))
        unknown = self.approve(self.propose(data=self.values(provider='Corrected again', documented_cost=None)))
        self.assertEqual(zero.corrected_values['documented_cost'], '0.00')
        self.assertIsNone(unknown.corrected_values['documented_cost'])

    def test_incomplete_invalid_noop_and_unsafe_action_inputs_leave_no_files(self):
        missing = self.values()
        missing.pop('provider')
        invalid = [missing, self.values(status='active'), self.values(documented_cost=1.2),
            self.values(documented_cost='NaN'), self.values(documented_cost='-1'),
            self.values(documented_cost='0.001'), self.values(documented_cost='1', cost_reference=''),
            self.values(finished_date=timezone.localdate()+timedelta(days=1)),
            self.values(problem='x'*4001), {name: getattr(self.case, name) for name in service.FIELDS}]
        for data in invalid:
            with self.subTest(data=str(data)[:70]), self.assertRaises(ValidationError):
                self.propose(data=data)
        for changes in ({'reason': ''}, {'reason': 'x'*4001}, {'upload': None}, {'expected_source': 'stale'}):
            with self.assertRaises(ValidationError):
                self.propose(**changes)
        self.assertEqual(Correction.objects.count(), 0)
        self.assertEqual(self.file_count(), 0)

    def test_immutable_content_and_decisions_detect_tampering(self):
        row = self.propose()
        row.reason = 'Replace retained history'
        with self.assertRaises(ValidationError):
            row.save()
        with self.assertRaises(ValidationError):
            row.delete()
        event = row.events.first()
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        Correction.objects.filter(pk=row.pk).update(reason='FORGED CORRECTION')
        with self.assertRaises(ValidationError):
            self.approve(row)
        response = self.client.get(reverse('inventory:maintenance-correction-detail', args=[row.pk]))
        self.assertContains(response, 'failed verification')
        self.assertNotContains(response, 'FORGED CORRECTION')

    def test_changed_original_and_stale_version_cannot_be_approved(self):
        row = self.propose()
        with self.assertRaises(ValidationError):
            self.approve(row, expected_version=2)
        type(self.case).objects.filter(pk=self.case.pk).update(provider='Changed original')
        with self.assertRaises(ValidationError):
            self.approve(row)
        row.refresh_from_db()
        self.assertEqual(row.status, 'proposed')

    def test_missing_or_modified_evidence_blocks_approval_and_download(self):
        row = self.propose()
        url = reverse('inventory:maintenance-correction-evidence', args=[row.pk])
        path = Path(row.file.path)
        path.write_bytes(b'x'*len(self.body))
        with self.assertRaises(ValidationError):
            self.approve(row)
        self.assertEqual(self.client.get(url).status_code, 404)
        path.unlink()
        with self.assertRaises(ValidationError):
            self.approve(row)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.approve(row, action='rejected').status, 'rejected')

    def test_original_evidence_loss_and_changed_approved_history_fail_closed(self):
        later = maintenance.open_maintenance(actor=self.clerk, asset=self.asset,
            data={'reported_date': timezone.localdate(), 'problem': 'Second completed work'})
        evidence = maintenance.attach_maintenance_evidence(actor=self.clerk, case=later,
            expected_version=1, upload=self.upload(), note='Original report')
        later = maintenance.update_maintenance(actor=self.clerk, case=later, expected_version=2,
            data={'work_performed': 'Original second work', 'documented_cost': '0'})
        self.case = maintenance.close_maintenance(actor=self.clerk, case=later, expected_version=3,
            action='completed', finished_date=timezone.localdate(), note='Original completion', outcome='active')
        row = self.propose()
        Path(evidence.file.path).unlink()
        with self.assertRaises(ValidationError):
            self.approve(row)

    def test_http_propose_independent_approval_and_uat_read_keep_original_visible(self):
        url = reverse('inventory:maintenance-correction-new', args=[self.case.pk])
        token = self.client.get(url).context['form'].initial['source_token']
        fields = dict(self.values(documented_cost='12.34', cost_reference='Corrected invoice'),
            source_token=token, reason='Correct invoice amount', source_reference='Service report', upload=self.upload())
        response = self.client.post(url, fields)
        self.assertEqual(response.status_code, 302)
        row = Correction.objects.get()
        detail = reverse('inventory:maintenance-correction-detail', args=[row.pk])
        self.assertEqual(self.client.post(detail, {'action': 'approved', 'expected_version': 1, 'note': 'Self'}).status_code, 403)
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(detail), 'Independent review')
        self.assertEqual(self.client.post(detail, {'action': 'approved', 'expected_version': 1, 'note': 'Independent comparison'}).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(detail, {'action': 'approved'}).status_code, 403)
        page = self.client.get(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        self.assertContains(page, 'Current approved documentary correction')
        self.assertContains(page, '12.34')
        self.assertContains(page, '0.00')
        self.assertContains(page, 'Original work record')
        self.assertContains(page, 'Review the current correction below')
        self.assertNotContains(page, 'Propose corrected information</a>')

    def test_authenticated_scope_csrf_and_signed_actor_are_enforced(self):
        url = reverse('inventory:maintenance-correction-new', args=[self.case.pk])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.clerk)
        self.assertEqual(csrf.post(url, {}).status_code, 403)
        response = self.client.get(url)
        token = response.context['form'].initial['source_token']
        fields = dict(self.values(), reason='Correction', source_reference='Report', upload=self.upload(), source_token=token+'bad')
        self.assertContains(self.client.post(url, fields), 'expired or changed')
        from inventory.maintenance_correction_views import SALT
        data = signing.loads(token, salt=SALT)
        data['actor'] = self.reviewer.pk
        fields.update(source_token=signing.dumps(data, salt=SALT), upload=self.upload())
        self.assertEqual(self.client.post(url, fields).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(Correction.objects.count(), 0)

    def test_download_uses_one_checked_handle_and_preserves_headers_and_access(self):
        row = self.propose()
        url = reverse('inventory:maintenance-correction-evidence', args=[row.pk])
        storage = Correction._meta.get_field('file').storage
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            response = self.client.get(url)
            self.assertEqual(b''.join(response.streaming_content), self.body)
            self.assertEqual(opened.call_count, 1)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('attachment', response['Content-Disposition'])
        self.client.force_login(self.outsider)
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(opened.call_count, 0)

    def test_path_guard_rejects_even_internally_consistent_unsafe_metadata(self):
        row = self.propose()
        outside = Path(self.files.name)/'outside.pdf'
        outside.write_bytes(self.body)
        row.file.name = 'outside.pdf'
        row.content_checksum = checksum(service.content(row))
        Correction.objects.filter(pk=row.pk).update(file=row.file.name, content_checksum=row.content_checksum)
        event = row.events.first()
        event.snapshot = service.event_snapshot(row, event)
        event.checksum = checksum(event.snapshot)
        row.events.filter(pk=event.pk).update(snapshot=event.snapshot, checksum=event.checksum)
        self.assertEqual(self.client.get(reverse('inventory:maintenance-correction-evidence', args=[row.pk])).status_code, 404)
        with self.assertRaises(ValidationError):
            self.approve(row)

    def test_recovery_reports_orphans_and_changed_records_without_repair(self):
        row = self.propose()
        output = StringIO()
        call_command('check_maintenance_corrections', stdout=output)
        self.assertIn('"checked": 1', output.getvalue())
        orphan = Path(row.file.path).parent/'orphan.pdf'
        orphan.write_bytes(self.body)
        with self.assertRaises(CommandError):
            call_command('check_maintenance_corrections', stdout=StringIO())
        self.assertTrue(orphan.exists())
        orphan.unlink()
        row.events.update(note='Changed history')
        with self.assertRaises(CommandError):
            call_command('check_maintenance_corrections', stdout=StringIO())

    def test_notices_and_corrections_share_document_budget_and_reference_notice_remains_possible(self):
        self.propose()
        for _ in range(19):
            fixtures.MaintenanceNoticeTests.record(self, upload=self.upload())
        for operation in (lambda: self.propose(), lambda: fixtures.MaintenanceNoticeTests.record(self, upload=self.upload())):
            with self.assertRaises(ValidationError):
                operation()
        self.assertFalse(fixtures.MaintenanceNoticeTests.record(self).file)
        self.assertEqual(self.file_count(), 20)

    def test_changed_approved_status_cannot_hide_history_or_silently_restore_original(self):
        row = self.approve(self.propose())
        Correction.objects.filter(pk=row.pk).update(status='rejected')
        with self.assertRaises(ValidationError):
            service.basis(self.case)
        page = self.client.get(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        self.assertContains(page, 'independent decision no longer matches')
        self.assertNotContains(page, 'No independently approved correction is in effect.')

    def test_changed_approved_file_blocks_current_values_and_further_successors(self):
        row = self.approve(self.propose())
        Path(row.file.path).write_bytes(b'x'*len(self.body))
        with self.assertRaises(ValidationError):
            service.basis(self.case)
        with self.assertRaises(ValidationError):
            self.propose(data=self.values(provider='Another unsupported successor'))
        page = self.client.get(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        self.assertContains(page, 'failed its integrity check')
        self.assertNotContains(page, 'Current approved documentary correction')

    def test_cancelled_case_correction_never_replays_the_original_cancellation(self):
        later = maintenance.open_maintenance(actor=self.clerk, asset=self.asset,
            data={'reported_date': timezone.localdate(), 'problem': 'Cancelled work request'})
        self.case = maintenance.close_maintenance(actor=self.clerk, case=later, expected_version=1,
            action='cancelled', finished_date=timezone.localdate(), note='Original cancellation')
        self.asset.refresh_from_db()
        before = asset_snapshot(self.asset), self.asset.audit_events.count(), fixtures.service.case_basis(self.case)
        self.approve(self.propose())
        self.asset.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual((asset_snapshot(self.asset), self.asset.audit_events.count(), fixtures.service.case_basis(self.case)), before)

    def test_expired_signed_form_cannot_submit_a_proposal(self):
        from time import time
        from inventory.maintenance_correction_views import SALT
        url = reverse('inventory:maintenance-correction-new', args=[self.case.pk])
        token = self.client.get(url).context['form'].initial['source_token']
        data = signing.loads(token, salt=SALT)
        with patch.object(signing.TimestampSigner, 'timestamp', return_value=signing.b62_encode(int(time())-1801)):
            expired = signing.dumps(data, salt=SALT)
        fields = dict(self.values(), reason='Keep my entered correction', source_reference='Report',
                      upload=self.upload(), source_token=expired)
        page = self.client.post(url, fields)
        self.assertContains(page, 'expired or changed')
        self.assertContains(page, 'Keep my entered correction')
        self.assertEqual(Correction.objects.count(), 0)

    def test_positive_cost_error_identifies_cost_reference_and_preserves_entries(self):
        url = reverse('inventory:maintenance-correction-new', args=[self.case.pk])
        token = self.client.get(url).context['form'].initial['source_token']
        fields = dict(self.values(documented_cost='12.34', cost_reference=''),
            source_token=token, reason='Keep this explanation', source_reference='A correction basis is already supplied',
            upload=self.upload())
        page = self.client.post(url, fields)
        self.assertContains(page, 'Enter Cost reference (the invoice or cost document)')
        self.assertContains(page, 'Keep this explanation')
        self.assertContains(page, 'select the supporting file again')
        self.assertEqual(Correction.objects.count(), 0)
        self.assertEqual(self.file_count(), 0)


class MaintenanceCorrectionDecisionFormTests(SimpleTestCase):
    def test_review_has_no_implicit_approval_and_requires_an_explicit_decision(self):
        from inventory.maintenance_correction_forms import CorrectionDecisionForm
        form = CorrectionDecisionForm({'expected_version': 1, 'note': 'Entered findings'})
        self.assertFalse(form.is_valid())
        self.assertIn('action', form.errors)
        self.assertEqual(list(form.fields['action'].choices)[0], ('', 'Choose a decision'))
