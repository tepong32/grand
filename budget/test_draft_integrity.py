"""Draft HTTP writes serialize with posting and retain atomic audit evidence."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections, transaction
from django.test import Client
from django.urls import reverse
from datetime import date

from .models import AllotmentOrderLine, AllotmentReleaseOrder, BudgetAuditEvent, ObligationRequest, ObligationRequestLine
from .services import transition_allotment_order, transition_obligation_request


class BudgetDraftFixture:
    def draft(self, kind):
        self.draft_counter = getattr(self, "draft_counter", 0) + 1
        self.authority = self.make_authorized_appropriation("1000", suffix="DRAFT-" + str(self.draft_counter))
        if kind == "allotment":
            item = self.dated_allotment(self.authority, "DRAFT-GUARD", 5, "100", post=False)
            actor = self.preparer
        else:
            self.dated_allotment(self.authority, "DRAFT-EXECUTABLE", 5, "1000")
            item = self.make_obligation_request(self.authority, reference="DRAFT-GUARD", total="100")
            self.add_obligation_line(item, "100")
            actor = self.requester
        client = Client()
        client.force_login(actor)
        return item, client

    def request_data(self, item, client, kind, operation):
        args = [item.public_id]
        suffix = "edit" if operation == "header" else "line_" + operation
        if operation in {"edit", "delete"}:
            args.append(item.lines.get().pk)
        url = reverse("budget:" + kind + "_" + suffix, args=args)
        if operation == "delete":
            return url, {"reason": "Synthetic draft removal"}
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        data = {n: "" if form[n].value() is None else form[n].value() for n in form.fields}
        if operation == "create":
            data.update(appropriation_line=self.authority.schedule_lines.get().pk,
                        movement_type=AllotmentOrderLine.RELEASE if kind == "allotment" else ObligationRequestLine.OBLIGATE,
                        amount="1", remarks="Synthetic new draft line")
        elif "remarks" in data:
            data["remarks"] = "Synthetic draft correction"
        return url, data

    def post_document(self, item, kind):
        if kind == "allotment":
            transition_allotment_order(item, "submit", self.preparer)
            return transition_allotment_order(item, "post", self.authorizer, "Independent synthetic posting")
        transition_obligation_request(item, "submit", self.requester)
        return transition_obligation_request(item, "certify", self.certifier,
                                             "Independent synthetic certification", "OBR-DRAFT-GUARD")

    def financial_state(self, item):
        return (type(item).objects.filter(pk=item.pk).values().get(),
                list(item.lines.order_by("pk").values()), list(item.movements.order_by("pk").values()),
                BudgetAuditEvent.objects.count())


class BudgetDraftViewChecks(BudgetDraftFixture):
    """Owned by the existing AnnualBudgetPreparationTests discovery class."""

    @patch("django.utils.timezone.localdate", new=lambda: date(2027, 1, 10))
    def test_authorized_draft_line_edit_remains_available_for_both_workflows(self):
        for kind in ("allotment", "obligation"):
            with self.subTest(kind=kind):
                item, client = self.draft(kind)
                url, data = self.request_data(item, client, kind, "edit")
                response = client.post(url, data)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(item.lines.get().remarks, "Synthetic draft correction")
                item.refresh_from_db()
                self.assertEqual(item.status, item.DRAFT)

    @patch("django.utils.timezone.localdate", new=lambda: date(2027, 1, 10))
    def test_all_stale_routes_reject_after_posting_without_partial_changes(self):
        for kind in ("allotment", "obligation"):
            item, client = self.draft(kind)
            requests = [self.request_data(item, client, kind, op) for op in ("header", "create", "edit", "delete")]
            item = self.post_document(item, kind)
            before = self.financial_state(item)
            for url, data in requests:
                with self.subTest(kind=kind, url=url):
                    self.assertEqual(client.post(url, data).status_code, 404)
                    self.assertEqual(self.financial_state(item), before)

    @patch("django.utils.timezone.localdate", new=lambda: date(2027, 1, 10))
    def test_rejected_audit_rolls_back_line_and_version_before_rendering_error(self):
        item, client = self.draft("obligation")
        url, data = self.request_data(item, client, "obligation", "edit")
        before = self.financial_state(item)
        with patch("budget.views.record_event", side_effect=ValidationError("Synthetic rejected audit")):
            self.assertEqual(client.post(url, data).status_code, 200)
        self.assertEqual(self.financial_state(item), before)

    @patch("django.utils.timezone.localdate", new=lambda: date(2027, 1, 10))
    def test_foreign_office_cannot_mutate_draft(self):
        item, client = self.draft("allotment")
        url, data = self.request_data(item, client, "allotment", "edit")
        client.force_login(self.outsider)
        before = self.financial_state(item)
        self.assertIn(client.post(url, data).status_code, (403, 404))
        self.assertEqual(self.financial_state(item), before)


class BudgetDraftPostingChecks(BudgetDraftFixture):
    """Owned by the existing QuarterlyPlanningConcurrencyTests discovery class."""

    def draft_worker(self, client, url, data, ready, identity):
        connections.close_all()
        try:
            with connections["finance"].cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                identity.append(cursor.fetchone()[0])
            ready.set()
            return client.post(url, data).status_code
        finally:
            connections.close_all()

    def wait_for_draft_header(self, identity, table, future):
        deadline, tick = monotonic() + 15, Event()
        while monotonic() < deadline:
            with connections["finance"].cursor() as cursor:
                cursor.execute("""SELECT COUNT(*) FROM performance_schema.data_lock_waits w
                    JOIN performance_schema.threads t ON t.THREAD_ID = w.REQUESTING_THREAD_ID
                    JOIN performance_schema.data_locks l ON l.ENGINE = w.ENGINE
                        AND l.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID
                    WHERE t.PROCESSLIST_ID = %s AND l.OBJECT_NAME = %s""", [identity, table])
                if cursor.fetchone()[0]:
                    self.assertFalse(future.done())
                    return
            if future.done():
                self.fail("Draft mutation completed without waiting for its owning financial header")
            tick.wait(.01)
        self.fail("No native owning-header wait observed")

    def assert_draft_post_race(self, kind, operation):
        item, client = self.draft(kind)
        url, data = self.request_data(item, client, kind, operation)
        ready, identity = Event(), []
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic(using="finance"):
                item = self.post_document(item, kind)
                before = self.financial_state(item)
                future = pool.submit(self.draft_worker, client, url, data, ready, identity)
                self.assertTrue(ready.wait(15))
                self.wait_for_draft_header(identity[0], item._meta.db_table, future)
            self.assertEqual(future.result(timeout=15), 404)
        self.assertEqual(self.financial_state(item), before)

    def test_allotment_header_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('allotment', 'header')

    def test_allotment_create_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('allotment', 'create')

    def test_allotment_edit_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('allotment', 'edit')

    def test_allotment_delete_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('allotment', 'delete')

    def test_obligation_header_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('obligation', 'header')

    def test_obligation_create_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('obligation', 'create')

    def test_obligation_edit_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('obligation', 'edit')

    def test_obligation_delete_cannot_write_after_concurrent_posting(self):
        self.assert_draft_post_race('obligation', 'delete')
