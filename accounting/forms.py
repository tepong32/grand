from django import forms

from .models import (
    AccountingPeriod, FiscalYear, Fund, FundingSource, JournalEntry, JournalLine,
    LedgerAccount, PostingMapping, ProgramActivityProject, ResponsibilityCenter,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        department = kwargs.pop("department", None)
        super().__init__(*args, **kwargs)
        if department and hasattr(self.instance, "department_id"):
            self.instance.department_id = department.pk
            self.instance.department_label = department.name
        for field in self.fields.values():
            css_class = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs.setdefault("class", css_class)


class AccountingPeriodForm(StyledModelForm):
    class Meta:
        model = AccountingPeriod
        fields = ("fiscal_year_record", "period_number", "label", "starts_on", "ends_on", "is_adjustment_period")
        widgets = {"starts_on": forms.DateInput(attrs={"type": "date"}), "ends_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["fiscal_year_record"].queryset = FiscalYear.objects.filter(department_id=department.pk)
        self.fields["fiscal_year_record"].required = True

    def clean_fiscal_year_record(self):
        fiscal_year = self.cleaned_data["fiscal_year_record"]
        self.instance.fiscal_year = fiscal_year.year
        return fiscal_year

    def save(self, commit=True):
        self.instance.fiscal_year = self.cleaned_data["fiscal_year_record"].year
        return super().save(commit=commit)


class FiscalYearForm(StyledModelForm):
    class Meta:
        model = FiscalYear
        fields = ("year", "label", "starts_on", "ends_on", "business_date")
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
            "business_date": forms.DateInput(attrs={"type": "date"}),
        }


class FundForm(StyledModelForm):
    class Meta:
        model = Fund
        fields = ("code", "name", "category", "description", "effective_from", "effective_to", "is_active")
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"}), "effective_to": forms.DateInput(attrs={"type": "date"})}


class ResponsibilityCenterForm(StyledModelForm):
    class Meta:
        model = ResponsibilityCenter
        fields = ("code", "name", "office_id", "office_code", "description", "effective_from", "effective_to", "is_active")
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"}), "effective_to": forms.DateInput(attrs={"type": "date"})}


class LedgerAccountForm(StyledModelForm):
    class Meta:
        model = LedgerAccount
        fields = (
            "code", "title", "government_account_code", "account_type", "normal_balance", "parent",
            "subsidiary_reference_type", "effective_from", "effective_to", "allow_posting", "is_active",
        )
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"}), "effective_to": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        parents = LedgerAccount.objects.filter(department_id=department.pk)
        if self.instance.pk:
            parents = parents.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parents


class FundingSourceForm(StyledModelForm):
    class Meta:
        model = FundingSource
        fields = (
            "fiscal_year", "fund", "code", "name", "kind", "authority_reference",
            "effective_from", "effective_to", "is_active",
        )
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"}), "effective_to": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(department_id=department.pk)
        self.fields["fund"].queryset = Fund.objects.filter(department_id=department.pk, is_active=True)


class ProgramActivityProjectForm(StyledModelForm):
    class Meta:
        model = ProgramActivityProject
        fields = (
            "fiscal_year", "code", "name", "kind", "parent", "responsibility_center",
            "funding_source", "authority_reference", "effective_from", "effective_to", "is_active",
        )
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"}), "effective_to": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(department_id=department.pk)
        self.fields["parent"].queryset = ProgramActivityProject.objects.filter(department_id=department.pk)
        self.fields["responsibility_center"].queryset = ResponsibilityCenter.objects.filter(department_id=department.pk, is_active=True)
        self.fields["funding_source"].queryset = FundingSource.objects.filter(department_id=department.pk, is_active=True)

    def clean(self):
        cleaned = super().clean()
        fiscal_year = cleaned.get("fiscal_year")
        for field_name in ("parent", "funding_source"):
            related = cleaned.get(field_name)
            if fiscal_year and related and related.fiscal_year_id != fiscal_year.pk:
                self.add_error(field_name, "Choose a value from the selected fiscal year.")
        return cleaned


class PostingMappingForm(StyledModelForm):
    class Meta:
        model = PostingMapping
        fields = ("category", "source_code", "label", "account", "is_active")

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["account"].queryset = LedgerAccount.objects.filter(
            department_id=department.pk, is_active=True, allow_posting=True,
        )


class JournalEntryForm(StyledModelForm):
    class Meta:
        model = JournalEntry
        fields = ("reference", "entry_date", "period", "fund", "source_type", "description")
        widgets = {"entry_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["period"].queryset = AccountingPeriod.objects.filter(department_id=department.pk, status=AccountingPeriod.OPEN)
        self.fields["fund"].queryset = Fund.objects.filter(department_id=department.pk, is_active=True)


class JournalLineForm(StyledModelForm):
    class Meta:
        model = JournalLine
        fields = ("sequence", "account", "responsibility_center", "debit", "credit", "memo")
        widgets = {
            "debit": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "credit": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, department, entry=None, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        if entry is not None:
            self.instance.entry = entry
        self.fields["account"].queryset = LedgerAccount.objects.filter(
            department_id=department.pk, is_active=True, allow_posting=True,
        )
        self.fields["responsibility_center"].queryset = ResponsibilityCenter.objects.filter(
            department_id=department.pk, is_active=True,
        )


class ReversalForm(forms.Form):
    reference = forms.CharField(max_length=60, help_text="Use a unique reversing JEV number.")
    entry_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    period = forms.ModelChoiceField(queryset=AccountingPeriod.objects.none())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="This explanation is retained in the permanent audit trail.",
    )

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["period"].queryset = AccountingPeriod.objects.filter(
            department_id=department.pk, status=AccountingPeriod.OPEN,
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
