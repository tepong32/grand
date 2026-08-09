import os

from django.conf import settings
from django.core.exceptions import ValidationError


DEFAULT_ALLOWED_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".rtf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".xls",
    ".xlsx",
    ".csv",
    ".ppt",
    ".pptx",
)
DEFAULT_MAX_FILE_SIZE_MB = 5


def get_allowed_extensions():
    return tuple(
        ext.lower()
        for ext in getattr(
            settings,
            "TRACEPOINT_UPLOAD_ALLOWED_EXTENSIONS",
            DEFAULT_ALLOWED_EXTENSIONS,
        )
    )


def get_max_file_size_mb():
    try:
        return int(getattr(settings, "TRACEPOINT_UPLOAD_MAX_SIZE_MB", DEFAULT_MAX_FILE_SIZE_MB))
    except (TypeError, ValueError):
        return DEFAULT_MAX_FILE_SIZE_MB


def validate_uploaded_file(uploaded_file) -> None:
    if not uploaded_file:
        raise ValidationError("No file was uploaded.")

    name = getattr(uploaded_file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in get_allowed_extensions():
        raise ValidationError(f"Unsupported file type: {ext or 'unknown'}")

    size = getattr(uploaded_file, "size", None)
    if size is None:
        raise ValidationError("Uploaded file is invalid.")
    if size > get_max_file_size_mb() * 1024 * 1024:
        raise ValidationError(f"File size exceeds {get_max_file_size_mb()}MB.")

    allowed_types = set(
        getattr(
            settings,
            "TRACEPOINT_UPLOAD_ALLOWED_CONTENT_TYPES",
            [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-powerpoint",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "text/plain",
                "text/rtf",
                "image/jpeg",
                "image/png",
                "image/gif",
            ],
        )
    )
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type and content_type not in allowed_types and ext not in (".txt", ".rtf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"):
        raise ValidationError("Unsupported file content type.")
