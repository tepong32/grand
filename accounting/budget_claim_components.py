"""Dated classification capacity over reviewed sources; never a financial hold.

Callers must supply complete verified posted movements and reviewed component
identities. This calculator neither authenticates those inputs nor certifies totals.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from .budget_actuals import money


BASES = {"recognized_expenditure", "loan_principal", "non_expenditure"}


@dataclass(frozen=True)
class Component:
    key: str
    effective_date: date
    amount: Decimal
    basis: str


@dataclass(frozen=True)
class Movement:
    key: str
    component: str
    effective_date: date
    amount: Decimal
    kind: str = "application"
    reverses: str | None = None
    disposition: str = "exclude"
    purpose: str = "settlement"
    office_id: int | None = None
    object_class: str = ""


def validate_usage(components, movements):
    """Require dated per-component coverage and exact retained reversals.

    The reserved `origin:<component key>` identifies each original capacity event.
    Positive applications consume classification capacity; their exact reversals
    restore it on the reversal date. Capacity changes must reverse an actual earlier
    capacity event. Components are shared across offices, not copied per office.
    """
    components, movements = list(components), list(movements)
    sources, events, reverse_owners = {}, {}, {}
    for source in components:
        if (not isinstance(source, Component) or not isinstance(source.key, str) or not source.key.strip()
                or source.key in sources or type(source.effective_date) is not date
                or not isinstance(source.basis, str) or source.basis not in BASES or money(source.amount) <= 0):
            raise ValidationError("Use distinct reviewed components with explicit positive dated capacity and basis.")
        sources[source.key] = source
        key = "origin:" + source.key
        events[key] = Movement(key, source.key, source.effective_date, money(source.amount),
            kind="capacity", disposition="exclude", purpose="source_capacity")
    for movement in movements:
        if (not isinstance(movement, Movement) or not isinstance(movement.key, str) or not movement.key.strip()
                or movement.key.startswith("origin:") or movement.key in events
                or not isinstance(movement.component, str) or movement.component not in sources
                or type(movement.effective_date) is not date or movement.kind not in {"application", "capacity"}
                or (movement.reverses is not None and (not isinstance(movement.reverses, str) or not movement.reverses))
                or not isinstance(movement.purpose, str) or not movement.purpose.strip()
                or not isinstance(movement.object_class, str)
                or money(movement.amount) == 0):
            raise ValidationError("Use distinct actual movements on known source components.")
        events[movement.key] = movement
        source = sources[movement.component]
        if movement.effective_date < source.effective_date:
            raise ValidationError("A component cannot be used or reversed before its source date.")
        if movement.kind == "capacity":
            if (not movement.reverses or movement.disposition != "exclude" or movement.purpose != "source_capacity"
                    or movement.office_id is not None or movement.object_class):
                raise ValidationError("Capacity changes require exact source reversals, not new financial reserves.")
        elif movement.disposition == "include":
            if (source.basis != "loan_principal" or movement.purpose != "debt_principal"
                    or type(movement.office_id) is not int or movement.office_id <= 0
                    or not isinstance(movement.object_class, str) or not movement.object_class.strip()):
                raise ValidationError("Only an explicitly reviewed principal component can support included debt principal.")
        elif movement.disposition != "exclude" or movement.office_id is not None or movement.object_class:
            raise ValidationError("Excluded component applications cannot carry an expenditure allocation.")
        if money(movement.amount) < 0 and not movement.reverses:
            raise ValidationError("Restored classification capacity requires an exact actual reversal.")
    visited = set()
    for first in events:
        key, path = first, set()
        while key not in visited:
            if key in path:
                raise ValidationError("Component reversal lineage cannot be cyclic.")
            path.add(key)
            event = events[key]
            if not event.reverses:
                break
            prior = events.get(event.reverses)
            if (prior is None or prior.component != event.component or prior.kind != event.kind
                    or event.effective_date < prior.effective_date or money(event.amount) != -money(prior.amount)
                    or (event.disposition, event.purpose, event.office_id, event.object_class)
                       != (prior.disposition, prior.purpose, prior.office_id, prior.object_class)
                    or (event.reverses in reverse_owners and reverse_owners[event.reverses] != key)):
                raise ValidationError("Preserve one exact reversal of the original component, amount, date and classification.")
            reverse_owners[event.reverses] = key
            key = event.reverses
        visited.update(path)
    dated = defaultdict(lambda: defaultdict(lambda: {"capacity": Decimal("0.00"), "application": Decimal("0.00")}))
    for event in events.values():
        dated[event.component][event.effective_date][event.kind] += money(event.amount)
    result = {}
    for key in sources:
        capacity, applied, boundaries = Decimal("0.00"), Decimal("0.00"), []
        for day, changes in sorted(dated[key].items()):
            capacity += changes["capacity"]
            applied += changes["application"]
            if capacity < 0 or applied < 0 or applied > capacity:
                raise ValidationError(f"Component {key} exceeds its dated classification capacity on {day.isoformat()}.")
            boundaries.append({"date": day.isoformat(), "capacity": str(capacity),
                "applied": str(applied), "available": str(capacity - applied)})
        result[key] = {"capacity": str(capacity), "applied": str(applied),
                       "available": str(capacity - applied), "boundaries": boundaries}
    return result
