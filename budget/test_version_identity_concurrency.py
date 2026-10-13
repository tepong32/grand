from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from accounting import test_budget_attribution_concurrency as races
from accounting.models import ResponsibilityCenter
from . import test_version_identity as fixtures
from .models import BudgetCall, BudgetVersion, BudgetCeiling
from .services import consolidate_versions, create_version_draft, transition_version


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native annual-call creation locks')
class VersionIdentityConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(fixtures.VersionIdentityTests.employee.__func__)
    make_call = fixtures.VersionIdentityTests.make_call
    make_version = fixtures.VersionIdentityTests.make_version
    add_line = fixtures.VersionIdentityTests.add_line
    draft = fixtures.VersionIdentityTests.draft
    race = races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        fixtures.VersionIdentityTests.setUpTestData.__func__(type(self))
        self.call = self.make_call(BudgetCall.PUBLISHED)
        self.sources = []
        for number, office in enumerate((self.requesting_office, self.other_office), 1):
            source = self.make_version(self.call, number)
            source.requesting_department_id = office.pk
            source.requesting_department_label = office.name
            source.status = BudgetVersion.APPROVED
            source.save()
            line = self.add_line(source)
            if number == 2:
                center = ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
                    department_label=self.accounting_office.name, code='HR', name=office.name, office_id=office.pk)
                line.responsibility_center = center; line.program = None
                line.save(update_fields=['responsibility_center', 'program'])
            self.sources.append(source)

    def consolidate(self, number):
        return consolidate_versions(sources=[self.sources[number-1]], user=self.reviewer,
            title=f'Concurrent combined proposal {number}', change_explanation='Distinct approved source set')

    def test_disjoint_sources_receive_distinct_sequential_executive_versions(self):
        result = self.race(lambda number: self.consolidate(number).version)
        self.assertCountEqual(result, [1, 2])
        targets = BudgetVersion.objects.filter(kind=BudgetVersion.EXECUTIVE).order_by('version')
        self.assertEqual(list(targets.values_list('version', flat=True)), [1, 2])
        self.assertEqual({target.source_links.get().source_version_id for target in targets}, {s.pk for s in self.sources})

    def test_manual_creation_competes_with_automatic_number_without_duplicate(self):
        def action(number):
            if number == 1:
                create_version_draft(self.draft(), self.preparer)
                return 'manual'
            return f'auto:{self.consolidate(2).version}'
        result = self.race(action)
        self.assertTrue(any(str(value).startswith('auto:') for value in result), result)
        numbers = list(BudgetVersion.objects.filter(kind=BudgetVersion.EXECUTIVE).values_list('version', flat=True))
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(sorted(numbers), [1, 2] if 'manual' in result else [1])

    def test_overlapping_source_sets_do_not_invert_source_and_call_locks(self):
        def action(number):
            return consolidate_versions(sources=self.sources if number == 1 else [self.sources[1]],
                user=self.reviewer, title=f'Overlapping scope {number}',
                change_explanation='Whole source set locked before annual call').version
        self.assertCountEqual(self.race(action), [1, 2])

    def test_source_approval_and_consolidation_share_version_then_call_order(self):
        source = self.sources[0]
        source.status = BudgetVersion.DRAFT
        source.save(update_fields=['status'])
        BudgetCeiling.objects.create(department_id=self.budget_office.pk,
            department_label=self.budget_office.name, budget_call=self.call,
            requesting_department_id=self.requesting_office.pk,
            requesting_department_label=self.requesting_office.name,
            fund=self.fund, expense_class='MOOE', amount='100000', basis='Synthetic reviewed ceiling')
        source = transition_version(source, 'submit', self.preparer)
        def action(number):
            if number == 1:
                transition_version(source, 'approve', self.reviewer, 'Independent source approval')
                return 'approved'
            self.consolidate(1)
            return 'consolidated'
        result = self.race(action)
        self.assertIn('approved', result)
        self.assertTrue('consolidated' in result or any('Only approved' in str(value) for value in result), result)
        self.assertEqual(BudgetVersion.objects.filter(kind=BudgetVersion.EXECUTIVE).count(),
                         1 if 'consolidated' in result else 0)

    def test_manual_successor_locks_predecessor_before_call_and_foreign_key_insert(self):
        def action(number):
            if number == 1:
                draft = self.draft(3, kind=BudgetVersion.DEPARTMENT, office=self.requesting_office.pk)
                draft.supersedes = self.sources[0]
                create_version_draft(draft, self.preparer)
                return 'successor'
            self.consolidate(1)
            return 'consolidated'
        self.assertCountEqual(self.race(action), ['successor', 'consolidated'])
