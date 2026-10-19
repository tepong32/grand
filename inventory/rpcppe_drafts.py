"""Supplied RPCPPE preparation only; no stock, custody or Accounting writes."""
from decimal import localcontext

from django import forms
from django.contrib.auth.decorators import login_required
from django.forms import formset_factory
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .property_determinations import can_act


class RPCPPEHeaderForm(forms.Form):
    lgu = forms.CharField(label="LGU / municipality", required=False, max_length=180)
    office = forms.CharField(label="Office", required=False, max_length=160)
    property_type = forms.CharField(label="Type of property (as supplied)", required=False, max_length=180)
    fund = forms.CharField(label="Fund label (as supplied)", required=False, max_length=160)
    as_of = forms.DateField(label="Inventory as of (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    form_reference = forms.CharField(label="Local form reference / revision", required=False, max_length=180)
    accountable_officer = forms.CharField(label="Accountable officer name (as supplied)", required=False, max_length=160)
    designation = forms.CharField(label="Accountable officer designation / office", required=False, max_length=180)
    assumption_date = forms.DateField(label="Date accountability assumed (as supplied)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    prepared_by = forms.CharField(label="Prepared by (name / designation placeholder)", required=False, max_length=180)
    reviewed_by = forms.CharField(label="Review / approval name and designation (as supplied)", required=False, max_length=180)


class RPCPPELineForm(forms.Form):
    card_name = "property card"
    article = forms.CharField(required=False, max_length=180)
    description = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
    property_number = forms.CharField(label="Property number (as supplied)", required=False, max_length=100)
    unit = forms.CharField(required=False, max_length=30)
    unit_value = forms.DecimalField(label="Unit value (as supplied)", required=False, min_value=0, max_digits=18, decimal_places=2)
    card_quantity = forms.DecimalField(label="Quantity per property card (as supplied)", required=False, min_value=0, max_digits=12, decimal_places=3)
    counted_quantity = forms.DecimalField(label="Quantity per physical count (as supplied)", required=False, min_value=0, max_digits=12, decimal_places=3)
    difference_value = forms.DecimalField(label="Difference value (signed, as supplied; not calculated)", required=False, max_digits=18, decimal_places=2)
    remarks = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        data = super().clean()
        card, counted, unit_value, supplied = (data.get(name) for name in
            ("card_quantity", "counted_quantity", "unit_value", "difference_value"))
        if all(value is not None for value in (card, counted, unit_value, supplied)):
            with localcontext() as context:
                context.prec = 40
                expected = (counted - card) * unit_value
            if supplied != expected:
                self.add_error("difference_value", f"Check the supplied difference value against (physical count minus {self.card_name}) × unit value. No rounding is inferred; leave the value blank if it needs Accounting review.")
        return data


RPCPPELines = formset_factory(RPCPPELineForm, extra=5, max_num=5, validate_max=True, absolute_max=5)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def preparation(request):
    if not can_act(request.user, "view"):
        raise PermissionDenied
    data = request.POST if request.method == "POST" else None
    header = RPCPPEHeaderForm(data, prefix="header")
    lines = RPCPPELines(data, prefix="lines")
    ready = request.method == "POST" and header.is_valid() and lines.is_valid()
    rows = []
    if ready:
        for form in lines:
            row = {name: form.cleaned_data.get(name) for name in form.fields}
            card, counted = row["card_quantity"], row["counted_quantity"]
            row["difference"] = counted - card if card is not None and counted is not None else None
            rows.append(row)
    return render(request, "inventory/rpcppe_preparation.html", {
        "header": header, "lines": lines, "ready": ready,
        "invalid": request.method == "POST" and not ready,
        "details": header.cleaned_data if ready else {}, "print_lines": rows,
    })
