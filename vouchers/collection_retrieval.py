"""Scoped collection register filters and descriptive source totals."""
from django import forms
from django.db.models import Count, Q, Sum

from .models import TreasuryCollectionSource as Source


class CollectionRegisterForm(forms.Form):
    q = forms.CharField(required=False, max_length=220, label="Receipt / deposit reference, book or payer")
    date_from = forms.DateField(required=False, label="From date", widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, label="Through date", widget=forms.DateInput(attrs={"type": "date"}))
    fund = forms.ChoiceField(required=False, label="Fund")
    kind = forms.ChoiceField(required=False, label="Record type", choices=(("", "All types"), *Source.KIND_CHOICES))
    status = forms.ChoiceField(required=False, label="Status", choices=(("", "All statuses"), *Source.STATUS_CHOICES))

    def __init__(self, data, *, scope):
        super().__init__(data)
        self.fields["fund"].choices = [("", "All visible funds"), *[
            (code, code) for code in scope.order_by("fund_code").values_list("fund_code", flat=True).distinct()
        ]]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise forms.ValidationError("From date must be on or before through date.")
        return data

    def apply(self, queryset):
        if not self.is_valid():
            return queryset.none()
        data = self.cleaned_data
        if data["q"]:
            queryset = queryset.filter(Q(document_reference__icontains=data["q"]) |
                Q(book_reference__icontains=data["q"]) | Q(proposal__payer_reference__icontains=data["q"]))
        for key, lookup in (("fund", "fund_code"), ("kind", "kind"), ("status", "status"),
                            ("date_from", "source_date__gte"), ("date_to", "source_date__lte")):
            if data[key]:
                queryset = queryset.filter(**{lookup: data[key]})
        return queryset.order_by("-source_date", "-pk")


def source_totals(queryset):
    rows = queryset.order_by("fund_code", "kind", "status").values("fund_code", "kind", "status").annotate(
        record_count=Count("pk"), recorded_amount=Sum("amount"),
    )
    return [{**row, "kind_label": dict(Source.KIND_CHOICES).get(row["kind"], row["kind"]),
             "status_label": dict(Source.STATUS_CHOICES).get(row["status"], row["status"])} for row in rows]
