from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from inventory.custody_returns import record_return, confirm_return, cancel_return
from inventory.employee_sources import resolve_employee_custodian
from inventory.models import AssetTransfer
from inventory.services import custody_source, create_asset_transfer
from . import test_grand_custody_returns


@skipUnlessDBFeature("has_select_for_update")
class CustodyReturnRaceTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        test_grand_custody_returns.CustodyReturnTests.setUpTestData.__func__(self)
        test_grand_custody_returns.CustodyReturnTests.setUp(self)

    def fresh(self, actor):
        return get_user_model().objects.get(pk=actor.pk)

    def race(self, *operations):
        barrier = Barrier(len(operations))
        def run(operation):
            connections.close_all()
            try:
                barrier.wait(timeout=15)
                return operation()
            except ValidationError:
                return "conflict"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            jobs = [pool.submit(run, operation) for operation in operations]
            return [job.result(timeout=45) for job in jobs]

    def start(self, request_id):
        return record_return(actor=self.fresh(self.clerk), asset=self.asset, request_id=request_id,
            expected_custody=custody_source(self.asset), data={"transfer_date": timezone.localdate(),
            "reference": "RETURN-RACE", "reason": "Witnessed", "return_condition": "unknown",
            "destination_custodian": "GSO store"})

    def ready(self):
        transfer = self.start(uuid4())
        test_grand_custody_returns.CustodyReturnTests.evidence(self, transfer)
        transfer.refresh_from_db()
        return transfer

    def test_duplicate_requests_create_one_retained_return(self):
        request_id = uuid4()
        results = self.race(lambda: str(self.start(request_id).public_id), lambda: str(self.start(request_id).public_id))
        self.assertEqual(results, [str(request_id), str(request_id)])
        transfer = AssetTransfer.objects.get(kind=AssetTransfer.RETURN)
        self.assertEqual(transfer.return_events.count(), 1)

    def test_return_and_new_employee_handoff_cannot_both_start(self):
        source = resolve_employee_custodian(actor=self.clerk, user_id=self.verifier.pk)
        def handoff():
            return create_asset_transfer(actor=self.fresh(self.clerk), asset=self.asset, data={
                "destination_employee_id": self.verifier.pk, "employee_source_checksum": source["sha256"],
                "transfer_date": timezone.localdate(), "reference": "PAR-RACE", "reason": "New custody"}).kind
        results = self.race(lambda: self.start(uuid4()).kind, handoff)
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.asset.transfers.filter(status=AssetTransfer.PENDING).count(), 1)

    def test_confirmation_and_cancellation_leave_one_consistent_outcome(self):
        transfer = self.ready()
        results = self.race(
            lambda: confirm_return(actor=self.fresh(self.verifier), transfer=transfer, expected_version=2, note="Checked").status,
            lambda: cancel_return(actor=self.fresh(self.clerk), transfer=transfer, expected_version=2, note="Recheck").status)
        self.assertEqual(results.count("conflict"), 1)
        transfer.refresh_from_db()
        self.asset.refresh_from_db()
        accepted = transfer.status == AssetTransfer.ACCEPTED
        self.assertEqual(self.asset.custodian_user_id, None if accepted else self.outsider.pk)
        self.assertEqual(self.asset.last_custody_return_id, transfer.pk if accepted else None)
        self.assertEqual(transfer.return_events.count(), 3)
        self.assertEqual(self.asset.audit_events.filter(action="returned").count(), 1 if accepted else 0)
