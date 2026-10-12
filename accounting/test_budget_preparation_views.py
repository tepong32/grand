from unittest.mock import patch
import time
import json

from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_preparation as editor
from . import test_budget_preparation as fixtures
from .models import BudgetExpenditureAttribution as Attribution


def posted_rows(entry, rows):
    prefix = f'journal-{entry.pk}'
    data = {prefix + '-mode': 'manual', prefix + '-rows-TOTAL_FORMS': str(len(rows)),
            prefix + '-rows-INITIAL_FORMS': '2', prefix + '-rows-MIN_NUM_FORMS': '0',
            prefix + '-rows-MAX_NUM_FORMS': '1000'}
    for index, row in enumerate(rows):
        for key, value in row.items():
            if key == 'claim_component':
                key, value = 'component', f"{row['line_id']}:{value['component_key']}"
            data[f'{prefix}-rows-{index}-{key}'] = value
    return data


class PreparationViewsTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixtures.PreparationContextTests.setUp
    entry = fixtures.PreparationContextTests.entry
    post = fixtures.PreparationContextTests.post
    capture = fixtures.PreparationContextTests.capture
    rows = fixtures.PreparationContextTests.rows
    propose = fixtures.PreparationContextTests.propose
    approve = fixtures.PreparationContextTests.approve

    def begin(self):
        self.client.force_login(self.maker)
        return self.client.post(reverse('accounting:budget_preparation_select'),
            {'fund': self.fund.pk, 'start': '2026-09-01', 'end': '2026-09-05', 'entries': [self.original.pk]})

    def payload(self, page):
        return {'context': page.context['token'], 'reason': 'Actual retained source explanation',
            'evidence_reference': 'SYN-SCREEN-PREPARE', **posted_rows(self.original, self.rows())}

    def test_select_explicit_split_submit_and_replay_retains_inputs(self):
        page = self.begin()
        self.assertContains(page, 'Prepare expenditure allocations')
        self.assertContains(page, 'Add allocation row')
        data = self.payload(page)
        result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(result.status_code, 302)
        record = Attribution.objects.get()
        self.assertEqual(record.status, 'submitted')
        self.assertEqual(len(record.allocations), 3)
        replay = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(replay.status_code, 409)
        self.assertContains(replay, 'newer proposal', status_code=409)
        self.assertContains(replay, data['reason'], status_code=409)
        self.assertEqual(Attribution.objects.count(), 1)

    def test_invalid_partition_and_expired_context_keep_entered_rows(self):
        data = self.payload(self.begin())
        key = f'journal-{self.original.pk}-rows-0-amount'
        data[key] = '999'
        result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(result.status_code, 409)
        self.assertContains(result, 'value="999"', status_code=409)
        self.assertFalse(Attribution.objects.exists())
        data[key] = '1000'
        with patch('django.core.signing.time.time', return_value=time.time() + editor.MAX_AGE + 10):
            result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertContains(result, 'expired', status_code=409)
        self.assertContains(result, data['reason'], status_code=409)
        self.assertFalse(Attribution.objects.exists())

    def test_permissions_csrf_and_post_only_submission(self):
        data = self.payload(self.begin())
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.maker)
        self.assertEqual(csrf.post(reverse('accounting:budget_preparation_submit'), data).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounting:budget_preparation_submit')).status_code, 405)
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.post(reverse('accounting:budget_preparation_submit'), data).status_code, 403)
        self.assertFalse(Attribution.objects.exists())

    def test_structured_transport_preserves_more_than_one_thousand_fields(self):
        page = self.begin()
        original = self.rows()
        rows = [dict(original[0], amount='10') for _ in range(100)] + original[1:]
        for row in rows:
            for key in ('center_id', 'expense_class', 'component', 'claim_component_basis', 'DELETE'):
                row.setdefault(key, '')
        values = {'reason': 'One hundred explicit shares', 'evidence_reference': 'SYN-LARGE',
                  **posted_rows(self.original, rows)}
        self.assertGreater(len(values), 1000)
        result = self.client.post(reverse('accounting:budget_preparation_submit'),
            {'context': page.context['token'], 'allocations_payload': json.dumps([(key, str(value)) for key, value in values.items()])})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(len(Attribution.objects.get().allocations), 102)


class PreparationJointViewsTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixtures.PreparationDependencyTests.setUp
    entry = fixtures.PreparationDependencyTests.entry
    post = fixtures.PreparationDependencyTests.post
    rows = fixtures.PreparationDependencyTests.rows
    approve = fixtures.PreparationDependencyTests.approve
    reference = fixtures.PreparationDependencyTests.reference
    payment_rows = fixtures.PreparationDependencyTests.payment_rows
    capture = fixtures.PreparationDependencyTests.capture
    propose = fixtures.PreparationDependencyTests.propose
    reverse_and_review = fixtures.PreparationDependencyTests.reverse_and_review
    stale_pair = fixtures.PreparationDependencyTests.stale_pair

    def test_standalone_reviewed_reversal_uses_retained_mirror(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        returned = self.reverse_and_review(self.payment, 'EDITOR-RETURN', 5)
        self.client.force_login(self.maker)
        page = self.client.post(reverse('accounting:budget_preparation_select'),
            {'fund': self.fund.pk, 'start': '2026-09-01', 'end': '2026-09-10', 'entries': [returned.pk]})
        self.assertContains(page, 'Mirror the independently reviewed predecessor')
        result = self.client.post(reverse('accounting:budget_preparation_submit'),
            {'context': page.context['token'], 'reason': 'Retain the exact reviewed mirror',
             'evidence_reference': 'SYN-MIRROR-UI', f'journal-{returned.pk}-mode': 'reviewed'})
        self.assertEqual(result.status_code, 302)
        records = list(Attribution.objects.filter(evidence_reference='SYN-MIRROR-UI'))
        self.assertEqual(len(records), 1)
        self.approve(records)

    def test_joint_editor_inherits_without_client_allocations(self):
        returned, _ = self.stale_pair()
        self.client.force_login(self.maker)
        page = self.client.post(reverse('accounting:budget_preparation_select'),
            {'fund': self.fund.pk, 'start': '2026-09-01', 'end': '2026-09-10',
             'entries': [returned.pk, self.payment.pk]})
        self.assertContains(page, 'proposal in this batch')
        data = {'context': page.context['token'], 'reason': 'Explicit joint repair', 'evidence_reference': 'SYN-JOINT-UI',
                **posted_rows(self.payment, self.payment_rows()), f'journal-{returned.pk}-mode': 'parent'}
        result = self.client.post(reverse('accounting:budget_preparation_submit'), data)
        self.assertEqual(result.status_code, 302)
        records = list(Attribution.objects.filter(evidence_reference='SYN-JOINT-UI').order_by('entry_id'))
        self.assertEqual(len(records), 2)
        self.approve(records)
