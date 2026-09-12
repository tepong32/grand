from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import Permission

from accounting.models import JournalSubsidiaryLine, LedgerAccount, JournalEntry, JournalLine, Fund, PostingMapping
from accounting.services import subsidiary_schedule_rows, control_reconciliation_snapshot
from finance.models import FinanceParty, FinanceTransactionVariant, FinancePostingRuleLine
from reporting.datasets import PostedAdvanceScheduleDataset
from . import tests as fixtures
from .models import VoucherPostingRequest, VoucherCase
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .services import prepare_voucher, validate_accounting, issue_check, submit_checks_for_advice, finalize_bank_advice, release_check
from accounting.services import submit_entry, post_entry, create_reversal


class AdvanceRecognitionTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.VoucherWorkflowTests.setUpTestData.__func__)
    employee = classmethod(fixtures.VoucherWorkflowTests.employee.__func__)
    create_case = fixtures.VoucherWorkflowTests.create_case
    budget_certify = fixtures.VoucherWorkflowTests.budget_certify
    return_signatures = fixtures.VoucherWorkflowTests.return_signatures
    ready_for_treasury = fixtures.VoucherWorkflowTests.ready_for_treasury
    enable_payment_event_rules = fixtures.VoucherWorkflowTests.enable_payment_event_rules
    acknowledge_advice = fixtures.VoucherWorkflowTests.acknowledge_advice

    @classmethod
    def setUpClass(cls):
        files = TemporaryDirectory()
        cls.addClassCleanup(files.cleanup)
        setting = override_settings(MEDIA_ROOT=files.name, GRAND_EXPORT_ROOT=files.name)
        setting.enable()
        cls.addClassCleanup(setting.disable)
        super().setUpClass()

    def setUp(self):
        # Adapt synthetic governed fixture, never operator configuration/history.
        FinanceParty.objects.filter(pk=self.party.pk).update(party_type=FinanceParty.EMPLOYEE, display_name="Synthetic accountable officer")
        self.party.refresh_from_db()
        FinanceTransactionVariant.objects.filter(pk=self.transaction_variant.pk).update(kind=FinanceTransactionVariant.CASH_ADVANCE)
        self.transaction_variant.refresh_from_db()
        self.advance = LedgerAccount.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, code="1-ADV-SYNTH", title="Synthetic accountable advances",
            account_type="asset", normal_balance="debit")
        self.recognition_rule.lines.filter(sequence=20).delete()
        self.recognition_rule.lines.filter(sequence=10).update(account_source=FinancePostingRuleLine.ADVANCE_ACCOUNT,
            amount_source=FinancePostingRuleLine.GROSS, ledger_account_code=self.advance.code)

    def accounting_prepare(self, case, key="prepare-dv"):
        case.refresh_from_db()
        return prepare_voucher(case=case, actor=self.preparer, voucher_date=date(2026, 8, 25),
            gross_amount=Decimal("1000"), deductions=[], line_description="Synthetic officer advance",
            line_account_code="5-02-03", document_codes=["invoice"],
            expected_version=case.state_version, idempotency_key=key)

    def test_recognition_payment_and_officer_schedule(self):
        self.enable_payment_event_rules("op_suppliers")
        case = self.ready_for_treasury()
        recognition = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        detail = JournalSubsidiaryLine.objects.get(category=JournalSubsidiaryLine.ADVANCE)
        self.assertEqual(detail.debit, Decimal("1000"))
        self.assertEqual(detail.reference_key, f"finance-party:{self.party.code}")
        self.assertEqual(detail.source_snapshot["advance_recognition"]["party_id"], self.party.pk)
        self.assertEqual(detail.entry.lines.filter(account__account_type="expense").count(), 0)
        self.assertEqual(recognition.payload["advance_recognition"]["party_version"], self.party.version)
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp",
            check_number="ADV-001", amount=Decimal("1000"), expected_version=case.state_version,
            idempotency_key="advance-issue")
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user,
            expected_version=case.state_version, idempotency_key="advance-submit")
        case.refresh_from_db()
        batch = finalize_bank_advice(case=case, actor=self.preparer, advice_number="ADVANCE-ADVICE",
            advice_date=date(2026, 8, 25), expected_version=case.state_version, idempotency_key="advance-advice",
            preparation_note="Synthetic officer advance", authority_reference="Synthetic locally reviewed basis",
            local_applicability_note="Synthetic scenario; local acceptance remains open")
        self.acknowledge_advice(batch)
        case.refresh_from_db(); instrument.refresh_from_db()
        release_check(case=case, instrument=instrument, actor=self.treasury_user, claimant=self.claimant,
            receipt_reference="SYNTHETIC-ADVANCE-RECEIPT", expected_version=case.state_version,
            idempotency_key="advance-release")
        request = case.posting_requests.get(kind=VoucherPostingRequest.PAYMENT)
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer); entry.refresh_from_db()
        post_entry(entry, self.validator); entry.refresh_from_db()
        reconcile_posted_voucher_entry(entry, self.validator)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual(entry.lines.get(account__code="1-01-02").credit, Decimal("1000"))
        rows = subsidiary_schedule_rows(self.accounting.pk, "advance", timezone.localdate())
        self.assertEqual(rows[0]["balance"], Decimal("1000"))
        snapshot, _ = control_reconciliation_snapshot(self.accounting.pk, timezone.localdate())
        control = next(row for row in snapshot["rows"] if row["category"] == "advance")
        self.assertEqual(Decimal(control["gl_balance"]), Decimal("1000"))
        self.assertEqual(Decimal(control["difference"]), 0)
        payload = PostedAdvanceScheduleDataset().payload(self.accounting, date(2026,1,1), timezone.localdate(), {})
        self.assertEqual(payload.control_status, "reconciled")
        self.assertEqual(payload.sources[0]["amount"], Decimal("1000"))
        self.preparer.user_permissions.add(*Permission.objects.filter(codename__in=("view_general_ledger", "export_finance_work")))
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("accounting:subsidiary_controls"))
        self.assertContains(response, "Recognized officer advances")
        response = self.client.get(reverse("accounting:subsidiary_export", args=["advance"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-GRAND-Export-Archived"], "true")
        self.assertIn("debit_balance", response.content.decode())
        self.assertIn("Synthetic accountable officer", response.content.decode())
        with self.assertRaisesMessage(ValidationError, "detached reversal is not supported"):
            create_reversal(detail.entry, self.preparer, reference="INVALID-ADV-REVERSAL",
                entry_date=detail.entry.entry_date, period=detail.entry.period, reason="Synthetic error")
        self.assertFalse(JournalEntry.objects.filter(reversal_of=detail.entry).exists())

        # A later GL-only credit cannot silently appear as a liquidated advance.
        mismatch = JournalEntry.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, reference="ADV-UNLINKED", entry_date=detail.entry.entry_date,
            period=detail.entry.period, fund=detail.entry.fund, source_type="manual", description="Synthetic unexplained asset movement",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=mismatch, sequence=1, account=self.advance, credit=Decimal("100"))
        JournalLine.objects.create(entry=mismatch, sequence=2, account=LedgerAccount.objects.get(code="1-01-02"), debit=Decimal("100"))
        submit_entry(mismatch, self.preparer); mismatch.refresh_from_db()
        post_entry(mismatch, self.validator)
        discrepant = PostedAdvanceScheduleDataset().payload(self.accounting, date(2026,1,1), timezone.localdate(), {})
        self.assertEqual(discrepant.control_status, "exception")
        self.assertEqual(discrepant.control_totals["difference"], Decimal("-100"))
        other_fund = Fund.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, code="other-synthetic", name="Synthetic second fund")
        other = JournalEntry.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, reference="ADV-OTHER-FUND", entry_date=detail.entry.entry_date,
            period=detail.entry.period, fund=other_fund, source_type="manual", description="Synthetic other-fund control gap",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=other, sequence=1, account=self.advance, credit=Decimal("100"))
        JournalLine.objects.create(entry=other, sequence=2, account=LedgerAccount.objects.get(code="1-01-02"), debit=Decimal("100"))
        submit_entry(other, self.preparer); other.refresh_from_db()
        post_entry(other, self.validator)
        discrepant = PostedAdvanceScheduleDataset().payload(self.accounting, date(2026,1,1), timezone.localdate(), {})
        self.assertEqual(discrepant.control_totals["absolute_difference"], Decimal("200"))

    def test_supplier_cannot_be_accountable_officer(self):
        FinanceParty.objects.filter(pk=self.party.pk).update(party_type=FinanceParty.SUPPLIER)
        self.party.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "governed employee"):
            self.ready_for_treasury()
        self.assertFalse(VoucherPostingRequest.objects.exists())

    def test_expense_account_cannot_be_used_as_advance(self):
        self.recognition_rule.lines.filter(sequence=10).update(ledger_account_code="5-02-03")
        with self.assertRaisesMessage(ValidationError, "debit-normal asset"):
            self.ready_for_treasury()
        self.assertFalse(JournalSubsidiaryLine.objects.filter(category="advance").exists())

    def test_ordinary_supplier_variant_cannot_create_advance(self):
        FinanceTransactionVariant.objects.filter(pk=self.transaction_variant.pk).update(kind=FinanceTransactionVariant.ORDINARY_SUPPLIER)
        with self.assertRaisesMessage(ValidationError, "cash-advance variant"):
            self.ready_for_treasury()
        self.assertFalse(VoucherPostingRequest.objects.exists())

    def test_advance_cannot_credit_an_asset_as_payable(self):
        PostingMapping.objects.filter(category=PostingMapping.PAYABLE).update(account=self.advance)
        with self.assertRaisesMessage(ValidationError, "credit-normal payable liability"):
            self.ready_for_treasury()
        self.assertFalse(JournalSubsidiaryLine.objects.filter(category="advance").exists())
