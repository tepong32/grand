"""A cancelled check must not strand an otherwise reversible deduction/DV."""
from datetime import date
from decimal import Decimal

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse

from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import test_deduction_corrections as fixtures
from .models import VoucherCase, PaymentInstrument
from .services import (issue_check, cancel_check, prepare_voucher, validate_accounting,
    submit_checks_for_advice, finalize_bank_advice, release_check,
    prepare_controlled_dv_print, record_dv_printed, assemble_finance_packet)
from .forms import CheckIssueForm
from accounting.payables import _capacity


class CancelledCheckCorrectionTests(fixtures.DeductionCorrectionTests):
    def setUp(self):
        fixtures.fixtures.PriorPayableDVTests.setUp(self)
        # Establish the synthetic policy before the DV pins validation evidence.
        if self._testMethodName == "test_posted_issuance_and_exact_cancellation_allow_deduction_correction":
            Rule.objects.filter(pk=self.payment_rule.pk).update(recognition_point=Rule.PAYMENT_ISSUANCE)
            for kind in (Rule.CANCELLATION, Rule.REPLACEMENT):
                rule = Rule.objects.get(variant=self.transaction_variant, event_kind=kind)
                Rule.objects.filter(pk=rule.pk).update(accounting_effect=Rule.JOURNAL_ENTRY)
                restoring = kind == Rule.CANCELLATION
                Line.objects.bulk_create([
                    Line(rule=rule, sequence=1, label="Original payable", side=Line.CREDIT if restoring else Line.DEBIT,
                        account_source=Line.PRIOR_PAYABLE, amount_source=Line.EVENT_AMOUNT),
                    Line(rule=rule, sequence=2, label="Bank", side=Line.DEBIT if restoring else Line.CREDIT,
                        account_source=Line.BANK_MAPPING, amount_source=Line.EVENT_AMOUNT, cash_flow_category="op_suppliers")])
        self.case = self.case_for_validation(deductions=True)
        self.validate(self.case)
        self.original_request = self.case.posting_requests.get(kind=Rule.ADJUSTMENT)
        self.adjustment = self.post_request(self.original_request)
        self.case.refresh_from_db()

    def cancel_before_correction(self, *, issuance=False):
        instrument = issue_check(case=self.case, actor=self.treasury_user, bank_account_code="gf-lbp",
            fund_code="general-fund", check_number="CORRECTION-CANCELLED", amount=900,
            expected_version=self.case.state_version, idempotency_key="issue-before-correction")
        if issuance:
            self.post_request(self.case.posting_requests.get(kind=Rule.PAYMENT))
        self.case.refresh_from_db()
        cancel_check(case=self.case, instrument=instrument, actor=self.treasury_user,
            reason="Cancel check before correcting the deduction", expected_version=self.case.state_version,
            idempotency_key="cancel-before-correction")
        cancellation = self.case.posting_requests.get(kind=Rule.CANCELLATION)
        if issuance:
            self.post_request(cancellation)
        self.case.refresh_from_db(); instrument.refresh_from_db()
        self.assertEqual(instrument.status, PaymentInstrument.CANCELLED)
        self.assertEqual(self.case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)
        return instrument

    def resolved_before_correction(self, *, issuance):
        return self.cancel_before_correction(issuance=issuance)

    def assert_cancelled_correction(self, *, issuance):
        instrument = self.resolved_before_correction(issuance=issuance)
        retained_status = instrument.status
        original_lines = list(self.adjustment.lines.values("pk", "debit", "credit"))
        self.client.force_login(self.preparer)
        page = self.client.get(reverse("vouchers:case_detail", args=[self.case.public_id]))
        self.assertContains(page, "Correct posted deductions")
        response = self.client.post(reverse("vouchers:case_action", args=[self.case.public_id, "correct-deductions"]),
            {"state_version": self.case.state_version, "idempotency_key": "correct-cancelled-http",
                "correction_date": timezone.localdate().isoformat(), "reason": "Correct deductions after cancellation"})
        self.assertEqual(response.status_code, 302)
        correction = next(r for r in self.case.posting_requests.filter(kind=Rule.REVERSAL) if r.payload.get("deduction_correction"))
        self.post_request(correction)
        self.case.refresh_from_db(); instrument.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)
        self.assertEqual(instrument.status, retained_status)
        self.assertEqual(list(self.adjustment.lines.values("pk", "debit", "credit")), original_lines)
        self.assertEqual(_capacity(self.source), Decimal("1500"))
        detail = correction.payload["deduction_correction"]
        self.assertEqual(detail.get("resolved_instruments", detail.get("cancelled_instruments"))[0]["instrument"], str(instrument.public_id))
        self.template.controlled_print_required = True
        self.template.save(update_fields=("controlled_print_required",))
        prepare_voucher(case=self.case, actor=self.preparer, voucher_date=timezone.localdate(), gross_amount=1000,
            deductions=[{"code": "ewt", "description": "Corrected deduction", "amount": Decimal("50")}],
            line_description="Corrected invoice evidence", line_account_code=self.expense_account.code,
            document_codes=["invoice"], expected_version=self.case.state_version, idempotency_key="corrected-prepare")
        self.case.refresh_from_db()
        from .case_exports import dv_print_preparation_queryset
        self.assertTrue(dv_print_preparation_queryset(self.preparer).filter(pk=self.case.pk).exists())
        job = prepare_controlled_dv_print(case=self.case, actor=self.preparer, replacement_reason="",
            expected_version=self.case.state_version, idempotency_key="corrected-signing-copy")
        self.assertTrue(job.output.file.name)
        self.case.refresh_from_db()
        record_dv_printed(case=self.case, actor=self.preparer, copy_count=1,
            printer_or_form_stock="Synthetic printer", print_note="Synthetic copy inspection",
            expected_version=self.case.state_version, idempotency_key="corrected-printed")
        self.case.refresh_from_db()
        from tracepoint.models import TrackedPacket
        assemble_finance_packet(case=self.case, actor=self.preparer, expected_document_count=2,
            expected_page_count=4, confidentiality=TrackedPacket.RESTRICTED, assembly_note="Synthetic corrected packet",
            expected_version=self.case.state_version, idempotency_key="corrected-packet")
        self.return_signatures(self.case)
        validate_accounting(case=self.case, actor=self.validator, jev_number="CANCEL-CORRECTED", jev_date=timezone.localdate(),
            note="Independent review after cancellation", prior_payable_line_id=self.source.pk,
            expected_version=self.case.state_version, idempotency_key="corrected-validate")
        self.post_request(self.case.posting_requests.get(kind=Rule.ADJUSTMENT, version=2))
        self.case.refresh_from_db()
        self.assertFalse(CheckIssueForm(case=self.case).fields["replaces"].queryset.filter(pk=instrument.pk).exists())
        with self.assertRaisesMessage(ValidationError, "belongs to a corrected DV"):
            issue_check(case=self.case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
                check_number="INVALID-OLD-REPLACEMENT", amount=900, replaces=instrument,
                expected_version=self.case.state_version, idempotency_key="invalid-old-replacement")
        fresh = issue_check(case=self.case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="CORRECTED-NEW-CHECK", amount=950,
            expected_version=self.case.state_version, idempotency_key="corrected-new-check")
        if issuance:
            self.post_request(self.case.posting_requests.get(kind=Rule.PAYMENT, trigger_key=f"payment-instrument:{fresh.public_id}:issued"))
        self.case.refresh_from_db()
        submit_checks_for_advice(case=self.case, actor=self.treasury_user,
            expected_version=self.case.state_version, idempotency_key="corrected-advice")
        self.case.refresh_from_db()
        batch = finalize_bank_advice(case=self.case, actor=self.preparer, advice_number="CORRECTED-ADVICE",
            advice_date=timezone.localdate(), expected_version=self.case.state_version, idempotency_key="corrected-finalize",
            preparation_note="Synthetic review", authority_reference="Synthetic reviewed procedure", local_applicability_note="Synthetic")
        self.acknowledge_advice(batch)
        self.case.refresh_from_db(); fresh.refresh_from_db()
        release_check(case=self.case, instrument=fresh, actor=self.treasury_user, claimant=self.claimant,
            receipt_reference="CORRECTED-RECEIPT", expected_version=self.case.state_version, idempotency_key="corrected-release")
        if not issuance:
            self.post_request(self.case.posting_requests.get(kind=Rule.PAYMENT, trigger_key=f"payment-instrument:{fresh.public_id}:released"))
        self.case.refresh_from_db(); instrument.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual(instrument.status, retained_status)
        self.assertEqual(_capacity(self.source), Decimal("500"))
        self.client.force_login(self.validator)
        exported = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertEqual(exported.status_code, 200)
        self.assertIn(b"1500.00,1000.00,500.00", exported.content)

    def test_correction_cannot_predate_cancellation(self):
        self.cancel_before_correction()
        with self.assertRaisesMessage(ValidationError, "predate"):
            self.request(correction_date=date(2026, 8, 26))

    def test_changed_cancellation_evidence_blocks_materialization(self):
        from .posting import materialize_voucher_journal
        instrument = self.cancel_before_correction()
        self.request(correction_date=timezone.localdate())
        correction = self.case.posting_requests.get(kind=Rule.REVERSAL)
        PaymentInstrument.objects.filter(pk=instrument.pk).update(cancellation_reason="Changed after proposal")
        with self.assertRaisesMessage(ValidationError, "differ from the retained correction"):
            materialize_voucher_journal(correction, self.preparer)

    def test_cancelled_release_time_check_allows_deduction_correction(self):
        self.assert_cancelled_correction(issuance=False)

    def test_posted_issuance_and_exact_cancellation_allow_deduction_correction(self):
        self.assert_cancelled_correction(issuance=True)
