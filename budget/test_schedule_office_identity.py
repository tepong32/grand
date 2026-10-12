from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse

from accounting.models import ResponsibilityCenter
from departments.models import Department
from . import actuals_selection
from . import test_actuals_selection as fixtures
from .models import BudgetVersion
from .planning_context import build_context, displayed_context
from .services import transition_version
from .test_historical_forecasts import HistoricalForecastTests


class ScheduleOfficeIdentityTests(fixtures.ActualsSelectionTests):
    def test_submitted_office_and_export_survive_setup_rename_and_remap(self):
        self.choose()
        self.version = transition_version(self.version, 'submit', self.preparer)
        frozen = deepcopy(self.version.planning_context_snapshot)
        row = frozen['certified_schedule'][0]
        self.assertEqual(row['office_id'], self.requesting_office.pk)
        self.assertEqual(row['office_label'], self.requesting_office.name)
        self.client.force_login(self.preparer)
        url = reverse('budget:object_schedule_export', args=[self.version.public_id])
        before = self.client.get(url)
        self.assertContains(before, 'Captured office ID')
        self.assertContains(before, self.requesting_office.name)
        Department.objects.filter(pk=self.requesting_office.pk).update(name='Renamed after submission')
        ResponsibilityCenter.objects.filter(pk=self.center.pk).update(office_id=self.budget_office.pk)
        self.assertEqual(displayed_context(self.version, self.preparer), frozen)
        self.assertEqual(self.client.get(url).content, before.content)

    def test_external_and_proposed_rows_capture_the_same_office(self):
        adopted = self.adopt('140')
        self.choose(kind='external', source_id=adopted.public_id)
        row = build_context(self.version, self.preparer)['certified_schedule'][0]
        self.assertTrue(row['has_proposal'])
        self.assertEqual(row['office_id'], row['half_rows'][0]['scope']['office_id'])
        self.assertEqual(row['office_label'], self.requesting_office.name)

    def test_mapping_change_between_source_validation_and_projection_is_rejected(self):
        self.choose()
        resolve = actuals_selection.resolve

        def changed(*args, **kwargs):
            result = resolve(*args, **kwargs)
            ResponsibilityCenter.objects.filter(pk=self.center.pk).update(office_id=self.budget_office.pk)
            return result

        with patch.object(actuals_selection, 'resolve', side_effect=changed):
            with self.assertRaisesMessage(ValidationError, 'office mapping changed'):
                build_context(self.version, self.preparer)

    def test_historical_only_mapping_change_after_validation_is_rejected(self):
        self.version.lines.all().delete()
        self.choose()
        resolve = actuals_selection.resolve

        def changed(*args, **kwargs):
            result = resolve(*args, **kwargs)
            ResponsibilityCenter.objects.filter(pk=self.center.pk).update(office_id=self.budget_office.pk)
            return result

        with patch.object(actuals_selection, 'resolve', side_effect=changed):
            with self.assertRaisesMessage(ValidationError, 'captured office identity'):
                build_context(self.version, self.preparer)

    def test_proposal_only_unmapped_center_is_missing_not_requesting_office(self):
        self.choose()
        center = ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='UNMAPPED', name='Unmapped proposal center')
        self.line.responsibility_center = center
        self.line.save(update_fields=('responsibility_center',))
        schedule = build_context(self.version, self.preparer)['certified_schedule']
        proposed = next(row for row in schedule if row['has_proposal'])
        self.assertIsNone(proposed['office_id'])
        self.assertEqual(proposed['office_label'], '')
        self.assertEqual(next(row for row in schedule if not row['has_proposal'])['office_id'], self.requesting_office.pk)

    def test_legacy_frozen_schedule_is_not_backfilled_or_export_extended(self):
        self.choose()
        self.version = transition_version(self.version, 'submit', self.preparer)
        legacy = deepcopy(self.version.planning_context_snapshot)
        legacy['schema'] = 6
        for row in legacy['certified_schedule']:
            row.pop('office_id')
            row.pop('office_label')
        # Reproduce a previously retained schema-6 snapshot; no live reconstruction.
        BudgetVersion.objects.filter(pk=self.version.pk).update(planning_context_snapshot=legacy)
        self.version.refresh_from_db()
        self.assertEqual(displayed_context(self.version, self.preparer), legacy)
        self.client.force_login(self.preparer)
        response = self.client.get(reverse('budget:object_schedule_export', args=[self.version.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Captured office ID')


class ForecastOfficeIdentityTests(HistoricalForecastTests):
    def test_clearing_source_preserves_forecast_office_without_live_reassignment(self):
        row = self.historical()
        self.save(row)
        self.choose(kind='clear', source_id='')
        ResponsibilityCenter.objects.filter(pk=self.center.pk).update(office_id=self.budget_office.pk)
        context = build_context(self.version, self.preparer)
        orphan = next(item for item in context['certified_schedule'] if item.get('historical_forecast'))
        self.assertEqual(orphan['office_id'], self.requesting_office.pk)
        self.assertEqual(orphan['office_label'], self.requesting_office.name)
        self.assertTrue(orphan['forecast_problem'])
        self.assertIsNone(orphan['current_total'])
