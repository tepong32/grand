"""Actor-bound source selections for the two nonpersistent supplies drafts."""
import hashlib
import json

from django.core import signing

from .supply_drafts import MAX_DRAFT_LINES


def source_digest(sources):
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()


def sign_selection(actor, sources, *, salt):
    return signing.dumps({"actor": actor.pk, "ids": [source["id"] for source in sources],
                          "digest": source_digest(sources)}, salt=salt)


def read_selection(token, actor, *, salt):
    if len(token) > 8000:
        raise signing.BadSignature()
    payload = signing.loads(token, salt=salt, max_age=8 * 60 * 60)
    if payload["actor"] != actor.pk:
        raise signing.BadSignature()
    ids = payload["ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_DRAFT_LINES or any(type(pk) is not int for pk in ids):
        raise signing.BadSignature()
    return payload
