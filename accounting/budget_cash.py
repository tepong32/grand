"""Historical dated gross/restricted/net cash adoption; no native capture or posting."""
from datetime import date
from decimal import Decimal
from hashlib import sha256
import re
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from . import summary_actuals as shared
from .access import department_for_user,has_explicit_permission
from .budget_actuals import money
from .cash_classifications import checksum
from .models import BudgetCashEvidence as Record,Fund,AccountingAuditEvent


def event(record,actor,action):
    AccountingAuditEvent.objects.create(department_id=record.department_id,department_label=record.department_label,
        actor_id=actor.pk,actor_label=(actor.get_full_name() or actor.username)[:160],action=action,
        snapshot={'cash_evidence':str(record.public_id),'version':record.version,
            'payload_checksum':record.payload_checksum,'decision_checksum':record.decision_checksum})


def permitted(actor,action):
    from vouchers.roles import is_finance_uat_viewer
    return bool(actor.is_active and department_for_user(actor) and
        has_explicit_permission(actor,f'accounting.{action}_budget_cash_evidence') and
        (action in ('view','export') or not is_finance_uat_viewer(actor)))


def visible(actor):
    owner = department_for_user(actor)
    if not owner or not actor.is_active:
        raise PermissionDenied
    from budget.access import has_budget_permission
    own = any(permitted(actor, action) for action in ('view', 'prepare', 'review', 'export'))
    budget = any(has_budget_permission(actor, action) for action in
        ('prepare_budget_proposals', 'review_budget_proposals', 'view_budget_audit'))
    if not own and not budget:
        raise PermissionDenied
    query = Q(pk__in=[])
    if own:
        query |= Q(department_id=owner.pk)
        query |= Q(treasury_department_id=owner.pk, status='adopted')
    if budget:
        query |= Q(budget_department_id=owner.pk, status='adopted')
    return Record.objects.filter(query).select_related('fund').defer('certificate', 'reconciliation')


def restrictions(rows, *, no_restrictions, declaration, overlap_basis):
    if not isinstance(rows,list) or type(no_restrictions) is not bool:
        raise ValidationError('Supply explicit restriction rows or an evidenced no-restriction declaration.')
    shared.text(overlap_basis,'restriction coverage and overlap reconciliation')
    if no_restrictions:
        if rows: raise ValidationError('A no-restriction declaration cannot contain restriction amounts.')
        shared.text(declaration,'the explicit no-restriction source declaration')
        return []
    if not rows: raise ValidationError('Missing restrictions are not certified zero.')
    result,keys,refs=[],set(),set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError('Each restriction must be a structured source item.')
        key=shared.text(row.get('key'),'restriction identity',120)
        reference=shared.text(row.get('reference'),'restriction source/row',255)
        if key.casefold() in keys or reference.casefold() in refs:
            raise ValidationError('Do not count the same restriction identity or source row twice.')
        keys.add(key.casefold());refs.add(reference.casefold())
        amount=money(row.get('amount'))
        if amount<=0: raise ValidationError('Restriction leaf amounts must be positive; use an evidenced no-restriction declaration for zero.')
        result.append({'key':key,'reference':reference,'purpose':shared.text(row.get('purpose'),'restriction purpose'),
            'coverage':shared.text(row.get('coverage'),'restriction scope and overlap treatment'),'amount':str(amount)})
    return result


def decision(record):
    return {'record':str(record.public_id),'payload_checksum':record.payload_checksum,'status':record.status,
        'actor':record.reviewed_by_id,'label':record.reviewed_by_label,
        'at':record.reviewed_at.isoformat() if record.reviewed_at else None,'note':record.review_note,'authority':record.review_authority}


def verify(record):
    payload=record.payload
    identity={key:getattr(record,key) for key in ('department_id','budget_department_id','treasury_department_id','fund_id','entity_key','boundary')}
    identity['balance_date']=record.balance_date.isoformat()
    if checksum(payload)!=record.payload_checksum or any(payload['scope'][key]!=value for key,value in identity.items()) or payload['version']!=record.version or payload['prepared_by']!=record.prepared_by_id or payload['prepared_at']!=record.prepared_at.isoformat():
        raise ValidationError('Retained cash scope or evidence changed.')
    for field in ('certificate','reconciliation'):
        if sha256(bytes(getattr(record,field))).hexdigest()!=payload[field]['sha256']:
            raise ValidationError('Original cash document bytes changed.')
    total=sum((money(row['amount']) for row in payload['restrictions']),Decimal('0.00'))
    if total!=money(payload['restricted']) or money(payload['gross'])-total!=money(payload['net']):
        raise ValidationError('Gross, restricted and net cash controls do not reproduce their source.')
    if record.status!='submitted':
        if record.status not in ('adopted','returned') or not record.reviewed_at or not record.reviewed_by_id or record.reviewed_by_id==record.prepared_by_id or record.decision_checksum!=checksum(decision(record)):
            raise ValidationError('Retained independent cash adoption changed.')
    elif record.reviewed_at or record.reviewed_by_id or record.decision_checksum:
        raise ValidationError('A cash submission cannot contain a review decision.')
    return payload


@transaction.atomic(using='finance')
def propose(*,actor,fund_id,budget_department_id,treasury_department_id,entity_key,entity_label,balance_date,boundary,
            gross,restricted,net,rows,no_restrictions,declaration,overlap_basis,certificate,reconciliation,expected_latest,**metadata):
    if not permitted(actor,'prepare'): raise PermissionDenied
    from budget.models import BudgetCall
    from departments.models import Department
    owner=department_for_user(actor)
    fund=Fund.objects.select_for_update().filter(pk=fund_id,department_id=owner.pk).first()
    if not fund or not BudgetCall.objects.filter(department_id=budget_department_id,fiscal_year__department_id=owner.pk).exists() or not Department.objects.filter(pk=treasury_department_id).exists():
        raise ValidationError('Select the Accounting fund and its explicitly designated Budget/Treasury offices.')
    entity_key=shared.text(entity_key,'reporting entity',80).lower()
    if entity_key!='general' and not re.fullmatch(r'enterprise:[a-z0-9][a-z0-9_-]{0,60}',entity_key): raise ValidationError('Use the explicitly designated reporting entity key.')
    if type(balance_date) is not date or balance_date>timezone.localdate() or boundary not in ('start_of_day','end_of_day'):
        raise ValidationError('Retain the historical balance date and explicit start/end-of-day boundary.')
    scope={'department_id':owner.pk,'budget_department_id':budget_department_id,'treasury_department_id':treasury_department_id,
        'fund_id':fund.pk,'fund_code':fund.code,'entity_key':entity_key,'entity_label':shared.text(entity_label,'entity designation',255),
        'balance_date':balance_date.isoformat(),'boundary':boundary}
    group=Record.objects.filter(department_id=owner.pk,fund=fund,entity_key=entity_key,balance_date=balance_date,boundary=boundary)
    first=group.order_by('version').first()
    if first and any(first.payload['scope'][key]!=scope[key] for key in ('budget_department_id','treasury_department_id','entity_label')):
        raise ValidationError('Do not redirect this dated cash scope in a successor.')
    latest=group.aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or expected_latest!=latest: raise ValidationError('A newer cash submission exists; reload its history.')
    normalized=restrictions(rows,no_restrictions=no_restrictions,declaration=declaration,overlap_basis=overlap_basis)
    totals={key:str(money(value)) for key,value in (('gross',gross),('restricted',restricted),('net',net))}
    if money(restricted)!=sum((money(row['amount']) for row in normalized),Decimal('0.00')) or money(gross)-money(restricted)!=money(net):
        raise ValidationError('Restriction leaves and gross less restricted must reproduce the signed restricted/net controls.')
    retained={key:shared.text(metadata.get(key),key.replace('_',' ')) for key in
        ('reference','scope_authority','gross_basis','coverage','reconciliation_basis','accountant_name','accountant_authority','treasurer_name','treasurer_authority','reason')}
    if retained['accountant_name'].casefold()==retained['treasurer_name'].casefold(): raise ValidationError('Retain distinct original Treasurer and Accountant identities.')
    for role in ('accountant','treasurer'):
        day=metadata.get(role+'_certified_on')
        if type(day) is not date or not balance_date<=day<=timezone.localdate(): raise ValidationError('Original certification dates must cover this cash date and cannot be future dated.')
        retained[role+'_certified_on']=day.isoformat()
    docs={key:shared.document(upload,key) for key,upload in (('certificate',certificate),('reconciliation',reconciliation))}
    now=timezone.now();label=(actor.get_full_name() or actor.username)[:160]
    payload={'schema':1,'source_kind':'historical','scope':scope,'version':latest+1,**totals,**retained,
        'restrictions':normalized,'no_restrictions':no_restrictions,'declaration':declaration,'overlap_basis':overlap_basis,
        'certificate':docs['certificate'][1],'reconciliation':docs['reconciliation'][1],
        'prepared_by':actor.pk,'prepared_by_label':label,'prepared_at':now.isoformat()}
    record=Record.objects.create(department_id=owner.pk,department_label=owner.name,fund=fund,
        budget_department_id=budget_department_id,treasury_department_id=treasury_department_id,entity_key=entity_key,
        balance_date=balance_date,boundary=boundary,version=latest+1,payload=payload,payload_checksum=checksum(payload),
        certificate=docs['certificate'][0],reconciliation=docs['reconciliation'][0],prepared_by_id=actor.pk,prepared_by_label=label,prepared_at=now)
    event(record,actor,'budget_cash_submitted')
    return record


@transaction.atomic(using='finance')
def review(record,actor,*,adopt,note,authority,verified_documents=False):
    if not permitted(actor,'review') or record.department_id!=department_for_user(actor).pk: raise PermissionDenied
    fund=Fund.objects.select_for_update().get(pk=record.fund_id)
    if adopt is True and fund.department_id!=record.department_id:
        raise ValidationError('The cash fund no longer belongs to this Accounting ledger; reconcile its scope before review.')
    record=Record.objects.select_for_update().get(pk=record.pk);verify(record)
    if type(adopt) is not bool or record.status!='submitted' or record.prepared_by_id==actor.pk: raise ValidationError('Only an independent reviewer can decide a cash submission once.')
    if adopt:
        latest=Record.objects.filter(department_id=record.department_id,fund_id=record.fund_id,entity_key=record.entity_key,balance_date=record.balance_date,boundary=record.boundary).aggregate(n=Max('version'))['n']
        if latest!=record.version or verified_documents is not True: raise ValidationError('Review the latest submission and verify both original certifications, gross cash, restrictions and reconciliation.')
    record.status='adopted' if adopt else 'returned';record.reviewed_by_id=actor.pk
    record.reviewed_by_label=(actor.get_full_name() or actor.username)[:160];record.reviewed_at=timezone.now()
    record.review_note=shared.text(note,'independent cash review');record.review_authority=shared.text(authority,'cash adoption authority')
    record.decision_checksum=checksum(decision(record));record._decision_write=True;record.save()
    event(record,actor,'budget_cash_'+record.status)
    return record
