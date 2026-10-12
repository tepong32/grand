from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse

from accounting.models import Fund, ResponsibilityCenter
from . import test_actuals_selection as fixtures
from .actuals_consolidation import unresolved_origins
from .actuals_scopes import available_scopes
from .actuals_selection import select_source
from .planning_context import build_context, displayed_context
from .services import consolidate_versions, transition_version


class OfficeScopeActualsTests(fixtures.ActualsSelectionTests):
    def another_center(self, office=None):
        return ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='HIST-CENTER', name='Historical office activity',
            office_id=office or self.requesting_office.pk)

    def split_to(self, center):
        rows = self.rows()
        rows[0]['amount'] = '60'
        rows.append(dict(rows[0], amount='40', center_id=center.pk))
        self.review(self.propose(proposals=[{'entry_id': self.entry.pk, 'expected_latest': 1, 'allocations': rows}]))
        self.native = self.decide(self.native_propose(expected_latest=1))

    def test_native_history_in_another_center_is_discovered_and_frozen(self):
        center = self.another_center()
        self.split_to(center)
        key = f'{self.fund.pk}:{center.pk}:half'
        scopes, errors = available_scopes(self.version, self.preparer)
        self.assertFalse(errors)
        self.assertIn(key, scopes)
        self.choose(center_id=center.pk)
        context = build_context(self.version, self.preparer)
        historical = next(row for row in context['certified_schedule'] if row['center_id'] == center.pk)
        self.assertEqual(historical['half_amount'], '40.00')
        self.assertEqual(historical['proposed'], '0.00')
        self.assertFalse(historical['has_proposal'])
        self.assertIsNone(historical['prior_amount'])
        self.assertIsNone(historical['estimate'])
        self.assertIsNone(historical['current_total'])
        self.version = transition_version(self.version, 'submit', self.preparer)
        frozen = deepcopy(self.version.planning_context_snapshot)
        self.client.force_login(self.preparer)
        url = reverse('budget:object_schedule_export', args=[self.version.public_id])
        exported = self.client.get(url)
        self.assertContains(exported, 'HIST-CENTER')
        self.assertContains(exported, '40.00')
        self.assertContains(exported, 'No proposal line')
        self.journal('LATER-OFFICE-SOURCE', date(2026, 6, 30), Decimal('7'))
        self.assertEqual(displayed_context(self.version, self.preparer), frozen)
        self.assertEqual(self.client.get(url).content, exported.content)
        self.assertEqual(frozen['selected_actual_scopes'][key]['rows'][0]['amount'], '40.00')

    def test_unrepresented_office_is_not_discovered_or_selectable(self):
        center = self.another_center(self.budget_office.pk)
        self.split_to(center)
        scopes, _ = available_scopes(self.version, self.preparer)
        self.assertNotIn(f'{self.fund.pk}:{center.pk}:half', scopes)
        with self.assertRaisesMessage(ValidationError, 'represented'):
            self.choose(center_id=center.pk)

    def test_external_history_in_another_fund_requires_explicit_selection(self):
        center = self.another_center()
        fund = Fund.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='HIST-FUND', name='Synthetic historic fund')
        adopted = self.adopt('140', fund_id=fund.pk, center_id=center.pk)
        key = f'{fund.pk}:{center.pk}:half'
        scopes, _ = available_scopes(self.version, self.preparer)
        self.assertIn(key, scopes)
        self.client.force_login(self.preparer)
        screen = self.client.get(reverse('budget:actuals_sources', args=[self.version.public_id]), {'scope': key})
        self.assertContains(screen, 'Adopted external certificate')
        self.choose(fund_id=fund.pk, center_id=center.pk, kind='external', source_id=adopted.public_id)
        schedule = build_context(self.version, self.preparer)['certified_schedule']
        historical = next(row for row in schedule if row['fund_id'] == fund.pk)
        self.assertEqual(historical['half_amount'], '140.00')
        self.assertEqual(historical['fund_code'], 'HIST-FUND')
        self.assertEqual(historical['center_code'], 'HIST-CENTER')

    def test_historical_context_is_available_before_any_proposed_amount(self):
        self.version.lines.all().delete()
        self.choose()
        context = build_context(self.version, self.preparer)
        self.assertEqual(context['rows'], [])
        self.assertEqual(context['certified_schedule'][0]['half_amount'], '100.00')
        self.assertEqual(context['certified_schedule'][0]['proposed'], '0.00')
        self.assertIsNone(context['certified_schedule'][0]['estimate'])

    def test_consolidation_requires_review_of_historical_only_scope(self):
        center = self.another_center()
        self.split_to(center)
        self.choose(center_id=center.pk)
        source = transition_version(self.version, 'submit', self.preparer)
        source = transition_version(source, 'approve', self.reviewer, 'Independent historical context review')
        target = consolidate_versions(sources=[source], user=self.reviewer,
            title='Combined historical scope', change_explanation='Retain office history')
        key = f'{self.fund.pk}:{center.pk}:half'
        self.assertIn(key, unresolved_origins(target))
        self.assertIn(key, available_scopes(target, self.preparer)[0])
        with self.assertRaisesMessage(ValidationError, 'explicitly select'):
            transition_version(target, 'submit', self.preparer)
        target = select_source(version=target, actor=self.preparer, fund_id=self.fund.pk,
            center_id=center.pk, prefix='half', kind='native', source_id=self.native.public_id,
            expected_state_version=target.state_version, reason='Reviewed retained historical office scope')
        self.assertFalse(unresolved_origins(target))
        submitted = transition_version(target, 'submit', self.preparer)
        self.assertTrue(any(row['center_id'] == center.pk for row in submitted.planning_context_snapshot['certified_schedule']))

    def test_export_does_not_reconstruct_legacy_or_cross_office_context(self):
        self.client.force_login(self.preparer)
        url = reverse('budget:object_schedule_export', args=[self.version.public_id])
        self.assertEqual(self.client.get(url).status_code, 409)
        self.choose()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.maker)
        self.assertIn(self.client.get(url).status_code, (403, 404))
