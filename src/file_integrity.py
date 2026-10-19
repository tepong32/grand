"""Check retained filesystem bytes and return the same open streaming handle."""
import hashlib
from pathlib import Path, PureWindowsPath

from django.core.exceptions import ValidationError


def validate_file_namespace(field_file, *, namespace):
    """Path containment only; this does not establish any integrity baseline."""
    try:
        name = field_file.name or ""
        relative = Path(name)
        root = Path(field_file.storage.location).resolve()
        path = root / relative
        if (not name or relative.is_absolute() or PureWindowsPath(name).is_absolute()
                or "\\" in name or ".." in relative.parts
                or path.resolve() != path):
            raise ValueError("Unsafe private evidence path.")
        path.relative_to(root / namespace)
    except RuntimeError as error:
        raise ValidationError("Unsafe private evidence path.") from error


def open_checked_private_file(field_file, *, namespace, sha256, size=None, allow_legacy=False):
    """Use only retained metadata; hash-only sources and sized legacy files stay explicit."""
    source = None
    try:
        validate_file_namespace(field_file, namespace=namespace)
        if not sha256 and (not allow_legacy or size is None):
            raise ValidationError("Retained evidence has no integrity baseline.")
        source = field_file.open("rb")
        digest, actual_size = hashlib.sha256(), 0
        for block in source.chunks():
            digest.update(block)
            actual_size += len(block)
        if (sha256 and digest.hexdigest() != sha256) or (size is not None and actual_size != size):
            raise ValidationError("Retained evidence failed its integrity check.")
        source.seek(0)
        return source
    except Exception as error:
        if source is not None:
            source.close()
        if isinstance(error, RuntimeError):  # Path.resolve() refuses symlink loops.
            raise ValidationError("Unsafe private evidence path.") from error
        raise
