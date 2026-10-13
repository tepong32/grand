from copy import deepcopy
from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from accounting.models import FundingSource, LedgerAccount, JournalEntry
from accounting.cash_classifications import checksum
from accounting.summary_actuals import RECEIPTS
from .test_native_summary_reconciliation import NativeSummaryReconciliationFixture
from .resource_context import save_estimate
from .actuals_selection import select_source
from .services import consolidate_versions, transition_version
from . import receipt_forecasts as service, summary_reconciliations


class ReceiptForecastTests(NativeSummaryReconciliationFixture):
    def prepare_resources(self):
        self.revenue = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='SYN-FORECAST-SERVICE',
            title='Synthetic forecast service account', account_type='revenue', normal_balance='credit')
        source = FundingSource.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, fiscal_year=self.version.fiscal_year, fund=self.fund,
            code='SYN-FORECAST', name='Synthetic shared forecast source', kind='local',
            authority_reference='Synthetic financing authority', effective_from=date(2027,1,1))
        self.resources=[]
        for index in range(2):
            self.version.refresh_from_db()
            self.resources.append(save_estimate(version=self.version,actor=self.preparer,funding_source=source,
                description='Shared source worksheet '+str(index),amount=Decimal('100'),basis='Synthetic projected receipts',
                expected_state_version=self.version.state_version,reason='Retain proposed financing source'))

    def setUp(self):
        super().setUp()
        self.reconciliation = summary_reconciliations.prepare(**self.args())
        self.accept(self.reconciliation)
        self.reconciliation.refresh_from_db()
        self.captured = service.capture(reconciliation=self.reconciliation,actor=self.preparer)

    def component(self, identity, source_id, amount='100', **changes):
        row=dict(key=identity,source_id=str(source_id),amount=amount,disposition='include',category='service',
            account_id=self.revenue.pk,coverage_key=identity,overlap_of='',basis='Explicit synthetic forecast mapping')
        row.update(changes); return row

    def coverage(self, components):
        return [dict(category=key,
            amount=str(sum((Decimal(row['amount']) for row in components if row['disposition']=='include' and row['category']==key),Decimal('0.00'))),
            coverage='estimate' if any(row['disposition']=='include' and row['category']==key for row in components) else 'no_estimate',
            basis='Explicit synthetic full-category forecast declaration') for key in RECEIPTS]

    def inputs(self, **changes):
        half=[self.component('half-service','worksheet','30')]
        proposed=[self.component('source-a',self.resources[0].pk),
            self.component('source-b',self.resources[1].pk,disposition='overlap',coverage_key='source-a',overlap_of='source-a')]
        args=dict(half_sources=[dict(id='worksheet',amount='30',reference='Synthetic H2 collection worksheet',
            as_of='2026-09-01',basis='Synthetic dated Budget forecast basis')],half_components=half,
            proposed_components=proposed,coverage=dict(half_estimate=self.coverage(half),proposed=self.coverage(proposed)))
        args.update(changes); return args

    def test_real_capture_exact_partitions_overlap_and_pure_reproduction_without_posting(self):
        before=JournalEntry.objects.count()
        captured=deepcopy(self.captured)
        with self.assertNumQueries(0,using='finance'),self.assertNumQueries(0,using='default'):
            proposal=service.propose(captured,**self.inputs())
            body=service.verify(proposal)
        self.assertTrue(body['classification_complete'])
        self.assertEqual(body['columns']['proposed']['controls'],dict(include='100.00',overlap='100.00',
            exclude='0.00',unresolved='0.00',source_total='200.00',partition_total='200.00'))
        self.assertEqual(body['columns']['half_estimate']['diagnostic_total'],'30.00')
        self.assertIsNone(body['columns']['proposed']['official_total'])
        self.assertFalse(body['cash_available']); self.assertFalse(body['actual_receipts'])
        self.assertEqual(captured,self.captured); self.assertEqual(JournalEntry.objects.count(),before)
        self.assertNotIn('actuals',captured['payload'])
        self.assertNotIn('trial_balance',captured['payload'])
        independent=self.inputs()
        independent['proposed_components'][1].update(disposition='include',coverage_key='source-b',overlap_of='')
        independent['coverage']['proposed']=self.coverage(independent['proposed_components'])
        # A shared FundingSource is not proof that distinct original worksheets
        # describe the same receipts. Only an explicit overlap removes a component.
        self.assertEqual(service.propose(captured,**independent)['payload']['columns']['proposed']['diagnostic_total'],'200.00')

    def test_splits_zero_forecast_and_unresolved_coverage_never_imply_authority(self):
        args=self.inputs()
        proposed=[self.component('a60',self.resources[0].pk,'60'),self.component('a40',self.resources[0].pk,'40'),
            self.component('b60',self.resources[1].pk,'60',disposition='overlap',coverage_key='a60',overlap_of='a60'),
            self.component('b40',self.resources[1].pk,'40',disposition='overlap',coverage_key='a40',overlap_of='a40')]
        args['proposed_components']=proposed; args['coverage']['proposed']=self.coverage(proposed)
        body=service.propose(self.captured,**args)['payload']
        self.assertEqual(body['columns']['proposed']['diagnostic_total'],'100.00')
        args['half_sources'][0]['amount']='0'; args['half_components'][0]['amount']='0'
        args['coverage']['half_estimate']=self.coverage(args['half_components'])
        body=service.propose(self.captured,**args)['payload']
        self.assertTrue(body['classification_complete'])
        leaf=next(row for row in body['columns']['half_estimate']['categories'] if row['category']=='service')
        self.assertEqual(leaf['coverage'],'estimate'); self.assertEqual(leaf['amount'],'0.00')
        args['proposed_components'][0].update(disposition='unresolved',account_id=None,coverage_key='')
        args['proposed_components'][2].update(disposition='unresolved',account_id=None,coverage_key='',overlap_of='')
        args['coverage']['proposed']=self.coverage(args['proposed_components'])
        args['coverage']['proposed'][0]['coverage']='unresolved'
        body=service.propose(self.captured,**args)['payload']
        self.assertFalse(body['classification_complete']); self.assertIsNone(body['columns']['proposed']['official_total'])
        self.assertTrue(body['issues'])

    def test_duplicate_missing_amount_invalid_overlap_account_period_and_metadata_are_rejected(self):
        base=self.inputs()
        cases=[]
        duplicate=deepcopy(base); duplicate['proposed_components'][1].update(disposition='include',overlap_of='')
        cases.append(duplicate)
        partial=deepcopy(base); partial['proposed_components'][1]['amount']='99'; cases.append(partial)
        chain=deepcopy(base); chain['proposed_components'][1]['overlap_of']='source-b'; cases.append(chain)
        bad_account=deepcopy(base); bad_account['half_components'][0]['account_id']=self.account.pk; cases.append(bad_account)
        bad_category=deepcopy(base); bad_category['half_components'][0]['category']='local-total'; cases.append(bad_category)
        future=deepcopy(base); future['half_sources'][0]['as_of']='2028-01-01'; cases.append(future)
        missing=deepcopy(base); missing['coverage']['proposed'].pop(); cases.append(missing)
        negative=deepcopy(base); negative['half_sources'][0]['amount']='-30'; cases.append(negative)
        nan=deepcopy(base); nan['half_sources'][0]['amount']='NaN'; cases.append(nan)
        for args in cases:
            with self.subTest(args=args),self.assertRaises(ValidationError): service.propose(self.captured,**args)
        proposal=service.propose(self.captured,**base)
        proposal['payload']['columns']['proposed']['controls']['include']='200.00'
        proposal['checksum']=checksum(proposal['payload'])
        with self.assertRaises(ValidationError): service.verify(proposal)
        dated=deepcopy(self.captured)
        account=next(row for row in dated['payload']['accounts'] if row['id']==self.revenue.pk)
        account['effective_from']='2027-07-01'
        dated['checksum']=checksum(dated['payload'])
        with self.assertRaisesMessage(ValidationError,'applicable original account'):
            service.propose(dated,**base)
        # An account available during part of the proposed year remains an explicit
        # estimate mapping; this does not authorize a dated journal posting.
        other=next(row for row in self.captured['payload']['accounts']
            if row['account_type']=='asset' and row['is_active'] and row['allow_posting'])
        args=deepcopy(base); args['half_components'][0]['account_id']=other['id']
        self.assertTrue(service.propose(dated,**args)['payload']['classification_complete'])
        account['effective_from']='2028-01-01'
        dated['checksum']=checksum(dated['payload'])
        with self.assertRaisesMessage(ValidationError,'applicable original account'):
            service.propose(dated,**args)

    def test_scope_capture_permissions_source_drift_and_unfunded_resource_controls(self):
        with self.assertRaises(PermissionDenied): service.capture(reconciliation=self.reconciliation,actor=self.maker)
        permission=Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals')
        self.preparer.user_permissions.remove(permission)
        fresh=get_user_model().objects.get(pk=self.preparer.pk)
        with self.assertRaises(PermissionDenied): service.capture(reconciliation=self.reconciliation,actor=fresh)
        self.preparer.user_permissions.add(permission)
        funding=self.resources[0].funding_source
        funding.name='Changed source after approval'; funding.save(update_fields=('name',))
        with self.assertRaisesMessage(ValidationError,'changed after submission'):
            service.capture(reconciliation=self.reconciliation,actor=self.preparer)
        original=service.propose(self.captured,**self.inputs())
        self.assertEqual(service.verify(original)['columns']['proposed']['diagnostic_total'],'100.00')
        shadow=deepcopy(self.captured)
        for source in shadow['payload']['resources']['rows']: source['funding_source']['fund_id']=None
        primary=shadow['payload']['proposal']['public_id']
        shadow['payload']['resource_nodes'][primary]['resources']=deepcopy(shadow['payload']['resources'])
        shadow['payload']['resource_roots']=service._roots(shadow['payload']['resource_nodes'],primary)
        shadow['checksum']=checksum(shadow['payload'])
        with self.assertRaisesMessage(ValidationError,'require this Fund'):
            service.propose(shadow,**self.inputs())

    def test_copied_resource_identity_caps_and_nested_original_lineage_are_not_label_deduplication(self):
        shadow=deepcopy(self.captured); body=shadow['payload']; primary=body['proposal']['public_id']
        original=deepcopy(body['resources']['rows'][0]); first,second=body['resources']['rows']
        # Detached reproduction fixture of original retained consolidation evidence.
        original_proposal='11111111-1111-4111-8111-111111111111'
        node=deepcopy(body['resource_nodes'][primary]); node['proposal']=original_proposal
        node['resources']['rows']=[original]; node['resources']['origins']=[]
        body['resource_nodes'][original_proposal]=node
        origins=[dict(target_resource_id=row['id'],source_proposal=original_proposal,source_resource=deepcopy(original))
            for row in (first,second)]
        # Copies must match the original full estimate, regardless of display labels.
        second.update({name:deepcopy(value) for name,value in original.items() if name!='id'})
        body['resources']['origins']=origins
        body['resource_nodes'][primary]['resources']=deepcopy(body['resources'])
        body['resource_roots']=service._roots(body['resource_nodes'],primary)
        shadow['checksum']=checksum(body)
        args=self.inputs(); args['proposed_components'][1].update(disposition='include',coverage_key='different-label',overlap_of='')
        args['coverage']['proposed']=self.coverage(args['proposed_components'])
        with self.assertRaisesMessage(ValidationError,'original retained resource amount'):
            service.propose(shadow,**args)
        self.assertEqual(service.propose(shadow,**self.inputs())['payload']['columns']['proposed']['diagnostic_total'],'100.00')
        body['resource_nodes'][original_proposal]['resources']['origins']=[dict(target_resource_id=original['id'],
            source_proposal=primary,source_resource=deepcopy(first))]
        with self.assertRaises(ValidationError): service._roots(body['resource_nodes'],primary)

    def test_real_approved_consolidation_reproduces_original_source_identities(self):
        prior=next(row['source_id'] for row in self.version.actuals_source_selection.values() if row['prefix']=='prior')
        half=self.adopt('100')
        target=consolidate_versions(sources=[self.version],user=self.reviewer,
            title='Synthetic complete financing consolidation',change_explanation='Retain original financing sources')
        for prefix,identity in (('prior',prior),('half',half.public_id)):
            target=select_source(version=target,actor=self.preparer,fund_id=self.fund.pk,center_id=self.center.pk,
                prefix=prefix,kind='external',source_id=identity,expected_state_version=target.state_version,
                reason='Explicit original synthetic certificate selection for consolidated office context')
        target=transition_version(target,'submit',self.preparer)
        target=transition_version(target,'approve',self.reviewer,'Independent consolidated financing review')
        primary=str(target.public_id); original=str(self.version.public_id)
        nodes={primary:service._resource_node(target),original:service._resource_node(self.version)}
        roots=service._roots(nodes,primary)
        self.assertEqual(len(roots),2)
        self.assertEqual({row['resource_id'] for row in roots.values()},{item.pk for item in self.resources})
        for row in roots.values():
            self.assertEqual(row['proposal'],original)
            self.assertEqual(len(row['path']),2)
            self.assertEqual(row['resource']['amount'],'100.00')
