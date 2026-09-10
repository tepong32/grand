"""Portable statement files and printable notes from retained reviewed evidence."""
import hashlib
import io
import json
import zipfile

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import FinanceStatementNoteSet
from .services import report_run_integrity_errors
from .statement_services import note_set_snapshot, snapshot_checksum, validate_note_set


@transaction.atomic
def statement_bundle(note_set):
    note_set = FinanceStatementNoteSet.objects.select_for_update().get(pk=note_set.pk)
    if not note_set.is_complete_statement_package:
        raise ValidationError("A complete download requires all four statements. Historical note exports remain available.")
    if note_set.status not in (FinanceStatementNoteSet.REVIEWED, FinanceStatementNoteSet.APPROVED, FinanceStatementNoteSet.SUPERSEDED):
        raise ValidationError("Submit the notes for independent review before downloading the statement package.")
    if snapshot_checksum(note_set_snapshot(note_set)) != note_set.snapshot_checksum:
        raise ValidationError("The reviewed notes no longer match their retained checksum.")
    if not note_set.reviewed_by_id or not note_set.reviewed_at:
        raise ValidationError("The statement package lacks its retained independent review.")
    if any(note_set.source_snapshot.get(field, {}).get("public_id") != str(run.public_id)
            for field, run in note_set.statement_runs):
        raise ValidationError("The selected statement identities differ from the reviewed package.")
    if note_set.bundle_file or note_set.bundle_checksum:
        if not note_set.bundle_file or not note_set.bundle_checksum:
            raise ValidationError("The issued statement bundle has incomplete retained evidence.")
        try:
            with note_set.bundle_file.open("rb") as output:
                content = output.read()
        except (OSError, ValueError):
            raise ValidationError("The issued statement bundle file cannot be read.")
        if hashlib.sha256(content).hexdigest() != note_set.bundle_checksum:
            raise ValidationError("The issued statement bundle no longer matches its SHA-256 checksum.")
        return content
    validation = validate_note_set(note_set)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    files = {}
    for field, run in note_set.statement_runs:
        errors = report_run_integrity_errors(run)
        if errors:
            raise ValidationError([f"{field}: {error}" for error in errors])
        with run.output_file.open("rb") as output:
            content = output.read()
        if hashlib.sha256(content).hexdigest() != run.checksum:
            raise ValidationError("A statement file changed while preparing the download.")
        files[f"statements/{field.removesuffix('_run')}.{run.output_format}"] = content
    files["notes.html"] = render_to_string("reporting/statement_notes_print.html", {"note_set": note_set}).encode("utf-8")
    manifest = {"format": "GRAND four-statement package", "version": 1,
        "notes": note_set_snapshot(note_set), "notes_sha256": note_set.snapshot_checksum,
        "status": note_set.status, "reviewed_by": note_set.reviewed_by.username,
        "reviewed_at": note_set.reviewed_at,
        "files": [{"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            for name, content in files.items()]}
    files["manifest.json"] = json.dumps(manifest, cls=DjangoJSONEncoder, sort_keys=True, indent=2).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            # Stable metadata makes repeated downloads reproducible.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    content = buffer.getvalue()
    note_set.bundle_file.save(f"statements-{note_set.public_id}.zip", ContentFile(content), save=False)
    note_set.bundle_checksum = hashlib.sha256(content).hexdigest()
    note_set.bundled_at = timezone.now()
    note_set.save(update_fields=("bundle_file", "bundle_checksum", "bundled_at"))
    return content
