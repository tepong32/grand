"""Clerk intake and scoped Accounting review of retained reporting selections."""
from copy import deepcopy
from datetime import date
from functools import wraps
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

from accounting.summary_actuals import RECEIPTS, EXPENDITURES
from src.export_archive import archive_export
from .access import department_for_user, has_budget_permission
from .models import Form1AccountReview as Record, BudgetReceiptForecast
from . import form1_account_reviews as service, form1_account_proposals as drafts, form1_components, form1_flows, form1_flow_output

SALT = 'form1-account-clerk-preview-v1'
COLUMNS = {'prior_amount': 'Past-year actual', 'half_amount': 'Current H1 actual',
    'estimate': 'Current H2 estimate', 'proposed': 'Budget-year proposal'}


def permission(action):
    def decorate(view):
        @login_required
        @wraps(view)
        def guarded(request, *args, **kwargs):
            from vouchers.roles import is_finance_uat_viewer
            if (not has_budget_permission(request.user, action+'_form1_account_reviews')
                or (action in ('prepare', 'review') and is_finance_uat_viewer(request.user))):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return guarded
    return decorate


class Intake(forms.Form):
    preview = forms.CharField(widget=forms.HiddenInput)
    allocation = forms.JSONField(widget=forms.HiddenInput)
    coverage_reference = forms.CharField(label='Source coverage and selection basis', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    code_reference = forms.CharField(label='Applicable government code authority / version', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    evidence = forms.FileField(label='Original code-authority evidence (PDF, PNG or JPEG, up to 8 MiB)')


class Decision(forms.Form):
    authority = forms.CharField(label='Accounting designation authority', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    note = forms.CharField(label='Independent review or return reason', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    codes_verified = forms.BooleanField(required=False,
        label='I verified each selected government code and its applicability to the original source date and classification.')


def scoped(request, public_id):
    owner = department_for_user(request.user)
    return get_object_or_404(Record.objects.select_related('proposal__fiscal_year', 'fund', 'forecast').filter(
        Q(department_id=owner.pk) | Q(fund__department_id=owner.pk)), public_id=public_id)


def preview(inventory, forecast, actor):
    return dict(actor=actor.pk, forecast=str(forecast.public_id), inventory=inventory['checksum'],
        latest=Record.objects.filter(proposal=forecast.proposal, fund=forecast.fund).aggregate(n=Max('version'))['n'] or 0)


def allocations(supplied):
    if not isinstance(supplied, list):
        raise ValidationError('Retain all original component selections.')
    result = []
    for row in supplied:
        if not isinstance(row, dict) or set(row) != drafts.FIELDS:
            raise ValidationError('Retain exact account selection fields.')
        account = row['account_id']
        if account not in (None, ''):
            if not isinstance(account, str) or not account.isdecimal():
                raise ValidationError('Choose an account from the original captured chart.')
            account = int(account)
        else:
            account = None
        result.append(dict(row, account_id=account))
    return result


def components(inventory):
    body = form1_components.verify(inventory)
    entities = {row['entity_key']: row['scope']['entity_label'] for row in body['flows']['payload']['members']}
    result = []
    for original in body['components']:
        row = deepcopy(original); identity = row['identity']; source = identity['source']
        start, end = drafts.window(row, body)
        row.update(entity=entities[identity['entity']], column=COLUMNS[identity['column']],
            kind='Receipts' if identity['kind']=='receipt' else 'Expenditures',
            category_label=(RECEIPTS if identity['kind']=='receipt' else EXPENDITURES)[row['category']],
            period=start.isoformat() if start==end else f'{start.isoformat()} to {end.isoformat()}',
            source_label=(f"Native journal {source['entry']}, line {source['line']}" if source['route']=='native'
                else f"{source['route'].title()} source {source['record']}"),
            source_account_label=(row['source_account']['code']+' · '+row['source_account']['title'])
                if row['source_account'] else 'Original explicit zero without an account')
        result.append(row)
    return result


def editor_data(inventory, allocation=None):
    body = form1_components.verify(inventory)
    members = body['flows']['payload']['sources']['forecast']['payload']['group']['members']
    charts = {row['entity_key']: row['forecast']['payload']['capture']['payload']['accounts'] for row in members}
    accounts = {row['id']: row for chart in charts.values() for row in chart}
    rows = components(inventory)
    for row in rows:
        start, end = drafts.window(row, body)
        row['eligible_accounts'] = [str(account['id']) for account in charts[row['identity']['entity']]
            if account['government_account_code'].strip()
            and (not account['effective_from'] or date.fromisoformat(account['effective_from'])<=start)
            and (not account['effective_to'] or date.fromisoformat(account['effective_to'])>=end)
            and (row['identity']['column'] not in ('estimate','proposed')
                or (account['is_active'] is True and account['allow_posting'] is True))]
        # Keep the editor compact; complete original evidence stays in the retained package.
        row.pop('evidence')
    if allocation is not None and (not isinstance(allocation,list) or any(
        not isinstance(row,dict) or set(row)!=drafts.FIELDS for row in allocation)):
        allocation=None
    return dict(components=rows, accounts=[dict(id=str(row['id']),
        label=row['government_account_code']+' · '+row['title']+' (local '+row['code']+')')
        for row in accounts.values() if row['government_account_code'].strip()], allocation=allocation)


@require_GET
@permission('view')
def register(request):
    owner = department_for_user(request.user)
    status = request.GET.get('status','')
    if status not in ('','prepared','approved','returned'):
        return HttpResponse('Choose a valid package status.', status=400)
    query = Record.objects.select_related('proposal__fiscal_year','fund','forecast').defer('evidence').filter(
        Q(department_id=owner.pk) | Q(fund__department_id=owner.pk))
    if status: query = query.filter(status=status)
    search = request.GET.get('q','').strip()
    if search: query = query.filter(Q(fund__code__icontains=search) | Q(public_id__icontains=search)
        | Q(proposal__fiscal_year__year__icontains=search))
    visible = []
    for record in query:
        try:
            service._access(record.proposal,record.fund,request.user,'view'); service._sources(record,request.user)
        except PermissionDenied:
            continue
        except ValidationError as error:
            return HttpResponse(' '.join(error.messages), status=409)
        visible.append(record)
    page = Paginator(visible,50).get_page(request.GET.get('page'))
    params = request.GET.copy(); params.pop('page',None)
    return render(request,'budget/form1_account_register.html',dict(page=page,query=search,status=status,params=params.urlencode()))


@require_http_methods(['GET','POST'])
@permission('prepare')
def prepare(request, public_id):
    forecast = get_object_or_404(BudgetReceiptForecast.objects.select_related('proposal__fiscal_year','fund'),
        public_id=public_id, department_id=department_for_user(request.user).pk)
    service._access(forecast.proposal,forecast.fund,request.user,'prepare')
    try:
        inventory = form1_components.inventory(form1_flows.capture(forecast=forecast,actor=request.user))
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages),status=409)
    current = preview(inventory,forecast,request.user)
    form = Intake(request.POST or None,request.FILES or None,
        initial=dict(preview=signing.dumps(current,salt=SALT,compress=True)))
    supplied = None
    if request.method=='POST' and form.is_valid():
        supplied = form.cleaned_data['allocation']
        try:
            original = signing.loads(form.cleaned_data['preview'],salt=SALT,max_age=3600)
            if original != current:
                raise ValidationError('This preview changed or belongs to another actor. Reload current sources before preparing.')
            record = service.prepare(forecast=forecast,actor=request.user,allocations=allocations(supplied),
                coverage_reference=form.cleaned_data['coverage_reference'],code_reference=form.cleaned_data['code_reference'],
                evidence=form.cleaned_data['evidence'],expected_latest=original['latest'])
        except (ValidationError,signing.BadSignature) as error:
            form.add_error(None,error if isinstance(error,ValidationError) else 'The preparation preview is invalid or expired.')
        else:
            return redirect('budget:form1_account_detail',public_id=record.public_id)
    if supplied is None and form.is_bound: supplied=form.cleaned_data.get('allocation')
    return render(request,'budget/form1_account_prepare.html',dict(forecast=forecast,form=form,
        editor=editor_data(inventory,supplied),source_coverage=inventory['payload']['flows']['payload']['flow_coverage_complete']))


def detail_context(record, actor, form=None):
    retained = service.snapshot(record,actor)
    draft = retained['payload']['draft']['payload']; inventory=draft['inventory']
    rows = components(inventory)
    for row in rows: row['parts']=[part for part in draft['allocations'] if part['component']==row['key']]
    can_review = False; can_export = False
    try: service._access(record.proposal,record.fund,actor,'review')
    except PermissionDenied: pass
    else: can_review=record.status=='prepared' and record.prepared_by_id!=actor.pk
    try: service.snapshot(record,actor,export=True)
    except PermissionDenied: pass
    else: can_export=True
    controls=deepcopy(inventory['payload']['controls'])
    entities={member['entity_key']:member['entity_label'] for member in inventory['payload']['flows']['payload']['members']}
    for control in controls:
        control['entity']=entities[control['entity']]
        control['column']=COLUMNS[control['column']]
        control['category']=(RECEIPTS if control['kind']=='receipt' else EXPENDITURES)[control['category']]
        control['kind']='Receipts' if control['kind']=='receipt' else 'Expenditures'
    can_prepare_spa=False
    if record.status=='approved':
        from . import form1_spa_reviews
        try: form1_spa_reviews._access(record.proposal,record.fund,actor,'prepare')
        except PermissionDenied: pass
        else: can_prepare_spa=True
    return dict(record=record,snapshot=retained,rows=rows,controls=controls,can_prepare_spa=can_prepare_spa,
        current=service.is_current(record,actor) if record.status=='approved' else False,
        can_review=can_review,can_export=can_export,form=form or Decision(),
        sources=inventory['payload']['flows']['payload']['sources']['reconciliations'])


@require_GET
@permission('view')
def detail(request,public_id):
    record=scoped(request,public_id)
    try: context=detail_context(record,request.user)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    context['page']=Paginator(context.pop('rows'),25).get_page(request.GET.get('page'))
    return render(request,'budget/form1_account_detail.html',context)


@require_POST
@permission('review')
def review(request,public_id):
    record=scoped(request,public_id)
    service._access(record.proposal,record.fund,request.user,'review')
    if request.POST.get('action') not in ('approve','return'):
        return HttpResponse('Choose approve or return.',status=400)
    form=Decision(request.POST)
    if form.is_valid():
        try: service.review(record,request.user,approve=request.POST['action']=='approve',**form.cleaned_data)
        except ValidationError as error: form.add_error(None,error)
        else: return redirect('budget:form1_account_detail',public_id=record.public_id)
    try: context=detail_context(record,request.user,form)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    context['page']=Paginator(context.pop('rows'),25).get_page(1)
    return render(request,'budget/form1_account_detail.html',context,status=409)


@require_GET
@permission('export')
def export(request,public_id,kind):
    record=scoped(request,public_id)
    if kind not in ('json','authority','flow-json','flow-pdf'): return HttpResponse('Choose a complete package, flow draft or authority attachment.',status=400)
    try:
        retained=service.snapshot(record,request.user,export=True)
        if kind.startswith('flow-'):
            output=form1_flow_output.package(retained)
            content=(form1_flow_output.render_pdf(output) if kind=='flow-pdf'
                else json.dumps(output,ensure_ascii=False,indent=2).encode('utf-8'))
        else:
            content=json.dumps(retained,ensure_ascii=False,indent=2).encode('utf-8') if kind=='json' else service.evidence_bytes(record,request.user)
    except ValidationError as error: return HttpResponse(' '.join(error.messages),status=409)
    extension='json' if kind in ('json','flow-json') else ('pdf' if content.startswith(b'%PDF-') else 'png' if content.startswith(b'\x89PNG') else 'jpg')
    label='form1-flow-draft' if kind.startswith('flow-') else 'form1-account-review'
    filename=f'{label}-{record.public_id}-v{record.version}.{extension}'
    archived=archive_export(content=content,department=department_for_user(request.user),user=request.user,
        category=label,filename=filename,metadata=dict(payload_checksum=record.payload_checksum,kind=kind))
    service.record_event(record,'form1_accounts_exported',request.user,snapshot=dict(kind=kind,sha256=archived['sha256']))
    response=HttpResponse(content,content_type={'json':'application/json; charset=utf-8','pdf':'application/pdf','png':'image/png','jpg':'image/jpeg'}[extension])
    response['Content-Disposition']=f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256']=archived['sha256']; response['X-Content-Type-Options']='nosniff'
    return response
