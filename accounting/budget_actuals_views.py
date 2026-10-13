import csv
import io
import json
import uuid
import zipfile
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods
from src.export_archive import archive_export
from . import budget_actuals_preparations as preparations, budget_actuals_certifications as certifications
from . import budget_native_actuals as actuals
from .budget_actuals_forms import ScopeForm, PreparationForm, ReviewForm, DecisionForm, category_rows
from .access import department_for_user
from .models import NativeBudgetActualsPreparation as Record, AccountingAuditEvent
from .summary_actuals import RECEIPTS, EXPENDITURES
from .budget_actuals import money


@login_required
@require_GET
def register(request):
    rows=preparations.visible(request.user); search=request.GET.get('q','').strip()[:255]
    if search:
        condition=Q(entity_label__icontains=search)|Q(prepared_by_label__icontains=search)|Q(fund__code__icontains=search)
        try: condition|=Q(public_id=uuid.UUID(search))
        except ValueError: pass
        rows=rows.filter(condition)
    params=request.GET.copy(); params.pop('page',None)
    return render(request,'accounting/native_actuals_register.html',dict(page=Paginator(rows,50).get_page(request.GET.get('page')),
        q=search,params=params.urlencode(),can_prepare=preparations.permitted(request.user,'prepare')))


@login_required
@require_http_methods(['GET','POST'])
def create(request,public_id=None):
    if not preparations.permitted(request.user,'prepare'): raise PermissionDenied
    previous=None; initial={}
    if public_id:
        previous=get_object_or_404(preparations.visible(request.user),public_id=public_id,
            department_id=department_for_user(request.user).pk)
        initial=dict(fund=previous.fund_id,budget_department=previous.budget_department_id,
            treasury_department=previous.treasury_department_id,year=previous.period_end.year,
            period='h1' if previous.period_end.month==6 else 'year',entity_type='general' if previous.entity_key=='general' else 'enterprise',
            enterprise_reference=previous.entity_key.partition(':')[2],entity_label=previous.entity_label)
    supplied=request.POST if request.method=='POST' else request.GET if request.GET else initial or None
    scope_form=ScopeForm(supplied,actor=request.user)
    form=None; captured=None; receipt_rows=[]; expenditure_rows=[]; scope=None
    if supplied and scope_form.is_valid():
        scope=scope_form.scope_values()
        if previous and any(scope[key]!=getattr(previous,key) for key in
            ('fund_id','budget_department_id','treasury_department_id','period_start','period_end','entity_key','entity_label')):
            scope_form.add_error(None,'A successor must retain the original reporting scope and offices.')
        else:
            try: captured=actuals.capture(actor=request.user,fund_id=scope['fund_id'],
                period_start=scope['period_start'],period_end=scope['period_end'])
            except ValidationError as error: scope_form.add_error(None,error)
            else:
                receipt_rows,expenditure_rows=category_rows(captured)
                if captured['payload']['classification_complete']:
                    latest=Record.objects.filter(department_id=department_for_user(request.user).pk,
                        fund_id=scope['fund_id'],entity_key=scope['entity_key'],period_start=scope['period_start'],
                        period_end=scope['period_end']).aggregate(n=Max('version'))['n'] or 0
                    form=PreparationForm(request.POST if request.method=='POST' else None,captured=captured,
                        initial=dict(expected_source_checksum=captured['source_checksum'],expected_latest=latest))
                    if request.method=='POST' and form.is_valid():
                        data=form.cleaned_data
                        try:
                            record=preparations.prepare(actor=request.user,**{key:scope[key] for key in
                                ('fund_id','budget_department_id','treasury_department_id','period_start','period_end')},
                                expected_latest=data['expected_latest'],expected_source_checksum=data['expected_source_checksum'],
                                **form.declarations(scope),**{key:data[key] for key in ('reference','authority','reason')})
                        except ValidationError as error: form.add_error(None,error)
                        else: return redirect('accounting:native_actuals_detail',public_id=record.public_id)
                    mappings={label:request.POST.get(f'mapping_{index}') for index,label in enumerate(form.classes)
                        if request.POST.get(f'mapping_{index}') in EXPENDITURES}
                    receipt_rows,expenditure_rows=category_rows(captured,mappings)
    scope_fields=[]
    if scope and captured:
        for name in ScopeForm.base_fields:
            scope_fields.append((name,supplied.get(name,'')))
    return render(request,'accounting/native_actuals_form.html',dict(scope_form=scope_form,form=form,captured=captured,
        receipt_rows=receipt_rows,expenditure_rows=expenditure_rows,scope_fields=scope_fields,previous=previous),
        status=400 if request.method=='POST' else 200)


@login_required
@require_GET
def detail(request,public_id):
    record=get_object_or_404(preparations.visible(request.user),public_id=public_id)
    return _detail(request,record)


def _source_rows(native):
    receipts=native['receipts']['payload']['bridge']; expenses=native['expenditures']['payload']['bridge']
    rows=[dict(kind='Receipt',reference=row['reference'],date=row['date'],account=row['account'],
        amount=row['allocation']['signed_amount'],disposition=row['allocation']['disposition'],
        purpose=row['allocation']['purpose'],category=RECEIPTS.get(row['allocation']['category'],''),
        basis=row['allocation']['basis']) for row in receipts]
    for row in expenses:
        for part in row['allocations']:
            rows.append(dict(kind='Expenditure',reference=row['reference'],date=row['entry_date'],account=row['account'],
                amount=part['signed_amount'],disposition=part['disposition'],purpose=part.get('purpose',''),
                category=part.get('expense_class',''),basis=part.get('basis','')))
    return rows


def _detail(request,record,*,review_form=None,role=None,decision_form=None,status=200):
    try: joint=certifications.snapshot(record,request.user)['payload']
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    coverage=record.payload['coverage']['payload']; native=coverage['actuals']['payload']
    source_q=request.GET.get('source_q','').strip()[:255]; tb_q=request.GET.get('tb_q','').strip()[:255]
    source_rows=_source_rows(native)
    matching=[row for row in source_rows if not source_q or source_q.casefold() in ' '.join(
        str(value) for value in (*row.values(),row['account']['code'],row['account']['title'])).casefold()]
    tb=joint['trial_balance']['payload']; matching_tb=[row for row in tb['rows'] if not tb_q or tb_q.casefold() in
        (row['account']['code']+' '+row['account']['title']).casefold()]
    def params(name):
        values=request.GET.copy(); values.pop(name,None); return values.urlencode()
    owner=department_for_user(request.user).pk; decided=joint['decisions']
    actors={d['payload']['identity']['actor_id'] for d in decided}; roles={d['payload']['identity']['role'] for d in decided}
    forms=[]
    if record.status=='approved' and joint['status']!='returned' and request.user.pk!=record.prepared_by_id and request.user.pk not in actors:
        for candidate in certifications.ROLES:
            office=record.department_id if candidate=='accountant' else record.treasury_department_id
            if candidate not in roles and owner==office and certifications.permitted(request.user,candidate):
                forms.append(dict(role=candidate,label=candidate.title(),form=decision_form if role==candidate else DecisionForm()))
    can_review=record.status=='submitted' and owner==record.department_id and request.user.pk!=record.prepared_by_id and preparations.permitted(request.user,'review')
    current=None
    if joint['status']=='jointly_certified':
        try: current=certifications.is_current(record,request.user)
        except ValidationError: current=False
    rows=[dict(row,label=RECEIPTS[row['category']]) for row in coverage['receipt_rows']]+[
        dict(row,label=EXPENDITURES[row['category']]) for row in coverage['expenditure_rows']]
    history=preparations.visible(request.user).filter(department_id=record.department_id,fund_id=record.fund_id,
        entity_key=record.entity_key,period_start=record.period_start,period_end=record.period_end)
    return render(request,'accounting/native_actuals_detail.html',dict(record=record,joint=joint,coverage=coverage,
        fund=native['scope']['fund'],rows=rows,current=current,review_form=review_form or ReviewForm() if can_review else None,
        decision_forms=forms,sources=Paginator(matching,100).get_page(request.GET.get('sources_page')),
        source_count=len(source_rows),source_q=source_q,source_params=params('sources_page'),
        tb=tb,tb_rows=Paginator(matching_tb,100).get_page(request.GET.get('tb_page')),tb_q=tb_q,tb_params=params('tb_page'),
        history=Paginator(history,25).get_page(request.GET.get('history_page')),history_params=params('history_page'),
        can_export=preparations.permitted(request.user,'export'),
        can_prepare=owner==record.department_id and preparations.permitted(request.user,'prepare')),status=status)


@login_required
@require_http_methods(['POST'])
def review(request,public_id):
    if not preparations.permitted(request.user,'review'): raise PermissionDenied
    record=get_object_or_404(preparations.visible(request.user),public_id=public_id,
        department_id=department_for_user(request.user).pk)
    form=ReviewForm(request.POST)
    if form.is_valid():
        data=form.cleaned_data
        try: preparations.review(preparation_id=record.pk,actor=request.user,approve=data['outcome']=='approve',
            authority=data['authority'],note=data['note'])
        except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
        return redirect('accounting:native_actuals_detail',public_id=record.public_id)
    return _detail(request,record,review_form=form,status=400)


@login_required
@require_http_methods(['POST'])
def decide(request,public_id,role):
    if not certifications.permitted(request.user,role): raise PermissionDenied
    record=get_object_or_404(preparations.visible(request.user),public_id=public_id)
    if department_for_user(request.user).pk!=(record.department_id if role=='accountant' else record.treasury_department_id): raise PermissionDenied
    form=DecisionForm(request.POST)
    if form.is_valid():
        data=form.cleaned_data
        try: certifications.decide(preparation_id=record.pk,actor=request.user,role=role,
            certify=data['outcome']=='certify',authority=data['authority'],note=data['note'])
        except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
        return redirect('accounting:native_actuals_detail',public_id=record.public_id)
    return _detail(request,record,role=role,decision_form=form,status=400)


def _csv(rows):
    buffer=io.StringIO(newline=''); writer=csv.writer(buffer)
    for row in rows:
        writer.writerow(["'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')) else value for value in row])
    return buffer.getvalue().encode('utf-8-sig')


@login_required
@require_GET
def export(request,public_id,kind):
    record=get_object_or_404(preparations.visible(request.user,action='export'),public_id=public_id)
    if kind not in ('snapshot','package'): return HttpResponse('Unknown export.',status=404)
    try: captured=certifications.snapshot(record,request.user,action='export'); certifications.verify_snapshot(captured)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    content=json.dumps(captured,ensure_ascii=False,indent=2).encode('utf-8'); suffix='json'
    if kind=='package':
        body=captured['payload']; coverage=body['original_preparation']['coverage']['payload']
        category=[['Kind','Category','Amount','Coverage','Basis']]
        for category_kind,labels in (('receipt',RECEIPTS),('expenditure',EXPENDITURES)):
            category.extend([[category_kind,labels[row['category']],money(row['amount']),row['coverage'],row['basis']] for row in coverage[category_kind+'_rows']])
        balance=[['Account','Title','Opening signed balance','Period debit','Period credit','Closing signed balance','Closing debit','Closing credit']]
        balance.extend([[row['account']['code'],row['account']['title'],*[money(row[key]) for key in ('opening','debit','credit','closing','closing_debit','closing_credit')]] for row in body['trial_balance']['payload']['rows']])
        members={'joint-evidence.json':content,'category-coverage.csv':_csv(category),'fund-trial-balance.csv':_csv(balance)}
        bridge=[['Stream','Reference','Date','Account','Title','Signed amount','Disposition','Purpose','Category / class','Basis']]
        bridge.extend([[row['kind'],row['reference'],row['date'],row['account']['code'],row['account']['title'],
            money(row['amount']),row['disposition'],row['purpose'],row['category'],row['basis']]
            for row in _source_rows(coverage['actuals']['payload'])])
        members['source-movements.csv']=_csv(bridge)
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name,raw in members.items():
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; archive.writestr(info,raw)
        content=buffer.getvalue(); suffix='zip'
    filename=f'native-budget-actuals-{record.public_id}-{kind}.{suffix}'
    receipt=archive_export(content=content,department=department_for_user(request.user),user=request.user,
        category='native-budget-actuals',filename=filename,metadata=dict(preparation=str(record.public_id),checksum=captured['checksum']))
    AccountingAuditEvent.objects.create(department_id=record.department_id,department_label=record.department_label,
        actor_id=request.user.pk,actor_label=(request.user.get_full_name() or request.user.username)[:160],
        action='native_budget_actuals_exported',snapshot=dict(preparation=str(record.public_id),kind=kind,sha256=receipt['sha256']))
    response=HttpResponse(content,content_type='application/zip' if suffix=='zip' else 'application/json; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="{filename}"'; response['X-Content-Type-Options']='nosniff'
    response['X-GRAND-Export-SHA256']=receipt['sha256']; return response
