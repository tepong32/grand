from copy import deepcopy
from datetime import date

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_actuals_selection as fixtures
from .test_actuals_complete_scope import CompleteScopeSelectionTests
from .historical_forecasts import row_key, source_digest, save_forecast
from .models import BudgetAuditEvent
from .planning_context import build_context, displayed_context
from .services import transition_version, consolidate_versions


class HistoricalForecastTests(fixtures.ActualsSelectionTests):
    new_proposal_account = CompleteScopeSelectionTests.new_proposal_account

    def historical(self):
        self.new_proposal_account()
        self.choose()
        return next(row for row in build_context(self.version, self.preparer)['certified_schedule'] if not row['has_proposal'])

    def save(self, row, **changes):
        args = dict(version=self.version, actor=self.preparer, key=row_key(row),
            expected_state_version=self.version.state_version, expected_source_digest=source_digest(row),
            amount='40', as_of=date(2026, 8, 1), basis='Synthetic department forecast worksheet',
            reason='Reviewed July–December expectation')
        args.update(changes)
        self.version = save_forecast(**args)
        return self.version

    def test_forecast_is_separate_dated_frozen_and_exported(self):
        row = self.historical()
        self.save(row)
        context = build_context(self.version, self.preparer)
        historical = next(item for item in context['certified_schedule'] if not item['has_proposal'])
        self.assertEqual(historical['estimate'], '40.00')
        self.assertEqual(historical['current_total'], '140.00')
        self.assertEqual(historical['proposed'], '0.00')
        self.assertFalse(context['forecast_issues'])
        self.assertIsNone(self.version.lines.get().second_half_estimate)
        self.version = transition_version(self.version, 'submit', self.preparer)
        frozen = deepcopy(self.version.planning_context_snapshot)
        self.client.force_login(self.preparer)
        url = reverse('budget:object_schedule_export', args=[self.version.public_id])
        exported = self.client.get(url)
        self.assertContains(exported, 'Historical forecast evidence')
        self.assertContains(exported, 'Current historical forecast')
        self.assertContains(exported, 'Synthetic department forecast worksheet')
        with self.assertRaisesMessage(ValidationError, 'Return'):
            self.save(row, amount='80')
        self.assertEqual(displayed_context(self.version, self.preparer), frozen)
        self.assertEqual(self.client.get(url).content, exported.content)
        self.version = transition_version(self.version, 'approve', self.reviewer, 'Independent forecast review')
        self.assertEqual(displayed_context(self.version, self.reviewer), frozen)

    def test_zero_date_amount_and_stale_state_validation(self):
        row = self.historical()
        for changes in ({'amount': '-1'}, {'amount': 'NaN'}, {'as_of': date(2025, 8, 1)},
                        {'as_of': date(2026, 12, 1)}, {'basis': ''}, {'expected_source_digest': 'wrong'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.save(row, **changes)
        old_state = self.version.state_version
        self.save(row, amount='0')
        self.assertEqual(self.version.historical_forecasts[row_key(row)]['amount'], '0.00')
        self.assertEqual(next(item for item in build_context(self.version, self.preparer)['certified_schedule']
                              if not item['has_proposal'])['current_total'], '100.00')
        with self.assertRaisesMessage(ValidationError, 'changed'):
            self.save(row, expected_state_version=old_state)

    def test_cleared_actuals_leave_visible_forecast_and_block_submission_until_resolved(self):
        row = self.historical()
        self.save(row)
        self.choose(kind='clear', source_id='')
        context = build_context(self.version, self.preparer)
        self.assertTrue(context['forecast_issues'])
        self.assertEqual(len(context['historical_forecasts']), 1)
        with self.assertRaisesMessage(ValidationError, 'Select the historical'):
            transition_version(self.version, 'submit', self.preparer)
        self.save(row, clear=True)
        self.assertFalse(self.version.historical_forecasts)
        event = BudgetAuditEvent.objects.get(action='historical_forecast_cleared')
        self.assertEqual(event.snapshot['before']['amount'], '40.00')
        self.assertIsNone(event.snapshot['after'])

    def test_new_proposal_line_cannot_double_count_historical_forecast(self):
        row = self.historical()
        self.save(row)
        self.add_line(self.version, '200')
        context = build_context(self.version, self.preparer)
        self.assertTrue(context['forecast_issues'])
        with self.assertRaisesMessage(ValidationError, 'Proposal lines'):
            transition_version(self.version, 'submit', self.preparer)
        with self.assertRaisesMessage(ValidationError, 'without proposal lines'):
            self.save(row)
        self.save(row, clear=True)
        self.assertFalse(build_context(self.version, self.preparer)['forecast_issues'])

    def test_changed_certification_requires_deliberate_forecast_review(self):
        row = self.historical()
        self.save(row)
        self.native = self.decide(self.native_propose(expected_latest=1))
        self.choose()
        context = build_context(self.version, self.preparer)
        self.assertTrue(context['forecast_issues'])
        fresh = next(item for item in context['certified_schedule'] if not item['has_proposal'])
        self.client.force_login(self.preparer)
        exported = self.client.get(reverse('budget:object_schedule_export', args=[self.version.public_id]))
        self.assertContains(exported, 'Selected actual evidence changed')
        with self.assertRaisesMessage(ValidationError, 'Displayed actual evidence changed'):
            self.save(row)
        self.save(fresh)
        self.assertFalse(build_context(self.version, self.preparer)['forecast_issues'])

    def test_consolidation_retains_approved_forecast_and_origin(self):
        row = self.historical()
        self.save(row)
        source = transition_version(self.version, 'submit', self.preparer)
        source = transition_version(source, 'approve', self.reviewer, 'Forecast checked')
        target = consolidate_versions(sources=[source], user=self.reviewer,
            title='Combined forecast', change_explanation='Retain the approved office forecast')
        self.assertEqual(target.historical_forecasts[row_key(row)]['amount'], '40.00')
        self.assertEqual(target.historical_forecasts[row_key(row)]['origin']['proposal'], str(source.public_id))
        self.version = target
        self.choose()
        submitted = transition_version(self.version, 'submit', self.preparer)
        self.assertFalse(submitted.planning_context_snapshot['forecast_issues'])
        self.assertEqual(submitted.planning_context_snapshot['historical_forecasts'], submitted.historical_forecasts)

    def test_http_preview_replay_tamper_csrf_and_uat(self):
        row = self.historical()
        url = reverse('budget:historical_forecast_edit', args=[self.version.public_id, row_key(row)])
        self.client.force_login(self.preparer)
        page = self.client.get(url)
        self.assertContains(page, 'Historical object forecast')
        data = {'preview': page.context['form']['preview'].value(), 'action': 'save', 'amount': '20',
                'as_of': '2026-08-01', 'basis': 'Synthetic HTTP evidence', 'reason': 'Independent estimate basis'}
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.preparer)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.assertEqual(self.client.post(url, {**data, 'preview': data['preview'] + 'tampered'}).status_code, 409)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.version.refresh_from_db()
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.save(row, clear=True)
