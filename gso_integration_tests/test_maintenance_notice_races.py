from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature

from inventory.models import MaintenanceCorrectionNotice as Notice
from . import test_maintenance_notices as fixtures


class MaintenanceNoticeUpgradeTests(TransactionTestCase):
    databases = {'default', 'finance'}

    def test_additive_upgrade_preserves_closed_history_and_database_boundary(self):
        fixtures.MaintenanceNoticeTests.setUpTestData.__func__(type(self))
        fixtures.MaintenanceNoticeTests.setUp(self)
        before = fixtures.service.case_basis(self.case)
        connection = connections['default']
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('inventory', '0029_receipt_quantity_corrections')])
            self.assertNotIn(Notice._meta.db_table, connection.introspection.table_names())
        finally:
            MigrationExecutor(connection).migrate(leaves)
        self.case.refresh_from_db()
        self.assertEqual(fixtures.service.case_basis(self.case), before)
        self.assertIn(Notice._meta.db_table, connection.introspection.table_names())
        self.assertNotIn(Notice._meta.db_table, connections['finance'].introspection.table_names())
        self.assertEqual(Notice.objects.count(), 0)


@skipUnlessDBFeature('has_select_for_update')
class MaintenanceNoticeRaceTests(TransactionTestCase):
    databases = {'default', 'finance'}
    body = fixtures.MaintenanceNoticeTests.body
    upload = fixtures.MaintenanceNoticeTests.upload
    record = fixtures.MaintenanceNoticeTests.record

    def setUp(self):
        fixtures.MaintenanceNoticeTests.setUpTestData.__func__(type(self))
        fixtures.MaintenanceNoticeTests.setUp(self)

    def race(self, operation):
        barrier = Barrier(2)

        def worker():
            connections.close_all()
            try:
                actor = get_user_model().objects.get(pk=self.clerk.pk)
                barrier.wait(timeout=15)
                try:
                    return operation(actor)
                except ValidationError:
                    return 'conflict'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(worker) for _ in range(2)]
            return [job.result(timeout=45) for job in jobs]

    def test_competing_exact_retries_retain_one_notice_and_file(self):
        identity = uuid4()
        results = self.race(lambda actor: str(self.record(actor=actor, request_id=identity,
                                                         upload=self.upload()).public_id))
        self.assertEqual(results, [str(identity), str(identity)])
        self.assertEqual(Notice.objects.count(), 1)
        self.assertEqual(len([p for p in Path(self.files.name).rglob('*') if p.is_file()]), 1)

    def test_competing_uploads_share_the_locked_case_document_budget(self):
        for _ in range(19):
            self.record(upload=self.upload())
        results = self.race(lambda actor: str(self.record(actor=actor, upload=self.upload()).public_id))
        self.assertEqual(results.count('conflict'), 1)
        self.assertEqual(Notice.objects.count(), 20)
        self.assertEqual(len([p for p in Path(self.files.name).rglob('*') if p.is_file()]), 20)
