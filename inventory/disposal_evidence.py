"""Private disposal source checks; a legacy file has no upload-time hash."""
import hashlib
from pathlib import Path

from django.core.exceptions import ValidationError
from .private_evidence import open_checked_private_file


def prepare_uploads(groups):
    from .forms import MAX_DISPOSAL_FILE_BYTES, _validate_disposal_upload
    mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                  ".webp": "image/webp", ".pdf": "application/pdf"}
    prepared = []
    # Validate the whole action before any file is saved, including later groups.
    for kind, uploads in groups:
        for upload in uploads:
            upload.seek(0)
            _validate_disposal_upload(upload)
            digest, size = hashlib.sha256(), 0
            for block in upload.chunks():
                size += len(block)
                if size > MAX_DISPOSAL_FILE_BYTES:
                    raise ValidationError("Each file must be 15 MB or smaller.")
                digest.update(block)
            upload.seek(0)
            if not size:
                raise ValidationError("Empty evidence files cannot be retained.")
            prepared.append((upload, kind, digest.hexdigest(), size,
                             mime_types[Path(upload.name).suffix.lower()]))
    return prepared


def open_checked_evidence(row, *, allow_legacy=False):
    if not row.sha256 and not allow_legacy:
        raise ValidationError("Legacy disposal evidence has unknown integrity; no upload-time hash was retained.")
    try:
        return open_checked_private_file(row.file,
            namespace=f"inventory/disposal/{row.disposal_case.asset_id}",
            sha256=row.sha256, size=row.size, allow_legacy=allow_legacy)
    except ValidationError as error:
        raise ValidationError("Disposal evidence failed its integrity check. Investigate or restore the retained file.") from error
    except (OSError, ValueError) as error:
        raise ValidationError("Disposal evidence is unavailable. Investigate or restore the retained file.") from error


def verify_case_evidence(case, *, allow_legacy=False):
    """Strict by default for future source consumers; legacy review stays explicit."""
    for row in case.attachments.all():
        with open_checked_evidence(row, allow_legacy=allow_legacy):
            pass
