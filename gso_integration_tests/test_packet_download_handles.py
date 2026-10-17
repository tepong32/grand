from pathlib import Path
from pkgutil import resolve_name
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory import services, disposal_evidence
from inventory.models import AssetAccountingImport, AssetDisposalAttachment, AssetDisposalCase
from . import (test_grand_hr_custody_reviews, test_grand_property,
    test_grand_property_movements, test_grand_receipt_amendments,
    test_grand_receipt_quantity_corrections, test_grand_property_links,
    test_grand_asset_authority)


class PacketChecks:
    databases = {'default', 'finance'}
    unavailable_status = 404
    public_identity = False

    @classmethod
    def setUpTestData(cls):
        cls.packet_fixture.setUpTestData.__func__(cls)

    def setUp(self):
        self.packet_fixture.setUp(self)
        self.envelope, self.packet = self.build_packet()
        self.reader = getattr(self, 'packet_reader', self.clerk)
        identity = self.envelope.public_id if self.public_identity else self.envelope.pk
        self.url = reverse(self.download_route, args=[identity])
        self.path = Path(self.packet.file.path)
        self.body = self.path.read_bytes()
        self.client.force_login(self.reader)

    def test_original_boundary_rejects_replacement_after_source_validation(self):
        verify = resolve_name(self.legacy_validator_path)

        def replace(*args, **kwargs):
            result = verify(*args, **kwargs)
            self.path.write_bytes(b'x' * len(self.body))
            return result

        with patch(self.legacy_validator_path, side_effect=replace) as checked:
            response = self.client.get(self.url)
            content = b''.join(response.streaming_content) if response.streaming else b''
            self.assertEqual(checked.call_count, 1)
            self.assertEqual(response.status_code, self.unavailable_status, content)

    def test_valid_bytes_headers_and_actual_streaming_handle(self):
        storage = self.packet.file.storage
        original_open = storage.open
        opened, streams = [], []
        module = self.legacy_validator_path.rsplit('.', 1)[0]
        for suffix in ('.workflow', '.service', '.properties'):
            module = module.removesuffix(suffix)
        response_path = module + '.FileResponse'
        original_response = resolve_name(response_path)

        def observe(*args, **kwargs):
            result = original_open(*args, **kwargs)
            opened.append(result)
            return result

        def capture(source, *args, **kwargs):
            streams.append(source)
            return original_response(source, *args, **kwargs)

        with patch.object(storage, 'open', side_effect=observe), patch(response_path, side_effect=capture), CaptureQueriesContext(connections['finance']) as finance:
            response = self.client.get(self.url)
            try:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(streams), 1)
                self.assertIs(streams[0].file, opened[-1])
                self.assertFalse(opened[-1].closed)
            finally:
                content = b''.join(response.streaming_content) if response.streaming else b''
            self.assertEqual(content, self.body)
        self.assertTrue(all(source.closed for source in opened))
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in finance))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_same_size_corruption_and_missing_source_keep_existing_error_status(self):
        self.path.write_bytes(b'x' * len(self.body))
        self.assertEqual(self.client.get(self.url).status_code, self.unavailable_status)
        self.path.unlink()
        self.assertEqual(self.client.get(self.url).status_code, self.unavailable_status)

    def test_anonymous_and_revoked_reader_cannot_open_a_packet(self):
        storage = self.packet.file.storage
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            self.client.logout()
            self.assertEqual(self.client.get(self.url).status_code, 302)
            self.client.force_login(self.reader)
            self.reader.user_permissions.clear()
            self.reader.groups.clear()
            self.assertIn(self.client.get(self.url).status_code, (403, 404))
            self.assertEqual(opened.call_count, 0)

    def test_separately_granted_uat_read_is_preserved(self):
        self.client.force_login(self.packet_uat)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.body)


class HRCustodyPacketTests(PacketChecks, TestCase):
    packet_fixture = test_grand_hr_custody_reviews.GrandHRCustodyReviewTests
    download_route = 'inventory:hr-custody-review-evidence'
    legacy_validator_path = 'inventory.hr_custody_review_views.workflow.verify_source'
    unavailable_status = 409

    def build_packet(self):
        self.packet_uat = self.viewer
        row = self.packet_fixture.start(self)
        return row, row

    def test_retained_history_is_still_checked_before_source_download(self):
        self.envelope.events.update(snapshot={})
        self.assertEqual(self.client.get(self.url).status_code, 409)


class PropertyPacketTests(PacketChecks, TestCase):
    packet_fixture = test_grand_property.GrandPropertyTests
    download_route = 'inventory:property-evidence'
    legacy_validator_path = 'inventory.property_views.service.verify_source'

    def build_packet(self):
        self.packet_uat = self.viewer
        row = self.packet_fixture.record(self)
        return row, row


class MovementPacketTests(PacketChecks, TestCase):
    packet_fixture = test_grand_property_movements.PropertyMovementChainTests
    download_route = 'inventory:property-movement-evidence'
    legacy_validator_path = 'inventory.property_movement_views.service.verify_evidence'
    upload = packet_fixture.upload
    data = packet_fixture.data

    def build_packet(self):
        self.packet_uat = self.viewer
        self.determination = self.packet_fixture.determine(self)
        row = self.packet_fixture.record(self)
        return row, row


class CostAmendmentPacketTests(PacketChecks, TestCase):
    packet_fixture = test_grand_receipt_amendments.GrandReceiptAmendmentTests
    download_route = 'inventory:receipt-amendment-evidence'
    legacy_validator_path = 'inventory.receipt_amendment_views.verify_amendment_evidence'

    def build_packet(self):
        self.packet_uat = self.cost_uat
        row = self.packet_fixture.correction(self)
        return row, row

    def test_retained_content_checksum_is_still_checked(self):
        type(self.packet).objects.filter(pk=self.packet.pk).update(content_checksum='x'*64)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class QuantityCorrectionPacketTests(PacketChecks, TestCase):
    packet_fixture = test_grand_receipt_quantity_corrections.GrandQuantityCorrectionTests
    download_route = 'inventory:receipt-quantity-evidence'
    legacy_validator_path = 'inventory.receipt_quantity_views.verify_evidence'
    data = packet_fixture.data
    packet = packet_fixture.packet

    def build_packet(self):
        # This existing UAT fixture belongs to Accounting, so supply the same
        # explicit office/read scope as the clerk without granting mutation.
        from profiles.models import EmployeeProfile
        EmployeeProfile.objects.filter(user=self.viewer).update(assigned_department=self.gso)
        self.packet_uat = self.viewer
        row = self.packet_fixture.correction(self)
        return row, row

    def test_retained_event_chain_is_still_checked(self):
        self.envelope.events.update(snapshot={})
        self.assertEqual(self.client.get(self.url).status_code, 404)


class SharedPropertyPacketTests(PacketChecks, TestCase):
    packet_fixture = test_grand_property_links.PropertyLinkTests
    download_route = 'inventory_finance:property-link-evidence'
    legacy_validator_path = 'inventory_finance.property_link_views.properties.verify_source'
    public_identity = True

    def build_packet(self):
        self.packet_reader, self.packet_uat = self.proposer, self.finance_uat
        link = self.packet_fixture.request(self)
        return link, self.determination

    def test_link_history_and_original_property_scope_remain_separate(self):
        original = reverse('inventory:property-evidence', args=[self.packet.pk])
        self.assertEqual(self.client.get(original).status_code, 404)
        self.envelope.events.update(snapshot={})
        self.assertEqual(self.client.get(self.url).status_code, 404)


class AccountingCSVDownloadTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(test_grand_asset_authority.GrandAssetAuthorityTests.setUpTestData.__func__)

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        replacement = patch.object(AssetAccountingImport._meta.get_field('source_file'), 'storage', FileSystemStorage(location=directory.name))
        replacement.start()
        self.addCleanup(replacement.stop)
        count = services.start_asset_verification_round(actor=self.clerk, title='Synthetic CSV source', as_of_date=timezone.localdate())
        self.body = b'property_tag,asset_name\nCSV-01,Synthetic chair\n'
        self.row = services.import_accounting_asset_snapshot(actor=self.clerk, verification_round=count,
            upload=SimpleUploadedFile('source.csv', self.body))
        self.path = Path(self.row.source_file.path)
        self.url = reverse('inventory:asset-accounting-source-download', args=[self.row.pk])
        self.client.force_login(self.clerk)

    def test_original_boundary_rejects_a_changed_csv_against_its_retained_hash(self):
        self.path.write_bytes(b'x'*len(self.body))
        response = self.client.get(self.url)
        content = b''.join(response.streaming_content) if response.streaming else b''
        self.assertEqual(response.status_code, 404, content)

    def test_valid_hash_only_csv_and_existing_headers(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.body)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('source_size', {f.name for f in self.row._meta.fields})

    def test_missing_and_wrong_namespace_csv_fail_without_exposing_a_source(self):
        outside = Path(self.row.source_file.storage.location)/'outside.csv'
        outside.write_bytes(self.body)
        AssetAccountingImport.objects.filter(pk=self.row.pk).update(source_file='outside.csv')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        AssetAccountingImport.objects.filter(pk=self.row.pk).update(source_file=self.row.source_file.name)
        self.path.unlink()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_foreign_denial_and_granted_uat_read_preserve_round_scope(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.body)

    def test_unknown_hash_is_not_replaced_by_an_invented_baseline(self):
        AssetAccountingImport.objects.filter(pk=self.row.pk).update(source_sha256='')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.row.refresh_from_db()
        self.assertEqual(self.row.source_sha256, '')


class DisposalNamespaceDownloadTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(test_grand_asset_authority.GrandAssetAuthorityTests.setUpTestData.__func__)

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        replacement = patch.object(AssetDisposalAttachment._meta.get_field('file'), 'storage', FileSystemStorage(location=directory.name))
        replacement.start()
        self.addCleanup(replacement.stop)
        case = AssetDisposalCase.objects.create(asset=self.asset, submitted_by=self.clerk,
            reason='Synthetic namespace check', condition_details='Source retained')
        self.body = b'%PDF-native disposal packet'
        self.row = services._save_disposal_attachments(case=case, actor=self.clerk,
            groups=[('supporting',[SimpleUploadedFile('source.pdf',self.body)])])[0]
        self.url = reverse('inventory:disposal-attachment-download', args=[self.row.pk])
        self.client.force_login(self.clerk)

    def test_original_boundary_rejects_a_matching_file_outside_the_asset_namespace(self):
        outside = Path(self.row.file.storage.location)/'outside.pdf'
        outside.write_bytes(self.body)
        AssetDisposalAttachment.objects.filter(pk=self.row.pk).update(file='outside.pdf')
        response = self.client.get(self.url)
        content = b''.join(response.streaming_content) if response.streaming else b''
        self.assertEqual(response.status_code, 409, content)

    def test_known_and_legacy_hash_contracts_are_preserved(self):
        for sha, label in ((self.row.sha256,'verified'),('','unknown-legacy')):
            AssetDisposalAttachment.objects.filter(pk=self.row.pk).update(sha256=sha)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['X-Evidence-Integrity'],label)
            self.assertEqual(b''.join(response.streaming_content),self.body)
        self.row.refresh_from_db()
        with self.assertRaises(ValidationError):
            disposal_evidence.open_checked_evidence(self.row)
        with disposal_evidence.open_checked_evidence(self.row,allow_legacy=True) as source:
            self.assertEqual(source.read(),self.body)

    def test_legacy_size_and_missing_file_checks_still_apply(self):
        AssetDisposalAttachment.objects.filter(pk=self.row.pk).update(sha256='')
        Path(self.row.file.path).write_bytes(b'changed size')
        self.assertEqual(self.client.get(self.url).status_code,409)
        Path(self.row.file.path).unlink()
        self.assertEqual(self.client.get(self.url).status_code,409)


class CheckedFileContractTests(SimpleTestCase):
    def setUp(self):
        import hashlib
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.storage = FileSystemStorage(location=directory.name)
        replacement = patch.object(AssetDisposalAttachment._meta.get_field('file'), 'storage', self.storage)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.source = AssetDisposalAttachment(file='inventory/core/source.pdf').file
        path = Path(self.source.path)
        path.parent.mkdir(parents=True)
        self.body = b'%PDF-core checked source'
        path.write_bytes(self.body)
        self.digest = hashlib.sha256(self.body).hexdigest()

    def test_hash_only_source_checks_and_returns_one_open_handle(self):
        from inventory.private_evidence import open_checked_private_file
        with patch.object(self.storage, 'open', wraps=self.storage.open) as opened:
            with open_checked_private_file(self.source, namespace='inventory/core', sha256=self.digest) as source:
                self.assertEqual(source.read(), self.body)
            self.assertEqual(opened.call_count, 1)

    def test_row_api_cannot_silently_drop_a_required_size_baseline(self):
        from types import SimpleNamespace
        from inventory.private_evidence import open_checked_private_evidence
        row = SimpleNamespace(file=self.source, sha256=self.digest, size=None)
        with self.assertRaises(ValidationError), patch.object(self.storage, 'open', wraps=self.storage.open) as opened:
            open_checked_private_evidence(row, namespace='inventory/core')
        self.assertEqual(opened.call_count, 0)

    def test_unknown_hash_and_size_are_not_a_legacy_integrity_baseline(self):
        from inventory.private_evidence import open_checked_private_file
        with self.assertRaises(ValidationError):
            open_checked_private_file(self.source, namespace='inventory/core', sha256='', allow_legacy=True)

    def test_known_size_failure_closes_the_open_source(self):
        from inventory.private_evidence import open_checked_private_file
        opened = []
        original = self.storage.open
        def observe(*args, **kwargs):
            source = original(*args, **kwargs)
            opened.append(source)
            return source
        with patch.object(self.storage, 'open', side_effect=observe), self.assertRaises(ValidationError):
            open_checked_private_file(self.source, namespace='inventory/core', sha256=self.digest, size=len(self.body)+1)
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_unsafe_paths_fail_before_opening(self):
        from inventory.private_evidence import open_checked_private_file
        for name in (self.source.path, '../outside.pdf', 'inventory\\core\\source.pdf'):
            self.source.name = name
            with self.subTest(path=name), self.assertRaises((ValueError, ValidationError)), patch.object(self.storage, 'open', wraps=self.storage.open) as opened:
                open_checked_private_file(self.source, namespace='inventory/core', sha256=self.digest)
            self.assertEqual(opened.call_count, 0)
