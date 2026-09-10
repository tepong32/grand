from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from . import test_claim_attributions
from .claim_attributions import review, current
from .models import JournalEntry, PayableClaimAttribution, PayableClaimAttributionHead, PayableClaimReservation
from .payables import _reserve_claim
from .services import submit_entry, post_entry


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class ClaimAttributionConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = test_claim_attributions.ClaimAttributionTests.setUp
    entry = test_claim_attributions.ClaimAttributionTests.entry
    post = test_claim_attributions.ClaimAttributionTests.post
    legacy = test_claim_attributions.ClaimAttributionTests.legacy
    detail = test_claim_attributions.ClaimAttributionTests.detail
    proposal = test_claim_attributions.ClaimAttributionTests.proposal

    def race(self, actions):
        barrier = Barrier(2, timeout=25)

        def act(number):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.poster.pk)
                barrier.wait()
                actions[number](actor)
                return "accepted"
            except ValidationError as exc:
                return "; ".join(exc.messages)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(act, (0, 1)))
        self.assertEqual(results.count("accepted"), 1, results)
        return results

    def approve(self, pk, actor):
        return review(PayableClaimAttribution.objects.get(pk=pk), actor, approve=True, note="Concurrent independent review")

    def test_two_claims_cannot_adopt_the_same_historical_payment(self):
        source, applied = self.legacy()
        other = self.entry("OTHER-SOURCE", Decimal("1000"))
        other_source = other.lines.get(sequence=2)
        other_source.payable_party_key = other_source.payable_claim_reference = ""
        other_source.save()
        self.post(other)
        records = [self.proposal(source, [applied]), self.proposal(other_source, [applied], claim_reference="OTHER")]
        results = self.race([lambda actor: self.approve(records[0].pk, actor), lambda actor: self.approve(records[1].pk, actor)])
        self.assertTrue(any("already belongs" in result for result in results), results)
        self.assertEqual(PayableClaimAttributionHead.objects.count(), 1)

    def test_approval_and_native_recognition_share_invoice_identity_lock(self):
        source, _ = self.legacy()
        record = self.proposal(source, [])
        native = self.entry("NEW-RECOGNITION", Decimal("1000"), claim="HIST-001")
        submit_entry(native, self.maker)
        results = self.race([lambda actor: self.approve(record.pk, actor),
            lambda actor: post_entry(JournalEntry.objects.get(pk=native.pk), actor)])
        self.assertTrue(any("already recognized" in result for result in results), results)

    def test_newly_attributed_application_and_dv_hold_cannot_overcommit(self):
        source, applied = self.legacy()
        review(self.proposal(source, []), self.poster, approve=True, note="Initial reconciliation")
        correction = self.proposal(source, [applied], expected_version=1, reason="Reconciled a previously omitted payment")

        def reserve(actor):
            _reserve_claim(source_id=source.pk, case_public_id=uuid.uuid4(), key="historical-race",
                amount=Decimal("700"), actor_id=actor.pk, department_id=self.department.pk,
                fund_code=self.fund.code, party_key="supplier-001", as_of=date(2026, 9, 5))

        results = self.race([lambda actor: self.approve(correction.pk, actor), reserve])
        self.assertTrue(any("already applied or reserved" in result for result in results), results)
        self.assertEqual(int(current(source).version == 2) + PayableClaimReservation.objects.count(), 1)
