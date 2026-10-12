from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.urls import reverse

from accounting import budget_attributions
from accounting.services import create_reversal, submit_entry, post_entry
from . import test_actuals_selection as fixtures
from .models import BudgetCeiling
from .planning_context import build_context, displayed_context
from .services import transition_version


class NativeObjectSelectionTests(fixtures.ActualsSelectionTests):
    def multiple_objects(self):
        rows = self.rows()
        rows[0]['amount'] = '60'
        rows.append(dict(rows[0], amount='40', expense_class='FE', basis='Explicit synthetic second object portion'))
        self.review(self.propose(proposals=[{'entry_id': self.entry.pk, 'expected_latest': 1, 'allocations': rows}]))
        self.native = self.decide(self.native_propose(expected_latest=1))
        other = self.add_line(self.version, '100')
        other.expense_class = 'FE'; other.save(update_fields=('expense_class',))
        BudgetCeiling.objects.create(department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call=self.call, requesting_department_id=self.requesting_office.pk,
            requesting_department_label=self.requesting_office.name, fund=self.fund, expense_class='FE',
            amount=Decimal('1000'), basis='Synthetic object-class ceiling')
        return other

    def test_distinct_objects_sum_once_and_survive_submission_export(self):
        self.multiple_objects(); self.choose()
        context = build_context(self.version, self.preparer)
        row = context['rows'][0]
        self.assertEqual(len(context['rows']), 1)
        self.assertEqual(row['half_amount'], '100.00')  # Unclassified ledger activity is not repeated per object.
        self.assertEqual(row['half_certified']['amount'], '100.00')
        self.assertEqual([(part['expense_class'], part['amount']) for part in row['half_certified']['object_rows']],
                         [('FE', '40.00'), ('MOOE', '60.00')])
        self.assertTrue(row['half_certified_evidence']['matches_proposal_classes'])
        schedule = context['certified_schedule']
        self.assertEqual([(part['expense_class'], part['half_amount']) for part in schedule],
                         [('FE', '40.00'), ('MOOE', '60.00')])
        self.assertEqual(sum(Decimal(part['half_amount']) for part in schedule), Decimal('100'))
        self.version = transition_version(self.version, 'submit', self.preparer)
        frozen = deepcopy(self.version.planning_context_snapshot)
        self.client.force_login(self.preparer)
        url = reverse('budget:planning_context_export', args=[self.version.public_id])
        before = self.client.get(url)
        self.assertContains(before, 'object_rows')
        self.journal('AFTER-OBJECT-SNAPSHOT', date(2026, 6, 30), Decimal('9'))
        self.assertEqual(displayed_context(self.version, self.preparer), frozen)
        self.assertEqual(self.client.get(url).content, before.content)

    def test_unmatched_object_set_retains_evidence_but_does_not_invent_zero(self):
        other = self.multiple_objects(); self.choose()
        other.expense_class = 'CO'; other.save(update_fields=('expense_class',))
        context = build_context(self.version, self.preparer)
        row = context['rows'][0]
        self.assertIsNone(row['half_certified'])
        self.assertFalse(row['half_certified_evidence']['matches_proposal_classes'])
        self.assertEqual(row['half_certified_evidence']['amount'], '100.00')
        self.assertEqual(len(row['half_certified_evidence']['object_rows']), 2)
        historical = next(part for part in context['certified_schedule'] if part['expense_class'] == 'FE')
        self.assertEqual(historical['half_amount'], '40.00')
        self.assertEqual(historical['proposed'], '0.00')
        self.assertIsNone(historical['estimate'])
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(reverse('budget:version_detail', args=[self.version.public_id])),
                            'source and proposal class sets differ')
        exported = self.client.get(reverse('budget:planning_context_export', args=[self.version.public_id]))
        self.assertContains(exported, 'matches_proposal_classes')
        self.assertContains(exported, '40.00')

    def test_exact_reversal_retains_both_object_classes_at_zero_net(self):
        self.multiple_objects()
        reversal = create_reversal(self.entry, self.maker, reference='OBJECT-REVERSAL',
            period=self.entry.period, entry_date=date(2026, 6, 30), reason='Synthetic exact object correction')
        submit_entry(reversal, self.maker); post_entry(reversal, self.checker)
        allocations = budget_attributions.reversal_allocations(self.capture(), reversal.pk)
        self.review(self.propose(proposals=[{'entry_id': reversal.pk, 'expected_latest': 0, 'allocations': allocations}]))
        self.native = self.decide(self.native_propose(expected_latest=2))
        self.choose()
        row = build_context(self.version, self.preparer)['rows'][0]
        self.assertEqual(row['half_certified']['amount'], '0.00')
        self.assertEqual([item['amount'] for item in row['half_certified']['object_rows']], ['0.00', '0.00'])
        self.assertEqual([len(item['components']) for item in row['half_certified']['object_rows']], [2, 2])
