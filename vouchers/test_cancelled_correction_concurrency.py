from django.contrib.auth import get_user_model
from django.utils import timezone

from . import test_deduction_correction_concurrency as fixtures
from . import test_cancelled_check_corrections as scenarios
from .deduction_corrections import request_correction
from .models import VoucherCase, PaymentInstrument
from .services import issue_check


class CancelledCorrectionConcurrencyTests(fixtures.DeductionCorrectionConcurrencyTests):
    cancel_before_correction = scenarios.CancelledCheckCorrectionTests.cancel_before_correction

    def test_replacement_and_deduction_correction_share_case_lock(self):
        instrument = self.cancel_before_correction()
        case_id, version = self.case.pk, self.case.state_version
        def compete(number):
            case = VoucherCase.objects.get(pk=case_id)
            if number == 1:
                request_correction(case=case, actor=get_user_model().objects.get(pk=self.preparer.pk),
                    correction_date=timezone.localdate(), reason="Correct after cancellation",
                    expected_version=version, idempotency_key="race-cancel-correction")
            else:
                issue_check(case=case, actor=get_user_model().objects.get(pk=self.treasury_user.pk),
                    bank_account_code="gf-lbp", fund_code="general-fund", check_number="RACING-REPLACEMENT", amount=900,
                    replaces=PaymentInstrument.objects.get(pk=instrument.pk), expected_version=version,
                    idempotency_key="race-cancel-replacement")
            return "accepted"
        results = self.race(compete)
        self.assertEqual(results.count("accepted"), 1, results)
        pending = self.case.posting_requests.filter(kind="reversal", status="pending").exists()
        replacement = self.case.payment_instruments.filter(replaces=instrument).exists()
        self.assertNotEqual(pending, replacement)
