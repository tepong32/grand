from datetime import date

from django.urls import reverse

from . import test_budget_attribution_reversals as fixtures
from .test_budget_preparation_views import posted_rows
from .models import BudgetExpenditureAttribution as Attribution, JournalEntry, JournalLine, ResponsibilityCenter
from .services import submit_entry, post_entry


class PreparationPairingTests(fixtures.BudgetAttributionReversalTests):
    """Keep the existing reversal regressions alongside the guided-path checks."""

    def duplicate_source(self):
        parent = JournalEntry.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, period=self.entry.period, fund=self.fund,
            reference='EDITOR-DUPLICATES', entry_date=date(2026, 6, 30), description='Synthetic identical financial lines',
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        for sequence in (1, 2):
            JournalLine.objects.create(entry=parent, sequence=sequence, account=self.account,
                                       responsibility_center=self.center, debit=50)
        JournalLine.objects.create(entry=parent, sequence=3, account=self.offset, credit=100)
        submit_entry(parent, self.maker); post_entry(parent, self.checker)
        other = ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='PAIR-OTHER', name='Other reviewed office',
            office_id=self.budget_office.pk)
        originals = list(parent.lines.order_by('sequence'))
        rows = [dict(self.rows()[0], line_id=line.pk, amount='50', basis=f'Explicit original line {line.sequence}')
                for line in originals[:2]]
        rows[1]['center_id'] = other.pk
        rows.append(dict(self.rows()[1], line_id=originals[2].pk))
        self.review(self.submit_rows(parent, rows))
        child = self.reverse(parent, 'EDITOR-PAIRED-REVERSAL')
        children = list(child.lines.order_by('sequence'))
        self.client.force_login(self.maker)
        return parent, child, originals, children, rows, other

    def select(self, entries):
        return self.client.post(reverse('accounting:budget_preparation_select'),
            {'fund': self.fund.pk, 'start': '2026-01-01', 'end': '2026-06-30',
             'entries': [entry.pk for entry in entries]})

    def pairing_data(self, child, originals, children):
        # Deliberately cross-pair identical amounts: the distinct reviewed office
        # and evidence basis must follow the chosen original, not sequence order.
        return {f'journal-{child.pk}-pair-{children[0].pk}': originals[1].pk,
                f'journal-{child.pk}-pair-{children[1].pk}': originals[0].pk,
                f'journal-{child.pk}-pair-{children[2].pk}': originals[2].pk}

    def test_standalone_pairing_requires_a_complete_bijection_and_retains_offices(self):
        parent, child, originals, children, rows, other = self.duplicate_source()
        page = self.select([child])
        self.assertContains(page, 'Pair identical financial lines explicitly')
        self.assertIsNone(page.context['groups'][0]['pairing'][str(children[0].pk)].value())
        data = {'context': page.context['token'], 'reason': 'Explicit source-line evidence',
                'evidence_reference': 'SYN-PAIRED-UI', f'journal-{child.pk}-mode': 'reviewed'}
        before = Attribution.objects.count()
        missing = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(Attribution.objects.count(), before)
        data.update(self.pairing_data(child, originals, children))
        wrong = dict(data, **{f'journal-{child.pk}-pair-{children[1].pk}': originals[1].pk})
        rejected = self.client.post(reverse('accounting:budget_preparation_submit'), wrong)
        self.assertContains(rejected, 'paired exactly once', status_code=400)
        self.assertContains(rejected, data['reason'], status_code=400)
        self.assertEqual(Attribution.objects.count(), before)
        result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(result.status_code, 302)
        record = Attribution.objects.get(evidence_reference='SYN-PAIRED-UI')
        first = next(row for row in record.allocations if row['line_id'] == children[0].pk)
        self.assertEqual(first['center_id'], other.pk)
        self.assertEqual(first['reversal_source_line_id'], originals[1].pk)
        self.assertEqual(first['signed_amount'], '-50.00')
        self.review([record])

    def test_joint_pairing_uses_explicit_pending_parent_and_one_independent_decision(self):
        parent, child, originals, children, rows, other = self.duplicate_source()
        page = self.select([parent, child])
        data = {'context': page.context['token'], 'reason': 'Joint duplicate-line repair',
                'evidence_reference': 'SYN-JOINT-PAIR', **posted_rows(parent, rows),
                f'journal-{child.pk}-mode': 'parent', **self.pairing_data(child, originals, children)}
        result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(result.status_code, 302)
        records = list(Attribution.objects.filter(evidence_reference='SYN-JOINT-PAIR').order_by('entry_id'))
        self.assertEqual(len(records), 2)
        self.assertIn(str(parent.pk), records[1].dependencies)
        self.review(records)
        inherited = next(row for row in records[1].allocations if row['line_id'] == children[0].pk)
        self.assertEqual(inherited['center_id'], other.pk)

    def test_stale_pairing_retains_inputs_without_rebinding_new_predecessor(self):
        parent, child, originals, children, rows, other = self.duplicate_source()
        page = self.select([child])
        self.review(self.submit_rows(parent, rows, latest=1))
        before = Attribution.objects.count()
        data = {'context': page.context['token'], 'reason': 'Keep my chosen originals',
                'evidence_reference': 'SYN-STALE-PAIR', f'journal-{child.pk}-mode': 'reviewed',
                **self.pairing_data(child, originals, children)}
        result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertContains(result, 'Source coverage changed', status_code=409)
        self.assertContains(result, data['reason'], status_code=409)
        self.assertEqual(Attribution.objects.count(), before)
