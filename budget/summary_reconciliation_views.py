import json
from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounting import summary_actuals
from accounting import budget_actuals_preparations
from accounting.models import NativeBudgetActualsPreparation
from src.export_archive import archive_export
from .models import BudgetSummaryReconciliation as Record, BudgetOfficeForm
from .office_form_views import owned_version
from .access import budget_access_required, budget_permission_required, can_act_on_budget, department_for_user
from .summary_comparison_views import CohortForm
from . import summary_reconciliations as service, summary_sources

SALT = 'budget-summary-reconciliation-preparation-v1'


class PreparationForm(CohortForm):
    preview = forms.CharField(widget=forms.HiddenInput)
    prior = forms.ChoiceField(label='Exact past-year joint actuals source')
    half = forms.ChoiceField(label='Exact current first-half joint actuals source')

    def __init__(self, *args, proposal, actor, **kwargs):
        from types import SimpleNamespace
        super().__init__(*args, item=SimpleNamespace(proposal_id=proposal.pk,department_id=proposal.department_id,fund_id=0),entity_key='', **kwargs)
        self.fields.pop('entity_key')  # The selected adopted source supplies its explicit designation.
        self.fields['office_forms'].queryset = BudgetOfficeForm.objects.filter(proposal=proposal,status=BudgetOfficeForm.ISSUED,department_id=proposal.department_id)
        year = proposal.fiscal_year.year
        from datetime import date
        sources = summary_actuals.visible(actor).filter(status='approved',scope__budget_department_id=proposal.department_id)
        native = (budget_actuals_preparations.visible(actor) if budget_actuals_preparations.permitted(actor, 'view')
            else NativeBudgetActualsPreparation.objects.none()).filter(status='approved',
            budget_department_id=proposal.department_id).filter(joint_decisions__role='accountant',
            joint_decisions__outcome='certified').filter(joint_decisions__role='treasurer',
            joint_decisions__outcome='certified').distinct()
        self.source_choices = {}
        for name, start, end in (('prior',date(year-2,1,1),date(year-2,12,31)),('half',date(year-1,1,1),date(year-1,6,30))):
            candidates = [(str(obj.pk), ('historical', obj)) for obj in
                sources.filter(scope__period_start=start,scope__period_end=end).select_related('scope')]
            candidates += [('native:'+str(obj.public_id), ('native', obj)) for obj in
                native.filter(period_start=start,period_end=end).select_related('fund')]
            self.source_choices[name] = dict(candidates)
            self.fields[name].choices = [('', 'Choose one source route and version')] + [(key,
                f"{route.title()} · {obj.payload['reference']} · v{obj.version} · " +
                (f"{obj.entity_label} / {obj.fund.code}" if route=='native' else
                 f"{obj.payload['scope']['entity_label']} / {obj.payload['scope']['fund_code']}"))
                for key, (route, obj) in candidates]
            self.fields[name].widget.attrs.update({'class':'form-control','style':'max-width:100%'})

    def clean_prior(self):
        return self.source_choices['prior'][self.cleaned_data['prior']]

    def clean_half(self):
        return self.source_choices['half'][self.cleaned_data['half']]


@require_GET
@budget_access_required
def register(request, public_id):
    proposal = owned_version(request,public_id)
    records = Paginator(proposal.summary_reconciliations.all(),50).get_page(request.GET.get('page'))
    return render(request,'budget/summary_reconciliation_register.html',{'proposal':proposal,'records':records,
        'can_prepare':can_act_on_budget(request.user,'prepare_budget_proposals')})


@require_http_methods(['GET','POST'])
@budget_permission_required('prepare_budget_proposals')
def prepare(request, public_id):
    proposal = owned_version(request,public_id)
    versions = {f"{row['fund_id']}:{row['entity_key']}":row['latest'] for row in
        proposal.summary_reconciliations.values('fund_id','entity_key').annotate(latest=Max('version'))}
    token = signing.dumps({'actor':request.user.pk,'proposal':str(proposal.public_id),'versions':versions},salt=SALT)
    form = PreparationForm(request.POST if request.method=='POST' else None,proposal=proposal,actor=request.user,initial={'preview':token})
    if request.method=='POST' and form.is_valid():
        try:
            values = form.cleaned_data
            preview = signing.loads(values['preview'],salt=SALT,max_age=86400)
            if preview['actor']!=request.user.pk or preview['proposal']!=str(proposal.public_id):
                raise ValidationError('This preparation preview belongs to another actor or proposal.')
            half_route, half = values['half']
            prior_route, prior = values['prior']
            entity = half.entity_key if half_route=='native' else half.payload['scope']['entity_key']
            fund_id = half.fund_id if half_route=='native' else half.scope.fund_id
            key = f"{fund_id}:{entity}"
            record = service.prepare(proposal=proposal,actor=request.user,prior_id=prior.public_id,
                half_id=half.public_id,prior_route=prior_route,half_route=half_route,
                form_ids=[item.public_id for item in values['office_forms']],
                expected_offices=[int(value) for value in values['expected_offices']],entity_key=entity,
                coverage_reference=values['coverage_reference'],expected_latest=preview['versions'].get(key,0))
        except signing.BadSignature:
            form.add_error(None,'The preparation preview expired or changed. Reload it.')
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('budget:summary_reconciliation_detail',public_id=record.public_id)
    return render(request,'budget/summary_reconciliation_prepare.html',{'proposal':proposal,'form':form})


def owned_record(request, public_id):
    record = get_object_or_404(Record.objects.select_related('proposal'),public_id=public_id,department_id=department_for_user(request.user).pk)
    owned_version(request,record.proposal.public_id)
    return record


@require_GET
@budget_access_required
def detail(request, public_id):
    record = owned_record(request,public_id)
    try:
        payload = service.verify(record)
        summary_sources.require_visible(payload, request.user)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages),status=409)
    return render(request,'budget/summary_reconciliation_detail.html',{'record':record,'payload':payload,
        'comparisons':payload['comparisons'].values(),'can_review':can_act_on_budget(request.user,'review_budget_proposals')
        and record.status=='prepared' and record.prepared_by_id!=request.user.pk})


@require_POST
@budget_permission_required('review_budget_proposals')
def review(request, public_id):
    record = owned_record(request,public_id)
    if request.POST.get('action') not in ('accept','return'):
        return HttpResponse('Choose accept or return.',status=400)
    try:
        service.review(record,request.user,accept=request.POST['action']=='accept',note=request.POST.get('note'),authority=request.POST.get('authority'))
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages),status=409)
    return redirect('budget:summary_reconciliation_detail',public_id=record.public_id)


@require_GET
@budget_access_required
def export(request, public_id):
    record = owned_record(request,public_id)
    try:
        payload = service.verify(record)
        summary_sources.require_visible(payload, request.user, 'export')
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages),status=409)
    content = json.dumps({'payload':payload,'payload_checksum':record.payload_checksum,
        'decision':service.decision(record),'decision_checksum':record.decision_checksum},ensure_ascii=False,indent=2).encode('utf-8')
    filename = f'budget-reconciliation-{record.public_id}-v{record.version}.json'
    receipt = archive_export(content=content,department=department_for_user(request.user),user=request.user,
        category='budget-summary-reconciliation',filename=filename,metadata={'payload_checksum':record.payload_checksum})
    service.record_event(record,'summary_reconciliation_exported',request.user,snapshot={'payload_checksum':record.payload_checksum})
    response = HttpResponse(content,content_type='application/json; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256']=receipt['sha256']
    response['X-Content-Type-Options']='nosniff'
    return response
