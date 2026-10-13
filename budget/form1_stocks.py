"""Draft Form 1 opening-stock calendar and resource arithmetic, without issuance.

Annual opening is a linked January boundary, not an addition of semester stocks.
Pure verification grants no source authority, independent review or cash capacity.
"""
from copy import deepcopy
from datetime import date

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import text
from accounting import budget_cash
from . import form1_flows as flows, form1_stock_sources as stocks
from . import form1_cash_forecasts as bridges, receipt_forecast_reviews as reviews
from .models import BudgetReceiptForecast

OPENINGS=('prior_amount','half_amount','estimate','proposed')
CONVENTION='annual_boundary_reference'


def _actual(source):
    body=source['payload']
    if (checksum(body)!=source['checksum'] or body['kind']!='form1_actual_stock_source'
        or type(body['schema']) is not int or body['schema']!=1
        or any(body[key] is not False for key in ('form_issued','cash_available','source_freshness_certified'))):
        raise ValidationError('Retain the whole original cash stock envelope.')
    original=body['snapshot']['payload']
    if body['route']=='native':
        if original['status']!='jointly_certified':raise ValidationError('Retain both original cash certifications.')
        if (checksum(original)!=body['snapshot']['checksum'] or original['preparation']!=body['public_id']
            or checksum(original['original_preparation'])!=original['preparation_checksum']):
            raise ValidationError('Retain the whole original native cash snapshot and preparation identity.')
        original=original['original_preparation']
        restrictions=original['restriction_source']['payload']
    elif body['route']=='historical':
        snapshot=body['snapshot']
        if (checksum(original)!=snapshot['payload_checksum'] or checksum(snapshot['decision'])!=snapshot['decision_checksum']
            or snapshot['decision']['status']!='adopted' or snapshot['decision']['payload_checksum']!=snapshot['payload_checksum']
            or snapshot['decision']['record']!=body['public_id']):
            raise ValidationError('Retain the whole original adopted cash payload and decision.')
        restrictions=original
    else:raise ValidationError('Retain the explicit actual cash source route.')
    if (any(body[key]!=original[key] for key in ('gross','restricted','net'))
        or body['scope']!={key:original['scope'][key] for key in stocks.SCOPE_FIELDS}
        or money(body['gross'])-money(body['restricted'])!=money(body['net'])
        or sum((money(row['amount']) for row in body['restrictions']),money('0'))!=money(body['restricted'])):
        raise ValidationError('Actual stock projection must reproduce its original scope and controls.')
    if (body['restrictions']!=budget_cash.restrictions(restrictions['restrictions'],
        no_restrictions=restrictions['no_restrictions'],declaration=restrictions['declaration'],overlap_basis=restrictions['overlap_basis'])
        or any(body[key]!=restrictions[key] for key in ('no_restrictions','declaration','overlap_basis'))):
        raise ValidationError('Retain every original restriction identity, declaration and overlap basis.')
    return body


def _claims(claims,body,entity,target=None):
    # Whole native cash cannot be assigned to multiple entities by changing labels,
    # whether it appears directly or as a future projection's retained anchor.
    native=body['route']=='native'
    for scope in (body['scope'],target) if target else (body['scope'],):
        key=tuple(scope[field] for field in ('fund_id','balance_date','boundary'))
        owners,had_native=claims.get(key,(set(),False))
        if owners-{entity} and (native or had_native):
            raise ValidationError('Whole native cash requires reviewed allocation before cross-entity reuse.')
        claims[key]=(owners|{entity},had_native or native)


def compose(flow, selections, *, stock_convention, boundary_basis):
    """Pure draft calculation after server source/worksheet authorization."""
    try:
        if stock_convention!=CONVENTION:raise ValidationError('Retain the explicit annual-boundary draft convention.')
        basis=text(boundary_basis,'annual/semester stock boundary reconciliation')
        original=flows.verify(flow)
        if not isinstance(selections,list):raise ValidationError('Retain each original flow entity stock selection.')
        if any(not isinstance(row,dict) or set(row)!={'entity_key','opening'} for row in selections):
            raise ValidationError('Retain exact entity and whole opening-stock choices.')
        chosen={row['entity_key']:row['opening'] for row in selections}
        if len(chosen)!=len(selections) or set(chosen)!={row['entity_key'] for row in original['members']}:
            raise ValidationError('Stock inventory must match every original flow entity exactly once.')
        result=[]; claims={}
        for member in original['members']:
            scope=member['scope']; year=scope['budget_year']; entity=member['entity_key']
            if type(year) is not int or not 3<=year<=9999:raise ValidationError('Retain the original budget calendar year.')
            dates=dict(prior_amount=date(year-2,1,1),half_amount=date(year-1,1,1),
                estimate=date(year-1,7,1),proposed=date(year,1,1))
            choices=chosen[entity]
            if not isinstance(choices,dict) or set(choices)!=set(OPENINGS):
                raise ValidationError('Select all four unique opening boundaries; annual opening is an H1 reference.')
            cells={}
            for column in OPENINGS:
                choice=choices[column]
                expected=dict(department_id=scope['accounting_department_id'],
                    budget_department_id=scope['budget_department_id'],treasury_department_id=scope['treasury_department_id'],
                    fund_id=scope['fund_id'],entity_key=entity,balance_date=dates[column].isoformat(),boundary='start_of_day')
                if not isinstance(choice,dict):raise ValidationError('Retain an explicit actual, forecast or missing stock choice.')
                kind=choice.get('kind')
                if kind=='missing' and set(choice)=={'kind','basis'}:
                    cell=dict(kind=kind,scope=expected,gross=None,restricted=None,net=None,
                        basis=text(choice['basis'],'missing stock evidence'),source=None)
                elif kind in ('actual','forecast') and set(choice)=={'kind','source'}:
                    source=choice['source']
                    if kind=='actual':
                        body=_actual(source); actual_scope=body['scope']; anchor=body
                        if column=='proposed':raise ValidationError('A proposed opening needs an explicit estimate, not a relabelled actual.')
                    else:
                        body=source['payload']; anchor=_actual(body['source']); actual_scope=body['target']
                        if column in ('prior_amount','half_amount'):
                            raise ValidationError('Actual columns cannot be filled with forecast stocks.')
                        if bridges._calculate(body['source'],body['evidence'],**body['inputs'])!=source:
                            raise ValidationError('Retain the exact whole cash timing/restriction forecast.')
                    if actual_scope!=expected:raise ValidationError('Stock source must match exact flow owners, entity and opening boundary.')
                    _claims(claims,anchor,entity,target=actual_scope)
                    cell=dict(kind=kind,scope=expected,gross=body['gross'],restricted=body['restricted'],net=body['net'],source=deepcopy(source))
                else:raise ValidationError('Retain the explicit original stock choice, without additional derived fields.')
                cells[column]=cell
            cells['current_total']=dict(deepcopy(cells['half_amount']),reference_column='half_amount')
            ending={column:(str(money(cells[column]['net'])+money(member['receipt']['totals'][column])
                -money(member['expenditure']['totals'][column])) if all(value is not None for value in (
                    cells[column]['net'],member['receipt']['totals'][column],member['expenditure']['totals'][column])) else None)
                for column in flows.COLUMNS}
            result.append(dict(entity_key=entity,scope=deepcopy(scope),opening=cells,
                draft_resource_ending=ending,certified_actual_closing_cash=False,
                opening_coverage_complete=all(cell['net'] is not None for cell in cells.values())))
        body=dict(schema=1,kind='form1_opening_stock_draft',flow=deepcopy(flow),selections=deepcopy(selections),
            stock_convention=stock_convention,boundary_basis=basis,members=result,
            opening_coverage_complete=all(row['opening_coverage_complete'] for row in result),
            independently_reviewed=False,stock_complete=False,philhealth_deduction_complete=False,
            form_issued=False,cash_available=False)
        return dict(payload=body,checksum=checksum(body))
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Retain complete original Form 1 stock sources and calendar.') from error


def verify(envelope):
    try:
        body=envelope['payload']
        if checksum(body)!=envelope['checksum'] or compose(body['flow'],body['selections'],
            stock_convention=body['stock_convention'],boundary_basis=body['boundary_basis'])!=envelope:
            raise ValidationError('Stock draft must reproduce every original flow, choice and boundary.')
        return deepcopy(body)
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid original Form 1 opening stock draft.') from error


def _authorize(selections,actor,evidence,*,current,export=False):
    if not isinstance(evidence,dict):raise ValidationError('Retain the original forecast worksheet byte registry.')
    used=set()
    for row in selections:
        for choice in row['opening'].values():
            if choice['kind']=='missing':continue
            source=choice['source']
            if choice['kind']=='forecast':
                used.add(source['checksum'])
                bridges.reproduce(source,actor,evidence=evidence.get(source['checksum']),export=export)
                source=source['payload']['source']
            body=stocks.require_visible(source,actor,export=export)
            if current and stocks.capture(route=body['route'],identity=body['public_id'],expected_scope=body['scope'],actor=actor)!=source:
                raise ValidationError('Select the exact current original stock anchor.')
    if set(evidence)!=used:
        raise ValidationError('Retain exactly the original worksheets for selected forecast bridges.')


def capture(*,forecast,actor,selections,evidence,stock_convention,boundary_basis):
    flow=flows.capture(forecast=forecast,actor=actor)
    draft=compose(flow,selections,stock_convention=stock_convention,boundary_basis=boundary_basis)
    _authorize(draft['payload']['selections'],actor,evidence,current=True)
    return draft


def reproduce(envelope,actor,*,evidence,export=False):
    body=verify(envelope)
    original=body['flow']['payload']['sources']['forecast']
    record=BudgetReceiptForecast.objects.filter(public_id=original['payload']['identity']['public_id']).first()
    if not record or reviews.snapshot(record,actor,export=export)!=original:
        raise ValidationError('Retain accessible exact original reviewed flow sources.')
    _authorize(body['selections'],actor,evidence,current=False,export=export)
    return body
