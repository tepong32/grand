import tempfile
from unittest import skipUnless
from datetime import timedelta

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry
from . import tests as workflow
from .models import PaymentPresentationReport as Report, PaymentPresentationDecision as Decision
from .payment_presentations import capture, decide, protect_instrument, verify, visible_reports
from .services import issue_check, cancel_check, submit_checks_for_advice, finalize_bank_advice, release_check


class PresentationTests(TestCase):
    databases = {'default', 'finance'}
    employee = classmethod(workflow.VoucherWorkflowTests.employee.__func__)
    setUpTestData = classmethod(workflow.VoucherWorkflowTests.setUpTestData.__func__)
    create_case = workflow.VoucherWorkflowTests.create_case
    budget_certify = workflow.VoucherWorkflowTests.budget_certify
    accounting_prepare = workflow.VoucherWorkflowTests.accounting_prepare
    return_signatures = workflow.VoucherWorkflowTests.return_signatures
    ready_for_treasury = workflow.VoucherWorkflowTests.ready_for_treasury
    acknowledge_advice = workflow.VoucherWorkflowTests.acknowledge_advice
    enable_payment_event_rules = workflow.VoucherWorkflowTests.enable_payment_event_rules

    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory()
        cls.fixture_settings = override_settings(MEDIA_ROOT=cls.fixture_directory.name, GRAND_EXPORT_ROOT=cls.fixture_directory.name)
        cls.fixture_settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.fixture_settings.disable()
        cls.fixture_directory.cleanup()

    def setUp(self):
        for actor, permission in ((self.treasury_user, 'record_payment_presentations'), (self.validator, 'review_payment_presentations')):
            actor.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename=permission))
        self.case = self.ready_for_treasury()
        self.instrument = issue_check(case=self.case, actor=self.treasury_user, bank_account_code='gf-lbp',
            check_number='PRESENT-01', amount='900.00', expected_version=self.case.state_version, idempotency_key='present-issue')
        self.case.refresh_from_db()

    def report(self, **kwargs):
        data = dict(instrument=self.instrument, actor=self.treasury_user, observed_on=timezone.localdate(),
                    reason='Payee reports attempted encashment', evidence_reference='Synthetic incoming call register 01')
        data.update(kwargs)
        return capture(**data)

    def decision(self, report, **kwargs):
        report.refresh_from_db()
        data = dict(report=report, actor=self.validator, expected_version=report.state_version,
                    outcome=Decision.PENDING, effective_on=timezone.localdate(),
                    evidence_reference='Synthetic branch response 01', reason='Reviewed bank finding', next_action='Treasury contact bank')
        data.update(kwargs)
        return decide(**data)

    def test_attempt_and_independent_nonpayment_resolution_do_not_post_or_approve(self):
        before = JournalEntry.objects.count()
        report = self.report()
        self.decision(report)
        protect_instrument(self.instrument)
        self.decision(report, outcome=Decision.NOT_PAID)
        report.refresh_from_db()
        self.assertFalse(report.is_open)
        self.assertEqual(report.decisions.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), before)
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.status, 'issued')
        self.assertIsNone(self.instrument.current_advice_batch_id)
        verify(report)
        self.report(reason='A separate later presentation')

    def ready_for_release(self):
        submit_checks_for_advice(case=self.case, actor=self.treasury_user, expected_version=self.case.state_version,
                                 idempotency_key='presentation-advice')
        self.case.refresh_from_db()
        batch = finalize_bank_advice(case=self.case, actor=self.preparer, advice_number='PRESENT-ADV',
            advice_date=timezone.localdate(), expected_version=self.case.state_version, idempotency_key='presentation-batch',
            preparation_note='Original cheque', authority_reference='Synthetic bank procedure', local_applicability_note='Synthetic approved route')
        self.acknowledge_advice(batch)
        self.case.refresh_from_db()
        self.instrument.refresh_from_db()

    def release_instrument(self):
        return release_check(case=self.case, instrument=self.instrument, actor=self.treasury_user,
            claimant=self.claimant, receipt_reference='CLAIMANT-001', expected_version=self.case.state_version,
            idempotency_key='presentation-release')

    def test_pending_report_allows_ordinary_acknowledged_release(self):
        report = self.report()
        self.decision(report)
        self.ready_for_release()
        self.release_instrument()
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.status, 'released')
        self.decision(report, outcome=Decision.NOT_PAID, reason='Bank had not paid at time of presentation; normal release followed')

    def test_verified_payment_prevents_second_release_and_extra_check(self):
        report = self.report()
        self.ready_for_release()
        self.decision(report, outcome=Decision.PAID)
        with self.assertRaises(ValidationError):
            self.release_instrument()
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.status, 'advised')

    def post_source(self, source):
        from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
        from accounting.services import submit_entry, post_entry
        entry, _ = materialize_voucher_journal(source, self.preparer)
        submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        post_entry(entry, self.validator)
        entry.refresh_from_db()
        reconcile_posted_voucher_entry(entry, self.validator)
        self.case.refresh_from_db()
        self.instrument.refresh_from_db()
        return entry

    def paid_source(self):
        self.enable_payment_event_rules()
        self.ready_for_release()
        self.release_instrument()
        source = self.case.posting_requests.get(trigger_key=f'payment-instrument:{self.instrument.public_id}:released')
        self.post_source(source)
        return source

    def test_paid_finding_closes_only_against_its_completed_payment_source(self):
        source = self.paid_source()
        report = self.report()
        self.decision(report, outcome=Decision.PAID)
        recognition = self.case.posting_requests.get(kind='recognition')
        with self.assertRaises(ValidationError):
            self.decision(report, outcome=Decision.PAID_RECONCILED, source_reference=recognition.public_id)
        count = JournalEntry.objects.count()
        event = self.decision(report, outcome=Decision.PAID_RECONCILED, source_reference=source.public_id)
        report.refresh_from_db()
        self.assertFalse(report.is_open)
        self.assertEqual(event.snapshot['resolution']['request'], str(source.public_id))
        self.assertEqual(JournalEntry.objects.count(), count)
        verify(report)

    def test_no_entry_replacement_cannot_hide_unposted_release(self):
        self.enable_payment_event_rules()
        cancel_check(case=self.case, instrument=self.instrument, actor=self.treasury_user, reason='Spoiled before release',
            expected_version=self.case.state_version, idempotency_key='replace-before-payment')
        self.case.refresh_from_db()
        self.instrument = issue_check(case=self.case, actor=self.treasury_user, bank_account_code='gf-lbp',
            check_number='PRESENT-NOENTRY', amount='900.00', replaces=self.instrument,
            expected_version=self.case.state_version, idempotency_key='noentry-replacement')
        self.case.refresh_from_db()
        self.ready_for_release()
        self.release_instrument()
        report = self.report()
        self.decision(report, outcome=Decision.PAID)
        no_entry = self.case.posting_requests.get(trigger_key=f'payment-instrument:{self.instrument.public_id}:issued')
        with self.assertRaises(ValidationError):
            self.decision(report, outcome=Decision.PAID_RECONCILED, source_reference=no_entry.public_id)
        self.client.force_login(self.validator)
        self.assertNotContains(self.client.get(reverse('vouchers:presentation_detail', args=[report.public_id])), str(no_entry.public_id))
        payment = self.case.posting_requests.get(trigger_key=f'payment-instrument:{self.instrument.public_id}:released')
        self.post_source(payment)
        self.decision(report, outcome=Decision.PAID_RECONCILED, source_reference=payment.public_id)

    def test_return_finding_links_posted_review_before_replacement(self):
        from .models import TreasuryCashPolicy, PaymentInstrumentException
        from .cash_positions import open_instrument_exception
        from .advice import decide_returned_instrument
        self.paid_source()
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code='gf-lbp', fund_code='general-fund', mode='observe', minimum_reserve=0,
            position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=timezone.localdate().replace(month=1, day=1), authority_reference='Synthetic return policy',
            local_applicability_note='Synthetic Accounting/Treasury policy', status='active', created_by=self.treasury_user,
            submitted_by=self.treasury_user, submitted_at=timezone.now(), approved_by=self.validator, approved_at=timezone.now())
        report = self.report()
        self.decision(report, outcome=Decision.RETURNED)
        exception = open_instrument_exception(instrument=self.instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(), reason='Bank return', evidence_reference='BANK-RET-1')
        review = exception.accounting_reviews.get()
        decide_returned_instrument(review=review, actor=self.validator, approve=True, outcome='reissue',
            decision_reason='Restore payable through original bank return', evidence_reference='ACCOUNTING-RET-1', expected_version=review.state_version)
        review.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.decision(report, outcome=Decision.RETURN_LINKED, source_reference=review.public_id)
        self.post_source(review.posting_request)
        self.decision(report, outcome=Decision.RETURN_LINKED, source_reference=review.public_id)
        report.refresh_from_db()
        self.assertFalse(report.is_open)
        replacement = issue_check(case=self.case, actor=self.treasury_user, bank_account_code='gf-lbp', check_number='PRESENT-REISSUE',
            amount='900.00', replaces=self.instrument, expected_version=self.case.state_version, idempotency_key='presentation-reissue')
        self.assertEqual(replacement.replaces_id, self.instrument.pk)

    def test_verified_payment_blocks_cancel_and_cannot_be_dismissed(self):
        report = self.report()
        self.decision(report, outcome=Decision.PAID)
        with self.assertRaises(ValidationError):
            cancel_check(case=self.case, instrument=self.instrument, actor=self.treasury_user, reason='Cancel',
                         expected_version=self.case.state_version, idempotency_key='cancel-paid')
        with self.assertRaises(ValidationError):
            self.decision(report, outcome=Decision.MISTAKEN)
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.status, 'issued')

    def test_duplicate_dates_stale_and_immutable_evidence(self):
        with self.assertRaises(ValidationError):
            self.report(observed_on=timezone.localdate()+timedelta(days=1))
        report = self.report()
        with self.assertRaises(ValidationError):
            self.report()
        decision = self.decision(report)
        with self.assertRaises(ValidationError):
            self.decision(report, expected_version=1)
        decision.reason = 'Overwrite'
        with self.assertRaises(ValidationError):
            decision.save()
        self.instrument.amount += 1
        # Simulate out-of-service financial drift; verification must fail closed.
        type(self.instrument).objects.filter(pk=self.instrument.pk).update(amount=self.instrument.amount)
        report = Report.objects.select_related('instrument__case').get(pk=report.pk)
        with self.assertRaises(ValidationError):
            verify(report)

    def test_office_and_uat_boundaries_and_web(self):
        outsider = self.employee('other.treasury', self.requesting, 'view_bank_advice', 'record_payment_presentations')
        with self.assertRaises(PermissionDenied):
            self.report(actor=outsider)
        report = self.report()
        self.assertFalse(visible_reports(outsider).exists())
        self.client.force_login(self.validator)
        page = self.client.get(reverse('vouchers:presentation_detail', args=[report.public_id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Record independent bank finding')
        self.validator.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        with self.assertRaises(PermissionDenied):
            self.decision(report)
        self.assertNotContains(self.client.get(reverse('vouchers:presentation_detail', args=[report.public_id])), 'Record independent bank finding')

    def test_database_active_identity_and_reporter_cannot_review(self):
        report = self.report()
        self.treasury_user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='review_payment_presentations'))
        with self.assertRaises(PermissionDenied):
            self.decision(report, actor=self.treasury_user)
        duplicate = Report(instrument=report.instrument, treasury_department=report.treasury_department,
            accounting_department=report.accounting_department, observed_on=report.observed_on,
            reason=report.reason, evidence_reference=report.evidence_reference, snapshot=report.snapshot,
            checksum=report.checksum, reported_by=self.treasury_user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_web_capture_review_and_export_retains_prior_download(self):
        self.client.force_login(self.treasury_user)
        url = reverse('vouchers:presentation_create', args=[self.instrument.public_id])
        self.assertContains(self.client.get(url), 'Record presentation report')
        response = self.client.post(url, {'observed_on': timezone.localdate().isoformat(),
            'reason': 'At the branch', 'evidence_reference': 'CALL-001'})
        self.assertEqual(response.status_code, 302)
        report = Report.objects.get()
        export = reverse('vouchers:presentation_export', args=[report.public_id])
        original = self.client.get(export).content
        self.client.force_login(self.validator)
        result = self.client.post(response.url, {'expected_version': 1, 'outcome': Decision.MISTAKEN,
            'effective_on': timezone.localdate().isoformat(), 'evidence_reference': 'CORRECTED-REPORT',
            'reason': 'Different instrument confirmed', 'next_action': ''})
        self.assertEqual(result.status_code, 302)
        self.assertNotEqual(original, self.client.get(export).content)
        self.assertContains(self.client.get(result.url), 'Resolved')
        from pathlib import Path
        retained = list(Path(self.fixture_directory.name).rglob('*.json'))
        self.assertTrue(any(p.read_bytes() == original for p in retained))


from . import test_deduction_correction_concurrency as concurrency


@skipUnless(connections['default'].vendor == 'mysql', 'Requires native MySQL locks')
class PresentationConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(workflow.VoucherWorkflowTests.employee.__func__)
    create_case = PresentationTests.create_case
    budget_certify = PresentationTests.budget_certify
    accounting_prepare = PresentationTests.accounting_prepare
    return_signatures = PresentationTests.return_signatures
    ready_for_treasury = PresentationTests.ready_for_treasury
    report = PresentationTests.report
    decision = PresentationTests.decision
    race = concurrency.DeductionCorrectionConcurrencyTests.race

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(MEDIA_ROOT=temporary.name, GRAND_EXPORT_ROOT=temporary.name)
        settings.enable()
        self.addCleanup(settings.disable)
        workflow.VoucherWorkflowTests.setUpTestData.__func__(type(self))
        PresentationTests.setUp(self)

    def test_competing_reports_keep_one_active_identity(self):
        def action(number):
            self.report(reason=f'Caller {number}')
            return 'accepted'
        results = self.race(action)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(Report.objects.count(), 1)

    def test_competing_decisions_keep_one_current_version(self):
        report = self.report()
        def action(number):
            self.decision(Report.objects.get(pk=report.pk), expected_version=1, outcome=Decision.NOT_PAID)
            return 'accepted'
        results = self.race(action)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(report.decisions.count(), 1)

    def test_verified_payment_and_cancellation_share_case_lock(self):
        report = self.report()
        def action(number):
            if number == 1:
                self.decision(Report.objects.get(pk=report.pk), outcome=Decision.PAID)
            else:
                cancel_check(case=self.case, instrument=self.instrument, actor=self.treasury_user, reason='Wrong cheque',
                    expected_version=self.case.state_version, idempotency_key='race-cancel')
            return 'accepted'
        results = self.race(action)
        self.assertIn('accepted', results)
        self.assertEqual(report.decisions.get().outcome, Decision.PAID)
        self.case.refresh_from_db()
        with self.assertRaises(ValidationError):
            issue_check(case=self.case, actor=self.treasury_user, bank_account_code='gf-lbp', check_number='PRESENT-02',
                amount='900.00', expected_version=self.case.state_version, idempotency_key='race-reissue')
