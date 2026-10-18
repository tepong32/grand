"""Maintenance reviewers can navigate without receiving asset-register access."""
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from inventory.access import can as can_asset
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_maintenance_corrections as fixtures


class MaintenanceReviewNavigationTests(TestCase):
    databases = {'default', 'finance'}
    body = fixtures.MaintenanceCorrectionTests.body
    upload = fixtures.MaintenanceCorrectionTests.upload
    values = fixtures.MaintenanceCorrectionTests.values
    propose = fixtures.MaintenanceCorrectionTests.propose

    @classmethod
    def setUpTestData(cls):
        fixtures.MaintenanceCorrectionTests.setUpTestData.__func__(cls)
        # Ordinary asset readers hold this separate grant; the manager-only
        # scenario below explicitly removes it. Reviewers never receive it.
        cls.clerk.user_permissions.add(Permission.objects.get(
            content_type__app_label='inventory', codename='view_asset'))

    def setUp(self):
        fixtures.MaintenanceCorrectionTests.setUp(self)

    def assert_workspace_is_reachable(self, url):
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        workspace = reverse('inventory:maintenance-list') + '?status=all'
        self.assertContains(page, f'class="brand" href="{workspace}"')
        self.assertContains(page, f'href="{workspace}">Workspace</a>')
        self.assertContains(self.client.get(workspace), self.asset.asset_name)
        return page

    def test_minimal_reviewer_can_return_from_correction_and_original_to_case_history(self):
        row = self.propose()
        self.client.force_login(self.reviewer)
        self.assertFalse(can_asset(self.reviewer, 'view'))
        for url in (reverse('inventory:maintenance-correction-detail', args=[row.pk]),
                    reverse('inventory:maintenance-detail', args=[self.case.pk]),
                    reverse('inventory:maintenance-list')):
            with self.subTest(url=url):
                self.assert_workspace_is_reachable(url)
        asset_url = reverse('inventory:asset-detail', args=[self.asset.pk])
        original = self.client.get(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        self.assertNotContains(original, f'href="{asset_url}"')
        history = self.client.get(reverse('inventory:maintenance-list'))
        self.assertNotContains(history, f'href="{reverse("inventory:asset-list")}"')
        self.assertEqual(self.client.get(asset_url).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory:dashboard')).status_code, 403)
        self.assertEqual(row.events.count(), 1)

    def test_asset_readers_keep_their_original_record_link(self):
        self.client.force_login(self.clerk)
        page = self.assert_workspace_is_reachable(reverse('inventory:maintenance-detail', args=[self.case.pk]))
        asset_url = reverse('inventory:asset-detail', args=[self.asset.pk])
        self.assertContains(page, f'href="{asset_url}">Asset record</a>')
        self.assertEqual(self.client.get(asset_url).status_code, 200)
        history = self.client.get(reverse('inventory:maintenance-list'))
        self.assertContains(history, f'href="{reverse("inventory:asset-list")}">Asset register</a>')

    def test_managers_without_asset_read_can_return_from_all_entry_forms(self):
        self.clerk.user_permissions.remove(Permission.objects.get(
            content_type__app_label='inventory', codename='view_asset'))
        self.assertFalse(can_asset(self.clerk, 'view'))
        self.client.force_login(self.clerk)
        for name, identity in (('maintenance-correction-new', self.case.pk),
                               ('maintenance-notice-new', self.case.pk),
                               ('maintenance-open', self.asset.pk)):
            with self.subTest(page=name):
                page = self.assert_workspace_is_reachable(reverse('inventory:' + name, args=[identity]))
                self.assertNotContains(page, f'href="{reverse("inventory:asset-detail", args=[self.asset.pk])}"')

    def test_uat_reviewer_keeps_navigation_and_cannot_record_a_decision(self):
        row = self.propose()
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.reviewer)
        url = reverse('inventory:maintenance-correction-detail', args=[row.pk])
        page = self.assert_workspace_is_reachable(url)
        self.assertNotContains(page, 'Record independent decision')
        self.assertEqual(self.client.post(url, {'expected_version': 1, 'action': 'approved',
                                             'note': 'UAT cannot approve'}).status_code, 403)
        row.refresh_from_db()
        self.assertEqual(row.status, 'proposed')
        self.assertEqual(row.events.count(), 1)
