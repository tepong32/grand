"""Current, replaceable Assistance attachments; no retained hash baseline exists."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404

from src.file_integrity import validate_file_namespace


def document_response(document):
    try:
        validate_file_namespace(document.file, namespace="assistance_docs")
        source = document.file.open("rb")
    except (OSError, ValueError, RuntimeError, ValidationError):
        raise Http404("Attachment unavailable.") from None
    # Preserve image/PDF previews without serving arbitrary upload declarations
    # as executable HTML/SVG on this origin. Inline content is also sandboxed.
    try:
        prefix = source.read(16)
        source.seek(0)
        content_type = "application/octet-stream"
        suffix = Path(document.file.name).suffix.lower()
        if suffix == ".pdf" and prefix.startswith(b"%PDF-"):
            content_type = "application/pdf"
        elif suffix in {".jpg", ".jpeg", ".png", ".gif"}:
            from PIL import Image, UnidentifiedImageError
            try:
                image = Image.open(source)
                image.verify()
                allowed = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}
                content_type = allowed.get(image.format, content_type)
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                pass
            finally:
                source.seek(0)
        response = FileResponse(source, as_attachment=content_type == "application/octet-stream",
                                filename=Path(document.file.name).name, content_type=content_type)
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response["X-GRAND-File-Integrity"] = "not-recorded"
        return response
    except OSError:
        source.close()
        raise Http404("Attachment unavailable.") from None
    except Exception:
        source.close()
        raise
