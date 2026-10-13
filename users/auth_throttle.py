"""Bound password guessing across Django, allauth and admin entry points."""
import logging
import unicodedata
from datetime import timedelta
from ipaddress import ip_address, ip_network

from django.db import DatabaseError
from django.contrib.auth import get_user_model
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.http import base36_to_int, urlsafe_base64_decode

from .models import AuthAttemptBucket

logger = logging.getLogger(__name__)

CURRENT_PASSWORD_ROUTES = {"password_change", "admin:password_change", "account_change_password", "account_reauthenticate"}


def consume_attempt(scope, value, *, limit, window=300):
    now = timezone.now()
    digest = salted_hmac("grand-auth-attempts", f"{scope}:{value}", algorithm="sha256").hexdigest()
    AuthAttemptBucket.objects.get_or_create(digest=digest, defaults={"expires_at": now + timedelta(seconds=window)})
    # Conditional updates are atomic on both SQLite and MySQL; no cache-local
    # read/modify/write or conditional unique constraint is involved.
    AuthAttemptBucket.objects.filter(digest=digest, expires_at__lte=now).update(attempts=0, expires_at=now + timedelta(seconds=window))
    return bool(AuthAttemptBucket.objects.filter(digest=digest, attempts__lt=limit).update(attempts=F("attempts") + 1))


def network_identity(request):
    # Forwarded client headers are deliberately untrusted. The edge must
    # strip/validate them before any future proxy-specific identity adapter.
    try:
        address = ip_address(request.META.get("REMOTE_ADDR", ""))
        if address.version == 6:
            return str(ip_network(f"{address}/64", strict=False))
        return str(address)
    except ValueError:
        return "unknown"


def attempt_identities(route, post, kwargs, user=None):
    """Use the actual form field, then bind aliases to the persisted account.

    Database matching deliberately uses the authentication store's collation:
    case/accent aliases that authenticate as one user must share its counter.
    Ambiguous email/username matches consume every candidate's counter.
    """
    if route in CURRENT_PASSWORD_ROUTES:
        return [f"account:{user.pk}"] if user and user.is_authenticated else []
    if route in {"password_reset_confirm", "account_reset_password_from_key"}:
        raw = kwargs.get("uidb64", "") if route == "password_reset_confirm" else kwargs.get("uidb36", "")
        try:
            uid = int(urlsafe_base64_decode(raw)) if route == "password_reset_confirm" else base36_to_int(raw)
            if not 0 < uid < 2**63:
                raise ValueError
        except (ValueError, OverflowError, UnicodeError):
            return [f"invalid-uid:{raw}"]
        return [f"account:{uid}"]
    field = "login" if route == "account_login" else "username" if route in {"login", "admin:login"} else "email"
    raw = post.get(field, "").strip()
    if not raw:
        return []
    normalized = unicodedata.normalize("NFKC", raw).casefold()
    users = get_user_model().objects
    ids = set()
    for value in {raw, normalized}:
        if field in {"username", "login"}:
            ids.update(users.filter(username__iexact=value).values_list("pk", flat=True))
        if field in {"email", "login"}:
            from allauth.account.models import EmailAddress

            ids.update(users.filter(email__iexact=value).values_list("pk", flat=True))
            ids.update(EmailAddress.objects.filter(email__iexact=value).values_list("user_id", flat=True))
    return [f"account:{uid}" for uid in sorted(ids)] if ids else [f"submitted:{normalized}"]


class AuthAttemptMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Old social signups could have both identities. Quarantine rather than
        # silently deleting HR, leave or historical evidence on an existing user.
        user = request.user
        if user.is_authenticated and getattr(user, "employeeprofile", None) and getattr(user, "citizenprofile", None) and request.resolver_match.view_name not in {"logout", "account_logout"}:
            response = HttpResponse("Your account needs an identity review. Please contact your administrator.", status=403)
            response["Cache-Control"] = "no-store"
            return response
        if request.method != "POST":
            return None
        route = request.resolver_match.view_name
        if route in {"login", "account_login", "admin:login"} | CURRENT_PASSWORD_ROUTES:
            family, ip_limit, key_limit = "login", 30, 10
        elif route in {"password_reset", "password_reset_confirm", "account_reset_password", "account_reset_password_from_key"}:
            family, ip_limit, key_limit = "reset", 10, 5
        elif route in {"register", "account_signup", "socialaccount_signup"}:
            family, ip_limit, key_limit = "signup", 10, 5
        else:
            return None
        try:
            allowed = consume_attempt(f"{family}:network", network_identity(request), limit=ip_limit)
            if allowed:
                for identity in attempt_identities(route, request.POST, view_kwargs, user):
                    if not consume_attempt(f"{family}:identity", identity, limit=key_limit):
                        allowed = False
                        break
        except DatabaseError:
            logger.error("Authentication attempt storage unavailable")
            response = HttpResponse("Sign-in is temporarily unavailable. Please try again later.", status=503)
        else:
            if allowed:
                return None
            response = HttpResponse("Too many attempts. Please wait five minutes and try again.", status=429)
            response["Retry-After"] = "300"
        response["Cache-Control"] = "no-store"
        return response
