"""Account-free access. A short legacy code is never an access credential."""
from dataclasses import dataclass
from contextlib import contextmanager

from django.conf import settings
from django.core import signing
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import F
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


def _private_payload(token):
    try:
        if not isinstance(token, str) or len(token) > 512:
            raise ValueError
        payload = signing.loads(token, salt=LINK_SALT, max_age=private_link_lifetime())
        if (not isinstance(payload, dict) or set(payload) != {"id", "revision"}
                or type(payload["id"]) is not int or not isinstance(payload["revision"], str)):
            raise ValueError
        return payload
    except (signing.BadSignature, ValueError, TypeError):
        raise Http404("Private link unavailable. Request a new link using your registered email.") from None


def resolve_request_for_edit(token):
    payload = _private_payload(token)
    obj = get_object_or_404(CitizenRequest.objects.select_related("assistance_type"),
                            pk=payload["id"], is_active=True)
    if not constant_time_compare(payload["revision"], _revision(obj)):
        raise Http404("Private link unavailable.")
    return obj


@contextmanager
def locked_request_for_mutation(*, token=None, request_obj=None):
    """Serialize default-store mutations before reading authoritative eligibility.

    The identity update changes no value. InnoDB holds its row write lock until
    commit; SQLite reserves its writer before the following read (FOR UPDATE
    alone is ineffective there). Ordinary staff/admin UPDATEs take the same
    database write lock. Do not retry an expired/contended operation implicitly.
    Internal document callers may supply a credential-state snapshot instead of
    a web token; neither path trusts its stale activation/workflow fields.
    """
    payload = _private_payload(token) if token is not None else None
    pk = payload["id"] if payload else request_obj.pk
    if request_obj is not None and request_obj.pk != pk:
        raise Http404("Private link unavailable.")
    expected_revision = payload["revision"] if payload else _revision(request_obj)
    with transaction.atomic(using=DEFAULT_DB_ALIAS):
        rows = CitizenRequest.objects.using(DEFAULT_DB_ALIAS)
        if not rows.filter(pk=pk).update(is_active=F("is_active")):
            raise Http404("Private link unavailable.")
        # A locking read is current even under a caller's MySQL repeatable-read
        # transaction. Recheck token age after any wait for the owning row.
        obj = get_object_or_404(rows.select_for_update(), pk=pk, is_active=True)
        if token is not None:
            expected_revision = _private_payload(token)["revision"]
        if not constant_time_compare(expected_revision, _revision(obj)):
            raise Http404("Private link unavailable.")
        yield obj


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
