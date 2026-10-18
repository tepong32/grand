from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature

from inventory import maintenance_corrections as service
from inventory.models import MaintenanceCorrection as Correction, MaintenanceCorrectionEvent as Event
from inventory.property_determinations import checksum
from . import test_maintenance_corrections as fixtures
from . import test_maintenance_notices as notices


class MaintenanceCorrectionUpgradeTests(TransactionTestCase):
    databases = {'default', 'finance'}

    def test_additive_upgrade_preserves_original_cases_notices_and_two_store_boundary(self):
        fixtures.MaintenanceCorrectionTests.setUpTestData.__func__(type(self))
        fixtures.MaintenanceCorrectionTests.setUp(self)
        notices.MaintenanceNoticeTests.record(self)
        before = notices.service.case_basis(self.case), list(self.case.correction_notices.values())
        default = connections['default']
        finance_tables = set(connections['finance'].introspection.table_names())
        leaves = MigrationExecutor(default).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(default).migrate([('inventory', '0030_maintenance_correction_notices')])
            original_tables = set(default.introspection.table_names())
            self.assertNotIn(Correction._meta.db_table, original_tables)
        finally:
            MigrationExecutor(default).migrate(leaves)
        self.case.refresh_from_db()
        self.assertEqual((notices.service.case_basis(self.case), list(self.case.correction_notices.values())), before)
        self.assertEqual(set(default.introspection.table_names()) - original_tables,
                         {Correction._meta.db_table, Event._meta.db_table})
        self.assertEqual(set(connections['finance'].introspection.table_names()), finance_tables)
        self.assertNotIn(Correction._meta.db_table, finance_tables)


@skipUnlessDBFeature('has_select_for_update')
class MaintenanceCorrectionRaceTests(TransactionTestCase):
    databases = {'default', 'finance'}
    body = fixtures.MaintenanceCorrectionTests.body
    upload = fixtures.MaintenanceCorrectionTests.upload
    values = fixtures.MaintenanceCorrectionTests.values
    propose = fixtures.MaintenanceCorrectionTests.propose
    approve = fixtures.MaintenanceCorrectionTests.approve

    def setUp(self):
        fixtures.MaintenanceCorrectionTests.setUpTestData.__func__(type(self))
        fixtures.MaintenanceCorrectionTests.setUp(self)

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
            return [job.result(timeout=45) for job in jobs]

    def test_competing_exact_retries_retain_one_proposal_and_one_file(self):
        source, _ = service.basis(self.case)
        identity, data = uuid4(), self.values()

        def operation():
            actor = get_user_model().objects.get(pk=self.clerk.pk)
            return str(service.propose(actor=actor, case=self.case, request_id=identity,
                expected_source=checksum(source), data=data, reason='Corrected source',
                source_reference='Retained service report', upload=self.upload()).public_id)

        self.assertEqual(self.race([operation, operation]), [str(identity), str(identity)])
        self.assertEqual(Correction.objects.count(), 1)
        self.assertEqual(len([p for p in Path(self.files.name).rglob('*') if p.is_file()]), 1)

    def test_competing_approvals_cannot_replace_the_same_approved_predecessor(self):
        first, second = self.propose(), self.propose(data=self.values(provider='Competing documentary correction'))

        def operation(row):
            return lambda: service.decide(actor=get_user_model().objects.get(pk=self.reviewer.pk),
                row=row, expected_version=1, action='approved', note='Independent source comparison').status

        result = self.race([operation(first), operation(second)])
        self.assertCountEqual(result, ['approved', 'conflict'])
        self.assertEqual(Correction.objects.filter(status='approved').count(), 1)
        self.assertEqual(Correction.objects.filter(status='proposed').count(), 1)
        self.assertEqual(service.basis(self.case)[1].events.count(), 2)

    def test_notice_and_correction_writers_share_the_locked_document_budget(self):
        for _ in range(19):
            notices.MaintenanceNoticeTests.record(self, upload=self.upload())
        source, _ = service.basis(self.case)

        def correction():
            return service.propose(actor=get_user_model().objects.get(pk=self.clerk.pk), case=self.case,
                request_id=uuid4(), expected_source=checksum(source), data=self.values(), reason='Correct source',
                source_reference='Report', upload=self.upload()).status

        def notice():
            notices.MaintenanceNoticeTests.record(self, actor=get_user_model().objects.get(pk=self.clerk.pk), upload=self.upload())
            return 'notice'

        result = self.race([correction, notice])
        self.assertEqual(result.count('conflict'), 1)
        self.assertEqual(self.case.correction_notices.count() + self.case.reviewed_corrections.count(), 20)
        self.assertEqual(len([p for p in Path(self.files.name).rglob('*') if p.is_file()]), 20)
