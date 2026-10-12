"""Immutable whole-form preparations with separately authorized original source access."""
from copy import deepcopy
from hashlib import sha256
import uuid

from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from accounting.cash_classifications import checksum
from accounting.models import Fund
from accounting.summary_actuals import text
from .access import department_for_user,has_budget_permission
from .models import BudgetVersion,Form1SPAReview,Form1Package as Record,Form1PackageAttachment as Attachment,Form1PackageOffice
from . import form1_assembly as assembly,form1_spa_reviews as spa,form1_account_reviews as accounts
from . import form1_stocks as stocks,receipt_forecast_reviews as forecasts
from .services import record_event

RELATED=('proposal__fiscal_year','fund','spa_review__account_review__forecast',
    'spa_review__account_review__proposal__fiscal_year','spa_review__account_review__fund')


def offices(record,body):
    return {record.department_id,record.fund.department_id,
        *(row['scope']['treasury_department_id'] for row in body['members'])}


def verify_office_index(record,body):
    if set(record.office_index.values_list('department_id',flat=True)) != offices(record,body):
        raise ValidationError('The package office lookup differs from its original scope; resolve the index before retrieval.')


def _access(proposal,fund,body,actor,action):
    from vouchers.roles import is_finance_uat_viewer
    owner=department_for_user(actor)
    offices={proposal.department_id,fund.department_id}
    offices.update(row['scope']['treasury_department_id'] for row in body['members'])
    if (action not in ('prepare','view','export') or not owner or not actor.is_active
        or owner.pk not in ({proposal.department_id} if action=='prepare' else offices)
        or fund.department_id!=proposal.fiscal_year.department_id
        or not has_budget_permission(actor,action+'_form1_packages')
        or action=='prepare' and is_finance_uat_viewer(actor)):
        raise PermissionDenied('Use this package’s original office and explicit preparation/read/export permission.')


def manifest(envelope):
    return _manifest(assembly.verify(envelope))


def _manifest(body):
    """Derive attachment metadata from an already reproduced assembly."""
    ph=body['philhealth_source']['payload']; result={}
    for key,metadata in ph['documents'].items():
        if metadata is not None:result['philhealth:'+key]=deepcopy(metadata)
    stock=ph['inventory']['payload']['stock']['payload']
    for row in stock['selections']:
        for choice in row['opening'].values():
            if choice['kind']=='forecast':
                source=choice['source'];result['cash:'+source['checksum']]=deepcopy(source['payload']['evidence'])
    return result


def _bytes(evidence,documents):
    if not isinstance(evidence,dict) or not isinstance(documents,dict):
        raise ValidationError('Retain original cash worksheets and PhilHealth documents.')
    return {**{'cash:'+key:data for key,data in evidence.items()},
        **{'philhealth:'+key:data for key,data in documents.items()}}


def _check_bytes(expected,data):
    if set(expected)!=set(data) or any(not isinstance(data[key],bytes)
        or sha256(data[key]).hexdigest()!=metadata['sha256'] for key,metadata in expected.items()):
        raise ValidationError('Retain exactly the original whole-package attachment bytes.')


def verify(record,attachments=None,*,_assemblies=None):
    try:
        payload=record.payload
        if checksum(payload)!=record.payload_checksum:
            raise ValidationError('Retain the original whole package checksum.')
        # Request-local arithmetic cache only. Hash the actual complete envelope,
        # not its claimed checksum; each root identity and attachment is checked
        # below independently. This cache never supplies source authorization.
        key=checksum(payload['assembly']) if _assemblies is not None else None
        if _assemblies is not None and key in _assemblies:
            body=_assemblies[key]
        else:
            body=assembly.verify(payload['assembly'])
            if _assemblies is not None:_assemblies[key]=body
        identity=dict(public_id=str(record.public_id),proposal=str(record.proposal.public_id),
            department_id=record.department_id,accounting_department_id=record.fund.department_id,
            fund_id=record.fund_id,spa_review=str(record.spa_review.public_id),version=record.version,
            prepared_by=record.prepared_by_id,prepared_at=record.prepared_at.isoformat())
        original=body['spa_source']['payload']['spa_review']['payload']['identity']
        if (set(payload)!={'schema','identity','assembly','attachments','reference'} or type(payload['schema']) is not int
            or payload['schema']!=1 or payload['identity']!=identity
            or record.department_id!=record.proposal.department_id
            or record.fund.department_id!=record.proposal.fiscal_year.department_id
            or record.spa_review.proposal_id!=record.proposal_id or record.spa_review.fund_id!=record.fund_id
            or any(original[key]!=identity[key] for key in ('proposal','department_id','accounting_department_id','fund_id'))
            or original['public_id']!=identity['spa_review'] or type(record.version)is not int or record.version<=0
            or type(record.prepared_by_id)is not int or record.prepared_by_id<=0
            or timezone.is_naive(record.prepared_at) or payload['attachments']!=_manifest(body)):
            raise ValidationError('Retain the original whole package identity, source scope and attachment manifest.')
        text(payload['reference'],'whole package preparation reference')
        rows=list(record.attachments.all()) if attachments is None else list(attachments)
        if len({row.key for row in rows})!=len(rows) or any(row.package_id!=record.pk for row in rows):
            raise ValidationError('Retain each original attachment under its own package.')
        _check_bytes(payload['attachments'],{row.key:bytes(row.data) for row in rows})
        return body
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid original whole Form 1 preparation.') from error


def _sources(record,actor,action):
    """Package-only projections; no generic source endpoint or Budget editing grant."""
    for name in ('form1_spa_reviews','form1_account_reviews','budget_receipt_forecasts'):
        if not has_budget_permission(actor,action+'_'+name):
            raise PermissionDenied('This package also requires explicit original planning/account/SPA source permission.')
    source=Form1SPAReview.objects.select_related(*spa.RELATED).prefetch_related('decisions').get(pk=record.spa_review_id)
    spa.verify(source);accounts._sources(source.account_review,actor,action)
    expected=record.payload['assembly']['payload']['spa_source']['payload']['spa_review']
    if spa._snapshot(source)!=expected:
        raise ValidationError('Retain the exact original SPA model, decisions and authority bytes.')
    stock=record.payload['assembly']['payload']['philhealth_source']['payload']['inventory']['payload']['stock']['payload']
    forecast=source.account_review.forecast
    if forecasts._snapshot(forecast)!=stock['flow']['payload']['sources']['forecast']:
        raise ValidationError('Retain the exact original forecast model and whole flow source.')
    evidence={row.key[5:]:bytes(row.data) for row in record.attachments.all() if row.key.startswith('cash:')}
    stocks._authorize(stock['selections'],actor,evidence,current=False,export=action=='export')


@transaction.atomic(using='finance')
def prepare(*,spa_review,envelope,actor,evidence,documents,reference,expected_latest):
    proposal=BudgetVersion.objects.select_for_update().get(pk=spa_review.proposal_id)
    fund=Fund.objects.select_for_update().get(pk=spa_review.fund_id)
    body=assembly.verify(envelope);_access(proposal,fund,body,actor,'prepare')
    source=Form1SPAReview.objects.select_related(*spa.RELATED).get(pk=spa_review.pk,proposal=proposal,fund=fund)
    observed=assembly.capture(spa_review=source,philhealth_source=body['philhealth_source'],
        actor=actor,evidence=evidence,documents=documents)
    if observed!=envelope:raise ValidationError('Retain the exact current whole Form 1 source assembly.')
    latest=Record.objects.filter(proposal=proposal,fund=fund).aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest)is not int or expected_latest!=latest:
        raise ValidationError('A newer whole Form 1 preparation exists; reload its history.')
    data=_bytes(evidence,documents);expected=manifest(observed);_check_bytes(expected,data)
    now=timezone.now();public_id=uuid.uuid4()
    record=Record(public_id=public_id,proposal=proposal,fund=fund,spa_review=source,version=latest+1,
        department_id=proposal.department_id,department_label=proposal.department_label,prepared_by_id=actor.pk,prepared_at=now)
    identity=dict(public_id=str(public_id),proposal=str(proposal.public_id),department_id=proposal.department_id,
        accounting_department_id=fund.department_id,fund_id=fund.pk,spa_review=str(source.public_id),
        version=latest+1,prepared_by=actor.pk,prepared_at=now.isoformat())
    record.payload=dict(schema=1,identity=identity,assembly=deepcopy(observed),attachments=expected,
        reference=text(reference,'whole package preparation reference'))
    record.payload_checksum=checksum(record.payload)
    record.save()
    Form1PackageOffice.objects.bulk_create([Form1PackageOffice(package=record,department_id=office)
        for office in sorted(offices(record,body))])
    for key,content in data.items():Attachment.objects.create(package=record,key=key,data=content)
    verify(record);_sources(record,actor,'view')
    record_event(record,'form1_package_prepared',actor,reference,dict(payload_checksum=record.payload_checksum))
    return record


def _read(record,actor,*,export=False):
    record=Record.objects.select_related(*RELATED).prefetch_related('attachments').get(pk=record.pk)
    body=verify(record);action='export' if export else 'view'
    _access(record.proposal,record.fund,body,actor,action);_sources(record,actor,action)
    return record


def snapshot(record,actor,*,export=False):
    record=_read(record,actor,export=export)
    return dict(payload=deepcopy(record.payload),payload_checksum=record.payload_checksum,
        independently_reviewed=False,form_issued=False,cash_available=False)


def _current(record,actor):
    """Internal observer after original source authorization and proposal/Fund locks."""
    if (Record.objects.filter(proposal_id=record.proposal_id,fund_id=record.fund_id)
        .aggregate(n=Max('version'))['n']!=record.version):
        return False
    source=record.spa_review
    if (source.status!='approved' or Form1SPAReview.objects.filter(proposal_id=record.proposal_id,fund_id=record.fund_id)
        .aggregate(n=Max('version'))['n']!=source.version):
        return False
    try:
        # Original source visibility was checked for this actor above. The internal
        # observers do not grant generic SPA/Budget editing or borrow a maker's actor.
        spa._current(source,actor)
        stock=record.payload['assembly']['payload']['philhealth_source']['payload']['inventory']['payload']['stock']['payload']
        evidence={row.key[5:]:bytes(row.data) for row in record.attachments.all() if row.key.startswith('cash:')}
        stocks._authorize(stock['selections'],actor,evidence,current=True)
    except ValidationError:
        return False
    return True


@transaction.atomic(using='finance')
def is_current(record,actor):
    """Authorized observation; not completeness, approval or a posting freeze."""
    proposal=BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund=Fund.objects.select_for_update().get(pk=record.fund_id)
    record=_read(record,actor)
    if record.proposal_id!=proposal.pk or record.fund_id!=fund.pk:return False
    return _current(record,actor)


def attachment_bytes(record,actor,key):
    retained=snapshot(record,actor,export=True)
    row=Attachment.objects.filter(package_id=record.pk,key=key).first()
    if not row:raise ValidationError('Select an original attachment from this package.')
    data=bytes(row.data)
    if sha256(data).hexdigest()!=retained['payload']['attachments'][key]['sha256']:
        raise ValidationError('Original attachment bytes changed after verification.')
    return data
