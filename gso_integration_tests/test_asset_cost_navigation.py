"""Cross-office readers must return to their authorized documentary workspace."""
from django.test import TestCase
from django.urls import reverse
from . import test_asset_cost_allocations as fixtures


class AssetCostNavigationTests(TestCase):
    databases = {'default', 'finance'}
    body = fixtures.AssetCostAllocationTests.body
    upload = fixtures.AssetCostAllocationTests.upload
    accept = fixtures.AssetCostAllocationTests.accept
    entries = fixtures.AssetCostAllocationTests.entries
    propose = fixtures.AssetCostAllocationTests.propose

    @classmethod
    def setUpTestData(cls):
        fixtures.AssetCostAllocationTests.setUpTestData.__func__(cls)

    def setUp(self):
        fixtures.AssetCostAllocationTests.setUp(self)

    def test_accounting_reader_uat_and_owner_header_links_reach_the_authorized_module(self):
        row = self.propose()
        workspace = reverse('inventory_finance:asset-cost-workbench')
        detail = reverse('inventory_finance:asset-cost-detail', args=[row.pk])
        for actor in (self.accountant, self.accounting_uat, self.clerk):
            self.client.force_login(actor)
            for url in (detail, workspace):
                with self.subTest(actor=actor.username, url=url):
                    page = self.client.get(url)
                    self.assertContains(page, f'class="brand" href="{workspace}"')
                    self.assertContains(page, f'href="{workspace}">Workspace</a>')
                    self.assertEqual(self.client.get(workspace).status_code, 200)
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(reverse('inventory_finance:asset-cost-propose', args=[self.line.pk])),
                            f'href="{workspace}">Workspace</a>')
        self.client.force_login(self.accountant)
        self.assertEqual(self.client.get(reverse('inventory:dashboard')).status_code, 403)

    def test_existing_receiving_header_retains_its_original_dashboard_destination(self):
        self.client.force_login(self.clerk)
        page = self.client.get(reverse('inventory:receiving-detail', args=[self.line.receipt_id]))
        dashboard = reverse('inventory:dashboard')
        self.assertContains(page, f'class="brand" href="{dashboard}"')
        self.assertContains(page, f'href="{dashboard}">Workspace</a>')
