from datetime import date
from decimal import Decimal
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import JournalEntry, PayableClaimReservation
from accounting.payables import claim_rows, _capacity
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule, FinanceParty, FinanceNumberingSequence
from . import test_prior_payables as fixtures, test_earlier_accruals as earlier
from .deduction_corrections import request_correction, withdraw_correction
from .models import VoucherCase, VoucherPostingRequest
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .services import prepare_voucher, validate_accounting, issue_check
from .remittances import withholding_availability, create_batch, add_line


class DeductionCorrectionTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.PriorPayableDVTests.setUpTestData.__func__)
    employee = classmethod(fixtures.PriorPayableDVTests.employee.__func__)
    create_case = fixtures.PriorPayableDVTests.create_case
    budget_certify = fixtures.PriorPayableDVTests.budget_certify
    return_signatures = earlier.EarlierAccrualTests.return_signatures
    acknowledge_advice = fixtures.PriorPayableDVTests.acknowledge_advice
    enable_payment_event_rules = fixtures.PriorPayableDVTests.enable_payment_event_rules
    enable_remittance_route = fixtures.fixtures.VoucherWorkflowTests.enable_remittance_route
    case_for_validation = fixtures.PriorPayableDVTests.case_for_validation
    validate = fixtures.PriorPayableDVTests.validate
    post_request = fixtures.PriorPayableDVTests.post_request
    pay = fixtures.PriorPayableDVTests.pay

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix="grand-deduction-correction-")
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
        self.case = self.case_for_validation(deductions=True)
        self.validate(self.case)
        self.original_request = self.case.posting_requests.get(kind=Rule.ADJUSTMENT)
        self.adjustment = self.post_request(self.original_request)
        self.case.refresh_from_db()

    def request(self, **changes):
        self.case.refresh_from_db()
        args = dict(case=self.case, actor=self.preparer, correction_date=date(2026, 8, 26),
            reason="Correct the reviewed deduction amount", expected_version=self.case.state_version, idempotency_key="correct-deductions")
        args.update(changes)
        return request_correction(**args)

    def availability(self):
        return withholding_availability(finance_department_id=self.accounting.pk,
            transaction_type=self.transaction_variant.code, as_of_date=date(2026, 8, 31), include_nonpositive=True)

    def remittance(self):
        self.treasury_user.user_permissions.add(Permission.objects.get(content_type__app_label="vouchers", codename="prepare_remittances"))
        agency = FinanceParty.objects.create(department=self.accounting, release=self.release, code="correction-agency", version=1,
            display_name="Synthetic Revenue Agency", party_type=FinanceParty.AGENCY, effective_from=date(2026, 1, 1), status="active", created_by=self.preparer)
        FinanceNumberingSequence.objects.create(department=self.accounting, release=self.release, fiscal_year=2026,
            document_type="deduction-remittance", prefix="COR-REM-", padding=5, next_number=1, status="active", created_by=self.preparer)
        return create_batch(actor=self.treasury_user, configuration_release=self.release, transaction_variant=self.transaction_variant,
            recipient_party=agency, fund_code="general-fund", bank_account_code="gf-lbp", remittance_date=date(2026, 8, 31),
            payment_method="Electronic transfer", authority_reference="Synthetic reviewed remittance", evidence_reference="Synthetic retained schedule")

    def test_exact_reversal_reopens_dv_then_corrected_deduction_and_payment_reconcile(self):
        original_rows = list(self.adjustment.lines.values("account_id", "debit", "credit"))
        self.request()
        self.request()
        correction = self.case.posting_requests.get(kind=Rule.REVERSAL)
        self.assertEqual(self.availability()[0]["available"], Decimal("0"))
        self.case.refresh_from_db()
        with self.assertRaises((ValidationError, PermissionDenied)):
            issue_check(case=self.case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="MUST-NOT-ISSUE",
                amount=900, expected_version=self.case.state_version, idempotency_key="blocked-issue")
        entry = self.post_request(correction)
        self.assertEqual(entry.reversal_of_id, self.adjustment.pk)
        self.assertEqual(list(self.adjustment.lines.values("account_id", "debit", "credit")), original_rows)
        self.case.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)
        self.assertTrue(PayableClaimReservation.objects.get().released_at)
        self.assertEqual(_capacity(self.source), Decimal("1500"))
        self.assertEqual(self.availability()[0]["ledger_balance"], Decimal("0"))
        prepare_voucher(case=self.case, actor=self.preparer, voucher_date=date(2026, 8, 27), gross_amount=Decimal("1000"),
            deductions=[{"code": "ewt", "description": "Corrected deduction", "amount": Decimal("50")}],
            line_description="Corrected invoice evidence", line_account_code=self.expense_account.code, document_codes=["invoice"],
            expected_version=self.case.state_version, idempotency_key="corrected-prepare")
        self.return_signatures(self.case)
        validate_accounting(case=self.case, actor=self.validator, jev_number="CORRECTED-DEDUCTIONS", jev_date=date(2026, 8, 27),
            note="Independent corrected deduction review", prior_payable_line_id=self.source.pk,
            expected_version=self.case.state_version, idempotency_key="corrected-validate")
        self.post_request(self.case.posting_requests.get(kind=Rule.ADJUSTMENT, version=2))
        self.pay(self.case)
        self.assertEqual(claim_rows(self.accounting.pk, date(2026, 9, 30))[0]["outstanding"], Decimal("500"))
        self.assertEqual(self.availability()[0]["ledger_balance"], Decimal("50"))
        self.client.force_login(self.validator)
        exported = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": "2026-09-30"})
        self.assertEqual(exported.status_code, 200)
        self.assertIn(b"1500.00,1000.00,500.00", exported.content)

    def test_remittance_and_correction_cannot_reserve_the_same_withholding(self):
        batch = self.remittance()
        choice = self.availability()[0]["choice_key"]
        line = add_line(batch=batch, actor=self.treasury_user, choice_key=choice, amount=100, reason="Retained remittance schedule")
        with self.assertRaisesMessage(ValidationError, "already remitted, reserved or corrected"):
            self.request()
        self.assertFalse(self.case.posting_requests.filter(kind=Rule.REVERSAL).exists())
        from .remittances import revise_line
        revise_line(line=line, actor=self.treasury_user, amount=0, reason="Return unused balance for deduction correction")
        self.request()
        with self.assertRaises(ValidationError):
            add_line(batch=batch, actor=self.treasury_user, choice_key=choice, amount=100, reason="Must not consume correction hold")

    def test_http_scope_and_immutable_native_recovery(self):
        self.client.force_login(self.preparer)
        page = self.client.get(reverse("vouchers:case_detail", args=[self.case.public_id]))
        self.assertContains(page, "Correct posted deductions")
        url = reverse("vouchers:case_action", args=[self.case.public_id, "correct-deductions"])
        data = {"state_version": self.case.state_version, "idempotency_key": "http-correction", "correction_date": "2026-08-26", "reason": "Correct retained invoice deduction"}
        group, _ = Group.objects.get_or_create(name="Finance UAT Viewer")
        self.preparer.groups.add(group)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.preparer.groups.remove(group)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        correction = self.case.posting_requests.get(kind=Rule.REVERSAL)
        update = QuerySet.update
        def interrupted(qs, **values):
            if qs.model is VoucherPostingRequest and values.get("status") == VoucherPostingRequest.MATERIALIZED:
                raise RuntimeError("Interrupted default correction link")
            return update(qs, **values)
        with patch.object(QuerySet, "update", interrupted), self.assertRaises(RuntimeError):
            materialize_voucher_journal(correction, self.preparer)
        entry, created = materialize_voucher_journal(correction, self.preparer)
        self.assertFalse(created)
        submit_entry(entry, self.preparer)
        post_entry(entry, self.validator)
        with patch("vouchers.services._apply_case_return", side_effect=RuntimeError("Interrupted corrected DV return")), self.assertRaises(RuntimeError):
            reconcile_posted_voucher_entry(entry, self.validator)
        self.assertTrue(PayableClaimReservation.objects.get().released_at)
        reconcile_posted_voucher_entry(entry, self.validator)
        self.case.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)

    def test_correction_date_authority_and_issued_instrument_guards(self):
        for invalid in (None, date(2026, 8, 24), date(2099, 1, 1)):
            with self.subTest(date=invalid), self.assertRaises(ValidationError):
                self.request(correction_date=invalid)
        with self.assertRaises(PermissionDenied):
            self.request(actor=self.treasury_user)
        issue_check(case=self.case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="ALREADY-ISSUED",
            amount=900, expected_version=self.case.state_version, idempotency_key="actual-issue")
        with self.assertRaisesMessage(ValidationError, "payment instrument already exists"):
            self.request()

    def test_repeated_correction_retains_signed_governed_tax_output(self):
        from reporting.datasets import _governed_tax_payload
        self.request()
        self.post_request(self.case.posting_requests.get(kind=Rule.REVERSAL))
        self.case.refresh_from_db()
        prepare_voucher(case=self.case, actor=self.preparer, voucher_date=date(2026, 8, 27), gross_amount=Decimal("1000"),
            deductions=[{"code": "ewt", "description": "Governed tax after correction", "amount": Decimal("10"),
                "tax_rule_item": self.tax_rule_item, "tax_base": Decimal("1000")}],
            line_description="Reviewed taxable supply", line_account_code=self.expense_account.code, document_codes=["invoice"],
            expected_version=self.case.state_version, idempotency_key="tax-corrected-prepare")
        self.return_signatures(self.case)
        validate_accounting(case=self.case, actor=self.validator, jev_number="GOVERNED-CORRECTED-TAX", jev_date=date(2026, 8, 27),
            note="Reviewed tax base and rule", prior_payable_line_id=self.source.pk,
            expected_version=self.case.state_version, idempotency_key="tax-corrected-validate")
        self.post_request(self.case.posting_requests.get(kind=Rule.ADJUSTMENT, version=2))
        self.assertEqual(len(self.availability()), 1)  # Descriptions do not split one deduction identity.
        self.assertEqual(self.availability()[0]["available"], Decimal("10"))
        before = _governed_tax_payload(self.accounting, date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(before.control_totals["reported_tax_withheld"], Decimal("10"))

        self.request(correction_date=date(2026, 8, 28), idempotency_key="second-correction")
        self.post_request(self.case.posting_requests.get(kind=Rule.REVERSAL, version=2))
        after = _governed_tax_payload(self.accounting, date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(after.control_totals["reported_tax_withheld"], Decimal("0"))
        self.assertEqual(after.control_totals["ledger_difference"], Decimal("0"))
        self.assertEqual(after.control_status, "reconciled")
        self.assertEqual({row["tax_withheld"] for row in after.rows}, {Decimal("10"), Decimal("-10")})
        self.assertEqual(before.control_totals["reported_tax_withheld"], Decimal("10"))

    def test_unposted_withdrawal_and_discard_successor_preserve_original_deduction(self):
        self.request()
        self.case.refresh_from_db()
        withdraw_correction(case=self.case, actor=self.preparer, reason="Correction request made in error",
            expected_version=self.case.state_version, idempotency_key="withdraw-first")
        self.assertEqual(self.availability()[0]["available"], Decimal("100"))
        self.request(idempotency_key="request-after-withdrawal")
        request = self.case.posting_requests.get(kind=Rule.REVERSAL, version=2)
        entry, _ = materialize_voucher_journal(request, self.preparer)
        self.case.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "Discard an unposted correction draft"):
            withdraw_correction(case=self.case, actor=self.preparer, reason="Cannot abandon a retained draft",
                expected_version=self.case.state_version, idempotency_key="withdraw-draft")
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:entry_discard", args=[entry.public_id]), {"reason": "Draft no longer needed"})
        self.assertEqual(response.status_code, 302)
        successor = self.case.posting_requests.get(kind=Rule.REVERSAL, version=3)
        self.case.refresh_from_db()
        response = self.client.post(reverse("vouchers:case_action", args=[self.case.public_id, "withdraw-deduction-correction"]),
            {"reason": "Keep the original reviewed deductions", "state_version": self.case.state_version, "idempotency_key": "withdraw-successor"})
        self.assertEqual(response.status_code, 302)
        successor.refresh_from_db()
        self.assertEqual(successor.status, VoucherPostingRequest.CANCELLED)
        self.assertEqual(self.availability()[0]["available"], Decimal("100"))
        self.assertFalse(PayableClaimReservation.objects.get().released_at)
