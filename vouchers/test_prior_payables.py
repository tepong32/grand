"""Actual prior-claim DV, deduction, release and returned-payment handoffs."""
from datetime import date
from decimal import Decimal
import shutil
import tempfile
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import Group, Permission
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine, PayableClaimReservation
from accounting.payables import claim_rows, _capacity
from accounting.services import submit_entry, post_entry, create_reversal
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import tests as fixtures
from .forms import AccountingValidationForm
from .models import PayableIntake, VoucherCase, VoucherPostingRequest, PaymentInstrumentException, TreasuryCashPolicy, ReturnedInstrumentReview
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .prior_payables import current_reservation
from .services import validate_accounting, prepare_voucher, issue_check, submit_checks_for_advice, finalize_bank_advice, release_check, return_case, cancel_check
from .cash_positions import open_instrument_exception
from .advice import decide_returned_instrument


class PriorPayableDVTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.VoucherWorkflowTests.setUpTestData.__func__)
    employee = classmethod(fixtures.VoucherWorkflowTests.employee.__func__)
    create_case = fixtures.VoucherWorkflowTests.create_case
    budget_certify = fixtures.VoucherWorkflowTests.budget_certify
    return_signatures = fixtures.VoucherWorkflowTests.return_signatures
    acknowledge_advice = fixtures.VoucherWorkflowTests.acknowledge_advice
    enable_payment_event_rules = fixtures.VoucherWorkflowTests.enable_payment_event_rules

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix="grand-prior-dv-")
        cls.override = override_settings(MEDIA_ROOT=cls.temp, GRAND_EXPORT_ROOT=cls.temp)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.temp, ignore_errors=True)

    def setUp(self):
        self.payment_rule = self.enable_payment_event_rules(cash_flow_category="op_suppliers")
        adjustment = Rule.objects.create(variant=self.transaction_variant, code="prior-deductions",
            title="Reclassify prior payable deductions", event_kind=Rule.ADJUSTMENT,
            recognition_point=Rule.DV_VALIDATION, authority_reference="Synthetic reviewed policy", created_by=self.preparer)
        Line.objects.bulk_create([
            Line(rule=adjustment, sequence=1, label="Reduce original payable", side=Line.DEBIT,
                account_source=Line.PRIOR_PAYABLE, amount_source=Line.TOTAL_DEDUCTIONS),
            Line(rule=adjustment, sequence=2, label="Withholding payable", side=Line.CREDIT,
                account_source=Line.DEDUCTION_MAPPINGS, amount_source=Line.EACH_DEDUCTION)])
        self.original = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="EARLIER-ACCRUAL", entry_date=date(2026, 8, 20), period=self.accounting_period,
            fund=self.accounting_fund, description="Synthetic earlier accepted invoice", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=self.original, sequence=1, account=self.expense_account, debit=1500)
        JournalLine.objects.create(entry=self.original, sequence=2, account=self.payable_account, credit=1500,
            payable_party_key=f"finance-party:{self.party.code}", payable_claim_reference="PRIOR-INVOICE-1")
        submit_entry(self.original, self.preparer)
        post_entry(self.original, self.validator)
        self.source = self.original.lines.get(sequence=2)

    def case_for_validation(self, suffix="", deductions=False, claim_reference="PRIOR-INVOICE-1"):
        case = self.create_case("create" + suffix)
        self.budget_certify(case, "certify" + suffix)
        case.refresh_from_db()
        prepare_voucher(case=case, actor=self.preparer, voucher_date=date(2026, 8, 25), gross_amount=Decimal("1000"),
            deductions=([{"code": "ewt", "description": "Withholding", "amount": Decimal("100")}] if deductions else []),
            line_description="Settlement of prior invoice", line_account_code="5-02-03", document_codes=["invoice"],
            expected_version=case.state_version, idempotency_key="prepare" + suffix)
        self.return_signatures(case)
        PayableIntake.objects.create(case=case,
            claim_reference=claim_reference, claim_amount=1500, initial_allocation_amount=1000,
            initial_relationship_type=PayableIntake.PARTIAL, status=PayableIntake.READY,
            recognition_decision=PayableIntake.SETTLE_EXISTING_PAYABLE,
            recognition_basis="Previously accrued original invoice; settle part only.", prepared_by=self.requesting_user)
        case.refresh_from_db()
        return case

    def validate(self, case, *, source=None, key="validate", actor=None):
        return validate_accounting(case=case, actor=actor or self.validator,
            jev_number="PRIOR-ADJ" if case.disbursement_voucher.total_deductions else "", jev_date=date(2026, 8, 25), note="Verified prior invoice",
            expected_version=case.state_version, idempotency_key=key, prior_payable_line_id=(source or self.source).pk)

    def post_request(self, request):
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer)
        post_entry(entry, self.validator)
        entry.refresh_from_db()
        reconcile_posted_voucher_entry(entry, self.validator)
        return entry

    def pay(self, case, suffix="", replaces=None):
        case.refresh_from_db()
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="PRIOR-CHECK" + suffix, amount=case.disbursement_voucher.net_amount, replaces=replaces,
            expected_version=case.state_version, idempotency_key="issue" + suffix)
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user, expected_version=case.state_version, idempotency_key="advice" + suffix)
        case.refresh_from_db()
        batch = finalize_bank_advice(case=case, actor=self.preparer, advice_number="PRIOR-ADVICE" + suffix,
            advice_date=timezone.localdate(), expected_version=case.state_version, idempotency_key="finalize" + suffix,
            preparation_note="Synthetic review", authority_reference="Synthetic reviewed procedure",
            local_applicability_note="Synthetic acceptance")
        self.acknowledge_advice(batch)
        case.refresh_from_db(); instrument.refresh_from_db()
        release_check(case=case, instrument=instrument, actor=self.treasury_user, claimant=self.claimant,
            receipt_reference="PRIOR-RECEIPT" + suffix, expected_version=case.state_version, idempotency_key="release" + suffix)
        request = case.posting_requests.get(kind=Rule.PAYMENT, trigger_key=f"payment-instrument:{instrument.public_id}:released")
        return instrument, self.post_request(request)

    def test_no_deduction_dv_reuses_prior_claim_and_posts_only_actual_payment(self):
        case = self.case_for_validation()
        self.validate(case)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)
        self.assertFalse(case.posting_requests.exists())
        self.assertEqual(_capacity(self.source), Decimal("500"))
        reservation = current_reservation(case)
        self.client.force_login(self.validator)
        page = self.client.get(reverse("vouchers:case_detail", args=[case.public_id]))
        self.assertContains(page, "Prior-payable validation record")
        self.assertContains(page, "EARLIER-ACCRUAL")
        instrument, payment = self.pay(case)
        self.assertFalse(payment.lines.filter(account=self.expense_account).exists())
        line = payment.lines.get(account=self.payable_account)
        self.assertEqual((line.payable_origin_id, line.payable_reservation_id, line.debit), (self.source.pk, reservation.pk, Decimal("1000")))
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("500"))
        self.assertEqual(_capacity(self.source), Decimal("500"))
        with self.assertRaisesMessage(ValidationError, "governed cancellation or bank-return"):
            create_reversal(payment, self.preparer, reference="DETACHED-UNDO", entry_date=payment.entry_date,
                period=payment.period, reason="Detached reversal would bypass the payment workflow")
        export = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"1500.00,1000.00,500.00", export.content)
        self.assertEqual(export["X-GRAND-Export-Archived"], "true")

    def deduction_return_cycle(self, close=False):
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code="gf-lbp", fund_code="general-fund", mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=0, position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=date(2026, 1, 1), authority_reference="Synthetic policy", local_applicability_note="Synthetic",
            status=TreasuryCashPolicy.ACTIVE, created_by=self.treasury_user, submitted_by=self.treasury_user,
            submitted_at=timezone.now(), approved_by=self.validator, approved_at=timezone.now())
        case = self.case_for_validation(deductions=True)
        self.validate(case)
        adjustment = self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        self.assertEqual(adjustment.lines.get(account=self.payable_account).debit, Decimal("100"))
        self.assertFalse(adjustment.lines.filter(account=self.expense_account).exists())
        instrument, payment = self.pay(case)
        case.refresh_from_db(); instrument.refresh_from_db()
        exception = open_instrument_exception(instrument=instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(), reason="Bank returned unpaid",
            evidence_reference="Synthetic bank return memorandum")
        review = exception.accounting_reviews.get()
        decide_returned_instrument(review=review, actor=self.validator, approve=True,
            outcome=ReturnedInstrumentReview.CLOSE_WITHOUT_REISSUE if close else ReturnedInstrumentReview.REISSUE,
            decision_reason="Restore original payable for replacement", evidence_reference="Synthetic independent review",
            expected_version=review.state_version)
        review.refresh_from_db()
        if close:
            with patch("vouchers.cash_positions.resolve_instrument_exception", side_effect=RuntimeError("Interrupted closing handoff")):
                with self.assertRaises(RuntimeError):
                    self.post_request(review.posting_request)
            self.assertIsNotNone(PayableClaimReservation.objects.get().released_at)
            reversal = JournalEntry.objects.get(source_reference=str(review.posting_request.public_id))
            reconcile_posted_voucher_entry(reversal, self.validator)
        else:
            reversal = self.post_request(review.posting_request)
        self.assertEqual(reversal.reversal_of_id, payment.pk)
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("1400"))
        if close:
            self.assertEqual(_capacity(self.source), Decimal("1400"))
            self.assertIsNotNone(PayableClaimReservation.objects.get().released_at)
            case.refresh_from_db()
            self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
            next_case = self.case_for_validation("-after-close")
            self.validate(next_case)
            self.assertEqual(_capacity(self.source), Decimal("400"))
            return
        self.assertEqual(_capacity(self.source), Decimal("500"))
        instrument.refresh_from_db()
        self.pay(case, "-replacement", replaces=instrument)
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("500"))

    def test_deduction_adjustment_payment_bank_return_and_replacement(self):
        self.deduction_return_cycle()

    def test_return_closed_without_replacement_frees_only_unused_claim_capacity(self):
        self.deduction_return_cycle(close=True)

    def test_interrupted_validation_recovers_same_hold_and_return_releases_orphan(self):
        case = self.case_for_validation()
        with patch("vouchers.services._advance", side_effect=RuntimeError("Simulated default commit failure")):
            with self.assertRaises(RuntimeError):
                self.validate(case)
        self.assertFalse(case.accounting_validations.exists())
        self.assertEqual(PayableClaimReservation.objects.count(), 1)
        self.validate(case)
        self.assertEqual(PayableClaimReservation.objects.count(), 1)
        case.refresh_from_db()
        return_case(case=case, actor=self.treasury_user, target_stage=VoucherCase.ACCOUNTING_VALIDATION,
            reason="Correct selected claim before payment", expected_version=case.state_version, idempotency_key="return")
        self.assertEqual(_capacity(self.source), Decimal("1500"))
        case.refresh_from_db()
        self.validate(case, key="validate-again")
        self.assertEqual(PayableClaimReservation.objects.count(), 2)

    def test_historical_attribution_http_to_dv_payment_and_claim_export(self):
        from accounting.models import PostingMapping, PayableClaimAttribution
        from accounting.claim_attributions import serial_snapshot, propose, review
        legacy = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="HISTORICAL-INVOICE", entry_date=date(2026, 8, 20), period=self.accounting_period,
            fund=self.accounting_fund, description="Older invoice with no individual claim link",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=legacy, sequence=1, account=self.expense_account, debit=1500)
        historical = JournalLine.objects.create(entry=legacy, sequence=2, account=self.payable_account, credit=1500)
        submit_entry(legacy, self.preparer)
        post_entry(legacy, self.validator)
        old_payment = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="HISTORICAL-PAYMENT", entry_date=date(2026, 8, 22), period=self.accounting_period,
            fund=self.accounting_fund, description="Earlier partial payment",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        application = JournalLine.objects.create(entry=old_payment, sequence=1, account=self.payable_account, debit=300)
        bank = PostingMapping.objects.filter(department_id=self.accounting.pk, category=PostingMapping.BANK).first().account
        JournalLine.objects.create(entry=old_payment, sequence=2, account=bank, credit=300, cash_flow_category="op_suppliers")
        submit_entry(old_payment, self.preparer)
        post_entry(old_payment, self.validator)
        unchanged = serial_snapshot(historical, [application.pk])
        url = reverse("accounting:claim_attribution", args=[historical.pk])
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(url), "Historical claim attribution")
        response = self.client.post(url, {"expected_version": 0, "party_key": f"finance-party:{self.party.code}",
            "claim_reference": "HIST-001", "applications": [application.pk], "complete_history": "on",
            "evidence_reference": "Original invoice and partial-payment schedule", "reason": "Reconciled legacy claim"})
        self.assertEqual(response.status_code, 302, response.content)
        proposal = PayableClaimAttribution.objects.get(source=historical)
        review_url = reverse("accounting:claim_attribution_review", args=[historical.pk, proposal.public_id, "approve"])
        self.client.post(review_url, {"note": "Cannot approve my own proposal"})
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, proposal.SUBMITTED)
        self.client.force_login(self.validator)
        self.assertEqual(self.client.post(review_url, {"note": "Verified invoice and earlier payment"}).status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, proposal.APPROVED)
        case = self.case_for_validation("-historical", deductions=True, claim_reference="HIST-001")
        choices = AccountingValidationForm(case=case).fields["prior_payable_line"].queryset
        self.assertIn(historical, choices)
        self.validate(case, source=historical)
        self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        retained = current_reservation(case).source_snapshot["claim_attribution"]
        self.assertEqual(retained["public_id"], str(proposal.public_id))
        updated = propose(historical, self.preparer, party_key=f"finance-party:{self.party.code}",
            claim_reference="HIST-001", applications=[application.pk], evidence_reference="Additional reconciliation evidence",
            reason="Supplement the evidence without changing the invoice or applications", expected_version=1)
        review(updated, self.validator, approve=True, note="Verified supplementary evidence")
        self.assertEqual(current_reservation(case).source_snapshot["claim_attribution"], retained)
        _, payment = self.pay(case, suffix="-historical")
        line = payment.lines.get(account=self.payable_account)
        self.assertEqual((line.payable_origin_id, line.debit), (historical.pk, Decimal("900")))
        self.assertEqual(payment.source_snapshot["prior_payable"]["source"]["claim_attribution"], retained)
        self.assertEqual(serial_snapshot(historical, [application.pk]), unchanged)
        exported = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertEqual(exported.status_code, 200)
        self.assertIn(b"1500.00,1300.00,200.00", exported.content)
        self.preparer.groups.add(Group.objects.get_or_create(name="Finance UAT Viewer")[0])
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="view_accounting_workspace"))
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_validation_cannot_spend_capacity_restored_after_its_date(self):
        adjustment = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="PRIOR-REDUCTION", entry_date=date(2026, 8, 22), period=self.accounting_period,
            fund=self.accounting_fund, description="Earlier reduction of the original claim",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=adjustment, sequence=1, account=self.payable_account,
            debit=1000, payable_origin=self.source)
        JournalLine.objects.create(entry=adjustment, sequence=2, account=self.expense_account, credit=1000)
        submit_entry(adjustment, self.preparer)
        post_entry(adjustment, self.validator)
        undo = create_reversal(adjustment, self.preparer, reference="PRIOR-RESTORED",
            entry_date=date(2026, 8, 28), period=self.accounting_period, reason="Reverse the earlier reduction")
        submit_entry(undo, self.preparer)
        post_entry(undo, self.validator)
        self.assertEqual(_capacity(self.source), Decimal("1500"))
        for deductions in (True, False):
            case = self.case_for_validation(f"-dated-{deductions}", deductions=deductions)
            stage, version = case.current_stage, case.state_version
            with self.assertRaisesMessage(ValidationError, "on or after the requested date"):
                self.validate(case, key=f"too-early-{deductions}")
            case.refresh_from_db()
            self.assertEqual((case.current_stage, case.state_version), (stage, version))
            self.assertFalse(case.accounting_validations.exists())
            self.assertFalse(case.posting_requests.exists())
            self.assertFalse(PayableClaimReservation.objects.filter(case_public_id=case.public_id).exists())
        validate_accounting(case=case, actor=self.validator, jev_number="", jev_date=date(2026, 8, 29),
            note="Actual validation after the posted restoration", expected_version=case.state_version,
            idempotency_key="dated-valid", prior_payable_line_id=self.source.pk)
        _, payment = self.pay(case, suffix="-dated")
        self.assertEqual(payment.lines.get(account=self.payable_account).debit, Decimal("1000"))
        # Applications to a live reservation consume its hold, not capacity twice.
        self.assertEqual(_capacity(self.source, as_of=date(2026, 8, 29)), Decimal("500"))
        self.client.force_login(self.validator)
        export = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"1500.00,1000.00,500.00", export.content)

    def test_interrupted_validation_rechecks_retry_date_before_advancement(self):
        adjustment = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="RECOVERY-REDUCTION", entry_date=date(2026, 8, 22), period=self.accounting_period,
            fund=self.accounting_fund, description="Earlier reduction of the original claim",
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=adjustment, sequence=1, account=self.payable_account,
            debit=1000, payable_origin=self.source)
        JournalLine.objects.create(entry=adjustment, sequence=2, account=self.expense_account, credit=1000)
        submit_entry(adjustment, self.preparer)
        post_entry(adjustment, self.validator)
        undo = create_reversal(adjustment, self.preparer, reference="RECOVERY-RESTORED",
            entry_date=date(2026, 8, 28), period=self.accounting_period, reason="Reverse the earlier reduction")
        submit_entry(undo, self.preparer)
        post_entry(undo, self.validator)
        case = self.case_for_validation("-recovery-date")
        stage, version = case.current_stage, case.state_version
        with patch("vouchers.services._advance", side_effect=RuntimeError("Interrupted default-store advancement")):
            with self.assertRaises(RuntimeError):
                validate_accounting(case=case, actor=self.validator, jev_number="", jev_date=date(2026, 8, 29),
                    note="Actual later settlement", expected_version=version, idempotency_key="interrupted-claim-date",
                    prior_payable_line_id=self.source.pk)
        held = PayableClaimReservation.objects.get(case_public_id=case.public_id)
        retained = (held.pk, held.source_snapshot, held.source_checksum)
        self.client.force_login(self.validator)
        data = {"state_version": version, "idempotency_key": "retry-earlier", "jev_number": "",
            "jev_date": "2026-08-25", "prior_payable_line": self.source.pk}
        url = reverse("vouchers:case_action", args=[case.public_id, "validate-accounting"])
        response = self.client.post(url, data, follow=True)
        self.assertContains(response, "on or after the requested date")
        case.refresh_from_db()
        self.assertEqual((case.current_stage, case.state_version), (stage, version))
        self.assertFalse(case.accounting_validations.exists())
        self.assertFalse(case.posting_requests.exists())
        held.refresh_from_db()
        self.assertEqual((held.pk, held.source_snapshot, held.source_checksum), retained)
        self.assertIsNone(held.released_at)
        data.update(jev_date="2026-08-29", idempotency_key="retry-later")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(case.accounting_validations.count(), 1)
        self.assertEqual(PayableClaimReservation.objects.filter(case_public_id=case.public_id).count(), 1)
        self.pay(case, suffix="-recovered-date")
        exported = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertIn(b"1500.00,1000.00,500.00", exported.content)
        self.assertEqual(exported["X-GRAND-Export-Archived"], "true")

    def test_overreservation_manual_application_and_invalid_payee_are_blocked(self):
        first = self.case_for_validation("-one")
        self.validate(first)
        second = self.case_for_validation("-two")
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            self.validate(second)
        manual = JournalEntry.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="UNRESERVED", entry_date=date(2026, 8, 26), period=self.accounting_period, fund=self.accounting_fund,
            description="Attempt to consume held claim", created_by_id=self.preparer.pk, created_by_label="Maker")
        JournalLine.objects.create(entry=manual, sequence=1, account=self.payable_account, debit=600, payable_origin=self.source)
        JournalLine.objects.create(entry=manual, sequence=2, account=self.expense_account, credit=600)
        submit_entry(manual, self.preparer)
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            post_entry(manual, self.validator)
        with self.assertRaises(PermissionDenied):
            self.validate(second, actor=self.outsider)

    def test_form_scopes_claim_and_invalid_rule_cannot_duplicate_recognition(self):
        case = self.case_for_validation()
        form = AccountingValidationForm(case=case)
        self.assertFalse(form.fields["jev_number"].required)
        self.assertEqual(list(form.fields["prior_payable_line"].queryset), [self.source])
        Line.objects.filter(rule=self.payment_rule, side=Line.DEBIT).update(account_source=Line.ALLOCATION_ACCOUNTS,
            amount_source=Line.EACH_ALLOCATION)
        with self.assertRaises(ValidationError):
            self.validate(case)
        self.assertFalse(PayableClaimReservation.objects.exists())

    def test_finance_draft_survives_interrupted_core_link_and_recovers_once(self):
        case = self.case_for_validation(deductions=True)
        self.validate(case)
        request = case.posting_requests.get(kind=Rule.ADJUSTMENT)
        update = QuerySet.update

        def interrupted(queryset, **kwargs):
            if queryset.model is VoucherPostingRequest and kwargs.get("status") == VoucherPostingRequest.MATERIALIZED:
                raise RuntimeError("Simulated default-store link failure")
            return update(queryset, **kwargs)

        with patch.object(QuerySet, "update", interrupted):
            with self.assertRaises(RuntimeError):
                materialize_voucher_journal(request, self.preparer)
        self.assertEqual(JournalEntry.objects.filter(source_reference=str(request.public_id)).count(), 1)
        case.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "reservation has journal applications"):
            return_case(case=case, actor=self.validator, target_stage=VoucherCase.ACCOUNTING_VALIDATION,
                reason="Interrupted core link must not free a Finance draft's claim",
                expected_version=case.state_version, idempotency_key="interrupted-return")
        recovered, created = materialize_voucher_journal(request, self.preparer)
        self.assertFalse(created)
        self.assertEqual(recovered.lines.get(account=self.payable_account).payable_origin_id, self.source.pk)
        case.refresh_from_db()
        with self.assertRaises(ValidationError):
            return_case(case=case, actor=self.validator, target_stage=VoucherCase.ACCOUNTING_VALIDATION,
                reason="Cannot free a claim with a retained draft", expected_version=case.state_version, idempotency_key="blocked-return")
        self.assertEqual(_capacity(self.source), Decimal("500"))

    def test_issuance_payment_cancellation_and_replacement_restore_same_hold(self):
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
        case = self.case_for_validation()
        self.validate(case)
        case.refresh_from_db()
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="PRIOR-ISSUANCE", amount=1000, expected_version=case.state_version, idempotency_key="issue")
        payment = self.post_request(case.posting_requests.get(kind=Rule.PAYMENT))
        case.refresh_from_db()
        cancel_check(case=case, instrument=instrument, actor=self.treasury_user, reason="Spoiled check before release",
            expected_version=case.state_version, idempotency_key="cancel")
        cancellation = self.post_request(case.posting_requests.get(kind=Rule.CANCELLATION))
        self.assertEqual(cancellation.reversal_of_id, payment.pk)
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("1500"))
        self.assertEqual(_capacity(self.source), Decimal("500"))
        case.refresh_from_db(); instrument.refresh_from_db()
        issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="PRIOR-REPLACEMENT", amount=1000, replaces=instrument,
            expected_version=case.state_version, idempotency_key="replace")
        self.post_request(case.posting_requests.get(kind=Rule.REPLACEMENT))
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("500"))
        self.assertEqual(PayableClaimReservation.objects.count(), 1)

    def test_http_validation_and_uat_denial(self):
        from .roles import FINANCE_UAT_VIEWER_GROUP
        case = self.case_for_validation()
        url = reverse("vouchers:case_action", args=[case.public_id, "validate-accounting"])
        data = {"state_version": case.state_version, "idempotency_key": "http-validation",
            "jev_number": "", "jev_date": "2026-08-25", "note": "Selected original invoice",
            "prior_payable_line": self.source.pk}
        self.validator.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.validator)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PayableClaimReservation.objects.exists())
        self.validator.groups.clear()
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label="vouchers", codename="validate_accounting_voucher"))
        VoucherCase.objects.filter(pk=case.pk).update(current_department=self.requesting)
        case.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            self.validate(case, actor=self.outsider)
        self.assertFalse(PayableClaimReservation.objects.exists())
        VoucherCase.objects.filter(pk=case.pk).update(current_department=self.accounting)
        case.refresh_from_db()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)
        self.assertFalse(case.posting_requests.exists())
