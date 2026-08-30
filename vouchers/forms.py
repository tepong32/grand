from __future__ import annotations

import uuid
from decimal import Decimal

from django import forms
from django.db.models import Q, Sum
from django.utils import timezone

from departments.models import Department
from budget.models import ObligationMovement, ObligationRequest, PayableObligationAllocation
from budget.services import obligation_lineage_request_ids
from accounting.models import Fund
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceParty, FinancePartyClaimant, FinanceSignatory,
    FinanceTransactionVariant,
)

from .models import (
    PayableDocumentEvidence, PayableIntake, PaymentInstrument, VoucherCase,
    PaymentInstrumentException, TreasuryCashPolicy, TreasuryCashPosition,
    TreasuryRemittanceLine, VoucherPrintJob, WetSignatureTask,
)


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


def _obligation_capacity(obligation, *, exclude_case_public_id=None):
    current = ObligationMovement.objects.filter(
        request_id__in=obligation_lineage_request_ids(obligation),
    ).aggregate(total=Sum("obligation_effect"))["total"] or Decimal("0")
    allocations = PayableObligationAllocation.objects.filter(
        obligation=obligation, status=PayableObligationAllocation.ACTIVE,
    )
    if exclude_case_public_id:
        allocations = allocations.exclude(voucher_case_public_id=exclude_case_public_id)
    allocated = allocations.aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0")
    return current, current - allocated


def _eligible_obligations(department, *, exclude_case_public_id=None, exclude_existing_case=False):
    if not department:
        return ObligationRequest.objects.none()
    candidates = list(ObligationRequest.objects.filter(
        status=ObligationRequest.CERTIFIED,
        kind=ObligationRequest.ORIGINAL,
        requesting_department_id=department.pk,
    ).order_by("-obligation_date", "-pk"))
    eligible = []
    for obligation in candidates:
        if exclude_existing_case and exclude_case_public_id and PayableObligationAllocation.objects.filter(
            obligation=obligation,
            voucher_case_public_id=exclude_case_public_id,
            status=PayableObligationAllocation.ACTIVE,
        ).exists():
            continue
        _current, remaining = _obligation_capacity(
            obligation, exclude_case_public_id=exclude_case_public_id,
        )
        if remaining > Decimal("0"):
            eligible.append(obligation.pk)
    return ObligationRequest.objects.filter(pk__in=eligible).order_by("-obligation_date", "-pk")


class PayableIntakeForm(forms.Form):
    authoritative_obligation = CertifiedObligationChoiceField(
        queryset=ObligationRequest.objects.none(), label="Certified obligation",
        help_text="Certified original obligations with unallocated claim capacity in your current department are available.",
    )
    payee = forms.ModelChoiceField(queryset=FinanceParty.objects.none(), label="Governed supplier / payee")
    transaction_type = forms.ChoiceField()
    claim_reference = forms.CharField(max_length=120, help_text="Requesting-office claim, billing, or packet reference")
    invoice_number = forms.CharField(max_length=120, required=False)
    invoice_date = forms.DateField(widget=DateInput, required=False)
    claim_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    initial_allocation_amount = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01"),
        help_text="Allocate this much of the selected obligation now. The claim control may be larger when more obligations will be added.",
    )
    initial_relationship_type = forms.ChoiceField(
        choices=PayableIntake.RELATIONSHIP_CHOICES,
        label="Relationship to selected obligation",
    )
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
            self.fields["authoritative_obligation"].queryset = _eligible_obligations(department)
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
        claim_amount = cleaned.get("claim_amount")
        allocation_amount = cleaned.get("initial_allocation_amount")
        relationship = cleaned.get("initial_relationship_type")
        if claim_amount is not None and allocation_amount is not None and allocation_amount > claim_amount:
            self.add_error("initial_allocation_amount", "The initial allocation cannot exceed the payable claim control total.")
        if obligation and allocation_amount is not None:
            _current, remaining = _obligation_capacity(obligation)
            if allocation_amount > remaining:
                self.add_error("initial_allocation_amount", "The allocation exceeds the obligation's unallocated claim capacity.")
            if relationship in (PayableIntake.FULL, PayableIntake.FINAL) and allocation_amount != remaining:
                self.add_error("initial_allocation_amount", "A one-time/full or final allocation must consume the exact remaining obligation capacity.")
            if relationship in (PayableIntake.PARTIAL, PayableIntake.PROGRESS) and allocation_amount >= remaining:
                self.add_error("initial_allocation_amount", "A partial or progress allocation must leave a positive obligation balance.")
        return cleaned


class RemittanceBatchForm(forms.Form):
    configuration_release = forms.ModelChoiceField(queryset=FinanceConfigurationRelease.objects.none(), label="Approved Finance setup")
    transaction_variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(), label="Transaction / withholding group")
    recipient_party = forms.ModelChoiceField(queryset=FinanceParty.objects.none(), label="Receiving government agency")
    fund_code = forms.ChoiceField(label="Fund")
    bank_account_code = forms.ChoiceField(label="Bank / payment account")
    remittance_date = forms.DateField(widget=DateInput)
    payment_method = forms.CharField(max_length=80, help_text="For example: check, debit advice, electronic transfer, or other locally accepted method.")
    authority_reference = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), help_text="Record the reviewed COA/BIR/GSIS/PhilHealth/Pag-IBIG/local basis that applies; public guidance alone is not local acceptance.")
    evidence_reference = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), help_text="Reference the reviewed schedule, return, advice, or source packet without copying sensitive contents.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        releases = FinanceConfigurationRelease.objects.filter(status="active", effective_from__lte=today).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        self.fields["configuration_release"].queryset = releases
        release = None
        release_id = self.data.get("configuration_release") if self.is_bound else None
        if release_id and str(release_id).isdigit():
            release = releases.filter(pk=int(release_id)).first()
        if release is None:
            release = releases.order_by("-activated_at", "-pk").first()
        self.fields["configuration_release"].initial = release
        self.fields["transaction_variant"].queryset = FinanceTransactionVariant.objects.filter(release=release, status="active") if release else FinanceTransactionVariant.objects.none()
        self.fields["recipient_party"].queryset = FinanceParty.objects.filter(release=release, status="active", party_type=FinanceParty.AGENCY) if release else FinanceParty.objects.none()
        self.fields["fund_code"].choices = _items(release, "fund")
        self.fields["bank_account_code"].choices = _items(release, "bank_account")
        self.fields["remittance_date"].initial = today

    def clean(self):
        cleaned = super().clean()
        release = cleaned.get("configuration_release")
        for field in ("transaction_variant", "recipient_party"):
            item = cleaned.get(field)
            if release and item and item.release_id != release.pk:
                self.add_error(field, "Choose an active item from the selected Finance setup release.")
        return cleaned


class RemittanceLineForm(forms.Form):
    balance = forms.ChoiceField(label="Posted withholding balance")
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), initial="Included in the reviewed remittance schedule.")

    def __init__(self, *args, batch=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .remittances import withholding_availability
        rows = withholding_availability(finance_department_id=batch.finance_department_id, transaction_type=batch.transaction_variant.code, as_of_date=batch.remittance_date) if batch else []
        rows = [row for row in rows if row["fund_code"] == batch.fund_code]
        self.fields["balance"].choices = [
            (row["choice_key"], f"{row['reference_label']} · {row['account_code']} · available {row['available']:,.2f}")
            for row in rows
        ]


class RemittanceLineRevisionForm(forms.Form):
    revised_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.00"), help_text="Enter zero to remove this allocation before release.")
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), help_text="Explain the correction. GRAND keeps both versions.")

    def __init__(self, *args, line=None, **kwargs):
        super().__init__(*args, **kwargs)
        if line:
            self.fields["revised_amount"].initial = line.amount


class RemittanceReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=(("approve", "Approve for Treasury release"), ("return", "Return for correction")))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Review basis / correction instructions")


class RemittanceReleaseForm(forms.Form):
    release_reference = forms.CharField(max_length=160, label="Bank / payment release reference")
    acknowledgement_reference = forms.CharField(max_length=160, required=False, label="Agency acknowledgement / official receipt reference")


class PayableAllocationAddForm(WorkflowForm):
    authoritative_obligation = CertifiedObligationChoiceField(
        queryset=ObligationRequest.objects.none(), label="Additional certified obligation",
    )
    allocation_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    relationship_type = forms.ChoiceField(choices=PayableIntake.RELATIONSHIP_CHOICES)
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Explain why this obligation supports the same payable claim.",
    )

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case:
            self.fields["authoritative_obligation"].queryset = _eligible_obligations(
                case.requesting_department,
                exclude_case_public_id=case.public_id,
                exclude_existing_case=True,
            )

    def clean(self):
        cleaned = super().clean()
        obligation = cleaned.get("authoritative_obligation")
        amount = cleaned.get("allocation_amount")
        relationship = cleaned.get("relationship_type")
        if obligation and amount is not None:
            _current, remaining = _obligation_capacity(obligation)
            if amount > remaining:
                self.add_error("allocation_amount", "The allocation exceeds the obligation's unallocated claim capacity.")
            if relationship in (PayableIntake.FULL, PayableIntake.FINAL) and amount != remaining:
                self.add_error("allocation_amount", "A one-time/full or final allocation must consume the exact remaining obligation capacity.")
            if relationship in (PayableIntake.PARTIAL, PayableIntake.PROGRESS) and amount >= remaining:
                self.add_error("allocation_amount", "A partial or progress allocation must leave a positive obligation balance.")
        return cleaned


class PayableAllocationRevisionForm(WorkflowForm):
    allocation = forms.ChoiceField(label="Current obligation allocation")
    revised_amount = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.00"),
        help_text="Enter zero to remove this relationship before DV issuance.",
    )
    relationship_type = forms.ChoiceField(choices=PayableIntake.RELATIONSHIP_CHOICES)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case:
            active = PayableObligationAllocation.objects.filter(
                voucher_case_public_id=case.public_id,
                status=PayableObligationAllocation.ACTIVE,
            ).select_related("obligation").order_by("obligation__obligation_number")
            self.fields["allocation"].choices = [
                (
                    str(item.public_id),
                    f"{item.obligation.obligation_number} — {item.allocated_amount:,.2f} — {item.get_relationship_type_display()}",
                )
                for item in active
            ]


class PayableClaimControlForm(WorkflowForm):
    claim_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Explain the reviewed claim-control change. Allocation totals must reconcile before submission.",
    )

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case and hasattr(case, "payable_intake"):
            self.fields["claim_amount"].initial = case.payable_intake.claim_amount


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
    recognition_decision = forms.ChoiceField(choices=PayableIntake.RECOGNITION_CHOICES, required=False)
    recognition_basis = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    obligation_adjustment_decision = forms.ChoiceField(choices=PayableIntake.ADJUSTMENT_CHOICES, required=False)
    obligation_adjustment_basis = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") == PayableIntake.READY:
            for field in (
                "recognition_decision", "recognition_basis",
                "obligation_adjustment_decision", "obligation_adjustment_basis",
            ):
                if not cleaned.get(field):
                    self.add_error(field, "Required when accepting a payable as ready.")
        return cleaned


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


class ControlledPrintPrepareForm(WorkflowForm):
    replacement_reason = forms.CharField(
        required=False,
        label="Reason for replacing the earlier signing copy",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Leave blank for the first signing copy. A reprint must explain why the earlier copy must not be signed.",
    )


class PrintEvidenceForm(WorkflowForm):
    copy_count = forms.IntegerField(min_value=1, max_value=20, label="Number of copies actually printed")
    printer_or_form_stock = forms.CharField(
        max_length=180,
        label="Printer / paper used",
        help_text="Plain description only, for example: Accounting printer 1 · A4 bond · single-sided.",
    )
    print_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional note about alignment, spoiled copies, or assembly handling.",
    )

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        if case and case.voucher_template_id:
            self.fields["copy_count"].initial = case.voucher_template.default_copy_count
            self.fields["printer_or_form_stock"].initial = case.voucher_template.printer_instructions


class FinancePacketAssemblyForm(WorkflowForm):
    expected_document_count = forms.IntegerField(
        min_value=1, max_value=500, initial=1,
        label="Expected documents in the packet",
    )
    expected_page_count = forms.IntegerField(
        required=False, min_value=1, max_value=10000,
        label="Expected page count (if counted)",
    )
    confidentiality = forms.ChoiceField(
        choices=(("internal", "Internal"), ("restricted", "Restricted"), ("confidential", "Confidential / sensitive")),
        initial="restricted",
        help_text="Custody users see the packet identity and route, not voucher amounts.",
    )
    assembly_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        initial="Controlled DV signing copy and referenced supporting documents counted and assembled.",
        label="Packet assembly note",
    )


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
    fund_code = forms.ChoiceField(label="Cash fund", required=False)
    check_number = forms.CharField(max_length=60)
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    replaces = forms.ModelChoiceField(queryset=PaymentInstrument.objects.none(), required=False, label="Replaces cancelled check")

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        self.fields["bank_account_code"].choices = _items(case.configuration_release if case else None, "bank_account")
        funds = []
        if case and hasattr(case, "obligation"):
            codes = case.obligation.allocation_lines.values_list("fund_code", flat=True).distinct()
            funds = [(code, code) for code in codes]
        self.fields["fund_code"].choices = funds
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
        (VoucherCase.PAYABLE_PREPARATION, "Requesting-office payable preparation"),
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


class TreasuryCashPolicyForm(forms.Form):
    configuration_release = forms.ModelChoiceField(
        queryset=FinanceConfigurationRelease.objects.none(), label="Approved Finance setup",
    )
    bank_account_code = forms.ChoiceField(label="Bank / payment account")
    fund_code = forms.ChoiceField(label="Accounting fund")
    mode = forms.ChoiceField(choices=TreasuryCashPolicy.MODE_CHOICES, label="Control mode")
    minimum_reserve = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.00"))
    position_max_age_days = forms.IntegerField(min_value=1, max_value=366, initial=35, label="Maximum position age (days)")
    unclaimed_after_days = forms.IntegerField(min_value=1, max_value=366, initial=30, label="Mark unclaimed after (days)")
    stale_after_days = forms.IntegerField(min_value=2, max_value=730, initial=180, label="Mark stale after (days)")
    effective_from = forms.DateField(widget=DateInput)
    effective_to = forms.DateField(widget=DateInput, required=False)
    authority_reference = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Name the reviewed COA/DBM/bank/local issuance or approved procedure.",
    )
    local_applicability_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain who accepted this rule locally and where the signed or approved basis is kept.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        releases = FinanceConfigurationRelease.objects.filter(
            status="active", effective_from__lte=today,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).order_by("-fiscal_year", "title")
        self.fields["configuration_release"].queryset = releases
        release_id = self.data.get("configuration_release") or self.initial.get("configuration_release")
        release = releases.filter(pk=release_id).first() if release_id else releases.first()
        self.fields["bank_account_code"].choices = _items(release, "bank_account")
        self.fields["fund_code"].choices = list(
            Fund.objects.filter(department_id=release.department_id, is_active=True).order_by("code").values_list("code", "name")
        ) if release else []
        self.fields["effective_from"].initial = today

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("stale_after_days", 0) <= cleaned.get("unclaimed_after_days", 0):
            self.add_error("stale_after_days", "The stale threshold must be later than the unclaimed threshold.")
        return cleaned


class TreasuryCashPositionForm(forms.Form):
    as_of_date = forms.DateField(widget=DateInput)
    confirmed_inflows = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.00"), initial=Decimal("0.00"),
        help_text="Confirmed credits after the reconciled period; do not include hopeful forecasts.",
    )
    confirmed_outflows = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.00"), initial=Decimal("0.00"),
        help_text="Confirmed withdrawals after the reconciled period that are not already reserved here.",
    )
    other_holds = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.00"), initial=Decimal("0.00"),
        help_text="Restricted or earmarked cash excluded by the locally approved policy.",
    )
    evidence_reference = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    preparation_note = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["as_of_date"].initial = timezone.localdate()


class TreasuryCashReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=(("approve", "Approve"), ("return", "Return for correction")))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Review basis / correction instruction")


class InstrumentExceptionForm(forms.Form):
    instrument = forms.ModelChoiceField(queryset=PaymentInstrument.objects.none())
    kind = forms.ChoiceField(choices=PaymentInstrumentException.KIND_CHOICES)
    observed_on = forms.DateField(widget=DateInput)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    evidence_reference = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instrument"].queryset = PaymentInstrument.objects.exclude(
            status__in=(PaymentInstrument.DRAFT, PaymentInstrument.CANCELLED),
        ).select_related("case").order_by("-issued_at", "check_number")
        self.fields["observed_on"].initial = timezone.localdate()


class InstrumentExceptionResolutionForm(forms.Form):
    resolution = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Record the claimant contact, cancellation/replacement, bank acknowledgement, or Accounting correction reference.",
    )


class TracePointLinkForm(WorkflowForm):
    reference_number = forms.CharField(max_length=50, label="TracePoint item reference")
