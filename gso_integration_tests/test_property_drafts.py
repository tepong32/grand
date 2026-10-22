"""Nonpersistent property drafts retain native access and honest unknowns."""
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.property_output_views import ICSLineForm, SPCLineForm
from inventory.models import Asset
from . import test_grand_maintenance


class PropertyDraftAmountTests(SimpleTestCase):
    def test_supplied_costs_use_exact_decimals_without_filling_unknowns(self):
        for form_class, quantity in ((ICSLineForm, 'quantity'), (SPCLineForm, 'received')):
            for data in ({}, {quantity: '3', 'unit_cost': '0.10'},
                         {quantity: '3', 'unit_cost': '0.10', 'total_cost': '0.30'},
                         {quantity: '1', 'unit_cost': '0.00', 'total_cost': '0.00'}):
                with self.subTest(form=form_class.__name__, data=data):
                    form = form_class(data)
                    self.assertTrue(form.is_valid(), form.errors)
                    expected = Decimal(data['total_cost']) if 'total_cost' in data else None
                    self.assertEqual(form.cleaned_data['total_cost'], expected)

    def test_mismatched_invalid_or_excessive_amounts_are_rejected(self):
        for form_class, quantity in ((ICSLineForm, 'quantity'), (SPCLineForm, 'received')):
            for updates in ({'total_cost': '0.31'}, {'unit_cost': '-1'},
                            {'unit_cost': 'NaN'}, {'unit_cost': '0.001'},
                            {'unit_cost': '10000000000000000.00'}, {quantity: '1.5'}, {quantity: '-1'}):
                with self.subTest(form=form_class.__name__, updates=updates):
                    data = {quantity: '3', 'unit_cost': '0.10', 'total_cost': '0.30', **updates}
                    self.assertFalse(form_class(data).is_valid())

    def test_spc_zero_and_unknown_balance_are_distinct(self):
        for value, expected in (('', None), ('0', 0), ('7', 7)):
            form = SPCLineForm({'balance': value})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['balance'], expected)
        self.assertFalse(SPCLineForm({'balance': '-1'}).is_valid())


class PropertyDraftAccessTests(TestCase):
    databases = {'default', 'finance'}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        cls.other.name, cls.other.slug = 'Engineering', 'engineering'
        cls.other.save(update_fields=['name', 'slug'])
        permissions = Permission.objects.filter(content_type__app_label='inventory')
        for actor in (cls.clerk, cls.viewer, cls.outsider):
            actor.user_permissions.add(*permissions)

    @staticmethod
    def fields(**values):
        return {'lines-TOTAL_FORMS': '5', 'lines-INITIAL_FORMS': '0',
                'lines-MIN_NUM_FORMS': '0', 'lines-MAX_NUM_FORMS': '5', **values}

    def test_native_view_and_uat_drafts_never_write_or_query_finance(self):
        for name in ('ics', 'spc'):
            for actor in (self.clerk, self.viewer):
                self.client.force_login(actor)
                with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
                    response = self.client.post(reverse(f'inventory:{name}-preparation'), self.fields())
                with self.subTest(name=name, actor=actor.username):
                    self.assertContains(response, 'DRAFT — FOR COMPLETION AND REVIEW')
                    self.assertContains(response, '[LGU / municipality]')
                    self.assertTrue(response.context['ready'])
                    self.assertIn('no-store', response['Cache-Control'])
                    self.assertIn('private', response['Cache-Control'])
                    self.assertEqual(len(finance), 0)
                    self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))

    def test_anonymous_ungranted_and_wrong_office_cannot_prepare_drafts(self):
        for name in ('ics', 'spc'):
            url = reverse(f'inventory:{name}-preparation')
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
            self.assertEqual(self.client.post(url, self.fields()).status_code, 302)
            for actor in (self.no_grant, self.super_no_grant, self.outsider):
                self.client.force_login(actor)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, self.fields()).status_code, 403)

    def test_print_previews_preserve_supplied_zero_unknowns_and_escaped_text(self):
        self.client.force_login(self.clerk)
        for name, quantity in (('ics', 'quantity'), ('spc', 'received')):
            response = self.client.post(reverse(f'inventory:{name}-preparation'), self.fields(**{
                'header-lgu': '<script>alert(1)</script>', f'lines-0-{quantity}': '2',
                'lines-0-unit_cost': '0.00', 'lines-0-total_cost': '0.00',
                'lines-1-description': 'Unknown amount',
            }))
            self.assertTrue(response.context['ready'])
            self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
            self.assertNotContains(response, '<script>alert(1)</script>')
            self.assertEqual(response.context['print_lines'][0]['total_cost'], Decimal('0.00'))
            self.assertIsNone(response.context['print_lines'][1].get('total_cost'))
            self.assertContains(response, 'Print / Save as PDF')
            self.assertNotContains(response, 'class="panel draft-editor" open')

    def test_invalid_entries_stay_editable_and_have_no_preview(self):
        self.client.force_login(self.clerk)
        for name, quantity in (('ics', 'quantity'), ('spc', 'received')):
            response = self.client.post(reverse(f'inventory:{name}-preparation'), self.fields(**{
                'header-lgu': 'Keep my entries', f'lines-0-{quantity}': '3',
                'lines-0-unit_cost': '0.10', 'lines-0-total_cost': '0.31',
            }))
            self.assertFalse(response.context['ready'])
            self.assertContains(response, 'Check the source amounts.')
            self.assertContains(response, 'Keep my entries')
            self.assertContains(response, 'class="panel draft-editor" open')
            self.assertNotContains(response, 'id="draft-preview"')

    def test_formset_limits_methods_and_csrf_are_enforced(self):
        self.client.force_login(self.clerk)
        for name in ('ics', 'spc'):
            url = reverse(f'inventory:{name}-preparation')
            for fields in ({}, self.fields(**{'lines-TOTAL_FORMS': '100000'})):
                response = self.client.post(url, fields)
                self.assertFalse(response.context['ready'])
                self.assertLessEqual(len(response.context['lines'].forms), 50)
            self.assertEqual(self.client.put(url).status_code, 405)
            from django.test import Client
            csrf = Client(enforce_csrf_checks=True)
            csrf.force_login(self.clerk)
            self.assertEqual(csrf.post(url, self.fields()).status_code, 403)

    def test_register_links_to_both_drafts_and_keeps_par_available(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse('inventory:property-register'))
        for name in ('par', 'ics', 'spc'):
            self.assertContains(response, reverse(f'inventory:{name}-preparation'))

    def test_asset_copy_preserves_unknowns_without_guessing_local_identities(self):
        self.asset.quantity, self.asset.unit_cost = 2, None
        self.asset.property_tag, self.asset.supplier = 'REGISTER-TAG-ONLY', 'Not a draft supplier field'
        self.asset.save()
        self.client.force_login(self.clerk)
        url = reverse('inventory:asset-ics-preparation', args=[self.asset.pk])
        response = self.client.get(url)
        initial = response.context['lines'].forms[0].initial
        self.assertEqual(initial, {'description': self.asset.asset_name, 'quantity': 2, 'unit_cost': None})
        self.assertNotIn('inventory_number', initial)
        self.assertNotIn('recipient', response.context['header'].initial)
        self.assertContains(response, 'REGISTER-TAG-ONLY')
        self.assertNotContains(response, 'Not a draft supplier field')
        self.asset.unit_cost = Decimal('0.00')
        self.asset.save()
        response = self.client.get(url)
        self.assertEqual(response.context['lines'].forms[0].initial['unit_cost'], Decimal('0.00'))

    def test_asset_copy_and_edit_are_scoped_readonly_for_clerk_and_uat(self):
        url = reverse('inventory:asset-ics-preparation', args=[self.asset.pk])
        before = (self.asset.asset_name, self.asset.quantity, self.asset.status, self.asset.unit_cost)
        data = self.fields(**{'lines-INITIAL_FORMS': '1', 'lines-0-description': 'Edited draft only',
                              'lines-0-quantity': '3', 'lines-0-unit_cost': '0.10', 'lines-0-total_cost': '0.30'})
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
                entry = self.client.get(url)
                response = self.client.post(url, data)
            self.assertEqual(entry.status_code, 200)
            self.assertTrue(response.context['ready'])
            self.assertContains(response, 'Edited draft only')
            self.assertContains(response, 'Draft values require source review')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(len(finance), 0)
            self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))
        self.asset.refresh_from_db()
        self.assertEqual((self.asset.asset_name, self.asset.quantity, self.asset.status, self.asset.unit_cost), before)

    def test_copy_requires_export_grant_but_blank_drafts_remain_readable(self):
        self.no_grant.user_permissions.add(*Permission.objects.filter(content_type__app_label='inventory',
            codename__in=('view_asset', 'view_property_determination')))
        self.client.force_login(self.no_grant)
        response = self.client.get(reverse('inventory:property-register'))
        self.assertContains(response, 'Prepare ICS draft')
        self.assertNotContains(response, 'Start ICS draft with register details')
        self.assertEqual(self.client.get(reverse('inventory:ics-preparation')).status_code, 200)
        url = reverse('inventory:asset-ics-preparation', args=[self.asset.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, self.fields()).status_code, 403)
        self.client.force_login(self.super_no_grant)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_foreign_owner_is_hidden_even_if_asset_is_assigned_to_requester_office(self):
        foreign = Asset.objects.create(department_id=self.other.pk, asset_name='Foreign owner confidential',
                                       assigned_department_id=self.gso.pk)
        self.client.force_login(self.clerk)
        url = reverse('inventory:asset-ics-preparation', args=[foreign.pk])
        for response in (self.client.get(url), self.client.post(url, self.fields())):
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, 'Foreign owner confidential', status_code=404)
        register = self.client.get(reverse('inventory:property-register'))
        self.assertContains(register, reverse('inventory:asset-ics-preparation', args=[self.asset.pk]))
        self.assertNotContains(register, url)

    def test_copy_rechecks_source_owner_and_export_grant_on_post(self):
        url = reverse('inventory:asset-ics-preparation', args=[self.asset.pk])
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(url).status_code, 200)
        permission = Permission.objects.get(content_type__app_label='inventory', codename='export_asset_register')
        self.clerk.user_permissions.remove(permission)
        self.assertEqual(self.client.post(url, self.fields()).status_code, 403)
        self.clerk.user_permissions.add(permission)
        self.assertEqual(self.client.get(url).status_code, 200)
        Asset.objects.filter(pk=self.asset.pk).update(department_id=self.other.pk)
        self.assertEqual(self.client.post(url, self.fields()).status_code, 404)
