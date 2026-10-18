import hashlib
import io
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import TestCase, Client, SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from departments.models import Department
from profiles.models import EmployeeProfile
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from inventory.models import ReceivingEvidence, ReceiptCostAmendment, ReceivingLine, Asset
from inventory import receiving
from inventory.receipt_amendments import record_amendment, decide_amendment, amendment_basis
from inventory.property_determinations import checksum
from inventory_finance import asset_cost_allocations as service
from inventory_finance.asset_cost_forms import AllocationDecisionForm
from inventory_finance.models import AssetCostAllocation as Allocation, AssetCostAllocationEvent as Event
from . import test_grand_receiving_authority as fixtures


class AssetCostAllocationTests(TestCase):
    databases = {'default', 'finance'}
    body = b'%PDF-1.4\nSynthetic allocation source\n%%EOF'

    @classmethod
    def setUpTestData(cls):
        fixtures.GrandReceivingAuthorityTests.setUpTestData.__func__(cls)
        cls.finance = Department.objects.create(name='Allocation Accounting', slug='allocation-accounting')
        cls.accountant = get_user_model().objects.create_user(username='allocation-accountant', email='accountant@example.test')
        cls.accounting_uat = get_user_model().objects.create_user(username='allocation-uat', email='allocation-uat@example.test')
        for actor in (cls.accountant, cls.accounting_uat):
            EmployeeProfile.objects.filter(user=actor).update(assigned_department=cls.finance)
            actor.refresh_from_db()
            actor.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='view_general_ledger'))
        cls.accounting_uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        for actor in (cls.clerk, cls.accountant, cls.accounting_uat, cls.outsider, cls.viewer):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='inventory_finance', codename__endswith='_assetcostallocation'))
        for actor in (cls.clerk, cls.reviewer):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='inventory', codename__in=(
                'record_receiptcostamendment', 'review_receiptcostamendment')))

    def setUp(self):
        self.files = TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        for model in (ReceivingEvidence, ReceiptCostAmendment, Allocation):
            storage = patch.object(model._meta.get_field('file'), 'storage', FileSystemStorage(location=self.files.name))
            storage.start()
            self.addCleanup(storage.stop)
        self.line = self.accept()

    def upload(self):
        return SimpleUploadedFile('allocation.pdf', self.body, content_type='application/pdf')

    def accept(self, cost='100.00'):
        receipt = receiving.create_receipt(actor=self.clerk, data=fixtures.GrandReceivingAuthorityTests.data(self))
        receiving.save_receipt_line(actor=self.clerk, receipt=receipt, expected_version=1, data={
            'kind': 'asset', 'description': 'Synthetic computer bundle', 'unit': 'bundle',
            'delivered_quantity': 1, 'accepted_quantity': 1, 'rejected_quantity': 0,
            'property_tag': str(uuid4()), 'unit_cost': cost})
        receipt.refresh_from_db()
        for kind in ('delivery', 'inspection'):
            receiving.attach_receipt_evidence(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version,
                kind=kind, upload=self.upload(), note='Synthetic retained source')
            receipt.refresh_from_db()
        receipt = receiving.submit_receipt(actor=self.clerk, receipt=receipt, expected_version=receipt.state_version)
        receipt = receiving.accept_receipt(actor=self.reviewer, receipt=receipt, expected_version=receipt.state_version,
                                           note='Independent receiving acceptance')
        return receipt.lines.select_related('receipt', 'registered_asset').get()

    def entries(self, first='70.00', second='30.00'):
        return [dict(label='Processor', quantity='1', unit='unit', amount=first, reference='Invoice component A'),
                dict(label='Monitor', quantity='1', unit='unit', amount=second, reference='Invoice component B')]

    def propose(self, **changes):
        line = changes.get('line', self.line)
        args = dict(actor=self.clerk, line=line, finance_department_id=self.finance.pk, request_id=uuid4(),
            expected_basis=checksum(service.basis(line)[0]), entries=self.entries(),
            allocation_basis='Explicit amounts on the synthetic supplier component sheet', upload=self.upload())
        args.update(changes)
        return service.propose(**args)

    def decide(self, row, **changes):
        args = dict(actor=self.accountant, row=row, expected_version=row.state_version,
                    action='approved', note='Independent documentary comparison; valuation remains unconfirmed')
        args.update(changes)
        return service.decide(**args)

    def amendment(self, cost):
        self.line.refresh_from_db()
        row = record_amendment(actor=self.clerk, line=self.line, request_id=uuid4(), expected_basis=amendment_basis(self.line),
            unit_cost=cost, reference='Corrected invoice', reason='Documented source correction', upload=self.upload())
        decide_amendment(actor=self.reviewer, amendment=row, expected_version=1, action='approve', note='Independent cost document review')
        self.line.refresh_from_db()
        return row

    def test_reviewed_bundle_preserves_original_register_receipt_custody_and_finance(self):
        before = list(Asset.objects.values()), list(ReceivingLine.objects.values()), list(self.line.receipt.events.values())
        with CaptureQueriesContext(connections['finance']) as finance:
            row = self.decide(self.propose())
            service.verify(row)
            self.assertEqual(service.basis(self.line)[1].pk, row.pk)
        self.assertEqual(len(finance), 0)
        self.assertEqual(before, (list(Asset.objects.values()), list(ReceivingLine.objects.values()), list(self.line.receipt.events.values())))
        self.assertEqual(row.source_amount, Decimal('100.00'))
        self.assertEqual(row.events.count(), 2)
        self.assertEqual(row.components[0]['quantity'], '1.000')
        self.assertEqual(self.line.registered_asset.quantity, 1)

    def test_scope_explicit_grants_and_uat_are_required_for_proposal(self):
        for actor in (self.outsider, self.viewer, self.accounting_uat, self.super_no_grant, self.reviewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.propose(actor=actor)
        self.assertEqual(Allocation.objects.count(), 0)

    def test_review_requires_selected_office_ledger_grant_explicit_authority_and_independence(self):
        row = self.propose()
        for actor in (self.outsider, self.viewer, self.accounting_uat, self.clerk, self.reviewer):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.decide(row, actor=actor)
        self.accountant.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting', codename='view_general_ledger'))
        with self.assertRaises(PermissionDenied):
            self.decide(row)
        self.accountant.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='view_general_ledger'))
        self.accountant.user_permissions.remove(Permission.objects.get(content_type__app_label='inventory_finance', codename='review_assetcostallocation'))
        with self.assertRaises(PermissionDenied):
            self.decide(row)
        self.assertEqual(row.events.count(), 1)

    def test_same_person_cannot_review_even_with_all_authority(self):
        row = self.propose(finance_department_id=self.gso.pk)
        self.clerk.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='view_general_ledger'))
        with self.assertRaisesMessage(ValidationError, 'different authorized'):
            self.decide(row, actor=self.clerk)

    def test_components_require_explicit_exact_amounts_and_reject_guessed_residuals(self):
        invalid = [self.entries(first='69.99'), self.entries(first='70.001'), self.entries(first='-1'),
                   self.entries(first=float('nan')), [], self.entries() * 26]
        for entries in invalid:
            with self.subTest(entries=repr(entries)[:80]), self.assertRaises(ValidationError):
                self.propose(entries=entries)
        for key, raw in [('quantity', 0), ('quantity', True), ('quantity', '1.0001'), ('unit', ''), ('reference', '')]:
            entries = self.entries()
            entries[0][key] = raw
            with self.subTest(key=key, raw=raw), self.assertRaises(ValidationError):
                self.propose(entries=entries)
        entries = self.entries()
        entries[1]['label'] = 'processor'
        with self.assertRaises(ValidationError):
            self.propose(entries=entries)
        self.assertEqual(Allocation.objects.count(), 0)

    def test_unknown_cost_is_blocked_while_known_zero_is_retained_explicitly(self):
        unknown = self.accept(cost=None)
        with self.assertRaisesMessage(ValidationError, 'unknown is not zero'):
            self.propose(line=unknown)
        zero = self.accept(cost='0.00')
        row = self.decide(self.propose(line=zero, entries=self.entries(first='0.00', second='0.00')))
        self.assertEqual(row.source_amount, 0)
        self.assertEqual(row.source_snapshot['source']['unit_cost'], '0.00')

    def test_exact_retry_after_review_retains_one_proposal_and_file(self):
        identity, snapshot = uuid4(), checksum(service.basis(self.line)[0])
        row = self.propose(request_id=identity, expected_basis=snapshot)
        self.decide(row)
        again = self.propose(request_id=identity, expected_basis=snapshot)
        self.assertEqual(again.pk, row.pk)
        self.assertEqual(Allocation.objects.count(), 1)
        self.assertEqual(len(list((Path(self.files.name)/'inventory/asset-cost-allocations').rglob('*.pdf'))), 1)
        with self.assertRaises(ValidationError):
            self.propose(request_id=identity, expected_basis=snapshot, allocation_basis='Changed request content')

    def test_competing_predecessor_and_version_cannot_be_approved_but_can_be_rejected(self):
        first, second = self.propose(), self.propose(entries=self.entries(first='60.00', second='40.00'))
        self.decide(first)
        with self.assertRaises(ValidationError):
            self.decide(second)
        with self.assertRaises(ValidationError):
            self.decide(second, expected_version=True, action='rejected')
        self.decide(second, action='rejected')
        self.assertEqual(service.basis(self.line)[1].pk, first.pk)

    def test_documentary_cost_successor_requires_new_allocation_without_rewriting_approved_history(self):
        row = self.decide(self.propose())
        original = row.source_snapshot
        self.amendment('50.00')
        snapshot, head = service.basis(self.line)
        self.assertEqual(head.pk, row.pk)
        self.assertNotEqual(snapshot['source'], original['source'])
        replacement = self.decide(self.propose(entries=self.entries(first='35.00', second='15.00')))
        self.assertEqual(replacement.predecessor_id, row.pk)
        row.refresh_from_db()
        self.assertEqual(row.source_snapshot, original)
        self.line.registered_asset.refresh_from_db()
        self.assertEqual(self.line.registered_asset.unit_cost, Decimal('100.00'))

    def test_modified_original_receipt_cannot_be_adopted_as_a_fresh_source(self):
        ReceivingLine.objects.filter(pk=self.line.pk).update(unit_cost='90.00')
        self.line.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'retained acceptance'):
            self.propose(entries=self.entries(first='60.00', second='30.00'))

    def test_missing_changed_and_unsafe_source_files_block_proposal_and_approval(self):
        row = self.propose()
        source_file = self.line.receipt.evidence.first()
        path = Path(source_file.file.path)
        path.write_bytes(b'changed source')
        with self.assertRaises(ValidationError):
            self.decide(row)
        with self.assertRaises(ValidationError):
            self.propose()
        path.unlink()
        with self.assertRaises(ValidationError):
            self.decide(row)

    def test_corrupt_proposal_file_and_status_drift_fail_closed(self):
        row = self.propose()
        path = Path(row.file.path)
        path.write_bytes(b'changed allocation')
        with self.assertRaises(ValidationError):
            self.decide(row)
        path.write_bytes(self.body)
        row = self.decide(row)
        Allocation.objects.filter(pk=row.pk).update(status='rejected')
        with self.assertRaises(ValidationError):
            service.basis(self.line)

    def test_content_and_independent_events_are_immutable_and_checked(self):
        row = self.propose()
        row.basis = 'Rewritten'
        with self.assertRaises(ValidationError):
            row.save()
        with self.assertRaises(ValidationError):
            row.delete()
        entry = row.events.first()
        with self.assertRaises(ValidationError):
            entry.save()
        with self.assertRaises(ValidationError):
            entry.delete()
        Event.objects.filter(pk=entry.pk).update(note='Changed findings')
        row.refresh_from_db()
        with self.assertRaises(ValidationError):
            service.verify(row)

    def test_checked_download_uses_one_handle_preserves_headers_and_current_scope(self):
        row = self.propose()
        url = reverse('inventory_finance:asset-cost-evidence', args=[row.pk])
        self.client.force_login(self.accountant)
        storage = Allocation._meta.get_field('file').storage
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            response = self.client.get(url)
            self.assertEqual(b''.join(response.streaming_content), self.body)
            self.assertEqual(opened.call_count, 1)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.client.force_login(self.outsider)
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(opened.call_count, 0)
        self.client.force_login(self.accounting_uat)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.body)

    def test_authenticated_http_proposal_review_uat_read_and_forgery_boundaries(self):
        self.client.force_login(self.clerk)
        url = reverse('inventory_finance:asset-cost-propose', args=[self.line.pk])
        token = self.client.get(url).context['form'].initial['source_token']
        data = {'source_token': token, 'finance_department': self.finance.pk,
                'allocation_basis': 'Explicit supplier component statement', 'upload': self.upload(),
                'components-TOTAL_FORMS': '2', 'components-INITIAL_FORMS': '0'}
        for index, entry in enumerate(self.entries()):
            data.update({f'components-{index}-{key}': raw for key, raw in entry.items()})
        self.assertEqual(self.client.post(url, data).status_code, 302)
        row = Allocation.objects.get()
        detail = reverse('inventory_finance:asset-cost-detail', args=[row.pk])
        self.client.force_login(self.accountant)
        self.assertContains(self.client.get(detail), 'Choose a decision')
        self.assertEqual(self.client.post(detail, {'expected_version': 1, 'action': 'approved', 'note': 'Independent documentary review'}).status_code, 302)
        self.client.force_login(self.accounting_uat)
        page = self.client.get(detail)
        self.assertContains(page, 'Current reviewed documentary worksheet')
        self.assertContains(page, 'not an officially approved accounting value')
        self.assertNotContains(page, 'Record independent decision')
        self.assertEqual(self.client.post(detail, {'expected_version': 2, 'action': 'rejected', 'note': 'Forged UAT action'}).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 404)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.accountant)
        self.assertEqual(csrf.post(detail, {}).status_code, 403)

    def test_read_only_recovery_detects_changed_history_missing_files_and_orphans(self):
        row = self.decide(self.propose())
        before = list(Allocation.objects.values()), list(Event.objects.values())
        with CaptureQueriesContext(connections['default']) as queries:
            call_command('check_asset_cost_allocations', stdout=io.StringIO())
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in queries))
        orphan = Path(row.file.path).parent/'orphan.pdf'
        orphan.write_bytes(self.body)
        with self.assertRaises(CommandError):
            call_command('check_asset_cost_allocations', stdout=io.StringIO())
        self.assertEqual(before, (list(Allocation.objects.values()), list(Event.objects.values())))

    def test_signed_form_cannot_be_reused_by_another_actor_or_after_real_expiry(self):
        from time import time
        from inventory_finance.asset_cost_views import SALT
        self.client.force_login(self.clerk)
        url = reverse('inventory_finance:asset-cost-propose', args=[self.line.pk])
        token = self.client.get(url).context['form'].initial['source_token']
        payload = {'source_token': token, 'finance_department': self.finance.pk,
            'allocation_basis': 'Keep this entered basis', 'upload': self.upload(),
            'components-TOTAL_FORMS': '2', 'components-INITIAL_FORMS': '0'}
        for index, entry in enumerate(self.entries()):
            payload.update({f'components-{index}-{key}': raw for key, raw in entry.items()})
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='inventory_finance', codename='propose_assetcostallocation'))
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_login(self.clerk)
        with patch.object(signing.TimestampSigner, 'timestamp', return_value=signing.b62_encode(int(time())-1801)):
            expired = signing.dumps(signing.loads(token, salt=SALT), salt=SALT)
        payload.update(source_token=expired, upload=self.upload())
        page = self.client.post(url, payload)
        self.assertContains(page, 'expired or changed')
        self.assertContains(page, 'Keep this entered basis')
        self.assertEqual(Allocation.objects.count(), 0)

    def test_unsafe_pointer_is_rejected_even_with_matching_content_and_event_checksums(self):
        row = self.propose()
        outside = Path(self.files.name)/'outside.pdf'
        outside.write_bytes(self.body)
        for unsafe in ('outside.pdf', outside.as_posix(), f'inventory/asset-cost-allocations/{self.line.receipt.public_id}/../outside.pdf'):
            row.file.name = unsafe
            row.content_checksum = checksum(service.content(row))
            Allocation.objects.filter(pk=row.pk).update(file=unsafe, content_checksum=row.content_checksum)
            entry = row.events.first()
            entry.snapshot = service.event_snapshot(row, entry)
            entry.checksum = checksum(entry.snapshot)
            Event.objects.filter(pk=entry.pk).update(snapshot=entry.snapshot, checksum=entry.checksum)
            self.client.force_login(self.accountant)
            self.assertEqual(self.client.get(reverse('inventory_finance:asset-cost-evidence', args=[row.pk])).status_code, 404)
            with self.assertRaises(ValidationError):
                self.decide(row)

    def test_changed_source_or_superseded_approval_is_never_displayed_as_current(self):
        row = self.decide(self.propose())
        self.client.force_login(self.accountant)
        url = reverse('inventory_finance:asset-cost-detail', args=[row.pk])
        self.amendment('50.00')
        page = self.client.get(url)
        self.assertContains(page, 'source facts changed')
        self.assertNotContains(page, 'Current reviewed documentary worksheet')
        self.decide(self.propose(entries=self.entries(first='35.00', second='15.00')))
        self.assertNotContains(self.client.get(url), 'Current reviewed documentary worksheet')

    def test_pending_or_modified_cost_correction_history_blocks_new_approval(self):
        row = self.propose()
        amendment = record_amendment(actor=self.clerk, line=self.line, request_id=uuid4(),
            expected_basis=amendment_basis(self.line), unit_cost='50.00', reference='Corrected cost',
            reason='Documentary correction', upload=self.upload())
        with self.assertRaises(ValidationError):
            self.decide(row)
        decide_amendment(actor=self.reviewer, amendment=amendment, expected_version=1, action='approve', note='Independent review')
        ReceiptCostAmendment.objects.filter(pk=amendment.pk).update(status='rejected')
        self.line.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'history changed'):
            self.propose()

    def test_successor_starts_from_reviewed_entries_but_never_copies_evidence_or_rescales_amounts(self):
        row = self.decide(self.propose())
        self.client.force_login(self.clerk)
        url = reverse('inventory_finance:asset-cost-propose', args=[self.line.pk])
        page = self.client.get(url)
        self.assertEqual(page.context['lines'].initial, row.components)
        self.assertEqual(page.context['form'].initial['finance_department'], self.finance.pk)
        self.assertEqual(page.context['form'].initial['allocation_basis'], row.basis)
        self.assertNotIn('upload', page.context['form'].initial)
        self.assertContains(page, 'last reviewed worksheet')
        self.assertContains(page, reverse('inventory:receiving-detail', args=[self.line.receipt_id]))
        self.amendment('50.00')
        page = self.client.get(url)
        self.assertEqual(page.context['source']['amount'], '50.00')
        self.assertEqual(page.context['lines'].initial, row.components)
        self.assertEqual(page.context['lines'].initial[0]['amount'], '70.00')


class AssetCostDecisionFormTests(SimpleTestCase):
    def test_acceptance_is_never_an_implicit_default(self):
        self.assertEqual(AllocationDecisionForm().fields['action'].choices[0], ('', 'Choose a decision'))
        self.assertFalse(AllocationDecisionForm({'expected_version': 1, 'note': 'Findings'}).is_valid())

    def test_omit_label_applies_to_existing_and_new_component_rows(self):
        from inventory_finance.asset_cost_forms import AllocationComponents
        forms = AllocationComponents(prefix='components')
        self.assertEqual(forms.forms[0].fields['DELETE'].label, 'Omit this component')
        self.assertEqual(forms.empty_form.fields['DELETE'].label, 'Omit this component')
