"""Unsigned supplied supplies reports; never copy or alter the live stock ledger."""
from decimal import localcontext

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import formset_factory
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import can_stock, in_gso_scope
from .rpcppe_drafts import RPCPPELineForm


class SupplyHeaderForm(forms.Form):
    lgu = forms.CharField(label="LGU / municipality", required=False, max_length=180)
    office = forms.CharField(label="Office", required=False, max_length=160)
    fund = forms.CharField(label="Fund label (as supplied)", required=False, max_length=160)
    form_reference = forms.CharField(label="Local form reference / revision", required=False, max_length=180)
    prepared_by = forms.CharField(label="Prepared by (name / designation placeholder)", required=False, max_length=180)
    reviewed_by = forms.CharField(label="Review / approval name and designation (as supplied)", required=False, max_length=180)


class RPCIHeaderForm(SupplyHeaderForm):
    inventory_type = forms.CharField(label="Type of inventory (as supplied)", required=False, max_length=180)
    as_of = forms.DateField(label="Inventory as of (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    accountable_officer = forms.CharField(label="Accountable officer name (as supplied)", required=False, max_length=160)
    designation = forms.CharField(label="Accountable officer designation / office", required=False, max_length=180)
    assumption_date = forms.DateField(label="Date accountability assumed (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))


class RPCILineForm(RPCPPELineForm):
    card_name = "stock card"
    property_number = None
    stock_number = forms.CharField(label="Stock number (as supplied)", required=False, max_length=100)
    card_quantity = forms.DecimalField(label="Quantity per stock card (as supplied)", required=False, min_value=0, max_digits=12, decimal_places=3)
    field_order = ("article", "description", "stock_number", "unit", "unit_value", "card_quantity",
                   "counted_quantity", "difference_value", "remarks")


class RSMIHeaderForm(SupplyHeaderForm):
    number = forms.CharField(label="Report / control number (supplied, not generated)", required=False, max_length=80)
    period_start = forms.DateField(label="Report period from (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(label="Report period through (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        start, end = data.get("period_start"), data.get("period_end")
        if start is not None and end is not None and start > end:
            self.add_error("period_end", "The report period cannot end before it starts.")
        return data


class RSMILineForm(forms.Form):
    source_date = forms.DateField(label="Source date (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    reference = forms.CharField(label="RIS / source reference (as supplied)", required=False, max_length=180)
    stock_number = forms.CharField(label="Stock number (as supplied)", required=False, max_length=100)
    description = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
    unit = forms.CharField(required=False, max_length=30)
    recipient_office = forms.CharField(label="Receiving office / recipient (as supplied)", required=False, max_length=180)
    quantity = forms.DecimalField(label="Quantity issued (as supplied)", required=False, min_value=0, max_digits=12, decimal_places=3)
    unit_cost = forms.DecimalField(label="Unit cost (as supplied)", required=False, min_value=0, max_digits=18, decimal_places=2)
    amount = forms.DecimalField(label="Line amount (as supplied; not calculated)", required=False, min_value=0, max_digits=18, decimal_places=2)
    remarks = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        data = super().clean()
        quantity, unit, amount = (data.get(name) for name in ("quantity", "unit_cost", "amount"))
        if all(value is not None for value in (quantity, unit, amount)):
            with localcontext() as context:
                context.prec = 40
                expected = quantity * unit
            if amount != expected:
                self.add_error("amount", "Check quantity × unit cost against the supplied line amount. No rounding is inferred; leave the amount blank if it needs Accounting review.")
        return data


RPCILines = formset_factory(RPCILineForm, extra=5, max_num=5, validate_max=True, absolute_max=5)
RSMILines = formset_factory(RSMILineForm, extra=5, max_num=5, validate_max=True, absolute_max=5)


def _prepare(request, *, kind, title, header_class, line_set):
    if not in_gso_scope(request.user) or not can_stock(request.user, "view"):
        raise PermissionDenied
    data = request.POST if request.method == "POST" else None
    header = header_class(data, prefix="header")
    lines = line_set(data, prefix="lines")
    ready = request.method == "POST" and header.is_valid() and lines.is_valid()
    rows = []
    if ready:
        for form in lines:
            row = {name: form.cleaned_data.get(name) for name in form.fields}
            if kind == "RPCI":
                card, counted = row["card_quantity"], row["counted_quantity"]
                row["difference"] = counted - card if card is not None and counted is not None else None
            rows.append(row)
    return render(request, "inventory/supply_preparation.html", {"kind": kind, "title": title,
        "header": header, "lines": lines, "ready": ready, "invalid": request.method == "POST" and not ready,
        "details": header.cleaned_data if ready else {}, "print_lines": rows})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def rpci_preparation(request):
    return _prepare(request, kind="RPCI", title="Report on the Physical Count of Inventories",
                    header_class=RPCIHeaderForm, line_set=RPCILines)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def rsmi_preparation(request):
    return _prepare(request, kind="RSMI", title="Report of Supplies and Materials Issued",
                    header_class=RSMIHeaderForm, line_set=RSMILines)
