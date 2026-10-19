"""Integrity checks for separate files uploaded to the native Records registry."""
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError

from src.file_integrity import open_checked_private_file


def open_record_file(item):
    # The UUID binds bytes to this record. Keep the original office-folder name:
    # a later department slug rename must not invalidate an otherwise valid file.
    parts = PurePosixPath(item.file.name or "").parts
    if (len(parts) != 4 or parts[0] != "records"
            or parts[2] != str(item.record.public_id) or item.size_bytes is None):
        raise ValidationError("The retained record file has an invalid baseline.")
    return open_checked_private_file(
        item.file, namespace="/".join(parts[:3]),
        sha256=item.checksum, size=item.size_bytes,
    )
