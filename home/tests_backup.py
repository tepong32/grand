import gzip
import hashlib
import io
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from src.database_backups import BackupError, create_backup_set, verify_backup_set


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "grand_main",
        "USER": "grand",
        "PASSWORD": "secret",
        "HOST": "database.internal",
        "PORT": "3306",
    },
    "finance": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "grand_finance",
        "USER": "grand_finance",
        "PASSWORD": "secret",
        "HOST": "database.internal",
        "PORT": "3306",
    },
}


def write_synthetic_dump(alias, _database, target):
    with gzip.open(target, "wb") as output:
        output.write(f"-- synthetic {alias} SQL dump\nCREATE TABLE evidence (id int);\n".encode())


@override_settings(DATABASES=DATABASES, GRAND_BACKUP_RETENTION_COUNT=0)
class DatabaseBackupTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "grand-backups"

    def tearDown(self):
        self.temporary.cleanup()

    def create(self, **overrides):
        options = {
            "backup_root": self.root,
            "dump_writer": write_synthetic_dump,
            "created_at": datetime(2026, 9, 1, 8, 30, tzinfo=timezone.utc),
        }
        options.update(overrides)
        return create_backup_set(**options)

    def test_complete_set_is_verified_then_published_with_portable_manifest(self):
        result = self.create()

        self.assertTrue((self.root / "GRAND_BACKUP_ROOT.json").is_file())
        self.assertTrue(result["path"].is_dir())
        self.assertFalse((self.root / ".grand-backup.lock").exists())
        self.assertFalse(any((self.root / ".tmp").iterdir()))
        manifest = json.loads((result["path"] / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["scope"], "complete")
        self.assertEqual(manifest["status"], "completed")
        self.assertFalse(manifest["restore_tested"])
        self.assertEqual(len(result["manifest_sha256"]), 64)
        self.assertEqual(
            {item["database_alias"] for item in manifest["databases"]},
            {"default", "finance"},
        )
        for item in manifest["databases"]:
            artifact = result["path"] / item["filename"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            self.assertEqual(artifact.stat().st_size, item["byte_length"])

    def test_failure_does_not_publish_partial_set_and_releases_lock(self):
        def failing_writer(alias, database, target):
            write_synthetic_dump(alias, database, target)
            if alias == "finance":
                raise RuntimeError("synthetic dump failure")

        with self.assertRaisesMessage(BackupError, "synthetic dump failure"):
            self.create(dump_writer=failing_writer)

        self.assertEqual(list(self.root.glob("[0-9][0-9][0-9][0-9]/*/*/*")), [])
        self.assertFalse((self.root / ".grand-backup.lock").exists())

    def test_empty_compressed_dump_is_rejected(self):
        def empty_writer(_alias, _database, target):
            with gzip.open(target, "wb"):
                pass

        with self.assertRaisesMessage(BackupError, "contains no SQL data"):
            self.create(dump_writer=empty_writer)

    def test_existing_lock_rejects_duplicate_run_without_disturbing_it(self):
        self.root.mkdir(parents=True)
        (self.root / ".grand-backup.lock").mkdir()

        with self.assertRaisesMessage(BackupError, "already running"):
            self.create()

        self.assertTrue((self.root / ".grand-backup.lock").is_dir())

    @override_settings(GRAND_EXPORT_ROOT=".")
    def test_backup_root_cannot_overlap_user_export_root(self):
        with self.assertRaisesMessage(BackupError, "must be separate"):
            create_backup_set(
                backup_root=Path(".") / "restricted-backups",
                dump_writer=write_synthetic_dump,
            )

    def test_retention_removes_only_oldest_completed_sets(self):
        first = self.create(created_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        second = self.create(created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
        third = self.create(
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            retention_count=2,
        )

        self.assertFalse(first["path"].exists())
        self.assertTrue(second["path"].exists())
        self.assertTrue(third["path"].exists())
        self.assertEqual(
            third["removed_by_retention"],
            [first["path"].relative_to(self.root.resolve()).as_posix()],
        )

    @patch("home.management.commands.backup_databases.create_backup_set")
    def test_management_command_converts_backup_failure_to_nonzero_error(self, create):
        create.side_effect = BackupError("database unavailable")

        with self.assertRaisesMessage(CommandError, "database unavailable"):
            call_command("backup_databases")

    def test_partial_invocation_is_truthfully_labeled(self):
        result = self.create(database_aliases=("finance",))
        self.assertEqual(result["manifest"]["scope"], "partial")

    def test_copied_complete_set_verifies_against_separately_retained_manifest_hash(self):
        result = self.create()

        receipt = verify_backup_set(
            result["path"],
            expected_manifest_sha256=result["manifest_sha256"],
        )

        self.assertTrue(receipt["integrity_verified"])
        self.assertTrue(receipt["authenticity_verified"])
        self.assertFalse(receipt["restore_tested"])
        self.assertEqual(
            {item["database_alias"] for item in receipt["artifacts"]},
            {"default", "finance"},
        )

    def test_changed_valid_gzip_artifact_is_rejected(self):
        result = self.create()
        artifact = next(result["path"].glob("grand-default-*.sql.gz"))
        with gzip.open(artifact, "wb") as output:
            output.write(b"-- substituted SQL dump\n")

        with self.assertRaisesMessage(BackupError, "size does not match"):
            verify_backup_set(result["path"])

    def test_separately_retained_manifest_hash_detects_manifest_replacement(self):
        result = self.create()
        manifest_path = result["path"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["application_version"] = "substituted"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        with self.assertRaisesMessage(BackupError, "separately retained value"):
            verify_backup_set(
                result["path"],
                expected_manifest_sha256=result["manifest_sha256"],
            )

    def test_complete_scope_requires_exactly_both_database_aliases(self):
        result = self.create()
        manifest_path = result["path"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["databases"] = [
            item for item in manifest["databases"] if item["database_alias"] == "default"
        ]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        with self.assertRaisesMessage(BackupError, "exactly default and finance"):
            verify_backup_set(result["path"])

    def test_partial_set_requires_explicit_diagnostic_allowance(self):
        result = self.create(database_aliases=("finance",))

        with self.assertRaisesMessage(BackupError, "partial backup set"):
            verify_backup_set(result["path"])
        receipt = verify_backup_set(result["path"], allow_partial=True)
        self.assertEqual(receipt["scope"], "partial")

    def test_unsafe_manifest_artifact_path_is_rejected(self):
        result = self.create()
        manifest_path = result["path"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["databases"][0]["filename"] = "../outside.sql.gz"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        with self.assertRaisesMessage(BackupError, "unsafe artifact filename"):
            verify_backup_set(result["path"])

    def test_manifest_cannot_be_rewritten_to_claim_restore_success(self):
        result = self.create()
        manifest_path = result["path"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["restore_tested"] = True
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        with self.assertRaisesMessage(BackupError, "separate evidence"):
            verify_backup_set(result["path"])

    def test_unmanifested_sql_artifact_is_rejected(self):
        result = self.create()
        write_synthetic_dump("unknown", {}, result["path"] / "unlisted.sql.gz")

        with self.assertRaisesMessage(BackupError, "unmanifested SQL"):
            verify_backup_set(result["path"])

    def test_verification_command_emits_machine_readable_receipt(self):
        result = self.create()
        output = io.StringIO()

        call_command(
            "verify_database_backup",
            str(result["path"]),
            expect_manifest_sha256=result["manifest_sha256"],
            as_json=True,
            stdout=output,
        )

        receipt = json.loads(output.getvalue())
        self.assertTrue(receipt["authenticity_verified"])
        self.assertFalse(receipt["restore_tested"])


class NativeDumpBoundaryTests(SimpleTestCase):
    @override_settings(GRAND_MYSQL_DUMP_COMMAND="mysqldump")
    def test_local_sqlite_is_not_silently_copied_as_a_production_backup(self):
        from src.database_backups import _write_mysql_dump

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesMessage(BackupError, "native MySQL logical dump"):
                _write_mysql_dump(
                    "default",
                    {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"},
                    Path(temporary) / "dump.sql.gz",
                )

    @override_settings(GRAND_MYSQL_DUMP_COMMAND="mysqldump")
    @patch("src.database_backups.subprocess.Popen")
    def test_native_dump_keeps_password_out_of_process_arguments(self, popen):
        from src.database_backups import _write_mysql_dump

        class Process:
            def __init__(self):
                self.stdout = io.BytesIO(b"-- native synthetic SQL\n")

            def poll(self):
                return 0

            def terminate(self):
                return None

            def wait(self):
                return 0

        popen.return_value = Process()
        database = {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "grand_main",
            "USER": "grand_user",
            "PASSWORD": "do-not-expose-this-secret",
            "HOST": "database.internal",
            "PORT": "3306",
        }
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "dump.sql.gz"
            _write_mysql_dump("default", database, target)

            arguments = popen.call_args.args[0]
            self.assertNotIn(database["PASSWORD"], " ".join(arguments))
            option_path = Path(arguments[1].split("=", 1)[1])
            self.assertFalse(option_path.exists())
            with gzip.open(target, "rb") as source:
                self.assertEqual(source.read(), b"-- native synthetic SQL\n")
