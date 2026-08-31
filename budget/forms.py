from django import forms

from accounting.models import FiscalYear
from departments.models import Department

from .models import (
    AllotmentOrderLine, AllotmentReleaseOrder, AppropriationAuthorization,
    BudgetCall, BudgetCeiling, BudgetProposalLine, BudgetResourceEstimate, BudgetReviewComment, BudgetVersion,
    ObligationRequest, ObligationRequestLine,
)


class DateInput(forms.DateInput):
    input_type = "date"


class BudgetCallForm(forms.ModelForm):
    class Meta:
        model = BudgetCall
        fields = ("fiscal_year", "title", "authority_reference", "instructions", "proposal_opens_on", "proposal_due_on")
        widgets = {"proposal_opens_on": DateInput(), "proposal_due_on": DateInput(), "instructions": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(status__in=(FiscalYear.APPROVED, FiscalYear.ACTIVE)).order_by("-year")


class BudgetCeilingForm(forms.ModelForm):
    requesting_department = forms.ModelChoiceField(queryset=Department.objects.none())

    class Meta:
        model = BudgetCeiling
        fields = ("requesting_department", "fund", "expense_class", "amount", "basis")
        widgets = {"basis": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, budget_call=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.budget_call = budget_call
        self.fields["requesting_department"].queryset = Department.objects.all().order_by("name")
        self.fields["fund"].queryset = self.fields["fund"].queryset.filter(department_id=budget_call.fiscal_year.department_id, is_active=True)

    def save(self, commit=True):
        item = super().save(False)
        department = self.cleaned_data["requesting_department"]
        item.requesting_department_id, item.requesting_department_label = department.pk, department.name
        if commit:
            item.save()
        return item


class BudgetVersionForm(forms.ModelForm):
    requesting_department = forms.ModelChoiceField(queryset=Department.objects.none(), required=False)

    class Meta:
        model = BudgetVersion
        fields = ("budget_call", "kind", "version", "title", "requesting_department", "change_explanation", "supersedes")
        widgets = {"change_explanation": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, department_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requesting_department"].queryset = Department.objects.all().order_by("name")
        self.fields["budget_call"].queryset = BudgetCall.objects.filter(department_id=department_id, status=BudgetCall.PUBLISHED)
        self.fields["supersedes"].queryset = BudgetVersion.objects.filter(department_id=department_id, status__in=(BudgetVersion.APPROVED, BudgetVersion.AUTHORIZED))

    def save(self, commit=True):
        item = super().save(False)
        department = self.cleaned_data.get("requesting_department")
        item.requesting_department_id = department.pk if department else None
        item.requesting_department_label = department.name if department else ""
        item.fiscal_year = item.budget_call.fiscal_year
        if commit:
            item.save()
        return item


class BudgetProposalLineForm(forms.ModelForm):
    class Meta:
        model = BudgetProposalLine
        fields = ("fund", "responsibility_center", "program", "funding_source", "account", "expense_class", "appropriation_type", "particulars", "performance_target", "amount", "change_explanation")
        widgets = {"performance_target": forms.Textarea(attrs={"rows": 2}), "change_explanation": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, version=None, **kwargs):
        super().__init__(*args, **kwargs)
        ledger = version.fiscal_year.department_id
        for name in ("fund", "responsibility_center", "program", "funding_source", "account"):
            self.fields[name].queryset = self.fields[name].queryset.filter(department_id=ledger)


class BudgetReviewCommentForm(forms.ModelForm):
    class Meta:
        model = BudgetReviewComment
        fields = ("comment",)
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}


class BudgetResourceEstimateForm(forms.ModelForm):
    class Meta:
        model = BudgetResourceEstimate
        fields = ("funding_source", "description", "amount", "basis")
        widgets = {"basis": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, version=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funding_source"].queryset = self.fields["funding_source"].queryset.filter(
            department_id=version.fiscal_year.department_id,
            fiscal_year=version.fiscal_year,
            is_active=True,
        )


class BudgetConsolidationForm(forms.Form):
    sources = forms.ModelMultipleChoiceField(
        queryset=BudgetVersion.objects.none(), widget=forms.CheckboxSelectMultiple,
        help_text="Only independently approved department proposal versions are eligible.",
    )
    title = forms.CharField(max_length=180)
    change_explanation = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, department_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sources"].queryset = BudgetVersion.objects.filter(
            department_id=department_id, kind=BudgetVersion.DEPARTMENT, status=BudgetVersion.APPROVED,
        ).order_by("fiscal_year__year", "requesting_department_label", "-version")


class AppropriationAuthorizationForm(forms.ModelForm):
    class Meta:
        model = AppropriationAuthorization
        fields = ("version", "authority_type", "ordinance_number", "ordinance_date", "effectivity_date", "review_status", "review_reference", "review_date", "conditions", "evidence_reference", "signed_control_total")
        widgets = {
            "ordinance_date": DateInput(), "effectivity_date": DateInput(), "review_date": DateInput(),
            "conditions": forms.Textarea(attrs={"rows": 3}), "evidence_reference": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, department_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version"].queryset = BudgetVersion.objects.filter(
            department_id=department_id, kind__in=(BudgetVersion.FINAL, BudgetVersion.SUPPLEMENTAL, BudgetVersion.REENACTED),
            status=BudgetVersion.APPROVED, appropriation_authorization__isnull=True,
        )


class AllotmentReleaseOrderForm(forms.ModelForm):
    class Meta:
        model = AllotmentReleaseOrder
        fields = (
            "authorization", "order_number", "kind", "release_date", "effective_date",
            "authority_reference", "evidence_reference", "purpose", "signed_control_total", "corrects",
        )
        widgets = {
            "release_date": DateInput(), "effective_date": DateInput(),
            "evidence_reference": forms.Textarea(attrs={"rows": 4}), "purpose": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.department_id = department_id
        current_authorization_id = self.instance.authorization_id if self.instance and self.instance.pk else None
        authorizations = AppropriationAuthorization.objects.filter(
            department_id=department_id, status=AppropriationAuthorization.AUTHORIZED,
        ).select_related("version", "version__fiscal_year")
        if current_authorization_id:
            authorizations = authorizations.filter(pk=current_authorization_id)
            self.fields["authorization"].disabled = True
        self.fields["authorization"].queryset = authorizations
        corrections = AllotmentReleaseOrder.objects.filter(
            department_id=department_id, status=AllotmentReleaseOrder.POSTED,
        )
        if self.instance and self.instance.pk:
            corrections = corrections.exclude(pk=self.instance.pk)
        self.fields["corrects"].queryset = corrections

    def _post_clean(self):
        authorization = self.cleaned_data.get("authorization")
        if authorization:
            self.instance.authorization = authorization
            self.instance.fiscal_year = authorization.version.fiscal_year
            self.instance.department_id = self.department_id
            self.instance.department_label = authorization.department_label
        super()._post_clean()


class AllotmentOrderLineForm(forms.ModelForm):
    class Meta:
        model = AllotmentOrderLine
        fields = ("appropriation_line", "movement_type", "amount", "remarks")
        widgets = {"remarks": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.instance.order = order
        self.instance.department_id = order.department_id
        self.instance.department_label = order.department_label
        self.fields["appropriation_line"].queryset = order.authorization.schedule_lines.all()
        allowed = set(AllotmentOrderLine.ALLOWED_BY_ORDER.get(order.kind, ()))
        self.fields["movement_type"].choices = [
            choice for choice in AllotmentOrderLine.MOVEMENT_CHOICES if choice[0] in allowed
        ]


class ObligationRequestForm(forms.ModelForm):
    class Meta:
        model = ObligationRequest
        fields = (
            "authorization", "kind", "form_type", "request_reference", "obligation_date",
            "claimant_payee", "particulars", "evidence_reference", "signed_control_total", "corrects",
        )
        widgets = {
            "obligation_date": DateInput(), "particulars": forms.Textarea(attrs={"rows": 4}),
            "evidence_reference": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, requesting_department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requesting_department = requesting_department
        current_authorization_id = self.instance.authorization_id if self.instance and self.instance.pk else None
        authorizations = AppropriationAuthorization.objects.filter(
            status=AppropriationAuthorization.AUTHORIZED,
        ).select_related("version", "version__fiscal_year")
        if current_authorization_id:
            authorizations = authorizations.filter(pk=current_authorization_id)
            self.fields["authorization"].disabled = True
        self.fields["authorization"].queryset = authorizations
        corrections = ObligationRequest.objects.filter(
            requesting_department_id=requesting_department.pk, status=ObligationRequest.CERTIFIED,
        ) if requesting_department else ObligationRequest.objects.none()
        if self.instance and self.instance.pk:
            corrections = corrections.exclude(pk=self.instance.pk)
        self.fields["corrects"].queryset = corrections

    def _post_clean(self):
        authorization = self.cleaned_data.get("authorization")
        if authorization:
            self.instance.authorization = authorization
            self.instance.fiscal_year = authorization.version.fiscal_year
            self.instance.department_id = authorization.department_id
            self.instance.department_label = authorization.department_label
        if self.requesting_department:
            self.instance.requesting_department_id = self.requesting_department.pk
            self.instance.requesting_department_label = self.requesting_department.name
        super()._post_clean()


class ObligationRequestLineForm(forms.ModelForm):
    class Meta:
        model = ObligationRequestLine
        fields = ("appropriation_line", "movement_type", "amount", "remarks")
        widgets = {"remarks": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, request_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_item = request_item
        self.instance.request = request_item
        self.instance.department_id = request_item.department_id
        self.instance.department_label = request_item.department_label
        self.fields["appropriation_line"].queryset = request_item.authorization.schedule_lines.all()
        allowed = {ObligationRequestLine.OBLIGATE, ObligationRequestLine.REDUCE}
        if request_item.kind == ObligationRequest.ORIGINAL:
            allowed = {ObligationRequestLine.OBLIGATE}
        elif request_item.kind in (ObligationRequest.RETURN, ObligationRequest.CANCELLATION):
            allowed = {ObligationRequestLine.REDUCE}
        self.fields["movement_type"].choices = [
            choice for choice in ObligationRequestLine.MOVEMENT_CHOICES if choice[0] in allowed
        ]
