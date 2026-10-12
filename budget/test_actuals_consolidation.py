from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse

from . import test_actuals_selection as fixtures
from .actuals_consolidation import unresolved_origins
from .actuals_selection import select_source
from .models import BudgetCeiling, BudgetVersion
from .planning_context import build_context
from .services import consolidate_versions, transition_version, ceiling_differences


class ConsolidatedActualsTests(fixtures.ActualsSelectionTests):
    def approved(self, version=None):
        version = version or self.version
        version = transition_version(version, 'submit', self.preparer)
        return transition_version(version, 'approve', self.reviewer, 'Reviewed office proposal')

    def consolidate(self, *sources):
        return consolidate_versions(sources=list(sources), user=self.reviewer,
            title='Combined office proposal', change_explanation='Retain approved office origins')

    def select(self, target):
        return select_source(version=target, actor=self.preparer, fund_id=self.fund.pk,
            center_id=self.center.pk, prefix='half', kind='native', source_id=self.native.public_id,
            expected_state_version=target.state_version, reason='Reviewed combined scope against native certification')

    def test_retained_origins_require_selection_then_support_actual_submission(self):
        self.choose()
        source = self.approved()
        frozen = deepcopy(source.planning_context_snapshot)
        target = self.consolidate(source)
        self.assertEqual(len(unresolved_origins(target)), 1)
        with self.assertRaisesMessage(ValidationError, 'explicitly select'):
            transition_version(target, 'submit', self.preparer)
        self.client.force_login(self.preparer)
        screen = self.client.get(reverse('budget:actuals_sources', args=[target.public_id]),
            {'scope': f'{self.fund.pk}:{self.center.pk}:half'})
        self.assertContains(screen, 'Approved source proposals')
        self.assertContains(screen, source.title)
        target = self.select(target)
        target = transition_version(target, 'submit', self.preparer)
        self.assertEqual(target.planning_context_snapshot['rows'][0]['half_certified']['amount'], '100.00')
        source.refresh_from_db()
        self.assertEqual(source.planning_context_snapshot, frozen)
        self.assertEqual(len(target.actuals_source_origins), 1)

    def test_alternative_office_versions_cannot_be_combined(self):
        self.choose()
        first = self.approved()
        self.adopt('140')
        second = self.make_version(first.budget_call, 2)
        self.add_line(second)
        second = self.approved(second)
        before = BudgetVersion.objects.count()
        with self.assertRaisesMessage(ValidationError, 'one approved proposal version per'):
            self.consolidate(first, second)
        self.assertEqual(BudgetVersion.objects.count(), before)
        self.assertEqual(first.planning_context_snapshot['rows'][0]['half_certified']['amount'], '100.00')
        self.assertEqual(second.planning_context_snapshot['rows'][0]['half_certified']['amount'], '140.00')

    def test_stale_certification_does_not_erase_original_evidence(self):
        self.choose()
        source = self.approved()
        self.journal('AFTER-APPROVED-PROPOSAL', date(2026, 6, 30), Decimal('2'))
        target = self.consolidate(source)
        with self.assertRaisesMessage(ValidationError, 'fresh certification'):
            self.select(target)
        self.assertEqual(next(iter(target.actuals_source_origins.values()))['sources'][0]['explicit_choice']['source_id'], str(self.native.public_id))

    def test_clearing_choice_restores_required_review_and_origins_are_immutable(self):
        self.choose()
        target = self.select(self.consolidate(self.approved()))
        target = select_source(version=target, actor=self.preparer, fund_id=self.fund.pk,
            center_id=self.center.pk, prefix='half', kind='clear', source_id='',
            expected_state_version=target.state_version, reason='Reconsider the combined source')
        self.assertTrue(unresolved_origins(target))
        target.actuals_source_origins = {}
        with self.assertRaisesMessage(ValidationError, 'immutable'):
            target.full_clean()
        BudgetVersion.objects.filter(pk=target.pk).update(actuals_source_origins={})
        with self.assertRaisesMessage(ValidationError, 'creation evidence'):
            build_context(target, self.preparer)

    def test_external_default_is_retained_and_empty_legacy_sources_are_not_backfilled(self):
        self.adopt('140')
        target = self.consolidate(self.approved())
        origin = next(iter(target.actuals_source_origins.values()))['sources'][0]
        self.assertIsNone(origin['explicit_choice'])
        self.assertEqual(origin['evidence'][0]['amount'], '140.00')
        legacy = self.make_version(self.version.budget_call, 2)
        self.add_line(legacy)
        legacy.status = BudgetVersion.APPROVED
        legacy.save(update_fields=['status'])
        self.assertEqual(self.consolidate(legacy).actuals_source_origins, {})

    def test_consolidated_ceiling_does_not_pool_other_office_capacity(self):
        target = self.consolidate(self.approved())
        target.budget_call.ceilings.update(amount=Decimal('999'))
        BudgetCeiling.objects.create(department_id=target.department_id, department_label=target.department_label,
            budget_call=target.budget_call, requesting_department_id=self.requesting_office.pk+10000,
            requesting_department_label='Other office', fund=self.fund, expense_class='MOOE',
            amount=Decimal('100000'), basis='Separate office capacity')
        self.assertEqual(ceiling_differences(target)[0]['difference'], Decimal('-1'))
        with self.assertRaisesMessage(ValidationError, 'exceeds'):
            transition_version(target, 'submit', self.preparer)
