"""Run fresh, isolated two-store MySQL regressions without loading operator .env settings."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", nargs="*", help="Optional Django test labels; omission runs the full suite.")
    parser.add_argument("--verbosity", type=int, choices=(0, 1, 2, 3), default=1)
    parser.add_argument("--failfast", action="store_true")
    args = parser.parse_args()
    password = os.environ.get("GRAND_TEST_MYSQL_PASSWORD")
    try:
        port = int(os.environ.get("GRAND_TEST_MYSQL_PORT", ""))
    except ValueError:
        parser.error("Set GRAND_TEST_MYSQL_PORT to the disposable server's loopback port.")
    if not password or not 1 <= port <= 65535:
        parser.error("Set a nonempty GRAND_TEST_MYSQL_PASSWORD and a valid GRAND_TEST_MYSQL_PORT.")
    user = os.environ.get("GRAND_TEST_MYSQL_USER", "root")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ["DJANGO_SETTINGS_MODULE"] = "src.settings.dev"
    os.environ.setdefault("SKEY", "isolated-mysql-regression-only")
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    import pymysql
    with pymysql.connect(host="127.0.0.1", port=port, user=user, password=password, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), @@sql_mode")
            version, sql_mode = cursor.fetchone()
    if "MariaDB" in version or not {"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"}.intersection(sql_mode.split(",")):
        parser.error("The regression gate requires native MySQL with strict SQL mode enabled.")
    temporary_root = root / ".tmp"
    temporary_root.mkdir(exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="mysql-regression-", dir=temporary_root))
    shutil.copytree(root / "media" / "defaults", runtime / "media" / "defaults")
    from django.conf import settings
    settings.DATABASES = {
        alias: {
            "ENGINE": "django.db.backends.mysql", "NAME": f"grand_ci_{alias}",
            "TEST": {"NAME": f"test_grand_ci_{alias}"},
            "HOST": "127.0.0.1", "PORT": port, "USER": user, "PASSWORD": password,
            "OPTIONS": {"charset": "utf8mb4"},
        }
        for alias in ("default", "finance")
    }
    settings.MEDIA_ROOT = str(runtime / "media")
    settings.GRAND_EXPORT_ROOT = str(runtime / "exports")
    settings.GRAND_BACKUP_ROOT = str(runtime / "backups")
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    import django
    django.setup()
    from django.core.management import call_command
    print(f"MySQL {version}: fresh test_grand_ci_default / test_grand_ci_finance on loopback port {port}.", flush=True)
    print(f"Isolated runtime artifacts: {runtime}", flush=True)
    # Fixed names and no --keepdb: a previous TransactionTestCase flush removes
    # data-migration fixtures without removing their migration records.
    call_command("test", *args.labels, interactive=False, keepdb=False, verbosity=args.verbosity, failfast=args.failfast)


if __name__ == "__main__":
    main()
