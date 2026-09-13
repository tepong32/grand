from django.contrib.auth import get_user_model
from django.utils import timezone

from . import test_advance_concurrency as concurrent, test_liquidation_corrections as fixtures
from .liquidation_corrections import prepare
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .models import VoucherPostingRequest as Request
from accounting.models import JournalEntry
from accounting.services import submit_entry, post_entry


class LiquidationCorrectionConcurrencyTests(concurrent.AdvanceConcurrencyTests):
    liquidated_advance = fixtures.LiquidationCorrectionTests.liquidated_advance
    expenses = fixtures.LiquidationCorrectionTests.expenses
    post_request = fixtures.LiquidationCorrectionTests.post_request

    def correction(self, application, key):
        return prepare(application=application, actor=get_user_model().objects.get(pk=self.preparer.pk),
            day=timezone.localdate(), reason='Incorrect posted expense', key=key)

    def test_competing_corrections_create_one_active_proposal(self):
        detail, case, rule, application, original = self.liquidated_advance()
        def compete(number):
            self.correction(application, str(number))
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(case.posting_requests.filter(trigger_key__startswith='advance-liquidation-fix:').count(), 1)

    def test_duplicate_correction_materialization_creates_one_exact_reversal(self):
        detail, case, rule, application, original = self.liquidated_advance()
        correction = self.correction(application, 'ONE')
        def compete(number):
            entry, created = materialize_voucher_journal(Request.objects.get(pk=correction.pk),
                get_user_model().objects.get(pk=self.preparer.pk))
            return 'created' if created else 'recovered'
        self.assertCountEqual(self.race(compete), ['created','recovered'])
        self.assertEqual(JournalEntry.objects.filter(reversal_of=original).count(), 1)

    def test_correction_recovery_and_new_application_share_the_case_lock(self):
        detail, case, rule, application, original = self.liquidated_advance()
        correction = self.correction(application, 'RECOVERY')
        entry, _ = materialize_voucher_journal(correction, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        def compete(number):
            if number == 1:
                reconcile_posted_voucher_entry(JournalEntry.objects.get(pk=entry.pk),
                    get_user_model().objects.get(pk=self.validator.pk))
                return 'reconciled'
            self.expenses(detail, rule, '1000', 'AFTER', timezone.localdate())
            return 'reserved'
        results = self.race(compete)
        self.assertIn('reconciled', results)
        self.expenses(detail, rule, '1000', 'AFTER', timezone.localdate())
        self.assertEqual(case.posting_requests.filter(trigger_key='advance-liquidation:AFTER').count(), 1)
