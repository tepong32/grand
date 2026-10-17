from decimal import Decimal
from django import forms
from django.forms import formset_factory
from django.utils import timezone
from .access import department_model, gso_department_for_user
from .models import ConsumableItem


class RequisitionForm(forms.Form):
    request_token = forms.CharField(widget=forms.HiddenInput)
    requesting_department_id = forms.TypedChoiceField(coerce=int, choices=(), label="Requesting office")
    reference = forms.CharField(max_length=120, label="Supplied requisition reference")
    requested_on = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    purpose = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={"rows": 3}))
    upload = forms.FileField(label="Supplied approved requisition (PDF or image)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requesting_department_id"].choices = [("", "Select requesting office")] + list(
            department_model().objects.exclude(name="---select one---").order_by("name").values_list("pk", "name"))


class RequisitionLineForm(forms.Form):
    item_id = forms.TypedChoiceField(coerce=int, choices=(), label="Supply item")
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"), label="Requested quantity")

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        owner = gso_department_for_user(actor)
        self.fields["item_id"].choices = [("", "Select item")] + [(item.pk, f"{item.name} ({item.unit})")
            for item in ConsumableItem.objects.filter(department_id=owner.pk, is_active=True).order_by("name")]


RequisitionLines = formset_factory(RequisitionLineForm, extra=5, min_num=1, validate_min=True,
    max_num=50, validate_max=True, absolute_max=50)


class DecisionForm(forms.Form):
    note = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 2}), label="Review or closure basis")


class FulfillmentForm(forms.Form):
    line_id = forms.TypedChoiceField(coerce=int, choices=(), label="Requested line")
    outcome = forms.ChoiceField(choices=(("issued", "Issued"), ("unavailable", "Unavailable at check")))
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0, label="Quantity physically issued (zero if unavailable)")
    recipient = forms.CharField(max_length=160, required=False, label="Physical recipient (issued items only)")
    note = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 2}), label="Issue or availability facts")

    def __init__(self, *args, request, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["line_id"].choices = [(line.pk, f"{line.item_name} ({line.unit})") for line in request.lines.all()]


class VersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
