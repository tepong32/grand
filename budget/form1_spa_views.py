"""Guided SPA preparation, retained role decisions and complete source exports."""
from copy import deepcopy
from functools import wraps
from types import SimpleNamespace
import json

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from src.export_archive import archive_export
from .access import department_for_user, has_budget_permission
from .models import Form1AccountReview, Form1SPAReview as Record
from . import form1_spa_reviews as service, form1_spa_proposals as drafts
from . import form1_account_reviews as accounts, form1_account_views as account_views
from . import form1_spa_output as output

SALT = 'form1-spa-clerk-preview-v1'


def permission(action):
    def decorate(view):
        @login_required
        @wraps(view)
        def guarded(request, *args, **kwargs):
            from vouchers.roles import is_finance_uat_viewer
            mutations = ('prepare', 'budget', 'accounting')
            name = ('review_form1_spa_'+action if action in mutations[1:]
                else action+'_form1_spa_reviews')
            if not has_budget_permission(request.user, name) or (
                action in mutations and is_finance_uat_viewer(request.user)):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return guarded
    return decorate


class Intake(forms.Form):
    preview = forms.CharField(widget=forms.HiddenInput)
    # An evidenced no-activity package has no original SPA shares to partition.
    # None/malformed/missing shares still fail the service's exact partition checks.
    parts = forms.JSONField(required=False, widget=forms.HiddenInput)
    coverage = forms.JSONField(widget=forms.HiddenInput)
    coverage_reference = forms.CharField(label='Whole-source subdivision coverage basis', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    reference = forms.CharField(label='Original SPA source authority reference', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    evidence = forms.FileField(label='Original SPA authority evidence (PDF, PNG or JPEG, up to 8 MiB)')


class Decision(forms.Form):
    authority = forms.CharField(label='Designation authority', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    note = forms.CharField(label='Independent review or return reason', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    treatment_verified = forms.BooleanField(required=False,
        label='I verified the original source amounts, signed partitions and complete subdivision coverage for my designated role.')


def scoped(request, public_id):
    owner = department_for_user(request.user)
    if owner is None: raise PermissionDenied('Use an authorized original office.')
    return get_object_or_404(Record.objects.select_related(*service.RELATED).filter(
        Q(department_id=owner.pk) | Q(fund__department_id=owner.pk)), public_id=public_id)


def preview(source, retained, actor):
    return dict(actor=actor.pk, account_review=str(source.public_id),
        source=retained['payload_checksum'], decision=retained['decision_checksum'],
        latest=Record.objects.filter(proposal=source.proposal, fund=source.fund).aggregate(n=Max('version'))['n'] or 0)


def editor_data(retained, parts=None, coverage=None):
    original = retained['payload']['draft']['payload']
    inventory = original['inventory']['payload']
    components = {row['key']: row for row in account_views.components(original['inventory'])}
    shares = []
    for share in original['allocations']:
        component = components[share['component']]
        if component['identity']['kind']=='expenditure' and component['category']=='spa':
            shares.append(dict(allocation=share['key'], amount=share['amount'],
                reporting_code=share['account']['government_account_code'] if share['account'] else 'Unresolved', entity=component['entity'],
                column=component['column'], source=component['source_label'], original=deepcopy(share)))
    matrix = []
    for member in inventory['flows']['payload']['members']:
        controls = next(row for row in member['expenditure']['rows'] if row['category']=='spa')['amounts']
        for column, label in account_views.COLUMNS.items():
            for subdivision, title in drafts.SUBDIVISIONS.items():
                matrix.append(dict(entity=member['entity_key'], entity_label=member['entity_label'],
                    column=column, column_label=label, subdivision=subdivision, label=title,
                    original_control=controls[column]))
    return dict(shares=shares, matrix=matrix, subdivisions=drafts.SUBDIVISIONS,
        parts=parts if isinstance(parts,list) else None, coverage=coverage if isinstance(coverage,list) else None)


@require_GET
@permission('view')
def register(request):
    owner = department_for_user(request.user)
    if owner is None: raise PermissionDenied('Use an authorized original office.')
    status = request.GET.get('status','')
    if status not in ('','prepared','partially_approved','approved','returned'):
        return HttpResponse('Choose a valid SPA status.',status=400)
    query = Record.objects.select_related(*service.RELATED).defer('evidence').filter(
        Q(department_id=owner.pk) | Q(fund__department_id=owner.pk))
    if status: query=query.filter(status=status)
    search=request.GET.get('q','').strip()
    if search: query=query.filter(Q(fund__code__icontains=search) | Q(public_id__icontains=search)
        | Q(proposal__fiscal_year__year__icontains=search))
    visible=[]; checked_sources=set()
    for record in query.order_by('-prepared_at','-pk'):
        try:
            service._access(record.proposal,record.fund,request.user,'view')
            # Source authority depends on the original account package, not SPA
            # version. Reuse only this request's successful check of that exact FK.
            if record.account_review_id not in checked_sources:
                service._sources(record,request.user)
                checked_sources.add(record.account_review_id)
        except PermissionDenied: continue
        except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
        visible.append(record)
    params=request.GET.copy(); params.pop('page',None)
    return render(request,'budget/form1_spa_register.html',dict(
        page=Paginator(visible,50).get_page(request.GET.get('page')),query=search,status=status,params=params.urlencode()))


@require_http_methods(['GET','POST'])
@permission('prepare')
def prepare(request,public_id):
    owner=department_for_user(request.user)
    if owner is None: raise PermissionDenied('Use an authorized original office.')
    source=get_object_or_404(Form1AccountReview.objects.select_related('proposal__fiscal_year','fund','forecast'),
        public_id=public_id,department_id=owner.pk)
    service._access(source.proposal,source.fund,request.user,'prepare')
    try:
        retained=accounts.snapshot(source,request.user)
        if source.status!='approved': raise ValidationError('Select an independently approved account package.')
        service._current(SimpleNamespace(account_review=source,proposal_id=source.proposal_id,fund_id=source.fund_id),request.user)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    current=preview(source,retained,request.user)
    form=Intake(request.POST or None,request.FILES or None,
        initial=dict(preview=signing.dumps(current,salt=SALT,compress=True)))
    if request.method=='POST' and form.is_valid():
        try:
            signed=signing.loads(form.cleaned_data['preview'],salt=SALT,max_age=3600)
            if signed!=current:
                raise ValidationError('This preview changed or belongs to another actor. Reload the original source before preparing.')
            record=service.prepare(account_review=source,actor=request.user,
                expected_latest=signed['latest'],**{key:form.cleaned_data[key] for key in (
                    'parts','coverage','coverage_reference','reference','evidence')})
        except (ValidationError,signing.BadSignature) as error:
            form.add_error(None,error if isinstance(error,ValidationError) else 'The preparation preview is invalid or expired.')
        else: return redirect('budget:form1_spa_detail',public_id=record.public_id)
    return render(request,'budget/form1_spa_prepare.html',dict(source=source,form=form,
        editor=editor_data(retained,form.cleaned_data.get('parts') if form.is_bound else None,
            form.cleaned_data.get('coverage') if form.is_bound else None)))


def detail_context(record,actor,form=None):
    retained=service.snapshot(record,actor); body=retained['payload']['draft']['payload']
    can_export=False
    try: service.snapshot(record,actor,export=True)
    except PermissionDenied: pass
    else: can_export=True
    roles=[]
    if retained['status'] not in ('approved','returned') and record.prepared_by_id!=actor.pk:
        for role in ('budget','accounting'):
            if any(row['role']==role or row['actor_id']==actor.pk for row in retained['decisions']): continue
            try: service._access(record.proposal,record.fund,actor,role)
            except PermissionDenied: continue
            roles.append(role)
    rows=[]
    for member in body['members']:
        rows.append(dict(entity=member['entity_label'],label='Original SPA class control',amounts=member['original_spa_control']))
        for row in member['rows']:
            rows.append(dict(row,entity=member['entity_label']))
    components={row['key']:row for row in account_views.components(body['source_draft']['payload']['inventory'])}
    parts=[]
    for original in body['parts']:
        part=deepcopy(original); component=components[part['source_component']]
        account=part['original_allocation']['account']
        part.update(entity=component['entity'],column=component['column'],source=component['source_label'],
            reporting_code=account['government_account_code'] if account else 'Unresolved',
            reporting_title=account['title'] if account else 'Unresolved',
            subdivision_label=drafts.SUBDIVISIONS.get(part['subdivision'],'Unresolved'),
            original_amount=part['original_allocation']['amount'])
        parts.append(part)
    entities={member['entity_key']:member['entity_label'] for member in body['members']}
    coverage=[dict(cell,entity_label=entities[cell['entity']],column_label=account_views.COLUMNS[cell['column']],
        subdivision_label=drafts.SUBDIVISIONS[cell['subdivision']]) for cell in body['coverage']]
    from vouchers.roles import is_finance_uat_viewer
    owner = department_for_user(actor)
    current = service.is_current(record,actor) if retained['status']=='approved' else False
    can_prepare_package = bool(current and owner and owner.pk==record.department_id
        and has_budget_permission(actor,'prepare_form1_packages') and not is_finance_uat_viewer(actor))
    return dict(record=record,snapshot=retained,body=body,rows=rows,
        parts=parts,coverage=coverage,roles=roles,can_export=can_export,
        form=form or Decision(),current=current,can_prepare_package=can_prepare_package)


def render_detail(request,record,form=None,status=200):
    try: context=detail_context(record,request.user,form)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    context['part_page']=Paginator(context.pop('parts'),25).get_page(request.GET.get('page'))
    context['coverage_page']=Paginator(context.pop('coverage'),24).get_page(request.GET.get('coverage_page'))
    return render(request,'budget/form1_spa_detail.html',context,status=status)


@require_GET
@permission('view')
def detail(request,public_id): return render_detail(request,scoped(request,public_id))


@require_POST
@login_required
def review(request,public_id,role):
    if role not in ('budget','accounting'): return HttpResponse('Choose the Budget or Accounting role.',status=400)
    # Role authority does not imply source viewing; both are required before a decision.
    record=scoped(request,public_id)
    service._access(record.proposal,record.fund,request.user,role)
    service.snapshot(record,request.user)
    if request.POST.get('action') not in ('approve','return'): return HttpResponse('Choose approve or return.',status=400)
    form=Decision(request.POST)
    if form.is_valid():
        try: service.review(record,request.user,role=role,approve=request.POST['action']=='approve',**form.cleaned_data)
        except ValidationError as error: form.add_error(None,error)
        else: return redirect('budget:form1_spa_detail',public_id=record.public_id)
    return render_detail(request,record,form,status=409)


@require_GET
@permission('export')
def export(request,public_id,kind):
    record=scoped(request,public_id)
    if kind not in ('json','authority','flow-json','flow-pdf'): return HttpResponse('Choose a complete package, printable draft or original authority.',status=400)
    try:
        retained=service.snapshot(record,request.user,export=True)
        envelope=output.package(retained) if kind.startswith('flow-') else None
        if kind=='flow-pdf': content=output.render_pdf(envelope)
        elif kind in ('json','flow-json'): content=json.dumps(envelope if envelope is not None else retained,ensure_ascii=False,indent=2).encode('utf-8')
        else: content=service.evidence_bytes(record,request.user)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    extension='json' if kind in ('json','flow-json') else 'pdf' if content.startswith(b'%PDF-') else 'png' if content.startswith(b'\x89PNG') else 'jpg'
    category='form1-flow-spa-draft' if envelope is not None else 'form1-spa-review'
    filename=f'{category}-{record.public_id}-v{record.version}.{extension}'
    archived=archive_export(content=content,department=department_for_user(request.user),user=request.user,
        category=category,filename=filename,metadata=dict(payload_checksum=retained['payload_checksum'],kind=kind,
            output_checksum=envelope['checksum'] if envelope is not None else None))
    service.record_event(record,'form1_spa_exported',request.user,snapshot=dict(kind=kind,sha256=archived['sha256']))
    response=HttpResponse(content,content_type={'json':'application/json; charset=utf-8','pdf':'application/pdf','png':'image/png','jpg':'image/jpeg'}[extension])
    response['Content-Disposition']=f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256']=archived['sha256']; response['X-Content-Type-Options']='nosniff'
    return response
