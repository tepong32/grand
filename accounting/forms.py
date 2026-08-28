from django import forms

from .models import AccountingPeriod, Fund, JournalEntry, JournalLine, LedgerAccount, ResponsibilityCenter


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
        fields = ("fiscal_year", "period_number", "label", "starts_on", "ends_on")
        widgets = {"starts_on": forms.DateInput(attrs={"type": "date"}), "ends_on": forms.DateInput(attrs={"type": "date"})}


class FundForm(StyledModelForm):
    class Meta:
        model = Fund
        fields = ("code", "name", "description", "is_active")


class ResponsibilityCenterForm(StyledModelForm):
    class Meta:
        model = ResponsibilityCenter
        fields = ("code", "name", "description", "is_active")


class LedgerAccountForm(StyledModelForm):
    class Meta:
        model = LedgerAccount
        fields = ("code", "title", "account_type", "normal_balance", "parent", "allow_posting", "is_active")

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        parents = LedgerAccount.objects.filter(department_id=department.pk)
        if self.instance.pk:
            parents = parents.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parents


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
