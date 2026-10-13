from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from . import test_version_identity as fixtures
from .models import BudgetCall


class VersionIdentityMigrationTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(fixtures.VersionIdentityTests.employee.__func__)
    make_call = fixtures.VersionIdentityTests.make_call

    def test_populated_upgrade_preserves_versions_lines_and_generated_values(self):
        fixtures.VersionIdentityTests.setUpTestData.__func__(type(self))
        call = self.make_call(BudgetCall.PUBLISHED)
        connection = connections['finance']
        before = [('budget', '0012_actuals_source_origins')]
        after = [('budget', '0013_combined_version_identity')]
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes('budget')
        MigrationExecutor(connection).migrate(before)
        apps = MigrationExecutor(connection).loader.project_state(before).apps
        Version = apps.get_model('budget', 'BudgetVersion')
        values = dict(department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call_id=call.pk, fiscal_year_id=self.fiscal_year.pk, version=1,
            title='Retained populated upgrade', change_explanation='Keep exact source history',
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        try:
            combined = Version.objects.using('finance').create(kind='executive', **values)
            office = Version.objects.using('finance').create(kind='department',
                requesting_department_id=self.requesting_office.pk, **values)
            Audit = apps.get_model('budget', 'BudgetAuditEvent')
            audit = Audit.objects.using('finance').create(department_id=self.budget_office.pk,
                department_label=self.budget_office.name, target_type='BudgetVersion',
                target_id=str(combined.public_id), action='created',
                actor_id=self.preparer.pk, actor_label=self.preparer.username,
                snapshot={'retained': ['exact', 'history']})
            line = apps.get_model('budget', 'BudgetProposalLine').objects.using('finance').create(
                department_id=self.budget_office.pk, department_label=self.budget_office.name,
                version=combined, fund_id=self.fund.pk, responsibility_center_id=self.center.pk,
                account_id=self.account.pk, expense_class='MOOE', particulars='Retained line', amount='125.00')
            MigrationExecutor(connection).migrate(after)
            updated = MigrationExecutor(connection).loader.project_state(after).apps
            NewVersion = updated.get_model('budget', 'BudgetVersion')
            self.assertEqual(NewVersion.objects.using('finance').get(pk=combined.pk).combined_version_number, 1)
            self.assertIsNone(NewVersion.objects.using('finance').get(pk=office.pk).combined_version_number)
            self.assertEqual(NewVersion.objects.using('finance').get(pk=combined.pk).change_explanation,
                             'Keep exact source history')
            retained = updated.get_model('budget', 'BudgetAuditEvent').objects.using('finance').get(pk=audit.pk)
            self.assertEqual(retained.target_id, str(combined.public_id))
            self.assertEqual(retained.snapshot, {'retained': ['exact', 'history']})
            retained_line = updated.get_model('budget', 'BudgetProposalLine').objects.using('finance').get(pk=line.pk)
            self.assertEqual(retained_line.version_id, combined.pk)
            self.assertEqual(str(retained_line.amount), '125.00')
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_duplicate_preflight_preserves_both_historical_rows(self):
        fixtures.VersionIdentityTests.setUpTestData.__func__(type(self))
        call = self.make_call(BudgetCall.PUBLISHED)
        connection = connections['finance']
        before = [('budget', '0012_actuals_source_origins')]
        after = [('budget', '0013_combined_version_identity')]
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes('budget')
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        Version = apps.get_model('budget', 'BudgetVersion')
        values = dict(department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call_id=call.pk, fiscal_year_id=self.fiscal_year.pk, kind='executive', version=1,
            title='Synthetic retained duplicate', change_explanation='Preflight must preserve this evidence',
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        first = second = None
        try:
            first = Version.objects.using('finance').create(**values)
            second = Version.objects.using('finance').create(**values)
            with self.assertRaisesMessage(RuntimeError, 'controlled investigation'):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(Version.objects.using('finance').filter(pk__in=[first.pk, second.pk]).count(), 2)
            self.assertEqual(set(Version.objects.using('finance').values_list('change_explanation', flat=True)),
                             {'Preflight must preserve this evidence'})
        finally:
            # Only synthetic test rows are removed to restore the test schema.
            Version.objects.using('finance').filter(pk__in=[v.pk for v in (first, second) if v]).delete()
            MigrationExecutor(connection).migrate(latest)
