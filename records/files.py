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


def open_associated_file(association):
    """Retain native Records authority and use only actual source baselines."""
    from assistance.models import RequestDocument
    from reporting.models import ReportRun
    from vouchers.models import VoucherOutput
    from .services import association_file, association_is_owned

    if not association_is_owned(association):
        raise ValidationError("The linked source is unavailable in this department.")
    field, filename = association_file(association)
    source = association.content_object
    if not field:
        raise ValidationError("The linked source has no available file.")
    if isinstance(source, ReportRun):
        parts = PurePosixPath(field.name or "").parts
        if len(parts) != 5 or parts[:2] != ("reporting", "outputs"):
            raise ValidationError("The retained output path is invalid.")
        if association.role == "official_source":
            filings = [event for event in association.record.events.filter(action="filed_official_report")
                       if isinstance(event.metadata, dict)
                       and event.metadata.get("report_run") == str(source.public_id)]
            if len(filings) != 1 or filings[0].metadata.get("output_checksum") != source.checksum:
                raise ValidationError("The filed output no longer matches its retained source.")
        namespace = "/".join(parts[:4])
    elif isinstance(source, VoucherOutput):
        namespace = (f"vouchers/outputs/{source.case.reference_code}/"
                     f"{source.output_type}/v{source.version}")
    elif isinstance(source, RequestDocument):
        # This source has no retained hash/size fields. It deliberately references
        # the current replaceable attachment, not an immutable filed copy.
        from assistance.files import validate_document_file
        validate_document_file(field)
        return field.open("rb"), filename, None
    else:
        raise ValidationError("This linked source has no supported download.")
    return (open_checked_private_file(field, namespace=namespace, sha256=source.checksum),
            filename, source.checksum)
