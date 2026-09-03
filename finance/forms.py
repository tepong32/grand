import json
from datetime import datetime, time, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from reporting.models import FinanceLocalFormAcceptance

from .models import (
    FinanceCutoverDecision,
    FinanceCutoverQualificationEvidence, FinanceCutoverQualificationForm, FinanceCutoverQualificationPlan,
    FinanceCutoverReadinessExercise, FinanceCutoverReadinessPlan,
    FinanceRecoveryRehearsalEvidence,
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceDocumentRule, FinanceNumberingSequence,
    FinanceDiscoveryDecision,
    FinanceParty, FinancePartyClaimant, FinancePostingRule, FinancePostingRuleLine,
    FinanceShadowComparison, FinanceShadowCycle, FinanceShadowDefect,
    FinanceShadowReconciliationPlan, FinanceSignatory, FinanceStakeholderAcceptance,
    FinanceTemplateVersion, FinanceTransactionVariant,
    TAX_APPLICABILITY_CHOICES, TAX_FAMILY_CHOICES, TAX_REPORTING_BASIS_CHOICES,
    TAX_ROUNDING_CHOICES,
)


class DateInput(forms.DateInput):
    input_type = "date"


class FinanceReleaseForm(forms.ModelForm):
    class Meta:
        model = FinanceConfigurationRelease
        fields = ("code", "version", "title", "fiscal_year", "effective_from", "effective_to")
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}


class FinanceDiscoveryDecisionForm(forms.ModelForm):
    class Meta:
        model = FinanceDiscoveryDecision
        fields = (
            "cycle", "code", "phase", "question", "proposed_outcome",
            "affected_scope", "evidence_label", "authority_evidence_reference",
            "evidence_needed", "evidence_custody_reference", "blocks_affected_scope",
            "owner", "reviewer", "due_date", "change_reason",
        )
        widgets = {
            "question": forms.Textarea(attrs={"rows": 2}),
            "proposed_outcome": forms.Textarea(attrs={"rows": 4}),
            "affected_scope": forms.Textarea(attrs={"rows": 3}),
            "authority_evidence_reference": forms.Textarea(attrs={"rows": 3}),
            "evidence_needed": forms.Textarea(attrs={"rows": 3}),
            "evidence_custody_reference": forms.Textarea(attrs={"rows": 2}),
            "due_date": DateInput(),
            "change_reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, department=None, successor_of=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).order_by("last_name", "first_name", "username")
        self.fields["owner"].queryset = users
        self.fields["reviewer"].queryset = users
        if department:
            self.fields["cycle"].queryset = FinanceShadowCycle.objects.filter(
                department=department,
            ).order_by("-fiscal_year", "-planned_start", "code")
        if successor_of:
            self.fields["cycle"].disabled = True
            self.fields.pop("code")
        elif not getattr(self.instance, "predecessor_id", None):
            self.fields.pop("change_reason")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("evidence_label") != FinanceDiscoveryDecision.UNRESOLVED:
            if not str(cleaned.get("authority_evidence_reference") or "").strip():
                self.add_error(
                    "authority_evidence_reference",
                    "Reference the reviewed evidence before applying a non-Unresolved label.",
                )
            if not str(cleaned.get("evidence_custody_reference") or "").strip():
                self.add_error(
                    "evidence_custody_reference",
                    "State where the reviewed evidence is retained.",
                )
        if cleaned.get("evidence_label") == FinanceDiscoveryDecision.UNRESOLVED and not cleaned.get("blocks_affected_scope"):
            self.add_error(
                "blocks_affected_scope",
                "An unresolved decision must keep its named affected scope blocked.",
            )
        return cleaned


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


class FinanceTaxRuleForm(forms.ModelForm):
    tax_family = forms.ChoiceField(choices=TAX_FAMILY_CHOICES, label="Tax family")
    atc = forms.CharField(max_length=24, label="Alphanumeric tax code (ATC)")
    rate_percent = forms.DecimalField(
        max_digits=7, decimal_places=4, min_value=0.0001, max_value=100,
        label="Rate (%)",
        help_text="Enter the reviewed percentage, for example 1 or 2. Do not enter 0.01 for one percent.",
    )
    tax_base_label = forms.CharField(
        max_length=180, label="What amount the rate applies to",
        help_text="Use ordinary wording such as reviewed gross income payment, excluding locally inapplicable amounts.",
    )
    return_form_code = forms.CharField(
        max_length=40, label="Return / remittance form code",
        help_text="Example only after review: 1601-EQ. Confirm the current form and scope locally.",
    )
    certificate_form_code = forms.CharField(
        max_length=40, required=False, label="Certificate form code (if applicable)",
    )
    reporting_basis = forms.ChoiceField(
        choices=TAX_REPORTING_BASIS_CHOICES, label="Date used to place the item in a report period",
    )
    rounding_mode = forms.ChoiceField(choices=TAX_ROUNDING_CHOICES, label="Cent rounding")
    requires_tax_identifier = forms.BooleanField(
        required=False, initial=True,
        label="Require the payee's governed tax identifier before DV preparation",
    )
    authority_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Reviewed BIR / local authority reference",
    )
    applicability_status = forms.ChoiceField(
        choices=TAX_APPLICABILITY_CHOICES, label="Local applicability",
    )
    local_acceptance_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Local decision and retained evidence",
        help_text="Name who reviewed applicability, the covered transactions, and where the accepted evidence is retained.",
    )

    class Meta:
        model = FinanceConfigurationItem
        fields = (
            "release", "code", "version", "label", "description", "effective_from",
            "effective_to", "supersedes",
        )
        widgets = {"effective_from": DateInput(), "effective_to": DateInput()}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.category = "tax_rule"
        if department:
            self.instance.department = department
            self.fields["release"].queryset = FinanceConfigurationRelease.objects.filter(
                department=department, status="draft",
            )
            self.fields["supersedes"].queryset = FinanceConfigurationItem.objects.filter(
                department=department, category="tax_rule",
            ).exclude(status="draft")
        configuration = self.instance.configuration or {}
        for key in (
            "tax_family", "atc", "rate_percent", "tax_base_label", "return_form_code",
            "certificate_form_code", "reporting_basis", "rounding_mode",
            "requires_tax_identifier", "authority_reference", "applicability_status",
            "local_acceptance_note",
        ):
            if key in configuration:
                self.fields[key].initial = configuration[key]
        self.fields["reporting_basis"].initial = configuration.get("reporting_basis", "accounting_posting")
        self.fields["rounding_mode"].initial = configuration.get("rounding_mode", "half_up")
        self.fields["applicability_status"].initial = configuration.get("applicability_status", "candidate")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("applicability_status") == "locally_confirmed":
            authority = (cleaned.get("authority_reference") or "").strip()
            acceptance = (cleaned.get("local_acceptance_note") or "").strip()
            if authority.upper().startswith("EDIT BEFORE"):
                self.add_error("authority_reference", "Replace the starter warning with the reviewed authority.")
            if acceptance.upper().startswith("EDIT BEFORE"):
                self.add_error("local_acceptance_note", "Record the actual local applicability decision.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(False)
        instance.category = "tax_rule"
        instance.configuration = {
            "reporting_enabled": True,
            "tax_family": self.cleaned_data["tax_family"],
            "atc": self.cleaned_data["atc"].strip().upper(),
            "rate_percent": format(self.cleaned_data["rate_percent"].normalize(), "f"),
            "tax_base_label": self.cleaned_data["tax_base_label"].strip(),
            "return_form_code": self.cleaned_data["return_form_code"].strip().upper(),
            "certificate_form_code": self.cleaned_data["certificate_form_code"].strip().upper(),
            "reporting_basis": self.cleaned_data["reporting_basis"],
            "rounding_mode": self.cleaned_data["rounding_mode"],
            "requires_tax_identifier": self.cleaned_data["requires_tax_identifier"],
            "authority_reference": self.cleaned_data["authority_reference"].strip(),
            "applicability_status": self.cleaned_data["applicability_status"],
            "local_acceptance_note": self.cleaned_data["local_acceptance_note"].strip(),
        }
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


class FinanceCutoverReadinessPlanForm(forms.ModelForm):
    class Meta:
        model = FinanceCutoverReadinessPlan
        fields = (
            "curriculum_register_reference", "quick_guides_reference",
            "supervisor_runbook_reference", "support_owner", "support_channels_and_hours",
            "support_escalation_procedure", "local_acceptance_note",
        )
        widgets = {
            "curriculum_register_reference": forms.Textarea(attrs={"rows": 3}),
            "quick_guides_reference": forms.Textarea(attrs={"rows": 3}),
            "supervisor_runbook_reference": forms.Textarea(attrs={"rows": 3}),
            "support_channels_and_hours": forms.Textarea(attrs={"rows": 3}),
            "support_escalation_procedure": forms.Textarea(attrs={"rows": 4}),
            "local_acceptance_note": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "curriculum_register_reference": "Reference the human-readable role curriculum register and its retained version.",
            "quick_guides_reference": "List the floating Internal How-Tos, desk guides, or controlled quick guides available to each role.",
            "supervisor_runbook_reference": "Reference the supervisor observation, rerun, and acceptance instructions.",
            "support_channels_and_hours": "Name the actual help channel, operating hours, backup contact, and expected acknowledgement.",
            "support_escalation_procedure": "State the locally accepted escalation route for access, data, output, outage, and control incidents.",
            "local_acceptance_note": "State who confirmed this plan and where that decision evidence is retained.",
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        )
        if department:
            users = users.filter(employeeprofile__assigned_department=department)
        self.fields["support_owner"].queryset = users.order_by("last_name", "first_name", "username")


class FinanceCutoverReadinessExerciseForm(forms.Form):
    kind = forms.ChoiceField(choices=FinanceCutoverReadinessExercise.KIND_CHOICES)
    stakeholder_acceptance = forms.ModelChoiceField(
        queryset=FinanceStakeholderAcceptance.objects.none(), required=False,
        help_text="Required only for a role curriculum exercise. Choose the exact named stakeholder reviewer.",
    )
    code = forms.SlugField(max_length=80, help_text="Use a stable reference such as PRINT-UAT-001.")
    title = forms.CharField(max_length=200)
    enabled_scope = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    procedure = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Write the actual human-followable steps, inputs, volume, device/paper conditions, and safe fallback.",
    )
    expected_result = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="State the observable pass result, control total, response time, restored item, printed alignment, or support response.",
    )
    owner = forms.ModelChoiceField(queryset=get_user_model().objects.none())
    witness = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        help_text="Choose a different person who will independently inspect the retained result.",
    )
    scheduled_for = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    due_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, *args, cycle, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stakeholder_acceptance"].queryset = cycle.stakeholder_acceptances.select_related(
            "office", "assigned_reviewer",
        ).order_by("stakeholder_kind", "office__name", "pk")
        users = get_user_model().objects.filter(
            is_active=True, employeeprofile__assigned_department__isnull=False,
        ).order_by("last_name", "first_name", "username")
        self.fields["owner"].queryset = users
        self.fields["witness"].queryset = users
        if not self.is_bound:
            scheduled_for = timezone.make_aware(datetime.combine(cycle.planned_start, time(9, 0)))
            self.fields["enabled_scope"].initial = cycle.enabled_scope
            self.fields["scheduled_for"].initial = scheduled_for
            self.fields["due_at"].initial = scheduled_for + timedelta(hours=4)
            self.fields["procedure"].initial = (
                "1. Prepare only the approved synthetic or redacted inputs and the named device/paper/support conditions.\n"
                "2. Complete the ordinary work and one safe exception/fallback step.\n"
                "3. Compare the observable result with the expected control and retain a safe evidence reference.\n"
                "4. Contact the approved support route when the exercise calls for it."
            )
            self.fields["expected_result"].initial = (
                "The named control completes within the locally accepted condition, no unexplained difference remains, "
                "and the operator can use the documented fallback/support route without borrowed access."
            )


class FinanceCutoverReadinessExerciseResultForm(forms.Form):
    actual_result = forms.CharField(
        label="What actually happened", widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Record observable results and exceptions without unnecessary personal or production data.",
    )
    evidence_reference = forms.CharField(
        label="Retained evidence reference", widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reference the redacted script, timings, screenshot set, print sample, restore log, ticket, or signed observation sheet.",
    )


class FinanceRecoveryRehearsalResultForm(forms.ModelForm):
    actual_result = forms.CharField(
        label="What actually happened",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Summarize the witnessed two-store outcome and every exception without credentials or production personal data.",
    )
    evidence_reference = forms.CharField(
        label="Retained recovery packet reference",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reference the complete restricted rehearsal packet; do not upload dumps, credentials, or sensitive logs here.",
    )

    class Meta:
        model = FinanceRecoveryRehearsalEvidence
        fields = (
            "backup_id", "manifest_sha256", "default_artifact_sha256", "finance_artifact_sha256",
            "off_host_copy_reference", "off_host_copy_verified",
            "preflight_receipt_reference", "preflight_receipt_checksum", "preflight_passed",
            "policy_reference", "isolated_environment_reference", "release_reference",
            "database_versions", "restore_log_reference", "recovery_point_at",
            "simulated_interruption_at", "restored_at", "approved_rpo_minutes", "approved_rto_minutes",
            "default_store_restored", "finance_store_restored", "default_migrations_current",
            "finance_migrations_current", "control_totals_reconciled",
            "control_reconciliation_reference", "control_reconciliation_checksum",
            "cross_store_case_verified", "cross_store_verification_reference",
            "cross_store_verification_checksum", "runtime_files_checked",
            "runtime_files_verification_reference", "secure_disposal_completed",
            "secure_disposal_reference", "unresolved_exceptions", "exceptions_and_resolution",
        )
        widgets = {
            "off_host_copy_reference": forms.Textarea(attrs={"rows": 2}),
            "preflight_receipt_reference": forms.Textarea(attrs={"rows": 2}),
            "policy_reference": forms.Textarea(attrs={"rows": 2}),
            "isolated_environment_reference": forms.Textarea(attrs={"rows": 2}),
            "release_reference": forms.Textarea(attrs={"rows": 2}),
            "database_versions": forms.Textarea(attrs={"rows": 2}),
            "restore_log_reference": forms.Textarea(attrs={"rows": 2}),
            "recovery_point_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "simulated_interruption_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "restored_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "control_reconciliation_reference": forms.Textarea(attrs={"rows": 2}),
            "cross_store_verification_reference": forms.Textarea(attrs={"rows": 2}),
            "runtime_files_verification_reference": forms.Textarea(attrs={"rows": 2}),
            "secure_disposal_reference": forms.Textarea(attrs={"rows": 2}),
            "exceptions_and_resolution": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "backup_id": "Exact GRAND backup-set ID",
            "manifest_sha256": "Separately retained manifest SHA-256",
            "default_artifact_sha256": "Default-store artifact SHA-256",
            "finance_artifact_sha256": "Finance-store artifact SHA-256",
            "recovery_point_at": "Backup recovery point",
            "simulated_interruption_at": "Simulated interruption / RTO start",
            "restored_at": "Both stores verified restored at",
            "approved_rpo_minutes": "Approved RPO (minutes)",
            "approved_rto_minutes": "Approved RTO (minutes)",
            "unresolved_exceptions": "Unresolved recovery exceptions remain",
        }
        help_texts = {
            "manifest_sha256": "Use the hash retained separately from the copied set.",
            "off_host_copy_reference": "State the restricted destination/custody reference for the verified copied set.",
            "preflight_receipt_reference": "Reference the non-secret live production_preflight receipt for this release environment.",
            "preflight_receipt_checksum": "SHA-256 of the retained preflight receipt bytes.",
            "isolated_environment_reference": "Identify the disposable host without recording credentials or network secrets.",
            "release_reference": "Record the matching GRAND version/revision and release record.",
            "database_versions": "Record the actual MySQL/MariaDB versions used for both restored stores.",
            "restore_log_reference": "Reference the restricted command/timing log; never paste client option files or passwords.",
            "control_reconciliation_reference": "Reference the retained opening, ledger, payable, withholding, cash, and report control comparison.",
            "cross_store_verification_reference": "Reference a representative Budget–Accounting–Treasury case proven across both restored stores.",
            "runtime_files_verification_reference": "Reference checks of required media/export records without treating exports as backups.",
            "secure_disposal_reference": "Reference the approved destruction/cleanup record for the isolated restored data.",
            "exceptions_and_resolution": "Describe every exception and its resolution, or explicitly state that none occurred.",
        }

    def __init__(self, *args, exercise, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["actual_result"].initial = exercise.actual_result
            self.fields["evidence_reference"].initial = exercise.evidence_reference
        for field_name in (
            "manifest_sha256", "default_artifact_sha256", "finance_artifact_sha256",
            "preflight_receipt_checksum", "control_reconciliation_checksum",
            "cross_store_verification_checksum",
        ):
            self.fields[field_name].widget.attrs.update({"spellcheck": "false", "autocomplete": "off"})

    def recovery_values(self):
        return {name: self.cleaned_data[name] for name in self._meta.fields}


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
    signed_decision_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reference the retained wet-signed or locally accepted attributable decision record. GRAND stores the reference, not a signature image.",
    )
    signed_decision_checksum = forms.CharField(
        min_length=64, max_length=64,
        help_text="Enter the SHA-256 of the retained decision copy so later changes are detectable.",
    )
    conditions_or_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") in {FinanceStakeholderAcceptance.CONDITIONAL, FinanceStakeholderAcceptance.REJECTED} and not cleaned.get("conditions_or_reason", "").strip():
            self.add_error("conditions_or_reason", "State each condition or the reason the scope is not accepted.")
        return cleaned


class FinanceCutoverQualificationPlanForm(forms.ModelForm):
    class Meta:
        model = FinanceCutoverQualificationPlan
        fields = (
            "minimum_consecutive_cycles", "require_parallel_cycle", "local_authority_reference",
            "accepted_rules_forms_reference", "field_evidence_basis",
        )
        widgets = {
            "local_authority_reference": forms.Textarea(attrs={"rows": 3}),
            "accepted_rules_forms_reference": forms.Textarea(attrs={"rows": 4}),
            "field_evidence_basis": forms.Textarea(attrs={"rows": 4}),
        }


class FinanceCutoverQualificationFormForm(forms.ModelForm):
    class Meta:
        model = FinanceCutoverQualificationForm
        fields = ("local_form", "position", "use_instructions")
        widgets = {"use_instructions": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["local_form"].queryset = FinanceLocalFormAcceptance.objects.filter(
            status=FinanceLocalFormAcceptance.ACCEPTED,
        ).select_related("department").order_by("department__name", "code", "version")
        self.fields["local_form"].label_from_instance = lambda item: (
            f"{item.department.name} · {item.name}"
            f"{f' ({item.form_number})' if item.form_number else ''} · v{item.version}"
        )
        self.fields["local_form"].help_text = (
            "Only independently accepted F10.2 form versions appear here. Their protected reference files remain in the form register."
        )


class FinanceCutoverQualificationEvidenceForm(forms.ModelForm):
    class Meta:
        model = FinanceCutoverQualificationEvidence
        fields = ("cycle", "sequence", "field_execution_reference", "rules_forms_reference")
        widgets = {
            "field_execution_reference": forms.Textarea(attrs={"rows": 4}),
            "rules_forms_reference": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, candidate_cycle=None, **kwargs):
        super().__init__(*args, **kwargs)
        if candidate_cycle:
            self.fields["cycle"].queryset = FinanceShadowCycle.objects.filter(
                department=candidate_cycle.department,
                fiscal_year=candidate_cycle.fiscal_year,
                enabled_scope=candidate_cycle.enabled_scope,
                status=FinanceShadowCycle.RECONCILED,
            ).order_by("planned_start", "code")
            self.fields["cycle"].help_text = (
                "Choose from reconciled cycles with this exact Finance office, fiscal year, and enabled scope. "
                "Sequence 1 is oldest; the candidate cycle must be last."
            )


class FinanceCutoverDecisionForm(forms.ModelForm):
    class Meta:
        model = FinanceCutoverDecision
        fields = (
            "authority_matrix_reference", "enabled_scope", "cutover_at",
            "opening_reconciliation_reference", "rollback_criteria",
            "legacy_read_only_retention_plan", "backup_recovery_evidence",
            "recovery_rehearsal",
            "signed_authority_reference", "signed_authority_checksum", "signature_custody_reference",
        )
        widgets = {
            "authority_matrix_reference": forms.Textarea(attrs={"rows": 3}),
            "enabled_scope": forms.Textarea(attrs={"rows": 4}),
            "cutover_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "opening_reconciliation_reference": forms.Textarea(attrs={"rows": 3}),
            "rollback_criteria": forms.Textarea(attrs={"rows": 4}),
            "legacy_read_only_retention_plan": forms.Textarea(attrs={"rows": 4}),
            "backup_recovery_evidence": forms.Textarea(attrs={"rows": 3}),
            "signed_authority_reference": forms.Textarea(attrs={"rows": 3}),
            "signature_custody_reference": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, cycle=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recovery_rehearsal"].required = True
        self.fields["recovery_rehearsal"].queryset = FinanceRecoveryRehearsalEvidence.objects.none()
        if cycle:
            self.fields["recovery_rehearsal"].queryset = FinanceRecoveryRehearsalEvidence.objects.filter(
                exercise__cycle=cycle,
                exercise__kind=FinanceCutoverReadinessExercise.BACKUP_RESTORE,
                exercise__status=FinanceCutoverReadinessExercise.PASSED,
            ).select_related("exercise").order_by("-restored_at", "-pk")
            self.fields["recovery_rehearsal"].help_text = (
                "Choose the independently passed two-store rehearsal for this cycle. "
                "The cutover record pins its backup ID and evidence checksum."
            )
        for field_name in ("signed_authority_reference", "signed_authority_checksum", "signature_custody_reference"):
            self.fields[field_name].required = True
