"""Employees can find shared worksheets and narrow the same authorized register."""
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from inventory_finance.models import AssetCostAllocation, AssetCostAllocationEvent
from . import test_asset_cost_allocations as fixtures


class AssetCostWorkQueueTests(TestCase):
    databases = {'default', 'finance'}
    body = fixtures.AssetCostAllocationTests.body
    upload = fixtures.AssetCostAllocationTests.upload
    accept = fixtures.AssetCostAllocationTests.accept
    entries = fixtures.AssetCostAllocationTests.entries
    propose = fixtures.AssetCostAllocationTests.propose
    decide = fixtures.AssetCostAllocationTests.decide

    @classmethod
    def setUpTestData(cls):
        fixtures.AssetCostAllocationTests.setUpTestData.__func__(cls)

    def setUp(self):
        fixtures.AssetCostAllocationTests.setUp(self)

    def states(self):
        approved = self.decide(self.propose())
        rejected = self.decide(self.propose(), action='rejected')
        pending = self.propose()
        return approved, rejected, pending

    def home(self, actor):
        self.client.force_login(actor)
        page = self.client.get(reverse('department_dashboard'))
        self.assertEqual(page.status_code, 200)
        return page

    def card(self, page):
        return next((row for row in page.context['dashboard_sections']
                     if row.get('url_name') == 'inventory_finance:asset-cost-workbench'), None)

    def test_employee_home_reaches_the_authorized_shared_workspace_without_mutating_records(self):
        self.propose()
        before = list(AssetCostAllocation.objects.values()), list(AssetCostAllocationEvent.objects.values())
        workspace = reverse('inventory_finance:asset-cost-workbench')
        for actor in (self.accountant, self.accounting_uat, self.clerk):
            with self.subTest(actor=actor.username):
                page = self.home(actor)
                self.assertContains(page, f'href="{workspace}"')
                self.assertIsNotNone(self.card(page))
                self.assertEqual(self.client.get(workspace).status_code, 200)
        self.assertEqual(before, (list(AssetCostAllocation.objects.values()), list(AssetCostAllocationEvent.objects.values())))

    def test_home_counts_use_current_office_and_explicit_shared_accounting_scope(self):
        self.states()
        other = Department.objects.create(name='Other worksheet review office', slug='other-worksheet-review')
        self.propose(finance_department_id=other.pk)
        for actor, expected in ((self.accountant, (1, 1, 1)), (self.accounting_uat, (1, 1, 1)),
                                (self.clerk, (2, 1, 1)), (self.outsider, (0, 0, 0))):
            with self.subTest(actor=actor.username):
                card = self.card(self.home(actor))
                self.assertIsNotNone(card)
                self.assertEqual({item['label']: item['value'] for item in card['summary_items']},
                                 dict(zip(('Awaiting review', 'Reviewed history', 'Rejected'), expected)))

    def test_missing_module_grants_hide_the_entry_and_preserve_existing_ledger_access(self):
        self.accountant.user_permissions.remove(*Permission.objects.filter(
            content_type__app_label='inventory_finance', codename__endswith='_assetcostallocation'))
        page = self.home(self.accountant)
        self.assertIsNone(self.card(page))
        self.assertNotContains(page, reverse('inventory_finance:asset-cost-workbench'))
        self.assertContains(page, reverse('accounting:workspace'))
        self.assertEqual(self.client.get(reverse('inventory_finance:asset-cost-workbench')).status_code, 403)

    def test_status_filter_limits_shared_rows_and_defaults_to_all(self):
        approved, rejected, pending = self.states()
        self.client.force_login(self.accountant)
        url = reverse('inventory_finance:asset-cost-workbench')
        for status, expected in (('proposed', [pending.pk]), ('approved', [approved.pk]),
                                  ('rejected', [rejected.pk]), ('all', [pending.pk, rejected.pk, approved.pk])):
            with self.subTest(status=status):
                page = self.client.get(url, {'status': status})
                self.assertEqual(page.status_code, 200)
                self.assertEqual([row.pk for row in page.context['page']], expected)
        self.assertEqual(self.client.get(url).context['page'].paginator.count, 3)

    def test_invalid_filter_is_rejected_and_cannot_disclose_shared_rows(self):
        self.propose()
        self.client.force_login(self.accountant)
        response = self.client.get(reverse('inventory_finance:asset-cost-workbench'), {'status': 'retired'})
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, self.line.receipt.delivery_reference, status_code=400)

    def test_proposal_pagination_preserves_the_status_and_source_position(self):
        for _ in range(20):
            self.propose()
        other_line = self.accept()
        for _ in range(6):
            self.propose(line=other_line)
        self.decide(self.propose(line=other_line), action='rejected')
        self.client.force_login(self.clerk)
        url = reverse('inventory_finance:asset-cost-workbench')
        first = self.client.get(url, {'status': 'proposed'})
        self.assertEqual(first.context['page'].paginator.count, 26)
        self.assertContains(first, '?status=proposed&amp;page=2&amp;source_page=1')
        second = self.client.get(url, {'status': 'proposed', 'page': 2, 'source_page': 1})
        self.assertEqual(len(second.context['page']), 1)
        self.assertEqual(second.context['page'][0].status, 'proposed')
        self.assertContains(second, '?status=proposed&amp;page=1&amp;source_page=1')

    def test_source_pagination_keeps_the_selected_review_filter(self):
        for _ in range(25):
            self.accept()
        self.client.force_login(self.clerk)
        response = self.client.get(reverse('inventory_finance:asset-cost-workbench'),
                                   {'status': 'rejected', 'source_page': 2})
        self.assertEqual(response.context['sources'].paginator.count, 26)
        self.assertEqual(response.context['sources'].number, 2)
        self.assertEqual(len(response.context['sources']), 1)
        self.assertEqual(response.context['page'].paginator.count, 0)
        self.assertContains(response, '?status=rejected&amp;page=1&amp;source_page=1')
