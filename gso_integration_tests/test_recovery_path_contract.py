import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.core.files.storage import FileSystemStorage
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase

from inventory.management.commands.check_receiving_evidence import Command


class RecoveryPathContractTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.relative_name = 'inventory/receiving/1/source.pdf'
        self.path = self.root/self.relative_name
        self.path.parent.mkdir(parents=True)
        self.body = b'%PDF-synthetic recovery pointer'
        self.path.write_bytes(self.body)
        self.record = SimpleNamespace(pk=7, file=SimpleNamespace(name=self.relative_name),
            sha256=hashlib.sha256(self.body).hexdigest(), size=len(self.body))
        storage = FileSystemStorage(location=self.root)
        self.command = Command()
        self.command.evidence_model = SimpleNamespace(_meta=SimpleNamespace(
            get_field=lambda name: SimpleNamespace(storage=storage)))
        self.command.evidence_records = lambda: iter([self.record])

    def audit(self, *, failure=False):
        output = StringIO()
        if failure:
            with self.assertRaises(CommandError):
                call_command(self.command, stdout=output)
        else:
            call_command(self.command, stdout=output)
        return json.loads(output.getvalue())

    def test_relative_metadata_still_checks_known_bytes(self):
        report = self.audit()
        self.assertEqual(report['checked'], 1)
        self.assertFalse(any(value for key, value in report.items() if key != 'checked'))
        self.assertEqual(self.path.read_bytes(), self.body)

    def test_absolute_pointer_inside_the_root_is_not_portable_safe_metadata(self):
        self.record.file.name = str(self.path)
        report = self.audit(failure=True)
        self.assertEqual([entry['id'] for entry in report['unsafe'] if 'id' in entry], [7])
        self.assertEqual(self.path.read_bytes(), self.body)

    def test_windows_backslashes_are_not_normalized_into_accepted_metadata(self):
        self.record.file.name = self.relative_name.replace('/', '\\')
        report = self.audit(failure=True)
        self.assertTrue(report['unsafe'])
        self.assertEqual(self.path.read_bytes(), self.body)

    def test_legacy_unknown_hash_remains_a_finding_without_becoming_changed(self):
        self.command.report_unknown_hashes = True
        self.record.sha256 = ''
        report = self.audit(failure=True)
        self.assertEqual(report['unknown'], [{'id': 7, 'path': self.relative_name}])
        self.assertFalse(report['changed'])
        self.assertEqual(self.record.sha256, '')
