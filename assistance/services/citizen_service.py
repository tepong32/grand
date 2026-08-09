from django.utils import timezone

from assistance.models import CitizenProfile


class CitizenProfileService:
    @staticmethod
    def get_or_create_citizen(*, full_name: str, email: str, phone: str):
        profile = (
            CitizenProfile.objects.filter(phone=phone).first()
            or CitizenProfile.objects.filter(email=email).first()
        )

        if profile:
            updated = False
            if profile.full_name != full_name:
                profile.full_name = full_name
                updated = True
            if profile.email != email:
                profile.email = email
                updated = True
            if profile.phone != phone:
                profile.phone = phone
                updated = True
            if updated:
                profile.last_request_at = timezone.now()
                profile.save(update_fields=["full_name", "email", "phone", "last_request_at", "updated_at"])
            return profile

        return CitizenProfile.objects.create(
            full_name=full_name,
            email=email,
            phone=phone,
            total_requests=0,
            last_request_at=timezone.now(),
        )

    @staticmethod
    def increment_request_count(profile: CitizenProfile) -> CitizenProfile:
        profile.total_requests = (profile.total_requests or 0) + 1
        profile.last_request_at = timezone.now()
        profile.save(update_fields=["total_requests", "last_request_at", "updated_at"])
        return profile