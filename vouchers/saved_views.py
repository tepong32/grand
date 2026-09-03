from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from .case_exports import ATTENTION_CHOICES
from .models import VoucherCase, VoucherCaseSavedView, VoucherPrintJob
from .roles import ROLE_PROFILES


MAX_PRIVATE_CASE_VIEWS = 25
FILTER_KEYS = (
    "stage", "transaction_type", "requesting_department", "attention", "custody", "q", "office",
)


def normalize_saved_case_filters(values, *, allow_office=False):
    filters = {
        key: " ".join(str(values.get(key, "") or "").split())
        for key in FILTER_KEYS
    }
    filters["q"] = filters["q"][:160]
    filters["transaction_type"] = filters["transaction_type"][:80]

    if filters["stage"] and filters["stage"] not in dict(VoucherCase.STAGE_CHOICES):
        raise ValidationError("Choose a valid voucher stage before saving this view.")
    if filters["attention"] and filters["attention"] not in dict(ATTENTION_CHOICES):
        raise ValidationError("Choose a valid attention group before saving this view.")
    valid_custody = {"needs_signing_copy", *dict(VoucherPrintJob.STATUS_CHOICES)}
    valid_custody.discard(VoucherPrintJob.SUPERSEDED)
    if filters["custody"] and filters["custody"] not in valid_custody:
        raise ValidationError("Choose a valid custody state before saving this view.")
    if filters["requesting_department"] and not filters["requesting_department"].isdigit():
        raise ValidationError("Choose a valid requesting office before saving this view.")
    if not allow_office:
        filters["office"] = ""
    elif filters["office"] and filters["office"] not in ROLE_PROFILES:
        raise ValidationError("Choose a valid UAT office preview before saving this view.")
    return {key: value for key, value in filters.items() if value}


@transaction.atomic
def save_private_case_view(*, owner, name, filters, allow_office=False):
    display_name = " ".join((name or "").split())[:80]
    if not display_name:
        raise ValidationError("Enter a short name for this private view.")
    name_key = display_name.casefold()[:80]
    current = VoucherCaseSavedView.objects.select_for_update().filter(
        owner=owner, name_key=name_key,
    ).first()
    if current is None and VoucherCaseSavedView.objects.filter(owner=owner).count() >= MAX_PRIVATE_CASE_VIEWS:
        raise ValidationError(
            f"You can keep up to {MAX_PRIVATE_CASE_VIEWS} private case views. Remove one before saving another."
        )
    saved_view = current or VoucherCaseSavedView(owner=owner)
    saved_view.name = display_name
    saved_view.name_key = name_key
    saved_view.filters = normalize_saved_case_filters(filters, allow_office=allow_office)
    saved_view.full_clean()
    saved_view.save()
    return saved_view, current is None
