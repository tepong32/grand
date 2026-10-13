"""Bound password guessing across Django, allauth and admin entry points."""
import logging
from datetime import timedelta
from ipaddress import ip_address, ip_network

from django.db import DatabaseError
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import AuthAttemptBucket

logger = logging.getLogger(__name__)


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
        if route in {"login", "account_login", "admin:login"}:
            family, ip_limit, key_limit = "login", 30, 10
            key = request.POST.get("login") or request.POST.get("username") or request.POST.get("email")
        elif route in {"password_reset", "password_reset_confirm", "account_reset_password", "account_reset_password_from_key"}:
            family, ip_limit, key_limit = "reset", 10, 5
            key = request.POST.get("email") or view_kwargs.get("uidb36") or view_kwargs.get("uidb64")
        elif route in {"register", "account_signup", "socialaccount_signup"}:
            family, ip_limit, key_limit = "signup", 10, 5
            key = request.POST.get("email")
        else:
            return None
        try:
            allowed = consume_attempt(f"{family}:network", network_identity(request), limit=ip_limit)
            if allowed and key:
                allowed = consume_attempt(f"{family}:identity", key.strip().casefold(), limit=key_limit)
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
