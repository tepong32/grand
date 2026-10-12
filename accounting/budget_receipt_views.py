import json
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.db.models import Max,Q
from django.http import Http404,HttpResponse
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_GET,require_http_methods,require_POST
from src.export_archive import archive_export
from .access import department_for_user
from . import budget_receipt_attributions as service,budget_receipt_partitions as partitions
from .budget_receipt_forms import Scope,Proposal,Component,Pairing,Review
from .models import BudgetReceiptAttributionBatch as Batch,BudgetReceiptAttribution as Member,BudgetReceiptAttributionHead as Head,AccountingAuditEvent


def visible(actor,action='view'):
    if not service.permitted(actor,action): raise PermissionDenied
    return Batch.objects.filter(department_id=department_for_user(actor).pk)


@login_required
@require_GET
def register(request):
    rows=visible(request.user).order_by('-prepared_at','-pk'); q=request.GET.get('q','').strip()[:255]
    if q: rows=rows.filter(Q(prepared_by_label__icontains=q)|Q(members__entry__reference__icontains=q)|
        Q(members__entry__description__icontains=q)|Q(members__entry__lines__memo__icontains=q)).distinct()
    params=request.GET.copy(); params.pop('page',None)
    return render(request,'accounting/receipt_classification_register.html',dict(
        page=Paginator(rows,50).get_page(request.GET.get('page')),q=q,params=params.urlencode(),
        can_prepare=service.permitted(request.user,'prepare')))


@login_required
@require_GET
def sources(request):
    if not service.permitted(request.user,'view'): raise PermissionDenied
    form=Scope(request.GET or None,actor=request.user); captured=None; page=None
    if form.is_bound and form.is_valid():
        data=form.cleaned_data
        try: captured=service.capture(actor=request.user,fund_id=data['fund'].pk,period_start=data['start'],period_end=data['end'])
        except ValidationError as error: form.add_error(None,error)
        else:
            ids=[row['entry_id'] for row in captured['payload']['journals']]
            latest={row['entry_id']:row['n'] for row in Member.objects.filter(entry_id__in=ids).values('entry_id').annotate(n=Max('version'))}
            heads={row.entry_id:row.attribution.version for row in Head.objects.filter(entry_id__in=ids).select_related('attribution')}
            posted={row['id']:row for row in captured['payload']['ledger']['payload']['journals']}
            rows=[]
            for row in captured['payload']['journals']:
                original=posted[row['entry_id']]
                text=' '.join([row['reference'],row['source_reference'],original['description'],
                    *[line['memo'] for line in original['lines']]])
                if not data['q'] or data['q'].casefold() in text.casefold():
                    rows.append(dict(row,description=original['description'],latest=latest.get(row['entry_id'],0),approved=heads.get(row['entry_id'],0)))
            page=Paginator(rows,100).get_page(request.GET.get('page'))
    params=request.GET.copy(); params.pop('page',None)
    return render(request,'accounting/receipt_classification_sources.html',dict(form=form,captured=captured,page=page,
        params=params.urlencode(),can_prepare=service.permitted(request.user,'prepare')))


@login_required
@require_http_methods(['GET','POST'])
def prepare(request,entry_id):
    if not service.permitted(request.user,'prepare'): raise PermissionDenied
    scope_form=Scope(request.POST if request.method=='POST' else request.GET,actor=request.user)
    form=None; entry=None; components=[]; pairing=None; parent=None; initial=[]; scope_fields=[]
    if scope_form.is_valid():
        data=scope_form.cleaned_data
        try:
            captured=service.capture(actor=request.user,fund_id=data['fund'].pk,period_start=data['start'],period_end=data['end'])
            if entry_id not in {row['entry_id'] for row in captured['payload']['journals']}: raise Http404
            _,entry,proof=partitions.entry_source(captured,entry_id)
            latest=Member.objects.filter(entry_id=entry_id).aggregate(n=Max('version'))['n'] or 0
            inherit=bool(entry['reversal_of_id'] and entry['lineage']['exact_mirror'] and not entry['lineage']['issue'])
            form=Proposal(request.POST if request.method=='POST' else None,lines=entry['lines'],inherit=inherit,
                initial=dict(expected_source_checksum=captured['source_checksum'],expected_latest=latest))
            if inherit:
                head=Head.objects.select_related('attribution__batch').filter(entry_id=entry['reversal_of_id']).first()
                if not head: raise ValidationError('Independently classify and review the original journal before inheriting this reversal.')
                parent=head.attribution
                _,original,_=partitions.entry_source(captured,entry['reversal_of_id'])
                pairing=Pairing(request.POST if request.method=='POST' else None,lines=entry['lines'],originals=original['lines'])
            else:
                initial=[dict(line_id=str(row['id']),amount=str(partitions.amount(str(max(
                    Decimal(row['debit']),Decimal(row['credit']))))),
                    disposition='unresolved',purpose='unresolved',category='',basis='') for row in entry['lines']]
                if request.method=='POST':
                    try:
                        supplied=json.loads(request.POST.get('rows',''))
                        if isinstance(supplied,list) and len(supplied)<=10000 and all(isinstance(row,dict) for row in supplied): initial=supplied
                    except (ValueError,TypeError): pass
                components=[Component(initial=row,lines=entry['lines'],prefix=f'component-{index}') for index,row in enumerate(initial)]
            if request.method=='POST':
                valid=form.is_valid()
                if pairing is not None: valid=pairing.is_valid() and valid
                if valid:
                    item=dict(entry_id=entry_id,expected_latest=form.cleaned_data['expected_latest'])
                    if inherit: item.update(inherit_from=str(parent.public_id),line_pairs=pairing.pairs())
                    else: item['rows']=form.cleaned_data['rows']
                    try:
                        batch=service.propose_batch(actor=request.user,fund_id=data['fund'].pk,period_start=data['start'],period_end=data['end'],
                            expected_source_checksum=form.cleaned_data['expected_source_checksum'],proposals=[item],
                            reason=form.cleaned_data['reason'],evidence_reference=form.cleaned_data['evidence_reference'])
                    except ValidationError as error: form.add_error(None,error)
                    else: return redirect('accounting:receipt_classification_detail',batch_id=batch.public_id)
            scope_fields=[(key,request.POST.get(key) if request.method=='POST' else request.GET.get(key,'')) for key in ('fund','start','end')]
        except ValidationError as error: scope_form.add_error(None,error); form=None
    return render(request,'accounting/receipt_classification_prepare.html',dict(scope_form=scope_form,form=form,entry=entry,
        components=components,blank=Component(lines=entry['lines'],prefix='component-__prefix__') if entry else None,
        pairing=pairing,parent=parent,scope_fields=scope_fields),status=400 if request.method=='POST' else 200)


@login_required
@require_GET
def detail(request,batch_id):
    return _detail(request,get_object_or_404(visible(request.user),public_id=batch_id))


def _detail(request,batch,form=None,status=200):
    try: captured=service.snapshot(batch,request.user)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    body=captured['payload']; inventory=body['inventory']['payload']
    journals={row['entry_id']:row for row in inventory['journals']}; lines={row['line_id']:row for row in inventory['lines']}
    rows=[]
    for member in body['members']:
        for allocation in member['partition']['payload']['allocations']:
            rows.append(dict(allocation,reference=journals[member['entry_id']]['reference'],date=journals[member['entry_id']]['date'],
                account=lines[allocation['line_id']]['account'],version=member['version']))
    q=request.GET.get('q','').strip()[:255]
    matching=[row for row in rows if not q or q.casefold() in ' '.join(str(v) for v in row.values()).casefold()]
    params=request.GET.copy(); params.pop('page',None)
    current=service.is_current(batch,request.user) if batch.status==Batch.APPROVED else None
    return render(request,'accounting/receipt_classification_detail.html',dict(batch=batch,body=body,current=current,
        page=Paginator(matching,100).get_page(request.GET.get('page')),count=len(rows),q=q,params=params.urlencode(),
        review_form=(form or Review()) if batch.status==Batch.SUBMITTED and batch.prepared_by_id!=request.user.pk and service.permitted(request.user,'review') else None,
        can_export=service.permitted(request.user,'export')),status=status)


@login_required
@require_POST
def review(request,batch_id):
    if not service.permitted(request.user,'review'): raise PermissionDenied
    batch=get_object_or_404(visible(request.user),public_id=batch_id); form=Review(request.POST)
    if form.is_valid():
        try: service.review_batch(batch_id=batch.public_id,actor=request.user,approve=form.cleaned_data['outcome']=='approve',note=form.cleaned_data['note'])
        except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
        return redirect('accounting:receipt_classification_detail',batch_id=batch.public_id)
    return _detail(request,batch,form,status=400)


@login_required
@require_GET
def export(request,batch_id):
    batch=get_object_or_404(visible(request.user,'export'),public_id=batch_id)
    try: captured=service.snapshot(batch,request.user,action='export'); service.verify_snapshot(captured)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    content=json.dumps(captured,ensure_ascii=False,indent=2).encode('utf-8')
    filename=f'budget-receipt-classification-{batch.public_id}.json'
    archived=archive_export(content=content,department=department_for_user(request.user),user=request.user,
        category='budget-receipt-classification',filename=filename,metadata=dict(batch=str(batch.public_id),checksum=captured['checksum']))
    AccountingAuditEvent.objects.create(department_id=batch.department_id,department_label=batch.department_label,
        actor_id=request.user.pk,actor_label=(request.user.get_full_name() or request.user.username)[:160],
        action='budget_receipt_exported',snapshot=dict(batch=str(batch.public_id),sha256=archived['sha256']))
    response=HttpResponse(content,content_type='application/json; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="{filename}"'; response['X-GRAND-Export-SHA256']=archived['sha256']
    response['X-Content-Type-Options']='nosniff'; return response
