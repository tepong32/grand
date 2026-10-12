"""Named joint actuals decisions over retained sources and Fund trial balance."""
from datetime import datetime, date
from types import SimpleNamespace
import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from . import budget_actuals_preparations as preparations, budget_native_actuals as actuals
from . import budget_actuals_trial_balance as trial_balance
from .access import department_for_user, has_explicit_permission
from .summary_actuals import text
from .budget_actuals import money
from .cash_classifications import checksum
from .models import NativeBudgetActualsPreparation as Preparation, NativeBudgetActualsDecision as Decision, Fund, AccountingAuditEvent

ROLES=('accountant','treasurer')


def permitted(actor, role):
    from vouchers.roles import is_finance_uat_viewer
    return bool(role in ROLES and not is_finance_uat_viewer(actor)
        and has_explicit_permission(actor,f'accounting.certify_{role}_native_budget_actuals'))


def _visible(record,actor,action='view'):
    if not preparations.visible(actor,action).filter(pk=record.pk).exists(): raise PermissionDenied


def _observe(record):
    from departments.models import Department
    original=preparations.verify(record)
    owner=Department.objects.filter(pk=record.department_id).first()
    if not owner: raise ValidationError('The retained Accounting source owner is no longer available.')
    observed=actuals._capture_for_owner(owner=owner,
        fund_id=record.fund_id,period_start=record.period_start,period_end=record.period_end)
    if observed['source_checksum']!=original['coverage']['payload']['actuals']['source_checksum']:
        raise ValidationError('Native actuals sources changed; prepare a successor.')
    return {'actuals':observed,'trial_balance':trial_balance.project(observed)}


def verify_decision(record, decision):
    original=preparations.verify(record)
    return _verify_decision(record,decision,original)


def _verify_decision(record,decision,original,original_trial=None):
    """Same-operation original already verified by this record's caller.

    Every officer's separate observation still reproduces its actuals and trial
    balance. This is no authorization/currentness cache or public bypass flag.
    """
    try:
        body=decision.payload
        identity=dict(public_id=str(decision.public_id),preparation=str(record.public_id),
            preparation_checksum=record.payload_checksum,review_checksum=record.decision_checksum,
            department_id=record.department_id,role=decision.role,outcome=decision.outcome,
            actor_id=decision.actor_id,actor_label=decision.actor_label,actor_department_id=decision.actor_department_id,
            decided_at=decision.decided_at.isoformat())
        office=record.department_id if decision.role=='accountant' else record.treasury_department_id
        if (record.status!='approved' or checksum(body)!=decision.payload_checksum
            or body['schema']!=1 or body['kind']!='native_budget_actuals_role_decision' or body['identity']!=identity
            or decision.preparation_id!=record.pk or decision.department_id!=record.department_id
            or decision.role not in ROLES or decision.outcome not in ('certified','returned')
            or decision.actor_department_id!=office or not decision.actor_id or decision.actor_id==record.prepared_by_id
            or decision.decided_at < record.reviewed_at):
            raise ValidationError('Retain exact independently authorized actuals role/office/source identity.')
        text(body['authority'],'certification authority'); text(body['note'],'decision explanation',4000)
        observation=body['observation']
        if decision.outcome=='certified':
            # project() itself verifies the complete observed native actuals.
            observed_trial=trial_balance.project(observation['actuals'])
            if original_trial is None:
                original_trial=trial_balance.project(original['coverage']['payload']['actuals'])
            if (observation['actuals']['source_checksum']!=original['coverage']['payload']['actuals']['source_checksum']
                or observation['trial_balance']!=observed_trial
                or observation['trial_balance']!=original_trial):
                raise ValidationError('Role certification must reproduce its exact source cohort and Fund trial balance.')
            read_at=datetime.fromisoformat(observation['actuals']['payload']['receipts']['captured_at'])
            if timezone.is_naive(read_at) or read_at>decision.decided_at:
                raise ValidationError('Retain source observation before the actuals decision.')
        elif observation is not None:
            raise ValidationError('A return must not invent successful observed source evidence.')
        return body
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid retained native actuals role decision.') from error


def _decisions(record):
    decisions=list(record.joint_decisions.order_by('decided_at','pk'))
    for decision in decisions: verify_decision(record,decision)
    if (len({d.role for d in decisions})!=len(decisions) or len({d.actor_id for d in decisions})!=len(decisions)
        or any(d.outcome=='returned' for d in decisions[:-1])):
        raise ValidationError('Retain distinct independent role actors and exact joint closure.')
    return decisions


@transaction.atomic(using='finance')
def decide(*, preparation_id, actor, role, certify, authority, note):
    if not permitted(actor,role): raise PermissionDenied
    if type(certify) is not bool: raise ValidationError('Choose explicit certification or return.')
    stored=Preparation.objects.get(pk=preparation_id); _visible(stored,actor)
    office=stored.department_id if role=='accountant' else stored.treasury_department_id
    if department_for_user(actor).pk!=office: raise PermissionDenied
    fund=Fund.objects.select_for_update().get(pk=stored.fund_id)
    record=Preparation.objects.select_for_update().get(pk=stored.pk); preparations.verify(record)
    decisions=_decisions(record)
    if (record.status!='approved' or actor.pk==record.prepared_by_id
        or any(d.role==role or d.actor_id==actor.pk or d.outcome=='returned' for d in decisions)):
        raise ValidationError('A distinct designated officer must decide a pending role on reviewed preparation.')
    authority=text(authority,'certification authority'); note=text(note,'decision explanation',4000)
    observation=None
    if certify:
        if fund.department_id!=record.department_id or preparations.group(record).aggregate(n=Max('version'))['n']!=record.version:
            raise ValidationError('Source ownership or latest preparation changed; retain a return.')
        observation=_observe(record)
    now=timezone.now(); key=uuid.uuid4(); label=(actor.get_full_name() or actor.username)[:160]
    identity=dict(public_id=str(key),preparation=str(record.public_id),preparation_checksum=record.payload_checksum,
        review_checksum=record.decision_checksum,department_id=record.department_id,role=role,
        outcome='certified' if certify else 'returned',actor_id=actor.pk,actor_label=label,
        actor_department_id=office,decided_at=now.isoformat())
    payload=dict(schema=1,kind='native_budget_actuals_role_decision',identity=identity,
        authority=authority,note=note,observation=observation)
    decision=Decision.objects.create(public_id=key,preparation=record,department_id=record.department_id,
        department_label=record.department_label,role=role,outcome=identity['outcome'],actor_id=actor.pk,
        actor_label=label,actor_department_id=office,decided_at=now,payload=payload,payload_checksum=checksum(payload))
    verify_decision(record,decision)
    AccountingAuditEvent.objects.create(department_id=record.department_id,department_label=record.department_label,
        actor_id=actor.pk,actor_label=label,action='native_budget_actuals_decided',snapshot=dict(
            preparation=str(record.public_id),decision=str(key),role=role,outcome=identity['outcome'],
            preparation_checksum=record.payload_checksum,decision_checksum=decision.payload_checksum))
    return decision


def snapshot(record,actor,action='view'):
    _visible(record,actor,action)
    return _snapshot(record,list(record.joint_decisions.order_by('decided_at','pk')))


def _snapshot(record,decisions):
    original=preparations.verify(record)
    original_trial=trial_balance.project(original['coverage']['payload']['actuals'])
    for d in decisions: _verify_decision(record,d,original,original_trial)
    if (len({d.role for d in decisions})!=len(decisions) or len({d.actor_id for d in decisions})!=len(decisions)
        or any(d.outcome=='returned' for d in decisions[:-1])):
        raise ValidationError('Retain independent actors and exact joint decision closure.')
    status=('returned' if record.status=='returned' or any(d.outcome=='returned' for d in decisions) else
        'awaiting_category_review' if record.status!='approved' else
        'jointly_certified' if len(decisions)==2 else 'awaiting_joint_certification')
    coverage=original['coverage']['payload']
    totals={kind:str(sum((money(row['amount']) for row in coverage[kind+'_rows']),money('0')))
        if status=='jointly_certified' else None for kind in ('receipt','expenditure')}
    payload=dict(schema=1,kind='native_budget_joint_actuals_snapshot',preparation_id=record.pk,
        original_preparation=original,preparation_checksum=record.payload_checksum,
        review=preparations.decision(record),review_checksum=record.decision_checksum,status=status,
        totals=totals,trial_balance=original_trial,
        decisions=[{'payload':d.payload,'checksum':d.payload_checksum} for d in decisions])
    return {'payload':payload,'checksum':checksum(payload)}


def verify_snapshot(captured):
    """Pure integrity reproduction of trusted server-issued evidence, not client authority."""
    try:
        body=captured['payload']; original=body['original_preparation']; identity=original['identity']
        if type(body['preparation_id']) is not int or body['preparation_id']<=0:
            raise ValidationError('Retain the exact preparation identity.')
        fields=dict(identity); fields.update(body['review'])
        for key in ('prepared_at','reviewed_at'):
            fields[key]=datetime.fromisoformat(fields[key]) if fields[key] else None
        for key in ('period_start','period_end'): fields[key]=date.fromisoformat(fields[key])
        fields.update(pk=body['preparation_id'],payload=original,payload_checksum=body['preparation_checksum'],
            decision_checksum=body['review_checksum'])
        record=SimpleNamespace(**fields)
        decisions=[]
        for envelope in body['decisions']:
            data=envelope['payload']; values=dict(data['identity'])
            values['decided_at']=datetime.fromisoformat(values['decided_at'])
            values.update(preparation_id=record.pk,payload=data,payload_checksum=envelope['checksum'])
            decisions.append(SimpleNamespace(**values))
        if any(a.decided_at>b.decided_at for a,b in zip(decisions,decisions[1:])):
            raise ValidationError('Retain decisions in their original time order.')
        if _snapshot(record,decisions)!=captured:
            raise ValidationError('Joint actuals snapshot does not reproduce its retained sources and approvals.')
        return body
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid detached joint actuals snapshot.') from error


def is_current(record,actor):
    retained=snapshot(record,actor)
    if (retained['payload']['status']!='jointly_certified'
        or not Fund.objects.filter(pk=record.fund_id,department_id=record.department_id).exists()
        or preparations.group(record).aggregate(n=Max('version'))['n']!=record.version): return False
    try: _observe(record)
    except ValidationError: return False
    return True
