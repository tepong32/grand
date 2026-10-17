from uuid import uuid4

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from . import maintenance_notices as service
from .maintenance import can_manage_maintenance
from .maintenance_views import scoped_assets
from .models import AssetMaintenanceCase, MaintenanceCorrectionNotice
from .private_evidence import open_checked_private_evidence
from .property_determinations import checksum

SALT = 'gso-maintenance-correction-notice-v1'


class NoticeForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    explanation = forms.CharField(max_length=4000, label='What needs correction, and what does the source say?',
                                  widget=forms.Textarea(attrs={'rows': 4}))
    source_reference = forms.CharField(max_length=240, label='Basis or reference (document, office reference or observation)')
    upload = forms.FileField(required=False, label='Supporting file (optional; PDF or image, up to 15 MB)')


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def notice_new(request, pk):
    case = get_object_or_404(AssetMaintenanceCase.objects.select_related('asset'), pk=pk,
                            asset__in=scoped_assets(request.user))
    if not can_manage_maintenance(request.user, case.asset):
        raise PermissionDenied
    source_error, token = '', ''
    try:
        token = signing.dumps({'actor': request.user.pk, 'case': str(case.public_id),
            'source': checksum(service.case_basis(case)), 'request': str(uuid4())}, salt=SALT)
    except ValidationError as error:
        source_error = ' '.join(error.messages)
    form = NoticeForm(request.POST if request.method == 'POST' else None,
                      request.FILES if request.method == 'POST' else None, initial={'source_token': token})
    if request.method == 'POST' and form.is_valid():
        try:
            fields = dict(form.cleaned_data)
            data = signing.loads(fields.pop('source_token'), salt=SALT, max_age=1800)
            if data['actor'] != request.user.pk or data['case'] != str(case.public_id):
                raise PermissionDenied
            service.record_notice(actor=request.user, case=case, request_id=data['request'],
                                  expected_source=data['source'], **fields)
        except signing.BadSignature:
            form.add_error(None, 'This form expired or changed. Check the work record, then reopen it.')
        except ValidationError as error:
            form.add_error(None, ' '.join(error.messages))
        else:
            return redirect('inventory:maintenance-detail', pk=case.pk)
    return render(request, 'inventory/maintenance_notice_new.html', {'case': case, 'form': form, 'source_error': source_error})


@never_cache
@login_required
@require_GET
def notice_evidence(request, pk):
    row = get_object_or_404(MaintenanceCorrectionNotice.objects.select_related('case'), pk=pk,
                           case__asset__in=scoped_assets(request.user))
    try:
        service.verify_notice(row)
        source = open_checked_private_evidence(row, namespace=f'inventory/maintenance_notices/{row.case.public_id}')
    except (OSError, ValueError, ValidationError):
        raise Http404('The retained notice document is unavailable.')
    response = FileResponse(source, as_attachment=True, filename=row.original_filename, content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
