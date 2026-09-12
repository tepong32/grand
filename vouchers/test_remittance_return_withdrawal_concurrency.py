from django.contrib.auth import get_user_model

from accounting.models import JournalEntry
from accounting.services import submit_entry, post_entry
from . import test_remittance_return_concurrency as concurrent
from . import test_remittance_return_withdrawal as scenarios
from . import test_remittance_returns as fixtures
from .models import RemittanceReturn, RemittancePostingRequest
from .remittance_returns import materialize_return
from .remittance_return_withdrawal import withdraw_return
from .remittances import materialize_remittance_journal, reconcile_posted_remittance_entry


class RemittanceReturnWithdrawalConcurrencyTests(concurrent.RemittanceReturnConcurrencyTests):
    propose = fixtures.RemittanceReturnTests.propose
    approved_return = scenarios.RemittanceReturnWithdrawalTests.approved_return

    def test_withdrawal_and_materialization_share_the_batch_lock(self):
        item = self.approved_return()
        source_id = item.posting_request_id
        def compete(number):
            if number == 1:
                withdraw_return(item=RemittanceReturn.objects.get(pk=item.pk),
                    actor=get_user_model().objects.get(pk=self.validator.pk), reason='Correct receipt before posting')
                return 'withdrawn'
            materialize_remittance_journal(RemittancePostingRequest.objects.get(pk=source_id),
                get_user_model().objects.get(pk=self.preparer.pk))
            return 'materialized'
        results = self.race(compete)
        self.assertEqual(sum(result in ('withdrawn', 'materialized') for result in results), 1, results)
        item.refresh_from_db()
        if item.status == item.WITHDRAWN:
            self.assertFalse(JournalEntry.objects.filter(source_type='remittance', source_reference=str(item.posting_request.public_id)).exists())

    def test_withdrawal_cannot_race_past_independent_posting(self):
        item = self.approved_return()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        submit_entry(entry, self.preparer)
        def compete(number):
            actor = get_user_model().objects.get(pk=self.validator.pk)
            if number == 1:
                withdraw_return(item=RemittanceReturn.objects.get(pk=item.pk), actor=actor,
                    reason='Must not bypass actual posting')
                return 'withdrawn'
            post_entry(JournalEntry.objects.get(pk=entry.pk), actor)
            return 'posted'
        results = self.race(compete)
        self.assertIn('posted', results)
        self.assertNotIn('withdrawn', results)
        reconcile_posted_remittance_entry(entry, self.validator)
        item.refresh_from_db()
        self.assertEqual(item.status, item.POSTED)
