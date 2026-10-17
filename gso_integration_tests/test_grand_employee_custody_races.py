from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from inventory.employee_sources import resolve_employee_custodian
from inventory.models import AssetTransfer
from inventory.services import create_asset_transfer, acknowledge_asset_transfer, cancel_asset_transfer
from . import test_grand_employee_custody


@skipUnlessDBFeature("has_select_for_update")
class EmployeeCustodyRaceTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        test_grand_employee_custody.GrandEmployeeCustodyTests.setUpTestData.__func__(self)
        self.data = {"destination_employee_id": self.outsider.pk,
            "employee_source_checksum": resolve_employee_custodian(actor=self.clerk, user_id=self.outsider.pk)["sha256"],
            "transfer_date": timezone.localdate(), "reason": "Concurrent handoff", "reference": "PAR-RACE"}

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

    def fresh(self, actor):
        return get_user_model().objects.get(pk=actor.pk)

    def test_duplicate_signed_request_records_one_handoff(self):
        request_id = uuid4()
        def start():
            return str(create_asset_transfer(actor=self.fresh(self.clerk), asset=self.asset,
                data=self.data, request_id=request_id).public_id)
        self.assertEqual(self.race(start, start), [str(request_id), str(request_id)])
        self.assertEqual(AssetTransfer.objects.count(), 1)

    def test_acknowledgment_and_cancellation_record_only_one_outcome(self):
        transfer = create_asset_transfer(actor=self.clerk, asset=self.asset, data=self.data)
        def accept():
            return acknowledge_asset_transfer(actor=self.fresh(self.outsider), transfer=transfer).status
        def cancel():
            return cancel_asset_transfer(actor=self.fresh(self.clerk), transfer=transfer, reason="Recheck").status
        results = self.race(accept, cancel)
        self.assertEqual(results.count("conflict"), 1)
        transfer.refresh_from_db()
        self.asset.refresh_from_db()
        accepted = transfer.status == AssetTransfer.ACCEPTED
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk if accepted else None)
        self.assertEqual(self.asset.audit_events.count(), 1 if accepted else 0)
