"""Source-authorized whole-package history and draft delivery."""
from django.contrib.auth.decorators import login_required
from types import SimpleNamespace
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from src.export_archive import archive_export
from .access import department_for_user, has_budget_permission
from .models import Form1Package
from . import form1_package_exports as outputs
from . import form1_packages as packages, form1_package_reviews as reviews
from .form1_flows import COLUMNS
from accounting.cash_classifications import checksum
from .services import record_event
from .form1_package_forms import PackageDecision

STATUSES={'prepared':'Awaiting internal reviews','partially_reviewed':'Some internal reviews recorded',
    'reviewed':'Internal reviews complete','returned':'Returned for a successor'}


def candidates(actor):
    owner=department_for_user(actor)
    if not owner or not actor.is_active or not has_budget_permission(actor,'view_form1_packages'):
        raise PermissionDenied('Use your designated office and package viewing permission.')
    return Form1Package.objects.filter(office_index__department_id=owner.pk).select_related(
        'proposal__fiscal_year','fund').defer('payload')


@login_required
@require_GET
def register(request):
    query=candidates(request.user)
    search=request.GET.get('q','').strip()
    status=request.GET.get('status','')
    if len(search)>160 or status not in ('',*STATUSES):
        return HttpResponse('Use a search of up to 160 characters and a listed internal review status.',status=400)
    if search:
        query=query.filter(Q(fund__code__icontains=search)|Q(proposal__fiscal_year__year__icontains=search)
            |Q(public_id__icontains=search))
    visible=[];assemblies={};checked_sources=set();denied_sources=set()
    # Stream candidates and retain only card metadata. Complete nested financial
    # roots must not accumulate merely to count or display a history page.
    for record in query.order_by('-prepared_at','-pk').iterator(chunk_size=1):
        try:
            original=Form1Package.objects.select_related('proposal__fiscal_year','fund','spa_review').defer(
                'spa_review__payload','spa_review__evidence').prefetch_related('attachments','decisions').get(pk=record.pk)
            body=packages.verify(original,_assemblies=assemblies)
            packages._access(original.proposal,original.fund,body,request.user,'view')
            # Reuse only this actor/request's successful original-source check of
            # the exact same actual SPA FK and fully hashed retained assembly.
            # Different roots still verify their identity, bytes, office index
            # and independent decisions; nothing persists as approval/currentness.
            source_key=(original.spa_review_id,checksum(original.payload['assembly']))
            if source_key in denied_sources:
                continue
            if source_key not in checked_sources:
                try:
                    packages._sources(original,request.user,'view')
                except PermissionDenied:
                    denied_sources.add(source_key)
                    continue
                checked_sources.add(source_key)
            packages.verify_office_index(original,body)
            state=reviews._state(original,body,list(original.decisions.all()))
        except PermissionDenied:
            continue
        except ValidationError as error:
            return HttpResponse(' '.join(error.messages),status=409)
        if not status or state['status']==status:
            card=SimpleNamespace(public_id=original.public_id,version=original.version,
                prepared_at=original.prepared_at,fund=SimpleNamespace(code=original.fund.code),
                proposal=SimpleNamespace(fiscal_year=SimpleNamespace(year=original.proposal.fiscal_year.year)))
            visible.append(dict(record=card,status=STATUSES[state['status']],
                complete=body['calculation_coverage_complete']))
    params=request.GET.copy();params.pop('page',None)
    return render(request,'budget/form1_package_register.html',dict(
        page=Paginator(visible,50).get_page(request.GET.get('page')),query=search,status=status,
        statuses=STATUSES.items(),params=params.urlencode()))


def render_detail(request,record,*,decision_role=None,decision_form=None,status=200):
    try:
        record=packages._read(record,request.user)
        body=record.payload['assembly']['payload'];packages.verify_office_index(record,body)
        state=reviews._state(record,body,list(record.decisions.all()))
        can_export=False
        try: packages._read(record,request.user,export=True)
        except PermissionDenied: pass
        else: can_export=True
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages),status=409)
    rows=[]
    for member in body['members']:
        def add(label,amounts):
            rows.append(dict(entity=member['entity_label'],label=label,
                values=[amounts[column] for column in COLUMNS]))
        add('Beginning balance after restrictions',{column:member['opening'][column]['net'] for column in COLUMNS})
        for row in member['receipt']['rows']:add(row['label'],row['amounts'])
        add('Total receipts',member['receipt']['totals'])
        for row in member['expenditure']['rows']:add(row['label'],row['amounts'])
        add('Total expenditures',member['expenditure']['totals'])
        add('Gross ending resources',member['resource_ending'])
        add('PhilHealth deduction',member['philhealth']['deduction'])
        add('Net ending balance',member['net_ending'])
    pending=[]
    completed={(item['payload']['identity']['role'],item['payload']['identity']['actor_department_id'])
        for item in state['decisions']}
    for item in state['required_reviews']:
        if (item['role'],item['department_id']) not in completed:pending.append(item)
    from vouchers.roles import is_finance_uat_viewer
    owner=department_for_user(request.user)
    decision_forms=[]
    if (state['status'] not in ('reviewed','returned') and record.prepared_by_id!=request.user.pk
        and not is_finance_uat_viewer(request.user)
        and not any(item['payload']['identity']['actor_id']==request.user.pk for item in state['decisions'])):
        for item in pending:
            role=item['role']
            if owner.pk==item['department_id'] and has_budget_permission(request.user,'review_form1_package_'+role):
                decision_forms.append(dict(role=role,form=decision_form if role==decision_role else PackageDecision(role)))
    params=request.GET.copy();params.pop('page',None)
    return render(request,'budget/form1_package_detail.html',dict(record=record,state=state,
        status=STATUSES[state['status']],pending=pending,can_export=can_export,
        complete=body['calculation_coverage_complete'],decision_forms=decision_forms,
        decision_errors=decision_form.non_field_errors() if decision_form is not None and not any(
            item['role']==decision_role for item in decision_forms) else None,
        page=Paginator(rows,50).get_page(request.GET.get('page')),params=params.urlencode()),status=status)


@login_required
@require_GET
def detail(request,public_id):
    record=get_object_or_404(candidates(request.user),public_id=public_id)
    return render_detail(request,record)


@login_required
@require_POST
def review(request,public_id,role):
    if role not in reviews.CHECKS:
        return HttpResponse('Choose Budget, Accounting or Treasury internal review.',status=400)
    from vouchers.roles import is_finance_uat_viewer
    if is_finance_uat_viewer(request.user) or not has_budget_permission(request.user,'review_form1_package_'+role):
        raise PermissionDenied('Use your independently designated whole-package review permission.')
    record=get_object_or_404(candidates(request.user),public_id=public_id)
    if request.POST.get('action') not in ('approve','return'):
        return HttpResponse('Choose internal approval or return.',status=400)
    form=PackageDecision(role,request.POST)
    try:
        # Reading authority is required even for a malformed submission; role
        # grants alone must not reveal or decide another officer's source evidence.
        record=packages._read(record,request.user)
        if form.is_valid():
            reviews.review(record,request.user,role=role,approve=request.POST['action']=='approve',
                checks=form.checks(),authority=form.cleaned_data['authority'],note=form.cleaned_data['note'])
            return redirect('budget:form1_package_detail',public_id=record.public_id)
    except ValidationError as error:
        form.add_error(None,error)
    return render_detail(request,record,decision_role=role,decision_form=form,status=409)


@login_required
@require_GET
def export(request, public_id, kind):
    if kind not in ('json', 'zip', 'pdf'):
        return HttpResponse('Choose complete draft JSON, original-document ZIP or printable PDF.', status=400)
    record = get_object_or_404(Form1Package, public_id=public_id)
    try:
        content, envelope = outputs.export(record, request.user, kind=kind)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    filename = f'form1-whole-draft-{record.public_id}-v{record.version}.{kind}'
    archived = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='form1-whole-package-draft', filename=filename,
        metadata=dict(package_checksum=envelope['payload']['original_package']['checksum'],
            output_checksum=envelope['checksum'], kind=kind, form_issued=False))
    record_event(record, 'form1_package_exported', request.user,
        snapshot=dict(kind=kind, sha256=archived['sha256'], output_checksum=envelope['checksum']))
    response = HttpResponse(content, content_type={'json':'application/json; charset=utf-8', 'zip':'application/zip', 'pdf':'application/pdf'}[kind])
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256'] = archived['sha256']
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
