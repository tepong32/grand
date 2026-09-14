from django.contrib.auth import get_user_model
from django.utils import timezone
from accounting.models import JournalSubsidiaryLine
from . import test_advance_concurrency as fixtures
from .models import VoucherPostingRequest as Request
from .services import issue_check, cancel_check
from .advance_recognition_corrections import prepare


class CancelledAdvanceConcurrencyTests(fixtures.AdvanceConcurrencyTests):
    def test_cancelled_advance_correction_and_old_check_replacement_are_exclusive(self):
        self.enable_payment_event_rules('op_suppliers')
        case = self.ready_for_treasury()
        detail = JournalSubsidiaryLine.objects.get(entry__public_id=case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code='gf-lbp', fund_code='general-fund',
            check_number='ADV-RACE-OLD', amount='1000', expected_version=case.state_version, idempotency_key='old-race')
        case.refresh_from_db()
        cancel_check(case=case, instrument=instrument, actor=self.treasury_user, reason='Incorrect unpaid advance',
            expected_version=case.state_version, idempotency_key='cancel-race')
        case.refresh_from_db(); instrument.refresh_from_db()
        def compete(number):
            if number == 1:
                prepare(detail=detail, actor=get_user_model().objects.get(pk=self.preparer.pk), day=timezone.localdate(),
                    reason='Correct cancelled original advance', key='correction-race')
            else:
                issue_check(case=case, actor=get_user_model().objects.get(pk=self.treasury_user.pk), bank_account_code='gf-lbp',
                    fund_code='general-fund', check_number='ADV-RACE-REPLACEMENT', amount='1000', replaces=instrument,
                    expected_version=case.state_version, idempotency_key='replacement-race')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
