"""Immutable internal whole-package decisions; no statutory signatures or issuance."""
from copy import deepcopy

from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from accounting.cash_classifications import checksum
from accounting.models import Fund
from accounting.summary_actuals import text
from .access import department_for_user,has_budget_permission
from .models import BudgetVersion,Form1Package as Package,Form1PackageDecision as Decision
from . import form1_packages as packages
from .services import record_event

CHECKS={
    'budget':('entity_inventory','estimates','stock_calendar','planning_cash_reconciliation','philhealth_policy'),
    'accounting':('actuals','accounts_and_spa','philhealth_sources','overlap_treatment'),
    'treasury':('cash_sources','restriction_lineage','timing_worksheet'),
}


def required(record,body):
    return {('budget',record.department_id),('accounting',record.fund.department_id),
        *(('treasury',member['scope']['treasury_department_id']) for member in body['members'])}


def _checks(role,supplied):
    if not isinstance(supplied,dict) or set(supplied)!=set(CHECKS[role]):
        raise ValidationError('Retain every explicit check for the original designated role.')
    for check in supplied.values():
        if not isinstance(check,dict) or set(check)!={'verified','basis'} or type(check['verified'])is not bool:
            raise ValidationError('Record an explicit verified/not-verified choice and basis for every check.')
        text(check['basis'],'independent whole-package verification basis')
    return deepcopy(supplied)


def _identity(record,row):
    return dict(public_id=str(row.public_id),package=str(record.public_id),package_checksum=record.payload_checksum,
        role=row.role,actor_id=row.actor_id,actor_department_id=row.actor_department_id,
        approve=row.approve,decided_at=row.decided_at.isoformat())


def _observation(record,approve):
    return dict(assembly_checksum=record.payload['assembly']['checksum'],
        attachments=deepcopy(record.payload['attachments']),source_current=True if approve else None)


def _state(record,body,rows):
    """Pure decision projection after the caller verifies the original whole package."""
    try:
        expected=required(record,body)
        if len({(row.role,row.actor_department_id) for row in rows})!=len(rows) or len({row.actor_id for row in rows})!=len(rows):
            raise ValidationError('Retain one distinct independent actor per required office/role decision.')
        for row in rows:
            payload=row.payload
            if (row.package_id!=record.pk or (row.role,row.actor_department_id) not in expected
                or type(row.actor_id)is not int or row.actor_id<=0 or row.actor_id==record.prepared_by_id
                or type(row.actor_department_id)is not int or type(row.approve)is not bool
                or timezone.is_naive(row.decided_at) or row.decided_at<record.prepared_at
                or set(payload)!={'schema','identity','checks','observation','authority','note'}
                or type(payload['schema'])is not int or payload['schema']!=1
                or checksum(payload['identity'])!=checksum(_identity(record,row))
                or checksum(payload['observation'])!=checksum(_observation(record,row.approve))
                or checksum(payload)!=row.payload_checksum):
                raise ValidationError('Retain the original independent actor, package and observed source evidence.')
            checks=_checks(row.role,payload['checks'])
            text(payload['authority'],'independent whole-package designation authority')
            text(payload['note'],'independent whole-package decision reason')
            if row.approve and (not body['calculation_coverage_complete'] or not all(item['verified'] for item in checks.values())):
                raise ValidationError('Approval requires complete original controls and all designated checks verified.')
        returned=[row for row in rows if not row.approve]
        if len(returned)>1 or (returned and any(row.decided_at>returned[0].decided_at for row in rows)):
            raise ValidationError('A returned whole package cannot receive later internal decisions.')
        complete=bool(rows) and not returned and {(row.role,row.actor_department_id) for row in rows}==expected
        status='returned' if returned else 'reviewed' if complete else 'partially_reviewed' if rows else 'prepared'
        return dict(package=str(record.public_id),package_checksum=record.payload_checksum,status=status,
            required_reviews=[dict(role=role,department_id=office) for role,office in sorted(expected)],
            decisions=[dict(payload=deepcopy(row.payload),checksum=row.payload_checksum)
                for row in sorted(rows,key=lambda row:(row.decided_at,row.role,row.actor_department_id))],
            internal_review_complete=complete,statutorily_certified=False,chief_executive_approved=False,
            form_issued=False,cash_available=False)
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid retained whole-package internal review evidence.') from error


def verify(record,decisions=None,attachments=None):
    body=packages.verify(record,attachments)
    rows=list(record.decisions.all()) if decisions is None else list(decisions)
    return _state(record,body,rows)


@transaction.atomic(using='finance')
def review(record,actor,*,role,approve,checks,authority,note):
    proposal=BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund=Fund.objects.select_for_update().get(pk=record.fund_id)
    record=Package.objects.select_for_update().get(pk=record.pk,proposal=proposal,fund=fund)
    owner=department_for_user(actor)
    from vouchers.roles import is_finance_uat_viewer
    if (not isinstance(role,str) or role not in CHECKS or not owner or not getattr(actor,'is_active',False)
        or not has_budget_permission(actor,'review_form1_package_'+role) or is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use the designated original office and explicit independent whole-package review permission.')
    record=packages._read(record,actor)
    body=record.payload['assembly']['payload'];rows=list(record.decisions.all());state=_state(record,body,rows)
    if (type(approve)is not bool or (role,owner.pk) not in required(record,body)
        or actor.pk==record.prepared_by_id or state['status'] in ('reviewed','returned')
        or any(row.actor_id==actor.pk or (row.role,row.actor_department_id)==(role,owner.pk) for row in rows)):
        raise ValidationError('A distinct designated officer must decide each pending role once.')
    checked=_checks(role,checks)
    if approve and (not body['calculation_coverage_complete'] or not all(item['verified'] for item in checked.values())
        or not packages._current(record,actor)):
        raise ValidationError('Approve only the latest complete package with current original sources and every check verified.')
    row=Decision(package=record,role=role,actor_id=actor.pk,actor_department_id=owner.pk,
        approve=approve,decided_at=timezone.now())
    row.payload=dict(schema=1,identity=_identity(record,row),checks=checked,observation=_observation(record,approve),
        authority=text(authority,'independent whole-package designation authority'),
        note=text(note,'independent whole-package decision reason'))
    row.payload_checksum=checksum(row.payload)
    _state(record,body,[*rows,row]);row.save()
    record_event(record,'form1_package_'+role+'_decided',actor,note,
        dict(decision=str(row.public_id),decision_checksum=row.payload_checksum,package_checksum=record.payload_checksum))
    return row


def snapshot(record,actor,*,export=False):
    record=packages._read(record,actor,export=export)
    return _state(record,record.payload['assembly']['payload'],list(record.decisions.all()))
