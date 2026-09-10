from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest import skipUnless
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from accounting.models import JournalEntry
from . import test_deduction_corrections as fixtures
from .deduction_corrections import request_correction, withdraw_correction
from .models import VoucherCase, VoucherPostingRequest, TreasuryRemittanceBatch, TreasuryRemittanceLine
from .posting import materialize_voucher_journal
from .remittances import add_line, revise_line


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class DeductionCorrectionConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.DeductionCorrectionTests.employee.__func__)
    create_case = fixtures.DeductionCorrectionTests.create_case
    budget_certify = fixtures.DeductionCorrectionTests.budget_certify
    return_signatures = fixtures.DeductionCorrectionTests.return_signatures
    enable_payment_event_rules = fixtures.DeductionCorrectionTests.enable_payment_event_rules
    case_for_validation = fixtures.DeductionCorrectionTests.case_for_validation
    validate = fixtures.DeductionCorrectionTests.validate
    post_request = fixtures.DeductionCorrectionTests.post_request
    availability = fixtures.DeductionCorrectionTests.availability
    remittance = fixtures.DeductionCorrectionTests.remittance

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="grand-correction-race-")
        self.addCleanup(temporary.cleanup)
        settings = override_settings(MEDIA_ROOT=temporary.name, GRAND_EXPORT_ROOT=temporary.name)
        settings.enable(); self.addCleanup(settings.disable)
        fixtures.DeductionCorrectionTests.setUpTestData.__func__(type(self))
        fixtures.DeductionCorrectionTests.setUp(self)

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

    def test_remittance_correction_and_duplicate_materialization_share_native_boundaries(self):
        batch = self.remittance()
        choice = self.availability()[0]["choice_key"]
        case_id, version = self.case.pk, self.case.state_version
        def request():
            return request_correction(case=VoucherCase.objects.get(pk=case_id), actor=get_user_model().objects.get(pk=self.preparer.pk),
                correction_date=date(2026, 8, 26), reason="Concurrent correction of deduction", expected_version=version,
                idempotency_key="race-correction")
        def compete(number):
            if number == 1:
                request()
            else:
                add_line(batch=TreasuryRemittanceBatch.objects.get(pk=batch.pk), actor=get_user_model().objects.get(pk=self.treasury_user.pk),
                    choice_key=choice, amount=100, reason="Concurrent remittance")
            return "accepted"
        results = self.race(compete)
        self.assertEqual(results.count("accepted"), 1, results)
        if TreasuryRemittanceLine.objects.filter(batch=batch, status="active").exists():
            revise_line(line=TreasuryRemittanceLine.objects.get(batch=batch, status="active"), actor=self.treasury_user,
                amount=0, reason="Release the unused remittance reservation")
        request()
        correction = self.case.posting_requests.get(kind="reversal")
        def materialize(_):
            entry, created = materialize_voucher_journal(VoucherPostingRequest.objects.get(pk=correction.pk),
                get_user_model().objects.get(pk=self.preparer.pk))
            return entry.pk, created
        results = self.race(materialize)
        self.assertTrue(all(isinstance(r, tuple) for r in results), results)
        self.assertEqual({r[0] for r in results}, {JournalEntry.objects.get(source_reference=str(correction.public_id)).pk})
        self.assertEqual(sorted(r[1] for r in results), [False, True])
        entry = JournalEntry.objects.get(source_reference=str(correction.public_id))
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.post(reverse("accounting:entry_discard", args=[entry.public_id]),
            {"reason": "Draft correction no longer needed"}).status_code, 302)
        correction = self.case.posting_requests.get(kind="reversal", status="pending")
        self.case.refresh_from_db()
        version = self.case.state_version
        def withdraw_or_create(number):
            if number == 1:
                materialize(number)
                return "created"
            withdraw_correction(case=VoucherCase.objects.get(pk=case_id), actor=get_user_model().objects.get(pk=self.preparer.pk),
                reason="Withdraw before creation", expected_version=version, idempotency_key="withdraw-race")
            return "withdrawn"
        results = self.race(withdraw_or_create)
        self.assertEqual(sum(r in ("created", "withdrawn") for r in results), 1, results)
        correction.refresh_from_db()
        entries = JournalEntry.objects.filter(source_reference=str(correction.public_id))
        if "withdrawn" in results:
            self.assertEqual(correction.status, VoucherPostingRequest.CANCELLED)
            self.assertFalse(entries.exists())
        else:
            self.assertEqual(correction.status, VoucherPostingRequest.MATERIALIZED)
            self.assertEqual(entries.count(), 1)
