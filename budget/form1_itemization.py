"""Detached original account/leaf flows; never stock, statutory approval or issuance."""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import RECEIPTS, EXPENDITURES
from . import form1_account_proposals as accounts, form1_flows

# Each group contains unique leaf identities. Parents are never additional money.
RECEIPT_GROUPS = (
    ('tax', 'Total Tax Revenue', ('basic_rpt','business_tax','other_local_tax')),
    ('non_tax', 'Total Non-Tax Revenue', ('regulatory','service','enterprise','other_local')),
    ('local', 'Total Local Sources', ('tax','non_tax')),
    ('national_shares', 'Other Shares from National Tax Collections', ('ecozone','evat','national_wealth','tobacco')),
    ('regular_external', 'Total External Sources — Regular Income', ('nta','gocc','national_shares','philhealth')),
    ('regular', 'Total Regular Income', ('local','regular_external')),
    ('non_regular_external', 'Total External Sources — Non-Regular Income', ('interlocal','grant')),
    ('capital_investment', 'Total Capital Investment Receipts', ('asset_sale','debt_security','loan_collection')),
    ('borrowings', 'Total Receipts from Loans and Borrowings', ('loan','bond')),
    ('non_income', 'Total Non-Income Receipts', ('capital_investment','borrowings')),
    ('non_regular', 'Total Non-Regular Income', ('non_regular_external','non_income')),
    ('total', 'Total Receipts', ('regular','non_regular')),
)


def amounts(values):
    """No absent coverage becomes a numeric zero, including the derived semester total."""
    result={column:values[column] for column in ('prior_amount','half_amount','estimate','proposed')}
    result['current_total']=(str(money(result['half_amount'])+money(result['estimate']))
        if result['half_amount'] is not None and result['estimate'] is not None else None)
    return {column:result[column] for column in form1_flows.COLUMNS}


def sum_rows(rows):
    return {column:(str(sum((money(row['amounts'][column]) for row in rows),Decimal('0.00')))
        if all(row['amounts'][column] is not None for row in rows) else None)
        for column in form1_flows.COLUMNS}


def hierarchy(leaves):
    nodes={row['category']:dict(key=row['category'],label=row['label'],leaves=[row['category']],
        amounts=deepcopy(row['amounts'])) for row in leaves}
    result=[]
    for key,label,children in RECEIPT_GROUPS:
        unique=[leaf for child in children for leaf in nodes[child]['leaves']]
        if len(unique)!=len(set(unique)):
            raise ValidationError('Receipt hierarchy must count each original leaf once.')
        node=dict(key=key,label=label,children=list(children),leaves=unique,
            amounts=sum_rows([nodes[leaf] for leaf in unique]))
        nodes[key]=node; result.append(node)
    if set(nodes['total']['leaves'])!=set(RECEIPTS):
        raise ValidationError('Receipt hierarchy must retain all original required leaves.')
    return result


def compose(draft):
    try:
        body=accounts.verify(draft)
        inventory=body['inventory']['payload']; flows=inventory['flows']['payload']
        original={row['key']:row for row in inventory['components']}
        grouped={}
        for share in body['allocations']:
            source=original[share['component']]; identity=source['identity']
            key=(identity['entity'],identity['kind'],source['category'],share['disposition'],share['account_id'])
            group=grouped.setdefault(key,dict(account=deepcopy(share['account']),disposition=share['disposition'],
                source_shares=[],totals={column:Decimal('0.00') for column in ('prior_amount','half_amount','estimate','proposed')}))
            if group['account']!=share['account']:
                raise ValidationError('Retain consistent original metadata for each reporting account identity.')
            group['totals'][identity['column']]+=money(share['amount'])
            group['source_shares'].append(dict(allocation=deepcopy(share),source_component=source['key']))
        members=[]
        for member in flows['members']:
            result=dict(entity_key=member['entity_key'],entity_label=member['entity_label'],scope=deepcopy(member['scope']))
            for kind,choices in (('receipt',RECEIPTS),('expenditure',EXPENDITURES)):
                leaves=[]
                for leaf in member[kind]['rows']:
                    rows=[]
                    for key,group in grouped.items():
                        if key[:3]!=(member['entity_key'],kind,leaf['category']):continue
                        values=amounts({column:(str(value) if leaf['amounts'][column] is not None else None)
                            for column,value in group['totals'].items()})
                        rows.append(dict(account=deepcopy(group['account']),disposition=group['disposition'],
                            amounts=values,source_shares=deepcopy(group['source_shares'])))
                    rows.sort(key=lambda row:(row['disposition'],row['account']['id'] if row['account'] else -1))
                    known=sum_rows(rows)
                    for column in form1_flows.COLUMNS:
                        if leaf['amounts'][column] is not None and known[column]!=leaf['amounts'][column]:
                            raise ValidationError('Itemized amounts must reproduce each known original leaf/column.')
                    leaves.append(dict(category=leaf['category'],label=choices[leaf['category']],
                        amounts=deepcopy(leaf['amounts']),accounts=rows))
                totals=sum_rows(leaves)
                if totals!=member[kind]['totals']:
                    raise ValidationError('Itemized leaves must reproduce the original whole-entity totals.')
                result[kind]=dict(rows=leaves,totals=totals,
                    hierarchy=hierarchy(leaves) if kind=='receipt' else [])
            members.append(result)
        payload=dict(schema=1,kind='form1_itemized_flow_draft',source_draft=deepcopy(draft),members=members,
            selection_complete=body['selection_complete'],source_coverage_complete=body['source_coverage_complete'],
            independently_reviewed=False,code_authority_approved=False,spa_subdivisions_complete=False,
            stock_complete=False,philhealth_deduction_complete=False,form_issued=False,cash_available=False)
        return dict(payload=payload,checksum=checksum(payload))
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Retain complete original itemized source structures.') from error


def verify(envelope):
    try:
        body=envelope['payload']
        if checksum(body)!=envelope['checksum'] or compose(body['source_draft'])!=envelope:
            raise ValidationError('Itemized flow draft does not reproduce its original shares and controls.')
        return body
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid itemized flow draft envelope.') from error
