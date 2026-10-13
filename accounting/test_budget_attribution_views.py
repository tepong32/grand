import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse

from departments.models import Department
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_attributions as service
from . import test_budget_reviewed_components as fixtures
from .models import BudgetExpenditureAttribution as Attribution, BudgetExpenditureAttributionHead as Head


class AttributionReviewViewsTests(TestCase):
    databases = {'default', 'finance'}
    entry = fixtures.ReviewedComponentTests.entry
    post = fixtures.ReviewedComponentTests.post
    capture = fixtures.ReviewedComponentTests.capture
    rows = fixtures.ReviewedComponentTests.rows

    def setUp(self):
        fixtures.ReviewedComponentTests.setUp(self)
        self.poster.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
                                                                 codename='export_budget_attributions'))
        self.second = self.post(self.entry('SECOND-SEARCH-TARGET', Decimal('1000'), claim='INV-SECOND'))
        self.records = self.propose([self.original, self.second])
        self.batch_id = self.records[0].batch_id
        self.client.force_login(self.poster)

    def propose(self, entries, version=0):
        proposals = []
        for entry in entries:
            rows = self.rows()
            mapping = {self.original.lines.get(sequence=n).pk: entry.lines.get(sequence=n).pk for n in (1, 2)}
            for row in rows:
                row['line_id'] = mapping[row['line_id']]
            proposals.append(dict(entry_id=entry.pk, expected_latest=version, allocations=rows))
        return service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 5),
            expected_source_checksum=self.capture()['checksum'], proposals=proposals,
            reason='Explicit complete source review', evidence_reference='SYN-REVIEW-SCREEN')

    def url(self, action, batch_id=None):
        if action == 'register':
            return reverse('accounting:budget_attribution_register')
        return reverse('accounting:budget_attribution_' + action, kwargs={'batch_id': batch_id or self.batch_id})

    def test_search_keeps_the_whole_batch_and_history_is_not_truncated(self):
        response = self.client.get(self.url('register'), {'q': 'SECOND-SEARCH-TARGET'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertEqual(list(response.context['page'])[0]['journals'], 2)
        for version in range(1, 52):
            self.propose([self.original], version=version)
        response = self.client.get(self.url('register'), {'entry': self.original.pk, 'page': 2})
        self.assertEqual(response.context['page'].paginator.count, 52)
        self.assertEqual(len(response.context['page']), 2)
        self.assertContains(response, 'Previous')
        invalid = self.client.get(self.url('register'), {'start': '2026-09-05', 'end': '2026-09-01'})
        self.assertContains(invalid, 'must not precede')
        self.assertEqual(invalid.context['page'].paginator.count, 0)

    def test_whole_group_review_and_retained_export_preserve_the_original_file(self):
        page = self.client.get(self.url('detail'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'SECOND-SEARCH-TARGET')
        self.assertContains(page, 'Record review for all 2 journals')
        export = self.client.get(self.url('export'))
        self.assertEqual(export.status_code, 200)
        data = json.loads(export.content)
        self.assertFalse(data['certificate'])
        self.assertEqual(len(data['records']), 2)
        retained = Path(settings.GRAND_EXPORT_ROOT) / export['X-GRAND-Export-Relative-Path']
        before = retained.read_bytes()
        result = self.client.post(self.url('decide'), {'decision': 'approve', 'note': 'Reviewed both complete partitions'})
        self.assertRedirects(result, self.url('detail'))
        self.assertEqual(Head.objects.count(), 2)
        self.assertEqual(Attribution.objects.filter(batch_id=self.batch_id, status='approved').count(), 2)
        after = self.client.get(self.url('export'))
        self.assertNotEqual(after['X-GRAND-Export-SHA256'], export['X-GRAND-Export-SHA256'])
        self.assertEqual(retained.read_bytes(), before)
        self.assertContains(self.client.get(self.url('detail')), 'Reviewed both complete partitions')

    def test_stale_failure_keeps_review_note_and_return_decides_every_member(self):
        self.propose([self.original], version=1)
        result = self.client.post(self.url('decide'), {'decision': 'approve', 'note': 'Retain this review input'})
        self.assertEqual(result.status_code, 409)
        self.assertContains(result, 'Retain this review input', status_code=409)
        self.assertContains(result, 'newer attribution', status_code=409)
        self.assertFalse(Head.objects.exists())
        self.assertEqual(Attribution.objects.filter(batch_id=self.batch_id, status='submitted').count(), 2)
        returned = self.client.post(self.url('decide'), {'decision': 'return', 'note': 'Return complete stale group'})
        self.assertEqual(returned.status_code, 302)
        self.assertEqual(Attribution.objects.filter(batch_id=self.batch_id, status='returned').count(), 2)

    def test_owner_uat_export_permission_and_self_review_boundaries(self):
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(self.url('export')).status_code, 403)
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='review_budget_attributions'))
        self.assertEqual(self.client.post(self.url('decide'), {'decision': 'approve', 'note': 'Own proposal'}).status_code, 409)
        self.poster.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.poster)
        self.assertEqual(self.client.get(self.url('detail')).status_code, 200)
        self.assertEqual(self.client.get(self.url('export')).status_code, 200)
        self.assertEqual(self.client.post(self.url('decide'), {'decision': 'approve', 'note': 'UAT mutation'}).status_code, 403)
        other = Department.objects.create(name='Other ledger', slug='other-review-ledger')
        self.poster.employeeprofile.assigned_department = other
        self.poster.employeeprofile.save(update_fields=('assigned_department',))
        self.client.force_login(self.poster)
        self.assertEqual(self.client.get(self.url('detail')).status_code, 404)
        self.assertEqual(self.client.get(self.url('export')).status_code, 404)
        self.assertEqual(self.client.get(self.url('register')).context['page'].paginator.count, 0)
        self.assertFalse(Head.objects.exists())

    def test_csrf_invalid_decision_and_tampered_evidence_fail_closed(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.poster)
        self.assertEqual(csrf.post(self.url('decide'), {'decision': 'approve', 'note': 'No CSRF token'}).status_code, 403)
        self.assertEqual(self.client.get(self.url('decide')).status_code, 405)
        self.assertEqual(self.client.post(self.url('decide'), {'decision': 'unexpected', 'note': 'Keep me'}).status_code, 400)
        Attribution.objects.filter(pk=self.records[0].pk).update(reason='Changed without proposal checksum')
        self.assertEqual(self.client.get(self.url('detail')).status_code, 409)
        self.assertEqual(self.client.get(self.url('export')).status_code, 409)
        self.assertFalse(Head.objects.exists())
