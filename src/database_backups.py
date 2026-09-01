from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.utils import timezone


ROOT_MARKER = "GRAND_BACKUP_ROOT.json"
LOCK_DIRECTORY = ".grand-backup.lock"
TEMP_DIRECTORY = ".tmp"


class BackupError(RuntimeError):
    """Raised when a complete, verified backup set cannot be published."""


@dataclass(frozen=True)
class BackupArtifact:
    database_alias: str
    logical_name: str
    engine: str
    filename: str
    byte_length: int
    sha256: str


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_backup_root(root: Path) -> None:
    export_root = Path(settings.GRAND_EXPORT_ROOT).expanduser().resolve()
    if (
        root == export_root
        or root.is_relative_to(export_root)
        or export_root.is_relative_to(root)
    ):
        raise BackupError(
            "GRAND_BACKUP_ROOT must be separate from GRAND_EXPORT_ROOT so restricted "
            "database recovery data cannot enter the user-export archive."
        )
    root.mkdir(parents=True, exist_ok=True)
    marker_path = root / ROOT_MARKER
    expected = {
        "application": "GRAND",
        "format": "GRAND database backup root",
        "version": 1,
        "publication_rule": (
            "Only non-dot backup-set directories containing a completed manifest are portable. "
            "Ignore .tmp and .grand-backup.lock."
        ),
    }
    if marker_path.exists():
        try:
            current = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BackupError(f"Backup-root marker is unreadable: {marker_path}") from exc
        if current.get("application") != "GRAND" or current.get("version") != 1:
            raise BackupError(f"Refusing unrecognized backup root: {root}")
        return
    _atomic_write(
        marker_path,
        json.dumps(expected, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )


def _acquire_lock(root: Path) -> Path:
    lock = root / LOCK_DIRECTORY
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise BackupError(
            f"Another GRAND database backup is already running (lock: {lock})."
        ) from exc
    owner = {
        "pid": os.getpid(),
        "started_at": timezone.now().isoformat(),
    }
    _atomic_write(
        lock / "owner.json",
        json.dumps(owner, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return lock


def _release_lock(lock: Path) -> None:
    if not lock.exists():
        return
    for child in lock.iterdir():
        if child.is_file():
            child.unlink()
    lock.rmdir()


def _option_file_value(value: object, label: str) -> str:
    text = str(value or "")
    if any(character in text for character in ("\0", "\r", "\n")):
        raise BackupError(f"The {label} database setting contains an unsupported line break.")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _write_mysql_dump(database_alias: str, database: dict, target: Path) -> None:
    """Stream a native MySQL logical dump into gzip without exposing its password in argv."""
    engine = str(database.get("ENGINE") or "")
    if "mysql" not in engine.lower():
        raise BackupError(
            f"Database {database_alias!r} uses {engine or 'an unknown engine'}; "
            "production backups require a native MySQL logical dump."
        )

    name = str(database.get("NAME") or "").strip()
    if not name:
        raise BackupError(f"Database {database_alias!r} has no configured NAME.")
    if any(character in name for character in ("\0", "\r", "\n")):
        raise BackupError(f"Database {database_alias!r} has an invalid NAME.")

    option_lines = [
        "[client]",
        f"user={_option_file_value(database.get('USER'), 'user')}",
        f"password={_option_file_value(database.get('PASSWORD'), 'password')}",
        f"host={_option_file_value(database.get('HOST') or 'localhost', 'host')}",
        f"port={_option_file_value(database.get('PORT') or '3306', 'port')}",
        "default-character-set=utf8mb4",
        "",
    ]
    option_path: Path | None = None
    target.unlink(missing_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".mysql-client-",
            suffix=".cnf",
            dir=target.parent,
            delete=False,
        ) as option_file:
            option_file.write("\n".join(option_lines))
            option_path = Path(option_file.name)
        try:
            option_path.chmod(0o600)
        except OSError:
            pass

        command = [
            str(getattr(settings, "GRAND_MYSQL_DUMP_COMMAND", "mysqldump")),
            f"--defaults-extra-file={option_path}",
            "--single-transaction",
            "--quick",
            "--routines",
            "--triggers",
            "--hex-blob",
            "--databases",
            name,
        ]
        with tempfile.TemporaryFile() as error_stream:
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=error_stream,
                )
            except OSError as exc:
                raise BackupError(
                    f"Could not start the configured MySQL dump command for {database_alias!r}."
                ) from exc
            assert process.stdout is not None
            try:
                with gzip.open(target, "xb") as compressed:
                    shutil.copyfileobj(process.stdout, compressed, length=1024 * 1024)
            except Exception:
                if process.poll() is None:
                    process.terminate()
                process.wait()
                raise
            finally:
                process.stdout.close()
            return_code = process.wait()
            if return_code:
                error_stream.seek(0)
                detail = error_stream.read(4096).decode("utf-8", errors="replace").strip()
                if detail:
                    detail = f" Detail: {detail}"
                raise BackupError(
                    f"MySQL dump failed for {database_alias!r} with exit code {return_code}.{detail}"
                )
    finally:
        if option_path is not None:
            option_path.unlink(missing_ok=True)
        if target.exists() and target.stat().st_size == 0:
            target.unlink()


def _verify_artifact(path: Path) -> tuple[int, str]:
    try:
        decompressed_length = 0
        with gzip.open(path, "rb") as source:
            while chunk := source.read(1024 * 1024):
                decompressed_length += len(chunk)
    except (OSError, EOFError) as exc:
        raise BackupError(f"Backup artifact is not a valid gzip stream: {path.name}") from exc
    if decompressed_length == 0:
        raise BackupError(f"Backup artifact contains no SQL data: {path.name}")

    digest = hashlib.sha256()
    byte_length = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            byte_length += len(chunk)
            digest.update(chunk)
    return byte_length, digest.hexdigest()


def _application_version() -> str:
    version_path = Path(settings.BASE_DIR) / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _completed_backup_sets(root: Path) -> list[tuple[str, Path]]:
    completed: list[tuple[str, Path]] = []
    for manifest_path in root.glob("[0-9][0-9][0-9][0-9]/*/*/*/manifest.json"):
        directory = manifest_path.parent.resolve()
        try:
            relative = directory.relative_to(root.resolve())
        except ValueError:
            continue
        if len(relative.parts) != 4:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            manifest.get("application") == "GRAND"
            and manifest.get("format") == "GRAND database backup set"
            and manifest.get("status") == "completed"
        ):
            completed.append((str(manifest.get("created_at") or ""), directory))
    return sorted(completed, key=lambda item: (item[0], str(item[1])), reverse=True)


def _apply_retention(root: Path, keep: int) -> list[str]:
    if keep <= 0:
        return []
    removed = []
    for _created_at, directory in _completed_backup_sets(root)[keep:]:
        relative = directory.relative_to(root.resolve()).as_posix()
        shutil.rmtree(directory)
        removed.append(relative)
    return removed


def create_backup_set(
    *,
    database_aliases: tuple[str, ...] = ("default", "finance"),
    backup_root: str | Path | None = None,
    retention_count: int | None = None,
    dump_writer=None,
    created_at: datetime | None = None,
) -> dict:
    """Create, verify, and atomically publish one logical database backup set."""
    aliases = tuple(dict.fromkeys(database_aliases))
    if not aliases:
        raise BackupError("At least one database alias is required.")
    unknown = [alias for alias in aliases if alias not in settings.DATABASES]
    if unknown:
        raise BackupError(f"Unknown database alias(es): {', '.join(unknown)}")
    keep = (
        int(settings.GRAND_BACKUP_RETENTION_COUNT)
        if retention_count is None
        else int(retention_count)
    )
    if keep < 0:
        raise BackupError("Backup retention count cannot be negative.")

    root = Path(backup_root or settings.GRAND_BACKUP_ROOT).expanduser().resolve()
    _ensure_backup_root(root)
    lock = _acquire_lock(root)
    now = created_at or timezone.now()
    if timezone.is_naive(now):
        now = now.replace(tzinfo=datetime_timezone.utc)
    now = now.astimezone(datetime_timezone.utc)
    backup_id = f"{now:%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}"
    staging = root / TEMP_DIRECTORY / backup_id
    final = root / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}" / backup_id
    published = False
    try:
        staging.mkdir(parents=True)
        artifacts = []
        writer = dump_writer or _write_mysql_dump
        for alias in aliases:
            database = settings.DATABASES[alias]
            filename = f"grand-{alias}-{now:%Y%m%dT%H%M%SZ}.sql.gz"
            target = staging / filename
            writer(alias, database, target)
            byte_length, sha256 = _verify_artifact(target)
            artifacts.append(
                BackupArtifact(
                    database_alias=alias,
                    logical_name=str(database.get("NAME") or ""),
                    engine=str(database.get("ENGINE") or ""),
                    filename=filename,
                    byte_length=byte_length,
                    sha256=sha256,
                )
            )

        manifest = {
            "application": "GRAND",
            "application_version": _application_version(),
            "backup_id": backup_id,
            "created_at": now.isoformat(),
            "databases": [asdict(artifact) for artifact in artifacts],
            "deployment_revision": os.environ.get("RENDER_GIT_COMMIT", ""),
            "format": "GRAND database backup set",
            "format_version": 1,
            "restore_tested": False,
            "scope": "complete" if set(aliases) == {"default", "finance"} else "partial",
            "status": "completed",
        }
        _atomic_write(
            staging / "manifest.json",
            json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, final)
        published = True
        retention_warning = ""
        try:
            removed = _apply_retention(root, keep)
        except OSError as exc:
            # The verified set is already visible at this point. Do not describe a
            # cleanup problem as a failed backup or remove the new recovery point.
            removed = []
            retention_warning = f"Backup published, but retention cleanup failed: {exc}"
        return {
            "backup_id": backup_id,
            "path": final,
            "manifest": manifest,
            "removed_by_retention": removed,
            "retention_warning": retention_warning,
        }
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"Database backup set {backup_id} failed: {exc}") from exc
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)
        _release_lock(lock)
