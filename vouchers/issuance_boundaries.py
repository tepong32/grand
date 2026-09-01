from django.db import transaction

from .models import FinanceFoundationIssuanceBoundary


DEFAULT_DB = "default"


def lock_foundation_issuance_boundary(*, department_id, fiscal_year):
    """Serialize setup amendments and number issuance for one office/year."""

    connection = transaction.get_connection(DEFAULT_DB)
    if not connection.in_atomic_block:
        raise RuntimeError(
            "Acquire the Finance issuance boundary inside a default-database transaction."
        )
    boundary, _created = FinanceFoundationIssuanceBoundary.objects.using(DEFAULT_DB).get_or_create(
        department_id=department_id,
        fiscal_year=fiscal_year,
    )
    return FinanceFoundationIssuanceBoundary.objects.using(DEFAULT_DB).select_for_update().get(
        pk=boundary.pk,
    )


def lock_foundation_issuance_boundaries(scopes):
    """Acquire multiple boundaries in deterministic order to avoid lock inversion."""

    locked = []
    normalized = sorted({
        (int(scope["department_id"]), int(scope["fiscal_year"]))
        for scope in scopes
    })
    for department_id, fiscal_year in normalized:
        locked.append(lock_foundation_issuance_boundary(
            department_id=department_id,
            fiscal_year=fiscal_year,
        ))
    return locked
