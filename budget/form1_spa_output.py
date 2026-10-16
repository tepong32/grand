"""Pure exact-source flow/SPA draft composition; no authority or currentness grant."""
from copy import deepcopy
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware
from reportlab.platypus import Spacer, KeepTogether
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import text
from . import form1_flow_output as flows, form1_spa_proposals as subdivisions
from . import form1_itemization as itemization
from .form1_integrity import operation

SOURCE_COLUMNS=('prior_amount','half_amount','estimate','proposed')
DECISION_FIELDS={'review','payload_checksum','role','approve','actor_id','actor_department_id',
    'treatment_verified','decided_at','authority','note','checksum'}


def _date(value):
    result=parse_datetime(value)
    if result is None or not is_aware(result):
        raise ValidationError('Retain original aware preparation and decision dates.')
    return result


def _positive(value):
    return type(value) is int and value>0


def _uuid(value):
    if not isinstance(value,str) or str(UUID(value))!=value:
        raise ValidationError('Retain the original public source identity.')


@operation
def verify_snapshot(snapshot):
    """Structural checks after the public service verifies model/attachment access.

    Checksums do not authorize a source or establish authenticity of unattached
    documents. Export callers must use the existing service's verified snapshot.
    """
    return _verify_snapshot(snapshot)[0]


def _verify_snapshot(snapshot):
    """Retain the flow reproduced during this same snapshot verification."""
    try:
        if set(snapshot)!={'payload','payload_checksum','status','decisions',
            'independently_reviewed','form_issued','cash_available'}:
            raise ValidationError('Retain the whole original SPA snapshot.')
        payload=snapshot['payload']; identity=payload['identity']
        if (set(payload)!={'schema','identity','source_account_review','draft','reference','evidence'}
            or type(payload['schema']) is not int or payload['schema']!=1 or checksum(payload)!=snapshot['payload_checksum']
            or snapshot['form_issued'] is not False or snapshot['cash_available'] is not False):
            raise ValidationError('Retain original SPA evidence without granting issuance or cash.')
        expected={'public_id','proposal','department_id','accounting_department_id','fund_id',
            'account_review','version','prepared_by','prepared_at'}
        if set(identity)!=expected or any(not _positive(identity[key]) for key in (
            'department_id','accounting_department_id','fund_id','version','prepared_by')):
            raise ValidationError('Retain the original SPA version, preparer and owner scopes.')
        for key in ('public_id','proposal','account_review'): _uuid(identity[key])
        prepared=_date(identity['prepared_at'])
        original=payload['source_account_review']; source=original['payload']['identity']
        flow=flows.package(original)
        if (original['decision']['status']!='approved'
            or original['independently_reviewed'] is not True or original['code_authority_approved'] is not True
            or source['public_id']!=identity['account_review']
            or any(source[key]!=identity[key] for key in (
                'proposal','department_id','accounting_department_id','fund_id'))
            or any(not _positive(source[key]) for key in ('department_id','accounting_department_id','fund_id','version','prepared_by'))
            or not _positive(original['decision']['reviewed_by'])
            or original['decision']['reviewed_by']==source['prepared_by']
            or _date(original['decision']['reviewed_at'])<_date(source['prepared_at'])
            or prepared<_date(original['decision']['reviewed_at'])):
            raise ValidationError('Join the exact original independently approved account package and owners.')
        body=subdivisions.verify(payload['draft'])
        if body['source_draft']!=original['payload']['draft']:
            raise ValidationError('SPA treatment must use the exact original reporting-account draft.')
        text(payload['reference'],'original SPA authority reference')
        text(payload['evidence']['name'],'original SPA evidence name',180)
        rows=snapshot['decisions']
        if not isinstance(rows,list) or len(rows)>2:
            raise ValidationError('Retain at most one original decision per SPA role.')
        roles=set(); actors=set(); returned=[]
        for row in rows:
            if (not isinstance(row,dict) or set(row)!=DECISION_FIELDS or row['role'] not in ('budget','accounting')
                or row['review']!=identity['public_id'] or row['payload_checksum']!=snapshot['payload_checksum']
                or row['role'] in roles or row['actor_id'] in actors or not _positive(row['actor_id'])
                or not _positive(row['actor_department_id'])
                or row['actor_id']==identity['prepared_by'] or type(row['approve']) is not bool
                or type(row['treatment_verified']) is not bool
                or row['actor_department_id']!=identity['department_id' if row['role']=='budget' else 'accounting_department_id']
                or _date(row['decided_at'])<prepared
                or checksum({key:value for key,value in row.items() if key!='checksum'})!=row['checksum']
                or (row['approve'] and (not row['treatment_verified'] or not body['spa_partition_complete']))):
                raise ValidationError('Retain distinct original office decisions over complete verified SPA treatment.')
            text(row['authority'],'SPA designation authority'); text(row['note'],'SPA decision note')
            roles.add(row['role']); actors.add(row['actor_id'])
            if not row['approve']: returned.append(_date(row['decided_at']))
        status='returned' if returned else 'approved' if len(rows)==2 else 'partially_approved' if rows else 'prepared'
        if (snapshot['status']!=status or snapshot['independently_reviewed'] is not (status=='approved')
            or len(returned)>1 or (returned and any(_date(row['decided_at'])>returned[0] for row in rows))):
            raise ValidationError('Printable SPA state must reproduce the original retained decisions.')
        return body,flow
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid exact-source SPA output evidence.') from error


@operation
def package(snapshot):
    body,flow=_verify_snapshot(snapshot)
    original_members={member['entity_key']:member for member in flow['payload']['itemization']['payload']['members']}
    if not body['members'] or {member['entity_key'] for member in body['members']}!=set(original_members):
        raise ValidationError('Retain every original reporting entity in the combined draft.')
    members=[]
    for member in body['members']:
        original=original_members[member['entity_key']]
        control=next(row for row in original['expenditure']['rows'] if row['category']=='spa')
        if (member['scope']!=original['scope'] or member['entity_label']!=original['entity_label']
            or member['original_spa_control']!=control['amounts']):
            raise ValidationError('Retain the original entity scope and SPA class control.')
        rows=[]
        for subdivision in member['rows']:
            groups={}
            for part in subdivision['source_parts']:
                share=part['original_allocation']
                key=checksum(dict(account=share['account'],disposition=share['disposition']))
                group=groups.setdefault(key,dict(key=key,account=deepcopy(share['account']),
                    disposition=share['disposition'],source_parts=[]))
                group['source_parts'].append(deepcopy(part))
            accounts=[]
            for group in groups.values():
                allocated={column:str(sum((money(part['amount']) for part in group['source_parts']
                    if part['source_identity']['column']==column),Decimal('0.00'))) for column in SOURCE_COLUMNS}
                group['allocated_amounts']=allocated
                group['amounts']=itemization.amounts({column:allocated[column]
                    if subdivision['amounts'][column] is not None else None for column in SOURCE_COLUMNS})
                accounts.append(group)
            accounts.sort(key=lambda row:row['key'])
            totals=itemization.sum_rows(accounts)
            if any(value is not None and totals[column]!=value for column,value in subdivision['amounts'].items()):
                raise ValidationError('Itemized SPA accounts must reproduce every known subdivision control.')
            rows.append(dict(subdivision=subdivision['subdivision'],label=subdivision['label'],
                amounts=deepcopy(subdivision['amounts']),allocated_amounts=deepcopy(subdivision['allocated_amounts']),
                accounts=accounts))
        members.append(dict(entity_key=member['entity_key'],entity_label=member['entity_label'],
            scope=deepcopy(member['scope']),original_spa_control=deepcopy(member['original_spa_control']),
            rows=rows,totals=deepcopy(member['totals']),unresolved_parts=deepcopy(member['unresolved_parts'])))
    result=dict(schema=1,kind='form1_flow_spa_output_draft',flow=flow,spa_review=deepcopy(snapshot),
        members=members,form_issued=False,cash_available=False,source_freshness_certified=False)
    return dict(payload=result,checksum=checksum(result))


def verify(envelope):
    try:
        body=envelope['payload']
        if checksum(body)!=envelope['checksum'] or package(body['spa_review'])!=envelope:
            raise ValidationError('The whole flow/SPA draft must reproduce its original source pair and rows.')
        return body
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid whole flow/SPA output draft.') from error


def render_pdf(envelope, *, number_pages=True):
    body=verify(envelope)
    return flows.render_pdf(body['flow'],spa_draft=envelope,number_pages=number_pages)


def print_member(body,entity_key,p,financial_row,table,heading,scope):
    """Layout only, called after whole-source verification by the flow renderer."""
    member=next(row for row in body['members'] if row['entity_key']==entity_key)
    snapshot=body['spa_review']; payload=snapshot['payload']; identity=payload['identity']
    draft=payload['draft']['payload']
    story=[Spacer(1,12),p('SPA SUBDIVISIONS - RETAINED SOURCE TREATMENT'),
        p(f"Original SPA package {identity['public_id']} / version {identity['version']} / state {snapshot['status']}"),
        p('Class, subdivision and account controls describe the same money; do not add them together. Unknown coverage stays unknown.'),
        p('Original SPA payload checksum: '+snapshot['payload_checksum']),
        p('Original SPA authority: '+payload['reference']),
        p('Original SPA evidence: '+payload['evidence']['name']),
        p('Original SPA evidence SHA256: '+payload['evidence']['sha256']),
        p('Coverage basis: '+draft['coverage_reference']),Spacer(1,5)]
    cells=[heading,financial_row('Original SPA class control','',member['original_spa_control'])]
    for row in member['rows']:
        cells.append(financial_row(row['label']+' - subdivision control','',row['amounts']))
        for group in row['accounts']:
            account=group['account']
            label=(f"{account['title']} (local {account['code']}; original ID {account['id']})" if account
                else 'Original explicit zero without account' if group['disposition']=='mapped' else 'Unresolved reporting selection')
            cells.append(financial_row(label,account['government_account_code'] if account else '',group['amounts']))
    story.extend([table(cells,scope),Spacer(1,10),p('RETAINED SPA OFFICE DECISIONS')])
    if not snapshot['decisions']:story.append(p('No SPA decisions yet.'))
    for row in snapshot['decisions']:
        story.append(KeepTogether([p(f"{row['role'].title()}: {'Approved' if row['approve'] else 'Returned'} / actor {row['actor_id']} / office {row['actor_department_id']} / {row['decided_at']}"),
            p(f"Treatment verified: {row['treatment_verified']} / designation: {row['authority']}"),
            p('Decision note: '+row['note']),p('Decision checksum: '+row['checksum'])]))
    story.extend([Spacer(1,10),p('SPA COVERAGE DECLARATIONS - ALL ORIGINAL CELLS')])
    columns={'prior_amount':'Past year actual','half_amount':'Current H1 actual','estimate':'Current H2 estimate','proposed':'Budget proposal'}
    for cell in draft['coverage']:
        if cell['entity']!=entity_key:continue
        story.append(KeepTogether([Spacer(1,5),p(f"{member['entity_label']} / {columns[cell['column']]} / {subdivisions.SUBDIVISIONS[cell['subdivision']]}: {cell['coverage']}"),p('Declaration basis: '+cell['basis'])]))
    story.extend([Spacer(1,10),p('SPA SIGNED PARTS - COMPLETE ORIGINAL EVIDENCE INDEX')])
    parts=[part for row in member['rows'] for group in row['accounts'] for part in group['source_parts']]+member['unresolved_parts']
    if not parts:story.append(p('No original SPA shares. The coverage declarations above remain required.'))
    for part in parts:
        share=part['original_allocation']; account=share['account']; source=part['source_identity']
        story.append(KeepTogether([Spacer(1,8),p(f"{member['entity_label']} / {columns[source['column']]} / {subdivisions.SUBDIVISIONS.get(part['subdivision'],'Unresolved')} / signed part {part['amount']}"),
            p('Part '+part['key']+' / original allocation '+part['allocation']+' / original component '+part['source_component']),
            p('Original signed allocation: '+share['amount']),
            p('Original source: '+'; '.join(f'{key}={value}' for key,value in source['source'].items())),
            p('Reporting selection: '+(account['government_account_code']+' / '+account['title'] if account else share['disposition']+' without account')),
            p('Original selection basis: '+share['basis']),p('Subdivision basis: '+part['basis'])]))
    return story
