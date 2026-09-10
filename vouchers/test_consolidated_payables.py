from datetime import date
from decimal import Decimal
import shutil
import tempfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine, PayableClaimReservation, PayableClaimReservationGroup, PayableClaimRetirement
from accounting.payables import _capacity, claim_rows
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule
from . import test_prior_payables as fixtures
from .models import PaymentInstrumentException, ReturnedInstrumentReview, VoucherCase, TreasuryCashPolicy
from .prior_payables import current_evidence
from .services import validate_accounting, issue_check, cancel_check, submit_checks_for_advice, finalize_bank_advice, release_check
from .cash_positions import open_instrument_exception
from .advice import decide_returned_instrument
from .deduction_corrections import request_correction
from .posting import reconcile_posted_voucher_entry


class ConsolidatedPayableTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.PriorPayableDVTests.setUpTestData.__func__)
    employee = classmethod(fixtures.PriorPayableDVTests.employee.__func__)
    create_case = fixtures.PriorPayableDVTests.create_case
    budget_certify = fixtures.PriorPayableDVTests.budget_certify
    return_signatures = fixtures.PriorPayableDVTests.return_signatures
    acknowledge_advice = fixtures.PriorPayableDVTests.acknowledge_advice
    enable_payment_event_rules = fixtures.PriorPayableDVTests.enable_payment_event_rules
    case_for_validation = fixtures.PriorPayableDVTests.case_for_validation
    post_request = fixtures.PriorPayableDVTests.post_request
    pay = fixtures.PriorPayableDVTests.pay

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix="grand-consolidated-")
        cls.override = override_settings(MEDIA_ROOT=cls.temp, GRAND_EXPORT_ROOT=cls.temp)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.temp, ignore_errors=True)

    def setUp(self):
        fixtures.PriorPayableDVTests.setUp(self)
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code="gf-lbp", fund_code="general-fund", mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=0, position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=date(2026, 1, 1), authority_reference="Synthetic reviewed policy", local_applicability_note="Synthetic",
            status=TreasuryCashPolicy.ACTIVE, created_by=self.treasury_user, submitted_by=self.treasury_user,
            submitted_at=timezone.now(), approved_by=self.validator, approved_at=timezone.now())
        entry = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="SECOND-ACCRUAL", entry_date=date(2026, 8, 20), period=self.accounting_period,
            fund=self.accounting_fund, description="Second synthetic invoice", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=entry, sequence=1, account=self.expense_account, debit=1500)
        self.second = JournalLine.objects.create(entry=entry, sequence=2, account=self.payable_account, credit=1500,
            payable_party_key=f"finance-party:{self.party.code}", payable_claim_reference="PRIOR-INVOICE-2")
        submit_entry(entry, self.preparer)
        post_entry(entry, self.validator)

    def rows(self, case):
        deduction = case.disbursement_voucher.deductions.first()
        return [{"source_id": self.source.pk, "gross": "600.00", "deductions": {str(deduction.pk): "40.00"} if deduction else {}},
            {"source_id": self.second.pk, "gross": "400.00", "deductions": {str(deduction.pk): "60.00"} if deduction else {}}]

    def validate_group(self, case, rows=None):
        case.refresh_from_db()
        return validate_accounting(case=case, actor=self.validator,
            jev_number="CONSOLIDATED-ADJUSTMENT" if case.disbursement_voucher.total_deductions else "",
            jev_date=date(2026, 8, 25), note="Invoice schedule independently checked",
            expected_version=case.state_version, idempotency_key="validate-group",
            prior_payable_allocations=rows or self.rows(case))

    def test_http_deductions_payment_claim_export_and_exact_return(self):
        case = self.case_for_validation(deductions=True)
        self.client.force_login(self.validator)
        deduction = case.disbursement_voucher.deductions.get()
        data = {"state_version": case.state_version, "idempotency_key": "http-group", "jev_number": "CONSOLIDATED-ADJUSTMENT",
            "jev_date": "2026-08-25", "consolidated": "on", "claims-TOTAL_FORMS": "2", "claims-INITIAL_FORMS": "0",
            "claims-0-source": self.source.pk, "claims-0-gross": "600", f"claims-0-deduction_{deduction.pk}": "40",
            "claims-1-source": self.second.pk, "claims-1-gross": "400", f"claims-1-deduction_{deduction.pk}": "60"}
        response = self.client.post(reverse("vouchers:case_action", args=[case.public_id, "validate-accounting"]), data)
        self.assertEqual(response.status_code, 302)
        evidence = current_evidence(case)
        self.assertEqual(evidence["schema"], 2)
        adjustment = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        self.assertEqual(list(adjustment.lines.filter(payable_origin__isnull=False).order_by("payable_origin_id").values_list("debit", flat=True)), [Decimal("40"), Decimal("60")])
        self.assertEqual(adjustment.lines.get(account=self.withholding_account).credit, Decimal("100"))
        page = self.client.get(reverse("vouchers:case_detail", args=[case.public_id]))
        self.assertContains(page, "SECOND-ACCRUAL")
        instrument, payment = self.pay(case)
        self.assertEqual(list(payment.lines.filter(payable_origin__isnull=False).order_by("payable_origin_id").values_list("debit", flat=True)), [Decimal("560"), Decimal("340")])
        self.assertFalse(payment.lines.filter(account=self.expense_account).exists())
        balances = {r["line"].pk: r["outstanding"] for r in claim_rows(self.accounting.pk, timezone.localdate())}
        self.assertEqual((balances[self.source.pk], balances[self.second.pk]), (Decimal("900"), Decimal("1100")))
        export = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertIn(b"1500.00,600.00,900.00", export.content)
        self.assertIn(b"1500.00,400.00,1100.00", export.content)
        instrument.refresh_from_db()
        exception = open_instrument_exception(instrument=instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(), reason="Unpaid bank return",
            evidence_reference="Synthetic bank evidence")
        review = exception.accounting_reviews.get()
        decide_returned_instrument(review=review, actor=self.validator, approve=True, outcome=ReturnedInstrumentReview.REISSUE,
            decision_reason="Reissue against the same invoice shares", evidence_reference="Synthetic review",
            expected_version=review.state_version)
        review.refresh_from_db()
        reversal = self.post_request(review.posting_request)
        self.assertEqual(reversal.reversal_of_id, payment.pk)
        self.assertEqual(list(reversal.lines.order_by("sequence").values_list("debit", "credit")),
            [(line.credit, line.debit) for line in payment.lines.order_by("sequence")])
        replacement, second_payment = self.pay(case, suffix="-replacement", replaces=instrument)
        self.assertEqual(replacement.prior_payable_allocation, instrument.prior_payable_allocation)
        self.assertEqual(second_payment.source_snapshot["prior_payable"], evidence)

    def test_atomic_group_and_interrupted_default_handoff(self):
        case = self.case_for_validation()
        # A later member fails after the first hold was created: neither survives.
        from accounting.payables import _reserve_claim
        def reserve_first(**kwargs):
            if kwargs["source_id"] == self.second.pk:
                raise ValidationError("Second claim failed")
            return _reserve_claim(**kwargs)
        with patch("accounting.claim_groups._reserve_claim", side_effect=reserve_first):
            with self.assertRaisesMessage(ValidationError, "Second claim failed"):
                self.validate_group(case)
        self.assertFalse(PayableClaimReservationGroup.objects.exists())
        self.assertFalse(PayableClaimReservation.objects.exists())
        with patch("vouchers.services._advance", side_effect=RuntimeError("Default handoff interrupted")):
            with self.assertRaises(RuntimeError):
                self.validate_group(case)
        self.assertEqual(PayableClaimReservation.objects.count(), 2)
        changed = self.rows(case)
        changed[0]["gross"], changed[1]["gross"] = "500.00", "500.00"
        with self.assertRaisesMessage(ValidationError, "different claim allocations"):
            self.validate_group(case, changed)
        self.validate_group(case)
        self.assertEqual(PayableClaimReservation.objects.count(), 2)
        self.assertEqual((_capacity(self.source), _capacity(self.second)), (Decimal("900"), Decimal("1100")))

    def test_partial_checks_require_allocations_and_replacement_retains_them(self):
        case = self.case_for_validation()
        self.validate_group(case)
        evidence = current_evidence(case)
        keys = [r["reservation"] for r in evidence["claims"]]
        def issue(number, amount, shares=None, replaces=None):
            case.refresh_from_db()
            return issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
                check_number=number, amount=amount, expected_version=case.state_version, idempotency_key=number,
                claim_payment_amounts=shares, replaces=replaces)
        with self.assertRaisesMessage(ValidationError, "partial check"):
            issue("MISSING-SHARES", "300")
        first = issue("SPLIT-FIRST", "300", {keys[0]: "200", keys[1]: "100"})
        with self.assertRaisesMessage(ValidationError, "already allocated"):
            issue("OVER-CLAIM", "500", {keys[0]: "500", keys[1]: "0"})
        case.refresh_from_db()
        cancel_check(case=case, instrument=first, actor=self.treasury_user, reason="Spoiled check",
            expected_version=case.state_version, idempotency_key="cancel-first")
        first.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "original check amount"):
            issue("BAD-REPLACEMENT", "300", {keys[0]: "100", keys[1]: "200"}, first)
        replacement = issue("SPLIT-REPLACEMENT", "300", replaces=first)
        self.assertEqual(replacement.prior_payable_allocation, first.prior_payable_allocation)
        remainder = issue("SPLIT-REMAINDER", "700")
        self.assertEqual(remainder.prior_payable_allocation["amounts"], {keys[0]: "400.00", keys[1]: "300.00"})
        remainder.prior_payable_allocation = {}
        with self.assertRaisesMessage(ValidationError, "immutable"):
            remainder.save()

    def test_posted_deduction_correction_retires_entire_group(self):
        case = self.case_for_validation(deductions=True)
        self.validate_group(case)
        original = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        case.refresh_from_db()
        request_correction(case=case, actor=self.preparer, correction_date=date(2026, 8, 26),
            reason="Correct invoice deduction shares", expected_version=case.state_version, idempotency_key="correct-group")
        request = case.posting_requests.get(kind=Rule.REVERSAL)
        correction = self.post_request(request)
        self.assertEqual(correction.reversal_of_id, original.pk)
        self.assertEqual(PayableClaimReservation.objects.filter(released_at__isnull=False).count(), 2)
        self.assertEqual((_capacity(self.source), _capacity(self.second)), (Decimal("1500"), Decimal("1500")))
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)

    def test_http_invalid_deduction_keeps_entered_schedule(self):
        case = self.case_for_validation(deductions=True)
        self.client.force_login(self.validator)
        deduction = case.disbursement_voucher.deductions.get()
        response = self.client.post(reverse("vouchers:case_action", args=[case.public_id, "validate-accounting"]), {
            "state_version": case.state_version, "idempotency_key": "bad-table", "jev_number": "BAD",
            "jev_date": "2026-08-25", "consolidated": "on", "claims-TOTAL_FORMS": "2", "claims-INITIAL_FORMS": "0",
            "claims-0-source": self.source.pk, "claims-0-gross": "600", f"claims-0-deduction_{deduction.pk}": "10",
            "claims-1-source": self.second.pk, "claims-1-gross": "400", f"claims-1-deduction_{deduction.pk}": "10"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Allocate every DV deduction exactly")
        self.assertContains(response, 'value="600"')
        self.assertFalse(PayableClaimReservation.objects.exists())

    def release_issued(self, case, suffix):
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user, expected_version=case.state_version, idempotency_key="advice-"+suffix)
        case.refresh_from_db()
        batch = finalize_bank_advice(case=case, actor=self.preparer, advice_number="GROUP-ADVICE-"+suffix,
            advice_date=timezone.localdate(), expected_version=case.state_version, idempotency_key="finalize-"+suffix,
            preparation_note="Synthetic review", authority_reference="Synthetic authority", local_applicability_note="Synthetic acceptance")
        self.acknowledge_advice(batch)
        results = []
        for instrument in case.payment_instruments.filter(status="advised"):
            case.refresh_from_db()
            release_check(case=case, instrument=instrument, actor=self.treasury_user, claimant=self.claimant,
                receipt_reference="GROUP-RECEIPT-"+instrument.check_number, expected_version=case.state_version,
                idempotency_key="release-"+instrument.check_number)
            request = case.posting_requests.get(kind=Rule.PAYMENT, trigger_key=f"payment-instrument:{instrument.public_id}:released")
            results.append((instrument, self.post_request(request)))
        return results

    def return_review(self, instrument, outcome):
        instrument.refresh_from_db()
        exception = open_instrument_exception(instrument=instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(), reason="Bank returned unpaid",
            evidence_reference="Synthetic returned-check evidence")
        review = exception.accounting_reviews.get()
        decide_returned_instrument(review=review, actor=self.validator, approve=True, outcome=outcome,
            decision_reason="Independent returned-payment decision", evidence_reference="Synthetic decision",
            expected_version=review.state_version)
        review.refresh_from_db()
        return review

    def test_partial_closing_return_frees_only_its_shares_and_other_check_can_be_reissued(self):
        case = self.case_for_validation()
        self.validate_group(case)
        evidence = current_evidence(case)
        keys = [row["reservation"] for row in evidence["claims"]]
        for index in (1, 2):
            case.refresh_from_db()
            issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
                check_number=f"TWO-CHECKS-{index}", amount="500", expected_version=case.state_version,
                idempotency_key=f"two-{index}", claim_payment_amounts={keys[0]: "300", keys[1]: "200"})
        paid = self.release_issued(case, "original")
        closing = self.return_review(paid[0][0], ReturnedInstrumentReview.CLOSE_WITHOUT_REISSUE)
        with patch("vouchers.cash_positions.resolve_instrument_exception", side_effect=RuntimeError("Interrupted close")):
            with self.assertRaises(RuntimeError):
                self.post_request(closing.posting_request)
        self.assertEqual(PayableClaimRetirement.objects.count(), 2)
        reversal = JournalEntry.objects.get(source_reference=str(closing.posting_request.public_id))
        reconcile_posted_voucher_entry(reversal, self.validator)
        self.assertEqual(PayableClaimRetirement.objects.count(), 2)
        self.assertEqual((_capacity(self.source), _capacity(self.second)), (Decimal("1200"), Decimal("1300")))

        # A future closing return cannot finance an earlier reservation.
        self.assertEqual((_capacity(self.source, as_of=date(2026, 8, 25)), _capacity(self.second, as_of=date(2026, 8, 25))),
            (Decimal("900"), Decimal("1100")))
        second = paid[1][0]
        review = self.return_review(second, ReturnedInstrumentReview.REISSUE)
        self.post_request(review.posting_request)
        second.refresh_from_db(); case.refresh_from_db()
        replacement = issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="REISSUE-ONLY-SECOND", amount="500", replaces=second, expected_version=case.state_version,
            idempotency_key="reissue-second")
        self.assertEqual(replacement.prior_payable_allocation, second.prior_payable_allocation)
        self.release_issued(case, "replacement")
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual((_capacity(self.source), _capacity(self.second)), (Decimal("1200"), Decimal("1300")))

    def test_replacement_advice_counts_the_other_already_paid_check(self):
        case = self.case_for_validation()
        self.validate_group(case)
        keys = [row["reservation"] for row in current_evidence(case)["claims"]]
        for index in (1, 2):
            case.refresh_from_db()
            issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
                check_number=f"PAID-PAIR-{index}", amount="500", expected_version=case.state_version,
                idempotency_key=f"paid-{index}", claim_payment_amounts={keys[0]: "300", keys[1]: "200"})
        paid = self.release_issued(case, "paid-pair")
        original = paid[0][0]
        review = self.return_review(original, ReturnedInstrumentReview.REISSUE)
        self.post_request(review.posting_request)
        original.refresh_from_db(); case.refresh_from_db()
        issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="PAID-PAIR-REPLACEMENT", amount="500", replaces=original, expected_version=case.state_version,
            idempotency_key="paid-pair-replacement")
        self.release_issued(case, "paid-pair-replacement")
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual((_capacity(self.source), _capacity(self.second)), (Decimal("900"), Decimal("1100")))
