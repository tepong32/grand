from decimal import Decimal
from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_budget_unlinked_liabilities as fixtures
from . import budget_preparation as editor
from .models import PayableClaimAttribution, JournalLine


class BudgetClaimRepairViewsTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixtures.UnlinkedLiabilityTests.setUp
    entry = fixtures.UnlinkedLiabilityTests.entry
    post = fixtures.UnlinkedLiabilityTests.post
    rows = fixtures.UnlinkedLiabilityTests.rows
    approve = fixtures.UnlinkedLiabilityTests.approve
    reference = fixtures.UnlinkedLiabilityTests.reference
    capture = fixtures.UnlinkedLiabilityTests.capture
    propose = fixtures.UnlinkedLiabilityTests.propose

    def finder(self, line=None):
        return reverse('accounting:budget_claim_sources', args=[(line or self.payment.lines.get(sequence=1)).pk])

    def test_guided_lookup_existing_claim_review_and_fresh_budget_source(self):
        self.client.force_login(self.maker)
        application = self.payment.lines.get(sequence=1)
        before = list(JournalLine.objects.values('pk', 'account_id', 'debit', 'credit', 'payable_origin_id'))
        prepared = editor.prepare(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 4), period_end=date(2026, 9, 5), entry_ids=[self.payment.pk])
        finder = self.client.get(self.finder())
        self.assertEqual([row.pk for row in finder.context['page']], [self.source.pk])
        url = reverse('accounting:claim_attribution', args=[self.source.pk]) + f'?budget_line={application.pk}'
        claim = self.client.get(url)
        self.assertContains(claim, 'has not been selected automatically')
        self.assertFalse(claim.context['form'].initial['applications'])
        result = self.client.post(url, {'expected_version': 0, 'party_key': self.source.payable_party_key,
            'claim_reference': self.source.payable_claim_reference, 'applications': [application.pk],
            'complete_history': 'on', 'reason': 'Verified original and entire payment history',
            'evidence_reference': 'SYN-GUIDED-CLAIM'})
        self.assertEqual(result.status_code, 302)
        proposal = PayableClaimAttribution.objects.get(evidence_reference='SYN-GUIDED-CLAIM')
        self.client.force_login(self.poster)
        reviewed = self.client.post(reverse('accounting:claim_attribution_review',
            args=[self.source.pk, proposal.public_id, 'approve']), {'note': 'Independently reconciled actual originals'})
        self.assertEqual(reviewed.status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'approved')
        self.assertEqual(before, list(JournalLine.objects.values('pk', 'account_id', 'debit', 'credit', 'payable_origin_id')))
        fresh = editor.prepare(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 4), period_end=date(2026, 9, 5), entry_ids=[self.payment.pk])
        self.assertNotEqual(prepared['context']['source_checksum'], fresh['context']['source_checksum'])
        self.assertFalse(fresh['context']['unlinked_liability_lines'])
        self.assertTrue(fresh['context']['warnings'])  # Source classification needs refreshed independent review.

    def test_paged_search_does_not_guess_by_amount_or_hide_original_credit(self):
        self.client.force_login(self.maker)
        for number in range(51):
            self.post(self.entry(f'OTHER-ORIGINAL-{number:02}', Decimal('1'), claim=f'OTHER-{number}'))
        page = self.client.get(self.finder(), {'page': 2})
        self.assertEqual(page.context['page'].paginator.count, 52)
        self.assertEqual(len(page.context['page']), 2)
        selected = self.client.get(self.finder(), {'q': self.original.reference})
        self.assertEqual([row.pk for row in selected.context['page']], [self.source.pk])
        original = self.client.get(self.finder(self.source))
        self.assertTrue(original.context['original'])
        self.assertEqual([row.pk for row in original.context['page']], [self.source.pk])
        self.assertFalse(PayableClaimAttribution.objects.exists())

    def test_scope_uat_and_linked_workflows_remain_guarded(self):
        self.client.force_login(self.maker)
        self.assertEqual(self.client.post(self.finder()).status_code, 405)
        expense = self.original.lines.get(sequence=1)
        self.assertEqual(self.client.get(self.finder(expense)).status_code, 404)
        linked = self.post(self.entry('ALREADY-LINKED', Decimal('1'), source=self.source, day=4)).lines.get(sequence=1)
        self.assertContains(self.client.get(self.finder(linked)), 'cannot reassign')
        claim_url = reverse('accounting:claim_attribution', args=[self.source.pk])
        self.assertEqual(self.client.get(claim_url, {'budget_line': linked.pk}).status_code, 404)
        self.assertEqual(self.client.get(claim_url, {'budget_line': 'invalid'}).status_code, 404)
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.get(self.finder()).status_code, 200)
        self.assertEqual(self.client.post(claim_url, {}).status_code, 403)
        self.assertFalse(PayableClaimAttribution.objects.exists())
