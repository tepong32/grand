from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from assistance.models import CitizenRequest, RequestTimeline
from assistance.services.citizen_service import CitizenProfileService


@dataclass(frozen=True)
class RequestLinks:
    track_link: str
    edit_link: str


class AssistanceRequestService:
    @staticmethod
    def get_status_guarded(request_obj: CitizenRequest):
        is_locked = request_obj.is_locked
        return {
            "locked": is_locked,
            "editable": not is_locked,
        }

    @staticmethod
    def duplicate_exists(*, assistance_type, email, period, semester):
        query = CitizenRequest.objects.filter(
            assistance_type=assistance_type,
            email=email,
            period=period,
            is_active=True,
        )
        if semester:
            query = query.filter(semester=semester)
        else:
            query = query.filter(semester__isnull=True)
        return query.exists()

    @classmethod
    @transaction.atomic
    def submit_request(cls, *, assistance_type, period, semester, full_name, email, phone):
        citizen = CitizenProfileService.get_or_create_citizen(
            full_name=full_name,
            email=email,
            phone=phone,
        )

        request_obj = CitizenRequest.objects.create(
            assistance_type=assistance_type,
            period=period,
            semester=semester,
            full_name=full_name,
            email=email,
            phone=phone,
            status="submitted",
            citizen=citizen,
            remarks="",
        )
        RequestTimeline.objects.create(
            request=request_obj,
            event_type="request_submitted",
            message="Assistance request submitted.",
            created_by=None,
        )

        CitizenProfileService.increment_request_count(citizen)
        return request_obj

    @staticmethod
    def build_links(request_obj: CitizenRequest, request):
        return RequestLinks(
            track_link=request.build_absolute_uri(request_obj.get_track_url()),
            edit_link=request.build_absolute_uri(request_obj.get_edit_url()),
        )

    @classmethod
    def transition_status(cls, request_obj: CitizenRequest, *, status: str, remarks: str | None = None):
        if status == request_obj.status:
            if remarks is not None and remarks != (request_obj.remarks or ""):
                request_obj.remarks = remarks
                request_obj.save(update_fields=["remarks"])
            return request_obj

        request_obj.status = status
        if remarks is not None:
            request_obj.remarks = remarks
        if status == "approved" and not request_obj.approved_at:
            request_obj.approved_at = timezone.now()
        request_obj.save(update_fields=["status", "remarks", "approved_at"])
        RequestTimeline.objects.create(
            request=request_obj,
            event_type="status_change",
            message=f"Status changed to {request_obj.get_status_display()}",
            created_by=None,
        )
        return request_obj
