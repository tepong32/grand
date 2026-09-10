from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections, close_old_connections
from django.test import TransactionTestCase

from . import statement_services, test_statement_notes
from .models import FinanceStatementNoteSet


@skipUnless(connections["default"].vendor == "mysql", "Requires native MySQL row locks")
class StatementPackageConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(test_statement_notes.StatementNotesAndReferenceComparisonTests.employee.__func__)
    definition = classmethod(test_statement_notes.StatementNotesAndReferenceComparisonTests.definition.__func__)
    statement_run = classmethod(test_statement_notes.StatementNotesAndReferenceComparisonTests.statement_run.__func__)
    make_note_set = test_statement_notes.StatementNotesAndReferenceComparisonTests.make_note_set

    def setUp(self):
        test_statement_notes.StatementNotesAndReferenceComparisonTests.setUpTestData.__func__(type(self))

    def test_competing_approvals_leave_only_newest_version_approved(self):
        candidates = [self.make_note_set(confirmed=True), self.make_note_set(confirmed=True)]
        for candidate in candidates:
            statement_services.submit_note_set(candidate, self.preparer)
        barrier = Barrier(2, timeout=20)
        original = statement_services._lock_note_department

        def synchronize(department_id):
            barrier.wait()
            return original(department_id)

        def approve(pk):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.reviewer.pk)
                package = FinanceStatementNoteSet.objects.get(pk=pk)
                try:
                    statement_services.review_note_set(package, actor, action="approve", note="Independent package review")
                    return "approved"
                except ValidationError as exc:
                    return "; ".join(exc.messages)
            finally:
                connections.close_all()

        with patch.object(statement_services, "_lock_note_department", synchronize):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(approve, [record.pk for record in candidates]))
        self.assertTrue(all(result == "approved" or "newer note package" in result for result in results), results)
        approved = FinanceStatementNoteSet.objects.get(status=FinanceStatementNoteSet.APPROVED)
        self.assertEqual(approved.version, 2)
