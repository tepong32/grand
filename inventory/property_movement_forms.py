from django import forms

from .models import PropertyDetermination, PropertyMovementRecord, ReceivingLine
from .property_movements import CONTENT_FIELDS


class DeterminationChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.reference} · {obj.get_treatment_display()} · {obj.source_date}"


class MovementSourceForm(forms.Form):
    determination = DeterminationChoice(queryset=PropertyDetermination.objects.none(), label="Verified property document")
    source = forms.ChoiceField(label="Opening or confirmed physical event")

    def __init__(self, *args, asset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["determination"].queryset = asset.property_determinations.filter(status="verified").order_by("-decided_at", "-pk")
        choices = [("opening", "Documented end-of-day opening")]
        for row in ReceivingLine.objects.filter(registered_asset=asset, is_void=False, receipt__status="accepted").select_related("receipt"):
            choices.append((f"receipt:{row.pk}", f"Receipt · {row.receipt.delivery_reference} · {row.receipt.delivery_date}"))
        for row in asset.transfers.filter(status="accepted"):
            choices.append((f"{row.kind}:{row.pk}", f"{row.get_kind_display()} · {row.reference or 'Reference not recorded'} · {row.transfer_date}"))
        for row in asset.disposal_cases.filter(status="disposed"):
            choices.append((f"disposal:{row.pk}", f"Disposal · {row.completion_reference} · {row.disposal_date}"))
        self.fields["source"].choices = choices

    def source_identity(self):
        kind, _, local_id = self.cleaned_data["source"].partition(":")
        return kind, int(local_id) if local_id else None


class MovementForm(forms.ModelForm):
    source_token = forms.CharField(widget=forms.HiddenInput)
    upload = forms.FileField(label="Movement or opening source packet (PDF or image)")
    stock_delta = forms.TypedChoiceField(coerce=int, label="Documented effect on stock")
    opening_quantity = forms.TypedChoiceField(coerce=int, empty_value=None, required=False,
        choices=(("", "Choose the documented quantity"), (0, "0 — not in stock"), (1, "1 — in stock")),
        label="Documented opening quantity")

    class Meta:
        model = PropertyMovementRecord
        fields = CONTENT_FIELDS
        widgets = {"movement_date": forms.DateInput(attrs={"type": "date"}),
                   "remarks": forms.Textarea(attrs={"rows": 3})}
        labels = {"movement_date": "Physical source date / opening as-of date",
                  "within_day_order": "Order on this date", "reference": "Source document reference",
                  "item_number": "Assigned receipt / issue item number (optional if unknown)",
                  "office_officer_label": "Office or accountable officer stated in the source",
                  "unit_cost": "Documented unit cost (leave unknown blank)",
                  "remarks": "Source facts and reason for the stock effect or correction"}
        help_texts = {"within_day_order": "Use 1, 2, and so on in documented chronological order for this date.",
                      "unit_cost": "A supplied documentary amount, not Accounting valuation.",
                      "item_number": "Copy the assigned number; this form does not allocate a numbering series."}

    def __init__(self, *args, source_kind, source_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stock_delta"].choices = {
            "opening": ((0, "Opening — no movement"),),
            "receipt": ((1, "Add one received item to stock"),),
            "handoff": (("", "Choose the documented effect"), (-1, "Issue one item from stock"), (0, "Reassignment — no stock change")),
            "return": (("", "Choose the documented effect"), (1, "Return one item to stock"), (0, "Return does not establish stock")),
            "disposal": (("", "Choose the documented effect"), (-1, "Remove one item from stock"), (0, "Already issued — no stock change")),
        }[source_kind]
        if source_kind == "opening":
            self.fields["opening_quantity"].required = True
            for name in ("stock_delta", "within_day_order"):
                self.fields[name].disabled = True
                self.fields[name].widget = forms.HiddenInput()
                self.initial[name] = 0
        else:
            self.fields["opening_quantity"].disabled = True
            self.fields["opening_quantity"].widget = forms.HiddenInput()
            self.initial["opening_quantity"] = None
            self.fields["movement_date"].disabled = True
            self.initial["movement_date"] = source_date
            self.fields["within_day_order"] = forms.IntegerField(min_value=1, max_value=32767,
                label="Order on this date", help_text="Use documented chronological order: 1, 2, and so on.")
            if source_kind == "receipt":
                self.fields["stock_delta"].disabled = True
                self.initial["stock_delta"] = 1


class MovementCutoffForm(forms.Form):
    cutoff = forms.DateField(label="Working balance through", widget=forms.DateInput(attrs={"type": "date"}))
