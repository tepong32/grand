"""Exact shared-payment arithmetic over unchanged original financial lines.

This module does not authorize, persist or approve attribution, or enable a new
posting route. Coordinated approval, source ownership and multi-source reversal
integration must be implemented before these results can govern settlements.
"""
from collections import defaultdict
from copy import copy

from django.core.exceptions import ValidationError

from .claim_splits import ZERO, _amount, _normalize_allocations


def normalize_shared_allocations(sources, applications, rows):
    """Allocate each real credit and application once across explicit invoices.

Input rows contain ``source_id`` and ``invoices`` (the existing invoice schema).
Output adds canonical per-credit application totals. Projected financial amounts
exist only on shallow copies for calculation; original line IDs remain evidence
identities and no stored journal/subsidiary line is changed or fabricated.
"""
    sources, applications = list(sources), list(applications)
    by_source = {line.pk: line for line in sources}
    by_application = {str(line.pk): line for line in applications}
    if (len(sources) < 2 or len(by_source) != len(sources)
            or not isinstance(rows, list) or len(rows) != len(sources)
            or any(not isinstance(row, dict) or set(row) != {'source_id', 'invoices'}
                or type(row['source_id']) is not int for row in rows)
            or {row['source_id'] for row in rows} != set(by_source)):
        raise ValidationError('Allocate each selected original credit once in the shared schedule.')
    if (len(by_application) != len(applications)
            or any(line.pk in by_source for line in applications)):
        raise ValidationError('Select each historical application once, separately from the original credits.')
    owner = lambda line: (line.entry.department_id, line.entry.fund_id, line.account_id)
    if any(owner(line) != owner(sources[0]) for line in [*sources, *applications]):
        raise ValidationError('Use historical credits and applications from the same office, fund and liability account.')
    for line in applications:
        if bool(_amount(line.debit)) == bool(_amount(line.credit)):
            raise ValidationError('Each historical application must have exactly one financial side.')

    totals = defaultdict(lambda: ZERO)
    members = []
    for row in sorted(rows, key=lambda row: row['source_id']):
        invoices = row['invoices']
        if not isinstance(invoices, list) or not invoices:
            raise ValidationError('Identify at least one invoice for each original credit.')
        shares = defaultdict(lambda: ZERO)
        for invoice in invoices:
            if (not isinstance(invoice, dict) or not isinstance(invoice.get('applications'), dict)
                    or any(pk not in by_application for pk in invoice['applications'])):
                raise ValidationError('Allocate only the selected historical applications using their retained IDs.')
            for pk, value in invoice['applications'].items():
                amount = _amount(value)
                shares[pk] += amount
                totals[pk] += amount
        members.append((row, shares))
    if any(totals[pk] != _amount(line.debit or line.credit) for pk, line in by_application.items()):
        raise ValidationError('Allocate every shared historical application in full across the original credits.')

    result, keys, identities = [], set(), set()
    for row, shares in members:
        projected = []
        for pk in sorted(shares, key=int):
            if not shares[pk]:
                continue
            original = by_application[pk]
            line = copy(original)
            line.debit, line.credit = (shares[pk], ZERO) if original.debit else (ZERO, shares[pk])
            projected.append(line)
        invoices = _normalize_allocations(by_source[row['source_id']], projected,
            row['invoices'], minimum_invoices=1)
        for invoice in invoices:
            identity = (invoice['party_key'].casefold(), invoice['claim_reference'].casefold())
            if invoice['key'] in keys or identity in identities:
                raise ValidationError('Use each invoice identity only once across the shared schedule.')
            keys.add(invoice['key'])
            identities.add(identity)
        result.append({'source_id': row['source_id'], 'invoices': invoices,
            'applications': {pk: str(shares[pk]) for pk in sorted(shares, key=int) if shares[pk]}})
    return result
