"""Staff can discover closed-case corrections without gaining asset access."""
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from inventory import maintenance
from inventory.models import Asset, AssetMaintenanceCase, MaintenanceCorrection, MaintenanceCorrectionEvent
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_maintenance_corrections as fixtures


class MaintenanceWorkQueueTests(TestCase):
    databases = {'default', 'finance'}
    body = fixtures.MaintenanceCorrectionTests.body
    upload = fixtures.MaintenanceCorrectionTests.upload
    values = fixtures.MaintenanceCorrectionTests.values
    propose = fixtures.MaintenanceCorrectionTests.propose
    approve = fixtures.MaintenanceCorrectionTests.approve

    @classmethod
    def setUpTestData(cls):
        fixtures.MaintenanceCorrectionTests.setUpTestData.__func__(cls)

    def setUp(self):
        fixtures.MaintenanceCorrectionTests.setUp(self)

    def test_minimal_reviewer_finds_closed_cases_from_employee_home(self):
        self.propose()
        self.client.force_login(self.reviewer)
        home = self.client.get(reverse('department_dashboard'))
        destination = reverse('inventory:maintenance-list') + '?status=all'
        self.assertContains(home, f'href="{destination}"')
        self.assertContains(self.client.get(destination), self.asset.asset_name)
        self.assertEqual(self.client.get(reverse('inventory:asset-list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory:dashboard')).status_code, 403)

    def test_pending_filter_excludes_closed_cases_without_proposals(self):
        original = self.case
        pending = self.propose()
        self.case = maintenance.open_maintenance(actor=self.clerk, asset=self.asset,
            data={'reported_date': original.reported_date, 'problem': 'No correction'})
        self.case = maintenance.close_maintenance(actor=self.clerk, case=self.case, expected_version=1,
            action='cancelled', finished_date=original.finished_date, note='No work required')
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('inventory:maintenance-list'), {'status': 'all', 'review': 'proposed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([case.pk for case in response.context['page']], [pending.case_id])
        self.assertContains(response, '1 awaiting correction review')

    def close_case(self, actor=None, asset=None):
        case = maintenance.open_maintenance(actor=actor or self.clerk, asset=asset or self.asset,
            data={'reported_date': self.case.reported_date, 'problem': 'Retained concern'})
        return maintenance.close_maintenance(actor=actor or self.clerk, case=case, expected_version=1,
            action='cancelled', finished_date=self.case.finished_date, note='No work required')

    def test_home_counts_cases_once_and_excludes_the_other_gso_office(self):
        self.propose()
        self.propose()
        original = self.case
        other_asset = Asset.objects.create(department_id=self.other.pk, asset_name='Other office repair')
        self.case = self.close_case(actor=self.outsider, asset=other_asset)
        self.propose(actor=self.outsider)
        self.case = original
        self.client.force_login(self.reviewer)
        home = self.client.get(reverse('department_dashboard'))
        card = next(row for row in home.context['dashboard_sections'] if row['title'] == 'Maintenance requests')
        self.assertEqual({row['label']: row['value'] for row in card['summary_items']},
            {'Open cases': 0, 'Completed cases': 1, 'Cases with proposed corrections': 1})
        response = self.client.get(reverse('inventory:maintenance-list'), {'status': 'all', 'review': 'proposed'})
        self.assertEqual([case.pk for case in response.context['page']], [self.case.pk])
        self.assertContains(response, '2 awaiting correction review')
        self.assertNotContains(response, other_asset.asset_name)

    def test_uat_keeps_read_entry_and_missing_case_read_grant_cannot_enter(self):
        row = self.propose()
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.reviewer)
        destination = reverse('inventory:maintenance-list') + '?status=all'
        self.assertContains(self.client.get(reverse('department_dashboard')), f'href="{destination}"')
        detail = reverse('inventory:maintenance-correction-detail', args=[row.pk])
        self.assertNotContains(self.client.get(detail), 'Record independent decision')
        self.assertEqual(self.client.post(detail, {'expected_version': 1, 'action': 'approved',
            'note': 'UAT must remain read only'}).status_code, 403)
        self.reviewer.user_permissions.remove(Permission.objects.get(
            content_type__app_label='inventory', codename='view_assetmaintenancecase'))
        self.assertNotContains(self.client.get(reverse('department_dashboard')), f'href="{destination}"')
        self.assertEqual(self.client.get(destination).status_code, 403)
        row.refresh_from_db()
        self.assertEqual((row.status, row.events.count()), ('proposed', 1))

    def test_pending_pagination_is_complete_and_preserves_both_filters(self):
        self.propose()
        for _ in range(25):
            self.case = self.close_case()
            self.propose()
        self.client.force_login(self.reviewer)
        url = reverse('inventory:maintenance-list')
        first = self.client.get(url, {'status': 'all', 'review': 'proposed'})
        self.assertEqual(first.context['page'].paginator.count, 26)
        self.assertContains(first, '?status=all&amp;review=proposed&amp;page=2')
        second = self.client.get(url, {'status': 'all', 'review': 'proposed', 'page': 2})
        self.assertEqual(len(second.context['page']), 1)
        self.assertEqual(len({row.pk for row in first.context['page']} | {row.pk for row in second.context['page']}), 26)
        self.assertContains(second, '?status=all&amp;review=proposed&amp;page=1')

    def test_original_open_default_and_status_intersection_remain_read_only(self):
        self.propose()
        before = (list(AssetMaintenanceCase.objects.values()), list(MaintenanceCorrection.objects.values()),
                  list(MaintenanceCorrectionEvent.objects.values()), list(Asset.objects.values()))
        self.client.force_login(self.reviewer)
        url = reverse('inventory:maintenance-list')
        for parameters in ({}, {'status': 'open', 'review': 'proposed'}):
            self.assertEqual(self.client.get(url, parameters).context['page'].paginator.count, 0)
        self.assertEqual(self.client.get(url, {'status': 'completed', 'review': 'proposed'}).context['page'].paginator.count, 1)
        self.assertEqual(before, (list(AssetMaintenanceCase.objects.values()), list(MaintenanceCorrection.objects.values()),
                  list(MaintenanceCorrectionEvent.objects.values()), list(Asset.objects.values())))

    def test_unsupported_review_filter_fails_without_disclosing_case_data(self):
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('inventory:maintenance-list'), {'status': 'all', 'review': 'approved'})
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, self.asset.asset_name, status_code=400)
