"""Reservation dates must reproduce the claim's actual posted chronology."""
from datetime import date
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from . import test_payable_claims
from .models import PayableClaimReservation
from .payables import _reserve_claim, _release_unused_claim
from .services import create_reversal


class DatedClaimReservationTests(TestCase):
    databases = {"default", "finance"}
    setUp = test_payable_claims.PayableClaimTests.setUp
    entry = test_payable_claims.PayableClaimTests.entry
    post = test_payable_claims.PayableClaimTests.post

    def reserve(self, source, amount, day, **kwargs):
        return _reserve_claim(source_id=source.pk, case_public_id=uuid.uuid4(), key=str(uuid.uuid4()),
            amount=Decimal(amount), actor_id=self.poster.pk, department_id=self.department.pk,
            fund_code=self.fund.code, party_key="supplier-001", as_of=date(2026, 9, day), **kwargs)

    def history(self, payment_day=4):
        original = self.post(self.entry("ORIGINAL", Decimal("1000")))
        source = original.lines.get(sequence=2)
        payment = self.post(self.entry("PAID", Decimal("800"), source=source, day=payment_day))
        undo = create_reversal(payment, self.maker, reference="RESTORED", entry_date=date(2026, 9, 8),
            period=self.period, reason="Actual payment reversal")
        self.post(undo)
        return source

    def test_later_reversal_cannot_fund_an_earlier_reservation(self):
        source = self.history()
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            self.reserve(source, "700", 5)
        self.assertFalse(PayableClaimReservation.objects.exists())
        held = self.reserve(source, "200", 5)
        self.assertEqual(held.amount, Decimal("200"))
        _release_unused_claim(held, actor_id=self.poster.pk, reason="Reprepare after actual reversal")
        self.assertEqual(self.reserve(source, "1000", 8).amount, Decimal("1000"))

    def test_intervening_posted_payment_limits_backdated_capacity(self):
        source = self.history(payment_day=6)
        # Balance is 1,000 on the requested date and today, but only 200 on day 6.
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            self.reserve(source, "700", 5)
        self.assertEqual(self.reserve(source, "200", 5).amount, Decimal("200"))

    def test_existing_unused_hold_is_included_and_recovery_keeps_same_evidence(self):
        source = self.history()
        held = self.reserve(source, "150", 5)
        with self.assertRaisesMessage(ValidationError, "already applied or reserved"):
            self.reserve(source, "100", 5)
        recovered = _reserve_claim(source_id=source.pk, case_public_id=held.case_public_id,
            key=held.reservation_key, amount=held.amount, actor_id=self.poster.pk,
            department_id=self.department.pk, fund_code=self.fund.code,
            party_key="supplier-001", as_of=date(2026, 9, 5))
        self.assertEqual(recovered.pk, held.pk)
        self.assertEqual(recovered.source_checksum, held.source_checksum)
        self.assertEqual(self.reserve(source, "50", 5).amount, Decimal("50"))

    def test_recovery_cannot_move_a_later_hold_into_an_earlier_shortfall(self):
        source = self.history()
        held = self.reserve(source, "700", 9)
        with self.assertRaisesMessage(ValidationError, "requested date"):
            _reserve_claim(source_id=source.pk, case_public_id=held.case_public_id,
                key=held.reservation_key, amount=held.amount, actor_id=self.poster.pk,
                department_id=self.department.pk, fund_code=self.fund.code,
                party_key="supplier-001", as_of=date(2026, 9, 5))
        self.assertEqual(PayableClaimReservation.objects.count(), 1)
        held.refresh_from_db()
        self.assertIsNone(held.released_at)

    def test_recovery_at_exact_capacity_keeps_the_original_hold(self):
        source = self.history()
        held = self.reserve(source, "1000", 9)
        recovered = _reserve_claim(source_id=source.pk, case_public_id=held.case_public_id,
            key=held.reservation_key, amount=held.amount, actor_id=self.poster.pk,
            department_id=self.department.pk, fund_code=self.fund.code,
            party_key="supplier-001", as_of=date(2026, 9, 9))
        self.assertEqual(recovered.pk, held.pk)
        self.assertEqual(recovered.source_checksum, held.source_checksum)
        self.assertEqual(PayableClaimReservation.objects.count(), 1)
