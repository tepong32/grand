"""Object-level planning schedule from validated choices and proposal lines."""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError


def project(groups, choices, labels):
    rows = {}

    def row_for(key, expense_class, account_code, account_title):
        identity = (*key, expense_class.strip().casefold())
        office_id = labels['office_ids'].get(key[1])
        return rows.setdefault(identity, {'fund_id': key[0], 'center_id': key[1], 'account_id': key[2],
            'fund_code': labels['funds'][key[0]], 'center_code': labels['centers'][key[1]],
            'office_id': office_id, 'office_label': labels['office_names'].get(office_id, ''),
            'account_code': account_code, 'account_title': account_title, 'expense_class': expense_class,
            'proposal_lines': [], 'prior_rows': [], 'half_rows': []})

    for key, group in groups.items():
        if group['office_id'] != labels['office_ids'].get(key[1]):
            raise ValidationError('Proposal office mapping changed during capture. Reload the planning context.')
        for line in group['lines']:
            row_for(key, line['expense_class'], group['account'], group['account_title'])['proposal_lines'].append(deepcopy(line))
    for choice in choices.values():
        for evidence in choice['rows']:
            key = (choice['fund_id'], choice['center_id'], evidence['account_id'])
            group = groups.get(key, {})
            row = row_for(key, evidence['expense_class'], evidence.get('account_code', group.get('account', '')),
                          evidence.get('account_title', group.get('account_title', '')))
            if not row['office_id'] or evidence.get('scope', {}).get('office_id') != row['office_id']:
                raise ValidationError('Selected actuals do not match the captured office identity. Review the source mapping.')
            row['fund_code'] = choice.get('fund_code', row['fund_code'])
            row['center_code'] = choice.get('center_code', row['center_code'])
            row[choice['prefix'] + '_rows'].append(deepcopy(evidence))
    result = []
    for identity in sorted(rows):
        row = rows[identity]
        lines = row['proposal_lines']
        row['has_proposal'] = bool(lines)
        row['proposed'] = str(sum((Decimal(line['proposed']) for line in lines), Decimal('0.00')))
        row['estimate'] = str(sum((Decimal(line['estimate']) for line in lines), Decimal('0.00'))) if (
            lines and all(line['estimate'] is not None for line in lines)) else None
        for prefix in ('prior', 'half'):
            evidence = row[prefix + '_rows']
            row[prefix + '_amount'] = str(sum((Decimal(item['amount']) for item in evidence), Decimal('0.00'))) if evidence else None
        row['current_total'] = str(Decimal(row['half_amount']) + Decimal(row['estimate'])) if (
            row['half_amount'] is not None and row['estimate'] is not None) else None
        result.append(row)
    return result
