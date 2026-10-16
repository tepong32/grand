"""Source-scoped clerk delivery for actual Form 1 paper returns and issues."""
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from src.export_archive import archive_export
from . import form1_signed_copies as signed, form1_final_issues as final, form1_unsigned_copies as unsigned
from .form1_integrity import operation
from .form1_signed_forms import SignedReceipt, SignedDecision, FinalIssue
from .models import Form1UnsignedCopy as Copy, Form1SignedReceipt as Receipt, Form1FinalIssue as Issue
from .services import record_event

STATUSES = {'unverified':'Awaiting independent signature verification',
    'verified':'Signed-return evidence independently verified', 'returned':'Returned for corrected evidence'}


def _can(actor, action, record, *, final=False):
    try:
        owner = signed.access(actor,action,final=final)
    except PermissionDenied:
        return False
    return owner.pk == record.department_id


@login_required
@require_http_methods(['GET','POST'])
@operation
def history(request, public_id):
    signed.access(request.user,'view')
    copy = get_object_or_404(Copy.objects.select_related('preparation__package'),public_id=public_id)
    try:
        unsigned.snapshot(copy,request.user)
        copy_export = False
        try:
            unsigned.snapshot(copy,request.user,export=True)
        except PermissionDenied:
            pass
        else:
            copy_export = True
        can_record = copy_export and _can(request.user,'record',copy)
        query = Receipt.objects.filter(copy=copy)
        latest = query.aggregate(n=Max('version'))['n'] or 0
        head = signed._head(copy) if can_record else None
        form = SignedReceipt(request.POST if request.method=='POST' else None,
            request.FILES if request.method=='POST' else None,copy=copy,
            initial=dict(expected_latest=latest,predecessor=head.public_id if head else None)) if can_record else None
        if request.method=='POST':
            if not can_record:
                raise PermissionDenied('Use original Budget receipt-recording and original-source export authority.')
            if form.is_valid():
                try:
                    predecessor = None
                    if form.cleaned_data['predecessor']:
                        predecessor = Issue.objects.filter(public_id=form.cleaned_data['predecessor']).first()
                        if predecessor is None:
                            raise ValidationError('Reload the original final-issue predecessor.')
                    record = signed.record(copy=copy,actor=request.user,predecessor=predecessor,**form.arguments())
                except ValidationError as error:
                    form.add_error(None,error)
                else:
                    return redirect('budget:form1_signed_detail',public_id=record.public_id)
        page = Paginator(query,10).get_page(request.GET.get('page'))
        rows = [(record,STATUSES[state['status']]) for record,state in signed.history(
            copy,page.object_list.values_list('pk',flat=True),request.user)]
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages),status=409)
    return render(request,'budget/form1_signed_history.html',dict(copy=copy,form=form,head=head,
        rows=rows,page=page,copy_export=copy_export),status=409 if request.method=='POST' else 200)


@operation
def render_detail(request, record, *, status=200, decision_form=None, issue_form=None):
    try:
        retained = signed.snapshot(record,request.user)
        can_export = False
        try:
            signed.snapshot(record,request.user,export=True)
        except PermissionDenied:
            pass
        else:
            can_export = True
        issued = Issue.objects.filter(receipt=record).first()
        issued_state = None; issue_export = False
        if issued:
            retained = signed.snapshot(record,request.user)
            try:
                issued_state = final.snapshot(issued,request.user)
                final.snapshot(issued,request.user,export=True)
            except PermissionDenied:
                pass
            else:
                issue_export = True
        independent = request.user.pk not in (record.captured_by_id,record.copy.preparation.prepared_by_id,
                                              record.copy.preparation.package.prepared_by_id)
        can_verify = (can_export and independent and retained['status']=='unverified'
                      and _can(request.user,'verify',record))
        can_issue = (can_export and independent and issued is None and _can(request.user,'issue',record,final=True))
        people = record.copy.preparation.payload['signatories']
        members = record.copy.preparation.package.payload['assembly']['payload']['members']
        dates = [(member['entity_label'],[(title,people[role]['name'],
                    retained['payload']['physical_return']['signed_dates'][member['entity_key']][role])
                 for role,title in signed.signing.ROLES.items()]) for member in members]
        findings = []
        if retained['review']:
            labels = dict(SignedDecision(copy=record.copy).findings)
            findings = [(labels[key],row) for key,row in retained['review']['payload']['checks'].items()]
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages),status=409)
    return render(request,'budget/form1_signed_detail.html',dict(record=record,retained=retained,
        display_status=STATUSES[retained['status']],dates=dates,findings=findings,can_export=can_export,
        issued=issued if issued_state else None,issued_state=issued_state,issue_export=issue_export,
        can_verify_issue=can_verify and can_issue,
        decision_form=(decision_form or SignedDecision(copy=record.copy)) if can_verify else None,
        decision_errors=decision_form.non_field_errors() if decision_form is not None and not can_verify else None,
        issue_form=(issue_form or FinalIssue()) if can_issue and retained['status']=='verified' else None,
        issue_errors=issue_form.non_field_errors() if issue_form is not None and
            not (can_issue and retained['status']=='verified') else None),status=status)


@login_required
@require_GET
def detail(request, public_id):
    signed.access(request.user,'view')
    record = get_object_or_404(Receipt.objects.select_related('copy__preparation__package'),public_id=public_id)
    return render_detail(request,record)


@login_required
@require_POST
@operation
def review(request, public_id):
    signed.access(request.user,'verify')
    record = get_object_or_404(Receipt.objects.select_related('copy__preparation__package'),public_id=public_id)
    action = request.POST.get('action')
    if action not in ('verify','return','verify_issue'):
        raise PermissionDenied('Choose independent verification, return, or verification with final issuance.')
    form = SignedDecision(request.POST,copy=record.copy)
    try:
        signed.snapshot(record,request.user)
        if form.is_valid():
            if action=='verify_issue':
                final.verify_and_issue(receipt=record,actor=request.user,checks=form.checks(),
                    note=form.cleaned_data['note'],reference=form.cleaned_data['reference'])
            else:
                signed.review(receipt=record,actor=request.user,approve=action=='verify',
                              checks=form.checks(),note=form.cleaned_data['note'])
            return redirect('budget:form1_signed_detail',public_id=record.public_id)
    except ValidationError as error:
        form.add_error(None,error)
    return render_detail(request,record,status=409,decision_form=form)


@login_required
@require_POST
@operation
def issue(request, public_id):
    signed.access(request.user,'issue',final=True)
    record = get_object_or_404(Receipt.objects.select_related('copy__preparation__package'),public_id=public_id)
    form = FinalIssue(request.POST)
    try:
        signed.snapshot(record,request.user)
        if form.is_valid():
            final.issue(receipt=record,actor=request.user,reference=form.cleaned_data['reference'])
            return redirect('budget:form1_signed_detail',public_id=record.public_id)
    except ValidationError as error:
        form.add_error(None,error)
    return render_detail(request,record,status=409,issue_form=form)


def _download(request,record,content,retained,*,issued):
    filename = f'form1-final-{record.public_id}.zip' if issued else f'form1-signed-return-{record.public_id}.pdf'
    archived = archive_export(content=content,department=signed.department_for_user(request.user),user=request.user,
        category='form1-final-issue' if issued else 'form1-signed-return',filename=filename,
        metadata=dict(evidence_checksum=retained['payload_checksum'],form_issued=issued))
    record_event(record,'form1_final_package_exported' if issued else 'form1_signed_return_exported',request.user,
                 snapshot=dict(sha256=archived['sha256'],evidence_checksum=retained['payload_checksum']))
    response = FileResponse(BytesIO(content),as_attachment=True,filename=filename,
                            content_type='application/zip' if issued else 'application/pdf')
    response['X-GRAND-Export-SHA256'] = archived['sha256']
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_GET
def document(request, public_id):
    signed.access(request.user,'export')
    record = get_object_or_404(Receipt,public_id=public_id)
    try:
        content,retained = signed.returned_document(record,request.user)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages),status=409)
    return _download(request,record,content,retained,issued=False)


@login_required
@require_GET
def issued_document(request, public_id):
    signed.access(request.user,'export',final=True)
    record = get_object_or_404(Issue,public_id=public_id)
    try:
        content,retained = final.document(record,request.user)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages),status=409)
    return _download(request,record,content,retained,issued=True)
