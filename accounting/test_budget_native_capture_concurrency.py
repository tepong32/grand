from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest import skipUnless

from django.db import close_old_connections, connections, transaction
from django.test import TransactionTestCase

from . import test_budget_native_sources as fixtures
from . import budget_native_sources as sources


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL consistent statement reads")
class NativeBudgetCaptureConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.NativeBudgetSourceTests.employee.__func__)
    make_call = fixtures.NativeBudgetSourceTests.make_call
    make_version = fixtures.NativeBudgetSourceTests.make_version
    add_line = fixtures.NativeBudgetSourceTests.add_line
    add_ceiling = fixtures.NativeBudgetSourceTests.add_ceiling
    grant = fixtures.NativeBudgetSourceTests.grant
    journal = fixtures.NativeBudgetSourceTests.journal
    capture = fixtures.NativeBudgetSourceTests.capture

    def setUp(self):
        fixtures.NativeBudgetSourceTests.setUpTestData.__func__(type(self))
        fixtures.NativeBudgetSourceTests.setUp(self)

    def test_commit_after_select_cannot_mix_financial_rows_or_live_metadata(self):
        self.journal("BEFORE", date(2026, 6, 30), Decimal("200"))
        old_title = self.account.title
        committed = []

        def post_and_change_metadata():
            close_old_connections()
            try:
                with transaction.atomic(using="finance"):
                    self.journal("DURING-CAPTURE", date(2026, 6, 30), Decimal("75"))
                    type(self.account).objects.filter(pk=self.account.pk).update(title="Changed concurrently")
            finally:
                connections.close_all()

        def interleave(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.lstrip().upper().startswith("SELECT") and not committed:
                # SELECT has acquired its snapshot; commit before the capture can
                # assemble evidence or issue an accidental lazy metadata query.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(post_and_change_metadata).result(timeout=30)
                committed.append(True)
            return result

        with connections["finance"].execute_wrapper(interleave):
            captured = self.capture()
        self.assertEqual(committed, [True])
        self.assertEqual(captured["payload"]["controls"]["debit"], "200.00")
        self.assertEqual(captured["payload"]["journals"][0]["lines"][0]["account"]["title"], old_title)
        self.assertFalse(sources.is_current(captured, self.maker))
        after = self.capture()["payload"]
        self.assertEqual(after["controls"]["debit"], "275.00")
        self.assertEqual({entry["lines"][0]["account"]["title"] for entry in after["journals"]},
                         {"Changed concurrently"})
