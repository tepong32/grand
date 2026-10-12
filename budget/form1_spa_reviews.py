"""Separate retained Budget/Accounting decisions over original SPA source shares."""
from copy import deepcopy
from hashlib import sha256
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from accounting.cash_classifications import checksum
from accounting import summary_actuals
from accounting.models import Fund
from .access import department_for_user, has_budget_permission
from .models import BudgetVersion,Form1AccountReview,Form1SPAReview as Record,Form1SPADecision as Decision
from .services import record_event
from . import form1_account_reviews as accounts,form1_spa_proposals as drafts

RELATED=('proposal__fiscal_year','fund','account_review__proposal__fiscal_year',
    'account_review__fund','account_review__forecast')


def _access(proposal,fund,actor,action):
    from vouchers.roles import is_finance_uat_viewer
    owner=department_for_user(actor)
    scopes={'prepare':(proposal.department_id,), 'budget':(proposal.department_id,),
        'accounting':(fund.department_id,), 'view':(proposal.department_id,fund.department_id),
        'export':(proposal.department_id,fund.department_id)}
    permission=(f'review_form1_spa_{action}' if action in ('budget','accounting') else f'{action}_form1_spa_reviews')
    if (action not in scopes or not owner or owner.pk not in scopes[action]
        or fund.department_id!=proposal.fiscal_year.department_id
        or not has_budget_permission(actor,permission)
        or (action not in ('view','export') and is_finance_uat_viewer(actor))):
        raise PermissionDenied('Use the original Budget/Accounting office and explicit SPA role.')


def _source_snapshot(source):
    return dict(payload=deepcopy(accounts.verify(source)),payload_checksum=source.payload_checksum,
        decision=accounts.decision(source),decision_checksum=source.decision_checksum,
        independently_reviewed=source.status=='approved',code_authority_approved=source.status=='approved',form_issued=False)


def decision(row,record):
    return dict(review=str(record.public_id),payload_checksum=record.payload_checksum,role=row.role,
        approve=row.approve,actor_id=row.actor_id,actor_department_id=row.actor_department_id,
        treatment_verified=row.treatment_verified,decided_at=row.decided_at.isoformat(),authority=row.authority,note=row.note)


def _status(rows):
    if any(not row.approve for row in rows): return 'returned'
    return 'approved' if len(rows)==2 else 'partially_approved' if rows else 'prepared'


def verify(record,decisions=None):
    try:
        payload=record.payload; source=record.account_review
        body=drafts.verify(payload['draft'])
        identity=dict(public_id=str(record.public_id),proposal=str(record.proposal.public_id),
            department_id=record.department_id,accounting_department_id=record.fund.department_id,
            fund_id=record.fund_id,account_review=str(source.public_id),version=record.version,
            prepared_by=record.prepared_by_id,prepared_at=record.prepared_at.isoformat())
        if (set(payload)!={'schema','identity','source_account_review','draft','reference','evidence'}
            or payload['schema']!=1 or payload['identity']!=identity
            or record.department_id!=record.proposal.department_id
            or record.fund.department_id!=record.proposal.fiscal_year.department_id
            or source.proposal_id!=record.proposal_id or source.fund_id!=record.fund_id or source.status!='approved'
            or payload['source_account_review']!=_source_snapshot(source)
            or body['source_draft']!=payload['source_account_review']['payload']['draft']
            or checksum(payload)!=record.payload_checksum
            or payload['evidence']['sha256']!=sha256(bytes(record.evidence)).hexdigest()):
            raise ValidationError('Retain the exact original account decision, SPA sources and authority attachment.')
        summary_actuals.text(payload['reference'],'SPA source authority reference')
        summary_actuals.text(payload['evidence']['name'],'SPA evidence name',180)
        rows=list(record.decisions.all()) if decisions is None else list(decisions)
        if len({row.role for row in rows})!=len(rows) or len({row.actor_id for row in rows})!=len(rows):
            raise ValidationError('Retain distinct original role decisions and actors.')
        for row in rows:
            if (row.review_id!=record.pk or row.role not in ('budget','accounting') or type(row.approve)is not bool
                or row.actor_id==record.prepared_by_id or not row.actor_id or not row.decided_at
                or row.decided_at<record.prepared_at or type(row.treatment_verified)is not bool
                or row.actor_department_id!=(record.department_id if row.role=='budget' else record.fund.department_id)
                or row.decision_checksum!=checksum(decision(row,record))
                or (row.approve and (not body['spa_partition_complete'] or not row.treatment_verified))):
                raise ValidationError('Retain independent decisions over complete original SPA treatment.')
            summary_actuals.text(row.authority,'SPA designation authority')
            summary_actuals.text(row.note,'SPA independent review note')
        if record.status!=_status(rows): raise ValidationError('SPA state must reproduce its immutable role decisions.')
        returned=[row for row in rows if not row.approve]
        if len(returned)>1 or (returned and any(row.decided_at>returned[0].decided_at for row in rows)):
            raise ValidationError('A returned SPA version cannot receive a later decision.')
        return payload
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid retained SPA review evidence.') from error


def _sources(record,actor,action='view'):
    source=record.account_review
    accounts._access(source.proposal,source.fund,actor,action)
    accounts._sources(source,actor,action)


def _current(record,actor):
    source=record.account_review
    if (source.status!='approved' or Form1AccountReview.objects.filter(proposal_id=record.proposal_id,
        fund_id=record.fund_id).aggregate(n=Max('version'))['n']!=source.version):
        raise ValidationError('The original approved account package has a successor.')
    accounts._current(source,actor)


@transaction.atomic(using='finance')
def prepare(*,account_review,actor,parts,coverage,coverage_reference,reference,evidence,expected_latest):
    proposal=BudgetVersion.objects.select_for_update().get(pk=account_review.proposal_id)
    fund=Fund.objects.select_for_update().get(pk=account_review.fund_id)
    _access(proposal,fund,actor,'prepare')
    source=Form1AccountReview.objects.select_related('proposal__fiscal_year','fund','forecast').get(
        pk=account_review.pk,proposal=proposal,fund=fund)
    retained=accounts.snapshot(source,actor)
    draft=drafts.propose(retained['payload']['draft'],parts,coverage,coverage_reference=coverage_reference)
    latest=Record.objects.filter(proposal=proposal,fund=fund).aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest)is not int or expected_latest!=latest:
        raise ValidationError('A newer SPA preparation exists; reload its history.')
    data,metadata=summary_actuals.document(evidence,'SPA subdivision authority')
    now=timezone.now(); public_id=uuid.uuid4()
    record=Record(public_id=public_id,proposal=proposal,fund=fund,account_review=source,version=latest+1,
        department_id=proposal.department_id,department_label=proposal.department_label,
        prepared_by_id=actor.pk,prepared_at=now,evidence=data)
    identity=dict(public_id=str(public_id),proposal=str(proposal.public_id),department_id=proposal.department_id,
        accounting_department_id=fund.department_id,fund_id=fund.pk,account_review=str(source.public_id),
        version=latest+1,prepared_by=actor.pk,prepared_at=now.isoformat())
    record.payload=dict(schema=1,identity=identity,source_account_review=retained,draft=draft,
        reference=summary_actuals.text(reference,'SPA original source authority reference'),evidence=metadata)
    record.payload_checksum=checksum(record.payload)
    verify(record,[]); _current(record,actor); record.save()
    record_event(record,'form1_spa_prepared',actor,reference,dict(payload_checksum=record.payload_checksum))
    return record


@transaction.atomic(using='finance')
def review(record,actor,*,role,approve,authority,note,treatment_verified=False):
    proposal=BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund=Fund.objects.select_for_update().get(pk=record.fund_id)
    if role not in ('budget','accounting'): raise ValidationError('Select the Budget or Accounting role.')
    _access(proposal,fund,actor,role)
    record=Record.objects.select_for_update().select_related(*RELATED).get(pk=record.pk,proposal=proposal,fund=fund)
    rows=list(record.decisions.all()); verify(record,rows); _sources(record,actor)
    if (type(approve)is not bool or type(treatment_verified)is not bool or record.status in ('approved','returned') or actor.pk==record.prepared_by_id
        or any(row.role==role or row.actor_id==actor.pk for row in rows)):
        raise ValidationError('A distinct designated actor must decide each pending role once.')
    if approve:
        if (treatment_verified is not True or not drafts.verify(record.payload['draft'])['spa_partition_complete']
            or Record.objects.filter(proposal=proposal,fund=fund).aggregate(n=Max('version'))['n']!=record.version):
            raise ValidationError('Review the latest complete SPA treatment and explicitly verify source/subdivision coverage.')
        _current(record,actor)
    row=Decision(review=record,role=role,approve=approve,actor_id=actor.pk,actor_department_id=department_for_user(actor).pk,
        treatment_verified=treatment_verified,decided_at=timezone.now(),
        authority=summary_actuals.text(authority,'SPA designation authority'),note=summary_actuals.text(note,'SPA independent review note'))
    row.decision_checksum=checksum(decision(row,record)); rows.append(row)
    record.status=_status(rows); verify(record,rows)
    row.save(); record._decision_write=True; record.save(update_fields=('status',))
    record_event(record,'form1_spa_'+role+'_decided',actor,note,decision(row,record))
    return record


def _read(record,actor,*,export=False):
    record=Record.objects.select_related(*RELATED).prefetch_related('decisions').get(pk=record.pk)
    action='export' if export else 'view'
    _access(record.proposal,record.fund,actor,action); verify(record); _sources(record,actor,action)
    return record


def _snapshot(record):
    """Internal projection; callers must authenticate the model and original sources."""
    payload=record.payload
    return dict(payload=deepcopy(payload),payload_checksum=record.payload_checksum,status=record.status,
        decisions=[dict(decision(row,record),checksum=row.decision_checksum) for row in record.decisions.all()],
        independently_reviewed=record.status=='approved',form_issued=False,cash_available=False)


def snapshot(record,actor,*,export=False):
    return _snapshot(_read(record,actor,export=export))


def evidence_bytes(record,actor):
    retained=_read(record,actor,export=True)
    return bytes(retained.evidence)


@transaction.atomic(using='finance')
def is_current(record,actor):
    proposal=BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund=Fund.objects.select_for_update().get(pk=record.fund_id)
    record=Record.objects.select_related(*RELATED).prefetch_related('decisions').get(pk=record.pk,proposal=proposal,fund=fund)
    _access(proposal,fund,actor,'view'); verify(record); _sources(record,actor)
    if record.status!='approved' or Record.objects.filter(proposal=proposal,fund=fund).aggregate(n=Max('version'))['n']!=record.version:
        return False
    try: _current(record,actor); return True
    except ValidationError: return False
