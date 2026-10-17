"""Fill-in PAR preparation; does not issue numbers, sign or persist records."""
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import formset_factory
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .property_determinations import can_act


class PARHeaderForm(forms.Form):
    lgu = forms.CharField(label='LGU / municipality', required=False, max_length=180)
    office = forms.CharField(label='Office', required=False, max_length=160)
    fund = forms.CharField(label='Fund (as supplied)', required=False, max_length=160)
    form_reference = forms.CharField(label='Local form reference / revision', required=False, max_length=180)
    number = forms.CharField(label='PAR number (supplied, not generated)', required=False, max_length=80)
    numbering = forms.CharField(label='Local numbering instructions', required=False, max_length=240)
    issuer = forms.CharField(label='Issuer name', required=False, max_length=160)
    issuer_role = forms.CharField(label='Issuer designation / office', required=False, max_length=180)
    recipient = forms.CharField(label='Recipient name', required=False, max_length=160)
    recipient_role = forms.CharField(label='Recipient designation / office', required=False, max_length=180)


class PARLineForm(forms.Form):
    quantity = forms.DecimalField(required=False, min_value=Decimal("0.001"), max_digits=12, decimal_places=3)
    unit = forms.CharField(required=False, max_length=30)
    description = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={'rows':2}))
    property_number = forms.CharField(required=False, max_length=100)
    acquisition_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))
    acquisition_cost = forms.DecimalField(label='Acquisition cost (as supplied)', required=False, min_value=0, max_digits=15, decimal_places=2)


PARLines = formset_factory(PARLineForm, extra=5, max_num=5, validate_max=True, absolute_max=5)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def par_preparation(request):
    if not can_act(request.user, 'view'):
        raise PermissionDenied
    data = request.POST if request.method == 'POST' else None
    header = PARHeaderForm(data, prefix='header')
    lines = PARLines(data, prefix='lines')
    ready = request.method == 'POST' and header.is_valid() and lines.is_valid()
    return render(request, 'inventory/par_preparation.html', {
        'header':header, 'lines':lines, 'ready':ready,
        'details': header.cleaned_data if ready else {},
        'print_lines': [form.cleaned_data for form in lines] if ready else [],
    })
