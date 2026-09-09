import gzip
import hashlib
import io
import json
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        self.capture = MagicMock()
        self.capture.receipt.return_value = {
            "mode": "mysql_global_read_lock",
            "server_uuid": "11111111-1111-1111-1111-111111111111",
            "connection_id": 42,
            "started_at": "2026-09-01T08:30:00+00:00",
            "completed_at": "2026-09-01T08:30:01+00:00",
        }
        @contextmanager
        def synthetic_capture(_aliases):
            yield self.capture
        capture_patch = patch("src.database_backups._capture_mysql_snapshot", synthetic_capture)
        capture_patch.start()
        self.addCleanup(capture_patch.stop)

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
        self.assertTrue(verify_backup_set(result["path"])["coordinated_capture_recorded"])
        self.assertEqual(
            {item["database_alias"] for item in manifest["databases"]},
            {"default", "finance"},
        )
        for item in manifest["databases"]:
            artifact = result["path"] / item["filename"]
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item["sha256"])
            self.assertEqual(artifact.stat().st_size, item["byte_length"])

    def test_lost_capture_after_dump_does_not_publish_and_preserves_prior_set(self):
        prior = self.create()
        self.capture.verify.side_effect = [None, BackupError("capture lost")]
        with self.assertRaisesMessage(BackupError, "capture lost"):
            self.create()
        self.assertTrue(prior["path"].is_dir())
        self.assertFalse(any((self.root / ".tmp").iterdir()))
        self.assertFalse((self.root / ".grand-backup.lock").exists())

    def test_old_manifest_integrity_does_not_claim_coordinated_capture(self):
        result = self.create()
        path = result["path"] / "manifest.json"
        manifest = json.loads(path.read_text())
        del manifest["capture"]
        path.write_text(json.dumps(manifest))
        self.assertFalse(verify_backup_set(result["path"])["coordinated_capture_recorded"])

    def test_invalid_capture_receipt_is_rejected(self):
        result = self.create()
        path = result["path"] / "manifest.json"
        manifest = json.loads(path.read_text())
        for invalid in (True, 0, "42"):
            manifest["capture"]["connection_id"] = invalid
            path.write_text(json.dumps(manifest))
            with self.assertRaisesMessage(BackupError, "invalid coordinated capture"):
                verify_backup_set(result["path"])
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


@override_settings(DATABASES=DATABASES)
class CoordinatedCaptureTests(SimpleTestCase):
    server = "11111111-1111-1111-1111-111111111111"

    def setUp(self):
        registry_patch = patch("src.database_backups.connections")
        self.registry = registry_patch.start()
        self.addCleanup(registry_patch.stop)
        self.opened = []
        for index, alias in enumerate(("default", "finance"), start=1):
            connection = MagicMock()
            connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (self.server, index)
            self.opened.append(connection)
        self.registry.__getitem__.side_effect = lambda alias: MagicMock(copy=MagicMock(return_value=self.opened[("default", "finance").index(alias)]))

    def test_one_read_lock_spans_both_dumps_and_sessions_are_closed(self):
        from src.database_backups import _capture_mysql_snapshot
        with _capture_mysql_snapshot(("default", "finance")) as capture:
            capture.verify()
            self.assertEqual(capture.receipt()["mode"], "mysql_global_read_lock")
            for connection in self.opened:
                connection.close.assert_not_called()
        cursor = self.opened[0].cursor.return_value.__enter__.return_value
        self.assertEqual(sum(call.args[0] == "FLUSH TABLES WITH READ LOCK" for call in cursor.execute.call_args_list), 1)
        for connection in self.opened:
            connection.close.assert_called_once()

    def test_different_servers_are_rejected_before_capture(self):
        from src.database_backups import _capture_mysql_snapshot
        self.opened[1].cursor.return_value.__enter__.return_value.fetchone.return_value = ("22222222-2222-2222-2222-222222222222", 2)
        with self.assertRaisesMessage(BackupError, "different MySQL servers"):
            with _capture_mysql_snapshot(("default", "finance")):
                self.fail("Must not capture independently")
        self.assertFalse(any(call.args[0] == "FLUSH TABLES WITH READ LOCK" for call in self.opened[0].cursor.return_value.__enter__.return_value.execute.call_args_list))
        for connection in self.opened:
            connection.close.assert_called_once()

    def test_reconnection_invalidates_capture_and_releases_sessions(self):
        from src.database_backups import _capture_mysql_snapshot
        with self.assertRaisesMessage(BackupError, "connection changed"):
            with _capture_mysql_snapshot(("default", "finance")) as capture:
                self.opened[0].cursor.return_value.__enter__.return_value.fetchone.return_value = (self.server, 99)
                capture.verify()
        for connection in self.opened:
            connection.close.assert_called_once()

    def test_missing_lock_privilege_fails_closed_and_closes_sessions(self):
        from src.database_backups import _capture_mysql_snapshot
        def execute(statement):
            if statement == "FLUSH TABLES WITH READ LOCK":
                raise RuntimeError("synthetic denied privilege")
        self.opened[0].cursor.return_value.__enter__.return_value.execute.side_effect = execute
        with self.assertRaisesMessage(BackupError, "No backup set was published"):
            with _capture_mysql_snapshot(("default", "finance")):
                self.fail("Must not enter capture")
        for connection in self.opened:
            connection.close.assert_called_once()


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
