"""Checked private evidence downloads; return the verified open file."""
import hashlib
from pathlib import Path, PureWindowsPath

from django.core.exceptions import ValidationError


def open_checked_private_evidence(row, *, namespace):
    source = None
    try:
        name = row.file.name or ""
        relative = Path(name)
        root = Path(row.file.storage.location).resolve()
        path = root / relative
        if (not name or relative.is_absolute() or PureWindowsPath(name).is_absolute()
                or "\\" in name or ".." in relative.parts
                or path.resolve() != path):
            raise ValueError("Unsafe private evidence path.")
        path.relative_to(root / namespace)
        if not row.sha256:
            raise ValidationError("Retained evidence has no integrity baseline.")
        source = row.file.open("rb")
        digest, size = hashlib.sha256(), 0
        for block in source.chunks():
            digest.update(block)
            size += len(block)
        if digest.hexdigest() != row.sha256 or size != row.size:
            raise ValidationError("Retained evidence failed its integrity check.")
        source.seek(0)
        return source
    except Exception as error:
        if source is not None:
            source.close()
        if isinstance(error, RuntimeError):  # Path.resolve() refuses symlink loops.
            raise ValidationError("Unsafe private evidence path.") from error
        raise
