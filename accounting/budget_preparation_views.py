"""Guided source selection and explicit preparation; certification is separate."""
import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.http import QueryDict
from django.views.decorators.http import require_http_methods, require_POST

from . import budget_preparation as editor
from . import budget_preparation_forms as allocation_forms
from .models import Fund, JournalEntry


class Scope(forms.Form):
    fund = forms.ModelChoiceField(queryset=Fund.objects.none())
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Period start')
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Period end')
    q = forms.CharField(required=False, max_length=255, label='Journal reference contains')

    def __init__(self, *args, owner_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fund'].queryset = Fund.objects.filter(department_id=owner_id)

    def clean(self):
        values = super().clean()
        if values.get('start') and values.get('end') and values['end'] < values['start']:
            raise ValidationError('Period end must not precede its start.')
        return values


class JournalChoice(forms.ModelMultipleChoiceField):
    def label_from_instance(self, entry):
        return f'{entry.entry_date} · {entry.reference} · {entry.description}'


class Sources(forms.Form):
    entries = JournalChoice(queryset=JournalEntry.objects.none(), required=False,
        label='Posted journals for this batch', widget=forms.CheckboxSelectMultiple)


@login_required
@require_http_methods(['GET', 'POST'])
def select(request):
    owner_id = editor._owner(request.user)
    data = request.POST if request.method == 'POST' else request.GET
    scope = Scope(data or None, owner_id=owner_id)
    sources, page, basket, selected_rows = Sources(), None, '', []
    error, status, selected = '', 200, set()
    if scope.is_valid():
        values = scope.cleaned_data
        scope_key = {'actor': request.user.pk, 'owner': owner_id, 'fund': values['fund'].pk,
                     'start': values['start'].isoformat(), 'end': values['end'].isoformat()}
        eligible = JournalEntry.objects.filter(
            department_id=owner_id, fund=values['fund'], status=JournalEntry.POSTED,
            entry_date__range=(values['start'], values['end'])).order_by('entry_date', 'pk')
        page_number = data.get('page', '1')
        if request.method == 'POST':
            try:
                retained = None
                if data.get('basket'):
                    retained = signing.loads(data['basket'], salt='budget-preparation-selection', max_age=editor.MAX_AGE)
                    if retained['scope'] != scope_key:
                        raise PermissionDenied
                    selected = set(retained['selected'])
                sources = Sources(data)
                sources.fields['entries'].queryset = eligible.filter(pk__in=retained['shown']) if retained else eligible
                if not sources.is_valid():
                    raise ValidationError('A selected journal is no longer available on this page. Start a new selection if its scope changed.')
                checked = set(sources.cleaned_data['entries'].values_list('pk', flat=True))
                updated = (selected - set(retained['shown']) if retained else set()) | checked
                if data.get('remove'):
                    updated.discard(int(data['remove']))
                if len(updated) > 250:
                    raise ValidationError('A review batch may contain at most 250 journals. Your previous selection has been retained.')
                selected = updated
                if eligible.filter(pk__in=selected).count() != len(selected):
                    raise ValidationError('A retained journal is no longer available in this scope. Start a new selection; no batch was prepared.')
                action = 'remove' if data.get('remove') else data.get('action', 'prepare')
                if action == 'prepare':
                    prepared = editor.prepare(actor=request.user, fund_id=values['fund'].pk,
                        period_start=values['start'], period_end=values['end'],
                        entry_ids=list(eligible.filter(pk__in=selected).values_list('pk', flat=True)))
                    return _render_editor(request, prepared['context'], prepared['token'])
                if action == 'search':
                    page_number = 1
                elif action.startswith('page:'):
                    page_number = action.split(':', 1)[1]
                elif action not in ('save', 'remove'):
                    raise ValidationError('Choose a selection action from this page.')
            except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
                error, status = 'The retained selection expired or changed. Start a new source selection.', 400
            except ValidationError as exc:
                error, status = ' '.join(exc.messages), 400
        matches = eligible.filter(reference__icontains=values['q'])
        page = Paginator(matches, 50).get_page(page_number)
        shown = list(page.object_list.values_list('pk', flat=True))
        sources = Sources(initial={'entries': sorted(selected)})
        sources.fields['entries'].queryset = eligible.filter(pk__in=shown)
        selected_rows = list(eligible.filter(pk__in=selected))
        basket = signing.dumps({'scope': scope_key, 'selected': sorted(selected), 'shown': shown},
                               salt='budget-preparation-selection', compress=True)
    return render(request, 'accounting/budget_preparation_select.html',
        {'scope': scope, 'sources': sources, 'page': page, 'basket': basket,
         'selected_rows': selected_rows, 'selection_error': error}, status=status)


def _render_editor(request, context, token, data=None, status=200):
    basis = allocation_forms.Basis(data)
    groups = allocation_forms.journal_forms(context, data)
    if data is not None:
        proposals = allocation_forms.proposals(groups)
        if basis.is_valid() and proposals is not None:
            try:
                records = editor.submit(actor=request.user, token=token, proposals=proposals,
                    reason=basis.cleaned_data['reason'], evidence_reference=basis.cleaned_data['evidence_reference'])
            except ValidationError as exc:
                basis.add_error(None, exc)
                status = 409
            else:
                return redirect('accounting:budget_attribution_detail', batch_id=records[0].batch_id)
        elif status == 200:
            status = 400
    return render(request, 'accounting/budget_preparation_editor.html',
        {'context': context, 'token': token, 'basis': basis, 'groups': groups}, status=status)


@login_required
@require_POST
def submit(request):
    token = request.POST.get('context', '')
    data = request.POST
    if 'allocations_payload' in request.POST:
        try:
            pairs = json.loads(request.POST['allocations_payload'])
            if not isinstance(pairs, list) or any(not isinstance(pair, list) or len(pair) != 2
                    or not all(isinstance(value, str) for value in pair) for pair in pairs):
                raise ValueError
            data = QueryDict('', mutable=True)
            for key, value in pairs:
                if key in ('context', 'csrfmiddlewaretoken', 'allocations_payload'):
                    raise ValueError
                data.appendlist(key, value)
        except (ValueError, TypeError):
            return render(request, 'accounting/budget_preparation_expired.html',
                          {'errors': ['The entered allocation data could not be read.']}, status=400)
    try:
        context = editor.read(actor=request.user, token=token)
    except ValidationError as exc:
        try:
            context = editor.read(actor=request.user, token=token, for_redisplay=True)
        except ValidationError:
            return render(request, 'accounting/budget_preparation_expired.html', {'errors': exc.messages}, status=409)
        return _render_editor(request, context, token, data, status=409)
    return _render_editor(request, context, token, data)
