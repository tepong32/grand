from __future__ import annotations

import uuid
from decimal import Decimal

from django import forms
from django.db.models import Q, Sum
from django.utils import timezone

from departments.models import Department
from budget.models import ObligationRequest
from finance.models import (
    FinanceConfigurationItem, FinanceParty, FinancePartyClaimant, FinanceSignatory,
    FinanceTransactionVariant,
)

from .models import PayableDocumentEvidence, PayableIntake, PaymentInstrument, VoucherCase, WetSignatureTask


class DateInput(forms.DateInput):
    input_type = "date"


class WorkflowForm(forms.Form):
    state_version = forms.IntegerField(widget=forms.HiddenInput)
    idempotency_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, case=None, **kwargs):
        initial = kwargs.setdefault("initial", {})
        if case is not None:
            initial.setdefault("state_version", case.state_version)
        initial.setdefault("idempotency_key", uuid.uuid4().hex)
        super().__init__(*args, **kwargs)


def _items(release, category):
    if not release:
        return []
    return list(
        FinanceConfigurationItem.objects.filter(release=release, category=category, status="active")
        .order_by("label").values_list("code", "label")
    )


class BudgetCaseForm(forms.Form):
    requesting_department = forms.ModelChoiceField(queryset=Department.objects.none())
    payee = forms.ModelChoiceField(queryset=FinanceParty.objects.none(), label="Supplier / payee")
    transaction_type = forms.ChoiceField()
    particulars = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    idempotency_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, release=None, **kwargs):
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("idempotency_key", uuid.uuid4().hex)
        super().__init__(*args, **kwargs)
        self.fields["requesting_department"].queryset = Department.objects.order_by("name")
        if release:
            today = timezone.localdate()
            self.fields["payee"].queryset = FinanceParty.objects.filter(
                release=release, status="active", effective_from__lte=today,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).order_by("display_name")
            self.fields["transaction_type"].choices = _items(release, "transaction_type")


class CertifiedObligationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obligation):
        return (
            f"{obligation.obligation_number} — {obligation.claimant_payee} — "
            f"{obligation.signed_control_total:,.2f}"
        )


class PayableIntakeForm(forms.Form):
    authoritative_obligation = CertifiedObligationChoiceField(
        queryset=ObligationRequest.objects.none(), label="Certified obligation",
        help_text="Only unlinked original obligations belonging to your current department are available.",
    )
    payee = forms.ModelChoiceField(queryset=FinanceParty.objects.none(), label="Governed supplier / payee")
    transaction_type = forms.ChoiceField()
    claim_reference = forms.CharField(max_length=120, help_text="Requesting-office claim, billing, or packet reference")
    invoice_number = forms.CharField(max_length=120, required=False)
    invoice_date = forms.DateField(widget=DateInput, required=False)
    claim_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    procurement_reference = forms.CharField(max_length=180, required=False)
    delivery_reference = forms.CharField(max_length=180, required=False)
    inspection_acceptance_reference = forms.CharField(max_length=180, required=False)
    evidence_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reference the applicable request, procurement, delivery, inspection/acceptance, invoice, and claim evidence.",
    )
    duplicate_review_note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional human review note for a similar payee/invoice/claim warning.",
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, release=None, department=None, **kwargs):
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("idempotency_key", uuid.uuid4().hex)
        super().__init__(*args, **kwargs)
        if department:
            queryset = ObligationRequest.objects.filter(
                status=ObligationRequest.CERTIFIED,
                kind=ObligationRequest.ORIGINAL,
                requesting_department_id=department.pk,
                linked_voucher_case_public_id__isnull=True,
            ).order_by("-obligation_date", "-pk")
            self.fields["authoritative_obligation"].queryset = queryset
        if release:
            today = timezone.localdate()
            self.fields["payee"].queryset = FinanceParty.objects.filter(
                release=release, status="active", effective_from__lte=today,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).order_by("display_name")
            typed = list(
                FinanceTransactionVariant.objects.filter(
                    release=release, status="active", effective_from__lte=today,
                ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
                .order_by("label").values_list("code", "label")
            )
            self.fields["transaction_type"].choices = typed or _items(release, "transaction_type")

    def clean(self):
        cleaned = super().clean()
        obligation = cleaned.get("authoritative_obligation")
        amount = cleaned.get("claim_amount")
        if obligation and amount is not None:
            from budget.services import obligation_lineage_request_ids
            from budget.models import ObligationMovement
            total = ObligationMovement.objects.filter(
                request_id__in=obligation_lineage_request_ids(obligation),
            ).aggregate(total=Sum("obligation_effect"))["total"] or Decimal("0")
            if amount != total:
                self.add_error(
                    "claim_amount",
                    "The payable must equal the current certified obligation lineage. "
                    "Use a governed obligation adjustment before intake when the final claim differs.",
                )
        return cleaned


class PayableEvidenceForm(WorkflowForm):
    evidence = forms.ModelChoiceField(queryset=PayableDocumentEvidence.objects.none(), label="Checklist item")
    status = forms.ChoiceField(choices=PayableDocumentEvidence.STATUS_CHOICES)
    evidence_reference = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Reference the source record; do not paste sensitive source content.",
    )
    decision_note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required for a conditional not-applicable decision or authorized waiver.",
    )

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case:
            self.fields["evidence"].queryset = case.payable_document_evidence.order_by(
                "source_rule__display_order", "requirement_code",
            )


class PayableSubmitForm(WorkflowForm):
    pass


class PayableReviewForm(WorkflowForm):
    decision = forms.ChoiceField(choices=((PayableIntake.READY, "Accept as payment-ready"), (PayableIntake.RETURNED, "Return for correction")))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))


class BudgetCertificationForm(WorkflowForm):
    obligation_date = forms.DateField(widget=DateInput)
    budget_source_reference = forms.CharField(max_length=160, help_text="Existing approved appropriation/allotment source reference")
    fund_code = forms.ChoiceField(label="Fund")
    responsibility_center_code = forms.ChoiceField(label="Responsibility center")
    account_code = forms.ChoiceField(label="Account / expenditure code", required=False)
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        release = case.configuration_release if case else None
        self.fields["fund_code"].choices = _items(release, "fund")
        self.fields["responsibility_center_code"].choices = _items(release, "responsibility_center")
        self.fields["account_code"].choices = [("", "— Optional —")] + _items(release, "account_classification")
        self.fields["obligation_date"].initial = timezone.localdate()


class VoucherPreparationForm(WorkflowForm):
    voucher_date = forms.DateField(widget=DateInput)
    gross_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    line_description = forms.CharField(max_length=240)
    line_account_code = forms.ChoiceField(label="Account / expenditure code")
    deduction_code = forms.ChoiceField(required=False)
    deduction_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"), required=False)
    document_codes = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False, label="Supporting documents present")

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        release = case.configuration_release if case else None
        self.fields["line_account_code"].choices = _items(release, "account_classification")
        self.fields["deduction_code"].choices = [("", "— No deduction —")] + _items(release, "tax_rule")
        self.fields["document_codes"].choices = _items(release, "document_requirement")
        self.fields["voucher_date"].initial = timezone.localdate()
        if case and hasattr(case, "obligation"):
            self.fields["gross_amount"].initial = case.obligation.certified_amount
            self.fields["line_description"].initial = case.particulars

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("deduction_code")) != bool(cleaned.get("deduction_amount")):
            raise forms.ValidationError("Select both a deduction rule and amount, or leave both blank.")
        return cleaned


class SignatureReturnForm(WorkflowForm):
    task = forms.ModelChoiceField(queryset=WetSignatureTask.objects.none(), label="Returned wet-signature step")
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case:
            self.fields["task"].queryset = case.signature_tasks.filter(status=WetSignatureTask.PENDING).order_by("sequence")


class SignatorySelectionField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, signatory):
        acting = " · acting" if signatory.acting else ""
        return f"{signatory.role_code} — {signatory.display_name} ({signatory.position_title}{acting})"


class NonFinancialAmendmentForm(WorkflowForm):
    voucher_date = forms.DateField(
        label="Disbursement voucher date",
        widget=DateInput,
        help_text="This does not change the JEV posting date or accounting period.",
    )
    signatories = SignatorySelectionField(
        queryset=FinanceSignatory.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Choose exactly one approved person for every required signature role.",
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain the date or signatory correction for the permanent audit trail.",
    )

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if not case or not hasattr(case, "disbursement_voucher"):
            return
        department_id = case.configuration_release.department_id
        queryset = FinanceSignatory.objects.filter(
            department_id=department_id, status="active",
        ).select_related("release").order_by("role_code", "display_name", "pk")
        self.fields["signatories"].queryset = queryset
        self.fields["voucher_date"].initial = case.disbursement_voucher.voucher_date
        latest_round = case.signature_tasks.order_by("-round_number").values_list("round_number", flat=True).first()
        if latest_round:
            current = case.signature_tasks.filter(round_number=latest_round)
            selected = []
            for task in current:
                match = queryset.filter(
                    role_code=task.role_code,
                    display_name=task.signatory_name_snapshot,
                    position_title=task.position_snapshot,
                ).first()
                if match:
                    selected.append(match.pk)
            self.fields["signatories"].initial = selected

    def clean(self):
        cleaned = super().clean()
        voucher_date = cleaned.get("voucher_date")
        signatories = list(cleaned.get("signatories") or [])
        if not voucher_date:
            return cleaned
        invalid = [
            item for item in signatories
            if item.valid_from > voucher_date or (item.valid_to and item.valid_to < voucher_date)
        ]
        if invalid:
            self.add_error("signatories", "Every selected signatory must be valid on the revised voucher date.")
        roles = [item.role_code for item in signatories]
        if len(roles) != len(set(roles)):
            self.add_error("signatories", "Choose only one person for each signature role.")
        return cleaned


class AccountingValidationForm(WorkflowForm):
    jev_number = forms.CharField(max_length=60)
    jev_date = forms.DateField(widget=DateInput)
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        self.fields["jev_date"].initial = timezone.localdate()


class CheckIssueForm(WorkflowForm):
    bank_account_code = forms.ChoiceField(label="Bank / payment account")
    check_number = forms.CharField(max_length=60)
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    replaces = forms.ModelChoiceField(queryset=PaymentInstrument.objects.none(), required=False, label="Replaces cancelled check")

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        self.fields["bank_account_code"].choices = _items(case.configuration_release if case else None, "bank_account")
        if case and hasattr(case, "disbursement_voucher"):
            existing = sum((item.amount for item in case.payment_instruments.exclude(status=PaymentInstrument.CANCELLED)), Decimal("0.00"))
            self.fields["amount"].initial = case.disbursement_voucher.net_amount - existing
            self.fields["replaces"].queryset = case.payment_instruments.filter(status=PaymentInstrument.CANCELLED, replacement__isnull=True)


class BankAdviceForm(WorkflowForm):
    advice_number = forms.CharField(max_length=60)
    advice_date = forms.DateField(widget=DateInput)

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        self.fields["advice_date"].initial = timezone.localdate()


class CheckReleaseForm(WorkflowForm):
    instrument = forms.ModelChoiceField(queryset=PaymentInstrument.objects.none())
    claimant = forms.ModelChoiceField(queryset=FinancePartyClaimant.objects.none(), label="Authorized claimant")
    receipt_reference = forms.CharField(max_length=120)

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case:
            self.fields["instrument"].queryset = case.payment_instruments.filter(status=PaymentInstrument.ADVISED)
            self.fields["claimant"].queryset = FinancePartyClaimant.objects.filter(
                party=case.payee, status="active", valid_from__lte=timezone.localdate(),
            ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=timezone.localdate()))


class SubmitChecksForm(WorkflowForm):
    pass


class ReturnCaseForm(WorkflowForm):
    target_stage = forms.ChoiceField(choices=(
        (VoucherCase.ACCOUNTING_PREPARATION, "Accounting DV preparation"),
        (VoucherCase.AWAITING_SIGNATURES, "Wet signatures"),
        (VoucherCase.ACCOUNTING_VALIDATION, "Accounting validation"),
        (VoucherCase.TREASURY_CHECK_PREPARATION, "Treasury check preparation"),
        (VoucherCase.ACCOUNTING_BANK_ADVICE, "Accounting bank advice"),
    ))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))


class CancelCheckForm(WorkflowForm):
    instrument = forms.ModelChoiceField(queryset=PaymentInstrument.objects.none())
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case:
            self.fields["instrument"].queryset = case.payment_instruments.filter(status__in=(PaymentInstrument.ISSUED, PaymentInstrument.ADVISED))


class TracePointLinkForm(WorkflowForm):
    reference_number = forms.CharField(max_length=50, label="TracePoint item reference")
