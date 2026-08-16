from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .access import can_receive_packets, can_revoke_credentials, department_for_user
from .models import DailyEmployeeCredential, EmployeeCredentialEvent


class CredentialError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedCredential:
    credential: DailyEmployeeCredential
    token: str


def digest_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _day_expiry(valid_on):
    local_zone = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(valid_on + timedelta(days=1), time.min), local_zone)


def _may_manage(actor, employee):
    return actor == employee or can_revoke_credentials(actor, department_for_user(employee))


def issue_daily_credential(*, employee, actor=None, replace=False, replacement_reason="Daily code replaced"):
    actor = actor or employee
    if not can_receive_packets(employee):
        raise CredentialError("Daily codes require an active employee with a department assignment.")
    if not _may_manage(actor, employee):
        raise CredentialError("You are not allowed to issue or replace this employee's daily code.")

    valid_on = timezone.localdate()
    with transaction.atomic():
        existing = DailyEmployeeCredential.objects.select_for_update().filter(
            employee=employee,
            valid_on=valid_on,
            revoked_at__isnull=True,
        ).first()
        if existing and not replace:
            raise CredentialError("An active daily code already exists. Replace it to issue a new code.")
        if existing:
            existing.revoked_at = timezone.now()
            existing.revoked_by = actor
            existing.revocation_reason = replacement_reason.strip() or "Daily code replaced"
            existing.full_clean()
            existing.save(update_fields=("revoked_at", "revoked_by", "revocation_reason"))
            EmployeeCredentialEvent.objects.create(
                credential=existing,
                actor=actor,
                action="revoked_for_replacement",
                note=existing.revocation_reason,
            )

        issued = None
        for _attempt in range(5):
            token = secrets.token_urlsafe(32)
            credential = DailyEmployeeCredential(
                employee=employee,
                token_digest=digest_token(token),
                valid_on=valid_on,
                expires_at=_day_expiry(valid_on),
                issued_by=actor,
            )
            credential.full_clean()
            try:
                with transaction.atomic():
                    credential.save(force_insert=True)
                issued = IssuedCredential(credential=credential, token=token)
                break
            except IntegrityError:
                continue
        if issued is None:
            raise CredentialError("A unique daily code could not be issued. Try again.")

        EmployeeCredentialEvent.objects.create(
            credential=issued.credential,
            actor=actor,
            action="issued",
            metadata={"valid_on": valid_on.isoformat(), "expires_at": issued.credential.expires_at.isoformat()},
        )
        if existing:
            existing.replaced_by = issued.credential
            existing.full_clean()
            existing.save(update_fields=("replaced_by",))
    return issued


def revoke_daily_credential(*, credential, actor, reason):
    if not _may_manage(actor, credential.employee):
        raise CredentialError("You are not allowed to revoke this employee's daily code.")
    reason = reason.strip()
    if not reason:
        raise CredentialError("Explain why the daily code is being revoked.")
    if credential.revoked_at:
        return credential
    credential.revoked_at = timezone.now()
    credential.revoked_by = actor
    credential.revocation_reason = reason
    credential.full_clean()
    credential.save(update_fields=("revoked_at", "revoked_by", "revocation_reason"))
    EmployeeCredentialEvent.objects.create(credential=credential, actor=actor, action="revoked", note=reason)
    return credential


def resolve_daily_credential(token):
    credential = DailyEmployeeCredential.objects.select_related(
        "employee", "employee__employeeprofile", "employee__employeeprofile__assigned_department"
    ).filter(token_digest=digest_token(token)).first()
    if not credential or not credential.is_valid:
        raise CredentialError("This employee code is invalid, expired, replaced, or revoked.")
    return credential
