"""Whole-source Form 1 period flows; stock, itemization and issuance stay separate."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import transaction

from accounting.cash_classifications import checksum
from accounting.budget_actuals import money
from accounting.summary_actuals import RECEIPTS, EXPENDITURES
from accounting.models import Fund
from .models import BudgetVersion, BudgetSummaryReconciliation
from . import receipt_forecast_reviews as forecasts, summary_reconciliations, summary_sources, office_forms

COLUMNS = ('prior_amount', 'half_amount', 'estimate', 'current_total', 'proposed')


def forecast_record(snapshot):
    payload = snapshot['payload']; identity = payload['identity']; decision = snapshot['decision']
    record = SimpleNamespace(**{key:identity[key] for key in ('public_id', 'department_id', 'fund_id', 'version')},
        proposal=SimpleNamespace(public_id=identity['proposal']), prepared_by_id=identity['prepared_by'],
        prepared_at=datetime.fromisoformat(identity['prepared_at']), payload=payload,
        payload_checksum=snapshot['payload_checksum'], status=decision['status'],
        reviewed_by_id=decision['reviewed_by'],
        reviewed_at=datetime.fromisoformat(decision['reviewed_at']) if decision['reviewed_at'] else None,
        review_note=decision['note'], review_authority=decision['authority'],
        decision_checksum=snapshot['decision_checksum'])
    forecasts.verify(record)
    if record.status != 'approved' or forecasts.decision(record) != decision:
        raise ValidationError('Use the original independently approved forecast package.')
    expected = dict(payload=payload, payload_checksum=record.payload_checksum,
        decision=decision, decision_checksum=record.decision_checksum, status=record.status,
        actual_receipts=False, cash_available=False, form_issued=False,
        reviewed_totals={member['entity_key']:{column:member['forecast']['payload']['columns'][column]['diagnostic_total']
            for column in ('half_estimate', 'proposed')} for member in payload['group']['members']})
    if snapshot != expected:
        raise ValidationError('Retain the complete original reviewed forecast snapshot.')
    return record


def parent_record(envelope):
    body = envelope['payload']; decision = envelope['decision']
    record = SimpleNamespace(public_id=envelope['public_id'],
        proposal=SimpleNamespace(public_id=body['proposal']), fund_id=body['fund_id'],
        entity_key=body['entity_key'], department_id=body['department_id'], version=body['version'],
        prepared_by_id=body['prepared_by'], prepared_at=datetime.fromisoformat(body['prepared_at']),
        payload=body, payload_checksum=envelope['payload_checksum'], status=decision['status'],
        reviewed_by_id=decision['reviewed_by'],
        reviewed_at=datetime.fromisoformat(decision['reviewed_at']) if decision['reviewed_at'] else None,
        review_note=decision['note'], review_authority=decision['authority'],
        decision_checksum=envelope['decision_checksum'])
    summary_reconciliations.verify(record)
    if body['schema'] < 2 or record.status != 'accepted' or summary_reconciliations.decision(record) != decision:
        raise ValidationError('Use original accepted reconciliation evidence with full source decisions.')
    return record


def actual_leaves(source, kind, choices):
    if any(row['kind'] not in ('receipt', 'expenditure') for row in source['rows']):
        raise ValidationError('Retain only receipt and expenditure actuals rows.')
    rows = [row for row in source['rows'] if row['kind'] == kind]
    if any(row['category'] not in choices for row in rows):
        raise ValidationError('Retain only the original required leaf categories.')
    if sum((money(row['amount']) for row in rows), Decimal('0.00')) != money(source['totals'][kind]):
        raise ValidationError('Actual leaf amounts must reproduce their retained source control.')
    return {key: str(sum((money(row['amount']) for row in rows if row['category'] == key), Decimal('0.00')))
        if any(row['category'] == key for row in rows) else None for key in choices}


def flow_rows(choices, prior, half, estimate, proposed):
    result = []
    for key, label in choices.items():
        values = dict(prior_amount=prior[key], half_amount=half[key], estimate=estimate[key], proposed=proposed[key])
        values['current_total'] = (str(money(half[key])+money(estimate[key]))
            if half[key] is not None and estimate[key] is not None else None)
        result.append(dict(category=key, label=label, amounts=values))
    totals = {column:str(sum((money(row['amounts'][column]) for row in result), Decimal('0.00')))
        if all(row['amounts'][column] is not None for row in result) else None for column in COLUMNS}
    return dict(rows=result, totals=totals)


def claim_period(periods, *, fund_id, start, end, entity, route):
    """A whole native Fund cohort also overlaps a historical route for another entity."""
    period = periods.setdefault((fund_id, start, end), dict(entities=set(), native=False))
    if period['entities'] - {entity} and (route == 'native' or period['native']):
        raise ValidationError('Two entities cannot reuse whole actuals without reviewed allocation, including mixed source routes.')
    period['entities'].add(entity)
    period['native'] = period['native'] or route == 'native'


def office_schedule(form, *, proposal, department_id, fund_id):
    body = form['payload']; schedule = body['schedule']
    if (body['proposal'] != proposal or body['department_id'] != department_id
        or schedule['fund_id'] != fund_id or checksum(body['context']) != body['context_checksum']
        or office_forms.project(body['context'], schedule['office_id'], fund_id) != schedule):
        raise ValidationError('Office flow rows must reproduce the original frozen context and proposal scope.')
    return schedule


def compose(sources):
    """Reproduce trusted retained evidence without queries or source authority grants."""
    try:
        if set(sources) != {'schema', 'kind', 'forecast', 'reconciliations'} or sources['schema'] != 1 or sources['kind'] != 'form1_flow_sources':
            raise ValidationError('Use complete original Form 1 flow sources.')
        package = forecast_record(sources['forecast'])
        group = package.payload['group']
        parents = [parent_record(row) for row in sources['reconciliations']]
        by_entity = {parent.entity_key:parent for parent in parents}
        if len(by_entity) != len(parents) or set(by_entity) != {member['entity_key'] for member in group['members']}:
            raise ValidationError('Retain every declared entity reconciliation exactly once.')
        members = []; office_owners = {}; actual_owners = {}; periods = {}
        for member in group['members']:
            forecast = member['forecast']['payload']; captured = forecast['capture']['payload']
            scope = captured['scope']; original = captured['reconciliation']; parent = by_entity[member['entity_key']]
            if (str(parent.public_id) != original['public_id'] or parent.payload_checksum != original['payload_checksum']
                or parent.decision_checksum != original['decision_checksum']
                or summary_reconciliations.decision(parent) != original['decision']
                or parent.proposal.public_id != package.proposal.public_id or parent.fund_id != package.fund_id
                or parent.department_id != package.department_id):
                raise ValidationError('Retain each forecast member\'s exact accepted reconciliation and source scope.')
            year = scope['budget_year']; actuals = {}
            for name, start, end in (('prior', date(year-2,1,1), date(year-2,12,31)),
                ('half', date(year-1,1,1), date(year-1,6,30))):
                source = deepcopy(parent.payload['actuals'][name]); source.setdefault('route', 'historical')
                body = summary_sources.verify(source); actual_scope = body['scope']
                expected = dict(department_id=scope['accounting_department_id'], budget_department_id=scope['budget_department_id'],
                    treasury_department_id=scope['treasury_department_id'], fund_id=scope['fund_id'],
                    entity_key=scope['entity_key'], entity_label=scope['entity_label'], period_start=start.isoformat(), period_end=end.isoformat())
                if any(actual_scope[key] != value for key,value in expected.items()):
                    raise ValidationError('Actuals must retain exact entity, owning offices, Fund and comparison dates.')
                claim_period(periods, fund_id=scope['fund_id'], start=start.isoformat(), end=end.isoformat(),
                    entity=member['entity_key'], route=source['route'])
                if source['route'] == 'native':
                    # Native coverage is a whole Fund cohort, not a financial split
                    # created merely by assigning it another entity designation.
                    identities = [('native-fund-period', scope['fund_id'], start.isoformat(), end.isoformat())]
                else:
                    identities = [('historical-source', source['id'])]
                    identities += [('historical-row', body['evidence']['sha256'], row['source_row'].casefold()) for row in body['rows']]
                for identity in identities:
                    if identity in actual_owners and actual_owners[identity] != member['entity_key']:
                        raise ValidationError('Two entities cannot reuse whole actuals or the same historical source row without reviewed allocation.')
                    actual_owners[identity] = member['entity_key']
                actuals[name] = body
            forms = parent.payload['forms']
            for form in forms:
                schedule = office_schedule(form, proposal=package.proposal.public_id,
                    department_id=scope['budget_department_id'], fund_id=scope['fund_id'])
                identity = (scope['fund_id'], schedule['office_id'])
                if identity in office_owners and office_owners[identity] != member['entity_key']:
                    raise ValidationError('Assign an original whole office/Fund source once; shared offices need reviewed row allocations.')
                office_owners[identity] = member['entity_key']
            estimates = {column:{key: str(sum((money(row[column]) for form in forms
                for row in form['payload']['schedule']['rows'] if row['category'] == key), Decimal('0.00')))
                for key in EXPENDITURES} for column in ('estimate', 'proposed')}
            receipt_estimates = {column:{row['category']:row['amount'] for row in forecast['columns'][column]['categories']}
                for column in ('half_estimate', 'proposed')}
            receipt = flow_rows(RECEIPTS, actual_leaves(actuals['prior'], 'receipt', RECEIPTS),
                actual_leaves(actuals['half'], 'receipt', RECEIPTS), receipt_estimates['half_estimate'], receipt_estimates['proposed'])
            expense = flow_rows(EXPENDITURES, actual_leaves(actuals['prior'], 'expenditure', EXPENDITURES),
                actual_leaves(actuals['half'], 'expenditure', EXPENDITURES), estimates['estimate'], estimates['proposed'])
            missing = [dict(kind=kind, category=row['category'], column=column) for kind,schedule in
                (('receipt', receipt), ('expenditure', expense)) for row in schedule['rows']
                for column in ('prior_amount', 'half_amount') if row['amounts'][column] is None]
            members.append(dict(entity_key=member['entity_key'], entity_label=member['entity_label'],
                scope=deepcopy(scope), receipt=receipt, expenditure=expense, missing_actual_coverage=missing,
                reported_actual_controls={name:deepcopy(body['totals']) for name,body in actuals.items()}))
        payload = dict(schema=1, kind='form1_period_flow_composition', sources=deepcopy(sources), members=members,
            flow_coverage_complete=all(not member['missing_actual_coverage'] for member in members),
            stock_complete=False, account_itemization_complete=False, philhealth_deduction_complete=False,
            form_issued=False, cash_available=False)
        return dict(payload=payload, checksum=checksum(payload))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Retain complete original Form 1 flow source structures.') from error


def verify(envelope):
    try:
        if checksum(envelope['payload']) != envelope['checksum'] or compose(envelope['payload']['sources']) != envelope:
            raise ValidationError('Retained Form 1 period flows do not reproduce their original sources.')
        return envelope['payload']
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError('Invalid retained Form 1 period flow envelope.') from error


@transaction.atomic(using='finance')
def capture(*, forecast, actor):
    """Fresh server-only composition; later source changes do not rewrite this result."""
    proposal = BudgetVersion.objects.select_for_update().get(pk=forecast.proposal_id)
    Fund.objects.select_for_update().get(pk=forecast.fund_id)
    forecast.refresh_from_db()
    snapshot = forecasts.snapshot(forecast, actor)
    if not forecasts.is_current(forecast, actor):
        raise ValidationError('Select the latest approved forecast with current original sources.')
    parents = []
    for member in snapshot['payload']['group']['members']:
        original = member['forecast']['payload']['capture']['payload']['reconciliation']
        parent = BudgetSummaryReconciliation.objects.get(public_id=original['public_id'], proposal=proposal,
            fund_id=forecast.fund_id, department_id=forecast.department_id)
        parents.append(dict(public_id=str(parent.public_id), payload=deepcopy(summary_reconciliations.verify(parent)),
            payload_checksum=parent.payload_checksum, decision=summary_reconciliations.decision(parent),
            decision_checksum=parent.decision_checksum))
    return compose(dict(schema=1, kind='form1_flow_sources', forecast=snapshot, reconciliations=parents))
