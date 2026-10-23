"""Checked private evidence downloads; return the verified open file."""
from django.core.exceptions import ValidationError

from src.file_integrity import open_checked_private_file


def open_checked_private_evidence(row, *, namespace):
    """Strict row contract: retained hash and size are both required."""
    if row.size is None:
        raise ValidationError("Retained evidence has no size baseline.")
    return open_checked_private_file(row.file, namespace=namespace, sha256=row.sha256, size=row.size)
