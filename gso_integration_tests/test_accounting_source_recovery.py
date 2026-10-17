import hashlib
import json
import shutil
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from inventory.models import AssetAccountingImport, AssetAccountingLine
from . import test_packet_download_handles as fixtures


class AccountingSourceRecoveryTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.AccountingCSVDownloadTests.setUpTestData.__func__)

    def setUp(self):
        fixtures.AccountingCSVDownloadTests.setUp(self)

    def audit(self, *, failure=False):
        output = StringIO()
        if failure:
            with self.assertRaises(CommandError):
                call_command('check_accounting_source_evidence', stdout=output)
        else:
            call_command('check_accounting_source_evidence', stdout=output)
        return json.loads(output.getvalue())

    def test_valid_retained_source_is_checked_without_database_or_file_changes(self):
        rows = list(AssetAccountingImport.objects.values()), list(AssetAccountingLine.objects.values())
        with CaptureQueriesContext(connections['default']) as default, CaptureQueriesContext(connections['finance']) as finance:
            report = self.audit()
        self.assertEqual(report['checked'], 1)
        self.assertFalse(any(value for key, value in report.items() if key != 'checked'))
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))
        self.assertEqual(len(finance), 0)
        self.assertEqual((list(AssetAccountingImport.objects.values()), list(AssetAccountingLine.objects.values())), rows)
        self.assertEqual(self.path.read_bytes(), self.body)

    def test_same_size_corruption_is_reported_without_rebaselining(self):
        self.path.write_bytes(b'x'*len(self.body))
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['changed']], [self.row.pk])
        self.assertFalse(report['unreferenced'])
        self.row.refresh_from_db()
        self.assertNotEqual(self.row.source_sha256, digest)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), digest)

    def test_missing_source_is_reported_without_reconstructing_it(self):
        self.path.unlink()
        report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['missing']], [self.row.pk])
        self.assertFalse(self.path.exists())

    def test_unknown_hash_remains_unknown(self):
        AssetAccountingImport.objects.filter(pk=self.row.pk).update(source_sha256='')
        report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['unknown']], [self.row.pk])
        self.row.refresh_from_db()
        self.assertEqual(self.row.source_sha256, '')
        self.assertEqual(self.path.read_bytes(), self.body)

    def test_historical_unretained_source_is_distinct_from_a_missing_archive(self):
        AssetAccountingImport.objects.filter(pk=self.row.pk).update(source_file='')
        report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['unretained']], [self.row.pk])
        self.assertFalse(report['missing'])
        self.assertTrue(self.path.exists())
        self.assertEqual(self.row.source_sha256, hashlib.sha256(self.body).hexdigest())

    def test_orphan_is_reported_and_retained_for_investigation(self):
        orphan = self.path.parent/'unreferenced.csv'
        orphan.write_bytes(self.body)
        report = self.audit(failure=True)
        self.assertEqual(report['unreferenced'], [orphan.relative_to(self.row.source_file.storage.location).as_posix()])
        self.assertEqual(orphan.read_bytes(), self.body)

    def test_matching_bytes_in_the_wrong_round_namespace_are_unsafe(self):
        root = Path(self.row.source_file.storage.location)
        name = 'inventory/reconciliation/999999/other.csv'
        foreign = root/name
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(self.body)
        AssetAccountingImport.objects.filter(pk=self.row.pk).update(source_file=name)
        report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['unsafe']], [self.row.pk])
        self.assertEqual(foreign.read_bytes(), self.body)

    def test_unreadable_source_cannot_be_reported_as_valid(self):
        with patch.object(self.row.source_file.storage, 'open', side_effect=PermissionError('Synthetic denied read')):
            report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['unreadable']], [self.row.pk])

    def test_unenumerable_storage_cannot_hide_orphans(self):
        def inaccessible(*args, onerror, **kwargs):
            onerror(PermissionError('Synthetic denied enumeration'))
            return iter(())
        with patch('inventory.management.commands.check_accounting_source_evidence.os.walk', side_effect=inaccessible):
            report = self.audit(failure=True)
        self.assertTrue(report['unreadable'])

    def test_restored_private_file_copy_is_checked_against_unchanged_metadata(self):
        original_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
        metadata = list(AssetAccountingImport.objects.values())
        with TemporaryDirectory() as directory:
            copied = Path(directory)/'private'
            shutil.copytree(self.row.source_file.storage.location, copied)
            restored = copied/self.row.source_file.name
            with patch.object(AssetAccountingImport._meta.get_field('source_file'), 'storage', FileSystemStorage(location=copied)):
                self.assertEqual(self.audit()['checked'], 1)
                restored.write_bytes(b'x'*len(self.body))
                self.assertTrue(self.audit(failure=True)['changed'])
                restored.unlink()
                self.assertTrue(self.audit(failure=True)['missing'])
        self.assertEqual(list(AssetAccountingImport.objects.values()), metadata)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), original_hash)


class EmptyAccountingSourceRecoveryTests(TestCase):
    databases = {'default', 'finance'}

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        replacement = patch.object(AssetAccountingImport._meta.get_field('source_file'), 'storage', FileSystemStorage(location=self.directory.name))
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_empty_history_and_absent_namespace_are_a_valid_empty_check(self):
        output = StringIO()
        call_command('check_accounting_source_evidence', stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report['checked'], 0)
        self.assertFalse(any(value for key, value in report.items() if key != 'checked'))

    def test_empty_database_does_not_make_unreferenced_archives_invisible(self):
        source = Path(self.directory.name)/'inventory/reconciliation/1/orphan.csv'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'synthetic unreferenced archive')
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command('check_accounting_source_evidence', stdout=output)
        self.assertEqual(json.loads(output.getvalue())['unreferenced'], ['inventory/reconciliation/1/orphan.csv'])
        self.assertTrue(source.exists())
