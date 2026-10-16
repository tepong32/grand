"""Original-source-scoped preparation and independent designation review."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from io import BytesIO
from src.export_archive import archive_export

from . import form1_packages as packages, form1_signing as service, form1_unsigned_copies as copies, form1_signed_copies as signed
from .form1_signing_forms import SigningPreparation, SigningDecision, SigningCopyRelease
from .models import Form1Package, Form1SigningPreparation as Preparation, Form1UnsignedCopy
from .services import record_event
from .form1_integrity import operation

STATUSES = {'prepared': 'Awaiting independent preparation review',
            'reviewed_preparation': 'Preparation evidence reviewed', 'returned': 'Returned for a successor'}


@login_required
@require_http_methods(['GET', 'POST'])
def history(request, public_id):
    package = get_object_or_404(Form1Package, public_id=public_id)
    service._capability(request.user, 'view')
    try:
        package = packages._read(package, request.user)
        can_prepare = False
        try:
            service._capability(request.user, 'prepare')
        except PermissionDenied:
            pass
        else:
            can_prepare = service.department_for_user(request.user).pk == package.department_id
        query = Preparation.objects.filter(package=package)
        latest = query.aggregate(n=Max('version'))['n'] or 0
        form = SigningPreparation(request.POST or None, request.FILES or None,
                                  initial={'expected_latest': latest}) if can_prepare else None
        if request.method == 'POST':
            if not can_prepare:
                raise PermissionDenied('Use this Budget office’s signing-preparation authority.')
            if form.is_valid():
                try:
                    record = service.prepare(package=package, actor=request.user, **form.arguments())
                except ValidationError as error:
                    form.add_error(None, error)
                else:
                    return redirect('budget:form1_signing_detail', public_id=record.public_id)
        page = Paginator(query, 25).get_page(request.GET.get('page'))
        rows = [(record, STATUSES[service.snapshot(record, request.user)['status']]) for record in page]
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    return render(request, 'budget/form1_signing_history.html', dict(
        package=package, form=form, rows=rows, page=page), status=409 if request.method == 'POST' else 200)


@operation
def render_detail(request, record, form=None, status=200, copy_form=None):
    try:
        retained = service.snapshot(record, request.user)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    can_export = False
    try:
        service.snapshot(record, request.user, export=True)
    except PermissionDenied:
        pass
    else:
        can_export = True
    can_review = False
    try:
        owner = service._capability(request.user, 'review')
    except PermissionDenied:
        pass
    else:
        can_review = (owner.pk == record.department_id and retained['review'] is None
                      and request.user.pk not in (record.prepared_by_id, record.package.prepared_by_id))
    people = [(role, title, retained['payload']['signatories'][role]) for role, title in service.ROLES.items()]
    findings = [dict(label=key.replace('_', ' ').capitalize(), **finding)
                for key, finding in retained['review']['payload']['checks'].items()] if retained['review'] else []
    unsigned = Form1UnsignedCopy.objects.filter(preparation=record).first()
    copy_state = None; copy_export = False; can_release = False
    try:
        if unsigned:
            try:
                copy_state = copies.snapshot(unsigned, request.user)
            except PermissionDenied:
                pass
            if copy_state is not None:
                try:
                    copies.snapshot(unsigned, request.user, export=True)
                except PermissionDenied:
                    pass
                else:
                    copy_export = True
        elif retained['status'] == 'reviewed_preparation':
            try:
                owner = copies._access(request.user, 'release')
                service.snapshot(record, request.user, export=True)
            except PermissionDenied:
                pass
            else:
                can_release = owner.pk == record.department_id and request.user.pk not in (
                    record.prepared_by_id, record.package.prepared_by_id)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    signed_history = False
    if unsigned is not None and copy_state is not None:
        try:
            signed.access(request.user,'view')
        except PermissionDenied:
            pass
        else:
            signed_history = True
    return render(request, 'budget/form1_signing_detail.html', dict(record=record,signed_history=signed_history,
        retained=retained, display_status=STATUSES[retained['status']], people=people,
        findings=findings, can_export=can_export,
        unsigned_copy=unsigned if copy_state else None, copy_state=copy_state, copy_export=copy_export,
        copy_form=(copy_form or SigningCopyRelease()) if can_release else None,
        copy_errors=copy_form.non_field_errors() if copy_form is not None and not can_release else None,
        form=(form or SigningDecision()) if can_review else None,
        decision_errors=form.non_field_errors() if form is not None and not can_review else None), status=status)


@login_required
@require_GET
def detail(request, public_id):
    record = get_object_or_404(Preparation.objects.select_related('package'), public_id=public_id)
    return render_detail(request, record)


@login_required
@require_POST
def review(request, public_id):
    record = get_object_or_404(Preparation.objects.select_related('package'), public_id=public_id)
    service._capability(request.user, 'review')
    if request.POST.get('action') not in ('approve', 'return'):
        raise PermissionDenied('Choose independent preparation review or return.')
    form = SigningDecision(request.POST)
    try:
        service.snapshot(record, request.user)
        if form.is_valid():
            service.review(preparation=record, actor=request.user, approve=request.POST['action'] == 'approve',
                           checks=form.checks(), note=form.cleaned_data['note'])
            return redirect('budget:form1_signing_detail', public_id=record.public_id)
    except ValidationError as error:
        form.add_error(None, error)
    return render_detail(request, record, form=form, status=409)


@login_required
@require_GET
def document(request, public_id, role):
    record = get_object_or_404(Preparation, public_id=public_id)
    try:
        content, metadata = service.designation_document(record, role, request.user)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    archived = archive_export(content=content, department=service.department_for_user(request.user),
        user=request.user, category='form1-designation-document', filename=metadata['name'],
        metadata=dict(preparation=str(record.public_id), preparation_checksum=record.payload_checksum,
                      role=role, document_sha256=metadata['sha256'], form_issued=False))
    record_event(record, 'form1_designation_exported', request.user,
                 snapshot=dict(role=role, sha256=archived['sha256']))
    response = FileResponse(BytesIO(content), as_attachment=True, filename=metadata['name'], content_type='application/octet-stream')
    response['X-GRAND-Export-SHA256'] = archived['sha256']
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
