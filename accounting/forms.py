from django import forms

from .models import (
    AccountingPeriod, FiscalYear, Fund, FundingSource, JournalEntry, JournalLine,
    BankStatementBatch,
    LedgerAccount, OpeningBalanceBatch, OpeningBalanceRow, PostingMapping,
    PeriodClosePolicy, PeriodCloseRun, ProgramActivityProject, ResponsibilityCenter,
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


class PeriodClosePolicyForm(StyledModelForm):
    class Meta:
        model = PeriodClosePolicy
        fields = (
            "title", "description", "mode", "require_control_reconciliation",
            "require_bank_reconciliation", "require_statement_reports",
            "require_handoff_clearance", "require_year_end_closing_entries",
            "authority_reference", "local_acceptance_note",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "mode": "Observe explains missing local evidence without blocking close. Enforce blocks the accepted gates.",
            "authority_reference": "Record the reviewed circular, manual, memo, resolution, office order, or local close calendar.",
            "local_acceptance_note": "Record who accepted this version, when, and where the signed or approved evidence is retained.",
        }


class PeriodCloseRunForm(forms.Form):
    period = forms.ModelChoiceField(queryset=AccountingPeriod.objects.none())
    adjustment_review_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Explain adjusting JEVs, closing JEVs when applicable, or why no entry is required.",
    )
    evidence_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Give a human-readable retained-folder, packet, schedule, or records reference.",
    )
    preparer_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, department, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        periods = AccountingPeriod.objects.filter(
            department_id=department.pk, status=AccountingPeriod.OPEN,
        ).order_by("fiscal_year", "period_number")
        if instance:
            periods = AccountingPeriod.objects.filter(pk=instance.period_id)
            self.fields["period"].disabled = True
            self.initial.update({
                "period": instance.period_id,
                "adjustment_review_note": instance.adjustment_review_note,
                "evidence_reference": instance.evidence_reference,
                "preparer_note": instance.preparer_note,
            })
        self.fields["period"].queryset = periods
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class PeriodReopenRequestForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        help_text="Describe the discovered error and the correction that requires postings to reopen.",
    )
    authority_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        help_text="Record the approved memo, instruction, finding, or other retained authority.",
    )


class PeriodCloseDecisionForm(forms.Form):
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


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


class OpeningBalanceBatchForm(StyledModelForm):
    class Meta:
        model = OpeningBalanceBatch
        fields = (
            "fiscal_year", "period", "title", "source_reference", "expected_row_count",
            "expected_debit", "expected_credit", "is_zero_balance_declaration",
        )
        widgets = {
            "expected_debit": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "expected_credit": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(
            department_id=department.pk,
            status__in=(FiscalYear.DRAFT, FiscalYear.FOR_REVIEW, FiscalYear.APPROVED, FiscalYear.ACTIVE),
        )
        self.fields["period"].queryset = AccountingPeriod.objects.filter(
            department_id=department.pk, status=AccountingPeriod.OPEN, fiscal_year_record__isnull=False,
        )

    def clean(self):
        cleaned = super().clean()
        fiscal_year = cleaned.get("fiscal_year")
        period = cleaned.get("period")
        if fiscal_year and period and period.fiscal_year_record_id != fiscal_year.pk:
            self.add_error("period", "Choose an open period from the selected fiscal year.")
        return cleaned


class OpeningBalanceBatchCorrectionForm(OpeningBalanceBatchForm):
    change_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Cite the corrected source schedule, review instruction, or authority for changing the declared controls.",
    )


class OpeningBalanceImportForm(forms.Form):
    source_file = forms.FileField(
        help_text=(
            "UTF-8 CSV columns: fund_code, account_code, responsibility_center_code, debit, credit, "
            "subsidiary_reference, memo. The last three descriptive columns are optional."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv", "class": "form-control-file"}),
    )


class OpeningBalanceRowCorrectionForm(forms.Form):
    raw_fund_code = forms.CharField(max_length=80, label="Fund code")
    raw_account_code = forms.CharField(max_length=80, label="Account code")
    raw_responsibility_center_code = forms.CharField(max_length=80, required=False, label="Responsibility-center code")
    raw_debit = forms.CharField(max_length=80, required=False, label="Debit")
    raw_credit = forms.CharField(max_length=80, required=False, label="Credit")
    subsidiary_reference = forms.CharField(max_length=160, required=False)
    memo = forms.CharField(max_length=255, required=False)
    change_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Cite the corrected source schedule, authorized adjustment, or review instruction.",
    )

    def __init__(self, *args, row: OpeningBalanceRow | None = None, **kwargs):
        if row is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "raw_fund_code": row.raw_fund_code,
                "raw_account_code": row.raw_account_code,
                "raw_responsibility_center_code": row.raw_responsibility_center_code,
                "raw_debit": row.raw_debit,
                "raw_credit": row.raw_credit,
                "subsidiary_reference": row.subsidiary_reference,
                "memo": row.memo,
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class BankStatementBatchForm(StyledModelForm):
    class Meta:
        model = BankStatementBatch
        fields = (
            "statement_reference", "bank_account_code", "bank_name", "account_number_masked", "fund",
            "period_start", "period_end", "received_on", "opening_balance", "closing_balance",
            "expected_row_count", "expected_deposits", "expected_withdrawals",
        )
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
            "received_on": forms.DateInput(attrs={"type": "date"}),
            "opening_balance": forms.NumberInput(attrs={"step": "0.01"}),
            "closing_balance": forms.NumberInput(attrs={"step": "0.01"}),
            "expected_deposits": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "expected_withdrawals": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        help_texts = {
            "statement_reference": "Use the bank's statement number or a locally controlled monthly reference.",
            "bank_account_code": "Enter the human-readable code from the active Finance Setup bank-account mapping.",
            "account_number_masked": "Keep only a safe masked value, for example ••••1234.",
        }

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, department=department, **kwargs)
        self.fields["fund"].queryset = Fund.objects.filter(department_id=department.pk, is_active=True)


class BankStatementBatchCorrectionForm(BankStatementBatchForm):
    change_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Cite the corrected bank statement, bank advice, reviewer instruction, or other supporting reference.",
    )


class BankStatementImportForm(forms.Form):
    source_file = forms.FileField(
        help_text=(
            "UTF-8 CSV columns: transaction_date, bank_reference, description, withdrawal, deposit, "
            "running_balance. Use YYYY-MM-DD dates; running_balance may be blank."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv", "class": "form-control-file"}),
    )
    change_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        help_text="Required when replacing an already staged statement version.",
    )


class BankMatchForm(forms.Form):
    journal_line_id = forms.IntegerField(widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        help_text="Record the exact bank reference, paid check, transfer reference, or other match basis.",
    )


class BankUnmatchForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        help_text="Explain why the prior match is being superseded.",
    )


class BankOutstandingForm(forms.Form):
    journal_line_id = forms.IntegerField(widget=forms.HiddenInput())
    explanation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    evidence_reference = forms.CharField(max_length=160)
    expected_clearance_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


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
