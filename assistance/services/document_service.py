from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from assistance.models import CitizenRequest, RequestDocument, RequestTimeline
from .file_validation import validate_uploaded_file


class DocumentServiceError(Exception):
    """Business rule violation for document operations."""

    pass


def _assert_request_allows_document_changes(request_obj: CitizenRequest):
    if not request_obj.is_active:
        raise DocumentServiceError("This request is no longer active.")
    if request_obj.is_locked:
        raise DocumentServiceError("This request is locked and cannot be changed.")


def _assert_document_is_mutable(doc: RequestDocument):
    if doc.status in {"approved", "pending"}:
        raise DocumentServiceError("This document is currently locked and cannot be replaced.")


def _delete_stored_file_if_needed(name: str | None) -> None:
    if not name:
        return
    try:
        default_storage.delete(name)
    except OSError:
        pass


class DocumentService:
    @classmethod
    def upload_or_replace(
        cls,
        *,
        request_obj: CitizenRequest,
        document_type: str,
        uploaded_file,
        created_by=None,
    ) -> RequestDocument:
        if document_type not in {k for k, _ in RequestDocument.DOCUMENT_TYPE_CHOICES}:
            raise DocumentServiceError("Invalid document type.")

        validate_uploaded_file(uploaded_file)
        _assert_request_allows_document_changes(request_obj)

        old_name = None
        with transaction.atomic():
            doc = (
                RequestDocument.objects.select_for_update()
                .filter(
                    request=request_obj,
                    document_type=document_type,
                    is_removed=False,
                )
                .first()
            )
            if doc:
                _assert_document_is_mutable(doc)
                old_name = doc.file.name if doc.file else None
                doc.file = uploaded_file
                doc.status = "pending"
                doc.remarks = doc.remarks or ""
                doc.replacement_count = (doc.replacement_count or 0) + 1
                doc.save(update_fields=["file", "status", "remarks", "replacement_count"])
                RequestTimeline.objects.create(
                    request=request_obj,
                    event_type="document_replaced" if old_name else "document_uploaded",
                    message=(
                        f"Supporting document ({document_type}) uploaded."
                        if not old_name
                        else f"Supporting document ({document_type}) replaced."
                    ),
                    created_by=created_by,
                )
            else:
                doc = RequestDocument.objects.create(
                    request=request_obj,
                    document_type=document_type,
                    file=uploaded_file,
                    status="pending",
                    remarks="",
                )
                RequestTimeline.objects.create(
                    request=request_obj,
                    event_type="document_uploaded",
                    message=f"Supporting document ({document_type}) uploaded.",
                    created_by=created_by,
                )

        if old_name:
            _delete_stored_file_if_needed(old_name)

        return doc

    @classmethod
    def soft_delete_document(
        cls,
        *,
        request_obj: CitizenRequest,
        document_id: int,
        created_by=None,
    ) -> RequestDocument:
        _assert_request_allows_document_changes(request_obj)

        with transaction.atomic():
            doc = (
                RequestDocument.objects.select_for_update()
                .filter(
                    id=document_id,
                    request=request_obj,
                    is_removed=False,
                )
                .first()
            )
            if not doc:
                raise DocumentServiceError("Document not found.")

            doc.is_removed = True
            doc.removed_at = timezone.now()
            doc.save(update_fields=["is_removed", "removed_at"])

            RequestTimeline.objects.create(
                request=request_obj,
                event_type="document_removed",
                message=f"Supporting document ({doc.document_type}) removed by requester.",
                created_by=created_by,
            )

        return doc
