from decimal import Decimal
from django import forms

from inventory.models import ReceivingLine, ReceivingReceipt
from vouchers.models import VoucherLineItem


class ReceiptLineChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.receipt.delivery_reference} · line {obj.sequence}: {obj.description}"


class ClaimLineChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Line {obj.pk}: {obj.description} · {obj.amount:,.2f}"


class ProposalForm(forms.Form):
    receipt_line = ReceiptLineChoice(queryset=ReceivingLine.objects.none(), label="Accepted receipt line")
    source_line = ClaimLineChoice(queryset=VoucherLineItem.objects.none(), label="Claim line")
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"),
                                label="Amount supported by this receipt")
    basis = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Explain how the delivery documents support this amount. This does not approve payment or establish asset cost.")

    def __init__(self, *args, department, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["receipt_line"].queryset = ReceivingLine.objects.select_related("receipt").filter(
            receipt__department_id=department.pk, receipt__status=ReceivingReceipt.ACCEPTED,
            is_void=False, accepted_quantity__gt=0).order_by("receipt_id", "sequence")
        self.fields["source_line"].queryset = VoucherLineItem.objects.filter(voucher__case=case).order_by("pk")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class ConfirmProposalForm(forms.Form):
    proposal_token = forms.CharField(widget=forms.HiddenInput)


class ReviewForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=(("approve", "Approve support"), ("reject", "Reject proposal"),
                                       ("withdraw", "Withdraw link")))
    note = forms.CharField(max_length=4000, label="Review or correction reason",
                           widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
