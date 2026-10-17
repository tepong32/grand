"""Read-only SPC source worksheets over the existing reviewed reconstruction."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import OuterRef, Subquery
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import property_determinations as properties, property_movements as movements
from .access import can as can_asset, gso_department_for_user
from .models import Asset, PropertyDetermination


def can_prepare(actor):
    return (properties.can_act(actor, 'view') and movements.can_act(actor, 'view')
            and can_asset(actor, 'export'))


def _source_assets(actor):
    latest = PropertyDetermination.objects.filter(asset_id=OuterRef('pk'), status='verified').order_by('-decided_at', '-pk')
    return Asset.objects.filter(department_id=gso_department_for_user(actor).pk).annotate(
        supplied_class=Subquery(latest.values('property_class')[:1]),
        supplied_fund=Subquery(latest.values('fund_label')[:1]),
        supplied_treatment=Subquery(latest.values('treatment')[:1]),
    ).filter(supplied_treatment='semi_expendable').exclude(supplied_class='').exclude(supplied_fund='')


class SourceCardForm(forms.Form):
    property_class = forms.ChoiceField(label='Class shown in verified property documents')
    fund = forms.ChoiceField(label='Fund shown in verified property documents')
    cutoff = forms.DateField(label='Source movements through', widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, pairs, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['property_class'].choices = [('', 'Choose a supplied class')] + [(v, v) for v in sorted({p[0] for p in pairs})]
        self.fields['fund'].choices = [('', 'Choose a supplied fund')] + [(v, v) for v in sorted({p[1] for p in pairs})]

    def clean_cutoff(self):
        value = self.cleaned_data['cutoff']
        if value > timezone.localdate():
            raise ValidationError('Choose today or an earlier source date.')
        return value


@never_cache
@login_required
@require_GET
def spc_source_worksheet(request):
    if not can_prepare(request.user):
        raise PermissionDenied
    assets = _source_assets(request.user)
    # Preserve exact supplied labels under both case-sensitive and MySQL collations.
    pairs = set(assets.order_by().values_list('supplied_class', 'supplied_fund'))
    form = SourceCardForm(request.GET or None, pairs=pairs, initial={'cutoff': timezone.localdate()})
    prepared, rows = False, []
    if form.is_valid():
        prepared = True
        data = form.cleaned_data
        for asset in assets.filter(supplied_class=data['property_class'], supplied_fund=data['fund']).order_by('pk'):
            if (asset.supplied_class, asset.supplied_fund) != (data['property_class'], data['fund']):
                continue
            try:
                projection = movements.project(actor=request.user, asset=asset, cutoff=data['cutoff'])
            except ValidationError as error:
                projection = {'issues': error.messages, 'opening': None, 'rows': [], 'balance': None}
            if not projection['issues']:
                facts = projection['opening'].source_snapshot['determination']
                if (facts['treatment'], facts['property_class'], facts['fund_label']) != ('semi_expendable', data['property_class'], data['fund']):
                    projection['issues'].append('The reviewed opening uses a different class or fund. Reconcile its source before combining entries.')
            if projection['issues']:
                projection = {**projection, 'balance': None, 'opening': None, 'rows': []}
            rows.append({'asset': asset, 'projection': projection})
    return render(request, 'inventory/spc_source_worksheet.html', {
        'form': form, 'prepared': prepared, 'rows': rows,
        'details': form.cleaned_data if prepared else {},
    })
