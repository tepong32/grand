"""Evidenced cash-timing bridge drafts over original authorized stock sources.

These estimates never post, certify actual cash, establish intra-day capacity or
inherit officer approval. Budgetary flow totals are not cash movements.
"""
from copy import deepcopy
from datetime import date
from hashlib import sha256

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import text, document
from . import form1_stock_sources as stocks

INPUTS=('target_date','target_boundary','cash_changes','proposed_restrictions','restriction_changes',
    'cash_coverage','cash_basis','no_cash_changes','cash_declaration',
    'restriction_coverage','restriction_basis','no_restrictions','restriction_declaration')
CASH_FIELDS={'key','source_row','effective_date','direction','amount','basis'}
RESTRICTION_FIELDS={'key','source_row','effective_date','restriction','action','amount','basis'}
LEAF_FIELDS={'key','reference','purpose','coverage'}


def _day(value):
    if not isinstance(value,str):raise ValidationError('Retain the explicit ISO cash forecast date.')
    try: result=date.fromisoformat(value)
    except ValueError as error:raise ValidationError('Retain the explicit ISO cash forecast date.') from error
    if result.isoformat()!=value:raise ValidationError('Retain the canonical ISO cash forecast date.')
    return result


def _moves(rows,fields,anchor,target,kind):
    if not isinstance(rows,list):raise ValidationError('Retain explicit cash-timing and restriction movement lists.')
    result=[]; keys=set(); references=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!=fields:raise ValidationError('Retain the complete structured forecast movement.')
        item=deepcopy(row); key=text(item['key'],'forecast movement identity',120)
        reference=text(item['source_row'],'original worksheet row',255)
        day=_day(item['effective_date'])
        if (key.casefold() in keys or reference.casefold() in references
            or not (day>anchor[0] or day==anchor[0] and anchor[1]=='start_of_day')
            or not (day<target[0] or day==target[0] and target[1]=='end_of_day')):
            raise ValidationError('Each worksheet row must be unique and fall after the actual anchor, within the target boundary.')
        choice=item['direction' if kind=='cash' else 'action']
        if choice not in (('in','out') if kind=='cash' else ('add','remove')):
            raise ValidationError('Select explicit cash in/out or restriction addition/removal.')
        amount=money(item['amount'])
        if amount<=0:raise ValidationError('Forecast movements require positive amounts and an explicit direction.')
        item.update(key=key,source_row=reference,amount=str(amount),basis=text(item['basis'],'cash timing/source reconciliation'))
        if kind!='cash':item['restriction']=text(item['restriction'],'original or proposed restriction identity',120)
        result.append(item); keys.add(key.casefold()); references.add(reference.casefold())
    return sorted(result,key=lambda item:(item['effective_date'],item['key']))


def _calculate(source,evidence,**inputs):
    """Arithmetic only; public callers authenticate the whole source first."""
    if set(inputs)!=set(INPUTS):raise ValidationError('Retain the whole explicit cash forecast schedule.')
    original=source['payload']; anchor_scope=original['scope']
    target_day=_day(inputs['target_date']); target_boundary=inputs['target_boundary']
    anchor=(_day(anchor_scope['balance_date']),anchor_scope['boundary']); target=(target_day,target_boundary)
    if target_boundary not in ('start_of_day','end_of_day') or (
        target_day,int(target_boundary=='end_of_day'))<=(anchor[0],int(anchor[1]=='end_of_day')):
        raise ValidationError('Forecast forward from the original actual cash boundary.')
    for coverage in ('cash_coverage','restriction_coverage'):
        if inputs[coverage] not in ('complete','missing'):raise ValidationError('Declare complete or missing forecast coverage.')
    for flag in ('no_cash_changes','no_restrictions'):
        if type(inputs[flag]) is not bool:raise ValidationError('Retain explicit forecast zero declarations.')
    for field in ('cash_declaration','restriction_declaration'):
        if not isinstance(inputs[field],str):raise ValidationError('Retain explicit declaration text, or an empty string.')
    cash=_moves(inputs['cash_changes'],CASH_FIELDS,anchor,target,'cash')
    changes=_moves(inputs['restriction_changes'],RESTRICTION_FIELDS,anchor,target,'restriction')
    cash_complete=inputs['cash_coverage']=='complete'; restrictions_complete=inputs['restriction_coverage']=='complete'
    if inputs['no_cash_changes']:
        if not cash_complete or cash:raise ValidationError('A no-cash-change declaration requires complete empty movement coverage.')
        cash_declaration=text(inputs['cash_declaration'],'explicit no-cash-change evidence')
    else:
        cash_declaration=inputs['cash_declaration']
        if cash_complete and not cash:raise ValidationError('Missing cash changes are not an evidenced zero forecast.')
        if cash_declaration:raise ValidationError('Do not attach a zero declaration to a non-zero or missing schedule.')
    positions={row['key']:dict(original=deepcopy(row),proposed=False,amount=money(row['amount'])) for row in original['restrictions']}
    keys={key.casefold() for key in positions}; references={item['original']['reference'].casefold() for item in positions.values()}
    proposed=inputs['proposed_restrictions']
    if not isinstance(proposed,list):raise ValidationError('Retain explicit proposed restriction identities.')
    leaves=[]
    for row in proposed:
        if not isinstance(row,dict) or set(row)!=LEAF_FIELDS:raise ValidationError('Retain complete proposed restriction identity and coverage.')
        leaf={field:text(row[field],'proposed restriction '+field,120 if field=='key' else 255 if field=='reference' else 2000) for field in LEAF_FIELDS}
        if leaf['key'].casefold() in keys or leaf['reference'].casefold() in references:
            raise ValidationError('Do not rename or duplicate an original restriction identity/reference.')
        positions[leaf['key']]=dict(original=deepcopy(leaf),proposed=True,amount=money('0'))
        keys.add(leaf['key'].casefold()); references.add(leaf['reference'].casefold()); leaves.append(leaf)
    additions=set(); days={}
    for change in changes:
        if change['restriction'] not in positions:raise ValidationError('Select an exact original or proposed restriction identity.')
        if change['action']=='add':additions.add(change['restriction'])
        delta=money(change['amount'])*(1 if change['action']=='add' else -1)
        group=days.setdefault(change['effective_date'],{})
        group[change['restriction']]=group.get(change['restriction'],money('0'))+delta
    for day in sorted(days):
        for key,delta in days[day].items():
            positions[key]['amount']+=delta
            if positions[key]['amount']<0:
                raise ValidationError('Later forecast additions cannot fund earlier restriction removals.')
    if any(leaf['key'] not in additions for leaf in leaves):raise ValidationError('Every new restriction requires an explicit forecast addition.')
    restricted=money(sum((item['amount'] for item in positions.values()),money('0')))
    if inputs['no_restrictions']:
        if not restrictions_complete or restricted:raise ValidationError('An evidenced zero target restriction requires complete zero coverage.')
        restriction_declaration=text(inputs['restriction_declaration'],'explicit target no-restriction evidence')
    else:
        restriction_declaration=inputs['restriction_declaration']
        if restrictions_complete and not restricted:raise ValidationError('Zero future restrictions need their own explicit declaration.')
        if restriction_declaration:raise ValidationError('Do not attach a zero restriction declaration to non-zero or missing coverage.')
    cash_change=money(sum((money(row['amount'])*(1 if row['direction']=='in' else -1) for row in cash),money('0')))
    gross=money(money(original['gross'])+cash_change)
    normalized=dict(inputs,target_date=target_day.isoformat(),cash_changes=cash,
        proposed_restrictions=sorted(leaves,key=lambda row:row['key']),restriction_changes=changes,
        cash_basis=text(inputs['cash_basis'],'whole cash timing/coverage reconciliation'),cash_declaration=cash_declaration,
        restriction_basis=text(inputs['restriction_basis'],'whole restriction coverage/overlap reconciliation'),
        restriction_declaration=restriction_declaration)
    body=dict(schema=1,kind='form1_cash_forecast_bridge_draft',source=deepcopy(source),inputs=normalized,
        target=dict(anchor_scope,balance_date=target_day.isoformat(),boundary=target_boundary),evidence=deepcopy(evidence),
        cash_change=str(cash_change),diagnostic_gross=str(gross),diagnostic_restricted=str(restricted),
        restriction_positions=[dict(item,amount=str(item['amount'])) for _,item in sorted(positions.items())],
        gross=str(gross) if cash_complete else None,restricted=str(restricted) if restrictions_complete else None,
        net=str(money(gross-restricted)) if cash_complete and restrictions_complete else None,
        coverage_complete=cash_complete and restrictions_complete,independently_reviewed=False,
        actual_cash=False,cash_available=False,source_freshness_certified=False,form_issued=False)
    return dict(payload=body,checksum=checksum(body))


def propose(*,source,actor,evidence,**inputs):
    """Return the unreviewed draft and original worksheet bytes for later retention."""
    try:
        body=source['payload']
        observed=stocks.capture(route=body['route'],identity=body['public_id'],expected_scope=body['scope'],actor=actor)
        if observed!=source:raise ValidationError('Select the exact current original cash source.')
        data,metadata=document(evidence,'original cash timing and restriction forecast worksheet')
        return _calculate(source,metadata,**inputs),data
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Retain the complete original cash forecast bridge evidence.') from error


def reproduce(envelope,actor,*,evidence,export=False):
    """Original-source authority and byte checks, independent of newer source heads."""
    try:
        body=envelope['payload']
        if checksum(body)!=envelope['checksum'] or not isinstance(evidence,bytes) or sha256(evidence).hexdigest()!=body['evidence']['sha256']:
            raise ValidationError('Retain the original whole forecast draft and worksheet bytes.')
        stocks.require_visible(body['source'],actor,export=export)
        if _calculate(body['source'],body['evidence'],**body['inputs'])!=envelope:
            raise ValidationError('Forecast controls must reproduce the original source and entire schedule.')
        return deepcopy(body)
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid original cash forecast bridge draft.') from error
