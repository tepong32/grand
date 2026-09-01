import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from src.production_preflight import (
    _native_mysql_client_available,
    _probe_root,
    evaluate_production_preflight,
)


class ProductionPreflightTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="grand-production-preflight-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.media_root = self.root / "runtime" / "media"
        self.export_root = self.root / "runtime" / "exports"
        self.backup_root = self.root / "runtime" / "backups"
        self.static_root = self.root / "staticfiles"
        for path in (self.media_root, self.export_root, self.backup_root):
            path.mkdir(parents=True)
        admin_css = self.static_root / "admin" / "css"
        admin_css.mkdir(parents=True)
        (admin_css / "base.css").write_text("/* collected */\n", encoding="utf-8")
        self.settings_override = override_settings(
            DEBUG=False,
            SECRET_KEY="a-production-secret-with-more-than-fifty-characters-1234567890",
            ALLOWED_HOSTS=["grand.example.gov.ph", "127.0.0.1", "localhost"],
            CSRF_TRUSTED_ORIGINS=["https://grand.example.gov.ph"],
            SECURE_SSL_REDIRECT=True,
            SESSION_COOKIE_SECURE=True,
            CSRF_COOKIE_SECURE=True,
            SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
            SECURE_HSTS_SECONDS=3600,
            EMAIL_HOST="smtp.example.gov.ph",
            EMAIL_PORT=465,
            EMAIL_HOST_USER="grand@example.gov.ph",
            EMAIL_HOST_PASSWORD="smtp-test-secret",
            ASSISTANCE_FROM_EMAIL="assistance@example.gov.ph",
            NOTIFICATIONS_FROM_EMAIL="notifications@example.gov.ph",
            PW_RESET_FROM_EMAIL="password-reset@example.gov.ph",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.mysql",
                    "NAME": "grand",
                    "USER": "grand_app",
                    "PASSWORD": "default-test-secret",
                    "HOST": "mysql.internal",
                    "PORT": "3306",
                },
                "finance": {
                    "ENGINE": "django.db.backends.mysql",
                    "NAME": "grand_finance",
                    "USER": "grand_finance_app",
                    "PASSWORD": "finance-test-secret",
                    "HOST": "mysql.internal",
                    "PORT": "3306",
                },
            },
            MEDIA_ROOT=self.media_root,
            GRAND_EXPORT_ROOT=self.export_root,
            GRAND_BACKUP_ROOT=self.backup_root,
            STATIC_ROOT=self.static_root,
            GRAND_MYSQL_DUMP_COMMAND="mysqldump",
            GRAND_MYSQL_CLIENT_COMMAND="mysql",
            GRAND_DEPLOYMENT_APPROVAL_REFERENCE="DEPLOY-2026-001",
            GRAND_STORAGE_CUSTODY_REFERENCE="STORAGE-2026-001",
            GRAND_BACKUP_POLICY_REFERENCE="RECOVERY-2026-001",
            GRAND_MONITORING_REFERENCE="MONITOR-2026-001",
            GRAND_ROLLBACK_PLAN_REFERENCE="ROLLBACK-2026-001",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    @patch("src.production_preflight._native_mysql_client_available", return_value=True)
    def test_configuration_receipt_passes_without_claiming_live_or_cutover_acceptance(self, _client):
        receipt = evaluate_production_preflight(configuration_only=True)

        self.assertTrue(receipt["configuration_passed"])
        self.assertTrue(receipt["selected_scope_passed"])
        self.assertIsNone(receipt["live_checks_passed"])
        self.assertFalse(receipt["deployment_preflight_passed"])
        self.assertFalse(receipt["restore_tested"])
        self.assertFalse(receipt["cutover_authorized"])
        self.assertEqual(len(receipt["receipt_checksum"]), 64)
        serialized = json.dumps(receipt)
        self.assertNotIn("default-test-secret", serialized)
        self.assertNotIn("finance-test-secret", serialized)
        self.assertNotIn("smtp-test-secret", serialized)

    @patch("src.production_preflight._native_mysql_client_available", return_value=True)
    def test_live_receipt_requires_both_database_and_all_storage_probes(self, _client):
        database_results = lambda alias: [
            {
                "code": f"{alias}_database_connectivity",
                "category": "database",
                "status": "passed",
                "message": "Passed.",
            },
            {
                "code": f"{alias}_migrations_current",
                "category": "database",
                "status": "passed",
                "message": "Passed.",
            },
        ]
        storage_result = lambda label, _setting: {
            "code": f"{label}_root_atomic_write",
            "category": "storage",
            "status": "passed",
            "message": "Passed.",
        }
        with patch("src.production_preflight._database_live_checks", side_effect=database_results), patch(
            "src.production_preflight._probe_root", side_effect=storage_result
        ):
            receipt = evaluate_production_preflight()

        self.assertTrue(receipt["live_checks_passed"])
        self.assertTrue(receipt["deployment_preflight_passed"])
        self.assertFalse(receipt["restore_tested"])
        self.assertFalse(receipt["cutover_authorized"])

    @patch("src.production_preflight._native_mysql_client_available", return_value=True)
    def test_overlapping_runtime_root_fails_before_live_probes(self, _client):
        with override_settings(GRAND_EXPORT_ROOT=self.media_root / "nested"):
            receipt = evaluate_production_preflight()

        statuses = {item["code"]: item["status"] for item in receipt["checks"]}
        self.assertEqual(statuses["runtime_roots_separated"], "failed")
        self.assertEqual(statuses["live_checks_deferred"], "not_run")
        self.assertFalse(receipt["selected_scope_passed"])

    @patch("src.production_preflight._native_mysql_client_available", return_value=True)
    @override_settings(GRAND_BACKUP_POLICY_REFERENCE="replace-me")
    def test_missing_operational_reference_fails_with_plain_language_reason(self, _client):
        receipt = evaluate_production_preflight(configuration_only=True)

        check = next(
            item for item in receipt["checks"]
            if item["code"] == "operational_decision_references_present"
        )
        self.assertEqual(check["status"], "failed")
        self.assertIn("backup, retention, RPO/RTO policy", check["message"])

    def test_atomic_storage_probe_writes_renames_reads_and_cleans_up(self):
        check = _probe_root("media", "MEDIA_ROOT")

        self.assertEqual(check["status"], "passed")
        self.assertEqual(list(self.media_root.iterdir()), [])

    @patch("src.production_preflight._native_mysql_client_available", return_value=True)
    def test_json_management_command_emits_non_secret_configuration_receipt(self, _client):
        output = io.StringIO()

        call_command(
            "production_preflight",
            configuration_only=True,
            as_json=True,
            stdout=output,
        )

        receipt = json.loads(output.getvalue())
        self.assertTrue(receipt["selected_scope_passed"])
        self.assertFalse(receipt["deployment_preflight_passed"])

    @patch("src.production_preflight._native_mysql_client_available", return_value=False)
    def test_command_returns_nonzero_when_a_required_client_is_missing(self, _client):
        output = io.StringIO()

        with self.assertRaises(CommandError):
            call_command(
                "production_preflight",
                configuration_only=True,
                as_json=True,
                stdout=output,
            )

        receipt = json.loads(output.getvalue())
        self.assertFalse(receipt["selected_scope_passed"])
        self.assertEqual(
            next(
                item["status"] for item in receipt["checks"]
                if item["code"] == "native_mysql_clients_available"
            ),
            "failed",
        )

    @patch("src.production_preflight.subprocess.run")
    def test_arbitrary_executable_does_not_pass_as_mysql_client(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout="Python 3.11.0",
            stderr="",
        )

        self.assertFalse(
            _native_mysql_client_available(sys.executable, dump=False)
        )

    @patch("src.production_preflight.subprocess.run")
    @patch("src.production_preflight.shutil.which")
    def test_mysql_dump_and_restore_client_identities_are_distinguished(self, which, run):
        which.side_effect = lambda command: f"C:/tools/{command}.exe"
        run.side_effect = (
            SimpleNamespace(
                returncode=0,
                stdout="mysqldump Ver 8.0 Distrib 8.0, for Win64 (MySQL Community)",
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout="mysql Ver 8.0 Distrib 8.0, for Win64 (MySQL Community)",
                stderr="",
            ),
        )

        self.assertTrue(_native_mysql_client_available("mysqldump", dump=True))
        self.assertTrue(_native_mysql_client_available("mysql", dump=False))
