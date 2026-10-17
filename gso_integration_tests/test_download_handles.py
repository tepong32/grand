from pathlib import Path
from pkgutil import resolve_name
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory import stock_counts
from profiles.models import EmployeeProfile
from . import (test_grand_stock_counts, test_grand_custody_returns,
               test_grand_requisitions, test_grand_supply_returns)


class DownloadChecks:
    databases = {'default', 'finance'}

    @classmethod
    def setUpTestData(cls):
        cls.fixture.setUpTestData.__func__(cls)

    def setUp(self):
        # The factory uses this outer test's addCleanup, including setup failures.
        self.fixture.setUp(self)
        self.row, self.parent = self.build()
        self.url = reverse(self.route, args=[self.row.pk])
        self.original_path = Path(self.row.file.path)
        self.original_bytes = self.original_path.read_bytes()
        self.client.force_login(self.clerk)

    def test_valid_download_streams_the_last_opened_handle_with_existing_headers(self):
        storage = self.row.file.storage
        original_open = storage.open
        opened = []
        streamed = []
        response_path = self.verifier_path.rsplit('.', 1)[0].removesuffix('.service') + '.FileResponse'
        original_response = resolve_name(response_path)

        def observe(*args, **kwargs):
            result = original_open(*args, **kwargs)
            opened.append(result)
            return result

        def capture_stream(source, *args, **kwargs):
            streamed.append(source)
            return original_response(source, *args, **kwargs)

        with patch.object(storage, 'open', side_effect=observe), patch(response_path, side_effect=capture_stream), CaptureQueriesContext(connections['finance']) as finance:
            response = self.client.get(self.url)
            try:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(streamed), 1)
                self.assertIs(streamed[0].file, opened[-1])
                self.assertFalse(opened[-1].closed)
            finally:
                # The client replaces file_to_stream while wrapping the response.
                # Always exhaust its wrapper, including assertion-failure paths.
                received = b''.join(response.streaming_content) if response.streaming else b''
            self.assertEqual(received, self.original_bytes)
        self.assertEqual(len(finance), 0)
        self.assertTrue(all(source.closed for source in opened))
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_change_after_legacy_validation_cannot_supply_unchecked_download_bytes(self):
        # Reproduce the exact check/use window: all old verification succeeds,
        # then the requested file changes before the view opens its stream.
        original_verify = resolve_name(self.verifier_path)

        def change_after_check(*args, **kwargs):
            result = original_verify(*args, **kwargs)
            self.original_path.write_bytes(b'x' * len(self.original_bytes))
            return result

        with patch(self.verifier_path, side_effect=change_after_check) as verified:
            response = self.client.get(self.url)
            # Consume an incorrect original response so it also closes normally.
            received = b''.join(response.streaming_content) if response.streaming else b''
            self.assertEqual(verified.call_count, 1)
            self.assertEqual(response.status_code, 404, received)

    def test_modified_same_size_and_missing_files_keep_the_generic_404(self):
        self.original_path.write_bytes(b'x' * len(self.original_bytes))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.original_path.unlink()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_unsafe_paths_cannot_become_downloads_even_with_matching_bytes(self):
        storage_root = Path(self.row.file.storage.location)
        foreign = storage_root/'outside-case.pdf'
        foreign.write_bytes(self.original_bytes)
        names = [str(self.original_path), 'outside-case.pdf', '../outside.pdf',
                 self.row.file.name.replace('/', '\\')]
        for name in names:
            with self.subTest(path=name):
                type(self.row).objects.filter(pk=self.row.pk).update(file=name)
                response = self.client.get(self.url)
                if response.streaming:
                    b''.join(response.streaming_content)
                self.assertEqual(response.status_code, 404)

    def test_anonymous_foreign_and_revoked_access_do_not_open_evidence(self):
        storage = self.row.file.storage
        with patch.object(storage, 'open', wraps=storage.open) as opened:
            self.client.logout()
            self.assertEqual(self.client.get(self.url).status_code, 302)
            self.client.force_login(getattr(self, 'foreign_reader', self.outsider))
            self.assertIn(self.client.get(self.url).status_code, (403, 404))
            self.client.force_login(self.clerk)
            self.clerk.user_permissions.clear()
            self.clerk.groups.clear()
            self.assertIn(self.client.get(self.url).status_code, (403, 404))
            self.assertEqual(opened.call_count, 0)

    def test_separately_authorized_uat_read_access_remains_available(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.original_bytes)


class StockCountDownloadTests(DownloadChecks, TestCase):
    fixture = test_grand_stock_counts.GrandStockCountTests
    route = 'inventory:stock-count-evidence'
    verifier_path = 'inventory.stock_count_views.verify_count_evidence'

    def build(self):
        count = self.fixture.record(self)
        return self.fixture.evidence(self, count), count

    def test_bad_sibling_still_blocks_a_valid_requested_file(self):
        sibling = stock_counts.attach_count_evidence(actor=self.clerk, count=self.parent,
            expected_version=self.parent.state_version,
            upload=SimpleUploadedFile('second.pdf', b'%PDF-second count document'), note='Second sheet')
        Path(sibling.file.path).write_bytes(b'changed')
        self.assertEqual(self.client.get(self.url).status_code, 404)


class CustodyReturnDownloadTests(DownloadChecks, TestCase):
    fixture = test_grand_custody_returns.CustodyReturnTests
    route = 'inventory:custody-return-evidence'
    verifier_path = 'inventory.custody_return_views.verify_return_evidence'

    def build(self):
        transfer = self.fixture.start(self)
        self.foreign_reader = get_user_model().objects.create_user(
            username='unrelated-evidence-reader', email='unrelated-evidence-reader@example.test')
        EmployeeProfile.objects.filter(user=self.foreign_reader).update(assigned_department=self.other)
        self.foreign_reader.user_permissions.add(Permission.objects.get(
            content_type__app_label='inventory', codename='view_asset'))
        return self.fixture.evidence(self, transfer), transfer

    def test_source_employee_keeps_personal_return_evidence_access(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.original_bytes)

    def test_bad_sibling_still_blocks_a_valid_requested_file(self):
        self.parent.refresh_from_db()
        sibling = self.fixture.evidence(self, self.parent)
        Path(sibling.file.path).write_bytes(b'changed')
        self.assertEqual(self.client.get(self.url).status_code, 404)


class RequisitionDownloadTests(DownloadChecks, TestCase):
    fixture = test_grand_requisitions.GrandRequisitionTests
    route = 'inventory:requisition-evidence'
    verifier_path = 'inventory.requisition_views.service.verify_source'

    def build(self):
        row = self.fixture.create(self)
        return row, row


class SupplyReturnDownloadTests(DownloadChecks, TestCase):
    fixture = test_grand_supply_returns.GrandSupplyReturnTests
    route = 'inventory:supply-return-evidence'
    verifier_path = 'inventory.supply_return_views.service.verify_source'

    def build(self):
        row = self.fixture.record(self)
        return row, row
