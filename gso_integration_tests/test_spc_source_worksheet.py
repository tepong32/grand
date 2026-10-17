"""Source worksheets preserve the existing reviewed quantity/integrity boundary."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory import property_determinations as properties
from inventory.models import Asset
from . import test_grand_property_movements as chain


class SPCSourceWorksheetTests(TestCase):
    databases = {'default', 'finance'}

    @classmethod
    def setUpTestData(cls):
        chain.PropertyMovementChainTests.setUpTestData.__func__(cls)

    def setUp(self):
        fixture = chain.PropertyMovementChainTests('test_real_receipt_issue_return_disposal_sources_project_without_repeating_movements')
        self.addCleanup(fixture.doCleanups)
        for name in ('gso', 'other', 'clerk', 'outsider', 'no_grant', 'super_no_grant', 'viewer', 'asset'):
            setattr(fixture, name, getattr(self, name))
        fixture.setUp()
        self.fixture = fixture
        self.export = Permission.objects.get(content_type__app_label='inventory', codename='export_asset_register')
        for actor in (self.clerk, self.viewer, self.outsider):
            actor.user_permissions.add(self.export)
        self.determination = fixture.determination = fixture.determine()
        self.opening = fixture.decide(fixture.record())
        self.url = reverse('inventory:spc-source-worksheet')
        self.client.force_login(self.clerk)

    def query(self, **changes):
        return {'property_class': 'Equipment', 'fund': 'General fund',
                'cutoff': timezone.localdate().isoformat(), **changes}

    def test_native_clerk_and_uat_read_reviewed_sources_without_writes_or_finance(self):
        for actor in (self.clerk, self.viewer):
            self.client.force_login(actor)
            with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
                response = self.client.get(self.url, self.query())
            self.assertContains(response, 'DRAFT - SPC source worksheet')
            self.assertTrue(response.context['prepared'])
            projection = response.context['rows'][0]['projection']
            self.assertEqual(projection['balance'], 1)
            self.assertEqual(projection['opening'].pk, self.opening.pk)
            self.assertIsNone(projection['opening'].unit_cost)
            self.assertContains(response, 'Unknown')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(len(finance), 0)
            self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in default))

    def test_missing_opening_stays_unresolved_beside_valid_item(self):
        other = Asset.objects.create(department_id=self.gso.pk, asset_name='Documented item without opening')
        self.fixture.asset = other
        self.fixture.determine()
        response = self.client.get(self.url, self.query())
        self.assertEqual(len(response.context['rows']), 2)
        missing = next(row for row in response.context['rows'] if row['asset'].pk == other.pk)['projection']
        self.assertIsNone(missing['balance'])
        self.assertIsNone(missing['opening'])
        self.assertEqual(missing['rows'], [])
        self.assertContains(response, 'Balance unresolved.')
        self.assertContains(response, 'No independently verified opening balance')
        self.assertContains(response, 'No quantities or costs are added across items.')

    def test_corrupted_opening_evidence_exposes_no_usable_quantities(self):
        Path(self.opening.file.path).write_bytes(b'%PDF-changed source')
        response = self.client.get(self.url, self.query())
        projection = response.context['rows'][0]['projection']
        self.assertTrue(projection['issues'])
        self.assertIsNone(projection['opening'])
        self.assertIsNone(projection['balance'])
        self.assertEqual(projection['rows'], [])
        self.assertNotContains(response, 'Opening: 1')

    def test_pending_correction_suppresses_all_source_quantities(self):
        self.fixture.record(expected_predecessor=str(self.opening.public_id),
                            data=self.fixture.data(reference='Pending correction'))
        response = self.client.get(self.url, self.query())
        projection = response.context['rows'][0]['projection']
        self.assertTrue(any('pending' in issue.lower() for issue in projection['issues']))
        self.assertIsNone(projection['balance'])
        self.assertIsNone(projection['opening'])

    def test_current_fund_label_cannot_relabel_old_reviewed_opening(self):
        data = {name: getattr(self.determination, name) for name in properties.CONTENT_FIELDS}
        data.update(fund_label='Another fund', reference='Successor classification', reason='Supplied fund correction')
        successor = properties.record(actor=self.clerk, asset=self.asset, request_id=uuid4(),
            expected_source=properties.source_basis(self.asset), expected_predecessor=str(self.determination.public_id),
            data=data, upload=self.fixture.upload())
        properties.decide(actor=self.fixture.reviewer, row=successor, expected_version=1,
                          action='verify', note='Independent source review')
        response = self.client.get(self.url, self.query(fund='Another fund'))
        projection = response.context['rows'][0]['projection']
        self.assertTrue(any('different class or fund' in issue for issue in projection['issues']))
        self.assertIsNone(projection['balance'])
        self.assertIsNone(projection['opening'])
        self.assertNotContains(response, 'Opening: 1')

    def test_grants_are_explicit_and_other_office_choices_do_not_leak(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        for actor in (self.super_no_grant, self.no_grant):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.clerk)
        self.clerk.user_permissions.remove(self.export)
        self.assertEqual(self.client.get(self.url, self.query()).status_code, 403)
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, self.query())
        self.assertFalse(response.context['prepared'])
        self.assertEqual(response.context['rows'], [])
        self.assertEqual(list(response.context['form'].fields['property_class'].choices), [('', 'Choose a supplied class')])
        self.assertNotContains(response, self.asset.asset_name)

    def test_invalid_future_and_forged_choices_produce_no_source_output(self):
        for changes in ({'cutoff': 'not-a-date'}, {'cutoff': timezone.localdate()+timedelta(days=1)},
                        {'property_class': 'Foreign class'}, {'fund': 'Foreign fund'}):
            response = self.client.get(self.url, self.query(**changes))
            self.assertFalse(response.context['prepared'])
            self.assertEqual(response.context['rows'], [])
        self.assertEqual(self.client.post(self.url, self.query()).status_code, 405)

    def test_register_exposes_shortcut_only_with_source_and_export_authority(self):
        register = reverse('inventory:property-register')
        self.assertContains(self.client.get(register), self.url)
        self.clerk.user_permissions.remove(self.export)
        self.assertNotContains(self.client.get(register), self.url)

    def test_exact_source_labels_are_not_combined_by_database_collation(self):
        other = Asset.objects.create(department_id=self.gso.pk, asset_name='Distinct supplied label')
        data = {name: getattr(self.determination, name) for name in properties.CONTENT_FIELDS}
        data.update(fund_label='general fund', reference='Distinct label source')
        row = properties.record(actor=self.clerk, asset=other, request_id=uuid4(),
            expected_source=properties.source_basis(other), expected_predecessor=None,
            data=data, upload=self.fixture.upload())
        properties.decide(actor=self.fixture.reviewer, row=row, expected_version=1,
                          action='verify', note='Independent document check')
        response = self.client.get(self.url, self.query())
        choices = list(response.context['form'].fields['fund'].choices)
        self.assertIn(('General fund', 'General fund'), choices)
        self.assertIn(('general fund', 'general fund'), choices)
        self.assertEqual([row['asset'].pk for row in response.context['rows']], [self.asset.pk])

    def test_reviewed_zero_cost_is_printed_and_never_replaced_with_unknown(self):
        successor = self.fixture.record(expected_predecessor=str(self.opening.public_id),
            data=self.fixture.data(reference='Documented zero cost', unit_cost=Decimal('0.00')))
        self.fixture.decide(successor)
        response = self.client.get(self.url, self.query())
        projection = response.context['rows'][0]['projection']
        self.assertFalse(projection['issues'])
        self.assertEqual(projection['opening'].unit_cost, Decimal('0.00'))
        self.assertContains(response, '<td>0.00</td>', html=True)
