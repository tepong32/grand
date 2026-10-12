import json

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounting.cash_classifications import checksum
from src.export_archive import archive_export
from . import office_forms as service
from .access import budget_access_required, budget_permission_required, department_for_user, can_act_on_budget
from .models import BudgetVersion, BudgetOfficeForm
from .planning_context import can_read_context

SALT = 'budget-office-form-preview-v1'


def owned_version(request, public_id):
    version = get_object_or_404(BudgetVersion, public_id=public_id, department_id=department_for_user(request.user).pk)
    if not can_read_context(request.user, version):
        raise PermissionDenied
    return version


class PreparationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea)):
                field.widget.attrs['class'] = 'form-control'

    preview = forms.CharField(widget=forms.HiddenInput)
    lgu = forms.CharField(label='LGU name', max_length=200)
    fund_scope = forms.CharField(label='Fund scope and authority', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    coverage = forms.CharField(label='Complete office/fund/period coverage basis and evidence reference', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    coverage_confirmed = forms.BooleanField(label='I checked all applicable office objects and both historical periods, including activity without a proposed amount. Missing rows have not been treated as zero.')
    department_head_name = forms.CharField(label='Department Head name', max_length=160)
    department_head_authority = forms.CharField(label='Department Head designation evidence', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    budget_officer_name = forms.CharField(label='Local Budget Officer name', max_length=160)
    budget_officer_authority = forms.CharField(label='Local Budget Officer designation evidence', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    chief_executive_name = forms.CharField(label='Local Chief Executive name', max_length=160)
    chief_executive_authority = forms.CharField(label='Local Chief Executive designation evidence', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))


@require_GET
@budget_access_required
def register(request, public_id):
    version = owned_version(request, public_id)
    scopes, errors = {}, []
    try:
        context = service.frozen_context(version, request.user)
        for row in context['certified_schedule']:
            if row.get('office_id'):
                scopes[(row['office_id'], row['fund_id'])] = row
    except ValidationError as exc:
        errors = exc.messages
    records = Paginator(version.office_forms.all(), 50).get_page(request.GET.get('page'))
    return render(request, 'budget/office_forms.html', {'version': version, 'scopes': list(scopes.values()),
        'errors': errors, 'records': records, 'can_prepare': can_act_on_budget(request.user, 'prepare_budget_proposals')})


@require_http_methods(['GET', 'POST'])
@budget_permission_required('prepare_budget_proposals')
def prepare(request, public_id, office_id, fund_id):
    version = owned_version(request, public_id)
    errors, schedule, form = [], None, None
    status = 200
    try:
        context = service.frozen_context(version, request.user)
        schedule = service.project(context, office_id, fund_id)
    except ValidationError as exc:
        errors, status = exc.messages, 409
    else:
        token = signing.dumps({'actor': request.user.pk, 'version': str(version.public_id), 'office': office_id,
            'fund': fund_id, 'context': checksum(context), 'latest': service.latest(version, office_id, fund_id)}, salt=SALT)
        form = PreparationForm(request.POST if request.method == 'POST' else None, initial={'preview': token})
        if request.method == 'POST':
            status = 409
            if form.is_valid():
                try:
                    preview = signing.loads(form.cleaned_data['preview'], salt=SALT, max_age=86400)
                    if any(preview.get(key) != value for key, value in {'actor': request.user.pk,
                        'version': str(version.public_id), 'office': office_id, 'fund': fund_id}.items()):
                        raise ValidationError('This preparation preview belongs to another actor or scope.')
                    data = form.cleaned_data
                    item = service.prepare(version=version, actor=request.user, office_id=office_id, fund_id=fund_id,
                        expected_latest=preview['latest'], expected_context_checksum=preview['context'],
                        **{key: data[key] for key in ('lgu', 'fund_scope', 'coverage', 'coverage_confirmed')},
                        signatories={role: {field: data[role + '_' + field] for field in ('name', 'authority')} for role in service.ROLES})
                except signing.BadSignature:
                    form.add_error(None, 'The preparation preview expired or is invalid. Reload it.')
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    return redirect('budget:office_form_detail', public_id=item.public_id)
    return render(request, 'budget/office_form_prepare.html', {'version': version, 'form': form,
        'errors': errors, 'schedule': schedule}, status=status)


def owned_form(request, public_id):
    item = get_object_or_404(BudgetOfficeForm.objects.select_related('proposal'), public_id=public_id,
        department_id=department_for_user(request.user).pk)
    if not can_read_context(request.user, item.proposal):
        raise PermissionDenied
    return item


@require_GET
@budget_access_required
def detail(request, public_id):
    item = owned_form(request, public_id)
    try:
        payload = service.verify(item)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409)
    return render(request, 'budget/office_form_detail.html', {'item': item, 'data': payload,
        'evidence': json.dumps(payload, ensure_ascii=False, indent=2),
        'can_review': can_act_on_budget(request.user, 'review_budget_proposals') and item.prepared_by_id != request.user.pk})


@require_POST
@budget_permission_required('review_budget_proposals')
def action(request, public_id):
    item = owned_form(request, public_id)
    if request.POST.get('action') not in ('issue', 'return'):
        return HttpResponse('Choose issue or return.', status=400)
    try:
        service.decide(item=item, actor=request.user, issue=request.POST['action'] == 'issue', note=request.POST.get('note', ''))
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409)
    messages.success(request, 'Independent office-form decision recorded. No physical signature is implied.')
    return redirect('budget:office_form_detail', public_id=item.public_id)


@require_GET
@budget_access_required
def download(request, public_id):
    item = owned_form(request, public_id)
    try:
        service.verify(item)
        if item.status != item.ISSUED:
            raise ValidationError('Only independently issued copies can be downloaded.')
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409)
    content = bytes(item.document)
    filename = f'lbp-form-2-{item.public_id}-v{item.version}-unsigned.pdf'
    archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='budget-office-form', filename=filename,
        metadata={'payload_checksum': item.payload_checksum, 'decision_checksum': item.decision_checksum, 'unsigned': True})
    service.record_event(item, 'office_form_downloaded', request.user,
        snapshot={'document_checksum': item.document_checksum, 'unsigned': True})
    response = HttpResponse(content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256'] = item.document_checksum
    return response
