from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from . import payables, test_payable_claims
from .models import JournalEntry
from .services import post_entry, submit_entry


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class PayableClaimConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = test_payable_claims.PayableClaimTests.setUp
    entry = test_payable_claims.PayableClaimTests.entry
    post = test_payable_claims.PayableClaimTests.post

    def test_competing_payments_cannot_overapply_one_claim(self):
        original = self.post(self.entry("CLAIM", Decimal("1000")))
        source = original.lines.get(sequence=2)
        payments = [self.entry(f"PAY-{number}", Decimal("700"), source=source, day=4) for number in (1, 2)]
        for payment in payments:
            submit_entry(payment, self.maker)
        barrier = Barrier(2, timeout=20)
        check = payables.validate_claim_applications

        def simultaneous(entry, **kwargs):
            barrier.wait()
            return check(entry, **kwargs)

        def post(pk):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.poster.pk)
                try:
                    post_entry(JournalEntry.objects.get(pk=pk), actor)
                    return "posted"
                except ValidationError as exc:
                    return "; ".join(exc.messages)
            finally:
                connections.close_all()

        with patch.object(payables, "validate_claim_applications", simultaneous):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(post, [entry.pk for entry in payments]))
        self.assertEqual(results.count("posted"), 1, results)
        self.assertTrue(any("would use" in result for result in results), results)
        self.assertEqual(source.payable_applications.filter(entry__status=JournalEntry.POSTED).count(), 1)

    def test_competing_recognitions_cannot_duplicate_invoice_identity(self):
        candidates = [self.entry(f"CLAIM-{number}", Decimal("1000")) for number in (1, 2)]
        for entry in candidates:
            submit_entry(entry, self.maker)
        barrier = Barrier(2, timeout=20)
        check = payables.validate_claim_applications

        def simultaneous(entry, **kwargs):
            barrier.wait()
            return check(entry, **kwargs)

        def post(pk):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.poster.pk)
                try:
                    post_entry(JournalEntry.objects.get(pk=pk), actor)
                    return "posted"
                except ValidationError as exc:
                    return "; ".join(exc.messages)
            finally:
                connections.close_all()

        with patch.object(payables, "validate_claim_applications", simultaneous):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(post, [entry.pk for entry in candidates]))
        self.assertEqual(results.count("posted"), 1, results)
        self.assertTrue(any("already recognized" in result for result in results), results)
