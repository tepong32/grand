"""An actual cancelled advance must reach corrected Budget, DV and payment."""
from django.utils import timezone
from . import test_advance_recognition_corrections as fixtures
from .models import VoucherPostingRequest as Request, PaymentInstrument
from .services import issue_check, cancel_check


class CancelledAdvanceCorrectionTests(fixtures.AdvanceRecognitionCorrectionTests):
    def test_cancelled_evidence_is_dated_pinned_and_not_retired_before_posting(self):
        from datetime import timedelta
        from django.core.exceptions import ValidationError
        from accounting.models import JournalSubsidiaryLine
        from .advance_recognition_corrections import prepare, validate
        from .cancelled_corrections import retired_instruments
        from .posting import materialize_voucher_journal
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        self.before_original_correction(case)
        detail = JournalSubsidiaryLine.objects.get(entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        with self.assertRaisesMessage(ValidationError, 'cannot predate'):
            prepare(detail=detail, actor=self.preparer, day=timezone.localdate()-timedelta(days=1), reason='Earlier date rejected', key='too-early')
        request = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(), reason='Retained cancellation evidence', key='pinned')
        entry, _ = materialize_voucher_journal(request, self.preparer)
        self.assertNotIn(str(self.cancelled.public_id), retired_instruments(case))
        original_reason = self.cancelled.cancellation_reason
        PaymentInstrument.objects.filter(pk=self.cancelled.pk).update(cancellation_reason='Changed retained evidence')
        with self.assertRaisesMessage(ValidationError, 'exact cancelled'):
            validate(entry)
        PaymentInstrument.objects.filter(pk=self.cancelled.pk).update(cancellation_reason=original_reason)
        self.post_request(request)
        self.assertIn(str(self.cancelled.public_id), retired_instruments(case))

    def authoritative_payable_for_review(self):
        result = super().authoritative_payable_for_review()
        if getattr(self, 'issuance', False):
            from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
            Rule.objects.filter(pk=result[1].pk).update(recognition_point=Rule.PAYMENT_ISSUANCE)
            rule = Rule.objects.get(variant=self.transaction_variant, event_kind=Rule.CANCELLATION)
            Rule.objects.filter(pk=rule.pk).update(accounting_effect=Rule.JOURNAL_ENTRY)
            Line.objects.bulk_create([
                Line(rule=rule, sequence=1, label='Restore original payable', side=Line.CREDIT,
                    account_source=Line.PAYABLE_MAPPING, amount_source=Line.EVENT_AMOUNT),
                Line(rule=rule, sequence=2, label='Reverse original bank payment', side=Line.DEBIT,
                    account_source=Line.BANK_MAPPING, amount_source=Line.EVENT_AMOUNT, cash_flow_category='op_suppliers')])
        return result

    def before_original_correction(self, case):
        case.refresh_from_db()
        self.cancelled = issue_check(case=case, actor=self.treasury_user,
            bank_account_code='gf-lbp', fund_code='general-fund', check_number='ADV-OLD-CANCELLED',
            amount='1000', expected_version=case.state_version, idempotency_key='advance-before-correction')
        if getattr(self, 'issuance', False):
            self.original_payment = self.post_request(case.posting_requests.get(kind=Request.PAYMENT))
        case.refresh_from_db()
        cancel_check(case=case, instrument=self.cancelled, actor=self.treasury_user,
            reason='Incorrect advance amount before actual release', expected_version=case.state_version,
            idempotency_key='cancel-advance-before-correction')
        if getattr(self, 'issuance', False):
            cancellation = self.post_request(case.posting_requests.get(kind=Request.CANCELLATION))
            self.assertEqual(cancellation.reversal_of_id, self.original_payment.pk)
        case.refresh_from_db(); self.cancelled.refresh_from_db()
        self.assertEqual(self.cancelled.status, PaymentInstrument.CANCELLED)
        self.assertIsNone(self.cancelled.released_at)
        self.assertEqual(case.posting_requests.get(kind=Request.CANCELLATION).status,
            Request.POSTED if getattr(self, 'issuance', False) else Request.NOT_REQUIRED)
        if getattr(self, 'print_corrected', False):
            self.template.controlled_print_required = True
            self.template.save(update_fields=('controlled_print_required',))
            from django.urls import reverse
            from accounting.models import JournalSubsidiaryLine
            source = JournalSubsidiaryLine.objects.get(entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
                category=JournalSubsidiaryLine.ADVANCE)
            self.assertContains(self.client.get(reverse('accounting:advance_detail', args=[source.pk])), 'Correct original unpaid advance')
        return 'check'

    def test_cancelled_advance_reaches_revised_budget_and_actual_payment(self):
        super().test_budget_amount_correction_to_new_recognition_actual_payment_and_output()
        from .cancelled_corrections import retired_instruments
        from .forms import CheckIssueForm
        self.assertIn(str(self.cancelled.public_id), retired_instruments(self.cancelled.case))
        self.assertFalse(CheckIssueForm(case=self.cancelled.case).fields['replaces'].queryset.filter(pk=self.cancelled.pk).exists())

    def test_cancelled_advance_reaches_revised_budget_and_actual_payment_at_issuance(self):
        self.issuance = True
        self.test_cancelled_advance_reaches_revised_budget_and_actual_payment()

    def test_corrected_advance_signing_copy_and_packet_reach_payment(self):
        self.print_corrected = True
        self.issuance = True
        self.test_cancelled_advance_reaches_revised_budget_and_actual_payment()

    def return_signatures(self, case):
        if getattr(self, 'print_corrected', False) and hasattr(self, 'cancelled'):
            from .case_exports import dv_print_preparation_queryset
            from .services import prepare_controlled_dv_print, record_dv_printed, assemble_finance_packet
            from tracepoint.models import TrackedPacket
            case.refresh_from_db()
            self.assertTrue(dv_print_preparation_queryset(self.preparer).filter(pk=case.pk).exists())
            job = prepare_controlled_dv_print(case=case, actor=self.preparer, replacement_reason='',
                expected_version=case.state_version, idempotency_key='corrected-advance-copy')
            self.assertTrue(job.output.file.name)
            case.refresh_from_db()
            record_dv_printed(case=case, actor=self.preparer, copy_count=1, printer_or_form_stock='Synthetic printer',
                print_note='Synthetic corrected advance copy', expected_version=case.state_version, idempotency_key='corrected-advance-printed')
            case.refresh_from_db()
            assemble_finance_packet(case=case, actor=self.preparer, expected_document_count=2, expected_page_count=4,
                confidentiality=TrackedPacket.RESTRICTED, assembly_note='Synthetic corrected advance packet',
                expected_version=case.state_version, idempotency_key='corrected-advance-packet')
        return super().return_signatures(case)

    def pay(self, case, suffix='', replaces=None):
        if not getattr(self, 'issuance', False):
            return super().pay(case, suffix, replaces)
        from .services import submit_checks_for_advice, finalize_bank_advice, release_check
        case.refresh_from_db()
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code='gf-lbp',
            fund_code='general-fund', check_number='ADV-NEW-ISSUANCE', amount=case.disbursement_voucher.net_amount,
            expected_version=case.state_version, idempotency_key='new-advance-issuance')
        entry = self.post_request(case.posting_requests.get(kind=Request.PAYMENT,
            trigger_key=f'payment-instrument:{instrument.public_id}:issued'))
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user, expected_version=case.state_version, idempotency_key='new-advice')
        case.refresh_from_db()
        batch = finalize_bank_advice(case=case, actor=self.preparer, advice_number='ADV-NEW-ADVICE', advice_date=timezone.localdate(),
            expected_version=case.state_version, idempotency_key='new-finalize', preparation_note='Synthetic reviewed replacement',
            authority_reference='Synthetic approved practice', local_applicability_note='Synthetic')
        self.acknowledge_advice(batch)
        case.refresh_from_db(); instrument.refresh_from_db()
        release_check(case=case, instrument=instrument, actor=self.treasury_user, claimant=self.claimant,
            receipt_reference='ADV-NEW-RECEIPT', expected_version=case.state_version, idempotency_key='new-release')
        return instrument, entry
