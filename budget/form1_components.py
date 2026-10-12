"""Original Form 1 flow components, without inferred reporting-account mappings."""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from . import form1_flows

SOURCE_COLUMNS = ('prior_amount', 'half_amount', 'estimate', 'proposed')


def inventory(flows):
    """Pure original component closure; current total is derived, never another source."""
    try:
        body = form1_flows.verify(flows)
        group = body['sources']['forecast']['payload']['group']
        parents = {row['payload']['entity_key']:row['payload'] for row in body['sources']['reconciliations']}
        components = []

        def append(entity, kind, column, category, value, identity, evidence, account=None):
            original = dict(entity=entity, kind=kind, column=column, source=identity)
            components.append(dict(key=checksum(original), identity=original, category=category,
                amount=str(money(value)), evidence=deepcopy(evidence), source_account=deepcopy(account),
                reporting_account_status='not_mapped'))

        for member in group['members']:
            entity = member['entity_key']; parent = parents[entity]
            for period, column in (('prior', 'prior_amount'), ('half', 'half_amount')):
                source = parent['actuals'][period]
                if source.get('route', 'historical') == 'native':
                    original = source['snapshot']['payload']['original_preparation']['coverage']['payload']
                    actuals = original['actuals']['payload']
                    for position, row in enumerate(actuals['receipts']['payload']['bridge']):
                        allocation = row['allocation']
                        if allocation['disposition'] == 'include':
                            append(entity, 'receipt', column, allocation['category'], allocation['signed_amount'],
                                dict(route='native', record=source['id'], entry=row['entry_id'],
                                    line=allocation['line_id'], component_position=position), row, row['account'])
                    classes = {row['expense_class']:row['category'] for row in original['class_mappings']}
                    for position, row in enumerate(actuals['expenditures']['payload']['rows']):
                        for part_position, part in enumerate(row['components']):
                            append(entity, 'expenditure', column, classes[row['expense_class']],
                                part['allocation']['signed_amount'], dict(route='native', record=source['id'],
                                    entry=part['entry_id'], line=part['line_id'], row_position=position,
                                    component_position=part_position), part, row['account'])
                else:
                    for position, row in enumerate(source['payload']['rows']):
                        append(entity, row['kind'], column, row['category'], row['amount'],
                            dict(route='historical', record=source['id'], source_row=row['source_row'], position=position),
                            row, dict(id=row['account_id'], code=row['account_code'], title=row['account_title'])
                                if row['account_id'] is not None else None)
            forecast = member['forecast']['payload']
            for original_column, column in (('half_estimate', 'estimate'), ('proposed', 'proposed')):
                for row in forecast['columns'][original_column]['components']:
                    if row['disposition'] == 'include':
                        append(entity, 'receipt', column, row['category'], row['amount'],
                            dict(route='forecast', record=body['sources']['forecast']['payload']['identity']['public_id'],
                                source=row['source_id'], component=row['key']), row, row['account'])
                for form in parent['forms']:
                    for position, row in enumerate(form['payload']['schedule']['rows']):
                        append(entity, 'expenditure', column, row['category'], row[column],
                            dict(route='office', record=form['id'], position=position), row,
                            dict(id=row['account_id'], code=row['account_code'], title=row['account_title']))
        components.sort(key=lambda row:row['key'])
        if len({row['key'] for row in components}) != len(components):
            raise ValidationError('Retain each original flow component exactly once.')
        controls = []
        for member in body['members']:
            for kind in ('receipt', 'expenditure'):
                for row in member[kind]['rows']:
                    for column in SOURCE_COLUMNS:
                        selected = [item for item in components if item['identity']['entity'] == member['entity_key']
                            and item['identity']['kind'] == kind and item['identity']['column'] == column
                            and item['category'] == row['category']]
                        value = sum((money(item['amount']) for item in selected), Decimal('0.00'))
                        expected = row['amounts'][column]
                        if expected is not None and value != money(expected):
                            raise ValidationError('Original components must reproduce each known flow leaf exactly.')
                        controls.append(dict(entity=member['entity_key'], kind=kind, category=row['category'],
                            column=column, component_amount=str(value), declared_amount=expected,
                            coverage='missing' if expected is None else 'covered', component_keys=[item['key'] for item in selected]))
        payload = dict(schema=1, kind='form1_original_flow_components', flows=deepcopy(flows),
            components=components, controls=controls, account_itemization_complete=False,
            independently_reviewed=False, form_issued=False)
        return dict(payload=payload, checksum=checksum(payload))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Retain complete original Form 1 component evidence.') from error


def verify(envelope):
    try:
        if checksum(envelope['payload']) != envelope['checksum'] or inventory(envelope['payload']['flows']) != envelope:
            raise ValidationError('Form 1 components no longer reproduce their original sources.')
        return envelope['payload']
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError('Invalid retained Form 1 component inventory.') from error
