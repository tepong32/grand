"""Original advance correction acceptance, using disposable two-store fixtures."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounting.models import JournalEntry, JournalSubsidiaryLine
from accounting.services import subsidiary_schedule_rows
from . import test_advances as fixtures, tests as workflow, test_prior_payables as payment_fixtures
from .models import VoucherCase, VoucherPostingRequest
from .services import return_case


class AdvanceRecognitionCorrectionTests(fixtures.AdvanceRecognitionTests):
    authoritative_payable_for_review = workflow.VoucherWorkflowTests.authoritative_payable_for_review
    post_request = payment_fixtures.PriorPayableDVTests.post_request
    pay = payment_fixtures.PriorPayableDVTests.pay

    def test_web_permissions_exact_mirror_and_independent_withdrawal(self):
        import uuid
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group, Permission
        from accounting.models import JournalLine
        from accounting.services import submit_entry, post_entry, discard_draft
        from .advance_recognition_corrections import withdraw
        from .roles import FINANCE_UAT_VIEWER_GROUP
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        original = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        detail = JournalSubsidiaryLine.objects.get(entry__public_id=original.accounting_entry_public_id, category='advance')
        self.preparer.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=('view_officer_advances','post_journal_entries')))
        self.client.force_login(self.preparer)
        url = reverse('accounting:advance_recognition_correct', args=[detail.pk])
        self.assertContains(self.client.get(url), 'Correct original unpaid advance')
        invalid = self.client.post(url, {'day':'2026-08-01', 'reason':'Retained invalid correction date', 'key':str(uuid.uuid4())})
        self.assertContains(invalid, 'Retained invalid correction date')
        response = self.client.post(url, {'day':timezone.localdate().isoformat(), 'reason':'Synthetic source error', 'key':str(uuid.uuid4())})
        self.assertEqual(response.status_code, 302)
        request = case.posting_requests.get(kind=VoucherPostingRequest.REVERSAL)
        self.assertNotContains(self.client.get(reverse('accounting:advance_detail', args=[detail.pk])), 'Prepare expense liquidation')
        entry = JournalEntry.objects.get(public_id=request.accounting_entry_public_id)
        line = entry.lines.get(credit__gt=0)
        JournalLine.objects.filter(pk=line.pk).update(account=self.expense_account)
        with self.assertRaisesMessage(ValidationError, 'exactly mirror'):
            submit_entry(entry, self.preparer)
        JournalLine.objects.filter(pk=line.pk).update(account_id=line.account_id)
        submit_entry(entry, self.preparer)
        with self.assertRaisesMessage(ValidationError, 'independent Accounting'):
            post_entry(entry, get_user_model().objects.get(pk=self.preparer.pk))
        from accounting.services import return_entry
        return_entry(entry, self.validator, 'Withdraw incorrect unposted proposal')
        discard_draft(entry, self.preparer, 'Discard before independent withdrawal')
        with self.assertRaises(ValidationError):
            withdraw(request, get_user_model().objects.get(pk=self.preparer.pk), 'Cannot approve own withdrawal')
        withdraw(request, self.validator, 'Independently confirmed every draft discarded')
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'day':timezone.localdate().isoformat(), 'reason':'Denied', 'key':str(uuid.uuid4())}).status_code, 403)

    def test_budget_amount_correction_to_new_recognition_actual_payment_and_output(self):
        from django.urls import reverse
        from django.contrib.auth.models import Permission
        from budget.models import ObligationRequest, ObligationRequestLine, PayableObligationAllocation
        from budget.services import transition_obligation_request, downstream_issuance_boundary
        from .models import PayableIntake
        from .services import (review_payable_intake, prepare_voucher, validate_accounting,
            revise_payable_obligation_allocation, revise_payable_claim_control, submit_payable_intake,
            reconcile_authoritative_obligation)
        from .advance_recognition_corrections import prepare
        from .advance_sources import disbursement
        case, payment_rule, obligation, owner = self.authoritative_payable_for_review()

        def review_and_recognize(amount, suffix):
            case.refresh_from_db()
            review_payable_intake(case=case, actor=self.validator, decision=PayableIntake.READY,
                reason='Independent reviewed advance documents', expected_version=case.state_version,
                idempotency_key=f'review-{suffix}')
            case.refresh_from_db()
            prepare_voucher(case=case, actor=self.preparer, voucher_date=timezone.localdate(), gross_amount=Decimal(amount),
                deductions=[], line_description='Synthetic advance for official expenses', line_account_code='5-02-03',
                document_codes=['invoice'], expected_version=case.state_version, idempotency_key=f'dv-{suffix}')
            case.refresh_from_db(); self.return_signatures(case)
            validate_accounting(case=case, actor=self.validator, jev_number=f'ADV-{suffix}', jev_date=timezone.localdate(),
                note='Independent advance recognition', expected_version=case.state_version, idempotency_key=f'validate-{suffix}')
            return self.post_request(case.posting_requests.filter(kind=VoucherPostingRequest.RECOGNITION).latest('pk'))

        original = review_and_recognize('1000', 'ORIGINAL')
        original_request = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        detail = original.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)
        self.preparer.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=('view_officer_advances','export_officer_advances')))
        self.client.force_login(self.preparer)
        archived = self.client.get(reverse('accounting:advance_export')).content
        self.assertEqual(downstream_issuance_boundary(obligation), 'disbursement voucher')
        correction = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
            reason='Original authorized advance amount was overstated', key='BUDGET-AMOUNT')
        from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
        from accounting.services import submit_entry, post_entry
        reversal, _ = materialize_voucher_journal(correction, self.preparer)
        submit_entry(reversal, self.preparer); post_entry(reversal, self.validator)
        self.assertEqual(downstream_issuance_boundary(obligation), 'disbursement voucher')
        reconcile_posted_voucher_entry(reversal, self.validator)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.PAYABLE_PREPARATION)
        self.client.force_login(self.requesting_user)
        self.assertContains(self.client.get(reverse('vouchers:case_detail', args=[case.public_id])), 'Corrected advance payable preparation')
        self.client.force_login(self.preparer)
        self.assertEqual(downstream_issuance_boundary(obligation), '')
        adjustment = ObligationRequest.objects.create(department_id=obligation.department_id,
            department_label=obligation.department_label, authorization=obligation.authorization,
            fiscal_year=obligation.fiscal_year, requesting_department_id=obligation.requesting_department_id,
            requesting_department_label=obligation.requesting_department_label, kind=ObligationRequest.ADJUSTMENT,
            form_type=obligation.form_type, request_reference='ADV-OBR-CORRECTION', obligation_date=timezone.localdate(),
            claimant_payee=obligation.claimant_payee, particulars='Correct overstated unpaid advance',
            evidence_reference='Synthetic independently retained source correction', signed_control_total=Decimal('-200'),
            corrects=obligation, created_by_id=self.requesting_user.pk, created_by_label=self.requesting_user.username)
        ObligationRequestLine.objects.create(department_id=obligation.department_id, department_label=obligation.department_label,
            request=adjustment, appropriation_line=obligation.lines.get().appropriation_line,
            movement_type=ObligationRequestLine.REDUCE, amount=Decimal('200'), remarks='Reduce corrected advance')
        transition_obligation_request(adjustment, 'submit', self.requesting_user)
        transition_obligation_request(adjustment, 'certify', self.budget_user,
            'Independent Budget review of corrected advance and reversal', 'OBR-ADV-CORRECTED')
        allocation = PayableObligationAllocation.objects.get(voucher_case_public_id=case.public_id, status='active')
        revise_payable_obligation_allocation(case=case, allocation_public_id=allocation.public_id, revised_amount=Decimal('800'),
            relationship_type=allocation.relationship_type, reason='Use independently corrected obligation amount',
            actor=self.requesting_user, expected_version=case.state_version, idempotency_key='correct-allocation')
        case.refresh_from_db()
        revise_payable_claim_control(case=case, claim_amount=Decimal('800'), reason='Corrected supported advance amount',
            actor=self.requesting_user, expected_version=case.state_version, idempotency_key='correct-claim')
        case.refresh_from_db()
        self.assertEqual(case.payable_intake.initial_allocation_amount, Decimal('1000'))
        self.assertEqual(case.payable_intake.claim_amount, Decimal('800'))
        reconcile_authoritative_obligation(case=case, actor=self.requesting_user,
            expected_version=case.state_version, idempotency_key='recover-corrected-allocation')
        case.refresh_from_db()
        submit_payable_intake(case=case, actor=self.requesting_user, expected_version=case.state_version, idempotency_key='resubmit-advance')
        replacement = review_and_recognize('800', 'REPLACEMENT')
        self.assertEqual(replacement.source_snapshot['advance_replacement']['original_request'], str(original_request.public_id))
        self.assertEqual(downstream_issuance_boundary(obligation), 'disbursement voucher')
        instrument, payment = self.pay(case, suffix='-CORRECTED-ADVANCE')
        fresh = replacement.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)
        self.assertEqual(disbursement(fresh, timezone.localdate())['released_net'], Decimal('800'))
        self.assertEqual(instrument.amount, Decimal('800'))
        self.assertEqual(sum((x['balance'] for x in subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())), Decimal('0')), Decimal('800'))
        self.assertIn(b'1000', archived)
        self.assertIn(b'800', self.client.get(reverse('accounting:advance_export')).content)
        self.assertEqual(original.totals, (Decimal('1000'), Decimal('1000')))

    def return_signatures(self, case):
        from .models import WetSignatureTask
        from .services import record_signature_return
        for task in case.signature_tasks.filter(status=WetSignatureTask.PENDING).order_by('sequence', 'pk'):
            case.refresh_from_db()
            record_signature_return(case=case, task=task, actor=self.preparer, note='Synthetic signed correction copy returned',
                expected_version=case.state_version, idempotency_key=f'advance-signature:{task.pk}')
        case.refresh_from_db()
        return case

    def test_unpaid_correction_reopens_dv_and_retains_original_accounting(self):
        from accounting.models import LedgerAccount
        from accounting.services import submit_entry, post_entry
        from finance.models import FinancePostingRuleLine
        from .advance_recognition_corrections import prepare, correction_window
        from .advance_sources import original as read_original
        from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
        from .services import prepare_voucher, validate_accounting
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        request = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        old = JournalEntry.objects.get(public_id=request.accounting_entry_public_id)
        detail = old.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)
        before = list(old.lines.values_list('account_id', 'debit', 'credit'))
        correction = prepare(detail=detail, actor=self.preparer, day=timezone.localdate(),
            reason='Synthetic advance was recognized in the wrong advance account', key='UNPAID')
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_EVENT_POSTING)
        entry, created = materialize_voucher_journal(correction, self.preparer)
        self.assertTrue(created)
        self.assertEqual(materialize_voucher_journal(correction, self.preparer)[0].pk, entry.pk)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        self.assertFalse(correction_window(case))
        reconcile_posted_voucher_entry(entry, self.validator)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)
        self.assertTrue(correction_window(case))
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], 0)
        account = LedgerAccount.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            code='1-ADV-CORRECT', title='Correct synthetic advance account', account_type='asset', normal_balance='debit')
        self.recognition_rule.lines.filter(account_source=FinancePostingRuleLine.ADVANCE_ACCOUNT).update(ledger_account_code=account.code)
        prepare_voucher(case=case, actor=self.preparer, voucher_date=timezone.localdate(), gross_amount=Decimal('1000'),
            deductions=[], line_description='Corrected original advance source', line_account_code='5-02-03',
            document_codes=['invoice'], expected_version=case.state_version, idempotency_key='CORRECTED-DV')
        case.refresh_from_db(); self.return_signatures(case)
        validate_accounting(case=case, actor=self.validator, jev_number='CORRECTED-ADVANCE', jev_date=timezone.localdate(),
            note='Independent corrected source review', expected_version=case.state_version, idempotency_key='CORRECTED-VALIDATION')
        new = case.posting_requests.filter(kind=VoucherPostingRequest.RECOGNITION).latest('pk')
        replacement, _ = materialize_voucher_journal(new, self.preparer)
        submit_entry(replacement, self.preparer); post_entry(replacement, self.validator)
        reconcile_posted_voucher_entry(replacement, self.validator)
        fresh = replacement.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)
        self.assertEqual(read_original(fresh)[0].journal_line.account_id, account.pk)
        self.assertEqual(list(old.lines.values_list('account_id', 'debit', 'credit')), before)
        self.assertEqual(sum((x['balance'] for x in subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())), Decimal('0')), Decimal('1000'))

    def test_current_return_does_not_reopen_a_posted_unpaid_advance(self):
        case = self.ready_for_treasury()
        source = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        original = JournalEntry.objects.get(public_id=source.accounting_entry_public_id)
        self.assertFalse(case.payment_instruments.exists())
        self.assertEqual(original.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE).debit, Decimal('1000'))
        with self.assertRaisesMessage(ValidationError, 'already has a posted JEV'):
            return_case(case=case, actor=self.treasury_user, target_stage=VoucherCase.ACCOUNTING_VALIDATION,
                reason='Synthetic incorrect advance amount before payment',
                expected_version=case.state_version, idempotency_key='recognition-correction-gap')
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)
        self.assertFalse(original.reversal_entries.exists())
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], Decimal('1000'))
