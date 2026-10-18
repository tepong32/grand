from uuid import uuid4
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from inventory.models import ReceivingLine, ReceivingReceipt
from inventory.private_evidence import open_checked_private_evidence
from inventory.property_determinations import checksum
from accounting.access import department_for_user
from . import asset_cost_allocations as service
from .asset_cost_forms import AllocationProposalForm, AllocationComponents, AllocationDecisionForm

SALT = 'gso-documentary-asset-cost-allocation-v1'
STATUS_FILTERS = (('all', 'All proposals'), ('proposed', 'Awaiting review'),
                  ('approved', 'Reviewed history'), ('rejected', 'Rejected proposals'))


@never_cache
@login_required
@require_GET
def workbench(request):
    owner = department_for_user(request.user)
    if not service.can_view_workbench(request.user):
        raise PermissionDenied
    status = request.GET.get('status', 'all')
    if status not in dict(STATUS_FILTERS):
        return HttpResponseBadRequest('Choose a valid allocation review status.')
    sources = ReceivingLine.objects.none()
    if service.can_propose(request.user):
        sources = ReceivingLine.objects.select_related('receipt', 'registered_asset').filter(
            receipt__department_id=owner.pk, receipt__status=ReceivingReceipt.ACCEPTED,
            kind=ReceivingLine.ASSET, is_void=False, registered_asset__isnull=False).order_by('-receipt_id', 'sequence')
    rows = service.visible(request.user).select_related('line__receipt', 'finance_department').order_by('-pk')
    if status != 'all':
        rows = rows.filter(status=status)
    return render(request, 'inventory_finance/asset_cost_workbench.html', {
        'page': Paginator(rows, 25).get_page(request.GET.get('page')),
        'sources': Paginator(sources, 25).get_page(request.GET.get('source_page')),
        'selected_status': status, 'status_choices': STATUS_FILTERS})


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def propose(request, pk):
    owner = department_for_user(request.user)
    if not owner or not service.can_propose(request.user):
        raise PermissionDenied
    line = get_object_or_404(ReceivingLine.objects.select_related('receipt', 'registered_asset'),
                            pk=pk, receipt__department_id=owner.pk)
    initial, component_initial, snapshot, error = {}, None, None, ''
    try:
        snapshot, head = service.basis(line)
        if head:
            component_initial = head.components
            initial.update(finance_department=head.finance_department_id, allocation_basis=head.basis)
        initial['source_token'] = signing.dumps({'actor': request.user.pk, 'line': line.pk,
            'basis': checksum(snapshot), 'request': str(uuid4())}, salt=SALT)
    except ValidationError as problem:
        error = ' '.join(problem.messages)
    form = AllocationProposalForm(request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None, initial=initial)
    lines = AllocationComponents(request.POST if request.method == 'POST' else None, prefix='components', initial=component_initial)
    if request.method == 'POST':
        valid = form.is_valid()
        components_valid = lines.is_valid()
        if valid and components_valid:
            try:
                token = signing.loads(form.cleaned_data['source_token'], salt=SALT, max_age=1800)
                if token['actor'] != request.user.pk or token['line'] != line.pk:
                    raise PermissionDenied
                row = service.propose(actor=request.user, line=line,
                    finance_department_id=form.cleaned_data['finance_department'].pk,
                    request_id=token['request'], expected_basis=token['basis'],
                    entries=[{key: entry[key] for key in ('label', 'quantity', 'unit', 'amount', 'reference')}
                             for entry in lines.cleaned_data if entry and not entry.get('DELETE')],
                    allocation_basis=form.cleaned_data['allocation_basis'], upload=form.cleaned_data['upload'])
            except signing.BadSignature:
                form.add_error(None, 'This form expired or changed. Reopen it from the source list.')
            except ValidationError as problem:
                form.add_error(None, ' '.join(problem.messages))
            else:
                return redirect('inventory_finance:asset-cost-detail', pk=row.pk)
    return render(request, 'inventory_finance/asset_cost_propose.html', {
        'line': line, 'form': form, 'lines': lines, 'source': snapshot['source'] if snapshot else None,
        'source_error': error, 'from_approved': component_initial is not None})


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def detail(request, pk):
    row = get_object_or_404(service.visible(request.user).select_related('line__receipt', 'finance_department', 'proposed_by'), pk=pk)
    allowed = service.can_review(request.user, row) and row.proposed_by_id != request.user.pk
    form = AllocationDecisionForm(request.POST if request.method == 'POST' else None,
                                  initial={'expected_version': row.state_version})
    if request.method == 'POST':
        if not allowed:
            raise PermissionDenied
        if form.is_valid():
            try:
                service.decide(actor=request.user, row=row, **form.cleaned_data)
            except ValidationError as problem:
                form.add_error(None, ' '.join(problem.messages))
            else:
                return redirect('inventory_finance:asset-cost-detail', pk=row.pk)
    error, source_error, current = '', '', False
    try:
        service.verify(row)
    except ValidationError as problem:
        error = ' '.join(problem.messages)
    if not error:
        try:
            snapshot, head = service.basis(row.line)
            current = row.status == 'approved' and head.pk == row.pk and row.source_snapshot['source'] == snapshot['source']
            if row.source_snapshot['source'] != snapshot['source']:
                source_error = 'The source facts changed after this proposal. Retain this worksheet as history and propose a new allocation.'
        except ValidationError as problem:
            source_error = ' '.join(problem.messages)
    return render(request, 'inventory_finance/asset_cost_detail.html', {
        'record': row, 'form': form, 'can_review': allowed and row.status == 'proposed' and not error,
        'record_error': error, 'source_error': source_error, 'is_current': current})


@never_cache
@login_required
@require_GET
def evidence(request, pk):
    row = get_object_or_404(service.visible(request.user).select_related('line__receipt'), pk=pk)
    try:
        service.verify(row, files=False)
        source = open_checked_private_evidence(row, namespace=f'inventory/asset-cost-allocations/{row.line.receipt.public_id}')
    except (OSError, ValueError, ValidationError):
        raise Http404('The retained allocation evidence is unavailable or requires investigation.')
    response = FileResponse(source, as_attachment=True, filename=row.original_filename, content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
