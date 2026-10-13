"""Scoped whole-batch review of retained expenditure classifications."""
import json
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from src.export_archive import archive_export
from .access import department_for_user
from . import budget_attributions as service
from .models import BudgetExpenditureAttribution as Attribution, Fund


class Filters(forms.Form):
    q = forms.CharField(required=False, max_length=255, label='Journal, evidence reference or preparer')
    fund = forms.ModelChoiceField(required=False, queryset=Fund.objects.none())
    status = forms.ChoiceField(required=False, choices=(('', 'All decisions'),
        ('submitted', 'For independent review'), ('approved', 'Review recorded'), ('returned', 'Returned')))
    start = forms.DateField(required=False, label='Covered from', widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(required=False, label='Covered through', widget=forms.DateInput(attrs={'type': 'date'}))
    entry = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, owner_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fund'].queryset = Fund.objects.filter(department_id=owner_id)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise ValidationError('Covered through must not precede covered from.')
        return data


class Decision(forms.Form):
    note = forms.CharField(max_length=2000, label='Review basis or required correction',
                           widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}))
    decision = forms.ChoiceField(choices=(('approve', 'Record review'), ('return', 'Return for correction')))


def _visible(actor):
    if not any(service.permitted(actor, action) for action in ('view', 'prepare', 'review', 'export')):
        raise PermissionDenied
    return Attribution.objects.filter(department_id=department_for_user(actor).pk)


def _batch(actor, batch_id):
    if not _visible(actor).filter(batch_id=batch_id).exists():
        raise Http404
    records = list(Attribution.objects.filter(batch_id=batch_id).select_related('entry__fund').order_by('entry_id'))
    owner_id = department_for_user(actor).pk
    if any(record.department_id != owner_id for record in records):
        raise Http404
    first = records[0]
    fields = ('prepared_by_id', 'prepared_at', 'period_start', 'period_end', 'status',
              'reviewed_by_id', 'reviewed_at', 'review_note')
    for record in records:
        service.verify(record)
        if (record.entry.fund_id != first.entry.fund_id
                or any(getattr(record, field) != getattr(first, field) for field in fields)):
            raise ValidationError('The retained batch does not reproduce one complete group decision.')
    return records


@login_required
@require_GET
def register(request):
    query = _visible(request.user)
    form = Filters(request.GET, owner_id=department_for_user(request.user).pk)
    status = ''
    if form.is_valid():
        data = form.cleaned_data
        match = query
        if data['q']:
            match = match.filter(Q(entry__reference__icontains=data['q'])
                | Q(evidence_reference__icontains=data['q']) | Q(prepared_by_label__icontains=data['q']))
        if data['entry']:
            match = match.filter(entry_id=data['entry'])
        # A matching journal selects its entire batch, never a partial review group.
        query = query.filter(batch_id__in=match.order_by().values('batch_id'))
        if data['fund']:
            query = query.filter(entry__fund=data['fund'])
        if data['start']:
            query = query.filter(period_end__gte=data['start'])
        if data['end']:
            query = query.filter(period_start__lte=data['end'])
        status = data['status']
    else:
        query = query.none()
    batches = query.order_by().values('batch_id', 'prepared_at', 'prepared_by_label',
        'entry__fund__code', 'period_start', 'period_end').annotate(journals=Count('pk'),
        reference=Min('entry__reference'), stage=Min('status'), last_stage=Max('status'))
    if status:
        batches = batches.filter(stage=status, last_stage=status)
    page = Paginator(batches.order_by('-prepared_at', '-batch_id'), 50).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'accounting/budget_attribution_register.html',
                  {'form': form, 'page': page, 'querystring': params.urlencode(),
                   'can_prepare': service.permitted(request.user, 'prepare')})


def _detail(request, records, decision_form=None, status=200):
    items = []
    unresolved = 0
    for record in records:
        source = record.source_snapshot['journal']
        lines = {line['id']: line for line in source['lines']}
        rows = []
        originals = {line['id']: (entry, line) for entry in record.source_snapshot.get('claim_sources', [])
                     for line in entry['lines']}
        reversal_sources = {line['id']: (entry, line) for entry in record.source_snapshot.get('ancestors', [])
                            for line in entry['lines']}
        for allocation in record.allocations:
            unresolved += allocation['disposition'] == 'unresolved'
            original = originals.get(allocation.get('claim_component', {}).get('source_line_id'))
            reversed_line = reversal_sources.get(allocation.get('reversal_source_line_id'))
            rows.append({'allocation': allocation, 'line': lines[allocation['line_id']],
                'purpose': allocation['purpose'].replace('_', ' ').capitalize(),
                'source_basis': allocation.get('claim_component_basis', '').replace('_', ' ').capitalize(),
                'reversal_original': (f"{reversed_line[0]['reference']} · line {reversed_line[1]['sequence']} · {reversed_line[1]['account']['code']}"
                                      if reversed_line else ''),
                'original': (f"{original[0]['reference']} · line {original[1]['sequence']} · {original[1]['account']['code']}"
                             if original else '')})
        items.append({'record': record, 'source': source, 'rows': rows,
                      'included': sum((Decimal(row['signed_amount']) for row in record.allocations
                                       if row['disposition'] == 'include'), Decimal('0.00'))})
    first = records[0]
    can_review = service.permitted(request.user, 'review') and all(
        record.status == Attribution.SUBMITTED and record.prepared_by_id != request.user.pk for record in records)
    return render(request, 'accounting/budget_attribution_detail.html', {
        'first': first, 'items': items, 'unresolved': unresolved, 'can_review': can_review,
        'can_export': service.permitted(request.user, 'export'),
        'decision_form': decision_form if decision_form is not None else Decision()}, status=status)


@login_required
@require_GET
def detail(request, batch_id):
    try:
        records = _batch(request.user, batch_id)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409, content_type='text/plain; charset=utf-8')
    return _detail(request, records)


@login_required
@require_POST
def decide(request, batch_id):
    if not service.permitted(request.user, 'review'):
        raise PermissionDenied
    form = Decision(request.POST)
    try:
        records = _batch(request.user, batch_id)
        if form.is_valid():
            try:
                service.review_batch(batch_id=batch_id, actor=request.user,
                    approve=form.cleaned_data['decision'] == 'approve', note=form.cleaned_data['note'])
            except ValidationError as exc:
                form.add_error(None, exc)
                return _detail(request, _batch(request.user, batch_id), form, status=409)
            messages.success(request, 'The complete batch review was recorded.')
            return redirect('accounting:budget_attribution_detail', batch_id=batch_id)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409, content_type='text/plain; charset=utf-8')
    return _detail(request, records, form, status=400)


@login_required
@require_GET
def export(request, batch_id):
    if not service.permitted(request.user, 'export'):
        raise PermissionDenied
    try:
        records = _batch(request.user, batch_id)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=409, content_type='text/plain; charset=utf-8')
    payload = {'schema': 1, 'kind': 'budget_expenditure_classification_review',
        'certificate': False, 'batch_id': str(batch_id), 'records': [
            {'review': service.projection(record), 'source_snapshot': record.source_snapshot} for record in records]}
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
    filename = f'budget-expenditure-review-{batch_id}.json'
    receipt = archive_export(content=content, department=department_for_user(request.user), user=request.user,
        category='budget-expenditure-reviews', filename=filename,
        metadata={'batch_id': str(batch_id), 'classification_only': True})
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    response['X-GRAND-Export-SHA256'] = receipt['sha256']
    response['X-GRAND-Export-Relative-Path'] = receipt['relative_path']
    return response
