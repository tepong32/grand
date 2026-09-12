from tempfile import TemporaryDirectory
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from . import test_advances as fixtures, test_deduction_correction_concurrency as concurrent
from .advance_applications import prepare, materialize
from .models import VoucherPostingRequest
from accounting.models import JournalEntry
from accounting.services import submit_entry, post_entry


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class AdvanceConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.AdvanceRecognitionTests.employee.__func__)
    create_case = fixtures.AdvanceRecognitionTests.create_case
    budget_certify = fixtures.AdvanceRecognitionTests.budget_certify
    accounting_prepare = fixtures.AdvanceRecognitionTests.accounting_prepare
    return_signatures = fixtures.AdvanceRecognitionTests.return_signatures
    ready_for_treasury = fixtures.AdvanceRecognitionTests.ready_for_treasury
    enable_payment_event_rules = fixtures.AdvanceRecognitionTests.enable_payment_event_rules
    acknowledge_advice = fixtures.AdvanceRecognitionTests.acknowledge_advice
    paid_advance = fixtures.AdvanceRecognitionTests.paid_advance
    liquidation_rule = fixtures.AdvanceRecognitionTests.liquidation_rule
    race = concurrent.DeductionCorrectionConcurrencyTests.race

    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name, GRAND_EXPORT_ROOT=folder.name)
        settings.enable(); self.addCleanup(settings.disable)
        fixtures.AdvanceRecognitionTests.setUpTestData.__func__(type(self))
        fixtures.AdvanceRecognitionTests.setUp(self)
    def ready(self, *, reconcile=True):
        self.detail, self.case, self.instrument = self.paid_advance(reconcile=reconcile)
        self.rule = self.liquidation_rule()

    def proposal(self, key):
        return prepare(detail=self.detail, actor=get_user_model().objects.get(pk=self.preparer.pk), rule=self.rule,
            day=timezone.localdate(), expenses=[{"account_code":"5-02-03", "amount":"600", "document_reference":"SYNTHETIC-EXPENSE"}],
            evidence_reference=f"SYNTHETIC-RACE-{key}", key=str(key))

    def test_competing_expenses_cannot_reserve_the_same_release(self):
        self.ready()
        def compete(number):
            self.proposal(number)
            return "accepted"
        result = self.race(compete)
        self.assertEqual(result.count("accepted"), 1, result)
        self.assertEqual(self.case.posting_requests.filter(kind=VoucherPostingRequest.LIQUIDATION).count(), 1)

    def test_duplicate_materialization_creates_one_liquidation_journal(self):
        self.ready()
        request = self.proposal("same-source")
        def compete(number):
            entry, created = materialize(VoucherPostingRequest.objects.get(pk=request.pk),
                get_user_model().objects.get(pk=self.preparer.pk))
            return "created" if created else "recovered"
        result = self.race(compete)
        self.assertCountEqual(result, ["created", "recovered"])
        self.assertEqual(JournalEntry.objects.filter(source_reference=str(request.public_id)).count(), 1)

    def test_competing_posts_record_one_application(self):
        self.ready()
        request = self.proposal("one-post")
        entry, _ = materialize(request, self.preparer)
        submit_entry(entry, self.preparer)
        def compete(number):
            post_entry(JournalEntry.objects.get(pk=entry.pk), get_user_model().objects.get(pk=self.validator.pk))
            return "posted"
        result = self.race(compete)
        self.assertEqual(result.count("posted"), 1, result)
        self.assertEqual(entry.audit_events.filter(action="posted").count(), 1)

    def test_payment_reconciliation_and_reservation_do_not_invert_source_locks(self):
        from .posting import reconcile_posted_voucher_entry
        self.ready(reconcile=False)
        payment = self.case.posting_requests.get(kind=VoucherPostingRequest.PAYMENT)
        def compete(number):
            if number == 1:
                reconcile_posted_voucher_entry(JournalEntry.objects.get(public_id=payment.accounting_entry_public_id),
                    get_user_model().objects.get(pk=self.validator.pk))
                return "reconciled"
            self.proposal("payment-recovery")
            return "reserved"
        result = self.race(compete)
        self.assertIn("reconciled", result)
        self.assertTrue(any(item == "reserved" or "Post and reconcile" in item for item in result), result)
        self.proposal("payment-recovery")
        self.assertEqual(self.case.posting_requests.filter(kind=VoucherPostingRequest.LIQUIDATION).count(), 1)
