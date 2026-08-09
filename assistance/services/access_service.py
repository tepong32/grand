from dataclasses import dataclass

from django.shortcuts import get_object_or_404

from assistance.models import CitizenRequest


def normalize_code(value):
    return (value or "").strip().upper()


@dataclass(frozen=True)
class RequestCodeLookup:
    reference_code: str
    edit_code: str | None = None


def validate_reference_code_match(reference_code, edit_code: str | None = None) -> RequestCodeLookup:
    reference_code = normalize_code(reference_code)
    edit_code = normalize_code(edit_code)
    return RequestCodeLookup(reference_code=reference_code, edit_code=edit_code if edit_code else None)


def resolve_request_for_reference(reference_code):
    return get_object_or_404(
        CitizenRequest.objects.select_related("assistance_type"),
        reference_code=normalize_code(reference_code),
        is_active=True,
    )


def resolve_request_for_edit(edit_code):
    return get_object_or_404(
        CitizenRequest.objects.select_related("assistance_type"),
        edit_code=normalize_code(edit_code),
        is_active=True,
    )


def request_codes_match(reference_code: str, edit_code: str | None = None):
    base = CitizenRequest.objects.filter(reference_code=normalize_code(reference_code), is_active=True)
    if not base.exists():
        return (False, False)
    if edit_code:
        return (True, base.filter(edit_code=normalize_code(edit_code)).exists())
    return (True, False)