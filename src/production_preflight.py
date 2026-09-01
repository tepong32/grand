from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


PREFLIGHT_FORMAT = "GRAND production environment preflight"
PREFLIGHT_FORMAT_VERSION = 1
RUNTIME_ROOTS = (
    ("media", "MEDIA_ROOT"),
    ("exports", "GRAND_EXPORT_ROOT"),
    ("backups", "GRAND_BACKUP_ROOT"),
)
OPERATIONAL_REFERENCES = (
    ("deployment approval", "GRAND_DEPLOYMENT_APPROVAL_REFERENCE"),
    ("runtime storage/custody decision", "GRAND_STORAGE_CUSTODY_REFERENCE"),
    ("backup, retention, RPO/RTO policy", "GRAND_BACKUP_POLICY_REFERENCE"),
    ("monitoring and escalation plan", "GRAND_MONITORING_REFERENCE"),
    ("release rollback plan", "GRAND_ROLLBACK_PLAN_REFERENCE"),
)
PLACEHOLDER_TERMS = {
    "change-me",
    "changeme",
    "none",
    "replace-me",
    "replace-with-a-long-random-production-secret",
    "tbd",
    "todo",
}


def _check(code, category, status, message):
    return {
        "code": code,
        "category": category,
        "status": status,
        "message": message,
    }


def _is_placeholder(value):
    normalized = str(value or "").strip().lower()
    return not normalized or normalized in PLACEHOLDER_TERMS or normalized.startswith("replace-")


def _native_mysql_client_available(command, *, dump):
    configured = str(command or "").strip()
    if not configured:
        return False
    path = Path(configured).expanduser()
    if path.is_absolute() or path.parent != Path("."):
        executable = str(path) if path.is_file() else ""
    else:
        executable = shutil.which(configured) or ""
    if not executable:
        return False
    try:
        completed = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    identity = f"{Path(executable).stem} {completed.stdout} {completed.stderr}".lower()
    mysql_family = "mysql" in identity or "mariadb" in identity
    identifies_dump = "dump" in identity
    return completed.returncode == 0 and mysql_family and identifies_dump is dump


def _configuration_checks():
    checks = []
    checks.append(
        _check(
            "debug_disabled",
            "security",
            "passed" if settings.DEBUG is False else "failed",
            "Django debug mode is disabled." if settings.DEBUG is False else "Django debug mode must be disabled.",
        )
    )

    secret = str(settings.SECRET_KEY or "")
    secret_valid = len(secret) >= 50 and not _is_placeholder(secret) and "build-only" not in secret.lower()
    checks.append(
        _check(
            "secret_key_configured",
            "security",
            "passed" if secret_valid else "failed",
            "A non-placeholder production secret key is configured."
            if secret_valid
            else "Configure a non-placeholder production secret key of at least 50 characters.",
        )
    )

    hosts = [str(value).strip().lower() for value in settings.ALLOWED_HOSTS if str(value).strip()]
    external_hosts = [host for host in hosts if host not in {"localhost", "127.0.0.1", "[::1]"}]
    hosts_valid = bool(external_hosts) and "*" not in hosts
    checks.append(
        _check(
            "allowed_hosts_restricted",
            "security",
            "passed" if hosts_valid else "failed",
            "At least one explicit external hostname is allowed and no wildcard is present."
            if hosts_valid
            else "Configure at least one explicit external hostname and do not use an ALLOWED_HOSTS wildcard.",
        )
    )

    csrf_origins = [str(value).strip().lower() for value in settings.CSRF_TRUSTED_ORIGINS]
    csrf_valid = all(value.startswith("https://") for value in csrf_origins)
    checks.append(
        _check(
            "csrf_origins_https",
            "security",
            "passed" if csrf_valid else "failed",
            "Every additional trusted CSRF origin uses HTTPS."
            if csrf_valid
            else "Every configured trusted CSRF origin must use HTTPS.",
        )
    )

    security_values = {
        "SECURE_SSL_REDIRECT": getattr(settings, "SECURE_SSL_REDIRECT", False),
        "SESSION_COOKIE_SECURE": getattr(settings, "SESSION_COOKIE_SECURE", False),
        "CSRF_COOKIE_SECURE": getattr(settings, "CSRF_COOKIE_SECURE", False),
        "SECURE_PROXY_SSL_HEADER": bool(getattr(settings, "SECURE_PROXY_SSL_HEADER", None)),
        "SECURE_HSTS_SECONDS": int(getattr(settings, "SECURE_HSTS_SECONDS", 0) or 0) > 0,
    }
    missing_security = [name for name, enabled in security_values.items() if not enabled]
    checks.append(
        _check(
            "https_security_controls",
            "security",
            "passed" if not missing_security else "failed",
            "HTTPS redirect, proxy recognition, secure cookies, and an initial HSTS window are enabled."
            if not missing_security
            else "Required production HTTPS controls are disabled: " + ", ".join(missing_security),
        )
    )

    email_fields = (
        "EMAIL_HOST",
        "EMAIL_HOST_USER",
        "EMAIL_HOST_PASSWORD",
        "ASSISTANCE_FROM_EMAIL",
        "NOTIFICATIONS_FROM_EMAIL",
        "PW_RESET_FROM_EMAIL",
    )
    email_valid = all(
        not _is_placeholder(getattr(settings, name, "")) for name in email_fields
    ) and int(getattr(settings, "EMAIL_PORT", 0) or 0) > 0
    checks.append(
        _check(
            "outbound_email_configured",
            "integration",
            "passed" if email_valid else "failed",
            "The SMTP connection and all application sender addresses are configured."
            if email_valid
            else "Configure the SMTP connection and Assistance, notification, and password-reset sender addresses.",
        )
    )

    database_identities = {}
    database_configuration_valid = True
    for alias in ("default", "finance"):
        config = settings.DATABASES.get(alias, {})
        engine = str(config.get("ENGINE") or "").lower()
        required = ("NAME", "USER", "PASSWORD", "HOST", "PORT")
        valid = "mysql" in engine and all(not _is_placeholder(config.get(name)) for name in required)
        database_configuration_valid = database_configuration_valid and valid
        if valid:
            database_identities[alias] = (
                str(config["HOST"]).strip().lower(),
                str(config["PORT"]).strip(),
                str(config["NAME"]).strip().lower(),
            )
    checks.append(
        _check(
            "two_mysql_stores_configured",
            "database",
            "passed" if database_configuration_valid else "failed",
            "The default and Finance aliases each have a complete non-placeholder MySQL configuration."
            if database_configuration_valid
            else "Configure complete non-placeholder MySQL settings for both default and finance.",
        )
    )
    stores_distinct = (
        len(database_identities) == 2
        and database_identities["default"] != database_identities["finance"]
    )
    checks.append(
        _check(
            "database_stores_distinct",
            "database",
            "passed" if stores_distinct else "failed",
            "The default and Finance stores resolve to different logical database identities."
            if stores_distinct
            else "The default and Finance aliases must not resolve to the same host/port/database identity.",
        )
    )

    root_paths = {}
    roots_absolute = True
    for label, setting_name in RUNTIME_ROOTS:
        configured = Path(getattr(settings, setting_name)).expanduser()
        roots_absolute = roots_absolute and configured.is_absolute()
        root_paths[label] = configured.resolve()
    checks.append(
        _check(
            "runtime_roots_absolute",
            "storage",
            "passed" if roots_absolute else "failed",
            "Media, export, and backup roots use absolute paths."
            if roots_absolute
            else "Media, export, and backup roots must use absolute deployment paths.",
        )
    )
    root_values = list(root_paths.values())
    roots_separate = len(set(root_values)) == len(root_values) and not any(
        left in right.parents or right in left.parents
        for index, left in enumerate(root_values)
        for right in root_values[index + 1 :]
    )
    static_root = Path(settings.STATIC_ROOT).expanduser().resolve()
    roots_separate = roots_separate and all(
        root != static_root and root not in static_root.parents and static_root not in root.parents
        for root in root_values
    )
    checks.append(
        _check(
            "runtime_roots_separated",
            "storage",
            "passed" if roots_separate else "failed",
            "Media, exports, backups, and collected static files have non-overlapping roots."
            if roots_separate
            else "Media, export, backup, and static roots must be separate and non-overlapping.",
        )
    )

    dump_available = _native_mysql_client_available(
        settings.GRAND_MYSQL_DUMP_COMMAND, dump=True,
    )
    restore_available = _native_mysql_client_available(
        settings.GRAND_MYSQL_CLIENT_COMMAND, dump=False,
    )
    checks.append(
        _check(
            "native_mysql_clients_available",
            "recovery",
            "passed" if dump_available and restore_available else "failed",
            "Native MySQL dump and restore clients are available in the release environment."
            if dump_available and restore_available
            else "Install or configure both native MySQL dump and restore clients.",
        )
    )

    static_ready = static_root.is_dir() and (static_root / "admin" / "css" / "base.css").is_file()
    checks.append(
        _check(
            "collected_static_assets_present",
            "release",
            "passed" if static_ready else "failed",
            "Collected Django administration assets are present in the release."
            if static_ready
            else "Run collectstatic in the release image and retain the collected assets.",
        )
    )

    missing_references = [
        label
        for label, setting_name in OPERATIONAL_REFERENCES
        if _is_placeholder(getattr(settings, setting_name, ""))
    ]
    checks.append(
        _check(
            "operational_decision_references_present",
            "governance",
            "passed" if not missing_references else "failed",
            "All required non-secret deployment decision references are configured."
            if not missing_references
            else "Missing approved reference(s): " + ", ".join(missing_references),
        )
    )
    return checks


def _database_live_checks(alias):
    connection = connections[alias]
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        connected = bool(row and row[0] == 1)
    except Exception:
        return [
            _check(
                f"{alias}_database_connectivity",
                "database",
                "failed",
                f"The {alias} database did not pass a live connection query; inspect restricted deployment logs.",
            ),
            _check(
                f"{alias}_migrations_current",
                "database",
                "not_run",
                f"Migration state was not checked because the {alias} database connection failed.",
            ),
        ]

    checks = [
        _check(
            f"{alias}_database_connectivity",
            "database",
            "passed" if connected else "failed",
            f"The {alias} database passed a live connection query."
            if connected
            else f"The {alias} database returned an unexpected live-query result.",
        )
    ]
    try:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        checks.append(
            _check(
                f"{alias}_migrations_current",
                "database",
                "failed",
                f"The {alias} migration state could not be evaluated; inspect restricted deployment logs.",
            )
        )
    else:
        checks.append(
            _check(
                f"{alias}_migrations_current",
                "database",
                "passed" if not pending else "failed",
                f"The {alias} database has no unapplied migrations."
                if not pending
                else f"The {alias} database still has unapplied migrations.",
            )
        )
    return checks


def _probe_root(label, setting_name):
    root = Path(getattr(settings, setting_name)).expanduser().resolve()
    source = root / f".grand-preflight-{uuid.uuid4().hex}.tmp"
    destination = root / f".grand-preflight-{uuid.uuid4().hex}.verified"
    payload = f"GRAND {label} atomic storage probe\n".encode("utf-8")
    probe_succeeded = False
    try:
        if not root.is_dir():
            raise OSError("configured root is not an existing directory")
        with source.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(source, destination)
        if destination.read_bytes() != payload:
            raise OSError("atomic probe content changed")
        probe_succeeded = True
    except OSError:
        probe_succeeded = False
    cleanup_succeeded = True
    for path in (source, destination):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            cleanup_succeeded = False
    if not probe_succeeded or not cleanup_succeeded:
        return _check(
            f"{label}_root_atomic_write",
            "storage",
            "failed",
            f"The configured {label} root failed its create, fsync, atomic-rename, read-back, or cleanup probe.",
        )
    return _check(
        f"{label}_root_atomic_write",
        "storage",
        "passed",
        f"The configured {label} root passed create, fsync, atomic rename, read-back, and cleanup.",
    )


def _release_version():
    try:
        return (Path(settings.BASE_DIR) / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def evaluate_production_preflight(*, configuration_only=False):
    configuration_checks = _configuration_checks()
    configuration_passed = all(item["status"] == "passed" for item in configuration_checks)
    live_checks = []
    if not configuration_only:
        if configuration_passed:
            for alias in ("default", "finance"):
                live_checks.extend(_database_live_checks(alias))
            for label, setting_name in RUNTIME_ROOTS:
                live_checks.append(_probe_root(label, setting_name))
        else:
            live_checks.append(
                _check(
                    "live_checks_deferred",
                    "preflight",
                    "not_run",
                    "Correct the configuration failures before probing databases or runtime storage.",
                )
            )
    selected_checks = configuration_checks + live_checks
    selected_scope_passed = all(item["status"] == "passed" for item in selected_checks)
    live_checks_passed = (
        None
        if configuration_only
        else bool(live_checks) and all(item["status"] == "passed" for item in live_checks)
    )
    checked_at = timezone.now()
    receipt = {
        "application": "GRAND",
        "format": PREFLIGHT_FORMAT,
        "format_version": PREFLIGHT_FORMAT_VERSION,
        "scope": "configuration" if configuration_only else "live_environment",
        "checked_at": checked_at.isoformat(),
        "application_version": _release_version(),
        "release_revision": str(
            os.getenv("RENDER_GIT_COMMIT") or os.getenv("GRAND_RELEASE_REVISION") or "unknown"
        ).strip()[:200],
        "configuration_passed": configuration_passed,
        "live_checks_passed": live_checks_passed,
        "selected_scope_passed": selected_scope_passed,
        "deployment_preflight_passed": bool(not configuration_only and selected_scope_passed),
        "restore_tested": False,
        "cutover_authorized": False,
        "checks": selected_checks,
    }
    receipt["receipt_checksum"] = hashlib.sha256(
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    ).hexdigest()
    return receipt
