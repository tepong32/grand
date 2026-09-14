"""A reviewed bank return must support a coherent corrected advance source cycle."""
from datetime import date, timedelta
from unittest.mock import patch
from django.utils import timezone
from . import test_advance_recognition_corrections as fixtures
from .models import TreasuryCashPolicy, PaymentInstrumentException, ReturnedInstrumentReview as Review
from .cash_positions import open_instrument_exception
from .advice import decide_returned_instrument


class ReturnedAdvanceCorrectionTests(fixtures.AdvanceRecognitionCorrectionTests):
    def test_withdrawn_original_correction_preserves_reviewed_replacement_route(self):
        from django.core.exceptions import ValidationError
        from accounting.models import JournalSubsidiaryLine
        from accounting.services import discard_draft
        from .advance_recognition_corrections import prepare, withdraw
        from .posting import materialize_voucher_journal
        from .models import VoucherPostingRequest as Request
        from .services import issue_check
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        self.before_original_correction(case)
        detail = JournalSubsidiaryLine.objects.get(
            entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        request = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
            reason='Review original correction proposal', key='WITHDRAW-RETURN')
        entry, _ = materialize_voucher_journal(request, self.preparer)
        with self.assertRaises(ValidationError):
            withdraw(request, self.validator, 'Draft still active')
        discard_draft(entry, self.preparer, 'Discard original correction draft')
        withdraw(request, self.validator, 'Independent decision to retain original and replace check')
        self.review.refresh_from_db(); case.refresh_from_db(); request.refresh_from_db()
        self.assertEqual(request.status, Request.CANCELLED)
        self.assertEqual(self.review.status, Review.READY_FOR_TREASURY)
        self.assertEqual(self.review.exception.status, PaymentInstrumentException.OPEN)
        self.assertFalse(case.events.filter(action='advance_return_retired').exists())
        replacement = issue_check(case=case, actor=self.treasury_user, bank_account_code='gf-lbp',
            fund_code='general-fund', check_number='ADV-WITHDRAW-REPLACEMENT', amount='1000', replaces=self.returned,
            expected_version=case.state_version, idempotency_key='withdrawn-correction-replacement')
        self.assertEqual(replacement.replaces_id, self.returned.pk)

    def authoritative_payable_for_review(self):
        result = super().authoritative_payable_for_review()
        if getattr(self, 'issuance', False):
            from finance.models import FinancePostingRule as Rule
            Rule.objects.filter(pk=result[1].pk).update(recognition_point=Rule.PAYMENT_ISSUANCE)
        return result

    def pay(self, case, suffix='', replaces=None):
        if not getattr(self, 'issuance', False):
            return super().pay(case, suffix, replaces)
        from .services import issue_check, submit_checks_for_advice, finalize_bank_advice, release_check
        from .models import VoucherPostingRequest as Request
        case.refresh_from_db()
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code='gf-lbp',
            fund_code='general-fund', check_number='ADV-ISSUANCE'+suffix,
            amount=case.disbursement_voucher.net_amount, replaces=replaces,
            expected_version=case.state_version, idempotency_key='issue'+suffix)
        entry = self.post_request(case.posting_requests.get(kind=Request.PAYMENT,
            trigger_key=f'payment-instrument:{instrument.public_id}:issued'))
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user,
            expected_version=case.state_version, idempotency_key='advice'+suffix)
        case.refresh_from_db()
        batch = finalize_bank_advice(case=case, actor=self.preparer, advice_number='ADV-ADVICE'+suffix,
            advice_date=timezone.localdate(), expected_version=case.state_version, idempotency_key='finalize'+suffix,
            preparation_note='Synthetic issuance review', authority_reference='Synthetic approved procedure',
            local_applicability_note='Synthetic')
        self.acknowledge_advice(batch)
        case.refresh_from_db(); instrument.refresh_from_db()
        release_check(case=case, instrument=instrument, actor=self.treasury_user, claimant=self.claimant,
            receipt_reference='ADV-RECEIPT'+suffix, expected_version=case.state_version, idempotency_key='release'+suffix)
        return instrument, entry

    def test_returned_advance_at_issuance_reaches_corrected_budget_and_payment(self):
        self.issuance = True
        self.test_bank_returned_advance_reaches_corrected_budget_and_payment()

    def test_issuance_advance_retains_corrected_liquidation_refund_and_deposit(self):
        self.issuance = True
        self.correct_expenses_before_return = True
        self.test_corrected_refund_and_deposit_survive_original_correction_and_new_payment()
        correction = self.review.case.posting_requests.get(payload__has_key='advance_recognition_correction')
        data = correction.payload['advance_recognition_correction']
        self.assertEqual(len(data['settled_applications']), 1)
        self.assertEqual(len(data['settled_refunds']), 1)

    def assert_retained_fund_identity(self, correction, entry_ids):
        from django.core.exceptions import ValidationError
        from accounting.models import Fund, JournalEntry
        from .advance_recognition_corrections import validate
        entries = JournalEntry.objects.filter(public_id__in=entry_ids)
        funds = set(entries.values_list('fund_id', flat=True))
        self.assertEqual(len(funds), 1)
        original_fund = funds.pop()
        other = Fund.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            code='OTHER-RETAINED-FUND', name='Synthetic different fund')
        try:
            entries.update(fund=other)
            with self.assertRaises(ValidationError):
                validate(JournalEntry.objects.get(public_id=correction.accounting_entry_public_id))
        finally:
            entries.update(fund_id=original_fund)
        validate(JournalEntry.objects.get(public_id=correction.accounting_entry_public_id))

    def test_refund_correction_must_be_posted_by_original_correction_date(self):
        from django.core.exceptions import ValidationError
        from accounting.models import JournalSubsidiaryLine
        from .advance_recognition_corrections import prepare
        from .models import VoucherPostingRequest as Request
        from .collection_corrections import propose
        from . import test_advance_refunds as refund_fixtures
        earlier = timezone.now() - timedelta(days=1)
        self.correct_refund_before_return = True
        self.defer_refund_correction = True
        with patch('django.utils.timezone.now', return_value=earlier):
            self.enable_payment_event_rules('op_suppliers')
            case = self.ready_for_treasury()
            self.before_original_correction(case)
        detail = JournalSubsidiaryLine.objects.get(
            entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        with self.assertRaisesMessage(ValidationError, 'linked advance liquidation/refund'):
            prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
                reason='Outstanding actual refund prevents original correction', key='REFUND-OUTSTANDING')
        for source in (self.refund_deposit, self.refund_source):
            fix = propose(original=source, actor=self.treasury_user, corrected_on=timezone.localdate(),
                reason='Actual later deposit and refund corrections')
            refund_fixtures.AdvanceRefundTests.post_refund_source(self, fix)
        with self.assertRaisesMessage(ValidationError, 'linked advance liquidation/refund'):
            prepare(detail=detail, actor=self.preparer, day=timezone.localdate(earlier),
                reason='Cannot backdate original correction before actual refund correction', key='REFUND-EARLY')
        correction = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
            reason='Original correction after actual refund restoration', key='REFUND-CURRENT')
        self.post_request(correction)
        correction.refresh_from_db()
        self.assertEqual(correction.status, Request.POSTED)

    def test_corrected_refund_and_deposit_survive_original_correction_and_new_payment(self):
        from django.core.exceptions import ValidationError
        from .advance_recognition_corrections import validate
        from accounting.models import JournalEntry
        self.correct_refund_before_return = True
        self.test_bank_returned_advance_reaches_corrected_budget_and_payment()
        correction = self.review.case.posting_requests.get(payload__has_key='advance_recognition_correction')
        history = correction.payload['advance_recognition_correction']['settled_refunds']
        self.assertEqual(history[0]['receipt']['original']['source'], str(self.refund_source.public_id))
        self.assertEqual(history[0]['deposits'][0]['original']['source'], str(self.refund_deposit.public_id))
        entry = JournalEntry.objects.get(public_id=correction.accounting_entry_public_id)
        source_type = type(self.refund_deposit)
        source_type.objects.filter(pk=self.refund_deposit.pk).update(review_reason='Changed retained deposit decision')
        with self.assertRaises(ValidationError):
            validate(entry)
        source_type.objects.filter(pk=self.refund_deposit.pk).update(review_reason=self.refund_deposit.review_reason)
        validate(entry)
        self.assert_retained_fund_identity(correction, [
            part['journal']['entry'] for pair in [history[0]['receipt'], *history[0]['deposits']]
            for part in (pair['original'], pair['correction'])])

    def test_corrected_liquidation_survives_original_correction_and_new_payment(self):
        from django.core.exceptions import ValidationError
        from .advance_recognition_corrections import validate
        from .models import VoucherPostingRequest as Request
        from accounting.models import JournalEntry
        self.correct_expenses_before_return = True
        self.test_bank_returned_advance_reaches_corrected_budget_and_payment()
        correction = self.review.case.posting_requests.get(payload__has_key='advance_recognition_correction')
        history = correction.payload['advance_recognition_correction']['settled_applications']
        self.assertEqual(history[0]['application']['entry'], str(self.expense_entry.public_id))
        self.assertEqual(history[0]['correction']['entry'], str(self.expense_correction_entry.public_id))
        self.expense_application.refresh_from_db()
        self.assertEqual(self.expense_application.status, Request.POSTED)
        entry = JournalEntry.objects.get(public_id=correction.accounting_entry_public_id)
        detail = self.expense_entry.subsidiary_lines.get()
        self.expense_entry.subsidiary_lines.filter(pk=detail.pk).update(reference_label='Changed retained officer')
        with self.assertRaisesMessage(ValidationError, 'corrected liquidation history changed'):
            validate(entry)
        self.expense_entry.subsidiary_lines.filter(pk=detail.pk).update(reference_label=detail.reference_label)
        validate(entry)
        self.assert_retained_fund_identity(correction,
            [self.expense_entry.public_id, self.expense_correction_entry.public_id])

    def test_later_liquidation_correction_cannot_enable_earlier_original_correction(self):
        from django.core.exceptions import ValidationError
        from accounting.models import JournalSubsidiaryLine
        from .advance_applications import prepare as prepare_expenses
        from .liquidation_corrections import prepare as correct_expenses
        from .advance_recognition_corrections import prepare
        from .models import VoucherPostingRequest as Request
        earlier = timezone.now() - timedelta(days=1)
        with patch('django.utils.timezone.now', return_value=earlier):
            self.enable_payment_event_rules('op_suppliers')
            case = self.ready_for_treasury()
            self.prepare_released_advance(case)
            detail = JournalSubsidiaryLine.objects.get(
                entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
                category=JournalSubsidiaryLine.ADVANCE)
            application = prepare_expenses(detail=detail, actor=self.preparer, rule=self.liquidation_rule(),
                day=timezone.localdate(), expenses=[{'account_code': '5-02-03', 'amount': '100',
                    'document_reference': 'DATED-EXPENSE'}], evidence_reference='Retained dated expense', key='DATED-HISTORY')
            self.post_request(application)
            self.review_bank_return(case)
        fix = correct_expenses(application=application, actor=self.preparer, day=timezone.localdate(),
            reason='Expense corrected on its actual later date', key='DATED-HISTORY')
        self.post_request(fix)
        with self.assertRaisesMessage(ValidationError, 'linked advance liquidation/refund'):
            prepare(detail=detail, actor=self.preparer, day=timezone.localdate(earlier),
                reason='Cannot backdate original correction before expense restoration', key='TOO-EARLY')
        correction = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
            reason='Correct original after actual expense restoration', key='ACTUAL-DATE')
        self.post_request(correction)
        correction.refresh_from_db()
        self.assertEqual(correction.status, Request.POSTED)

    def test_posted_liquidation_blocks_original_returned_advance_correction(self):
        from django.core.exceptions import ValidationError
        from accounting.models import JournalSubsidiaryLine
        from .advance_recognition_corrections import prepare
        from .advance_applications import prepare as prepare_expenses
        from .models import VoucherPostingRequest as Request
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        self.prepare_released_advance(case)
        detail = JournalSubsidiaryLine.objects.get(
            entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        application = prepare_expenses(detail=detail, actor=self.preparer, rule=self.liquidation_rule(),
            day=timezone.localdate(), expenses=[{'account_code': '5-02-03', 'amount': '100',
                'document_reference': 'RETAINED-EXPENSE'}], evidence_reference='Independent expense evidence', key='USED-ADVANCE')
        expense_entry = self.post_request(application)
        self.review_bank_return(case)
        with self.assertRaisesMessage(ValidationError, 'linked advance liquidation/refund'):
            prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
                reason='Cannot erase accepted expenses', key='USED-RETURN')
        application.refresh_from_db(); expense_entry.refresh_from_db()
        self.assertEqual(application.status, Request.POSTED)
        self.assertEqual(expense_entry.status, expense_entry.POSTED)
        self.assertFalse(case.posting_requests.filter(payload__has_key='advance_recognition_correction').exists())

    def test_return_retirement_rolls_back_and_recovers_after_finance_posting(self):
        from django.core.exceptions import ValidationError
        from accounting.models import JournalSubsidiaryLine
        from accounting.services import submit_entry, post_entry
        from .advance_recognition_corrections import prepare, validate
        from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
        from .models import VoucherPostingRequest as Request, VoucherCase
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        self.before_original_correction(case)
        detail = JournalSubsidiaryLine.objects.get(
            entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        correction = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
            reason='Correct returned advance recognition', key='RETURN-RECOVERY')
        entry, _ = materialize_voucher_journal(correction, self.preparer)
        submit_entry(entry, self.preparer)
        post_entry(entry, self.validator)
        with patch('vouchers.cash_positions.resolve_instrument_exception', side_effect=RuntimeError('Synthetic closure interruption')):
            with self.assertRaisesMessage(RuntimeError, 'Synthetic closure interruption'):
                reconcile_posted_voucher_entry(entry, self.validator)
        correction.refresh_from_db(); self.review.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(correction.status, Request.MATERIALIZED)
        self.assertEqual(self.review.status, Review.READY_FOR_TREASURY)
        self.assertEqual(self.review.exception.status, PaymentInstrumentException.OPEN)
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_EVENT_POSTING)
        self.assertFalse(case.events.filter(action='advance_return_retired').exists())
        reconcile_posted_voucher_entry(entry, self.validator)
        reconcile_posted_voucher_entry(entry, self.validator)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.CLOSED)
        self.assertEqual(case.events.filter(action='advance_return_retired').count(), 1)
        validate(entry)
        retained_version = self.review.state_version
        Review.objects.filter(pk=self.review.pk).update(state_version=retained_version + 1)
        with self.assertRaisesMessage(ValidationError, 'retired this return authorization'):
            validate(entry)
        Review.objects.filter(pk=self.review.pk).update(state_version=retained_version)
        validate(entry)

    def test_return_withholding_begins_on_observed_date(self):
        from accounting.models import JournalSubsidiaryLine
        from .advance_sources import disbursement
        from .models import VoucherPostingRequest as Request
        released_at = timezone.now() - timedelta(days=2)
        with patch('django.utils.timezone.now', return_value=released_at):
            self.enable_payment_event_rules('op_suppliers')
            case = self.ready_for_treasury()
            self.prepare_released_advance(case)
        self.review_bank_return(case)
        detail = JournalSubsidiaryLine.objects.get(
            entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        for day in (timezone.localdate(released_at), timezone.localdate() - timedelta(days=1)):
            proof = disbursement(detail, day)
            self.assertEqual(proof['released_net'], self.returned.amount)
            self.assertEqual(proof['withheld_returns'], 0)
            self.assertEqual(proof['sources'][0]['returns'], [])
        proof = disbursement(detail, timezone.localdate())
        self.assertEqual(proof['released_net'], 0)
        self.assertEqual(proof['withheld_returns'], self.returned.amount)
        self.assertEqual(proof['sources'][0]['returns'][0]['observed_on'], timezone.localdate().isoformat())

    def test_reviewed_advance_bank_return_retains_payment_and_cash_flow_lineage(self):
        from django.core.exceptions import ValidationError
        from .advance_payment_cancellations import validate
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        self.before_original_correction(case)
        self.assertEqual(self.return_entry.reversal_of_id, self.original_payment.pk)
        self.assertEqual(self.return_entry.source_snapshot['advance_payment_return']['original_entry'], str(self.original_payment.public_id))
        original_purposes = list(self.original_payment.lines.order_by('sequence').values_list('cash_flow_category', flat=True))
        self.assertEqual(list(self.return_entry.lines.order_by('sequence').values_list('cash_flow_category', flat=True)), original_purposes)
        from accounting.models import JournalSubsidiaryLine
        from .advance_sources import disbursement
        from .models import VoucherPostingRequest as Request
        detail = JournalSubsidiaryLine.objects.get(entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        proof = disbursement(detail, timezone.localdate())
        self.assertEqual(proof['released_net'], 0)
        self.assertEqual(proof['sources'][0]['return_posting']['entry'], str(self.return_entry.public_id))
        PaymentInstrumentException.objects.filter(pk=self.review.exception_id).update(kind=PaymentInstrumentException.STALE)
        with self.assertRaisesMessage(ValidationError, 'bank-return review'):
            disbursement(detail, timezone.localdate())
        PaymentInstrumentException.objects.filter(pk=self.review.exception_id).update(kind=PaymentInstrumentException.RETURNED)
        line = self.return_entry.lines.exclude(cash_flow_category='').get()
        self.return_entry.lines.filter(pk=line.pk).update(cash_flow_category='')
        with self.assertRaisesMessage(ValidationError, 'cash-flow purpose'):
            validate(self.return_entry)
        self.return_entry.lines.filter(pk=line.pk).update(cash_flow_category=line.cash_flow_category)
        validate(self.return_entry)

    def before_original_correction(self, case):
        self.prepare_released_advance(case)
        if getattr(self, 'correct_refund_before_return', False):
            from . import test_advance_refunds as refund_fixtures
            from accounting.models import JournalSubsidiaryLine
            from finance.models import FinanceConfigurationItem
            from .models import VoucherPostingRequest as Request
            from .collections import record_deposit
            refund_fixtures.AdvanceRefundTests.configure_refund_rules(self)
            detail = JournalSubsidiaryLine.objects.get(
                entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
                category=JournalSubsidiaryLine.ADVANCE)
            self.refund_source = refund_fixtures.AdvanceRefundTests.capture_refund(self, detail)
            refund_fixtures.AdvanceRefundTests.post_refund_source(self, self.refund_source)
            bank = FinanceConfigurationItem.objects.get(release=self.release, category='bank_account', code='gf-lbp')
            self.refund_deposit = record_deposit(actor=self.treasury_user, variant=self.transaction_variant,
                deposited_on=timezone.localdate(), fund_code='general-fund', deposit_reference='RETURNED-ADVANCE-REFUND',
                receiving_bank_id=bank.public_id, allocations=[{'receipt': str(self.refund_source.public_id), 'amount': '400'}],
                evidence_reference='Actual officer refund deposited')
            refund_fixtures.AdvanceRefundTests.post_refund_source(self, self.refund_deposit)
        if getattr(self, 'correct_expenses_before_return', False):
            from accounting.models import JournalSubsidiaryLine
            from .models import VoucherPostingRequest as Request
            from .advance_applications import prepare
            detail = JournalSubsidiaryLine.objects.get(
                entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
                category=JournalSubsidiaryLine.ADVANCE)
            self.expense_application = prepare(detail=detail, actor=self.preparer, rule=self.liquidation_rule(),
                day=timezone.localdate(), expenses=[{'account_code': '5-02-03', 'amount': '100',
                    'document_reference': 'CORRECTED-EXPENSE'}], evidence_reference='Retained expense evidence', key='CORRECTED-HISTORY')
            self.expense_entry = self.post_request(self.expense_application)
        self.review_bank_return(case)
        if getattr(self, 'correct_refund_before_return', False) and not getattr(self, 'defer_refund_correction', False):
            from .collection_corrections import propose
            from . import test_advance_refunds as refund_fixtures
            for source in (self.refund_deposit, self.refund_source):
                fix = propose(original=source, actor=self.treasury_user, corrected_on=timezone.localdate(),
                    reason='Correct the actual refund source before original advance correction')
                refund_fixtures.AdvanceRefundTests.post_refund_source(self, fix)
        if getattr(self, 'correct_expenses_before_return', False):
            from .liquidation_corrections import prepare
            fix = prepare(application=self.expense_application, actor=self.preparer, day=timezone.localdate(),
                reason='Correct the accepted expense before correcting its original advance', key='CORRECTED-HISTORY')
            self.expense_correction_entry = self.post_request(fix)
        return 'check'

    def prepare_released_advance(self, case):
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code='gf-lbp', fund_code='general-fund', mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=0, position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=date(2026, 1, 1), authority_reference='Synthetic reviewed procedure',
            local_applicability_note='Synthetic', status=TreasuryCashPolicy.ACTIVE,
            created_by=self.treasury_user, submitted_by=self.treasury_user, submitted_at=timezone.now(),
            approved_by=self.validator, approved_at=timezone.now())
        self.returned, self.original_payment = self.pay(case, '-BEFORE-RETURN')
        self.returned.refresh_from_db()

    def review_bank_return(self, case):
        exception = open_instrument_exception(instrument=self.returned, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(),
            reason='Bank returned the advance check unpaid', evidence_reference='Synthetic bank return evidence')
        self.review = exception.accounting_reviews.get()
        decide_returned_instrument(review=self.review, actor=self.validator, approve=True, outcome=Review.REISSUE,
            decision_reason='Independently reverse the unpaid instrument', evidence_reference='Synthetic independent return review',
            expected_version=self.review.state_version)
        self.review.refresh_from_db()
        self.return_entry = self.post_request(self.review.posting_request)
        case.refresh_from_db()

    def test_bank_returned_advance_reaches_corrected_budget_and_payment(self):
        super().test_budget_amount_correction_to_new_recognition_actual_payment_and_output()
        self.assertEqual(self.return_entry.reversal_of_id, self.original_payment.pk)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, Review.CLOSED)
        self.assertEqual(self.review.exception.status, PaymentInstrumentException.RESOLVED)
