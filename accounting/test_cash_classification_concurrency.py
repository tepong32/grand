from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections, close_old_connections
from django.test import TransactionTestCase

from . import cash_classifications, test_cash_classifications
from .models import CashFlowClassification, CashFlowClassificationHead


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class CashClassificationConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = test_cash_classifications.CashClassificationTests.setUp
    post = test_cash_classifications.CashClassificationTests.post
    proposal = test_cash_classifications.CashClassificationTests.proposal

    def test_competing_first_approvals_serialize_on_posted_source(self):
        entry = self.post("CONCURRENT-CASH", [("expense", 90, 0, ""), ("cash", 0, 90, "")])
        candidates = [self.proposal(entry), self.proposal(entry)]
        barrier = Barrier(2, timeout=20)
        original = cash_classifications._locked_entry

        def synchronized_lock(*args, **kwargs):
            barrier.wait()
            return original(*args, **kwargs)

        def approve(pk):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.checker.pk)
                record = CashFlowClassification.objects.get(pk=pk)
                try:
                    cash_classifications.review_classification(record, actor, approve=True, note="Concurrent source check")
                    return "approved"
                except ValidationError as exc:
                    return "; ".join(exc.messages)
            finally:
                connections.close_all()

        with patch.object(cash_classifications, "_locked_entry", synchronized_lock):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(approve, [record.pk for record in candidates]))
        self.assertEqual(results.count("approved"), 1, results)
        self.assertTrue(any("approved first" in result for result in results), results)
        self.assertEqual(CashFlowClassificationHead.objects.filter(entry=entry).count(), 1)
        self.assertEqual(entry.cash_classifications.filter(status=CashFlowClassification.APPROVED).count(), 1)
        self.assertEqual(entry.cash_classifications.filter(status=CashFlowClassification.SUBMITTED).count(), 1)
