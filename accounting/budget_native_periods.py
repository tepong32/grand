"""Exact-period views of trusted retained ledger evidence; never certification."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from . import budget_native_sources as sources, budget_claim_sources as claims
from .cash_classifications import checksum


def reframe(captured, *, period_start, period_end):
    """Narrow a server capture without rereading posting or approval pointers.

    The parent capture must cover the entire requested activity period. Retained
    reversal and connected claim journals remain dependencies only. Callers must
    retain the parent alongside this derived view: a checksum is not authority.
    """
    payload = sources.verify(captured)
    try:
        if (payload['schema'] != 7 or type(period_start) is not date or type(period_end) is not date
                or not date.fromisoformat(payload['scope']['period_start']) <= period_start
                <= period_end <= date.fromisoformat(payload['scope']['period_end'])):
            raise ValidationError('Select a complete period inside the retained current-schema source.')
        entries = {}
        for group in ('journals', 'lineage_sources', 'claim_sources'):
            for entry in payload[group]:
                if type(entry['id']) is not int or entry['id'] in entries:
                    raise ValidationError('Retain each ledger source identity exactly once.')
                entries[entry['id']] = entry
        selected = [entry for entry in payload['journals']
            if period_start <= date.fromisoformat(entry['entry_date']) <= period_end]
        selected_ids = {entry['id'] for entry in selected}
        ancestors = {key for entry in selected for key in entry['lineage']['ancestor_ids']}
        graph, _, _ = claims.dependency_graph(entries)
        retained = selected_ids | ancestors
        while True:
            if not retained <= entries.keys():
                raise ValidationError('Retain complete source dependencies before narrowing a period.')
            expanded = claims.related(retained, graph)
            for key in list(expanded):
                expanded.update(entries[key]['lineage']['ancestor_ids'])
            if expanded == retained:
                break
            retained = expanded
        lines = [line for entry in selected for line in entry['lines']]
        controls = {'journals': len(selected), 'lines': len(lines),
            'debit': str(sum((Decimal(line['debit']) for line in lines), Decimal('0.00'))),
            'credit': str(sum((Decimal(line['credit']) for line in lines), Decimal('0.00'))),
            'unassigned_lines': sum(line['center']['office_id'] is None for line in lines),
            'unresolved_lineage': sum(bool(entry['lineage']['issue']) for entry in selected)}
        derived = deepcopy(payload)
        derived['scope'].update(period_start=period_start.isoformat(), period_end=period_end.isoformat())
        derived.update(journals=deepcopy(selected),
            lineage_sources=[deepcopy(entry) for key, entry in entries.items() if key in ancestors - selected_ids],
            claim_sources=[deepcopy(entry) for key, entry in entries.items()
                if key in retained - selected_ids - ancestors], controls=controls)
        result = {'payload': derived, 'checksum': checksum(derived), 'captured_at': captured['captured_at']}
        result['evidence_checksum'] = checksum({'source_checksum': result['checksum'],
            'captured_at': result['captured_at']})
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid retained ledger period or dependency evidence.') from error
