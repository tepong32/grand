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

from . import test_payable_claims
from .models import JournalEntry, PayableClaimReservation
from .payables import _reserve_claim
from .services import post_entry, submit_entry


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class PayableReservationConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = test_payable_claims.PayableClaimTests.setUp
    entry = test_payable_claims.PayableClaimTests.entry
    post = test_payable_claims.PayableClaimTests.post

    def race(self, *, manual=False, transfer=False):
        source = self.post(self.entry("RESERVE-SOURCE", Decimal("1000"))).lines.get(sequence=2)
        payment = self.entry("RESERVE-PAY", Decimal("700"), source=source, day=4)
        if transfer:
            credit = payment.lines.get(sequence=2)
            credit.account = self.accounts["payable"]
            credit.cash_flow_category = ""
            credit.payable_party_key = "supplier-002"
            credit.payable_claim_reference = "TRANSFER-001"
            credit.save()
        submit_entry(payment, self.maker)
        barrier = Barrier(2, timeout=20)

        def act(number):
            close_old_connections()
            try:
                barrier.wait()
                if manual and number == 2:
                    actor = get_user_model().objects.get(pk=self.poster.pk)
                    post_entry(JournalEntry.objects.get(pk=payment.pk), actor)
                else:
                    _reserve_claim(source_id=source.pk, case_public_id=uuid.uuid4(), key=f"race-{number}",
                        amount=Decimal("700"), actor_id=self.poster.pk, department_id=self.department.pk,
                        fund_code=self.fund.code, party_key="supplier-001", as_of=date(2026, 9, 4))
                return "accepted"
            except ValidationError as exc:
                return "; ".join(exc.messages)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(act, (1, 2)))
        self.assertEqual(results.count("accepted"), 1, results)
        self.assertTrue(any("already applied or reserved" in result for result in results), results)
        payment.refresh_from_db()
        self.assertEqual(PayableClaimReservation.objects.count() + int(payment.status == JournalEntry.POSTED), 1)

    def test_competing_voucher_holds_cannot_reserve_same_claim_capacity(self):
        self.race()

    def test_manual_application_and_voucher_hold_share_native_source_lock(self):
        self.race(manual=True)

    def test_transfer_recognition_and_reservation_preserve_fund_source_lock_order(self):
        self.race(manual=True, transfer=True)
