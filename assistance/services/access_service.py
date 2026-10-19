"""Account-free access. A short legacy code is never an access credential."""
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.crypto import constant_time_compare, salted_hmac

from assistance.models import CitizenRequest

LINK_SALT = "assistance.private-access.v1"


def private_link_lifetime():
    return int(getattr(settings, "ASSISTANCE_PRIVATE_LINK_SECONDS", 7 * 24 * 60 * 60))


def _revision(request_obj):
    # Never expose the low-entropy legacy code in a decodable signed payload.
    return salted_hmac(
        LINK_SALT + ".revision",
        f"{request_obj.pk}:{request_obj.reference_code}:{request_obj.edit_code}:{request_obj.email}",
        algorithm="sha256",
    ).hexdigest()


def make_private_token(request_obj):
    return signing.dumps({"id": request_obj.pk, "revision": _revision(request_obj)}, salt=LINK_SALT)


def resolve_request_for_edit(token):
    try:
        if not isinstance(token, str) or len(token) > 512:
            raise ValueError
        payload = signing.loads(token, salt=LINK_SALT, max_age=private_link_lifetime())
        if (not isinstance(payload, dict) or set(payload) != {"id", "revision"}
                or type(payload["id"]) is not int or not isinstance(payload["revision"], str)):
            raise ValueError
        obj = CitizenRequest.objects.select_related("assistance_type").get(pk=payload["id"], is_active=True)
        if not constant_time_compare(payload["revision"], _revision(obj)):
            raise ValueError
        return obj
    except (signing.BadSignature, ValueError, TypeError, CitizenRequest.DoesNotExist):
        raise Http404("Private link unavailable. Request a new link using your registered email.") from None


def normalize_code(value):
    return (value or "").strip().upper()


@dataclass(frozen=True)
class RequestCodeLookup:
    reference_code: str
    edit_code: str | None = None


def validate_reference_code_match(reference_code, edit_code=None):
    return RequestCodeLookup(normalize_code(reference_code), None)


def resolve_request_for_reference(reference_code):
    return get_object_or_404(CitizenRequest.objects.select_related("assistance_type"),
                            reference_code=normalize_code(reference_code), is_active=True)


def request_codes_match(reference_code, edit_code=None):
    # Compatibility only: the retired PIN cannot authenticate or be tested.
    return (CitizenRequest.objects.filter(reference_code=normalize_code(reference_code), is_active=True).exists(), False)
