"""Bounded property draft entry preserves source access and supplied facts."""
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from inventory.models import Asset
from . import test_property_drafts as fixtures


class PropertyDraftLineEntryTests(TestCase):
    databases = {'default', 'finance'}
    fields = staticmethod(fixtures.PropertyDraftAccessTests.fields)

    @classmethod
    def setUpTestData(cls):
        fixtures.PropertyDraftAccessTests.setUpTestData.__func__(cls)

    def url(self, kind):
        return reverse(f'inventory:{kind}-preparation')

    def test_fifty_supplied_entries_are_all_printed_in_order(self):
        self.client.force_login(self.clerk)
        for kind, field in (('par', 'description'), ('ics', 'description'), ('spc', 'reference')):
            with self.subTest(kind=kind):
                values = self.fields(**{'lines-TOTAL_FORMS': '50'})
                values.update({f'lines-{i}-{field}': f'Supplied entry {i + 1}' for i in range(50)})
                result = self.client.post(self.url(kind), values)
                self.assertTrue(result.context['ready'])
                self.assertEqual([row[field] for row in result.context['print_lines']],
                                 [f'Supplied entry {i + 1}' for i in range(50)])
                self.assertIn('no-store', result['Cache-Control'])

    def test_growth_retains_invalid_inputs_and_omission_is_reversible(self):
        self.client.force_login(self.clerk)
        for kind, field in (('par', 'acquisition_cost'), ('ics', 'unit_cost'), ('spc', 'balance')):
            values = self.fields(**{'action': 'add_lines', 'header-fund': 'Keep this fund',
                                    f'lines-0-{field}': 'invalid',
                                    f'lines-4-{"reference" if kind == "spc" else "description"}': 'Retain fifth'})
            result = self.client.post(self.url(kind), values)
            self.assertEqual(len(result.context['lines'].forms), 10)
            self.assertFalse(result.context['ready'])
            self.assertContains(result, 'Keep this fund')
            self.assertContains(result, 'Retain fifth')
            self.assertContains(result, 'value="invalid"')
            self.assertNotContains(result, 'onclick="window.print()"')
            values.update({'action': 'preview', 'lines-TOTAL_FORMS': '10', 'lines-0-DELETE': 'on'})
            result = self.client.post(self.url(kind), values)
            self.assertTrue(result.context['ready'])
            self.assertEqual(len(result.context['print_lines']), 9)
            self.assertContains(result, 'value="invalid"')
            values.pop('lines-0-DELETE')
            self.assertFalse(self.client.post(self.url(kind), values).context['ready'])

    def test_source_drafts_keep_five_initial_slots_and_grow_without_writes(self):
        before = list(Asset.objects.values())
        for kind in ('par', 'ics'):
            url = reverse(f'inventory:asset-{kind}-preparation', args=[self.asset.pk])
            for actor in (self.clerk, self.viewer):
                self.client.force_login(actor)
                with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
                    opened = self.client.get(url)
                    self.assertEqual(len(opened.context['lines'].forms), 5)
                    self.assertEqual(opened.context['lines'].initial_form_count(), 1)
                    self.assertEqual(opened.context['lines'].forms[0].initial['description'], self.asset.asset_name)
                    values = self.fields(**{'lines-INITIAL_FORMS': '1', 'action': 'add_lines',
                                            'lines-0-description': 'Keep edited source', 'lines-0-quantity': '2'})
                    added = self.client.post(url, values)
                    self.assertEqual(len(added.context['lines'].forms), 10)
                    self.assertFalse(added.context['ready'])
                    values.update({'lines-TOTAL_FORMS': '10', 'action': 'preview'})
                    ready = self.client.post(url, values)
                    self.assertTrue(ready.context['ready'])
                    self.assertEqual(ready.context['print_lines'][0]['description'], 'Keep edited source')
                    self.assertContains(ready, 'source review')
                self.assertEqual(len(finance), 0)
                self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))
                malformed = self.client.post(url, self.fields(**{
                    'lines-INITIAL_FORMS': '1', 'lines-TOTAL_FORMS': '0', 'action': 'add_lines'}))
                self.assertFalse(malformed.context['ready'])
                self.assertTrue(malformed.context['lines'].non_form_errors())
        self.assertEqual(list(Asset.objects.values()), before)

    def test_malformed_counts_and_growth_at_limit_never_silently_drop_entries(self):
        self.client.force_login(self.clerk)
        for kind in ('par', 'ics', 'spc'):
            for total in ('-1', '51', '100000', 'invalid'):
                for action in ('preview', 'add_lines'):
                    result = self.client.post(self.url(kind), self.fields(**{
                        'lines-TOTAL_FORMS': total, 'action': action}))
                    self.assertFalse(result.context['ready'])
                    self.assertTrue(result.context['lines'].non_form_errors())
                    self.assertLessEqual(len(result.context['lines'].forms), 50)
            for initial in ('1', '2', '-1'):
                result = self.client.post(self.url(kind), self.fields(**{'lines-INITIAL_FORMS': initial}))
                self.assertFalse(result.context['ready'])
                self.assertTrue(result.context['lines'].non_form_errors())
            at_limit = self.client.post(self.url(kind), self.fields(**{
                'lines-TOTAL_FORMS': '50', 'action': 'add_lines'}))
            self.assertEqual(len(at_limit.context['lines'].forms), 50)
            self.assertFalse(at_limit.context['ready'])
            self.assertContains(at_limit, 'This sheet has 50 lines')

    def test_last_line_keeps_exact_amount_checks_and_unknown_zero_distinction(self):
        self.client.force_login(self.clerk)
        for kind, quantity in (('ics', 'quantity'), ('spc', 'received')):
            values = self.fields(**{'lines-TOTAL_FORMS': '50', f'lines-49-{quantity}': '3',
                                    'lines-49-unit_cost': '0.10', 'lines-49-total_cost': '0.31',
                                    f'lines-0-{"reference" if kind == "spc" else "description"}': 'Known item; unknown amount'})
            self.assertFalse(self.client.post(self.url(kind), values).context['ready'])
            values['lines-49-total_cost'] = '0.30'
            result = self.client.post(self.url(kind), values)
            self.assertTrue(result.context['ready'])
            self.assertEqual(result.context['print_lines'][49]['total_cost'], Decimal('0.30'))
            self.assertIsNone(result.context['print_lines'][0]['total_cost'])
            values.update({'lines-49-unit_cost': '0.00', 'lines-49-total_cost': '0.00'})
            self.assertEqual(self.client.post(self.url(kind), values).context['print_lines'][49]['total_cost'], 0)

    def test_growth_rechecks_source_export_authority(self):
        self.client.force_login(self.clerk)
        grant = Permission.objects.get(content_type__app_label='inventory', codename='export_asset_register')
        self.clerk.user_permissions.remove(grant)
        for kind in ('par', 'ics'):
            url = reverse(f'inventory:asset-{kind}-preparation', args=[self.asset.pk])
            self.assertEqual(self.client.post(url, self.fields(**{'action': 'add_lines'})).status_code, 403)
        for kind in ('par', 'ics', 'spc'):
            self.assertEqual(self.client.post(self.url(kind), self.fields(**{'action': 'add_lines'})).status_code, 200)
            self.client.force_login(self.outsider)
            self.assertEqual(self.client.post(self.url(kind), self.fields(**{'action': 'add_lines'})).status_code, 403)
            self.client.force_login(self.clerk)
