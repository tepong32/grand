"""Whole original Form 1 draft assembly; retained approvals remain source-specific."""
from copy import deepcopy

from django.core.exceptions import ValidationError
from accounting.cash_classifications import checksum
from . import form1_spa_output as spa, form1_spa_reviews as reviews
from . import form1_philhealth as philhealth, form1_flows as flows
from .models import Form1SPAReview
from .form1_integrity import operation


@operation
def compose(spa_source,philhealth_source):
    """Reproduce all rows from one exact original flow, without granting approval."""
    try:
        original_spa=spa.verify(spa_source); original_ph=philhealth.verify(philhealth_source)
        stock=original_ph['inventory']['payload']['stock']['payload']
        itemization=original_spa['flow']['payload']['itemization']['payload']
        account=itemization['source_draft']['payload']
        flow=account['inventory']['payload']['flows']
        if flow!=stock['flow']:
            raise ValidationError('The account/SPA and stock/PhilHealth packages must retain the exact same whole flow source.')
        indexed={row['entity_key']:row for row in itemization['members']}
        subdivisions={row['entity_key']:row for row in original_spa['members']}
        openings={row['entity_key']:row for row in stock['members']}
        deductions={row['entity_key']:row for row in original_ph['members']}
        if any(set(indexed)!=set(rows) for rows in (subdivisions,openings,deductions)):
            raise ValidationError('Retain every original entity in every whole-form schedule.')
        members=[]
        for entity,member in indexed.items():
            subdivision=subdivisions[entity]; opening=openings[entity]; deduction=deductions[entity]
            if any(row['scope']!=member['scope'] for row in (subdivision,opening,deduction)):
                raise ValidationError('Whole-form schedules must retain the same original offices, Fund, entity and year.')
            if (deduction['resource_ending']!=opening['draft_resource_ending']
                or any(set(values)!=set(flows.COLUMNS) for values in (
                    member['receipt']['totals'],member['expenditure']['totals'],
                    opening['draft_resource_ending'],deduction['deduction'],deduction['net_ending']))):
                raise ValidationError('Retain all five original financial columns and matching resource-ending controls.')
            members.append(dict(entity_key=entity,entity_label=member['entity_label'],scope=deepcopy(member['scope']),
                opening=deepcopy(opening['opening']),receipt=deepcopy(member['receipt']),
                expenditure=deepcopy(member['expenditure']),spa=deepcopy(subdivision),
                resource_ending=deepcopy(opening['draft_resource_ending']),
                philhealth=deepcopy(deduction),net_ending=deepcopy(deduction['net_ending'])))
        coverage=dict(flow=itemization['source_coverage_complete'],
            account_selection=itemization['selection_complete'],
            spa_partition=original_spa['spa_review']['payload']['draft']['payload']['spa_partition_complete'],
            opening=stock['opening_coverage_complete'],philhealth_partition=original_ph['deduction_partition_complete'])
        body=dict(schema=1,kind='form1_whole_assembly_draft',spa_source=deepcopy(spa_source),
            philhealth_source=deepcopy(philhealth_source),members=members,coverage=coverage,
            calculation_coverage_complete=all(coverage.values()),independently_reviewed=False,
            stock_complete=False,philhealth_deduction_complete=False,form_issued=False,
            cash_available=False,source_freshness_certified=False)
        return dict(payload=body,checksum=checksum(body))
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Retain complete original Form 1 schedules and source evidence.') from error


@operation
def verify(envelope):
    try:
        body=envelope['payload']
        if checksum(body)!=envelope['checksum'] or compose(body['spa_source'],body['philhealth_source'])!=envelope:
            raise ValidationError('The whole Form 1 assembly must reproduce every original schedule and control.')
        return deepcopy(body)
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid whole Form 1 assembly draft.') from error


def capture(*,spa_review,philhealth_source,actor,evidence,documents):
    """New selection requires current reviewed SPA and current stock/flow sources."""
    snapshot=reviews.snapshot(spa_review,actor)
    if not reviews.is_current(spa_review,actor):
        raise ValidationError('Select the current independently reviewed account/SPA source package.')
    original=philhealth.reproduce(philhealth_source,actor,evidence=evidence,documents=documents)
    retained_stock=original['inventory']['payload']['stock']
    if philhealth.capture(stock=retained_stock,actor=actor,evidence=evidence)!=original['inventory']:
        raise ValidationError('Select the exact current original stock/PhilHealth sources.')
    return compose(spa.package(snapshot),philhealth_source)


def reproduce(envelope,actor,*,evidence,documents,export=False):
    """Historical reads recheck original source rights and bytes without substitution."""
    body=verify(envelope); snapshot=body['spa_source']['payload']['spa_review']
    source=Form1SPAReview.objects.filter(public_id=snapshot['payload']['identity']['public_id']).first()
    if not source or reviews.snapshot(source,actor,export=export)!=snapshot:
        raise ValidationError('Retain the accessible exact original SPA model, decisions and attachments.')
    philhealth.reproduce(body['philhealth_source'],actor,evidence=evidence,documents=documents,export=export)
    return body
