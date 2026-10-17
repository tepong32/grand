from decimal import Decimal
from django import forms
from django.utils import timezone


class ReturnForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    source_allocation_id = forms.TypedChoiceField(coerce=int, empty_value=None, required=False, label="Documented original FIFO allocation")
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    reference = forms.CharField(max_length=120, label="Return document reference")
    returned_by = forms.CharField(max_length=160, label="Person returning the supplies")
    observed_on = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    condition_note = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 2}), label="Observed condition and quantity facts")
    cost_basis_note = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 2}), label="Evidence for the selected lot, or why its cost is unknown")
    upload = forms.FileField(label="Return evidence (PDF or image)")

    def __init__(self, *args, issue, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "Unknown cost / original lot not identified")]
        if issue.item.use_fifo:
            choices += [(row.pk, f"Receipt {row.lot.receipt.public_id} | issued {row.quantity} {issue.item.unit} | cost {row.lot.unit_cost if row.lot.unit_cost is not None else 'unknown'}")
                for row in issue.lot_allocations.select_related("lot__receipt").order_by("pk")]
        self.fields["source_allocation_id"].choices = choices


class ReturnDecisionForm(forms.Form):
    note = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 2}), label="Decision and handling basis")
    suitable_for_stock = forms.BooleanField(required=False, label="I checked that these goods are suitable for usable stock")


class ReturnVersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
