"""Two-period retained office reconciliation, without joint signing or issuance."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from accounting.cash_classifications import checksum
from accounting.models import Fund
from .models import BudgetSummaryReconciliation as Record, BudgetVersion, BudgetOfficeForm
from . import office_forms, summary_sources
from .summary_comparison import compare_cohort
from .services import _require_action, record_event


def decision(record):
    return {'payload_checksum': record.payload_checksum, 'status': record.status,
        'reviewed_by': record.reviewed_by_id, 'reviewed_at': record.reviewed_at.isoformat() if record.reviewed_at else None,
        'note': record.review_note, 'authority': record.review_authority}


def calculations(payload):
    result = {}
    for name in ('prior', 'half'):
        result[name] = compare_cohort(payload['actuals'][name]['payload'],
            [member['payload'] for member in payload['forms']], expected_offices=payload['expected_offices'],
            entity_key=payload['entity_key'], coverage_reference=payload['coverage_reference'])
    return result


def verify(record):
    payload = record.payload
    if payload.get('schema') not in (1,2,3):
        raise ValidationError('Unsupported retained reconciliation schema.')
    if checksum(payload) != record.payload_checksum or any(payload[key] != value for key, value in
        {'proposal': str(record.proposal.public_id), 'fund_id': record.fund_id, 'entity_key': record.entity_key,
         'version': record.version, 'department_id': record.department_id, 'prepared_by': record.prepared_by_id,
         'prepared_at': record.prepared_at.isoformat()}.items()):
        raise ValidationError('Retained reconciliation identity or payload changed.')
    if payload['schema']>=2:
        try:
            for name in ('prior','half'):
                source = payload['actuals'][name]
                if payload['schema']==3:
                    summary_sources.verify(source)
                    continue
                original = source['decision']
                if (checksum(source['payload'])!=source['payload_checksum'] or
                    checksum(original)!=source['decision_checksum'] or original['record']!=source['id'] or
                    original['payload_checksum']!=source['payload_checksum'] or original['status']!='approved' or
                    not original['reviewed_by'] or original['reviewed_by']==source['payload']['prepared_by'] or
                    not original['reviewed_at'] or not original['authority'] or not original['note']):
                    raise ValidationError('Retained original adoption evidence changed.')
            for source in payload['forms']:
                original = source['decision']
                if (checksum(source['payload'])!=source['payload_checksum'] or checksum(original)!=source['decision_checksum'] or
                    original['payload_checksum']!=source['payload_checksum'] or original['document_checksum']!=source['document_checksum'] or
                    original['status']!='issued' or not original['actor'] or original['actor']==source['payload']['prepared_by_id'] or
                    not original['at'] or not original['note']):
                    raise ValidationError('Retained original office issuance evidence changed.')
        except (KeyError,TypeError):
            raise ValidationError('Retain complete original source decisions in this reconciliation version.')
    if payload['schema'] == 3:
        try:
            scope = payload['actuals']['half']['payload']['scope']
            past = payload['actuals']['prior']['payload']['scope']
            year = payload['forms'][0]['payload']['schedule']['budget_year']
            if (any(scope[key] != past[key] for key in ('department_id', 'budget_department_id',
                    'treasury_department_id', 'fund_id', 'entity_key', 'entity_label'))
                or scope['fund_id'] != record.fund_id or scope['budget_department_id'] != record.department_id
                or scope['entity_key'] != record.entity_key
                or (past['period_start'], past['period_end'], scope['period_start'], scope['period_end']) != (
                    date(year-2,1,1).isoformat(), date(year-2,12,31).isoformat(),
                    date(year-1,1,1).isoformat(), date(year-1,6,30).isoformat())):
                raise ValidationError('Retain exact common actuals scope and proposal comparison periods.')
        except (KeyError, TypeError, IndexError, ValueError) as error:
            raise ValidationError('Retain complete native reconciliation scope evidence.') from error
    if calculations(payload) != payload['comparisons']:
        raise ValidationError('Retained reconciliation calculations changed.')
    if record.status != 'prepared':
        if record.status not in ('accepted', 'returned') or not record.reviewed_at or not record.reviewed_by_id or record.reviewed_by_id == record.prepared_by_id or checksum(decision(record)) != record.decision_checksum:
            raise ValidationError('Retained independent reconciliation decision changed.')
    elif record.reviewed_by_id or record.reviewed_at or record.decision_checksum:
        raise ValidationError('A preparation cannot contain a review decision.')
    return payload


@transaction.atomic(using='finance')
def prepare(*, proposal, actor, prior_id, half_id, form_ids, expected_offices, entity_key,
            coverage_reference, expected_latest, prior_route='historical', half_route='historical'):
    proposal = BudgetVersion.objects.select_for_update().get(pk=proposal.pk)
    _require_action(actor, proposal, 'prepare_budget_proposals')
    office_forms.frozen_context(proposal, actor)
    actuals = {}
    for name, identity, route in (('prior', prior_id, prior_route), ('half', half_id, half_route)):
        actuals[name] = summary_sources.capture(actor=actor, budget_department_id=proposal.department_id,
            identity=identity, route=route)
    schema = 3 if 'native' in (prior_route, half_route) else 2
    if schema == 2:
        for source in actuals.values():
            source.pop('route')  # Preserve the existing historical schema and verifier.
    scope = actuals['half']['payload']['scope']
    past = actuals['prior']['payload']['scope']
    if any(scope[key] != past[key] for key in ('department_id','budget_department_id','treasury_department_id','fund_id','entity_key','entity_label')):
        raise ValidationError('Both joint periods must have the same reporting scope and officers’ owning offices.')
    year = proposal.fiscal_year.year
    if (past['period_start'],past['period_end'],scope['period_start'],scope['period_end']) != (
        date(year-2,1,1).isoformat(),date(year-2,12,31).isoformat(),date(year-1,1,1).isoformat(),date(year-1,6,30).isoformat()):
        raise ValidationError('Joint periods must match the proposal comparison years exactly.')
    if schema == 3:
        Fund.objects.select_for_update().get(pk=scope['fund_id'])
        for source in actuals.values():
            summary_sources.require_current(source, actor=actor, budget_department_id=proposal.department_id)
    if not isinstance(form_ids, list) or not form_ids or len(set(form_ids)) != len(form_ids):
        raise ValidationError('Select distinct issued office versions.')
    forms = []
    for identity in form_ids:
        member = BudgetOfficeForm.objects.filter(public_id=identity, proposal=proposal,
            department_id=proposal.department_id, status=BudgetOfficeForm.ISSUED).first()
        if not member:
            raise ValidationError('Each selected form must be issued from this proposal.')
        if schema == 3:
            require_current_office(member)
        forms.append({'id': str(member.public_id), 'payload_checksum': member.payload_checksum,
            'decision_checksum': member.decision_checksum, 'document_checksum': member.document_checksum,
            'decision':deepcopy(office_forms.decision_payload(member)),
            'payload': deepcopy(office_forms.verify(member))})
    latest = Record.objects.filter(proposal=proposal,fund_id=scope['fund_id'],entity_key=entity_key).aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or expected_latest != latest:
        raise ValidationError('A newer reconciliation preparation exists; reload its history.')
    now = timezone.now()
    payload = {'schema':schema,'proposal':str(proposal.public_id),'department_id':proposal.department_id,
        'fund_id':scope['fund_id'],'entity_key':entity_key,'version':latest+1,'actuals':actuals,'forms':forms,
        'expected_offices':deepcopy(expected_offices),'coverage_reference':coverage_reference,
        'prepared_by':actor.pk,'prepared_at':now.isoformat()}
    payload['comparisons'] = calculations(payload)
    record = Record.objects.create(proposal=proposal, fund_id=scope['fund_id'],entity_key=entity_key,
        version=latest+1,department_id=proposal.department_id,department_label=proposal.department_label,
        payload=payload,payload_checksum=checksum(payload),prepared_by_id=actor.pk,prepared_at=now)
    record_event(record,'summary_reconciliation_prepared',actor,coverage_reference,{'payload_checksum':record.payload_checksum})
    return record


def require_current_office(member):
    latest = BudgetOfficeForm.objects.filter(proposal_id=member.proposal_id, office_id=member.office_id,
        fund_id=member.fund_id).aggregate(n=Max('version'))['n']
    if latest != member.version:
        raise ValidationError('A newer office form exists; select its independently issued version.')


@transaction.atomic(using='finance')
def review(record, actor, *, accept, note, authority):
    proposal = BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    _require_action(actor,proposal,'review_budget_proposals')
    if accept and record.payload.get('schema') == 3:
        Fund.objects.select_for_update().get(pk=record.fund_id)
    record = Record.objects.select_for_update().get(pk=record.pk,proposal=proposal)
    payload = verify(record)
    summary_sources.require_visible(payload, actor)
    if accept and payload['schema']<2:
        raise ValidationError('Prepare a successor retaining complete source decisions before new acceptance.')
    if type(accept) is not bool or record.status != 'prepared' or record.prepared_by_id == actor.pk:
        raise ValidationError('A different reviewer must decide a pending reconciliation once.')
    note = office_forms.required(note,'independent reconciliation review')
    authority = office_forms.required(authority,'coverage review designation')
    latest = Record.objects.filter(proposal=proposal,fund_id=record.fund_id,entity_key=record.entity_key).aggregate(n=Max('version'))['n']
    if accept and (latest != record.version or any(Decimal(row['difference']) != 0 for result in payload['comparisons'].values() for row in result['rows'])):
        raise ValidationError('Resolve every class difference and review the latest preparation before acceptance.')
    if accept and payload['schema'] == 3:
        office_forms.frozen_context(proposal, actor)
        for source in payload['actuals'].values():
            summary_sources.require_current(source, actor=actor, budget_department_id=proposal.department_id)
        for source in payload['forms']:
            member = BudgetOfficeForm.objects.filter(public_id=source['id'], proposal=proposal,
                department_id=proposal.department_id, status=BudgetOfficeForm.ISSUED).first()
            if not member or office_forms.verify(member) != source['payload'] or office_forms.decision_payload(member) != source['decision']:
                raise ValidationError('Selected office issuance evidence changed; retain a successor reconciliation.')
            require_current_office(member)
    record.status = 'accepted' if accept else 'returned'
    record.reviewed_by_id, record.reviewed_at = actor.pk, timezone.now()
    record.review_note, record.review_authority = note, authority
    record.decision_checksum = checksum(decision(record))
    record._decision_write = True
    record.save()
    record_event(record,'summary_reconciliation_'+record.status,actor,note,decision(record))
    return record
