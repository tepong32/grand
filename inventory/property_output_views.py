"""Fill-in property drafts; never issue numbers, sign or persist records."""
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .property_determinations import can_act
from .access import can as can_asset, gso_department_for_user
from .models import Asset
from .draft_lines import MAX_DRAFT_LINES, DraftLines, add_lines


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


PARLines = formset_factory(PARLineForm, formset=DraftLines, extra=5, max_num=MAX_DRAFT_LINES,
                          validate_max=True, absolute_max=MAX_DRAFT_LINES, can_delete=True)


def _par_preparation(request, source_asset=None):
    if not can_act(request.user, 'view'):
        raise PermissionDenied
    data = request.POST if request.method == 'POST' else None
    header = PARHeaderForm(data, prefix='header')
    initial = [{'description': source_asset.asset_name, 'quantity': source_asset.quantity}] if source_asset else None
    lines = PARLines(data, prefix='lines', initial=initial)
    if data is None and initial:
        lines.extra = 5 - len(initial)
    adding = request.method == 'POST' and request.POST.get('action') == 'add_lines'
    notice = ''
    if adding:
        lines, notice = add_lines(request.POST, PARLines, initial=initial)
    valid = request.method == 'POST' and header.is_valid() and lines.is_valid()
    ready = valid and not adding
    return render(request, 'inventory/par_preparation.html', {
        'header':header, 'lines':lines, 'ready':ready, 'source_asset':source_asset,
        'invalid': request.method == 'POST' and not valid,
        'line_notice': notice, 'can_add_lines': lines.total_form_count() < MAX_DRAFT_LINES,
        'details': header.cleaned_data if ready else {},
        'print_lines': [form.cleaned_data for form in lines if not form.cleaned_data.get('DELETE')] if ready else [],
    })


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def par_preparation(request):
    return _par_preparation(request)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def par_asset_preparation(request, pk):
    if not can_act(request.user, 'view') or not can_asset(request.user, 'export'):
        raise PermissionDenied
    asset = get_object_or_404(Asset, pk=pk, department_id=gso_department_for_user(request.user).pk)
    return _par_preparation(request, source_asset=asset)


class ICSHeaderForm(PARHeaderForm):
    number = forms.CharField(label='ICS number (supplied, not generated)', required=False, max_length=80)


def _check_supplied_total(form, quantity_field):
    data = form.cleaned_data
    quantity, unit_cost, total_cost = (data.get(name) for name in (quantity_field, 'unit_cost', 'total_cost'))
    if all(value is not None for value in (quantity, unit_cost, total_cost)) and quantity * unit_cost != total_cost:
        form.add_error('total_cost', 'The supplied quantity and unit cost do not match this total. Check the source amounts.')
    return data


class ICSLineForm(forms.Form):
    quantity = forms.IntegerField(required=False, min_value=1, max_value=999999999)
    unit = forms.CharField(required=False, max_length=30)
    description = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={'rows': 2}))
    inventory_number = forms.CharField(label='Inventory item number (as supplied)', required=False, max_length=100)
    unit_cost = forms.DecimalField(label='Unit cost (as supplied)', required=False, min_value=0, max_digits=18, decimal_places=2)
    total_cost = forms.DecimalField(label='Total cost (as supplied)', required=False, min_value=0, max_digits=18, decimal_places=2)
    useful_life = forms.CharField(label='Estimated useful life (as supplied)', required=False, max_length=120)

    def clean(self):
        super().clean()
        return _check_supplied_total(self, 'quantity')


class SPCHeaderForm(forms.Form):
    lgu = forms.CharField(label='LGU / municipality', required=False, max_length=180)
    fund = forms.CharField(label='Fund (as supplied)', required=False, max_length=160)
    property_class = forms.CharField(label='Semi-expendable property class (as supplied)', required=False, max_length=160)
    description = forms.CharField(label='Item description', required=False, max_length=500, widget=forms.Textarea(attrs={'rows': 2}))
    property_number = forms.CharField(label='Property number (as supplied)', required=False, max_length=100)
    useful_life = forms.CharField(label='Estimated useful life (as supplied)', required=False, max_length=120)
    form_reference = forms.CharField(label='Local form reference / revision', required=False, max_length=180)


class SPCLineForm(forms.Form):
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    reference = forms.CharField(label='Source document / item reference', required=False, max_length=180)
    received = forms.IntegerField(label='Quantity received (as supplied)', required=False, min_value=0, max_value=999999999)
    unit_cost = forms.DecimalField(label='Receipt unit cost (as supplied)', required=False, min_value=0, max_digits=18, decimal_places=2)
    total_cost = forms.DecimalField(label='Receipt total cost (as supplied)', required=False, min_value=0, max_digits=18, decimal_places=2)
    issued = forms.IntegerField(label='Quantity issued / transferred / disposed (as supplied)', required=False, min_value=0, max_value=999999999)
    office_officer = forms.CharField(label='Office / officer (as supplied)', required=False, max_length=180)
    balance = forms.IntegerField(label='Balance from source (not calculated)', required=False, min_value=0, max_value=999999999)
    remarks = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        super().clean()
        return _check_supplied_total(self, 'received')


ICSLines = formset_factory(ICSLineForm, formset=DraftLines, extra=5, max_num=MAX_DRAFT_LINES,
                          validate_max=True, absolute_max=MAX_DRAFT_LINES, can_delete=True)
SPCLines = formset_factory(SPCLineForm, formset=DraftLines, extra=5, max_num=MAX_DRAFT_LINES,
                          validate_max=True, absolute_max=MAX_DRAFT_LINES, can_delete=True)


def _preparation(request, *, kind, title, header_class, line_set, source_asset=None):
    if not can_act(request.user, 'view'):
        raise PermissionDenied
    data = request.POST if request.method == 'POST' else None
    header = header_class(data, prefix='header')
    initial = [{'description': source_asset.asset_name, 'quantity': source_asset.quantity,
                'unit_cost': source_asset.unit_cost}] if source_asset else None
    lines = line_set(data, prefix='lines', initial=initial)
    if data is None and initial:
        lines.extra = 5 - len(initial)
    adding = request.method == 'POST' and request.POST.get('action') == 'add_lines'
    notice = ''
    if adding:
        lines, notice = add_lines(request.POST, line_set, initial=initial)
    valid = request.method == 'POST' and header.is_valid() and lines.is_valid()
    ready = valid and not adding
    return render(request, 'inventory/property_preparation.html', {
        'kind': kind, 'title': title, 'header': header, 'lines': lines, 'ready': ready,
        'invalid': request.method == 'POST' and not valid,
        'line_notice': notice, 'can_add_lines': lines.total_form_count() < MAX_DRAFT_LINES,
        'source_asset': source_asset,
        'details': header.cleaned_data if ready else {},
        'print_lines': [form.cleaned_data for form in lines if not form.cleaned_data.get('DELETE')] if ready else [],
    })


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def ics_preparation(request):
    return _preparation(request, kind='ICS', title='Inventory Custodian Slip',
                        header_class=ICSHeaderForm, line_set=ICSLines)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def ics_asset_preparation(request, pk):
    if not can_act(request.user, 'view') or not can_asset(request.user, 'export'):
        raise PermissionDenied
    asset = get_object_or_404(Asset, pk=pk, department_id=gso_department_for_user(request.user).pk)
    return _preparation(request, kind='ICS', title='Inventory Custodian Slip',
                        header_class=ICSHeaderForm, line_set=ICSLines, source_asset=asset)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def spc_preparation(request):
    return _preparation(request, kind='SPC', title='Semi-expendable Property Card',
                        header_class=SPCHeaderForm, line_set=SPCLines)
