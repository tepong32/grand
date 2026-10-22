from decimal import Decimal
from datetime import date
from django.contrib.auth.models import Permission
from django.db import connections
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from inventory.models import Asset
from . import test_property_drafts as fixture


class PARSourcePreparationTests(TestCase):
    databases = {'default', 'finance'}
    fields = staticmethod(fixture.PropertyDraftAccessTests.fields)

    @classmethod
    def setUpTestData(cls):
        fixture.PropertyDraftAccessTests.setUpTestData.__func__(cls)

    def source_url(self, asset=None):
        return reverse('inventory:asset-par-preparation', args=[(asset or self.asset).pk])

    def test_only_register_name_and_quantity_are_prefilled(self):
        self.asset.quantity, self.asset.unit_cost = 2, Decimal('123.45')
        self.asset.property_tag = 'REGISTER-TAG-ONLY'
        self.asset.purchase_date = date(2026, 10, 1)
        self.asset.fund_code = 'SUPPLIED-REGISTER-FUND'
        self.asset.save()
        self.client.force_login(self.clerk)
        for cost in (Decimal('123.45'), Decimal('0.00'), None):
            self.asset.unit_cost = cost
            self.asset.save()
            response = self.client.get(self.source_url())
            self.assertEqual(response.context['lines'].forms[0].initial,
                             {'description': self.asset.asset_name, 'quantity': 2})
            self.assertFalse(response.context['header'].initial)
            self.assertContains(response, 'REGISTER-TAG-ONLY')
            self.assertNotContains(response, 'SUPPLIED-REGISTER-FUND')

    def test_edited_preview_preserves_zero_unknowns_and_original_records_for_clerk_and_uat(self):
        before = list(Asset.objects.values())
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
                response = self.client.post(self.source_url(), self.fields(**{
                    'lines-INITIAL_FORMS': '1', 'lines-0-description': '<script>draft only</script>',
                    'lines-0-quantity': '3', 'lines-0-acquisition_cost': '0.00',
                    'lines-1-description': 'Unknown acquisition facts'}))
            self.assertTrue(response.context['ready'])
            self.assertEqual(response.context['print_lines'][0]['acquisition_cost'], Decimal('0.00'))
            self.assertIsNone(response.context['print_lines'][1]['acquisition_cost'])
            self.assertContains(response, '&lt;script&gt;draft only&lt;/script&gt;')
            self.assertNotContains(response, '<script>draft only</script>')
            self.assertContains(response, 'Print / Save as PDF')
            self.assertContains(response, 'Draft values require source review')
            self.assertNotContains(response, 'class="panel par-editor" open')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(len(finance), 0)
            self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))
        self.assertEqual(list(Asset.objects.values()), before)

    def test_minimal_read_grants_keep_blank_par_but_require_export_for_source(self):
        self.assertEqual(self.client.get(self.source_url()).status_code, 302)
        self.assertEqual(self.client.post(self.source_url(), self.fields()).status_code, 302)
        self.no_grant.user_permissions.add(*Permission.objects.filter(content_type__app_label='inventory',
            codename__in=('view_asset', 'view_property_determination')))
        self.client.force_login(self.no_grant)
        self.assertEqual(self.client.get(reverse('inventory:par-preparation')).status_code, 200)
        self.assertNotContains(self.client.get(reverse('inventory:property-register')), 'Start PAR draft with register details')
        self.assertEqual(self.client.get(self.source_url()).status_code, 403)
        self.assertEqual(self.client.post(self.source_url(), self.fields()).status_code, 403)
        self.no_grant.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='export_asset_register'))
        self.assertEqual(self.client.get(self.source_url()).status_code, 200)
        for actor in (self.super_no_grant, self.outsider):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.source_url()).status_code, 403)

    def test_other_owner_is_hidden_even_when_current_custody_is_in_requesting_office(self):
        foreign = Asset.objects.create(department_id=self.other.pk, asset_name='Foreign PAR source', assigned_department_id=self.gso.pk)
        self.client.force_login(self.clerk)
        for response in (self.client.get(self.source_url(foreign)), self.client.post(self.source_url(foreign), self.fields())):
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, 'Foreign PAR source', status_code=404)
        register = self.client.get(reverse('inventory:property-register'))
        self.assertContains(register, self.source_url())
        self.assertNotContains(register, self.source_url(foreign))

    def test_post_rechecks_export_grant_and_current_owner(self):
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(self.source_url()).status_code, 200)
        grant = Permission.objects.get(content_type__app_label='inventory', codename='export_asset_register')
        self.clerk.user_permissions.remove(grant)
        self.assertEqual(self.client.post(self.source_url(), self.fields()).status_code, 403)
        self.clerk.user_permissions.add(grant)
        self.assertEqual(self.client.get(self.source_url()).status_code, 200)
        Asset.objects.filter(pk=self.asset.pk).update(department_id=self.other.pk)
        self.assertEqual(self.client.post(self.source_url(), self.fields()).status_code, 404)

    def test_invalid_draft_keeps_entries_expanded_without_preview(self):
        self.client.force_login(self.clerk)
        response = self.client.post(self.source_url(), self.fields(**{
            'lines-INITIAL_FORMS': '1', 'lines-0-description': 'Keep my draft', 'lines-0-quantity': '-1'}))
        self.assertFalse(response.context['ready'])
        self.assertContains(response, 'Keep my draft')
        self.assertContains(response, 'class="panel par-editor" open')
        self.assertContains(response, 'Your entries are retained below')
        self.assertNotContains(response, 'aria-label="PAR draft preview"')

    def test_blank_par_and_source_keep_bounded_forms_methods_and_csrf(self):
        self.client.force_login(self.clerk)
        for url in (reverse('inventory:par-preparation'), self.source_url()):
            response = self.client.post(url, self.fields(**{'lines-TOTAL_FORMS': '100000'}))
            self.assertFalse(response.context['ready'])
            self.assertLessEqual(len(response.context['lines'].forms), 50)
            self.assertEqual(self.client.put(url).status_code, 405)
            csrf = Client(enforce_csrf_checks=True)
            csrf.force_login(self.clerk)
            self.assertEqual(csrf.post(url, self.fields()).status_code, 403)
        self.assertContains(self.client.post(reverse('inventory:par-preparation'), self.fields()), 'DRAFT — FOR COMPLETION AND REVIEW')
