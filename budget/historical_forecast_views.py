from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .access import budget_permission_required, department_for_user
from .historical_forecasts import row_key, source_digest, save_forecast
from .models import BudgetVersion
from .planning_context import build_context

SALT = 'budget.historical-forecast.v1'


class ForecastForm(forms.Form):
    preview = forms.CharField(widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=(('save', 'Save forecast'), ('clear', 'Clear forecast')))
    amount = forms.DecimalField(required=False, min_value=0, max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='July–December estimate', help_text='Use an explicit zero only when supported by your forecast.')
    as_of = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), label='Prepared as of')
    basis = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        label='Planning basis and evidence reference')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}), label='Reason for this change')

    def clean(self):
        data = super().clean()
        if data.get('action') == 'save':
            for name in ('amount', 'as_of', 'basis'):
                if data.get(name) is None or data.get(name) == '':
                    self.add_error(name, 'Required when saving a forecast.')
        return data


@require_http_methods(['GET', 'POST'])
@budget_permission_required('prepare_budget_proposals')
def edit(request, public_id, key):
    version = get_object_or_404(BudgetVersion, public_id=public_id,
        department_id=department_for_user(request.user).pk)
    stored = version.historical_forecasts.get(key)
    row, problem = None, ''
    try:
        context = build_context(version, request.user) if version.status in (version.DRAFT, version.RETURNED) else version.planning_context_snapshot
        row = next((item for item in context.get('certified_schedule', []) if row_key(item) == key), None)
    except ValidationError as exc:
        problem = ' '.join(exc.messages)
    if not stored and (not row or row['has_proposal']):
        raise Http404
    editable = version.status in (version.DRAFT, version.RETURNED)
    token = signing.dumps({'actor': request.user.pk, 'version': str(version.public_id),
        'state': version.state_version, 'key': key, 'source_digest': source_digest(row) if row else None}, salt=SALT)
    form = ForecastForm(request.POST if request.method == 'POST' else None,
        initial={'preview': token, **{name: (stored or {}).get(name) for name in ('amount', 'as_of', 'basis')}})
    status = 200
    if request.method == 'POST':
        if form.is_valid():
            try:
                preview = signing.loads(form.cleaned_data['preview'], salt=SALT, max_age=86400)
                if preview['actor'] != request.user.pk or preview['version'] != str(version.public_id) or preview['key'] != key:
                    raise ValidationError('This preview belongs to another user, proposal or object.')
                save_forecast(version=version, actor=request.user, key=key,
                    expected_state_version=preview['state'], expected_source_digest=preview['source_digest'],
                    clear=form.cleaned_data['action'] == 'clear',
                    **{name: form.cleaned_data.get(name) for name in ('amount', 'as_of', 'basis', 'reason')})
            except (signing.BadSignature, KeyError, TypeError, ValueError):
                form.add_error(None, 'The forecast preview expired or is invalid. Reload before trying again.')
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Historical forecast change retained with its dated basis and audit evidence.')
                return redirect('budget:version_detail', public_id=version.public_id)
        status = 409
    return render(request, 'budget/historical_forecast.html', {'version': version, 'form': form,
        'row': row or (stored or {}).get('row'), 'stored': stored, 'problem': problem,
        'editable': editable, 'can_save': editable and row and not row['has_proposal'] and (row['prior_rows'] or row['half_rows'])}, status=status)
