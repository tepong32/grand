"""Ordinary office intake and immutable history for original-part findings."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from src.export_archive import archive_export
from vouchers.roles import is_finance_uat_viewer
from .access import department_for_user, has_budget_permission
from .models import Form1Package, Form1TreatmentProposal
from .services import record_event
from . import form1_packages as packages, form1_treatments as service

FINDINGS = {'deduct': 'Include as PhilHealth receipt', 'unresolved': 'Unresolved',
    'confirm_overlap': 'Confirm the claimed source linkage', 'reject_overlap': 'Reject the claimed overlap',
    'philhealth_carryover': 'PhilHealth carryover restriction', 'other': 'Other funding / restriction',
    'shf': 'Special Health Fund expense', 'counterpart': 'Ordinary LGU counterpart expense'}
CHECK_LABELS = {'entity_period_scope': 'Entity, fund and period scope',
    'whole_source_coverage': 'Every original signed source part', 'funding_authority': 'Applicable funding authority',
    'signed_source_lineage': 'Original signed amounts and correction lineage',
    'counterpart_identity': 'Exact counterpart source identity', 'shared_source_capacity': 'Shared source capacity',
    'restriction_identity': 'Original cash restriction identity', 'fund_transfer_route': 'Actual fund transfer route',
    'cash_timing': 'Cash dates and timing evidence'}
STATUSES = {'prepared': 'Awaiting independent findings', 'partially_reviewed': 'Some office findings recorded',
    'reviewed': 'Factual reviews complete', 'returned': 'Returned for a successor'}
COLUMN_LABELS = {'prior_amount': 'Past year actual', 'half_amount': 'Current H1 actual',
    'estimate': 'Current H2 estimate', 'proposed': 'Proposed budget year'}


class Preparation(forms.Form):
    expected_latest = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    reference = forms.CharField(label='Reason and source reference', max_length=2000, widget=forms.Textarea)
    authority = forms.FileField(label='Original applicable authority document')
    reconciliation = forms.FileField(label='Original source and funding reconciliation')


class Finding(forms.Form):
    basis = forms.CharField(label='Finding and evidence basis', max_length=2000, widget=forms.Textarea)
    funding_reference = forms.CharField(label='Applicable funding authority reference', max_length=2000,
        widget=forms.Textarea)
    lineage_reference = forms.CharField(label='Exact original source / counterpart reference', max_length=2000,
        widget=forms.Textarea)

    def __init__(self, part, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.part = part
        kind = part['original_source']['kind']
        from .form1_philhealth import TREATMENTS
        choices = (('confirm_overlap', 'reject_overlap', 'unresolved') if part['treatment'] == 'claimed_overlap'
            else ('deduct', 'unresolved') if kind == 'receipt' else TREATMENTS[kind])
        self.fields['part'] = forms.ChoiceField(choices=((part['key'], part['key']),), widget=forms.HiddenInput)
        self.fields['finding'] = forms.ChoiceField(label='Source finding',
            choices=(('', 'Choose a finding'), *((key, FINDINGS[key]) for key in choices)))
        self.order_fields(('part', 'finding', 'basis', 'funding_reference', 'lineage_reference'))


class Decision(forms.Form):
    authority = forms.CharField(label='Your designation authority', max_length=2000, widget=forms.Textarea)
    note = forms.CharField(label='Independent finding or return reason', max_length=2000, widget=forms.Textarea)

    def __init__(self, role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        for key in service.CHECKS[role]:
            self.fields[key+'_verified'] = forms.TypedChoiceField(label=CHECK_LABELS[key],
                choices=(('', 'Choose a finding'), ('true', 'Verified'), ('false', 'Not verified')),
                coerce=lambda value: value == 'true')
            self.fields[key+'_basis'] = forms.CharField(label=CHECK_LABELS[key]+' — evidence and basis',
                max_length=2000, widget=forms.Textarea)

    def checks(self):
        return {key: dict(verified=self.cleaned_data[key+'_verified'], basis=self.cleaned_data[key+'_basis'])
            for key in service.CHECKS[self.role]}


def can_prepare(actor, package):
    owner = department_for_user(actor)
    return bool(owner and owner.pk == package.department_id and actor.is_active
        and has_budget_permission(actor, 'prepare_form1_packages') and not is_finance_uat_viewer(actor))


def original(request, public_id):
    return packages._read(get_object_or_404(Form1Package, public_id=public_id), request.user)


@login_required
@require_GET
def history(request, public_id):
    try:
        package = original(request, public_id)
        cards = []
        for record in package.treatment_proposals.all().iterator():
            retained = service.snapshot(record, request.user)
            cards.append(dict(public_id=record.public_id, version=record.version,
                prepared_at=record.prepared_at, status=STATUSES[retained['review']['status']]))
        return render(request, 'budget/form1_treatment_history.html', dict(package=package,
            can_prepare=can_prepare(request.user, package),
            page=Paginator(cards, 50).get_page(request.GET.get('page'))))
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)


@login_required
@require_http_methods(['GET', 'POST'])
def prepare(request, public_id):
    try:
        package = original(request, public_id)
        if not can_prepare(request.user, package):
            raise PermissionDenied('Use the designated Budget preparer for the original package.')
        latest = package.treatment_proposals.first()
        prior = service.verify(latest) if latest else None
        initial = {row['part']: row for row in prior['findings']} if prior else {}
        parts = package.payload['assembly']['payload']['philhealth_source']['payload']['parts']
        entities = {row['entity_key']: row['entity_label'] for row in package.payload['assembly']['payload']['members']}
        posted = request.POST if request.method == 'POST' else None
        form = Preparation(posted, request.FILES if posted is not None else None,
            initial={'expected_latest': latest.version if latest else 0})
        findings = [Finding(part, posted, prefix='part'+str(index),
            initial=initial.get(part['key'], {'part': part['key']})) for index, part in enumerate(parts)]
        status = 200
        if request.method == 'POST':
            valid_parts = [item.is_valid() for item in findings]
            if form.is_valid() and all(valid_parts):
                try:
                    record = service.prepare(package, request.user, findings=[item.cleaned_data for item in findings],
                        **form.cleaned_data)
                    return redirect('budget:form1_treatment_detail', public_id=record.public_id)
                except ValidationError as error:
                    form.add_error(None, error)
            status = 409
        return render(request, 'budget/form1_treatment_prepare.html', dict(package=package, form=form,
            findings=[dict(form=item, original=item.part, entity=entities[item.part['original_source']['entity']],
                column=COLUMN_LABELS[item.part['original_source']['column']], kind=item.part['original_source']['kind'],
                original_finding=FINDINGS.get(item.part['treatment'], 'Claimed overlap')) for item in findings]), status=status)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)


def render_detail(request, record, *, role=None, form=None, status=200):
    try:
        retained = service.snapshot(record, request.user)
        state = retained['review']
        owner = department_for_user(request.user)
        decisions = {(row['payload']['identity']['role'], row['payload']['identity']['actor_department_id'])
            for row in state['decisions']}
        actors = {row['payload']['identity']['actor_id'] for row in state['decisions']}
        decision_forms = []
        if (state['status'] not in ('reviewed', 'returned') and not is_finance_uat_viewer(request.user)
            and request.user.pk not in actors | {record.prepared_by_id, record.package.prepared_by_id}):
            for item in state['required_reviews']:
                name = item['role']
                if ((name, owner.pk) not in decisions and owner.pk == item['department_id']
                    and has_budget_permission(request.user, 'review_form1_package_'+name)):
                    decision_forms.append(dict(role=name, form=form if role == name else Decision(name)))
        can_export = False
        try:
            service._read(record, request.user, export=True)
        except PermissionDenied:
            pass
        else:
            can_export = True
        body = retained['payload']['draft']['payload']
        entities = {row['entity_key']: row['entity_label'] for row in record.package.payload['assembly']['payload']['members']}
        findings = [dict(entity=entities[row['original_part']['original_source']['entity']],
            column=COLUMN_LABELS[row['original_part']['original_source']['column']], kind=row['original_part']['original_source']['kind'],
            amount=row['original_part']['amount'], label=FINDINGS[row['finding']], **row) for row in body['findings']]
        return render(request, 'budget/form1_treatment_detail.html', dict(record=record, state=state,
            status=STATUSES[state['status']], decision_forms=decision_forms, can_export=can_export,
            decision_errors=form.non_field_errors() if form is not None else None,
            can_prepare=can_prepare(request.user, record.package),
            page=Paginator(findings, 50).get_page(request.GET.get('page'))), status=status)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)


@login_required
@require_GET
def detail(request, public_id):
    return render_detail(request, get_object_or_404(Form1TreatmentProposal, public_id=public_id))


@login_required
@require_POST
def review(request, public_id, role):
    if role not in service.CHECKS or request.POST.get('action') not in ('approve', 'return'):
        return HttpResponse('Choose a listed office and factual approval or return.', status=400)
    if is_finance_uat_viewer(request.user) or not has_budget_permission(request.user, 'review_form1_package_'+role):
        raise PermissionDenied('Use the designated independent office reviewer.')
    record = get_object_or_404(Form1TreatmentProposal, public_id=public_id)
    form = Decision(role, request.POST)
    try:
        record = service._read(record, request.user)
        if form.is_valid():
            service.review(record, request.user, role=role, approve=request.POST['action'] == 'approve',
                checks=form.checks(), authority=form.cleaned_data['authority'], note=form.cleaned_data['note'])
            return redirect('budget:form1_treatment_detail', public_id=record.public_id)
    except ValidationError as error:
        form.add_error(None, error)
    return render_detail(request, record, role=role, form=form, status=409)


@login_required
@require_GET
def export(request, public_id, kind):
    record = get_object_or_404(Form1TreatmentProposal, public_id=public_id)
    try:
        content, envelope = service.export(record, request.user, kind=kind)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=409)
    filename = f'form1-findings-{record.public_id}-v{record.version}.{kind}'
    archived = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='form1-treatment-findings', filename=filename,
        metadata=dict(output_checksum=envelope['checksum'], treatment_checksum=record.payload_checksum,
            numeric_adjustment_approved=False, form_issued=False))
    record_event(record.package, 'form1_treatment_exported', request.user,
        snapshot=dict(kind=kind, sha256=archived['sha256'], output_checksum=envelope['checksum']))
    response = HttpResponse(content, content_type='application/zip' if kind == 'zip' else 'application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-GRAND-Export-SHA256'] = archived['sha256']
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
