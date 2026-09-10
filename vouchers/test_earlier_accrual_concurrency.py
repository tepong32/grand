from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from accounting.models import JournalEntry
from . import test_earlier_accruals as fixtures
from .models import VoucherCase, VoucherPostingRequest
from .posting import materialize_voucher_journal
from .services import return_case, submit_payable_intake


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class EarlierAccrualConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.EarlierAccrualTests.employee.__func__)
    authoritative_payable_for_review = fixtures.EarlierAccrualTests.authoritative_payable_for_review
    enable_payment_event_rules = fixtures.EarlierAccrualTests.enable_payment_event_rules
    review = fixtures.EarlierAccrualTests.review

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="grand-early-race-")
        self.addCleanup(temporary.cleanup)
        settings = override_settings(MEDIA_ROOT=temporary.name, GRAND_EXPORT_ROOT=temporary.name)
        settings.enable()
        self.addCleanup(settings.disable)
        fixtures.EarlierAccrualTests.setUpTestData.__func__(type(self))
        fixtures.EarlierAccrualTests.setUp(self)

    def race(self, action):
        barrier = Barrier(2, timeout=20)
        def run(number):
            close_old_connections()
            try:
                barrier.wait()
                return action(number)
            except ValidationError as exc:
                return "; ".join(exc.messages)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, (1, 2)))

    def test_review_retry_materialization_and_return_share_case_lock(self):
        case_id = self.case.pk
        version = self.case.state_version
        def review(_):
            # Separate worker instances prevent mutable ORM objects crossing threads.
            worker = fixtures.EarlierAccrualTests()
            worker.case = VoucherCase.objects.get(pk=case_id)
            worker.validator = get_user_model().objects.get(pk=self.validator.pk)
            worker.review(expected_version=version)
            return "reviewed"
        self.assertEqual(self.race(review), ["reviewed", "reviewed"])
        request = self.case.posting_requests.get()
        def materialize(_):
            entry, created = materialize_voucher_journal(VoucherPostingRequest.objects.get(pk=request.pk),
                get_user_model().objects.get(pk=self.preparer.pk))
            return (entry.pk, created)
        results = self.race(materialize)
        self.assertEqual({r[0] for r in results}, {JournalEntry.objects.get(source_reference=str(request.public_id)).pk})
        self.assertEqual(sorted(r[1] for r in results), [False, True])
        entry = JournalEntry.objects.get(source_reference=str(request.public_id))
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.post(reverse("accounting:entry_discard", args=[entry.public_id]),
            {"reason": "Correct source before re-review"}).status_code, 302)
        self.case.refresh_from_db()
        return_case(case=self.case, actor=self.preparer, target_stage=VoucherCase.PAYABLE_PREPARATION,
            reason="Correct reviewed packet", expected_version=self.case.state_version, idempotency_key="race-return-first")
        self.case.refresh_from_db()
        submit_payable_intake(case=self.case, actor=self.requesting_user,
            expected_version=self.case.state_version, idempotency_key="race-resubmit")
        self.review(idempotency_key="race-review-successor")
        request = self.case.posting_requests.get(version=2)
        self.case.refresh_from_db()
        version = self.case.state_version
        def return_or_materialize(number):
            if number == 1:
                materialize(number)
                return "created"
            return_case(case=VoucherCase.objects.get(pk=case_id), actor=get_user_model().objects.get(pk=self.preparer.pk),
                target_stage=VoucherCase.PAYABLE_PREPARATION, reason="Correct packet before posting",
                expected_version=version, idempotency_key="race-return-successor")
            return "returned"
        results = self.race(return_or_materialize)
        self.assertEqual(sum(r in ("created", "returned") for r in results), 1, results)
        request.refresh_from_db()
        entries = JournalEntry.objects.filter(source_reference=str(request.public_id))
        if "returned" in results:
            self.assertEqual(request.status, VoucherPostingRequest.CANCELLED)
            self.assertFalse(entries.exists())
        else:
            self.assertEqual(request.status, VoucherPostingRequest.MATERIALIZED)
            self.assertEqual(entries.count(), 1)
