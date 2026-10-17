from django import forms
from .models import ReceivingReceipt, ReceivingLine, ReceivingEvidence, ConsumableItem


class ReceiptForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.followup_source_id:
            for name in ("supplier", "delivery_reference", "delivery_date", "purchase_order_reference"):
                self.fields[name].disabled = True

    class Meta:
        model = ReceivingReceipt
        fields = ("supplier", "delivery_reference", "delivery_date", "purchase_order_reference",
                  "inspection_reference", "inspection_date", "inspector_label", "evidence_reference")
        widgets = {"delivery_date": forms.DateInput(attrs={"type": "date"}),
                   "inspection_date": forms.DateInput(attrs={"type": "date"}),
                   "evidence_reference": forms.Textarea(attrs={"rows": 3})}


class ReceiptLineForm(forms.ModelForm):
    class Meta:
        model = ReceivingLine
        fields = ("kind", "description", "unit", "delivered_quantity", "accepted_quantity",
                  "rejected_quantity", "rejection_reason", "unit_cost", "supply_item", "asset_kind",
                  "property_tag", "serial_number", "chassis_number")

    def __init__(self, *args, receipt, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.receipt = receipt
        self.fields["supply_item"].queryset = ConsumableItem.objects.filter(department_id=receipt.department_id, is_active=True)
        self.fields["accepted_quantity"].label = "Quantity supported for acceptance"
        self.fields["accepted_quantity"].help_text = "No stock is added until independent review accepts this receipt."
        if receipt.followup_source_id:
            for name in ("kind", "description", "unit", "supply_item", "asset_kind"):
                self.fields[name].disabled = True
            self.fields["delivered_quantity"].label = "Quantity covered by this follow-up"
            self.fields["delivered_quantity"].help_text = "Must equal accepted plus rejected; this is not another delivery."


class FollowupForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    inspection_reference = forms.CharField(max_length=180)
    inspection_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    inspector_label = forms.CharField(max_length=160)
    evidence_reference = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    accepted_quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0)
    rejected_quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0)
    rejection_reason = forms.CharField(max_length=240, required=False)
    unit_cost = forms.DecimalField(max_digits=13, decimal_places=2, min_value=0, required=False,
        help_text="Supplied cost for this follow-up. Blank means unknown; this is not Accounting valuation.")
    property_tag = forms.CharField(max_length=100, required=False)
    serial_number = forms.CharField(max_length=120, required=False)
    chassis_number = forms.CharField(max_length=80, required=False)

    def __init__(self, *args, source, **kwargs):
        super().__init__(*args, **kwargs)
        if source.kind == "supply":
            for name in ("property_tag", "serial_number", "chassis_number"):
                self.fields[name].widget = forms.HiddenInput()


class EvidenceForm(forms.Form):
    kind = forms.ChoiceField(choices=ReceivingEvidence.KIND_CHOICES)
    upload = forms.FileField(label="Document (PDF, JPG, PNG or WebP; up to 15 MB)")
    note = forms.CharField(max_length=240, label="What does this document establish or correct?")


class ReceiptActionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput(attrs={"id": ""}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
