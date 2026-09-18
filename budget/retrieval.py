"""Read-only register narrowing, applied after the actor's existing scope."""
from django import forms
from django.db.models import Q


class ObligationRetrievalForm(forms.Form):
    q = forms.CharField(required=False, max_length=220, label="OBR / request reference or payee")
    office = forms.ChoiceField(required=False, label="Requesting office")
    fund = forms.ChoiceField(required=False, label="Fund")
    date_from = forms.DateField(required=False, label="From date", widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, label="Through date", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, data, *, scope):
        super().__init__(data)
        self.fields["office"].choices = [("", "All visible offices")] + list(
            scope.order_by("requesting_department_label", "requesting_department_id")
            .values_list("requesting_department_id", "requesting_department_label").distinct()
        )
        codes = scope.order_by("lines__appropriation_line__fund_code").values_list(
            "lines__appropriation_line__fund_code", flat=True,
        ).distinct()
        self.fields["fund"].choices = [("", "All visible funds")] + [(code, code) for code in codes if code]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        start, end = data.get("date_from"), data.get("date_to")
        if start and end and start > end:
            raise forms.ValidationError("From date must be on or before through date.")
        return data

    def apply(self, queryset):
        if not self.is_valid():
            return queryset.none()
        data = self.cleaned_data
        if data["q"]:
            queryset = queryset.filter(
                Q(obligation_number__icontains=data["q"]) |
                Q(request_reference__icontains=data["q"]) |
                Q(claimant_payee__icontains=data["q"])
            )
        if data["office"]:
            queryset = queryset.filter(requesting_department_id=data["office"])
        if data["fund"]:
            # A request may contain several matching lines; return the request once.
            queryset = queryset.filter(pk__in=queryset.filter(
                lines__appropriation_line__fund_code=data["fund"],
            ).values("pk"))
        if data["date_from"]:
            queryset = queryset.filter(obligation_date__gte=data["date_from"])
        if data["date_to"]:
            queryset = queryset.filter(obligation_date__lte=data["date_to"])
        return queryset

    def evidence(self):
        return {key: str(value or "") for key, value in self.cleaned_data.items()}
