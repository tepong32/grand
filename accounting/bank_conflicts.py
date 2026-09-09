"""Translate known bank-match conflicts only after the owning transaction exits."""
from functools import wraps

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, connections


def bank_match_conflict_boundary(action):
    @wraps(action)
    def guarded(*args, **kwargs):
        owns_transaction = not connections["finance"].in_atomic_block
        try:
            return action(*args, **kwargs)
        except (OperationalError, IntegrityError) as exc:
            # A nested match must leave rollback/translation to automatic match's
            # outer boundary. Never continue or replay a partially aborted batch.
            code = exc.args[0] if exc.args else None
            duplicate_match = isinstance(exc, IntegrityError) and any(
                name in str(exc)
                for name in ("unique_active_statement_row_match", "unique_active_bank_journal_match")
            )
            if owns_transaction and (code == 1213 or duplicate_match):
                raise ValidationError(
                    "Another bank reconciliation changed at the same time. "
                    "This request was rolled back. Reload the statement, check its current matches, and retry if needed."
                ) from exc
            raise

    return guarded
