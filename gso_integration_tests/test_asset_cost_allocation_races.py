from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature
from inventory.receipt_amendments import record_amendment, decide_amendment, amendment_basis
from inventory_finance import asset_cost_allocations as service
from inventory_finance.models import AssetCostAllocation as Allocation, AssetCostAllocationEvent as Event
from inventory.property_determinations import checksum
from . import test_asset_cost_allocations as fixtures


class AssetCostAllocationUpgradeTests(TransactionTestCase):
    databases = {'default', 'finance'}
    accept = fixtures.AssetCostAllocationTests.accept
    upload = fixtures.AssetCostAllocationTests.upload
    body = fixtures.AssetCostAllocationTests.body

    def test_additive_upgrade_retains_receipt_asset_and_finance_store(self):
        fixtures.AssetCostAllocationTests.setUpTestData.__func__(type(self))
        fixtures.AssetCostAllocationTests.setUp(self)
        before = service.source(self.line)
        default = connections['default']
        finance_tables = set(connections['finance'].introspection.table_names())
        leaves = MigrationExecutor(default).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(default).migrate([('inventory_finance', '0007_receipt_quantity_correction_basis')])
            original_tables = set(default.introspection.table_names())
            self.assertNotIn(Allocation._meta.db_table, original_tables)
        finally:
            MigrationExecutor(default).migrate(leaves)
        self.line.refresh_from_db()
        self.assertEqual(service.source(self.line), before)
        self.assertEqual(set(default.introspection.table_names()) - original_tables, {Allocation._meta.db_table, Event._meta.db_table})
        self.assertEqual(set(connections['finance'].introspection.table_names()), finance_tables)
        self.assertNotIn(Allocation._meta.db_table, finance_tables)


@skipUnlessDBFeature('has_select_for_update')
class AssetCostAllocationRaceTests(TransactionTestCase):
    databases = {'default', 'finance'}
    body = fixtures.AssetCostAllocationTests.body
    upload = fixtures.AssetCostAllocationTests.upload
    accept = fixtures.AssetCostAllocationTests.accept
    entries = fixtures.AssetCostAllocationTests.entries
    propose = fixtures.AssetCostAllocationTests.propose
    decide = fixtures.AssetCostAllocationTests.decide

    def setUp(self):
        fixtures.AssetCostAllocationTests.setUpTestData.__func__(type(self))
        fixtures.AssetCostAllocationTests.setUp(self)

    def race(self, operations):
        barrier = Barrier(2)

        def worker(operation):
            connections.close_all()
            try:
                barrier.wait(timeout=15)
                try:
                    return operation()
                except ValidationError:
                    return 'conflict'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(worker, operation) for operation in operations]
            return [job.result(timeout=60) for job in jobs]

    def test_competing_exact_retries_keep_one_row_and_one_private_file(self):
        identity, expected = uuid4(), checksum(service.basis(self.line)[0])

        def operation():
            row = service.propose(actor=get_user_model().objects.get(pk=self.clerk.pk), line=self.line,
                finance_department_id=self.finance.pk, request_id=identity, expected_basis=expected,
                entries=self.entries(), allocation_basis='Explicit synthetic component amounts', upload=self.upload())
            return str(row.public_id)

        self.assertEqual(self.race([operation, operation]), [str(identity), str(identity)])
        self.assertEqual(Allocation.objects.count(), 1)
        self.assertEqual(len(list((Path(self.files.name)/'inventory/asset-cost-allocations').rglob('*.pdf'))), 1)

    def test_competing_reviews_cannot_both_replace_one_approved_predecessor(self):
        first, second = self.propose(), self.propose(entries=self.entries(first='60.00', second='40.00'))

        def operation(row):
            return lambda: service.decide(actor=get_user_model().objects.get(pk=self.accountant.pk), row=row,
                expected_version=1, action='approved', note='Independent documentary review').status

        self.assertCountEqual(self.race([operation(first), operation(second)]), ['approved', 'conflict'])
        self.assertEqual(Allocation.objects.filter(status='approved').count(), 1)
        self.assertEqual(service.basis(self.line)[1].events.count(), 2)

    def test_pending_source_correction_and_approval_share_the_receipt_lock(self):
        row = self.propose()
        amendment = record_amendment(actor=self.clerk, line=self.line, request_id=uuid4(),
            expected_basis=amendment_basis(self.line), unit_cost='50.00', reference='Corrected source',
            reason='Actual documentary correction', upload=self.upload())

        def correction():
            return decide_amendment(actor=get_user_model().objects.get(pk=self.reviewer.pk), amendment=amendment,
                expected_version=1, action='approve', note='Independent invoice correction').status

        def allocation():
            return service.decide(actor=get_user_model().objects.get(pk=self.accountant.pk), row=row,
                expected_version=1, action='approved', note='Independent documentary allocation review').status

        self.assertEqual(self.race([correction, allocation]), ['approved', 'conflict'])
        row.refresh_from_db()
        self.assertEqual(row.status, 'proposed')

    def test_competing_proposals_cannot_exceed_the_retained_document_budget(self):
        for _ in range(19):
            self.propose()
        expected = checksum(service.basis(self.line)[0])

        def operation():
            return service.propose(actor=get_user_model().objects.get(pk=self.clerk.pk), line=self.line,
                finance_department_id=self.finance.pk, request_id=uuid4(), expected_basis=expected,
                entries=self.entries(), allocation_basis='Explicit component statement', upload=self.upload()).status

        self.assertCountEqual(self.race([operation, operation]), ['proposed', 'conflict'])
        self.assertEqual(Allocation.objects.count(), 20)
        self.assertEqual(len(list((Path(self.files.name)/'inventory/asset-cost-allocations').rglob('*.pdf'))), 20)
