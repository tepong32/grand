"""Actual GRAND wiring, rather than the source harness's injected settings."""
from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.db import connections
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse, resolve
from inventory.checks import check_private_storage
from . import test_grand_asset_authority


class StorageConfigurationTests(SimpleTestCase):
    def test_public_and_relative_roots_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(MEDIA_ROOT=root / "media", STATIC_ROOT=root / "static", STATICFILES_DIRS=[]):
                for value in ("relative", root / "media", root / "media" / "private", root / "static" / "private"):
                    with self.subTest(value=str(value)), override_settings(DISPOSAL_PRIVATE_ROOT=value):
                        self.assertTrue(check_private_storage(None))
                with override_settings(DISPOSAL_PRIVATE_ROOT=root / "private"):
                    self.assertEqual(check_private_storage(None), [])

    def test_production_startup_requires_protected_storage(self):
        import os
        import subprocess
        import sys
        with TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, DJANGO_SETTINGS_MODULE="src.settings.prod",
                SKEY="synthetic-settings-test-only", DEFAULT_DB_NAME="unused_default",
                DEFAULT_DB_USER="unused", DEFAULT_DB_PASSWORD="unused",
                FINANCE_DB_NAME="unused_finance", FINANCE_DB_USER="unused",
                FINANCE_DB_PASSWORD="unused", GRAND_MEDIA_ROOT=str(root / "media"))
            env.pop("DISPOSAL_PRIVATE_ROOT", None)
            command = [sys.executable, "-c", "import dotenv; dotenv.load_dotenv=lambda *a,**k:False; import django; django.setup()"]
            for value, expected in ((None, False), (root / "media" / "private", False), (root / "private", True)):
                if value is not None:
                    env["DISPOSAL_PRIVATE_ROOT"] = str(value)
                result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
                with self.subTest(value=str(value)):
                    self.assertEqual(result.returncode == 0, expected, result.stderr)

    def test_native_urls_are_registered(self):
        self.assertEqual(settings.ROOT_URLCONF, "src.urls")
        url = reverse("inventory:par-preparation")
        self.assertTrue(url.startswith("/gso/inventory/"))
        self.assertEqual(resolve(url).view_name, "inventory:par-preparation")


class DestinationAuthorityTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_asset_authority.GrandAssetAuthorityTests.setUpTestData.__func__(cls)

    def test_native_dashboard_links_follow_explicit_grants(self):
        from departments.services.dashboard_service import _workspace_sections
        for actor, allowed in ((self.clerk, True), (self.viewer, True), (self.super_no_grant, False)):
            sections = _workspace_sections(self.gso, actor)
            destinations = {item.get("url_name") for item in sections}
            self.assertEqual("inventory:asset-list" in destinations, allowed)
            self.assertEqual("inventory:property-register" in destinations, allowed)
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("department_dashboard"))

    def test_inventory_tables_only_exist_in_default(self):
        for alias in ("default", "finance"):
            tables = connections[alias].introspection.table_names()
            self.assertEqual("inventory_asset" in tables, alias == "default")
            self.assertEqual(any(t.startswith("inventory_finance_") for t in tables), alias == "default")
