from django import forms

from accounting.models import FiscalYear
from departments.models import Department

from .models import AppropriationAuthorization, BudgetCall, BudgetCeiling, BudgetProposalLine, BudgetResourceEstimate, BudgetReviewComment, BudgetVersion


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
