import logging

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from assistance.models import CitizenRequest, RequestDocument, RequestTimeline
from .access_service import locked_request_for_mutation
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
    except Exception:
        # Cleanup must not turn an already committed replacement into a failure
        # or cause the new current file to be removed by rollback compensation.
        logging.getLogger(__name__).error("Attachment cleanup failed; storage recovery review required.")


class DocumentService:
    @classmethod
    def upload_or_replace(
        cls,
        *,
        request_obj: CitizenRequest,
        document_type: str,
        uploaded_file,
        created_by=None,
        access_token=None,
    ) -> RequestDocument:
        if document_type not in {k for k, _ in RequestDocument.DOCUMENT_TYPE_CHOICES}:
            raise DocumentServiceError("Invalid document type.")

        validate_uploaded_file(uploaded_file)
        doc, old_name = None, None
        try:
            with locked_request_for_mutation(request_obj=request_obj, token=access_token) as request_obj:
                _assert_request_allows_document_changes(request_obj)
                doc = RequestDocument.objects.select_for_update().filter(
                    request=request_obj, document_type=document_type).first()
                if doc:
                    old_name = doc.file.name if doc.file else None
                    was_removed = doc.is_removed
                    if not was_removed:
                        _assert_document_is_mutable(doc)
                    doc.file = uploaded_file
                    doc.status = "pending"
                    doc.remarks = doc.remarks or ""
                    doc.is_removed = False
                    doc.removed_at = None
                    doc.replacement_count = (doc.replacement_count or 0) + 1
                    doc.save(update_fields=["file", "status", "remarks", "replacement_count",
                                            "is_removed", "removed_at"])
                    event_type = "document_uploaded" if was_removed else "document_replaced"
                    message = f"Supporting document ({document_type}) {'uploaded again after removal' if was_removed else 'replaced'}."
                else:
                    # Keep the object available for compensating storage cleanup
                    # if the database insert or timeline write fails after save().
                    doc = RequestDocument(request=request_obj, document_type=document_type,
                                          file=uploaded_file, status="pending", remarks="")
                    doc.save()
                    event_type = "document_uploaded"
                    message = f"Supporting document ({document_type}) uploaded."
                RequestTimeline.objects.create(request=request_obj, event_type=event_type,
                                               message=message, created_by=created_by)
                if old_name:
                    transaction.on_commit(lambda: _delete_stored_file_if_needed(old_name))
        except Exception:
            # Authorization/eligibility failures occur before assigning a new
            # file. Later failures roll back rows and remove only the new stored
            # object, never the retained original. No immutable baseline is made.
            if (doc is not None and doc.file and doc.file._committed
                    and doc.file.name != old_name):
                _delete_stored_file_if_needed(doc.file.name)
            raise

        return doc

    @classmethod
    def soft_delete_document(
        cls,
        *,
        request_obj: CitizenRequest,
        document_id: int,
        created_by=None,
        access_token=None,
    ) -> RequestDocument:
        with locked_request_for_mutation(request_obj=request_obj, token=access_token) as request_obj:
            _assert_request_allows_document_changes(request_obj)
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
