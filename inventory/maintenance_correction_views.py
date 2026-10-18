from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from . import maintenance_corrections as service
from .maintenance import can_manage_maintenance
from .maintenance_correction_forms import CorrectionProposalForm, CorrectionDecisionForm, CorrectionValuesForm
from .maintenance_views import scoped_assets
from .models import AssetMaintenanceCase, MaintenanceCorrection
from .private_evidence import open_checked_private_evidence
from .property_determinations import checksum

SALT = 'gso-reviewed-maintenance-correction-v1'


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def correction_new(request, pk):
    case = get_object_or_404(AssetMaintenanceCase.objects.select_related('asset'), pk=pk,
                            asset__in=scoped_assets(request.user))
    if not can_manage_maintenance(request.user, case.asset):
        raise PermissionDenied
    error, initial = '', {}
    try:
        source, head = service.basis(case)
        initial = dict(head.corrected_values if head else {name: getattr(case, name) for name in service.FIELDS})
        initial['source_token'] = signing.dumps({'actor': request.user.pk, 'case': str(case.public_id),
            'source': checksum(source), 'request': str(uuid4())}, salt=SALT)
    except ValidationError as problem:
        error = ' '.join(problem.messages)
    form = CorrectionProposalForm(request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            values = form.cleaned_data
            token = signing.loads(values['source_token'], salt=SALT, max_age=1800)
            if token['actor'] != request.user.pk or token['case'] != str(case.public_id):
                raise PermissionDenied
            row = service.propose(actor=request.user, case=case, request_id=token['request'],
                expected_source=token['source'], data={name: values[name] for name in service.FIELDS},
                reason=values['reason'], source_reference=values['source_reference'], upload=values['upload'])
        except signing.BadSignature:
            form.add_error(None, 'This form expired or changed. Reopen it from the work record.')
        except ValidationError as problem:
            form.add_error(None, ' '.join(problem.messages))
        else:
            return redirect('inventory:maintenance-correction-detail', pk=row.pk)
    return render(request, 'inventory/maintenance_correction_new.html', {'case': case, 'form': form, 'source_error': error})


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def correction_detail(request, pk):
    row = get_object_or_404(MaintenanceCorrection.objects.select_related('case__asset', 'proposed_by'),
                            pk=pk, case__asset__in=scoped_assets(request.user))
    can_review = service.can_review(request.user, row.case.asset) and row.proposed_by_id != request.user.pk
    form = CorrectionDecisionForm(request.POST if request.method == 'POST' else None,
                                   initial={'expected_version': row.state_version})
    if request.method == 'POST':
        if not can_review:
            raise PermissionDenied
        if form.is_valid():
            try:
                service.decide(actor=request.user, row=row, **form.cleaned_data)
            except ValidationError as problem:
                form.add_error(None, ' '.join(problem.messages))
            else:
                return redirect('inventory:maintenance-correction-detail', pk=row.pk)
    error = ''
    try:
        service.verify(row)
    except ValidationError as problem:
        error = ' '.join(problem.messages)
    fields = [(field.label, field.value()) for field in CorrectionValuesForm(initial=row.corrected_values)] if not error else []
    return render(request, 'inventory/maintenance_correction_detail.html', {
        'record': row, 'form': form, 'can_review': can_review and row.status == 'proposed',
        'fields': fields, 'record_error': error})


@never_cache
@login_required
@require_GET
def correction_evidence(request, pk):
    row = get_object_or_404(MaintenanceCorrection.objects.select_related('case'), pk=pk,
                            case__asset__in=scoped_assets(request.user))
    try:
        service.verify(row, files=False)
        source = open_checked_private_evidence(row, namespace=f'inventory/maintenance_corrections/{row.case.public_id}')
    except (OSError, ValueError, ValidationError):
        raise Http404('The retained correction evidence is unavailable or requires investigation.')
    response = FileResponse(source, as_attachment=True, filename=row.original_filename, content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
