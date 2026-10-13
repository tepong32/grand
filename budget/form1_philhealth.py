"""Original-source PhilHealth deduction drafts; overlap claims are never approvals."""
from copy import deepcopy
from hashlib import sha256

from django.core.exceptions import ValidationError
from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from accounting.summary_actuals import text,document
from . import form1_stocks as stocks,form1_components as components,form1_itemization as rows
from .models import BudgetReceiptForecast
from .form1_integrity import operation

PART_FIELDS={'key','source','amount','treatment','counterpart','basis'}
COVERAGE_FIELDS={'entity','column','kind','coverage','basis'}
KINDS=('receipt','restriction','expense')
TREATMENTS={'receipt':('deduct','claimed_overlap','unresolved'),
    'restriction':('philhealth_carryover','other','unresolved'),
    'expense':('shf','counterpart','other','unresolved')}


@operation
def inventory(stock):
    try:
        original=stocks.verify(stock); flow=components.inventory(original['flow']); catalog=[]
        for component in flow['payload']['components']:
            kind=component['identity']['kind']
            if kind=='expenditure' or component['category']=='philhealth':
                catalog.append(dict(key=component['key'],kind='expense' if kind=='expenditure' else 'receipt',
                    entity=component['identity']['entity'],column=component['identity']['column'],amount=component['amount'],
                    capacity_identity=component['key'],original_component=deepcopy(component)))
        for member in original['members']:
            for column in components.SOURCE_COLUMNS:
                cell=member['opening'][column]
                if cell['kind']=='missing':continue
                source=cell['source']; actual=source if cell['kind']=='actual' else source['payload']['source']
                actual_body=actual['payload']; retained=actual_body['snapshot']['payload']
                origin=(actual_body['public_id'] if actual_body['route']=='historical'
                    else retained['original_preparation']['restriction_source']['public_id'])
                leaves=([dict(original=row,amount=row['amount'],proposed=False) for row in actual_body['restrictions']]
                    if cell['kind']=='actual' else source['payload']['restriction_positions'])
                for leaf in leaves:
                    identity=dict(entity=member['entity_key'],column=column,kind='restriction',
                        stock_checksum=source['checksum'],restriction=leaf['original']['key'])
                    capacity=checksum(dict(origin=source['checksum'] if leaf['proposed'] else origin,
                        restriction=leaf['original']['key']))
                    catalog.append(dict(key=checksum(identity),kind='restriction',entity=member['entity_key'],column=column,
                        amount=leaf['amount'],capacity_identity=capacity,identity=identity,
                        original_restriction=deepcopy(leaf),scope=deepcopy(cell['scope'])))
        catalog.sort(key=lambda row:row['key'])
        if len({row['key'] for row in catalog})!=len(catalog):raise ValidationError('Retain each original source once.')
        body=dict(schema=1,kind='form1_philhealth_inventory',stock=deepcopy(stock),flow_inventory=flow,catalog=catalog,
            independently_reviewed=False,form_issued=False,cash_available=False)
        return dict(payload=body,checksum=checksum(body))
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Retain complete original stock and PhilHealth source evidence.') from error


def verify_inventory(envelope):
    try:
        body=envelope['payload']
        if checksum(body)!=envelope['checksum'] or inventory(body['stock'])!=envelope:
            raise ValidationError('PhilHealth inventory must reproduce original flow and stock sources.')
        return body
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid original PhilHealth source inventory.') from error


def propose(source,parts,coverage,*,coverage_reference,documents):
    """Pure editable draft; original document bytes/access require the server helpers."""
    try:
        original=verify_inventory(source); catalog={row['key']:row for row in original['catalog']}
        stock=original['stock']['payload']; members={row['entity_key']:row for row in stock['members']}
        if not isinstance(parts,list) or not isinstance(coverage,list) or set(documents)!={'authority','reconciliation'}:
            raise ValidationError('Retain the complete signed partitions, coverage and document declarations.')
        for metadata in documents.values():
            if metadata is not None and (not isinstance(metadata,dict) or set(metadata)!={'name','sha256'}
                or not isinstance(metadata['sha256'],str) or len(metadata['sha256'])!=64
                or any(char not in '0123456789abcdef' for char in metadata['sha256'])):
                raise ValidationError('Retain the original policy/worksheet names and hashes.')
            if metadata is not None:text(metadata['name'],'original policy/worksheet filename',180)
        selected=[]; seen=set(); sums={key:money('0') for key in catalog}; counts={key:0 for key in catalog}
        for supplied in parts:
            if not isinstance(supplied,dict) or set(supplied)!=PART_FIELDS:raise ValidationError('Use exact original-source part fields.')
            key=text(supplied['key'],'PhilHealth part identity',160); item=catalog.get(supplied['source'])
            if key in seen or item is None:raise ValidationError('Select each part once over an original source.')
            value=money(supplied['amount']); capacity=money(item['amount']); treatment=supplied['treatment']
            if (capacity>0 and value<=0) or (capacity<0 and value>=0) or (capacity==0 and value!=0):
                raise ValidationError('Keep original signed sources and exactly one part for an explicit zero.')
            if treatment not in TREATMENTS[item['kind']]:raise ValidationError('Select an explicit source treatment or unresolved.')
            counterpart=supplied['counterpart']
            if not isinstance(counterpart,str) or (treatment!='claimed_overlap' and counterpart):
                raise ValidationError('Only an explicit receipt overlap claim may select a counterpart.')
            if treatment=='claimed_overlap':
                other=catalog.get(counterpart)
                if (not other or other['kind']=='receipt' or other['entity']!=item['entity'] or not value
                    or money(other['amount'])*value<=0):
                    raise ValidationError('Link the exact same-entity restriction/expense with matching signed capacity.')
            selected.append(dict(key=key,source=item['key'],amount=str(value),treatment=treatment,counterpart=counterpart,
                basis=text(supplied['basis'],'original source/SHF funding/overlap basis'),original_source=deepcopy(item)))
            sums[item['key']]+=value;counts[item['key']]+=1;seen.add(key)
        if any(not counts[key] or sums[key]!=money(item['amount']) or (not money(item['amount']) and counts[key]!=1)
            for key,item in catalog.items()):raise ValidationError('Partition every original amount exactly, including signed corrections and zeros.')
        selected.sort(key=lambda row:row['key'])
        claims={}
        for part in selected:
            if part['treatment']!='claimed_overlap':continue
            other=catalog[part['counterpart']]
            permitted='shf' if other['kind']=='expense' else 'philhealth_carryover'
            cap=abs(sum((money(row['amount']) for row in selected
                if row['source']==other['key'] and row['treatment']==permitted),money('0')))
            key=other['capacity_identity']; amount,limit=claims.get(key,(money('0'),cap))
            amount+=abs(money(part['amount']));limit=min(limit,cap)
            if amount>limit:raise ValidationError('Overlap claims cannot consume a source twice across parts or columns.')
            claims[key]=(amount,limit)
        matrix={}
        for supplied in coverage:
            if not isinstance(supplied,dict) or set(supplied)!=COVERAGE_FIELDS:raise ValidationError('Retain exact coverage declarations.')
            key=(supplied['entity'],supplied['column'],supplied['kind'])
            if (key in matrix or key[0] not in members or key[1] not in components.SOURCE_COLUMNS or key[2] not in KINDS
                or supplied['coverage'] not in ('complete','missing')):raise ValidationError('Declare every entity/column/source-kind once.')
            matrix[key]=dict(supplied,basis=text(supplied['basis'],'whole source coverage and non-overlap reconciliation'))
        expected={(entity,column,kind) for entity in members for column in components.SOURCE_COLUMNS for kind in KINDS}
        if set(matrix)!=expected:raise ValidationError('Retain the complete four-column receipt/restriction/expense coverage matrix.')
        controls={(row['entity'],row['column']):row for row in original['flow_inventory']['payload']['controls']
            if row['kind']=='receipt' and row['category']=='philhealth'}
        output=[]; complete=[]
        for entity,member in members.items():
            local=[row for row in selected if row['original_source']['entity']==entity]; known={}; diagnostic={}; reasons={}
            for column in components.SOURCE_COLUMNS:
                chosen=[row for row in local if row['original_source']['column']==column]
                pending=[row['key'] for row in chosen if row['treatment'] in ('unresolved','claimed_overlap')
                    or row['treatment']=='shf' and money(row['amount'])!=0]
                declared=controls[(entity,column)]['declared_amount']
                source_coverage=declared is not None and member['opening'][column]['restricted'] is not None
                for kind in ('receipt','restriction'):
                    covered=declared is not None if kind=='receipt' else member['opening'][column]['restricted'] is not None
                    if not covered and matrix[(entity,column,kind)]['coverage']=='complete':
                        raise ValidationError('Missing original receipt/restriction evidence cannot become complete by declaration.')
                expense_covered=all(row['declared_amount'] is not None for row in original['flow_inventory']['payload']['controls']
                    if row['entity']==entity and row['column']==column and row['kind']=='expenditure')
                if not expense_covered and matrix[(entity,column,'expense')]['coverage']=='complete':
                    raise ValidationError('Missing expense source coverage is not a reviewed zero overlap.')
                known[column]=source_coverage and expense_covered and not pending and all(documents.values()) and all(
                    matrix[(entity,column,kind)]['coverage']=='complete' for kind in KINDS)
                diagnostic[column]=str(money(sum((money(row['amount']) for row in chosen if row['treatment']=='deduct'),money('0'))))
                reasons[column]=pending
            deduction=rows.amounts({column:diagnostic[column] if known[column] else None for column in components.SOURCE_COLUMNS})
            ending=member['draft_resource_ending']
            net={column:str(money(ending[column])-money(deduction[column]))
                if ending[column] is not None and deduction[column] is not None else None for column in ending}
            complete.extend(known.values())
            output.append(dict(entity_key=entity,scope=deepcopy(member['scope']),diagnostic_deduction=rows.amounts(diagnostic),
                deduction=deduction,resource_ending=deepcopy(ending),net_ending=net,pending_overlap_or_treatment=reasons,
                source_parts=deepcopy(local)))
        body=dict(schema=1,kind='form1_philhealth_deduction_draft',inventory=deepcopy(source),parts=sorted(selected,key=lambda row:row['key']),
            coverage=[matrix[key] for key in sorted(matrix)],coverage_reference=text(coverage_reference,'whole PhilHealth policy/coverage reference'),
            documents=deepcopy(documents),members=output,deduction_partition_complete=bool(all(complete)),
            independently_reviewed=False,philhealth_deduction_complete=False,form_issued=False,cash_available=False)
        return dict(payload=body,checksum=checksum(body))
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Retain the whole original PhilHealth treatment and evidence.') from error


def verify(envelope):
    try:
        body=envelope['payload'];parts=[{key:row[key] for key in PART_FIELDS} for row in body['parts']]
        if checksum(body)!=envelope['checksum'] or propose(body['inventory'],parts,body['coverage'],
            coverage_reference=body['coverage_reference'],documents=body['documents'])!=envelope:
            raise ValidationError('Deduction controls must reproduce every original source, part and declaration.')
        return deepcopy(body)
    except (KeyError,TypeError,ValueError) as error:raise ValidationError('Invalid retained PhilHealth draft.') from error


def capture(*,stock,actor,evidence):
    original=stocks.verify(stock);source=original['flow']['payload']['sources']['forecast']
    record=BudgetReceiptForecast.objects.filter(public_id=source['payload']['identity']['public_id']).first()
    if not record:raise ValidationError('Select the original reviewed flow source.')
    observed=stocks.capture(forecast=record,actor=actor,selections=original['selections'],evidence=evidence,
        stock_convention=original['stock_convention'],boundary_basis=original['boundary_basis'])
    if observed!=stock:raise ValidationError('Select the exact current original stock/flow sources.')
    return inventory(observed)


def prepare(*,source,actor,evidence,parts,coverage,coverage_reference,authority=None,reconciliation=None):
    if capture(stock=verify_inventory(source)['stock'],actor=actor,evidence=evidence)!=source:
        raise ValidationError('Select the exact current PhilHealth source inventory.')
    retained={};metadata={}
    for key,upload in (('authority',authority),('reconciliation',reconciliation)):
        if upload is None:metadata[key]=None
        else:retained[key],metadata[key]=document(upload,'original PhilHealth '+key)
    return propose(source,parts,coverage,coverage_reference=coverage_reference,documents=metadata),retained


def reproduce(envelope,actor,*,evidence,documents,export=False):
    body=verify(envelope); stocks.reproduce(body['inventory']['payload']['stock'],actor,evidence=evidence,export=export)
    expected={key for key,value in body['documents'].items() if value is not None}
    if not isinstance(documents,dict) or set(documents)!=expected:raise ValidationError('Retain the exact original attached documents.')
    for key,data in documents.items():
        if not isinstance(data,bytes) or sha256(data).hexdigest()!=body['documents'][key]['sha256']:
            raise ValidationError('Original policy/overlap worksheet bytes changed.')
    return body
