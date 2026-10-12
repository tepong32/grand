"""Independent adoption of original joint certifications, without posting or signing."""
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import PureWindowsPath
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .access import department_for_user, has_explicit_permission
from .budget_actuals import money, MAX_EVIDENCE_BYTES, decision_snapshot
from .cash_classifications import checksum
from .models import BudgetSummaryScope as Scope, BudgetSummaryActual as Actual, Fund, LedgerAccount, AccountingAuditEvent

RECEIPTS = {'basic_rpt': 'Basic real property tax', 'business_tax': 'Business tax',
    'other_local_tax': 'Other local taxes', 'regulatory': 'Regulatory fees', 'service': 'Service/user charges',
    'enterprise': 'Economic enterprise receipts', 'other_local': 'Other local receipts',
    'nta': 'National Tax Allotment', 'gocc': 'GOCC shares', 'ecozone': 'Ecozone share',
    'evat': 'EVAT share', 'national_wealth': 'National wealth share', 'tobacco': 'Tobacco excise share',
    'philhealth': 'PhilHealth payments', 'interlocal': 'Inter-local transfer',
    'grant': 'Extraordinary receipts/grants/donations/aids', 'asset_sale': 'Sale of assets',
    'debt_security': 'Sale of other entities’ debt securities', 'loan_collection': 'Loan receivable collections',
    'loan': 'Loan proceeds', 'bond': 'Bond proceeds'}
EXPENDITURES = {'ps': 'Personal Services', 'mooe': 'Maintenance and Other Operating Expenses',
    'fe': 'Financial Expenses', 'co': 'Capital Outlays', 'spa': 'Special Purpose Appropriations'}


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return bool(actor.is_active and department_for_user(actor)
        and has_explicit_permission(actor, f'accounting.{action}_budget_summary_actuals')
        and (action in ('view', 'export') or not is_finance_uat_viewer(actor)))


def visible(actor):
    owner = department_for_user(actor)
    if not owner or not actor.is_active:
        raise PermissionDenied
    own = any(permitted(actor, action) for action in ('view', 'prepare', 'review', 'export'))
    from budget.access import has_budget_permission
    budget = any(has_budget_permission(actor, action) for action in
        ('prepare_budget_proposals', 'review_budget_proposals', 'view_budget_audit'))
    if not own and not budget:
        raise PermissionDenied
    query = Q(pk__in=[])
    if own:
        query |= Q(department_id=owner.pk)
        query |= Q(scope__treasury_department_id=owner.pk, status=Actual.APPROVED)
    if budget:
        query |= Q(scope__budget_department_id=owner.pk, status=Actual.APPROVED)
    return Actual.objects.filter(query).select_related('scope__fund').defer('evidence', 'trial_balance')


def text(value, name, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f'Retain {name} (up to {limit} characters).')
    return value.strip()


def document(upload, name):
    if upload is None or not hasattr(upload, 'read'):
        raise ValidationError(f'Attach the original {name}.')
    data = upload.read(MAX_EVIDENCE_BYTES + 1)
    if not data or len(data) > MAX_EVIDENCE_BYTES or not data.startswith((b'%PDF-', b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')):
        raise ValidationError(f'Use a PDF, PNG or JPEG for {name}, up to 8 MiB.')
    return data, {'name': PureWindowsPath(getattr(upload, 'name', name)).name[:180],
        'sha256': sha256(data).hexdigest()}


def normalize(owner_id, rows):
    if not isinstance(rows, list) or not rows:
        raise ValidationError('Enter itemized receipt and expenditure rows, including explicit certified zero where applicable.')
    accounts = {a.pk: a for a in LedgerAccount.objects.filter(department_id=owner_id)}
    result, seen = [], set()
    for supplied in rows:
        if not isinstance(supplied, dict):
            raise ValidationError('Each source row must be a structured item.')
        kind, category = supplied.get('kind'), supplied.get('category')
        choices = RECEIPTS if kind == 'receipt' else EXPENDITURES if kind == 'expenditure' else {}
        if category not in choices:
            raise ValidationError('Choose an explicit receipt category or expenditure class; subtotals are not leaf rows.')
        amount = money(supplied.get('amount'))
        reference = text(supplied.get('source_row'), 'a unique source page/row reference', 255)
        if reference.casefold() in seen:
            raise ValidationError('Do not enter the same source row twice.')
        seen.add(reference.casefold())
        account_id = supplied.get('account_id')
        account = accounts.get(account_id) if type(account_id) is int else None
        if not account and (account_id is not None or amount != 0):
            raise ValidationError('Use an account in this ledger; only an explicit certified zero may omit an account.')
        if '_csv_account_code' in supplied and supplied['_csv_account_code'].casefold() != (account.code.casefold() if account else ''):
            raise ValidationError('A CSV account changed before submission; reload the current source mapping.')
        result.append({'kind': kind, 'category': category, 'category_label': choices[category],
            'account_id': account.pk if account else None, 'account_code': account.code if account else '',
            'account_title': account.title if account else 'Explicit certified zero',
            'amount': str(amount), 'source_row': reference})
    if {r['kind'] for r in result} != {'receipt', 'expenditure'}:
        raise ValidationError('Retain both receipt and expenditure coverage; missing is not zero.')
    return result


def scope_snapshot(scope):
    return {key: getattr(scope, key) for key in ('department_id', 'budget_department_id',
        'treasury_department_id', 'fund_id', 'entity_key', 'entity_label')} | {
        'fund_code': scope.fund.code, 'period_start': scope.period_start.isoformat(), 'period_end': scope.period_end.isoformat()}


def verify(record):
    payload = record.payload
    identity = scope_snapshot(record.scope)
    identity.pop('fund_code')  # Historical labels survive later setup renaming.
    if (checksum(payload) != record.payload_checksum or
        {key: payload.get('scope', {}).get(key) for key in identity} != identity or
        record.department_id != record.scope.department_id or
        payload.get('version') != record.version or payload.get('base_version') != record.base_version or
        payload.get('prepared_by') != record.prepared_by_id or
        payload.get('prepared_by_label') != record.prepared_by_label or
        payload.get('prepared_at') != record.prepared_at.isoformat()):
        raise ValidationError('Retained joint summary identity or evidence changed.')
    for name in ('evidence', 'trial_balance'):
        if sha256(bytes(getattr(record, name))).hexdigest() != payload[name]['sha256']:
            raise ValidationError('Retained source document checksum differs.')
    if record.status != Actual.SUBMITTED:
        if (record.status not in (Actual.APPROVED, Actual.RETURNED) or not record.reviewed_by_id
            or record.reviewed_by_id == record.prepared_by_id or not record.reviewed_at
            or record.decision_checksum != checksum(decision_snapshot(record))):
            raise ValidationError('Retained independent adoption decision changed.')
    elif record.decision_checksum or record.reviewed_by_id or record.reviewed_at:
        raise ValidationError('A submitted version cannot contain an adoption decision.')
    return payload


def event(record, actor, action):
    AccountingAuditEvent.objects.create(department_id=record.department_id, department_label=record.department_label,
        actor_id=actor.pk, actor_label=(actor.get_full_name() or actor.username)[:160], action=action,
        snapshot={'summary_actual': str(record.public_id), 'scope': str(record.scope.public_id),
            'version': record.version, 'payload_checksum': record.payload_checksum, 'decision_checksum': record.decision_checksum})


@transaction.atomic(using='finance')
def propose(*, actor, fund_id, budget_department_id, treasury_department_id, entity_key, entity_label,
            period_start, period_end, evidence, trial_balance, rows, expected_latest,
            receipt_total, expenditure_total, **metadata):
    if not permitted(actor, 'prepare'):
        raise PermissionDenied
    from budget.models import BudgetCall
    from departments.models import Department
    owner = department_for_user(actor)
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=owner.pk).first()
    if not fund or not BudgetCall.objects.filter(department_id=budget_department_id,
        fiscal_year__department_id=owner.pk).exists() or not Department.objects.filter(pk=treasury_department_id).exists():
        raise ValidationError('Select this Accounting ledger, its linked Budget office and the designated Treasury office.')
    entity_key = text(entity_key, 'General Fund or enterprise identity', 80).lower()
    if entity_key != 'general' and not re.fullmatch(r'enterprise:[a-z0-9][a-z0-9_-]{0,60}', entity_key):
        raise ValidationError('Use general or enterprise:<stable-key> for the actual reporting entity.')
    entity_label = text(entity_label, 'the reporting entity designation', 255)
    if (type(period_start) is not date or type(period_end) is not date or
        period_start != date(period_end.year, 1, 1) or (period_end.month, period_end.day) not in ((6, 30), (12, 31))
        or period_end > timezone.localdate()):
        raise ValidationError('Select a completed calendar year or January–June period.')
    required = ('reference', 'issuer', 'scope_authority', 'coverage', 'trial_balance_reference',
        'reconciliation_basis', 'accountant_name', 'accountant_authority', 'treasurer_name', 'treasurer_authority', 'reason')
    retained = {key: text(metadata.get(key), key.replace('_', ' ')) for key in required}
    if retained['accountant_name'].casefold() == retained['treasurer_name'].casefold():
        raise ValidationError('Retain the distinct original Treasurer and Accountant certifications.')
    for role in ('accountant', 'treasurer'):
        day = metadata.get(role + '_certified_on')
        if type(day) is not date or not period_end <= day <= timezone.localdate():
            raise ValidationError('Each original certification date must cover this completed period and cannot be future dated.')
        retained[role + '_certified_on'] = day.isoformat()
    normalized = normalize(owner.pk, rows)
    totals = {'receipt': money(receipt_total), 'expenditure': money(expenditure_total)}
    for kind, total in totals.items():
        if sum((money(r['amount']) for r in normalized if r['kind'] == kind), Decimal('0.00')) != total:
            raise ValidationError(f'Itemized {kind} rows must reproduce the signed {kind} control total.')
    docs = {name: document(upload, name.replace('_', ' ')) for name, upload in
        (('evidence', evidence), ('trial_balance', trial_balance))}
    scope, _ = Scope.objects.get_or_create(department_id=owner.pk, fund=fund, entity_key=entity_key,
        period_start=period_start, period_end=period_end, defaults={'department_label': owner.name,
            'budget_department_id': budget_department_id, 'treasury_department_id': treasury_department_id, 'entity_label': entity_label})
    scope = Scope.objects.select_for_update().select_related('fund', 'current_version').get(pk=scope.pk)
    if (scope.budget_department_id, scope.treasury_department_id, scope.entity_label) != (budget_department_id, treasury_department_id, entity_label):
        raise ValidationError('Retain this scope’s original offices and entity designation; do not redirect historical evidence.')
    latest = scope.versions.aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or expected_latest != latest:
        raise ValidationError('A newer summary version exists; reload its history before submitting a successor.')
    now = timezone.now()
    payload = {'schema': 1, 'basis': 'historical-joint-actuals-adoption', 'scope': scope_snapshot(scope),
        **retained, 'rows': normalized, 'totals': {k: str(v) for k, v in totals.items()},
        **{name: data[1] for name, data in docs.items()}, 'prepared_by': actor.pk,
        'prepared_by_label': (actor.get_full_name() or actor.username)[:160], 'prepared_at': now.isoformat(),
        'version': latest + 1, 'base_version': scope.current_version.version if scope.current_version_id else 0}
    record = Actual.objects.create(scope=scope, department_id=owner.pk, department_label=owner.name,
        version=payload['version'], base_version=payload['base_version'], payload=payload, payload_checksum=checksum(payload),
        evidence=docs['evidence'][0], trial_balance=docs['trial_balance'][0], prepared_by_id=actor.pk,
        prepared_by_label=payload['prepared_by_label'], prepared_at=now)
    event(record, actor, 'summary_actual_submitted')
    return record


@transaction.atomic(using='finance')
def review(record, actor, *, approve, note, authority, verified_documents=False):
    if not permitted(actor, 'review'):
        raise PermissionDenied
    stored = Actual.objects.select_related('scope').get(pk=record.pk)
    if stored.department_id != department_for_user(actor).pk:
        raise PermissionDenied
    if type(approve) is not bool:
        raise ValidationError('Choose adopt or return.')
    Fund.objects.select_for_update().get(pk=stored.scope.fund_id)
    scope = Scope.objects.select_for_update().select_related('fund', 'current_version').get(pk=stored.scope_id)
    record = Actual.objects.select_for_update().get(pk=stored.pk)
    record.scope = scope
    payload = verify(record)
    if record.status != Actual.SUBMITTED or record.prepared_by_id == actor.pk:
        raise ValidationError('Only an independent reviewer can decide a submitted adoption.')
    note, authority = text(note, 'the independent review basis'), text(authority, 'adoption-review authority', 255)
    if approve:
        if verified_documents is not True:
            raise ValidationError('Verify both original certifications, source documents, coverage and trial-balance reconciliation.')
        if (record.version != scope.versions.aggregate(n=Max('version'))['n'] or
            record.base_version != (scope.current_version.version if scope.current_version_id else 0)):
            raise ValidationError('A newer submission or adoption exists; prepare or review its successor.')
        if (scope.fund.department_id != scope.department_id or payload['scope'] != scope_snapshot(scope)
            or normalize(record.department_id, payload['rows']) != payload['rows']):
            raise ValidationError('Source scope or account classifications changed; submit a successor.')
    record.status = Actual.APPROVED if approve else Actual.RETURNED
    record.reviewed_by_id, record.reviewed_by_label = actor.pk, (actor.get_full_name() or actor.username)[:160]
    record.reviewed_at, record.review_note, record.review_authority = timezone.now(), note, authority
    record.decision_checksum = checksum(decision_snapshot(record))
    record._decision_write = True
    record.save()
    if approve:
        scope.current_version = record
        scope._decision_write = True
        scope.save(update_fields=('current_version',))
    event(record, actor, 'summary_actual_adopted' if approve else 'summary_actual_returned')
    return record
