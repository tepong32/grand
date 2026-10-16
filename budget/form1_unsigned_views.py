from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_POST

from src.export_archive import archive_export
from . import form1_unsigned_copies as copies, form1_signing as signing
from .form1_signing_forms import SigningCopyRelease
from .form1_signing_views import render_detail
from .models import Form1SigningPreparation as Preparation, Form1UnsignedCopy as Copy
from .services import record_event


@login_required
@require_POST
def release(request, public_id):
    owner = copies._access(request.user, 'release')
    preparation = get_object_or_404(Preparation.objects.select_related('package'), public_id=public_id)
    if owner.pk != preparation.department_id:
        raise PermissionDenied('Use the original Budget office for copy release.')
    form = SigningCopyRelease(request.POST)
    try:
        signing.snapshot(preparation, request.user)
        if form.is_valid():
            copies.release(preparation=preparation, actor=request.user, reference=form.cleaned_data['reference'])
            return redirect('budget:form1_signing_detail', public_id=preparation.public_id)
    except ValidationError as error:
        form.add_error(None, error)
    return render_detail(request, preparation, status=409, copy_form=form)


@login_required
@require_GET
def document(request, public_id):
    record = get_object_or_404(Copy, public_id=public_id)
    try:
        content, retained = copies.document(record, request.user)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    filename = f'form1-unsigned-{record.public_id}.pdf'
    archived = archive_export(content=content, department=signing.department_for_user(request.user), user=request.user,
        category='form1-unsigned-signing-copy', filename=filename,
        metadata=dict(copy_checksum=retained['payload_checksum'], unsigned_copy_issued=True, form_issued=False))
    record_event(record, 'form1_unsigned_copy_exported', request.user,
                 snapshot=dict(sha256=archived['sha256'], copy_checksum=retained['payload_checksum']))
    response = FileResponse(BytesIO(content), as_attachment=True, filename=filename, content_type='application/pdf')
    response['X-GRAND-Export-SHA256'] = archived['sha256']
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
