from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
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

    def paid_advance(self, *, reconcile=True):
        self.enable_payment_event_rules("op_suppliers")
        case = self.ready_for_treasury()
        recognition = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        detail = JournalSubsidiaryLine.objects.get(category=JournalSubsidiaryLine.ADVANCE)
        self.assertEqual(detail.debit, Decimal("1000"))
        self.assertEqual(detail.reference_key, f"finance-party:{self.party.code}")
        self.assertEqual(detail.source_snapshot["advance_recognition"]["party_id"], self.party.pk)
        self.assertEqual(detail.entry.lines.filter(account__account_type="expense").count(), 0)
        self.assertEqual(recognition.payload["advance_recognition"]["party_version"], self.party.version)
        from .advance_sources import disbursement
        self.assertEqual(disbursement(detail, timezone.localdate())["released_net"], 0)
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
        if not reconcile:
            case.refresh_from_db()
            return detail, case, instrument
        reconcile_posted_voucher_entry(entry, self.validator)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual(disbursement(detail, timezone.localdate())["released_net"], Decimal("1000"))
        self.assertEqual(disbursement(detail, date(2026,8,25))["released_net"], 0)
        self.assertEqual(entry.lines.get(account__code="1-01-02").credit, Decimal("1000"))
        return detail, case, instrument

    def test_recognition_payment_and_officer_schedule(self):
        detail, case, instrument = self.paid_advance()
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

    def liquidation_rule(self):
        from finance.models import FinancePostingRule as Rule
        rule = Rule.objects.create(variant=self.transaction_variant, code="synthetic-liquidation",
            title="Synthetic accepted expenses", event_kind=Rule.LIQUIDATION,
            recognition_point=Rule.LIQUIDATION_ACCEPTANCE, description="Synthetic expense liquidation",
            authority_reference="Synthetic locally reviewed expense basis", created_by=self.preparer)
        FinancePostingRuleLine.objects.bulk_create([
            FinancePostingRuleLine(rule=rule, sequence=1, label="Accepted expense", side="debit",
                account_source=FinancePostingRuleLine.ALLOCATION_ACCOUNTS, amount_source=FinancePostingRuleLine.EACH_ALLOCATION),
            FinancePostingRuleLine(rule=rule, sequence=2, label="Original advance", side="credit",
                account_source=FinancePostingRuleLine.PRIOR_ADVANCE, amount_source=FinancePostingRuleLine.GROSS)])
        return rule

    def test_partial_liquidation_reserves_posts_and_reconciles_original_advance(self):
        from .advance_applications import prepare, materialize, reconcile
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        def proposal(amount, key, day=None):
            return prepare(detail=detail, actor=self.preparer, rule=rule, day=day or timezone.localdate(),
                expenses=[{"account_code":"5-02-03", "amount":amount, "document_reference":"SYNTHETIC-EXPENSE"}],
                evidence_reference=f"SYNTHETIC-LIQUIDATION-{key}", key=key)
        with self.assertRaisesMessage(ValidationError, "exceeds the released"):
            proposal("1", "backdated", date(2026,8,25))
        first = proposal("600", "first")
        self.assertEqual(proposal("600", "first").pk, first.pk)
        with self.assertRaisesMessage(ValidationError, "exceeds the released"):
            proposal("400.01", "over-capacity")
        second = proposal("400", "second")
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="post_journal_entries"))
        for request in (first, second):
            entry, created = materialize(request, self.preparer)
            self.assertTrue(created)
            self.assertEqual(materialize(request, self.preparer)[0].pk, entry.pk)
            submit_entry(entry, self.preparer); entry.refresh_from_db()
            with self.assertRaisesMessage(ValidationError, "independent Accounting"):
                post_entry(entry, self.preparer)
            post_entry(entry, self.validator); entry.refresh_from_db()
            reconcile(entry, self.validator)
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, "advance", timezone.localdate())[0]["balance"], 0)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual(JournalSubsidiaryLine.objects.filter(category="advance").count(), 3)
        with self.assertRaisesMessage(ValidationError, "exceeds the released"):
            proposal("0.01", "fully-used")

    def test_web_entry_retains_errors_and_independent_withdrawal_history(self):
        import uuid
        from accounting.services import discard_draft
        from .advance_applications import prepare
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="view_general_ledger"))
        self.client.force_login(self.preparer)
        url = reverse("accounting:advance_detail", args=[detail.pk])
        self.assertContains(self.client.get(url), "Prepare expense liquidation")
        data = {"day":timezone.localdate().isoformat(), "rule":rule.pk, "key":str(uuid.uuid4()),
            "document_reference":"SYNTHETIC-WEB-LIQ", "expenses-TOTAL_FORMS":"1", "expenses-INITIAL_FORMS":"0",
            "expenses-MIN_NUM_FORMS":"1", "expenses-MAX_NUM_FORMS":"100", "expenses-0-account":"5-02-03",
            "expenses-0-amount":"1000.01", "expenses-0-document_reference":"SYNTHETIC-WEB-EXPENSE"}
        response = self.client.post(url, data)
        self.assertContains(response, "exceeds the released")
        self.assertContains(response, "SYNTHETIC-WEB-EXPENSE")
        data["expenses-0-amount"] = "600"
        self.assertEqual(self.client.post(url, data).status_code, 302)
        request = case.posting_requests.get(kind=VoucherPostingRequest.LIQUIDATION)
        entry = JournalEntry.objects.get(public_id=request.accounting_entry_public_id)
        withdraw_url = reverse("accounting:advance_application_action", args=[request.public_id, "withdraw"])
        self.assertEqual(self.client.post(withdraw_url, {"reason":"Correct the source"}).status_code, 403)
        self.client.force_login(self.validator)
        self.assertEqual(self.client.post(withdraw_url, {"reason":"Correct the source"}).status_code, 302)
        request.refresh_from_db()
        self.assertNotEqual(request.status, VoucherPostingRequest.CANCELLED)
        discard_draft(entry, self.preparer, "Synthetic source correction")
        self.assertEqual(self.client.post(withdraw_url, {"reason":"Correct the source"}).status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.status, VoucherPostingRequest.CANCELLED)
        self.assertTrue(case.events.filter(action="advance_liquidation_withdrawn").exists())
        self.assertContains(self.client.get(url), "SYNTHETIC-WEB-LIQ")
        from django.contrib.auth.models import Group
        from .roles import FINANCE_UAT_VIEWER_GROUP
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(url), "SYNTHETIC-WEB-LIQ")
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_source_and_subsidiary_tampering_block_liquidation_submission(self):
        from .advance_applications import prepare, materialize
        detail, case, instrument = self.paid_advance()
        request = prepare(detail=detail, actor=self.preparer, rule=self.liquidation_rule(), day=timezone.localdate(),
            expenses=[{"account_code":"5-02-03", "amount":"600", "document_reference":"SYNTHETIC-EXPENSE"}],
            evidence_reference="SYNTHETIC-LIQ", key="tamper")
        entry, _ = materialize(request, self.preparer)
        JournalSubsidiaryLine.objects.filter(entry=entry).update(reference_key="another-officer")
        with self.assertRaisesMessage(ValidationError, "original officer"):
            submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.DRAFT)

    def test_web_liquidation_posts_expenses_without_second_payment_and_retains_export(self):
        import csv
        import io
        import uuid
        from pathlib import Path
        from django.conf import settings
        from .advance_applications import prepare, materialize, reconcile
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="view_general_ledger"))
        self.client.force_login(self.preparer)
        data = {"day":timezone.localdate().isoformat(), "rule":rule.pk, "key":str(uuid.uuid4()),
            "document_reference":"SYNTHETIC-ACCEPTED-EXPENSES", "expenses-TOTAL_FORMS":"2", "expenses-INITIAL_FORMS":"0",
            "expenses-MIN_NUM_FORMS":"1", "expenses-MAX_NUM_FORMS":"100", "expenses-0-account":"5-02-03",
            "expenses-0-amount":"200", "expenses-0-document_reference":"SYNTHETIC-EXPENSE-1",
            "expenses-1-account":"5-02-03", "expenses-1-amount":"400", "expenses-1-document_reference":"SYNTHETIC-EXPENSE-2"}
        self.assertEqual(self.client.post(reverse("accounting:advance_detail", args=[detail.pk]), data).status_code, 302)
        request = case.posting_requests.get(kind=VoucherPostingRequest.LIQUIDATION)
        entry = JournalEntry.objects.get(public_id=request.accounting_entry_public_id)
        self.assertEqual(self.client.post(reverse("accounting:entry_submit", args=[entry.public_id])).status_code, 302)
        self.client.force_login(self.validator)
        self.assertEqual(self.client.post(reverse("accounting:entry_post", args=[entry.public_id])).status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.status, VoucherPostingRequest.POSTED)
        self.assertEqual(list(entry.lines.order_by("sequence").values_list("debit", "credit")),
            [(Decimal("200"), Decimal("0")), (Decimal("400"), Decimal("0")), (Decimal("0"), Decimal("600"))])
        self.assertFalse(entry.lines.filter(account__code="1-01-02").exists())
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("accounting:subsidiary_export", args=["advance"]))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual(Decimal(rows[0]["debit_balance"]), Decimal("400"))
        archived = Path(settings.GRAND_EXPORT_ROOT) / response["X-GRAND-Export-Relative-Path"]
        self.assertEqual(archived.read_bytes(), response.content)

        second = prepare(detail=detail, actor=self.preparer, rule=rule, day=timezone.localdate(),
            expenses=[{"account_code":"5-02-03", "amount":"400", "document_reference":"SYNTHETIC-EXPENSE-3"}],
            evidence_reference="SYNTHETIC-FINAL-LIQUIDATION", key="final")
        final_entry, _ = materialize(second, self.preparer)
        submit_entry(final_entry, self.preparer); final_entry.refresh_from_db()
        post_entry(final_entry, self.validator); final_entry.refresh_from_db()
        reconcile(final_entry, self.validator)
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, "advance", timezone.localdate())[0]["balance"], 0)
        self.assertEqual(archived.read_bytes(), response.content)

    def test_standard_accounting_preparer_role_can_enter_and_export_without_general_ledger_access(self):
        import uuid
        from django.contrib.auth.models import Group
        from accounting.access import can_view_ledger
        from .roles import FINANCE_ROLE_PERMISSIONS, FINANCE_UAT_VIEWER_GROUP
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        group = Group.objects.get_or_create(name="Accounting DV Preparer")[0]
        permission_rows = []
        for label in FINANCE_ROLE_PERMISSIONS["Accounting DV Preparer"]:
            app, code = label.split(".")
            permission_rows.append(Permission.objects.get(content_type__app_label=app, codename=code))
        group.permissions.set(permission_rows)
        user = self.employee("advance.role.preparer", self.accounting)
        user.groups.add(group)
        self.assertFalse(can_view_ledger(user))
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("accounting:workspace")), "Officer advances and liquidations")
        register = reverse("accounting:advance_register")
        self.assertContains(self.client.get(register), detail.reference_label)
        url = reverse("accounting:advance_detail", args=[detail.pk])
        self.assertContains(self.client.get(url), "Remaining released amount:")
        data = {"day":timezone.localdate().isoformat(), "rule":rule.pk, "key":str(uuid.uuid4()),
            "document_reference":"SYNTHETIC-ROLE-LIQ", "expenses-TOTAL_FORMS":"1", "expenses-INITIAL_FORMS":"0",
            "expenses-MIN_NUM_FORMS":"1", "expenses-MAX_NUM_FORMS":"100", "expenses-0-account":"5-02-03",
            "expenses-0-amount":"600", "expenses-0-document_reference":"SYNTHETIC-ROLE-EXPENSE"}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        page = self.client.get(url)
        self.assertContains(page, "400.00")
        self.assertEqual(self.client.get(reverse("accounting:advance_export")).status_code, 200)
        viewer = self.employee("advance.only.viewer", self.accounting)
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="view_officer_advances"))
        viewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(register).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounting:advance_export")).status_code, 403)
        self.assertEqual(self.client.post(url, data).status_code, 403)

    def test_corrupt_or_unwitnessed_reservations_do_not_free_capacity(self):
        from copy import deepcopy
        from .advance_applications import prepare
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        def proposal(key):
            return prepare(detail=detail, actor=self.preparer, rule=rule, day=timezone.localdate(),
                expenses=[{"account_code":"5-02-03", "amount":"600", "document_reference":"SYNTHETIC-EXPENSE"}],
                evidence_reference=f"SYNTHETIC-{key}", key=key)
        first = proposal("original")
        corrupted = deepcopy(first.payload)
        corrupted["advance_application"]["amount"] = "1.00"
        VoucherPostingRequest.objects.filter(pk=first.pk).update(payload=corrupted)
        with self.assertRaisesMessage(ValidationError, "reservation evidence changed"):
            proposal("second")
        VoucherPostingRequest.objects.filter(pk=first.pk).update(payload=first.payload, status=VoucherPostingRequest.CANCELLED)
        with self.assertRaisesMessage(ValidationError, "independently withdrawn"):
            proposal("second")
        self.assertEqual(case.posting_requests.filter(kind=VoucherPostingRequest.LIQUIDATION).count(), 1)

    def test_observed_bank_return_withholds_release_before_liquidation_posting(self):
        from .models import TreasuryCashPolicy, PaymentInstrumentException
        from .cash_positions import open_instrument_exception
        from .advance_applications import prepare, materialize
        from .advance_sources import disbursement
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        request = prepare(detail=detail, actor=self.preparer, rule=rule, day=timezone.localdate(),
            expenses=[{"account_code":"5-02-03", "amount":"600", "document_reference":"SYNTHETIC-EXPENSE"}],
            evidence_reference="SYNTHETIC-PENDING-LIQ", key="pending")
        entry, _ = materialize(request, self.preparer)
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code="gf-lbp", fund_code="general-fund", mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=0, position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=date(2026,1,1), authority_reference="Synthetic policy", local_applicability_note="Synthetic",
            status=TreasuryCashPolicy.ACTIVE, created_by=self.treasury_user, submitted_by=self.treasury_user,
            submitted_at=timezone.now(), approved_by=self.validator, approved_at=timezone.now())
        open_instrument_exception(instrument=instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(),
            reason="Synthetic bank returned unpaid", evidence_reference="SYNTHETIC-BANK-RETURN")
        self.assertEqual(disbursement(detail, timezone.localdate())["released_net"], 0)
        with self.assertRaisesMessage(ValidationError, "exceeds the released"):
            submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.DRAFT)
