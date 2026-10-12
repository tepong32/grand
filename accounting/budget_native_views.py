"""Preparation, whole-cohort certification history and retained evidence download."""
import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from src.export_archive import archive_export
from .access import department_for_user
from . import budget_native_certifications as service
from . import budget_native_statements as calculation
from .models import Fund, NativeBudgetStatement as Statement

SALT = 'accounting.native-statement-preview.v1'


class Scope(forms.Form):
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    start = forms.DateField(label='Period begins', widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='Period ends', widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fund'].queryset = Fund.objects.filter(department_id=department_for_user(actor).pk)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        data = super().clean()
        start, end = data.get('start'), data.get('end')
        if start and end and (start.year != end.year or (start.month, start.day) != (1, 1)
                or (end.month, end.day) not in ((6, 30), (12, 31))):
            raise ValidationError('Use a January–June or full calendar-year period.')
        return data


class Preparation(Scope):
    context = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, label='Preparation explanation', widget=forms.Textarea(attrs={'rows': 3}))
    coverage = forms.CharField(max_length=2000, label='How complete source coverage was checked', widget=forms.Textarea(attrs={'rows': 3}))
    evidence_reference = forms.CharField(max_length=255, label='Supporting evidence reference')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('auto_id', 'native_preparation_%s')
        super().__init__(*args, **kwargs)
        for name in ('fund', 'start', 'end'):
            self.fields[name].widget = forms.HiddenInput()


class Decision(forms.Form):
    decision = forms.ChoiceField(choices=(('certify', 'Record native certification'), ('return', 'Return for correction')))
    authority = forms.CharField(max_length=255, label='Local Accountant designation or certification authority')
    note = forms.CharField(max_length=2000, label='Independent coverage review or required correction',
                           widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


def _visible(actor):
    if not any(service.permitted(actor, action) for action in ('view', 'prepare', 'certify', 'export')):
        raise PermissionDenied
    return Statement.objects.filter(department_id=department_for_user(actor).pk)


def _record(actor, public_id):
    record = get_object_or_404(_visible(actor).select_related('fund'), public_id=public_id)
    service.verify(record)
    return record


def _conflict(exc):
    return HttpResponse(' '.join(exc.messages), status=409, content_type='text/plain; charset=utf-8')


@login_required
@require_GET
def register(request):
    query = _visible(request.user).select_related('fund').order_by('-prepared_at', '-pk')
    q = request.GET.get('q', '').strip()[:255]
    if q:
        query = query.filter(Q(prepared_by_label__icontains=q) | Q(authority__icontains=q)
                             | Q(payload__evidence_reference__icontains=q))
    stage = request.GET.get('status', '')
    if stage:
        query = query.filter(status=stage) if stage in (Statement.SUBMITTED, Statement.CERTIFIED, Statement.RETURNED) else query.none()
    page = Paginator(query, 50).get_page(request.GET.get('page'))
    params = request.GET.copy(); params.pop('page', None)
    return render(request, 'accounting/budget_native_register.html', {'page': page, 'q': q, 'stage': stage,
        'querystring': params.urlencode(), 'can_prepare': service.permitted(request.user, 'prepare')})


@login_required
@require_http_methods(['GET', 'POST'])
def prepare(request):
    if not service.permitted(request.user, 'prepare'):
        raise PermissionDenied
    preview, preparation, status = None, None, 200
    scope = Scope(request.GET or None, actor=request.user)
    if request.method == 'POST':
        preparation = Preparation(request.POST, actor=request.user)
        if preparation.is_valid():
            values = preparation.cleaned_data
            try:
                context = signing.loads(values['context'], salt=SALT, max_age=86400)
                expected = {'actor': request.user.pk, 'owner': department_for_user(request.user).pk,
                    'fund': values['fund'].pk, 'start': values['start'].isoformat(), 'end': values['end'].isoformat()}
                if context.get('scope') != expected:
                    raise ValidationError('The preview belongs to another actor or period. Load a fresh preview.')
                record = service.propose(actor=request.user, fund_id=values['fund'].pk,
                    period_start=values['start'], period_end=values['end'], expected_latest=context['latest'],
                    expected_source_checksum=context['source'], reason=values['reason'],
                    coverage=values['coverage'], evidence_reference=values['evidence_reference'])
            except signing.BadSignature:
                preparation.add_error(None, 'The preview expired or changed. Load a fresh preview; entered explanations remain below.')
                status = 409
            except ValidationError as exc:
                preparation.add_error(None, exc); status = 409
            else:
                return redirect('accounting:budget_native_detail', public_id=record.public_id)
        else:
            status = 400
    elif scope.is_bound and scope.is_valid():
        values = scope.cleaned_data
        try:
            prepared = calculation.prepare(actor=request.user, fund_id=values['fund'].pk,
                period_start=values['start'], period_end=values['end'])
            preview = prepared['statement']['payload']
            latest = _visible(request.user).filter(fund=values['fund'], period_start=values['start'],
                period_end=values['end']).aggregate(number=Max('version'))['number'] or 0
            context = signing.dumps({'scope': {'actor': request.user.pk, 'owner': department_for_user(request.user).pk,
                'fund': values['fund'].pk, 'start': values['start'].isoformat(), 'end': values['end'].isoformat()},
                'source': prepared['source']['checksum'], 'latest': latest}, salt=SALT, compress=True)
            if preview['classification_complete']:
                preparation = Preparation(actor=request.user, initial={**values, 'context': context})
        except ValidationError as exc:
            scope.add_error(None, exc); status = 409
    return render(request, 'accounting/budget_native_prepare.html',
        {'scope': scope, 'preparation': preparation, 'preview': preview}, status=status)


def _detail(request, record, form=None, status=200):
    current, warning = False, ''
    try:
        current = service.is_current(record, request.user)
    except ValidationError as exc:
        warning = ' '.join(exc.messages)
    return render(request, 'accounting/budget_native_detail.html', {'record': record,
        'statement': record.payload['statement']['payload'], 'current': current, 'warning': warning,
        'can_export': service.permitted(request.user, 'export'),
        'can_decide': service.permitted(request.user, 'certify') and record.status == Statement.SUBMITTED
            and record.prepared_by_id != request.user.pk,
        'decision_form': form if form is not None else Decision()}, status=status)


@login_required
@require_GET
def detail(request, public_id):
    try:
        return _detail(request, _record(request.user, public_id))
    except ValidationError as exc:
        return _conflict(exc)


@login_required
@require_POST
def decide(request, public_id):
    if not service.permitted(request.user, 'certify'):
        raise PermissionDenied
    form = Decision(request.POST)
    try:
        record = _record(request.user, public_id)
        if form.is_valid():
            try:
                service.decide(statement_id=record.pk, actor=request.user,
                    certify=form.cleaned_data['decision'] == 'certify', authority=form.cleaned_data['authority'],
                    note=form.cleaned_data['note'])
            except ValidationError as exc:
                form.add_error(None, exc)
                return _detail(request, _record(request.user, public_id), form, status=409)
            messages.success(request, 'The native statement decision was recorded.')
            return redirect('accounting:budget_native_detail', public_id=public_id)
        return _detail(request, record, form, status=400)
    except ValidationError as exc:
        return _conflict(exc)


@login_required
@require_GET
def export(request, public_id):
    if not service.permitted(request.user, 'export'):
        raise PermissionDenied
    try:
        record = _record(request.user, public_id)
    except ValidationError as exc:
        return _conflict(exc)
    content = json.dumps({'kind': 'retained_native_budget_statement', 'schema': 1,
        'preparation': record.payload, 'payload_checksum': record.payload_checksum,
        'decision': service.decision_payload(record), 'decision_checksum': record.decision_checksum},
        sort_keys=True, ensure_ascii=False, indent=2).encode('utf-8')
    filename = f'native-budget-statement-{record.public_id}-{record.status}.json'
    receipt = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='native-budget-statements', filename=filename,
        metadata={'public_id': str(record.public_id), 'status': record.status, 'native_evidence': True})
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-GRAND-Export-SHA256'] = receipt['sha256']
    return response
