from django.db.models import Count, Max, Q
from django.utils import timezone

from assistance.models import CitizenProfile


def normalize_email(value):
    return (value or "").strip().casefold()


def normalize_phone(value):
    return "".join(character for character in (value or "") if character.isdigit())


class CitizenProfileService:
    @staticmethod
    def get_or_create_citizen(*, full_name: str, email: str, phone: str):
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        candidates = list(
            CitizenProfile.objects.filter(
                Q(normalized_email=normalized_email) | Q(normalized_phone=normalized_phone)
            ).order_by("pk")
        )

        exact = [
            profile
            for profile in candidates
            if profile.normalized_email == normalized_email
            and profile.normalized_phone == normalized_phone
        ]
        if exact:
            return exact[0]

        if len(candidates) == 1:
            # A single stable identifier may reconnect a resident to an existing
            # record. Conflicting identifiers are never merged automatically.
            return candidates[0]

        return CitizenProfile.objects.create(
            full_name=full_name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            total_requests=0,
            last_request_at=timezone.now(),
        )

    @staticmethod
    def increment_request_count(profile: CitizenProfile) -> CitizenProfile:
        summary = profile.requests.aggregate(total=Count("pk"), latest=Max("submitted_at"))
        profile.total_requests = summary["total"] or 0
        profile.last_request_at = summary["latest"]
        profile.save(update_fields=["total_requests", "last_request_at", "updated_at"])
        return profile


class CitizenReviewQueryService:
    SORTS = {
        "recent": ("-last_request_at", "-pk"),
        "requests": ("-request_total", "full_name", "pk"),
        "name": ("full_name", "pk"),
        "review": ("review_status", "-last_request_at", "pk"),
    }

    @classmethod
    def profiles(cls, *, search="", review_status="", sort="recent", allow_pii=False):
        queryset = CitizenProfile.objects.select_related("assigned_reviewer", "reviewed_by").annotate(
            request_total=Count("requests", distinct=True),
            active_request_total=Count("requests", filter=Q(requests__is_active=True), distinct=True),
            awaiting_action_total=Count(
                "requests",
                filter=Q(requests__is_active=True, requests__status__in=("submitted", "pending")),
                distinct=True,
            ),
            latest_request_at=Max("requests__submitted_at"),
        )
        if review_status:
            queryset = queryset.filter(review_status=review_status)
        if search and allow_pii:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        ordering = cls.SORTS.get(sort, cls.SORTS["recent"])
        if not allow_pii:
            masked_sorts = {
                "recent": ("-last_request_at", "-pk"),
                "requests": ("-request_total", "pk"),
                "review": ("review_status", "-last_request_at", "pk"),
            }
            ordering = masked_sorts.get(sort, masked_sorts["recent"])
        return queryset.order_by(*ordering)

    @staticmethod
    def duplicate_profile_ids():
        duplicate_ids = set()
        for field in ("normalized_email", "normalized_phone"):
            repeated = (
                CitizenProfile.objects.exclude(**{field: ""})
                .values(field)
                .annotate(total=Count("pk"))
                .filter(total__gt=1)
                .values_list(field, flat=True)
            )
            duplicate_ids.update(
                CitizenProfile.objects.filter(**{f"{field}__in": repeated}).values_list("pk", flat=True)
            )
        return duplicate_ids

    @staticmethod
    def mask(profile):
        words = [word for word in profile.full_name.split() if word]
        profile.display_name = " ".join(f"{word[0]}***" for word in words) or f"Citizen #{profile.pk}"
        local, separator, domain = profile.email.partition("@")
        profile.display_email = f"{local[:1]}***@{domain}" if separator else "Hidden"
        digits = normalize_phone(profile.phone)
        profile.display_phone = f"***-***-{digits[-4:]}" if len(digits) >= 4 else "Hidden"
        return profile
