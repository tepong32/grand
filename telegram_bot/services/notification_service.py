"""Fail closed until a reviewed association-qualification mechanism exists.

A chat ID or even a valid private binding is not notification qualification.
There is deliberately no settings switch, async send or transport construction
here. Delivery implementation requires a separately reviewed persisted evidence
contract and enforcement at this boundary before any transport can be enabled.
"""


def send_telegram_update(request_obj, message):
    """Deny all current/legacy destinations; return whether anything was sent."""
    return False
