"""Same-operation reuse of complete pure Form 1 evidence verification.

This never retains a model, permission, currentness result or returned object.
Only successful original-payload validators participate; the outer operation
discards its evidence keys even on failure.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from hashlib import sha256
import json

_verified = ContextVar('form1_verified_evidence', default=None)


@contextmanager
def _scope():
    if _verified.get() is not None:
        yield
        return
    token = _verified.set(set())
    try:
        yield
    finally:
        _verified.reset(token)


def operation(function):
    @wraps(function)
    def scoped(*args, **kwargs):
        with _scope():
            return function(*args, **kwargs)
    return scoped


def _key(envelope):
    try:
        encoded = json.dumps(envelope, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return None
    # JSON encoding can coerce tuples, subclasses and non-string object keys.
    # Such inputs still receive the original complete verification, uncached.
    pending = [envelope]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                return None
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
        elif type(value) not in (str, int, float, bool, type(None)):
            return None
    return sha256(encoded.encode('ascii')).digest()


def pure_payload(function):
    @wraps(function)
    def verify(envelope):
        seen = _verified.get()
        if seen is None:
            return function(envelope)
        key = _key(envelope)
        identity = (function, key)
        if key is not None and identity in seen:
            return envelope['payload']
        result = function(envelope)
        if key is not None and result is envelope['payload']:
            seen.add(identity)
        return result
    return verify
