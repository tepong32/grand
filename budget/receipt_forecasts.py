"""Explicit Form 1 receipt estimate partitions; no certification or cash authority."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from accounting.models import Fund, LedgerAccount
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import RECEIPTS, text
from .access import department_for_user
from .models import BudgetVersion, BudgetAuditEvent, BudgetSummaryReconciliation
from . import office_forms, resource_context, summary_reconciliations, summary_sources

COMPONENT_FIELDS = {'key', 'source_id', 'amount', 'disposition', 'category',
    'account_id', 'coverage_key', 'overlap_of', 'basis'}


def amount(value):
    result = money(value)
    if result < 0:
        raise ValidationError('Receipt forecasts require nonnegative amounts; do not copy signed actuals as estimates.')
    return result


def key(value, label):
    value = text(value, label, 160)
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.:-]{0,159}', value):
        raise ValidationError('Use explicit lowercase source/component/coverage keys without spaces.')
    return value


def _resource_node(version):
    context = version.planning_context_snapshot or {}
    submitted = BudgetAuditEvent.objects.filter(target_id=str(version.public_id), action='submit').order_by('-pk').first()
    resources = context.get('resources')
    if (not submitted or submitted.snapshot.get('planning_context') != context or resources is None):
        raise ValidationError('Retain the original submitted resource evidence for every consolidation source.')
    return dict(proposal=str(version.public_id), department_id=version.department_id,
        fiscal_year_id=version.fiscal_year_id, resources=deepcopy(resources))


def _roots(nodes, primary):
    """Follow retained resource identities, including nested consolidation copies."""
    root_node = nodes[primary]
    rows = root_node['resources']['rows']
    result = {}
    for row in rows:
        proposal, identity, visited, path = primary, row['id'], set(), []
        while True:
            marker = (proposal, identity)
            if marker in visited:
                raise ValidationError('Resource consolidation lineage contains a cycle.')
            visited.add(marker); path.append(dict(proposal=proposal, resource_id=identity))
            node = nodes[proposal]
            if (node['proposal'] != proposal or node['department_id'] != root_node['department_id']
                or node['fiscal_year_id'] != root_node['fiscal_year_id']
                or node['resources']['budget_year'] != root_node['resources']['budget_year']):
                raise ValidationError('Every resource origin must retain the same Budget owner and fiscal year.')
            matches = [item for item in node['resources']['rows'] if item['id']==identity]
            origins = [item for item in node['resources']['origins'] if item['target_resource_id']==identity]
            if len(matches)!=1 or len(origins)>1:
                raise ValidationError('Retain one exact resource and at most one original consolidation link.')
            current = matches[0]
            if not origins:
                result[str(row['id'])] = dict(proposal=proposal, resource_id=identity,
                    resource=deepcopy(current), path=path)
                break
            origin = origins[0]
            original = origin['source_resource']
            if ({name:value for name,value in current.items() if name!='id'} !=
                {name:value for name,value in original.items() if name!='id'}):
                raise ValidationError('A copied resource no longer reproduces its original amount, scope and basis.')
            proposal, identity = origin['source_proposal'], original['id']
            original_rows = nodes[proposal]['resources']['rows']
            if original not in original_rows:
                raise ValidationError('Retain the exact original source resource, not a detached origin label.')
    return result


@transaction.atomic(using='finance')
def capture(*, reconciliation, actor):
    """Capture trusted planning sources; never expose the parent actuals ledger here."""
    proposal = BudgetVersion.objects.select_for_update().get(pk=reconciliation.proposal_id)
    owner = department_for_user(actor)
    if not actor.is_active or not owner or owner.pk != proposal.department_id:
        raise PermissionDenied
    context = office_forms.frozen_context(proposal, actor)
    return _capture_sources(proposal, reconciliation, actor, context)


def _capture_sources(proposal, reconciliation, actor, context):
    """Internal observation after caller authorization; never a public access route."""
    record = BudgetSummaryReconciliation.objects.get(pk=reconciliation.pk, proposal=proposal)
    parent = summary_reconciliations.verify(record)
    summary_sources.require_visible(parent, actor)
    latest = proposal.summary_reconciliations.filter(fund_id=record.fund_id,
        entity_key=record.entity_key).aggregate(n=Max('version'))['n']
    if record.status!='accepted' or latest!=record.version:
        raise ValidationError('Select the latest independently accepted office reconciliation for this forecast scope.')
    original_scope = parent['actuals']['half']['payload']['scope']
    fund = Fund.objects.select_for_update().get(pk=record.fund_id)
    if (fund.department_id != proposal.fiscal_year.department_id
        or original_scope['department_id'] != fund.department_id):
        raise ValidationError('The selected forecast Fund must retain its original Accounting owner.')
    resources = resource_context.require_retained(proposal)
    primary = str(proposal.public_id)
    nodes = {primary: _resource_node(proposal)}
    if nodes[primary]['resources'] != resources or resources != context['resources']:
        raise ValidationError('The forecast must reuse the exact submitted resource cohort.')
    pending = [origin['source_proposal'] for origin in resources['origins']]
    while pending:
        identity = pending.pop()
        if identity in nodes:
            continue
        source = BudgetVersion.objects.filter(public_id=identity, department_id=proposal.department_id,
            fiscal_year_id=proposal.fiscal_year_id).first()
        if not source:
            raise ValidationError('A retained resource origin is outside this Budget owner/fiscal year.')
        nodes[identity] = _resource_node(source)
        pending.extend(origin['source_proposal'] for origin in nodes[identity]['resources']['origins'])
    account_rows = [dict(id=item.pk, department_id=item.department_id, code=item.code, title=item.title,
        government_account_code=item.government_account_code, account_type=item.account_type,
        normal_balance=item.normal_balance, is_active=item.is_active, allow_posting=item.allow_posting,
        effective_from=item.effective_from.isoformat() if item.effective_from else None,
        effective_to=item.effective_to.isoformat() if item.effective_to else None)
        for item in LedgerAccount.objects.filter(department_id=fund.department_id).order_by('pk')]
    scope = dict(budget_department_id=proposal.department_id, accounting_department_id=fund.department_id,
        treasury_department_id=original_scope['treasury_department_id'], fund_id=fund.pk, fund_code=fund.code,
        budget_year=proposal.fiscal_year.year, entity_key=record.entity_key,
        entity_label=original_scope['entity_label'])
    payload = dict(schema=1, kind='budget_receipt_forecast_sources', scope=scope,
        proposal=dict(public_id=primary, version=proposal.version, state_version=proposal.state_version,
            fiscal_year_id=proposal.fiscal_year_id, context_checksum=checksum(context)),
        reconciliation=dict(public_id=str(record.public_id), version=record.version,
            payload_checksum=record.payload_checksum, decision=summary_reconciliations.decision(record),
            decision_checksum=record.decision_checksum, prepared_by=record.prepared_by_id),
        resources=deepcopy(resources), resource_nodes=nodes, resource_roots=_roots(nodes, primary),
        accounts=account_rows)
    return dict(payload=payload, checksum=checksum(payload), observed_on=timezone.localdate().isoformat())


def verify_capture(captured):
    """Pure integrity of trusted captures; checksums never authenticate client input."""
    try:
        body = captured['payload']; scope = body['scope']; primary = body['proposal']['public_id']
        review = body['reconciliation']['decision']
        if (body['schema']!=1 or body['kind']!='budget_receipt_forecast_sources'
            or checksum(body)!=captured['checksum'] or type(scope['budget_year']) is not int or scope['budget_year']<3
            or body['resource_nodes'][primary]['resources']!=body['resources']
            or body['resources']['budget_year']!=scope['budget_year']
            or body['resources']['certified_receipts'] is not False or body['resources']['cash_available'] is not False
            or body['resource_roots']!=_roots(body['resource_nodes'],primary)
            or body['resource_nodes'][primary]['department_id']!=scope['budget_department_id']
            or body['resource_nodes'][primary]['fiscal_year_id']!=body['proposal']['fiscal_year_id']
            or checksum(review)!=body['reconciliation']['decision_checksum'] or review['status']!='accepted'
            or review['payload_checksum']!=body['reconciliation']['payload_checksum']
            or not review['reviewed_by'] or review['reviewed_by']==body['reconciliation']['prepared_by']
            or not review['reviewed_at'] or not review['authority'] or not review['note']):
            raise ValidationError('Retain complete accepted scope and exact resource lineage evidence.')
        date.fromisoformat(captured['observed_on'])
        seen = set()
        for row in body['accounts']:
            if (type(row['id']) is not int or row['id']<=0 or row['id'] in seen
                or row['department_id']!=scope['accounting_department_id']):
                raise ValidationError('Retain each original Accounting account identity once.')
            seen.add(row['id'])
        return body
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
        raise ValidationError('Invalid retained receipt forecast source capture.') from error


def _accounts(captured, column):
    scope = captured['scope']; year = scope['budget_year']-(column=='half_estimate')
    start, end = (date(year,7,1),date(year,12,31)) if column=='half_estimate' else (date(year,1,1),date(year,12,31))
    return {row['id']:row for row in captured['accounts'] if row['is_active'] is True and row['allow_posting'] is True
        and row['account_type'] in ('asset','liability','revenue')
        and (not row['effective_from'] or date.fromisoformat(row['effective_from'])<=end)
        and (not row['effective_to'] or date.fromisoformat(row['effective_to'])>=start)}


def _components(body, sources, supplied, column):
    if not isinstance(supplied,list):
        raise ValidationError('Supply explicit source components; do not infer classifications.')
    by_source = {row['id']:row for row in sources}
    if len(by_source)!=len(sources):
        raise ValidationError('Retain each forecast source identity once.')
    accounts = _accounts(body,column); rows = []; seen=set(); seen_sources=set()
    allocated = {identity:Decimal('0.00') for identity in by_source}
    for item in supplied:
        if not isinstance(item,dict) or set(item)!=COMPONENT_FIELDS:
            raise ValidationError('Retain exact component, source, mapping, overlap and basis fields.')
        identity = key(item['key'],'component identity')
        source_id = item['source_id']
        if identity in seen or type(source_id) is not str or source_id not in by_source:
            raise ValidationError('Select distinct component keys and exact retained source identities.')
        seen.add(identity); seen_sources.add(source_id)
        value=amount(item['amount']); allocated[source_id]+=value
        disposition=item['disposition']; category=item['category']; account_id=item['account_id']
        coverage_key=item['coverage_key']; overlap_of=item['overlap_of']
        if (disposition not in ('include','overlap','exclude','unresolved') or not isinstance(category,str)
            or (category and category not in RECEIPTS) or not isinstance(coverage_key,str)
            or not isinstance(overlap_of,str) or (account_id is not None and type(account_id) is not int)):
            raise ValidationError('Choose explicit valid mapping/disposition values.')
        if disposition in ('include','overlap'):
            if (not category or account_id not in accounts
                or by_source[source_id]['fund_id']!=body['scope']['fund_id']):
                raise ValidationError('Included/overlapping sources require this Fund, category and applicable original account.')
            coverage_key=key(coverage_key,'the funding coverage identity')
            if disposition=='include' and overlap_of:
                raise ValidationError('An included component cannot also be an overlap.')
            if disposition=='overlap': overlap_of=key(overlap_of,'the exact included overlap anchor')
        elif disposition=='exclude':
            if category or account_id is not None or coverage_key or overlap_of:
                raise ValidationError('An exclusion retains its basis without pretending to be included receipt coverage.')
        elif overlap_of or (account_id is not None and account_id not in accounts):
            raise ValidationError('Keep unresolved overlap/account choices explicit and unclaimed.')
        row=dict(key=identity,source_id=source_id,amount=str(value),disposition=disposition,
            category=category,account_id=account_id,coverage_key=coverage_key,overlap_of=overlap_of,
            basis=text(item['basis'],'component mapping/overlap basis',2000),
            account=deepcopy(accounts[account_id]) if account_id is not None else None)
        rows.append(row)
    if seen_sources!=set(by_source) or any(allocated[row['id']]!=amount(row['amount']) for row in sources):
        raise ValidationError('Partition every retained source amount exactly, including zero, exclusions and overlaps.')
    rows.sort(key=lambda row:row['key']); by_key={row['key']:row for row in rows}
    included={}; root_used={}; issues=[]
    for row in rows:
        if row['disposition']=='include':
            if row['coverage_key'] in included:
                raise ValidationError('Duplicate funding coverage must use an explicit exact overlap anchor, not two inclusions.')
            included[row['coverage_key']]=row
            root=by_source[row['source_id']]['root_key']
            root_used[root]=root_used.get(root,Decimal('0.00'))+amount(row['amount'])
        elif row['disposition']=='unresolved':
            issues.append(dict(kind='unresolved_component',column=column,component=row['key']))
    for row in rows:
        if row['disposition']=='overlap':
            anchor=by_key.get(row['overlap_of'])
            if (not anchor or anchor['disposition']!='include' or anchor['source_id']==row['source_id']
                or any(anchor[name]!=row[name] for name in ('amount','coverage_key','category','account_id'))):
                raise ValidationError('An overlap must mirror one included component on another source; no chains or partial guesses.')
    for source in sources:
        if root_used.get(source['root_key'],Decimal('0.00'))>amount(source['root_amount']):
            raise ValidationError('Copied resource sources cannot include more than their original retained resource amount.')
    controls={name:str(sum((amount(row['amount']) for row in rows if row['disposition']==name),Decimal('0.00')))
        for name in ('include','overlap','exclude','unresolved')}
    controls.update(source_total=str(sum((amount(row['amount']) for row in sources),Decimal('0.00'))),
        partition_total=str(sum((amount(row['amount']) for row in rows),Decimal('0.00'))))
    return rows, controls, issues


def propose(captured, *, half_sources, half_components, proposed_components, coverage):
    """Pure proposed arithmetic over complete sources; not a reviewed forecast."""
    try:
        return _propose(captured,half_sources,half_components,proposed_components,coverage)
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid receipt forecast proposal structure.') from error


def _propose(captured, half_sources, half_components, proposed_components, coverage):
    body=verify_capture(captured)
    if not isinstance(half_sources,list) or not isinstance(coverage,dict) or set(coverage)!= {'half_estimate','proposed'}:
        raise ValidationError('Retain second-half sources and both explicit leaf-coverage schedules.')
    halves=[]; seen=set()
    for source in half_sources:
        if not isinstance(source,dict) or set(source)!= {'id','amount','reference','as_of','basis'}:
            raise ValidationError('Retain each dated second-half source amount and its original forecast basis.')
        identity=key(source['id'],'second-half source identity')
        as_of=date.fromisoformat(source['as_of'])
        if identity in seen or as_of>date.fromisoformat(captured['observed_on']):
            raise ValidationError('Use distinct dated forecast sources without future observations.')
        seen.add(identity)
        halves.append(dict(id=identity,amount=str(amount(source['amount'])),fund_id=body['scope']['fund_id'],
            reference=text(source['reference'],'forecast worksheet reference',255),as_of=as_of.isoformat(),
            basis=text(source['basis'],'dated second-half estimate basis',2000),
            root_key='half:'+identity,root_amount=str(amount(source['amount']))))
    proposed=[]
    for source in body['resources']['rows']:
        root=body['resource_roots'][str(source['id'])]
        proposed.append(dict(id=str(source['id']),amount=source['amount'],fund_id=source['funding_source']['fund_id'],
            root_key=root['proposal']+':'+str(root['resource_id']),root_amount=root['resource']['amount']))
    columns={}; all_issues=[]
    for column,sources,components in (('half_estimate',halves,half_components),('proposed',proposed,proposed_components)):
        rows,controls,issues=_components(body,sources,components,column)
        declarations=coverage[column]
        if not isinstance(declarations,list) or len(declarations)!=len(RECEIPTS):
            raise ValidationError('Declare every required receipt leaf once for each forecast column.')
        categories={}; declared=set()
        for item in declarations:
            if not isinstance(item,dict) or set(item)!= {'category','amount','coverage','basis'}:
                raise ValidationError('Retain each category amount, coverage state and evidence basis.')
            category=item['category']
            if not isinstance(category,str) or category not in RECEIPTS or category in declared:
                raise ValidationError('Use each receipt leaf once, without overlapping subtotals.')
            declared.add(category)
            members=[row for row in rows if row['disposition']=='include' and row['category']==category]
            value=sum((amount(row['amount']) for row in members),Decimal('0.00'))
            if amount(item['amount'])!=value or item['coverage'] not in ('estimate','no_estimate','unresolved'):
                raise ValidationError('Declared category amounts must reproduce included source components.')
            expected='estimate' if members else 'no_estimate'
            if item['coverage']!='unresolved' and item['coverage']!=expected:
                raise ValidationError('Coverage must distinguish a real estimate, including zero, from no estimate.')
            if item['coverage']=='unresolved': issues.append(dict(kind='unresolved_category',column=column,category=category))
            categories[category]=dict(category=category,amount=str(value),coverage=item['coverage'],
                basis=text(item['basis'],'complete category estimate coverage basis',2000))
        columns[column]=dict(sources=sources,components=rows,controls=controls,
            categories=[categories[category] for category in sorted(categories)],
            diagnostic_total=controls['include'],official_total=None,issues=issues)
        all_issues.extend(issues)
    payload=dict(schema=1,kind='budget_receipt_forecast_proposal',capture=deepcopy(captured),columns=columns,
        classification_complete=not all_issues,issues=all_issues,review_status='not_reviewed',
        certification_status='not_certified',actual_receipts=False,cash_available=False)
    return dict(payload=payload,checksum=checksum(payload))


def verify(proposal):
    try:
        body=proposal['payload']; columns=body['columns']
        halves=[{name:row[name] for name in ('id','amount','reference','as_of','basis')}
            for row in columns['half_estimate']['sources']]
        components={column:[{name:row[name] for name in COMPONENT_FIELDS} for row in columns[column]['components']]
            for column in ('half_estimate','proposed')}
        reproduced=propose(body['capture'],half_sources=halves,
            half_components=components['half_estimate'],proposed_components=components['proposed'],
            coverage={column:columns[column]['categories'] for column in ('half_estimate','proposed')})
        if reproduced!=proposal:
            raise ValidationError('Receipt forecast proposal does not reproduce its complete source partitions and controls.')
        return body
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid detached receipt forecast proposal.') from error
