"""Native serialization of original correction against payment preparation."""
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import JournalEntry, JournalSubsidiaryLine
from . import test_advance_concurrency as fixtures
from . import tests as workflow, test_prior_payables as payment_fixtures
from .advance_recognition_corrections import prepare
from .models import VoucherPostingRequest as Request
from .posting import materialize_voucher_journal
from .services import issue_check


class AdvanceRecognitionCorrectionConcurrencyTests(fixtures.AdvanceConcurrencyTests):
    authoritative_payable_for_review = workflow.VoucherWorkflowTests.authoritative_payable_for_review
    post_request = payment_fixtures.PriorPayableDVTests.post_request

    def test_budget_amendment_and_replacement_dv_share_the_issuance_boundary(self):
        from decimal import Decimal
        from budget.models import ObligationRequest, ObligationRequestLine
        from budget.services import transition_obligation_request
        from .models import PayableIntake
        from .services import review_payable_intake, prepare_voucher, validate_accounting, submit_payable_intake
        case, _, obligation, _ = self.authoritative_payable_for_review()
        review_payable_intake(case=case, actor=self.validator, decision=PayableIntake.READY,
            reason='Independent original review', expected_version=case.state_version, idempotency_key='race-original-review')
        case.refresh_from_db()
        prepare_voucher(case=case, actor=self.preparer, voucher_date=timezone.localdate(), gross_amount=Decimal('1000'),
            deductions=[], line_description='Original advance', line_account_code='5-02-03', document_codes=['invoice'],
            expected_version=case.state_version, idempotency_key='race-original-dv')
        case.refresh_from_db(); self.return_signatures(case)
        validate_accounting(case=case, actor=self.validator, jev_number='ADV-BOUNDARY-ORIGINAL', jev_date=timezone.localdate(),
            note='Independent original posting', expected_version=case.state_version, idempotency_key='race-original-validate')
        source = self.post_request(case.posting_requests.get(kind=Request.RECOGNITION))
        self.post_request(prepare(detail=source.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE),
            actor=self.preparer, day=timezone.localdate(), reason='Original amount under review', key='boundary'))
        case.refresh_from_db()
        submit_payable_intake(case=case, actor=self.requesting_user, expected_version=case.state_version,
            idempotency_key='race-resubmit')
        case.refresh_from_db()
        review_payable_intake(case=case, actor=self.validator, decision=PayableIntake.READY,
            reason='Independent replacement review', expected_version=case.state_version, idempotency_key='race-rereview')
        case.refresh_from_db()
        adjustment = ObligationRequest.objects.create(department_id=obligation.department_id,
            department_label=obligation.department_label, authorization=obligation.authorization,
            fiscal_year=obligation.fiscal_year, requesting_department_id=obligation.requesting_department_id,
            requesting_department_label=obligation.requesting_department_label, kind=ObligationRequest.ADJUSTMENT,
            form_type=obligation.form_type, request_reference='ADV-BOUNDARY-ADJUSTMENT', obligation_date=timezone.localdate(),
            claimant_payee=obligation.claimant_payee, particulars='Concurrent amount reduction',
            evidence_reference='Synthetic boundary evidence', signed_control_total=Decimal('-100'), corrects=obligation,
            created_by_id=self.requesting_user.pk, created_by_label=self.requesting_user.username)
        ObligationRequestLine.objects.create(department_id=obligation.department_id, department_label=obligation.department_label,
            request=adjustment, appropriation_line=obligation.lines.get().appropriation_line,
            movement_type=ObligationRequestLine.REDUCE, amount=Decimal('100'), remarks='Synthetic reduction')
        transition_obligation_request(adjustment, 'submit', self.requesting_user)
        def compete(number):
            if number == 1:
                transition_obligation_request(ObligationRequest.objects.get(pk=adjustment.pk), 'certify',
                    get_user_model().objects.get(pk=self.budget_user.pk), 'Independent concurrent Budget decision', 'OBR-ADV-BOUNDARY')
                return 'accepted'
            prepare_voucher(case=case, actor=get_user_model().objects.get(pk=self.preparer.pk),
                voucher_date=timezone.localdate(), gross_amount=Decimal('1000'), deductions=[],
                line_description='Replacement advance', line_account_code='5-02-03', document_codes=['invoice'],
                expected_version=case.state_version, idempotency_key='race-replacement-dv')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)

    def unpaid_source(self):
        self.enable_payment_event_rules('op_suppliers')
        self.case = self.ready_for_treasury()
        source = self.case.posting_requests.get(kind=Request.RECOGNITION)
        self.source = JournalEntry.objects.get(public_id=source.accounting_entry_public_id)
        self.detail = self.source.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)

    def correction(self, key):
        return prepare(detail=JournalSubsidiaryLine.objects.get(pk=self.detail.pk),
            actor=get_user_model().objects.get(pk=self.preparer.pk), day=timezone.localdate(),
            reason='Synthetic original advance error before payment', key=str(key))

    def test_competing_original_corrections_retain_one_request(self):
        self.unpaid_source()
        def compete(number):
            self.correction(number)
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(self.case.posting_requests.filter(kind=Request.REVERSAL).count(), 1)

    def test_original_correction_and_check_issuance_are_exclusive(self):
        self.unpaid_source()
        def compete(number):
            if number == 1:
                self.correction('versus-check')
                return 'accepted'
            issue_check(case=self.case, actor=get_user_model().objects.get(pk=self.treasury_user.pk),
                bank_account_code='gf-lbp', fund_code='general-fund', check_number='ADV-CORRECTION-RACE',
                amount='1000', expected_version=self.case.state_version, idempotency_key='race-check')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(self.case.payment_instruments.count() + self.case.posting_requests.filter(kind=Request.REVERSAL).count(), 1)

    def test_duplicate_original_correction_materialization_retains_one_reversal(self):
        self.unpaid_source()
        request = self.correction('materialize')
        def compete(number):
            entry, created = materialize_voucher_journal(Request.objects.get(pk=request.pk),
                get_user_model().objects.get(pk=self.preparer.pk))
            return 'created' if created else 'recovered'
        self.assertCountEqual(self.race(compete), ['created', 'recovered'])
        self.assertEqual(JournalEntry.objects.filter(reversal_of=self.source).count(), 1)
