import json

from django import forms
from django.contrib.auth import get_user_model

from .models import (
    FinanceCutoverDecision,
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceDocumentRule, FinanceNumberingSequence,
    FinanceParty, FinancePartyClaimant, FinancePostingRule, FinancePostingRuleLine,
    FinanceShadowComparison, FinanceShadowCycle, FinanceShadowDefect,
    FinanceShadowReconciliationPlan, FinanceSignatory, FinanceStakeholderAcceptance,
    FinanceTemplateVersion, FinanceTransactionVariant,
)


class DateInput(forms.DateInput):
    input_type = "date"


class FinanceReleaseForm(forms.ModelForm):
    class Meta:
        model = FinanceConfigurationRelease
        fields = ("code", "version", "title", "fiscal_year", "effective_from", "effective_to")
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}


class FinanceItemForm(forms.ModelForm):
    configuration_json = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 7}),
        help_text='JSON object with reviewed, category-specific values. Example: {"requires_obr": true}.',
    )

    class Meta:
        model = FinanceConfigurationItem
        fields = ("release", "category", "code", "version", "label", "description", "effective_from", "effective_to", "supersedes")
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")
            self.fields["supersedes"].queryset = FinanceConfigurationItem.objects.filter(department=department).exclude(status="draft")
        if self.instance.pk:
            self.fields["configuration_json"].initial = json.dumps(self.instance.configuration, indent=2, sort_keys=True)

    def clean_configuration_json(self):
        raw = self.cleaned_data["configuration_json"] or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Enter valid JSON: {exc.msg}.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("Configuration must be a JSON object.")
        return value

    def save(self, commit=True):
        instance = super().save(False)
        instance.configuration = self.cleaned_data["configuration_json"]
        if commit:
            instance.save()
        return instance


class FinanceTransactionVariantForm(forms.ModelForm):
    class Meta:
        model = FinanceTransactionVariant
        fields = (
            "release", "code", "label", "kind", "description", "authority_reference",
            "effective_from", "effective_to",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "effective_from": DateInput(), "effective_to": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(
                department=department, status="draft",
            )


class FinanceDocumentRuleForm(forms.ModelForm):
    class Meta:
        model = FinanceDocumentRule
        fields = (
            "variant", "code", "label", "evidence_kind", "required", "waiver_allowed",
            "condition_description", "authority_reference", "display_order",
        )
        widgets = {
            "condition_description": forms.Textarea(attrs={"rows": 2}),
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.fields["variant"].queryset = FinanceTransactionVariant.objects.filter(
                department=department, release__status="draft",
            ).select_related("release").order_by("release", "label")


class FinancePostingRuleForm(forms.ModelForm):
    class Meta:
        model = FinancePostingRule
        fields = (
            "variant", "code", "title", "event_kind", "recognition_point", "accounting_effect",
            "description", "authority_reference",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "authority_reference": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.fields["variant"].queryset = FinanceTransactionVariant.objects.filter(
                department=department, release__status="draft", status="draft",
            ).select_related("release").order_by("release", "label")


class FinancePostingRuleLineForm(forms.ModelForm):
    class Meta:
        model = FinancePostingRuleLine
        fields = (
            "rule", "sequence", "label", "side", "account_source", "amount_source",
            "mapping_code", "ledger_account_code", "memo",
        )

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.fields["rule"].queryset = FinancePostingRule.objects.filter(
                variant__department=department,
                variant__release__status="draft",
                variant__status="draft",
            ).select_related("variant", "variant__release").order_by("variant__label", "event_kind")


class FinanceTemplateForm(forms.ModelForm):
    class Meta:
        model = FinanceTemplateVersion
        fields = (
            "release", "document_type", "version", "title", "form_reference",
            "authority_reference", "comparison_reference", "form_status",
            "paper_size", "orientation", "default_copy_count", "printer_instructions",
            "controlled_print_required", "workbook", "effective_from", "effective_to",
        )
        widgets = {
            "authority_reference": forms.Textarea(attrs={"rows": 3}),
            "comparison_reference": forms.Textarea(attrs={"rows": 3}),
            "printer_instructions": forms.Textarea(attrs={"rows": 3}),
            "effective_from": DateInput(), "effective_to": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        if not workbook.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Upload a macro-free .xlsx workbook only.")
        return workbook


class FinanceSignatoryForm(forms.ModelForm):
    class Meta:
        model = FinanceSignatory
        fields = (
            "release", "role_code", "display_name", "position_title", "acting",
            "custody_department", "custody_instructions", "valid_from", "valid_to",
        )
        widgets = {
            "custody_instructions": forms.Textarea(attrs={"rows": 2}),
            "valid_from": DateInput(), "valid_to": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")


class FinanceStarterTemplateForm(forms.Form):
    lgu_name = forms.CharField(
        max_length=180,
        label="Local government name",
        help_text="Example: Municipality of Sample. This remains editable in Excel.",
    )
    finance_office_name = forms.CharField(max_length=180, initial="Accounting Office")
    form_title = forms.CharField(max_length=180, initial="DISBURSEMENT VOUCHER")
    form_reference = forms.CharField(
        max_length=180,
        initial="Editable starter — verify current local form",
        help_text="Enter a form number only after the municipality confirms it.",
    )
    paper_size = forms.ChoiceField(choices=FinanceTemplateVersion.PAPER_SIZE_CHOICES, initial="a4")
    orientation = forms.ChoiceField(choices=FinanceTemplateVersion.ORIENTATION_CHOICES, initial="portrait")
    particulars_rows = forms.IntegerField(
        min_value=4, max_value=24, initial=8,
        label="Rows for particulars",
        help_text="More rows make the form longer; the uploaded version will be checked before use.",
    )
    default_copy_count = forms.IntegerField(min_value=1, max_value=10, initial=2, label="Usual number of copies")
    prepared_label = forms.CharField(max_length=120, initial="Prepared by")
    certified_label = forms.CharField(max_length=120, initial="Certified / reviewed by")
    approved_label = forms.CharField(max_length=120, initial="Approved for payment by")
    footer_note = forms.CharField(
        required=False,
        initial="STARTER FOR LOCAL REVIEW — compare with the current approved blank form before official use.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class FinanceNumberingSequenceForm(forms.ModelForm):
    class Meta:
        model = FinanceNumberingSequence
        fields = ("release", "fiscal_year", "document_type", "prefix", "padding", "next_number")

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")


class FinancePartyForm(forms.ModelForm):
    class Meta:
        model = FinanceParty
        fields = (
            "release", "code", "version", "display_name", "party_type", "address",
            "tax_identifier", "effective_from", "effective_to", "supersedes",
        )
        widgets = {"effective_from": DateInput(), "effective_to": DateInput(), "address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(department=department, status="draft")
            self.fields["supersedes"].queryset = FinanceParty.objects.filter(department=department).exclude(status="draft")


class FinancePartyClaimantForm(forms.ModelForm):
    class Meta:
        model = FinancePartyClaimant
        fields = ("display_name", "relationship", "valid_from", "valid_to")
        widgets = {"valid_from": DateInput(), "valid_to": DateInput()}


class FinanceShadowCycleForm(forms.ModelForm):
    class Meta:
        model = FinanceShadowCycle
        fields = (
            "code", "title", "fiscal_year", "run_kind", "enabled_scope", "source_system_label",
            "source_extract_reference", "planned_start", "planned_end", "predecessor",
        )
        widgets = {
            "enabled_scope": forms.Textarea(attrs={"rows": 4}),
            "source_extract_reference": forms.Textarea(attrs={"rows": 3}),
            "planned_start": DateInput(), "planned_end": DateInput(),
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        if department:
            self.instance.department = department
            self.fields["predecessor"].queryset = FinanceShadowCycle.objects.filter(
                department=department,
            ).exclude(status=FinanceShadowCycle.DRAFT)


class FinanceShadowSourceUploadForm(forms.Form):
    source_file = forms.FileField(
        label="Redacted source CSV",
        help_text="UTF-8 CSV, up to 5 MB. GRAND reads headings and row count only; it does not import the rows into transactions.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv", "class": "form-control-file"}),
    )
    redaction_confirmed = forms.BooleanField(
        label="I checked this copy for sensitive information",
        help_text="Upload only the minimum redacted/read-only comparison copy—not a live database or unrestricted production export.",
    )
    redaction_note = forms.CharField(
        label="What was removed, masked, or intentionally retained?",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Use plain language, for example: payee names replaced by case IDs; bank account kept to last four digits.",
    )
    change_reason = forms.CharField(
        required=False, label="Why is the prior version being replaced?",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required from version 2 onward. Earlier versions remain in the audit trail.",
    )


class FinanceShadowExternalLockForm(forms.Form):
    source_checksum = forms.RegexField(
        regex=r"^[0-9a-fA-F]{64}$", label="Source file SHA-256",
        help_text="Advanced option: paste the 64-character checksum calculated by the approved external custody process.",
    )
    schema_signature = forms.RegexField(
        regex=r"^[0-9a-fA-F]{64}$", label="Reviewed column-layout SHA-256",
        help_text="Paste the signature for the exact reviewed column order and naming contract.",
    )
    redaction_confirmed = forms.BooleanField(label="The externally retained source is redacted/read-only")
    redaction_note = forms.CharField(
        label="Redaction and custody note", widget=forms.Textarea(attrs={"rows": 3}),
    )
    change_reason = forms.CharField(
        required=False, label="Why is the prior lock being replaced?", widget=forms.Textarea(attrs={"rows": 2}),
    )


class FinanceShadowDriftReviewForm(forms.Form):
    reason = forms.CharField(
        label="Column change and safe mapping basis",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Name the added, removed, or renamed headings and the mapping/control evidence checked. This does not change official authority.",
    )


class FinanceShadowComparisonForm(forms.ModelForm):
    class Meta:
        model = FinanceShadowComparison
        fields = (
            "comparison_level", "control_code", "label", "source_reference", "grand_reference",
            "source_amount", "grand_amount", "source_count", "grand_count", "outcome",
            "explanation", "evidence_reference", "defect_owner",
        )
        widgets = {
            "source_reference": forms.Textarea(attrs={"rows": 2}),
            "grand_reference": forms.Textarea(attrs={"rows": 2}),
            "explanation": forms.Textarea(attrs={"rows": 3}),
            "evidence_reference": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["defect_owner"].queryset = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).order_by("last_name", "first_name", "username")


class FinanceShadowReconciliationPlanForm(forms.ModelForm):
    class Meta:
        model = FinanceShadowReconciliationPlan
        fields = (
            "cadence", "first_due_at", "grace_minutes", "minimum_reviewed_runs",
            "enabled_transaction_types", "local_authority_reference", "local_acceptance_note",
            "critical_resolution_hours", "critical_escalation_route",
            "high_resolution_hours", "high_escalation_route",
            "medium_resolution_hours", "medium_escalation_route",
            "low_resolution_hours", "low_escalation_route",
        )
        widgets = {
            "first_due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "enabled_transaction_types": forms.Textarea(attrs={"rows": 3}),
            "local_authority_reference": forms.Textarea(attrs={"rows": 2}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "grace_minutes": "Minutes after each scheduled comparison time before an unfinished run is shown overdue.",
            "minimum_reviewed_runs": "The locally accepted minimum number of independently reviewed runs required before final cycle submission.",
            "local_authority_reference": "Reference the approved pilot/UAT direction, procedure, meeting decision, or other retained authority.",
            "local_acceptance_note": "State who confirmed the cadence, severity targets, and escalation routes and where that evidence is retained.",
        }


class FinanceShadowDefectForm(forms.Form):
    comparison = forms.ModelChoiceField(queryset=FinanceShadowComparison.objects.none())
    code = forms.SlugField(max_length=80, help_text="Use a short stable reference such as DV-AMOUNT-001.")
    severity = forms.ChoiceField(choices=FinanceShadowDefect.SEVERITY_CHOICES)
    summary = forms.CharField(max_length=200)
    impact = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Describe the affected transaction, control, report, office, or decision without exposing unnecessary personal data.",
    )
    owner = forms.ModelChoiceField(queryset=get_user_model().objects.none())

    def __init__(self, *args, cycle, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comparison"].queryset = cycle.comparisons.filter(
            outcome=FinanceShadowComparison.OPEN_DEFECT,
        ).exclude(defects__status__in=(FinanceShadowDefect.OPEN, FinanceShadowDefect.RESOLUTION_REVIEW))
        self.fields["owner"].queryset = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).order_by("last_name", "first_name", "username")


class FinanceShadowDefectResolutionForm(forms.Form):
    resolution_note = forms.CharField(
        label="Correction completed", widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Explain the corrected mapping, data, workflow, output, or procedure and its resulting control value.",
    )
    evidence_reference = forms.CharField(
        label="Verification evidence reference", widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Reference the retained redacted case, rerun, worksheet, output, test, or reviewer evidence.",
    )


class FinanceStakeholderAcceptanceForm(forms.ModelForm):
    class Meta:
        model = FinanceStakeholderAcceptance
        fields = ("stakeholder_kind", "office", "assigned_reviewer", "enabled_scope")
        widgets = {"enabled_scope": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_reviewer"].queryset = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).order_by("last_name", "first_name", "username")


class FinanceStakeholderDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=FinanceStakeholderAcceptance.DECISION_CHOICES[1:])
    training_evidence_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reference the role-specific guide, exercise, attendance, or supervisor check. Personal tutorial progress is not acceptance evidence.",
    )
    uat_evidence_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reference the exact synthetic/redacted scenarios and results reviewed for this scope.",
    )
    conditions_or_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") in {FinanceStakeholderAcceptance.CONDITIONAL, FinanceStakeholderAcceptance.REJECTED} and not cleaned.get("conditions_or_reason", "").strip():
            self.add_error("conditions_or_reason", "State each condition or the reason the scope is not accepted.")
        return cleaned


class FinanceCutoverDecisionForm(forms.ModelForm):
    class Meta:
        model = FinanceCutoverDecision
        fields = (
            "authority_matrix_reference", "enabled_scope", "cutover_at",
            "opening_reconciliation_reference", "rollback_criteria",
            "legacy_read_only_retention_plan", "backup_recovery_evidence",
        )
        widgets = {
            "authority_matrix_reference": forms.Textarea(attrs={"rows": 3}),
            "enabled_scope": forms.Textarea(attrs={"rows": 4}),
            "cutover_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "opening_reconciliation_reference": forms.Textarea(attrs={"rows": 3}),
            "rollback_criteria": forms.Textarea(attrs={"rows": 4}),
            "legacy_read_only_retention_plan": forms.Textarea(attrs={"rows": 4}),
            "backup_recovery_evidence": forms.Textarea(attrs={"rows": 3}),
        }
