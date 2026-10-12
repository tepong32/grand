"""Explicit source choice over native certification or adopted external evidence."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting import budget_actuals as external
from accounting import budget_native_certifications as native
from accounting import budget_native_sources as sources
from accounting.cash_classifications import checksum
from accounting.models import BudgetActualScope, Fund, NativeBudgetStatement, ResponsibilityCenter
from .models import BudgetVersion
from .services import _require_action, record_event


def periods(version):
    year = version.fiscal_year.year
    return {'prior': (date(year - 2, 1, 1), date(year - 2, 12, 31)),
            'half': (date(year - 1, 1, 1), date(year - 1, 6, 30))}


def _scope(version, fund_id, center_id, prefix, *, allow_historical=False):
    if prefix not in periods(version):
        raise ValidationError('Select a valid comparison period.')
    proposed = version.lines.filter(fund_id=fund_id, responsibility_center_id=center_id).exists()
    if not proposed and not allow_historical:
        raise ValidationError('Select a fund, office and comparison period present in this proposal.')
    center = ResponsibilityCenter.objects.filter(pk=center_id, department_id=version.fiscal_year.department_id).first()
    if not center or not center.office_id:
        raise ValidationError('The proposal office must retain its Accounting ledger identity.')
    if not proposed:
        from .actuals_scopes import office_ids
        if center.office_id not in office_ids(version):
            raise ValidationError('Select historical evidence only for an office represented by this proposal.')
    return center, periods(version)[prefix]


def _external_scope(version, fund_id, center_id, start, end):
    return BudgetActualScope.objects.filter(department_id=version.fiscal_year.department_id,
        budget_department_id=version.department_id, fund_id=fund_id,
        responsibility_center_id=center_id, period_start=start, period_end=end,
        current_version__isnull=False).select_related('current_version', 'fund', 'responsibility_center').first()


def _source(version, fund_id, center_id, prefix, kind, source_id, *, complete_scope=False):
    """Caller holds this proposal and Fund boundary; return only the selected office."""
    center, (start, end) = _scope(version, fund_id, center_id, prefix, allow_historical=complete_scope)
    keys = {(fund_id, center_id, account_id) for account_id in version.lines.filter(
        fund_id=fund_id, responsibility_center_id=center_id).values_list('account_id', flat=True)}
    if kind == 'external':
        if complete_scope:
            scope = _external_scope(version, fund_id, center_id, start, end)
            if not scope or str(scope.current_version.public_id) != str(source_id):
                raise ValidationError('Select the current adopted external certificate for this office and period.')
            record = scope.current_version
            record.scope = scope
            payload = external.verify(record)
            # The retained certificate, not today's account catalog, defines its rows.
            keys = {(fund_id, center_id, row['account_id']) for row in payload['rows']}
        rows = [dict(row, account_id=key[0][2], source_kind='external') for key, row in external.planning_actuals(version, keys).items()
                if key[1] == prefix and row['certificate'] == str(source_id)]
        if not rows:
            raise ValidationError('Select the current adopted external certificate for this office and period.')
    elif kind == 'native':
        record = NativeBudgetStatement.objects.filter(public_id=source_id, department_id=version.fiscal_year.department_id,
            fund_id=fund_id, period_start=start, period_end=end, status=NativeBudgetStatement.CERTIFIED).first()
        latest = NativeBudgetStatement.objects.filter(fund_id=fund_id, period_start=start, period_end=end,
            status=NativeBudgetStatement.CERTIFIED).order_by('-version').values_list('pk', flat=True).first()
        if not record or record.pk != latest:
            raise ValidationError('Select the latest native certification for this fund and period.')
        payload = native.verify(record)
        current = sources._capture(version.fiscal_year.department_id, fund_id, start, end)
        if current['checksum'] != payload['source']['checksum']:
            raise ValidationError('Native source coverage changed; Accounting must prepare a fresh certification.')
        rows = []
        for row in payload['statement']['payload']['rows']:
            if row['center']['id'] != center_id or (not complete_scope and
                    (fund_id, center_id, row['account']['id']) not in keys):
                continue
            if row['office_id'] != center.office_id:
                raise ValidationError('Native office identity changed; reconcile the source before selection.')
            rows.append({'source_kind': 'native', 'account_id': row['account']['id'],
                'expense_class': row['expense_class'], 'amount': row['amount'],
                'certificate': str(record.public_id), 'version': record.version,
                'reference': payload['evidence_reference'], 'certified_on': record.decided_at.date().isoformat(),
                'accountant_name': record.decided_by_label, 'certification_authority': record.authority,
                'coverage': payload['coverage'], 'source_checksum': record.payload_checksum,
                'decision_checksum': record.decision_checksum,
                'ledger_source_checksum': payload['source']['checksum'],
                'scope': {'fund_id': fund_id, 'center_id': center_id, 'office_id': center.office_id,
                          'period_start': start.isoformat(), 'period_end': end.isoformat()},
                'components': row['components'], 'url': ''})
            if complete_scope:
                rows[-1].update(account_code=row['account']['code'], account_title=row['account']['title'])
        if not rows:
            raise ValidationError('No native certified rows match this proposal office; missing rows are not certified zero.')
    else:
        raise ValidationError('Choose native certification or adopted external evidence explicitly.')
    return sorted(rows, key=lambda row: (row['account_id'], row['expense_class']))


def _account_rows(rows):
    """One account total with every reviewed object retained, never last-row wins."""
    groups = {}
    for row in rows:
        groups.setdefault(row['account_id'], []).append(row)
    result = []
    for account_id in sorted(groups):
        objects = groups[account_id]
        if len(objects) == 1:
            result.append(objects[0])
            continue
        def identity(row):
            return {key: value for key, value in row.items() if key not in ('expense_class', 'amount', 'components')}
        common = identity(objects[0])
        if any(identity(row) != common for row in objects[1:]):
            raise ValidationError('Object rows must share the same retained certificate and account identity.')
        result.append({**common, 'expense_class': '',
            'expense_classes': sorted({row['expense_class'] for row in objects}),
            'amount': str(sum((Decimal(row['amount']) for row in objects), Decimal('0.00'))),
            'object_rows': objects})
    return result


@transaction.atomic(using='finance')
def select_source(*, version, actor, fund_id, center_id, prefix, kind, source_id, expected_state_version, reason,
                  expected_rows_checksum=None):
    version = BudgetVersion.objects.select_for_update().select_related('fiscal_year').get(pk=version.pk)
    _require_action(actor, version, 'prepare_budget_proposals')
    if version.status not in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
        raise ValidationError('Return the proposal before changing its certified source selection.')
    if type(fund_id) is not int or fund_id <= 0 or type(center_id) is not int or center_id <= 0:
        raise ValidationError('Select explicit fund and office identities from this proposal.')
    if type(expected_state_version) is not int or version.state_version != expected_state_version:
        raise ValidationError('The proposal changed; reload before selecting its actuals source.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Record why this certified source covers the proposal office and period.')
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=version.fiscal_year.department_id).first()
    if fund is None:
        raise PermissionDenied
    key = f'{fund_id}:{center_id}:{prefix}'
    before = version.actuals_source_selection.get(key)
    if kind == 'clear':
        if before is None:
            raise ValidationError('There is no explicit source choice to clear.')
        version.actuals_source_selection = {name: value for name, value in version.actuals_source_selection.items() if name != key}
        version.state_version += 1
        version.save(update_fields=('actuals_source_selection', 'state_version'))
        record_event(version, 'actuals_source_cleared', actor, reason.strip(),
            {'key': key, 'before': before, 'state_version': version.state_version})
        return version
    rows = _source(version, fund_id, center_id, prefix, kind, source_id, complete_scope=True)
    if expected_rows_checksum is not None and checksum(rows) != expected_rows_checksum:
        raise ValidationError('The displayed evidence changed; inspect the source again before selecting it.')
    selection = {'fund_id': fund_id, 'center_id': center_id, 'prefix': prefix, 'kind': kind,
        'coverage_mode': 'complete_scope',
        'fund_code': fund.code,
        'center_code': ResponsibilityCenter.objects.get(pk=center_id).code,
        'source_id': str(source_id), 'rows_checksum': checksum(rows), 'rows': rows,
        'selected_by_id': actor.pk, 'selected_at': timezone.now().isoformat(), 'reason': reason.strip()}
    version.actuals_source_selection = {**version.actuals_source_selection, key: selection}
    version.state_version += 1
    version.save(update_fields=('actuals_source_selection', 'state_version'))
    record_event(version, 'actuals_source_selected', actor, reason.strip(),
        {'key': key, 'before': before, 'after': selection, 'state_version': version.state_version})
    return version


@transaction.atomic(using='finance')
def preview_sources(version, actor, fund_id, center_id, prefix):
    """Authorized office-only candidates, coherent with the same mutation locks."""
    from .planning_context import can_read_context
    version = BudgetVersion.objects.select_for_update().select_related('fiscal_year').get(pk=version.pk)
    if not can_read_context(actor, version):
        raise PermissionDenied
    if not Fund.objects.select_for_update().filter(pk=fund_id,
            department_id=version.fiscal_year.department_id).exists():
        raise PermissionDenied
    center, (start, end) = _scope(version, fund_id, center_id, prefix, allow_historical=True)
    candidates, errors = [], []
    native_id = NativeBudgetStatement.objects.filter(fund_id=fund_id,
        department_id=version.fiscal_year.department_id, period_start=start, period_end=end,
        status=NativeBudgetStatement.CERTIFIED).order_by('-version').values_list('public_id', flat=True).first()
    identities = [('native', native_id)] if native_id else []
    try:
        scope = _external_scope(version, fund_id, center_id, start, end)
        if scope:
            identities.append(('external', scope.current_version.public_id))
    except ValidationError as exc:
        errors.append('External evidence: ' + ' '.join(exc.messages))
    for kind, source_id in identities:
        try:
            rows = _source(version, fund_id, center_id, prefix, kind, source_id, complete_scope=True)
        except ValidationError as exc:
            errors.append(kind.title() + ' evidence: ' + ' '.join(exc.messages))
        else:
            candidates.append({'kind': kind, 'source_id': str(source_id), 'rows': rows,
                               'rows_checksum': checksum(rows)})
    return version, candidates, errors


@transaction.atomic(using='finance')
def resolve(version, user, keys, existing):
    """Recheck explicit choices at draft display/submission; never add two routes."""
    from .planning_context import can_read_context
    if not can_read_context(user, version):
        raise PermissionDenied
    result = dict(existing)
    choices = version.actuals_source_selection
    # Sorted shared Fund locks serialize certifications and attribution changes.
    fund_ids = sorted({choice['fund_id'] for choice in choices.values()})
    owned = list(Fund.objects.select_for_update().filter(pk__in=fund_ids,
        department_id=version.fiscal_year.department_id).order_by('pk').values_list('pk', flat=True))
    if owned != fund_ids:
        raise PermissionDenied
    for choice in choices.values():
        mode = choice.get('coverage_mode')
        if mode not in (None, 'complete_scope'):
            raise ValidationError('Unknown retained actuals coverage mode; review the source choice.')
        rows = _source(version, choice['fund_id'], choice['center_id'], choice['prefix'], choice['kind'], choice['source_id'],
                       complete_scope=mode == 'complete_scope')
        if checksum(rows) != choice['rows_checksum'] or checksum(choice['rows']) != choice['rows_checksum']:
            raise ValidationError('A selected certified source changed. Review and explicitly select its current evidence.')
        for key in keys:
            if key[:2] == (choice['fund_id'], choice['center_id']):
                result.pop((key, choice['prefix']), None)
        for row in _account_rows(rows):
            key = (choice['fund_id'], choice['center_id'], row['account_id'])
            if key in keys:
                result[(key, choice['prefix'])] = {**row, 'selection': {name: choice[name]
                    for name in ('selected_by_id', 'selected_at', 'reason')}}
    return result
