from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.urls import reverse
from django.test import Client
from pypdf import PdfReader

from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP, FINANCE_ROLE_PERMISSIONS
from . import test_form1_signing as fixtures, form1_unsigned_copies as service, form1_unsigned_output as output
from . import form1_signing as signing
from .models import Form1UnsignedCopy as Copy


class Form1UnsignedFixture(fixtures.Form1SigningFixture):
    def setUp(self):
        super().setUp()
        for actor in (self.preparer, self.reviewer, self.checker):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget',
                codename__in=[action+'_form1_signing_copies' for action in ('release', 'view', 'export')]))

    def unsigned_preparation(self):
        package = self.reviewed_package()
        preparation = self.signing(package)
        self.decide_signing(preparation)
        return preparation

    def release_copy(self, preparation, **changes):
        args = dict(preparation=preparation, actor=self.reviewer,
                    reference='Synthetic independently released unsigned Form 1 for physical signing')
        args.update(changes)
        return service.release(**args)

    def copy_role_only(self, actor, name):
        actor.groups.clear(); actor.user_permissions.clear()
        for key in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
            actor.__dict__.pop(key, None)
        for value in FINANCE_ROLE_PERMISSIONS[name]:
            app, codename = value.split('.')
            actor.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))


class Form1UnsignedCopyTests(Form1UnsignedFixture):
    def test_release_retains_complete_unsigned_bytes_and_original_sources_without_posting(self):
        preparation = self.unsigned_preparation()
        original = signing.snapshot(preparation, self.reviewer)
        before = JournalEntry.objects.count()
        self.copy_role_only(self.reviewer, 'Budget Form 1 Signing Copy Releaser')
        self.client.force_login(self.reviewer)
        release_url = reverse('budget:form1_unsigned_release', args=[preparation.public_id])
        detail_url = reverse('budget:form1_signing_detail', args=[preparation.public_id])
        self.assertContains(self.client.get(detail_url), 'Release unsigned signing copy')
        self.assertEqual(self.client.get(release_url).status_code, 405)
        guarded = Client(enforce_csrf_checks=True); guarded.force_login(self.reviewer)
        self.assertEqual(guarded.post(release_url, {'reference':'Synthetic unsigned copy'}).status_code,403)
        response = self.client.post(release_url, {'reference':'Synthetic independently released unsigned Form 1 for physical signing'})
        record = Copy.objects.get(preparation=preparation)
        self.assertRedirects(response, detail_url, fetch_redirect_response=False)
        self.assertContains(self.client.get(detail_url),'Download original unsigned signing PDF')
        self.client.force_login(self.checker)
        response = self.client.get(reverse('budget:form1_unsigned_document',args=[record.public_id]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(b''.join(response.streaming_content),bytes(record.document))
        self.assertEqual(response['X-GRAND-Export-SHA256'],record.document_checksum)
        retained = service.snapshot(record, self.checker)
        self.assertTrue(retained['unsigned_copy_issued'])
        for key in output.FALSE_FLAGS:
            self.assertIs(retained[key], False)
        self.assertEqual(signing.snapshot(preparation, self.reviewer), original)
        self.assertEqual(JournalEntry.objects.count(), before)
        self.assertEqual(record._state.db, 'finance')
        self.assertIn(Copy._meta.db_table, connections['finance'].introspection.table_names())
        self.assertNotIn(Copy._meta.db_table, connections['default'].introspection.table_names())
        envelope = dict(payload=retained['payload'], checksum=retained['payload_checksum'])
        untouched = deepcopy(envelope)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            first = output.render_pdf(envelope)
            self.assertEqual(first, output.render_pdf(envelope))
        self.assertEqual(first, bytes(record.document))
        self.assertEqual(envelope, untouched)
        reader = PdfReader(BytesIO(first))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        normalized = ' '.join(text.split())
        self.assertNotIn('INCOMPLETE DRAFT', text)
        self.assertNotIn('not ready for signing', text)
        self.assertNotIn('Unknown', text)
        for role, title in signing.ROLES.items():
            self.assertIn(title, normalized)
            self.assertIn(preparation.payload['signatories'][role]['name'], normalized)
        self.assertIn(output.CERTIFICATION, ' '.join(text.split()))
        for index, page in enumerate(reader.pages, 1):
            self.assertIn('UNSIGNED', page.extract_text())
            self.assertIn(f'Page {index} of {len(reader.pages)}', page.extract_text())
        body = retained['payload']['original_package']['payload']['original_package']['payload']['assembly']['payload']
        for member in body['members']:
            for row in member['receipt']['rows'] + member['expenditure']['rows']:
                self.assertIn(row['label'], ' '.join(text.split()))
                for account in row['accounts']:
                    if account['account']:
                        self.assertIn(account['account']['government_account_code'], text)
            for row in member['spa']['rows']:
                self.assertIn(row['label'], ' '.join(text.split()))
        self.assertEqual(text.count('Date signed:'), 4*len(body['members']))
        self.assertEqual(text.count('Date approved:'), len(body['members']))
        with self.assertRaises(ValidationError): record.save()
        with self.assertRaises(ValidationError): record.delete()

    def test_pending_stale_superseded_maker_uat_and_foreign_office_cannot_release(self):
        package = self.reviewed_package()
        self.copy_role_only(self.preparer, 'Budget Form 1 Designation Preparer')
        preparation = self.signing(package)
        with self.assertRaises(ValidationError): self.release_copy(preparation)
        self.copy_role_only(self.reviewer, 'Budget Form 1 Designation Reviewer')
        self.decide_signing(preparation)
        self.copy_role_only(self.reviewer, 'Budget Form 1 Signing Copy Releaser')
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',codename='release_form1_signing_copies'))
        with self.assertRaises(ValidationError): self.release_copy(preparation, actor=self.preparer)
        with self.assertRaises(PermissionDenied): self.release_copy(preparation, actor=self.checker)
        group = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0]
        self.reviewer.groups.add(group)
        with self.assertRaises(PermissionDenied): self.release_copy(preparation)
        self.reviewer.groups.remove(group)
        successor = self.signing(package, expected_latest=1)
        with self.assertRaises(ValidationError): self.release_copy(preparation)
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',codename='review_form1_signing_preparations'))
        self.decide_signing(successor)
        # Designation-only makers cannot change forecasts. Grant that separate
        # source action only for this fixture's later source-staleness check.
        with self.assertRaises(PermissionDenied): self.prepare_forecast(expected_latest=1)
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',
            codename='prepare_budget_receipt_forecasts'))
        self.prepare_forecast(expected_latest=1)
        with self.assertRaises(ValidationError): self.release_copy(successor)
        self.assertFalse(Copy.objects.exists())

    def test_retained_download_does_not_rerender_or_require_current_heads_and_corruption_fails_closed(self):
        preparation = self.unsigned_preparation(); record = self.release_copy(preparation)
        original = service.snapshot(record, self.checker)
        with self.assertRaises(ValidationError): self.release_copy(preparation)
        self.prepare_forecast(expected_latest=1)
        with patch.object(output, 'render_pdf', side_effect=AssertionError('Never rerender issued bytes')):
            data, retained = service.document(record, self.checker)
        self.assertEqual(data, bytes(record.document)); self.assertEqual(retained, original)
        permission = Permission.objects.get(content_type__app_label='budget', codename='export_budget_receipt_forecasts')
        self.checker.user_permissions.remove(permission)
        self.assertEqual(service.snapshot(record,self.checker),original)
        with self.assertRaises(PermissionDenied): service.document(record,self.checker)
        self.checker.user_permissions.add(permission)
        permission = Permission.objects.get(content_type__app_label='budget', codename='view_form1_signing_copies')
        self.checker.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker)
        self.assertEqual(service.document(record,self.checker)[0],data)
        self.checker.user_permissions.add(permission)
        Copy.objects.filter(pk=record.pk).update(document=b'%PDF-corrupt')
        with self.assertRaises(ValidationError): service.snapshot(record,self.checker)
        Copy.objects.filter(pk=record.pk).update(document=data)
        changed=deepcopy(record.payload);changed['form_issued']=True
        Copy.objects.filter(pk=record.pk).update(payload=changed,payload_checksum=checksum(changed))
        with self.assertRaises(ValidationError): service.snapshot(record,self.checker)
        with self.assertRaises(ValidationError): output.render_pdf(dict(payload=changed,checksum=checksum(changed)))
