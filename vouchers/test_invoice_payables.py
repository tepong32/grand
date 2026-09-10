from datetime import date
from decimal import Decimal
import shutil
import tempfile
import uuid
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.claim_attributions import propose, review, serial_snapshot, current, allocation_rows
from accounting.models import JournalEntry, JournalLine, PostingMapping, PayableClaimReservation, PayableClaimRetirement
from accounting.payables import _capacity, _reserve_claim, claim_rows
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule
from . import test_consolidated_payables as setup_module
from .models import ReturnedInstrumentReview, VoucherCase
from .prior_payables import current_evidence
from .services import issue_check
from .deduction_corrections import request_correction
from .posting import reconcile_posted_voucher_entry


class InvoicePayableDVTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(setup_module.ConsolidatedPayableTests.setUpTestData.__func__)
    employee = classmethod(setup_module.ConsolidatedPayableTests.employee.__func__)
    create_case = setup_module.ConsolidatedPayableTests.create_case
    budget_certify = setup_module.ConsolidatedPayableTests.budget_certify
    return_signatures = setup_module.ConsolidatedPayableTests.return_signatures
    acknowledge_advice = setup_module.ConsolidatedPayableTests.acknowledge_advice
    enable_payment_event_rules = setup_module.ConsolidatedPayableTests.enable_payment_event_rules
    case_for_validation = setup_module.ConsolidatedPayableTests.case_for_validation
    post_request = setup_module.ConsolidatedPayableTests.post_request
    pay = setup_module.ConsolidatedPayableTests.pay
    validate_group = setup_module.ConsolidatedPayableTests.validate_group
    release_issued = setup_module.ConsolidatedPayableTests.release_issued
    return_review = setup_module.ConsolidatedPayableTests.return_review

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix="grand-invoice-dv-")
        cls.override = override_settings(MEDIA_ROOT=cls.temp, GRAND_EXPORT_ROOT=cls.temp)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.temp, ignore_errors=True)

    def setUp(self):
        setup_module.ConsolidatedPayableTests.setUp(self)
        original = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="HISTORICAL-CONSOLIDATED", entry_date=date(2026, 8, 20), period=self.accounting_period,
            fund=self.accounting_fund, description="Historical consolidated invoices", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=original, sequence=1, account=self.expense_account, debit=3000)
        self.source = JournalLine.objects.create(entry=original, sequence=2, account=self.payable_account, credit=3000)
        submit_entry(original, self.preparer); post_entry(original, self.validator)
        old = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="HISTORICAL-PAYMENT", entry_date=date(2026, 8, 21), period=self.accounting_period,
            fund=self.accounting_fund, description="Historical partial payment", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username)
        self.old_payment = JournalLine.objects.create(entry=old, sequence=1, account=self.payable_account, debit=500)
        bank = PostingMapping.objects.get(department_id=self.accounting.pk, category=PostingMapping.BANK, source_code="gf-lbp").account
        JournalLine.objects.create(entry=old, sequence=2, account=bank, credit=500, cash_flow_category="op_suppliers")
        submit_entry(old, self.preparer); post_entry(old, self.validator)
        self.invoice_keys = [str(uuid.UUID(int=1)), str(uuid.UUID(int=2))]
        rows = [{"key": key, "party_key": f"finance-party:{self.party.code}", "claim_reference": f"HIST-INV-{index}",
            "recognized": recognized, "applications": {str(self.old_payment.pk): payment}}
            for index, (key, recognized, payment) in enumerate(zip(self.invoice_keys, ("1800", "1200"), ("300", "200")), 1)]
        self.proposal_url = reverse("accounting:claim_attribution", args=[self.source.pk]) + "?mode=split"
        self.proposal_data = {"expected_version": "0", "applications": [str(self.old_payment.pk)],
            "evidence_reference": "Synthetic reconciled invoice schedule", "reason": "Identify the consolidated invoices",
            "complete_history": "on", "invoices-TOTAL_FORMS": "2", "invoices-INITIAL_FORMS": "0"}
        for index, row in enumerate(rows):
            self.proposal_data.update({f"invoices-{index}-{field}": row[field]
                for field in ("key", "party_key", "claim_reference", "recognized")})
            self.proposal_data[f"invoices-{index}-share_{self.old_payment.pk}"] = row["applications"][str(self.old_payment.pk)]
        self.client.force_login(self.preparer)
        response = self.client.post(self.proposal_url, self.proposal_data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        record = self.source.claim_attributions.get()
        self.client.force_login(self.validator)
        response = self.client.post(reverse("accounting:claim_attribution_review",
            args=[self.source.pk, record.public_id, "approve"]), {"note": "Checked invoices and payment"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(current(self.source).pk, record.pk)

    def test_proposal_refresh_add_and_invalid_totals_do_not_save(self):
        self.client.force_login(self.preparer)
        data = dict(self.proposal_data, expected_version="1", action="refresh")
        response = self.client.post(self.proposal_url, data)
        self.assertContains(response, "HISTORICAL-PAYMENT")
        self.assertEqual(self.source.claim_attributions.count(), 1)
        data["action"] = "add_invoice"
        response = self.client.post(self.proposal_url, data)
        self.assertEqual(len(response.context["invoices"].forms), 3)
        self.assertEqual(response.context["invoices"].forms[0]["recognized"].value(), "1800")
        data.update(action="submit", **{"invoices-0-recognized": "1799.99"})
        response = self.client.post(self.proposal_url, data)
        self.assertContains(response, "liability credit exactly")
        self.assertEqual(self.source.claim_attributions.count(), 1)
        data["invoices-0-recognized"] = "1800"
        data[f"invoices-0-share_{self.old_payment.pk}"] = "299.99"
        response = self.client.post(self.proposal_url, data)
        self.assertContains(response, "application in full")
        data[f"invoices-0-share_{self.old_payment.pk}"] = "300"
        data["expected_version"] = "0"
        response = self.client.post(self.proposal_url, data)
        self.assertContains(response, "approved attribution changed")
        self.assertEqual(self.source.claim_attributions.count(), 1)

    def test_returned_successor_is_prefilled_and_keeps_invoice_keys(self):
        self.client.force_login(self.preparer)
        data = dict(self.proposal_data, expected_version="1")
        data["invoices-0-claim_reference"] = "CORRECTED-INV"
        self.assertEqual(self.client.post(self.proposal_url, data).status_code, 302)
        record = self.source.claim_attributions.order_by("-version").first()
        self.client.force_login(self.validator)
        self.client.post(reverse("accounting:claim_attribution_review",
            args=[self.source.pk, record.public_id, "return"]), {"note": "Check supporting invoice"})
        self.client.force_login(self.preparer)
        response = self.client.get(self.proposal_url)
        self.assertEqual(response.context["invoices"].forms[0]["claim_reference"].value(), "CORRECTED-INV")
        self.assertEqual(str(response.context["invoices"].forms[0]["key"].value()), self.invoice_keys[0])
        self.assertEqual(self.client.post(self.proposal_url, data).status_code, 302)
        successor = self.source.claim_attributions.order_by("-version").first()
        self.assertEqual(successor.version, 3)
        self.assertEqual(allocation_rows(successor)[0]["key"], self.invoice_keys[0])

    def rows(self, case):
        deduction = case.disbursement_voucher.deductions.first()
        return [{"source_id": self.source.pk, "invoice_key": key, "gross": gross,
            "deductions": {str(deduction.pk): withheld} if deduction else {}}
            for key, gross, withheld in zip(self.invoice_keys, ("600", "400"), ("40", "60"))]

    def capacities(self, **kwargs):
        return [_capacity(self.source, invoice_key=key, **kwargs) for key in self.invoice_keys]

    def test_http_two_invoices_one_credit_deductions_payment_return_and_csv(self):
        case = self.case_for_validation(deductions=True)
        before = serial_snapshot(self.source, [self.old_payment.pk])
        deduction = case.disbursement_voucher.deductions.get()
        self.client.force_login(self.validator)
        response = self.client.post(reverse("vouchers:case_action", args=[case.public_id, "validate-accounting"]), {
            "state_version": case.state_version, "idempotency_key": "http-invoices", "jev_number": "INVOICE-ADJUSTMENT",
            "jev_date": "2026-08-25", "consolidated": "on", "claims-TOTAL_FORMS": "2", "claims-INITIAL_FORMS": "0",
            "claims-0-source": f"{self.source.pk}:{self.invoice_keys[0]}", "claims-0-gross": "600",
            f"claims-0-deduction_{deduction.pk}": "40",
            "claims-1-source": f"{self.source.pk}:{self.invoice_keys[1]}", "claims-1-gross": "400",
            f"claims-1-deduction_{deduction.pk}": "60"})
        self.assertEqual(response.status_code, 302)
        evidence = current_evidence(case)
        self.assertEqual(len(evidence["claims"]), 2)
        holds = list(PayableClaimReservation.objects.filter(source=self.source).order_by("invoice_key"))
        self.assertEqual([str(item.invoice_key) for item in holds], self.invoice_keys)
        self.assertEqual(self.capacities(), [Decimal("900"), Decimal("600")])
        adjustment = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        self.assertEqual([line.payable_allocation["shares"] for line in adjustment.lines.filter(payable_origin=self.source)],
            [{self.invoice_keys[0]: "40.00"}, {self.invoice_keys[1]: "60.00"}])
        instrument, payment = self.pay(case)
        self.assertFalse(payment.lines.filter(account=self.expense_account).exists())
        self.assertEqual(self.capacities(), [Decimal("900"), Decimal("600")])
        returned = self.return_review(instrument, ReturnedInstrumentReview.REISSUE)
        reversal = self.post_request(returned.posting_request)
        self.assertEqual([line.payable_allocation for line in reversal.lines.order_by("sequence")],
            [line.payable_allocation for line in payment.lines.order_by("sequence")])
        self.pay(case, suffix="-invoice-reissue", replaces=instrument)
        balances = [row["outstanding"] for row in claim_rows(self.accounting.pk, timezone.localdate()) if row["line"].pk == self.source.pk]
        self.assertEqual(balances, [Decimal("900"), Decimal("600")])
        export = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertIn(b"1800.00,900.00,900.00", export.content)
        self.assertIn(b"1200.00,600.00,600.00", export.content)
        self.assertEqual(serial_snapshot(self.source, [self.old_payment.pk]), before)

    def test_interrupted_validation_reuses_distinct_holds_on_the_same_source(self):
        case = self.case_for_validation()
        with patch("vouchers.services._advance", side_effect=RuntimeError("Interrupted invoice handoff")):
            with self.assertRaises(RuntimeError):
                self.validate_group(case)
        original_ids = set(PayableClaimReservation.objects.filter(source=self.source).values_list("public_id", flat=True))
        self.assertEqual(len(original_ids), 2)
        self.validate_group(case)
        self.assertEqual(set(PayableClaimReservation.objects.filter(source=self.source).values_list("public_id", flat=True)), original_ids)
        self.pay(case)
        self.assertEqual(self.capacities(), [Decimal("900"), Decimal("600")])

    def test_posted_invoice_deductions_can_be_corrected_without_rewriting_allocations(self):
        case = self.case_for_validation(deductions=True)
        self.validate_group(case)
        original = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        case.refresh_from_db()
        request_correction(case=case, actor=self.preparer, correction_date=date(2026, 8, 26),
            reason="Correct invoice deduction amounts", expected_version=case.state_version, idempotency_key="invoice-correction")
        correction = self.post_request(case.posting_requests.get(kind=Rule.REVERSAL))
        self.assertEqual([line.payable_allocation for line in correction.lines.order_by("sequence")],
            [line.payable_allocation for line in original.lines.order_by("sequence")])
        self.assertEqual(self.capacities(), [Decimal("1500"), Decimal("1000")])
        self.assertEqual(PayableClaimReservation.objects.filter(source=self.source, released_at__isnull=False).count(), 2)

    def test_partial_closing_return_retires_only_its_invoice_shares_on_actual_date(self):
        case = self.case_for_validation()
        self.validate_group(case)
        keys = [row["reservation"] for row in current_evidence(case)["claims"]]
        for index in (1, 2):
            case.refresh_from_db()
            issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
                check_number=f"INVOICE-PARTIAL-{index}", amount="500", expected_version=case.state_version,
                idempotency_key=f"invoice-partial-{index}", claim_payment_amounts={keys[0]: "300", keys[1]: "200"})
        paid = self.release_issued(case, "invoices")
        closing = self.return_review(paid[0][0], ReturnedInstrumentReview.CLOSE_WITHOUT_REISSUE)
        with patch("vouchers.cash_positions.resolve_instrument_exception", side_effect=RuntimeError("Interrupted close")):
            with self.assertRaises(RuntimeError):
                self.post_request(closing.posting_request)
        reversal = JournalEntry.objects.get(source_reference=str(closing.posting_request.public_id))
        reconcile_posted_voucher_entry(reversal, self.validator)
        self.assertEqual(PayableClaimRetirement.objects.count(), 2)
        self.assertEqual(self.capacities(), [Decimal("1200"), Decimal("800")])
        self.assertEqual(self.capacities(as_of=date(2026, 8, 25)), [Decimal("900"), Decimal("600")])
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            _reserve_claim(source_id=self.source.pk, invoice_key=self.invoice_keys[0], case_public_id=uuid.uuid4(),
                key="too-early-invoice", amount="1000", actor_id=self.validator.pk, department_id=self.accounting.pk,
                fund_code=self.accounting_fund.code, party_key=f"finance-party:{self.party.code}", as_of=date(2026, 8, 25))

    def test_group_rolls_back_first_invoice_when_second_is_already_reserved(self):
        existing = _reserve_claim(source_id=self.source.pk, invoice_key=self.invoice_keys[1],
            case_public_id=uuid.uuid4(), key="other-invoice-hold", amount="200", actor_id=self.validator.pk,
            department_id=self.accounting.pk, fund_code=self.accounting_fund.code,
            party_key=f"finance-party:{self.party.code}", as_of=date(2026, 8, 25))
        case = self.case_for_validation()
        rows = self.rows(case)
        rows[0]["gross"], rows[1]["gross"] = "100", "900"
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            self.validate_group(case, rows)
        self.assertEqual(list(PayableClaimReservation.objects.filter(source=self.source).values_list("pk", flat=True)), [existing.pk])
        rows[0]["gross"], rows[1]["gross"] = "200", "800"
        self.validate_group(case, rows)
        self.pay(case)
        self.assertEqual(self.capacities(), [Decimal("1300"), Decimal("0")])
