"""Explicit reporting-account draft partitions; never ledger changes or approval."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.summary_actuals import text
from accounting.cash_classifications import checksum
from . import form1_components
from .form1_integrity import pure_payload

FIELDS = {'key', 'component', 'amount', 'disposition', 'account_id', 'basis'}


def window(component, inventory):
    identity=component['identity']; entity=identity['entity']; column=identity['column']
    flows=inventory['flows']['payload']; parent=next(row['payload'] for row in flows['sources']['reconciliations'] if row['payload']['entity_key']==entity)
    if identity['source']['route']=='native':
        if identity['kind']=='receipt':
            day=date.fromisoformat(component['evidence']['date'])
        else:
            source=parent['actuals']['prior' if column=='prior_amount' else 'half']
            ledger=source['snapshot']['payload']['original_preparation']['coverage']['payload']['actuals']['payload']['expenditure_source']['payload']
            entry=next(row for row in ledger['journals'] if row['id']==identity['source']['entry'])
            day=date.fromisoformat(entry['entry_date'])
        return day,day
    scope=next(row['scope'] for row in flows['members'] if row['entity_key']==entity)
    year=scope['budget_year']
    return {'prior_amount':(date(year-2,1,1),date(year-2,12,31)),
        'half_amount':(date(year-1,1,1),date(year-1,6,30)),
        'estimate':(date(year-1,7,1),date(year-1,12,31)),
        'proposed':(date(year,1,1),date(year,12,31))}[column]


def propose(inventory, allocations, *, coverage_reference):
    try:
        original=form1_components.verify(inventory)
        components={row['key']:row for row in original['components']}
        members=original['flows']['payload']['sources']['forecast']['payload']['group']['members']
        charts={member['entity_key']:{row['id']:row for row in member['forecast']['payload']['capture']['payload']['accounts']} for member in members}
        if not isinstance(allocations,list):
            raise ValidationError('Supply explicit reporting-account allocations for every original component.')
        rows=[]; keys=set(); totals={key:Decimal('0.00') for key in components}; counts={key:0 for key in components}
        for supplied in allocations:
            if not isinstance(supplied,dict) or set(supplied)!=FIELDS:
                raise ValidationError('Use exact reporting-account allocation fields.')
            key=text(supplied['key'],'allocation identity',160); source=components.get(supplied['component'])
            if key in keys or source is None:
                raise ValidationError('Use each allocation identity once and select an original component.')
            keys.add(key); value=money(supplied['amount']); capacity=money(source['amount'])
            if (capacity>0 and value<=0) or (capacity<0 and value>=0) or (capacity==0 and value!=0):
                raise ValidationError('Preserve each original signed amount; do not net opposing shares or invent zero parts.')
            disposition=supplied['disposition']; account_id=supplied['account_id']; account=None
            if disposition not in ('mapped','unresolved') or (account_id is not None and type(account_id)is not int):
                raise ValidationError('Choose mapped or unresolved with an exact reporting account identity.')
            if disposition=='unresolved':
                if account_id is not None: raise ValidationError('Unresolved amounts cannot claim a reporting account.')
            elif account_id is None:
                if capacity!=0 or source['source_account'] is not None:
                    raise ValidationError('Only an original explicit zero without an account may remain account-free.')
            else:
                account=charts[source['identity']['entity']].get(account_id)
                if not account or not isinstance(account['government_account_code'],str) or not account['government_account_code'].strip():
                    raise ValidationError('Select an original captured account with an explicit government code; do not substitute its local code.')
                start,end=window(source,original)
                if ((account['effective_from'] and date.fromisoformat(account['effective_from'])>start)
                    or (account['effective_to'] and date.fromisoformat(account['effective_to'])<end)):
                    raise ValidationError('The reporting account must cover the original date or whole undated source interval.')
                if source['identity']['column'] in ('estimate','proposed') and (account['is_active'] is not True or account['allow_posting'] is not True):
                    raise ValidationError('Forecast reporting selections require an active original posting account.')
            totals[supplied['component']]+=value; counts[supplied['component']]+=1
            rows.append(dict(key=key,component=supplied['component'],amount=str(value),disposition=disposition,
                account_id=account_id,account=deepcopy(account),basis=text(supplied['basis'],'reporting-account basis')))
        if any(not counts[key] or totals[key]!=money(row['amount']) or (money(row['amount'])==0 and counts[key]!=1) for key,row in components.items()):
            raise ValidationError('Partition every original component exactly once in total, including unresolved and explicit zero amounts.')
        rows.sort(key=lambda row:row['key'])
        payload=dict(schema=1,kind='form1_reporting_account_proposal',inventory=deepcopy(inventory),allocations=rows,
            coverage_reference=text(coverage_reference,'reporting account coverage and code authority reference'),
            selection_complete=all(row['disposition']=='mapped' for row in rows),
            source_coverage_complete=original['flows']['payload']['flow_coverage_complete'],
            independently_reviewed=False,code_authority_approved=False,form_issued=False)
        return dict(payload=payload,checksum=checksum(payload))
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration) as error:
        raise ValidationError('Retain complete reporting-account source and allocation structures.') from error


@pure_payload
def verify(envelope):
    try:
        body=envelope['payload']
        inputs=[{key:row[key] for key in FIELDS} for row in body['allocations']]
        if checksum(body)!=envelope['checksum'] or propose(body['inventory'],inputs,coverage_reference=body['coverage_reference'])!=envelope:
            raise ValidationError('Reporting-account proposal does not reproduce its original selections and amounts.')
        return body
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid reporting-account proposal envelope.') from error
