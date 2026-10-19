from __future__ import annotations

import re

from django.http import Http404
from assistance.models import AssistanceRequest
from assistance.services.access_service import resolve_request_for_edit

LINK_TOKEN_PATTERN = re.compile(r'^(?P<ref>.+?)\s*::\s*(?P<edit>.+?)$')


def parse_assistance_link_payload(text):
    if not text:
        return None

    match = LINK_TOKEN_PATTERN.match(text.strip())
    if not match:
        return None

    return match.group('ref').strip(), match.group('edit').strip()


def find_request_by_reference(ref_code, edit_code):
    try:
        obj = resolve_request_for_edit(edit_code)
        return obj if obj.reference_code.casefold() == ref_code.casefold() and obj.claimed_at is None else None
    except Http404:
        return None


def link_chat_to_request(request_obj, chat_id):
    request_obj.telegram_chat_id = str(chat_id)
    request_obj.save(update_fields=['telegram_chat_id'])
    return request_obj


def unlink_chat_requests(chat_id):
    return AssistanceRequest.objects.filter(
        telegram_chat_id=str(chat_id),
        claimed_at__isnull=True,
    ).update(telegram_chat_id=None)
