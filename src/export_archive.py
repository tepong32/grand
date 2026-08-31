from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.text import slugify


ROOT_MARKER = "GRAND_EXPORT_ROOT.json"


def _segment(value, fallback):
    return (slugify(str(value or ""))[:80] or fallback).strip(".-_") or fallback


def _filename(value):
    source = Path(Path(str(value or "export.bin")).name)
    suffix = source.suffix.lower()
    suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ".bin"
    stem = _segment(source.stem, "export")
    return f"{stem}{suffix}"


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def archive_export(*, content, department, user, category, filename, metadata=None):
    """Atomically retain one downloaded export inside the single TraceSync-ready root."""
    if not isinstance(content, bytes):
        raise TypeError("Export archive content must be bytes.")
    root = Path(settings.GRAND_EXPORT_ROOT).expanduser().resolve()
    exported_at = timezone.now()
    digest = hashlib.sha256(content).hexdigest()
    department_segment = _segment(getattr(department, "slug", None) or getattr(department, "name", None), "department")
    user_segment = _segment(getattr(user, "username", None), f"user-{getattr(user, 'pk', 'unknown')}")
    category_segment = _segment(category, "exports")
    safe_filename = _filename(filename)
    artifact_name = f"{exported_at:%Y%m%dT%H%M%S%fZ}_{digest[:12]}_{safe_filename}"
    relative_dir = Path(department_segment) / user_segment / category_segment / f"{exported_at:%Y}" / f"{exported_at:%m}"
    artifact_path = (root / relative_dir / artifact_name).resolve()
    artifact_path.relative_to(root)

    marker_path = root / ROOT_MARKER
    if not marker_path.exists():
        marker = {
            "format": "GRAND portable export root",
            "version": 1,
            "copy_instruction": "Copy or synchronize this entire folder. Keep each artifact beside its .manifest.json file.",
            "layout": "department/user/category/year/month/artifact",
        }
        _atomic_write(marker_path, json.dumps(marker, indent=2, sort_keys=True).encode("utf-8") + b"\n")

    _atomic_write(artifact_path, content)
    manifest = {
        "format": "GRAND export manifest",
        "version": 1,
        "relative_path": artifact_path.relative_to(root).as_posix(),
        "sha256": digest,
        "byte_length": len(content),
        "exported_at": exported_at.isoformat(),
        "department": {
            "id": getattr(department, "pk", None),
            "slug": getattr(department, "slug", ""),
            "name": getattr(department, "name", ""),
        },
        "exported_by": {
            "id": getattr(user, "pk", None),
            "username": getattr(user, "username", ""),
        },
        "category": category_segment,
        "metadata": metadata or {},
    }
    manifest_content = json.dumps(
        manifest, cls=DjangoJSONEncoder, indent=2, sort_keys=True,
    ).encode("utf-8") + b"\n"
    manifest_path = artifact_path.with_name(artifact_path.name + ".manifest.json")
    _atomic_write(manifest_path, manifest_content)
    return {
        "path": artifact_path,
        "manifest_path": manifest_path,
        "sha256": digest,
        "relative_path": artifact_path.relative_to(root).as_posix(),
    }
