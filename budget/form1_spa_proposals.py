"""Explicit SPA subdivision partitions over unchanged original account shares."""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.summary_actuals import text
from accounting.cash_classifications import checksum
from . import form1_account_proposals as accounts, form1_components, form1_itemization

SUBDIVISIONS = {
    'development': 'Appropriation for Development Programs/Projects (20% Development Fund)',
    'ldrrm': 'Appropriation for Local Disaster Risk Reduction and Management (LDRRM) Programs/Projects',
    'debt_service': 'Appropriation for Debt Service',
    'enterprise_subsidy': 'Subsidy to Local Economic Enterprises/Public Utilities',
    'barangay_aid': 'Aid to Barangays',
    'other': 'Other Authorized SPAs',
}
PART_FIELDS = {'key','allocation','amount','subdivision','basis'}
COVERAGE_FIELDS = {'entity','column','subdivision','coverage','basis'}


def propose(draft, parts, coverage, *, coverage_reference):
    try:
        original=accounts.verify(draft); inventory=original['inventory']['payload']
        flows=inventory['flows']['payload']; components={row['key']:row for row in inventory['components']}
        shares={row['key']:row for row in original['allocations']
            if components[row['component']]['identity']['kind']=='expenditure'
            and components[row['component']]['category']=='spa'}
        members={row['entity_key']:row for row in flows['members']}
        controls={(entity,column):next(row for row in member['expenditure']['rows']
            if row['category']=='spa')['amounts'][column]
            for entity,member in members.items() for column in form1_components.SOURCE_COLUMNS}
        if not isinstance(parts,list) or not isinstance(coverage,list):
            raise ValidationError('Supply explicit SPA parts and the complete subdivision coverage matrix.')
        selected=[]; keys=set(); totals={key:Decimal('0.00') for key in shares}; counts={key:0 for key in shares}
        for supplied in parts:
            if not isinstance(supplied,dict) or set(supplied)!=PART_FIELDS:
                raise ValidationError('Use exact SPA part fields.')
            key=text(supplied['key'],'SPA part identity',160); share=shares.get(supplied['allocation'])
            if key in keys or share is None:
                raise ValidationError('Select each SPA part once over an original SPA account share.')
            keys.add(key); value=money(supplied['amount']); capacity=money(share['amount'])
            if (capacity>0 and value<=0) or (capacity<0 and value>=0) or (capacity==0 and value!=0):
                raise ValidationError('Retain original signed SPA shares; do not net opposite activity or add zero parts.')
            subdivision=supplied['subdivision']
            if subdivision not in (*SUBDIVISIONS,'unresolved'):
                raise ValidationError('Choose a named SPA subdivision or explicitly unresolved.')
            source=components[share['component']]
            selected.append(dict(key=key,allocation=share['key'],amount=str(value),subdivision=subdivision,
                basis=text(supplied['basis'],'SPA source subdivision basis'),original_allocation=deepcopy(share),
                source_component=source['key'],source_identity=deepcopy(source['identity'])))
            totals[share['key']]+=value; counts[share['key']]+=1
        if any(not counts[key] or totals[key]!=money(share['amount'])
            or (money(share['amount'])==0 and counts[key]!=1) for key,share in shares.items()):
            raise ValidationError('Partition every original SPA account share exactly, including explicit zero and unresolved parts.')
        matrix={}
        for supplied in coverage:
            if not isinstance(supplied,dict) or set(supplied)!=COVERAGE_FIELDS:
                raise ValidationError('Use exact SPA coverage fields.')
            key=(supplied['entity'],supplied['column'],supplied['subdivision'])
            if (key in matrix or key[0] not in members or key[1] not in form1_components.SOURCE_COLUMNS
                or key[2] not in SUBDIVISIONS or supplied['coverage'] not in ('complete','missing')):
                raise ValidationError('Declare each original entity/column/subdivision once with complete or missing coverage.')
            if controls[key[:2]] is None and supplied['coverage']=='complete':
                raise ValidationError('Missing original SPA coverage cannot become complete through subdivision selection.')
            matrix[key]=dict(entity=key[0],column=key[1],subdivision=key[2],coverage=supplied['coverage'],
                basis=text(supplied['basis'],'SPA subdivision coverage basis'))
        expected={(entity,column,subdivision) for entity in members for column in form1_components.SOURCE_COLUMNS
            for subdivision in SUBDIVISIONS}
        if set(matrix)!=expected:
            raise ValidationError('Retain the complete entity/four-column/six-subdivision coverage matrix.')
        selected.sort(key=lambda row:row['key']); output=[]; complete=[]
        for entity,member in members.items():
            local=[row for row in selected if row['source_identity']['entity']==entity]
            known={column:(controls[(entity,column)] is not None
                and all(matrix[(entity,column,subdivision)]['coverage']=='complete' for subdivision in SUBDIVISIONS)
                and not any(row['subdivision']=='unresolved' and row['source_identity']['column']==column for row in local))
                for column in form1_components.SOURCE_COLUMNS}
            complete.extend(known.values()); rows=[]
            for subdivision,label in SUBDIVISIONS.items():
                chosen=[row for row in local if row['subdivision']==subdivision]
                allocated={column:str(sum((money(row['amount']) for row in chosen
                    if row['source_identity']['column']==column),Decimal('0.00')))
                    for column in form1_components.SOURCE_COLUMNS}
                values=form1_itemization.amounts({column:allocated[column] if known[column] else None
                    for column in form1_components.SOURCE_COLUMNS})
                rows.append(dict(subdivision=subdivision,label=label,amounts=values,
                    allocated_amounts=allocated,source_parts=deepcopy(chosen)))
            total=form1_itemization.sum_rows(rows)
            original_control=form1_itemization.amounts({column:controls[(entity,column)]
                for column in form1_components.SOURCE_COLUMNS})
            for column,value in total.items():
                if value is not None and value!=original_control[column]:
                    raise ValidationError('Complete SPA subdivisions must reproduce the original class control exactly.')
            output.append(dict(entity_key=entity,entity_label=member['entity_label'],scope=deepcopy(member['scope']),
                rows=rows,totals=total,original_spa_control=original_control,
                unresolved_parts=deepcopy([row for row in local if row['subdivision']=='unresolved'])))
        body=dict(schema=1,kind='form1_spa_subdivision_proposal',source_draft=deepcopy(draft),parts=selected,
            coverage=[matrix[key] for key in sorted(matrix)],members=output,
            coverage_reference=text(coverage_reference,'SPA whole-source coverage authority reference'),
            spa_partition_complete=all(complete),reporting_account_selection_complete=original['selection_complete'],
            independently_reviewed=False,code_authority_approved=False,form_issued=False,cash_available=False)
        return dict(payload=body,checksum=checksum(body))
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration) as error:
        raise ValidationError('Retain complete original SPA source and coverage evidence.') from error


def verify(envelope):
    try:
        body=envelope['payload']
        parts=[{key:row[key] for key in PART_FIELDS} for row in body['parts']]
        if (checksum(body)!=envelope['checksum'] or propose(body['source_draft'],parts,body['coverage'],
            coverage_reference=body['coverage_reference'])!=envelope):
            raise ValidationError('SPA subdivisions no longer reproduce their original shares and coverage.')
        return body
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid retained SPA subdivision proposal.') from error
