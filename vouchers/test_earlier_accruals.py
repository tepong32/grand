"""Real Budget/intake review through an earlier named claim and later DV payment."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import Group
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
import tempfile
import shutil
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.payables import claim_rows
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from finance.work_tasks import finance_work_tasks
from . import tests as fixtures
from . import test_prior_payables as prior_fixtures
from .forms import AccountingValidationForm
from .models import PayableIntake, VoucherCase, VoucherPostingRequest
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .return_routes import return_route_options
from .services import review_payable_intake, prepare_voucher, return_case, submit_payable_intake, record_signature_return


class EarlierAccrualTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.VoucherWorkflowTests.setUpTestData.__func__)
    employee = classmethod(fixtures.VoucherWorkflowTests.employee.__func__)
    authoritative_payable_for_review = fixtures.VoucherWorkflowTests.authoritative_payable_for_review
    enable_payment_event_rules = fixtures.VoucherWorkflowTests.enable_payment_event_rules
    acknowledge_advice = fixtures.VoucherWorkflowTests.acknowledge_advice
    post_request = prior_fixtures.PriorPayableDVTests.post_request
    pay = prior_fixtures.PriorPayableDVTests.pay
    validate = prior_fixtures.PriorPayableDVTests.validate
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix="grand-earlier-")
        cls.override = override_settings(MEDIA_ROOT=cls.temp, GRAND_EXPORT_ROOT=cls.temp)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.temp, ignore_errors=True)

    def setUp(self):
        self.case, self.payment_rule, self.obligation, _ = self.authoritative_payable_for_review()
        self.rule = self.transaction_variant.posting_rules.get(event_kind=Rule.RECOGNITION)
        # Synthetic reviewed setup, established before any immutable transaction snapshot.
        Rule.objects.filter(pk=self.rule.pk).update(recognition_point=Rule.BILLING_VALIDATION)
        self.rule.lines.all().delete()
        Line.objects.bulk_create([
            Line(rule=self.rule, sequence=1, label="Accepted cost", side=Line.DEBIT,
                account_source=Line.ALLOCATION_ACCOUNTS, amount_source=Line.EACH_ALLOCATION),
            Line(rule=self.rule, sequence=2, label="Original claim", side=Line.CREDIT,
                account_source=Line.PAYABLE_MAPPING, amount_source=Line.GROSS)])

    def review(self, **changes):
        self.case.refresh_from_db()
        kwargs = dict(case=self.case, actor=self.validator, decision=PayableIntake.READY,
            reason="Independently checked invoice and acceptance", recognition_decision=PayableIntake.ACCRUE_BEFORE_SETTLEMENT,
            recognition_basis="Synthetic reviewed billing recognition policy", recognition_date=date(2026, 8, 22),
            recognition_reference="Accepted invoice review dated 2026-08-22", expected_version=self.case.state_version,
            idempotency_key="earlier-review")
        kwargs.update(changes)
        return review_payable_intake(**kwargs)

    def prepare(self, deductions=False):
        self.case.refresh_from_db()
        prepare_voucher(case=self.case, actor=self.preparer, voucher_date=date(2026, 8, 25),
            gross_amount=Decimal("1000"), deductions=([{"code": "ewt", "description": "Withholding", "amount": Decimal("100")}] if deductions else []),
            line_description="Accepted office supplies", line_account_code=self.expense_account.code,
            document_codes=["invoice"], expected_version=self.case.state_version, idempotency_key="early-dv")
        self.return_signatures(self.case)
        self.case.refresh_from_db()

    def return_signatures(self, case):
        for task in case.signature_tasks.filter(status="pending").order_by("sequence"):
            case.refresh_from_db()
            record_signature_return(case=case, task=task, actor=self.preparer, note="Signed current correction round",
                expected_version=case.state_version, idempotency_key=f"early-signature-{task.pk}")
        case.refresh_from_db()

    def test_actual_review_to_original_claim_to_dv_payment_and_export(self):
        self.review()
        self.case.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.ACCOUNTING_POSTING)
        self.assertFalse(hasattr(self.case, "disbursement_voucher"))
        request = self.case.posting_requests.get()
        self.assertEqual(request.payload["dv_number"], "")
        self.assertEqual(request.payload["earlier_accrual"]["obligations"][0]["obligation"], str(self.obligation.public_id))
        self.review()  # Retried review does not consume another JEV number or request.
        self.assertEqual(self.case.posting_requests.count(), 1)
        with self.assertRaises(ValidationError):
            self.prepare()
        entry = self.post_request(request)
        self.source = entry.lines.get(credit__gt=0)
        self.assertEqual(self.source.payable_claim_reference, self.case.payable_intake.claim_reference)
        self.assertEqual(claim_rows(self.accounting.pk, date(2026, 8, 22))[0]["outstanding"], Decimal("1000"))
        self.assertTrue(any(t["subject"] == "Reviewed payable for earlier accrual" for t in finance_work_tasks(self.validator, view="completed")["tasks"]))
        self.prepare()
        form = AccountingValidationForm(case=self.case)
        self.assertEqual(form.fields["prior_payable_line"].initial, self.source.pk)
        self.validate(self.case)
        self.assertEqual(self.case.posting_requests.filter(kind=Rule.RECOGNITION).count(), 1)
        _, payment = self.pay(self.case)
        self.assertFalse(payment.lines.filter(account=self.expense_account).exists())
        self.assertEqual(payment.lines.get(account=self.payable_account).payable_origin_id, self.source.pk)
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("0"))
        self.client.force_login(self.validator)
        export = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"1000.00,1000.00,0.00", export.content)

    def test_review_policy_date_and_named_account_controls(self):
        for values in ({"recognition_date": None}, {"recognition_reference": ""},
                {"recognition_date": timezone.localdate() + timedelta(days=1)}, {"recognition_date": date(2025, 1, 1)}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.review(**values)
        self.assertFalse(self.case.posting_requests.exists())
        Rule.objects.filter(pk=self.rule.pk).update(recognition_point=Rule.DV_VALIDATION)
        with self.assertRaisesMessage(ValidationError, "Earlier accrual requires"):
            self.review()
        Rule.objects.filter(pk=self.rule.pk).update(recognition_point=Rule.DELIVERY_ACCEPTANCE)
        group, _ = Group.objects.get_or_create(name="Finance UAT Viewer")
        self.validator.groups.add(group)
        with self.assertRaises(PermissionDenied):
            self.review()
        self.validator.groups.remove(group)
        self.review()
        request = self.case.posting_requests.get()
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer)
        with self.assertRaises((PermissionDenied, ValidationError)):
            post_entry(entry, self.preparer)
        post_entry(entry, self.validator)
        reconcile_posted_voucher_entry(entry, self.validator)

    def test_pre_dv_return_discards_source_then_allows_reviewed_successor(self):
        self.review()
        request = self.case.posting_requests.get()
        entry, _ = materialize_voucher_journal(request, self.preparer)
        self.case.refresh_from_db()
        args = dict(case=self.case, actor=self.preparer, target_stage=VoucherCase.PAYABLE_PREPARATION,
            reason="Correct the accepted claim evidence", expected_version=self.case.state_version, idempotency_key="early-return")
        with self.assertRaisesMessage(ValidationError, "earlier-accrual JEV is retained"):
            return_case(**args)
        self.client.force_login(self.preparer)
        with patch.object(VoucherPostingRequest, "save", side_effect=RuntimeError("Interrupted discard handoff")), self.assertRaises(RuntimeError):
            self.client.post(reverse("accounting:entry_discard", args=[entry.public_id]), {"reason": "Correct source evidence"})
        request.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(request.status, VoucherPostingRequest.MATERIALIZED)
        self.assertEqual(entry.status, JournalEntry.VOIDED)
        self.assertEqual(return_route_options(self.case)[0], [(VoucherCase.PAYABLE_PREPARATION, "Requesting-office payable preparation")])
        return_case(**args)
        with self.assertRaises(ValidationError):
            materialize_voucher_journal(request, self.preparer)
        self.case.refresh_from_db()
        submit_payable_intake(case=self.case, actor=self.requesting_user, expected_version=self.case.state_version, idempotency_key="early-resubmit")
        self.review(idempotency_key="early-successor")
        successor = self.case.posting_requests.get(version=2)
        self.assertNotEqual(successor.jev_number, request.jev_number)
        self.post_request(successor)
        self.case.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "posted claim requires governed correction"):
            return_case(**{**args, "expected_version": self.case.state_version, "idempotency_key": "rewrite-posted"})

    def test_interrupted_native_handoff_recovers_one_claim_and_blocks_source_return(self):
        self.review()
        request = self.case.posting_requests.get()
        real_update = QuerySet.update
        def fail_link(qs, **kwargs):
            if qs.model is VoucherPostingRequest and kwargs.get("status") == VoucherPostingRequest.MATERIALIZED:
                raise RuntimeError("Interrupted default link")
            return real_update(qs, **kwargs)
        with patch.object(QuerySet, "update", fail_link), self.assertRaises(RuntimeError):
            materialize_voucher_journal(request, self.preparer)
        self.case.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "earlier-accrual JEV is retained"):
            return_case(case=self.case, actor=self.preparer, target_stage=VoucherCase.PAYABLE_PREPARATION,
                reason="Cannot discard a hidden native draft", expected_version=self.case.state_version, idempotency_key="hidden-return")
        entry, created = materialize_voucher_journal(request, self.preparer)
        self.assertFalse(created)
        self.assertEqual(JournalEntry.objects.filter(source_reference=str(request.public_id)).count(), 1)
        submit_entry(entry, self.preparer)
        post_entry(entry, self.validator)
        with patch("vouchers.services._advance", side_effect=RuntimeError("Interrupted posting handoff")), self.assertRaises(RuntimeError):
            reconcile_posted_voucher_entry(entry, self.validator)
        reconcile_posted_voucher_entry(entry, self.validator)
        self.case.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)

    def test_http_review_requires_actual_evidence_and_retains_it_on_case(self):
        self.client.force_login(self.validator)
        page = self.client.get(reverse("vouchers:case_detail", args=[self.case.public_id]))
        self.assertContains(page, 'name="recognition_date"')
        url = reverse("vouchers:case_action", args=[self.case.public_id, "review-payable"])
        data = dict(decision=PayableIntake.READY, reason="Reviewed source packet",
            recognition_decision=PayableIntake.ACCRUE_BEFORE_SETTLEMENT, recognition_basis="Reviewed billing policy",
            obligation_adjustment_decision=PayableIntake.NO_ADJUSTMENT, obligation_adjustment_basis="No change required",
            state_version=self.case.state_version, idempotency_key="http-early")
        self.client.post(url, data)
        self.assertFalse(self.case.posting_requests.exists())
        data.update(recognition_date="2026-08-22", recognition_reference="Invoice acceptance record HTTP-1")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.case.posting_requests.count(), 1)
        page = self.client.get(reverse("vouchers:case_detail", args=[self.case.public_id]))
        self.assertContains(page, "Invoice acceptance record HTTP-1")
        request = self.case.posting_requests.get()
        type(self.expense_account).objects.filter(pk=self.expense_account.pk).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, "active posting account"):
            materialize_voucher_journal(request, self.preparer)
        request.refresh_from_db()
        self.assertEqual(request.status, VoucherPostingRequest.FAILED)
        self.assertIn("active posting account", request.failure_reason)
        type(self.expense_account).objects.filter(pk=self.expense_account.pk).update(is_active=True)
        self.post_request(request)

    def test_deductions_and_dv_correction_keep_the_generated_original_claim(self):
        self.review()
        entry = self.post_request(self.case.posting_requests.get())
        self.source = entry.lines.get(credit__gt=0)
        self.prepare()
        with self.assertRaises(ValidationError):
            self.validate(self.case, source=entry.lines.get(debit__gt=0))
        # Returning the DV does not cancel or re-recognize its posted earlier claim.
        return_case(case=self.case, actor=self.validator, target_stage=VoucherCase.ACCOUNTING_PREPARATION,
            reason="Correct the DV before settlement", expected_version=self.case.state_version, idempotency_key="dv-correction")
        self.case.refresh_from_db()
        self.assertEqual(self.case.payable_intake.recognition_decision, PayableIntake.ACCRUE_BEFORE_SETTLEMENT)
        prepare_voucher(case=self.case, actor=self.preparer, voucher_date=date(2026, 8, 25),
            gross_amount=Decimal("1000"), deductions=[{"code": "ewt", "description": "Withholding", "amount": Decimal("100")}],
            line_description="Corrected description", line_account_code=self.expense_account.code,
            document_codes=["invoice"], expected_version=self.case.state_version, idempotency_key="corrected-dv")
        self.return_signatures(self.case)
        self.case.refresh_from_db()
        adjustment = Rule.objects.create(variant=self.transaction_variant, code="early-deductions",
            title="Prior claim deductions", event_kind=Rule.ADJUSTMENT, recognition_point=Rule.DV_VALIDATION,
            authority_reference="Synthetic reviewed policy", created_by=self.preparer)
        Line.objects.bulk_create([
            Line(rule=adjustment, sequence=1, label="Reduce original", side=Line.DEBIT,
                account_source=Line.PRIOR_PAYABLE, amount_source=Line.TOTAL_DEDUCTIONS),
            Line(rule=adjustment, sequence=2, label="Tax liability", side=Line.CREDIT,
                account_source=Line.DEDUCTION_MAPPINGS, amount_source=Line.EACH_DEDUCTION)])
        self.validate(self.case)
        tax_entry = self.post_request(self.case.posting_requests.get(kind=Rule.ADJUSTMENT))
        self.assertEqual(tax_entry.lines.get(account=self.payable_account).payable_origin_id, self.source.pk)
        self.pay(self.case)
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("0"))
        self.assertEqual(self.case.posting_requests.filter(kind=Rule.RECOGNITION).count(), 1)
