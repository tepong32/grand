from copy import deepcopy
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from .models import BudgetReceiptForecast as Record
from .test_native_summary_reconciliation import NativeSummaryReconciliationFixture
from . import test_receipt_forecasts as proposal_fixtures
from . import receipt_forecasts as forecasts, receipt_forecast_reviews as service, summary_reconciliations, office_forms


class ReceiptForecastReviewFixture(NativeSummaryReconciliationFixture):
    prepare_resources = proposal_fixtures.ReceiptForecastTests.prepare_resources
    component = proposal_fixtures.ReceiptForecastTests.component
    coverage = proposal_fixtures.ReceiptForecastTests.coverage
    inputs = proposal_fixtures.ReceiptForecastTests.inputs

    def setup_forecast(self):
        self.reconciliation = summary_reconciliations.prepare(**self.args())
        self.accept(self.reconciliation)
        self.reconciliation.refresh_from_db()
        self.captured = forecasts.capture(reconciliation=self.reconciliation, actor=self.preparer)
        for actor, actions in ((self.preparer, ('view', 'export', 'prepare')), (self.reviewer, ('view', 'export', 'review'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget',
                codename__in=[action+'_budget_receipt_forecasts' for action in actions]))
        self.forecast = forecasts.propose(self.captured, **self.inputs())
        scope = self.captured['payload']['scope']
        self.entities = [dict(key=scope['entity_key'], label=scope['entity_label'])]

    def setUp(self):
        super().setUp()
        self.setup_forecast()

    def prepare_forecast(self, **changes):
        args = dict(proposal=self.version, actor=self.preparer, fund_id=self.fund.pk, proposals=[self.forecast],
            entity_inventory=self.entities, coverage_reference='Synthetic complete Fund/entity forecast inventory',
            coverage_confirmed=True, expected_latest=0)
        args.update(changes)
        return service.prepare(**args)

    def review_forecast(self, record, **changes):
        args = dict(actor=self.reviewer, approve=True, authority='Synthetic designated independent Budget Officer',
            note='Verified complete sources, category mappings and entity allocation')
        args.update(changes)
        return service.review(record, **args)


class ReceiptForecastReviewTests(ReceiptForecastReviewFixture):
    def test_retention_independent_authority_pure_reproduction_and_no_posting(self):
        before = JournalEntry.objects.count()
        record = self.prepare_forecast()
        self.assertIsNone(service.snapshot(record, self.preparer)['reviewed_totals'])
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',
            codename='review_budget_receipt_forecasts'))
        with self.assertRaisesMessage(ValidationError, 'different designated Budget Officer'):
            self.review_forecast(record, actor=self.preparer)
        record = self.review_forecast(record)
        retained = service.snapshot(record, self.preparer, export=True)
        self.assertEqual(retained['reviewed_totals']['general'], dict(half_estimate='30.00', proposed='100.00'))
        self.assertFalse(retained['actual_receipts']); self.assertFalse(retained['cash_available']); self.assertFalse(retained['form_issued'])
        self.assertTrue(service.is_current(record, self.preparer))
        record = Record.objects.select_related('proposal').get(pk=record.pk)
        with self.assertNumQueries(0, using='finance'), self.assertNumQueries(0, using='default'):
            service.verify(record)
        with self.assertRaises(ValidationError): self.review_forecast(record)
        record.payload['group']['coverage_reference'] = 'Overwrite retained coverage'
        with self.assertRaises(ValidationError): record.save()
        with self.assertRaises(ValidationError): record.delete()
        self.assertEqual(JournalEntry.objects.count(), before)

    def test_successor_source_change_stale_return_and_original_export(self):
        record = self.prepare_forecast()
        self.revenue.title = 'Changed original mapping after preparation'; self.revenue.save(update_fields=('title',))
        with self.assertRaisesMessage(ValidationError, 'source evidence changed'): self.review_forecast(record)
        returned = self.review_forecast(record, approve=False)
        self.assertEqual(returned.status, 'returned'); service.verify(returned)
        self.captured = forecasts.capture(reconciliation=self.reconciliation, actor=self.preparer)
        self.forecast = forecasts.propose(self.captured, **self.inputs())
        current = self.review_forecast(self.prepare_forecast(expected_latest=1))
        retained = service.snapshot(current, self.preparer, export=True)
        self.assertTrue(service.is_current(current, self.preparer))
        self.prepare_forecast(expected_latest=2)
        self.assertFalse(service.is_current(current, self.preparer))
        self.assertEqual(service.snapshot(current, self.preparer, export=True), retained)
        with self.assertRaisesMessage(ValidationError, 'newer forecast'): self.prepare_forecast(expected_latest=2)
        changed = deepcopy(current.payload)
        changed['group']['controls']['proposed']['diagnostic_total'] = '200.00'
        Record.objects.filter(pk=current.pk).update(payload=changed, payload_checksum=checksum(changed))
        current.refresh_from_db()
        with self.assertRaises(ValidationError): service.verify(current)

    def test_explicit_permissions_uat_read_export_and_foreign_owner(self):
        record = self.prepare_forecast()
        with self.assertRaises(PermissionDenied): self.prepare_forecast(actor=self.maker)
        with self.assertRaises(PermissionDenied): service.snapshot(record, self.maker)
        permission = Permission.objects.get(content_type__app_label='budget', codename='review_budget_receipt_forecasts')
        self.reviewer.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied): self.review_forecast(record)
        self.reviewer.user_permissions.add(permission)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        service.snapshot(record, self.preparer)
        with self.assertRaises(PermissionDenied): self.prepare_forecast(expected_latest=1)
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied): self.review_forecast(record, approve=False)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',
            codename='export_native_budget_actuals'))
        service.snapshot(record, self.preparer)
        with self.assertRaises(PermissionDenied): service.snapshot(record, self.preparer, export=True)

    def test_dedicated_role_definitions_support_review_without_generic_proposal_mutation(self):
        from vouchers.roles import FINANCE_ROLE_PERMISSIONS
        record = self.prepare_forecast()
        actor = self.employee(self.budget_office, 'forecast.designated.officer')
        for name in ('Budget Receipt Forecast Preparer', 'Budget Receipt Forecast Officer Reviewer'):
            role = Group.objects.get_or_create(name=name)[0]
            for label in FINANCE_ROLE_PERMISSIONS[name]:
                app, code = label.split('.', 1)
                role.permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        actor.groups.add(Group.objects.get(name='Budget Receipt Forecast Officer Reviewer'))
        self.assertFalse(actor.has_perm('budget.review_budget_proposals'))
        self.assertEqual(self.review_forecast(record, actor=actor).status, 'approved')

    def test_stale_native_office_and_reconciliation_inventory_do_not_approve(self):
        record = self.prepare_forecast()
        office_forms.prepare(**self.form_args(expected_latest=1))
        with self.assertRaisesMessage(ValidationError, 'newer office form'): self.review_forecast(record)
        self.assertEqual(self.review_forecast(record, approve=False).status, 'returned')
        with self.assertRaisesMessage(ValidationError, 'newer office form'):
            self.prepare_forecast(expected_latest=1)

    def test_pending_native_successor_blocks_approval_but_preserves_return(self):
        record = self.prepare_forecast()
        self.make_actuals(2026, 6, certify=False, expected_latest=1)
        with self.assertRaisesMessage(ValidationError, 'stale'): self.review_forecast(record)
        self.assertEqual(self.review_forecast(record, approve=False).status, 'returned')

    def test_pending_reconciliation_head_blocks_approval_but_preserves_return(self):
        record = self.prepare_forecast()
        summary_reconciliations.prepare(**self.args(expected_latest=1))
        with self.assertRaisesMessage(ValidationError, 'latest independently accepted'): self.review_forecast(record)
        self.assertEqual(self.review_forecast(record, approve=False).status, 'returned')

    def test_unresolved_coverage_incomplete_inventory_and_untrusted_capture_are_rejected(self):
        args = self.inputs(); args['coverage']['half_estimate'][0]['coverage'] = 'unresolved'
        pending = forecasts.propose(self.captured, **args)
        record = self.prepare_forecast(proposals=[pending])
        with self.assertRaisesMessage(ValidationError, 'classification resolved'): self.review_forecast(record)
        self.review_forecast(record, approve=False)
        for changes in (dict(entity_inventory=[]), dict(coverage_confirmed=False), dict(expected_latest=True)):
            with self.subTest(changes=changes), self.assertRaises(ValidationError): self.prepare_forecast(**changes)
        forged = deepcopy(self.captured)
        forged['payload']['accounts'][0]['title'] = 'Fabricated capture metadata'
        forged['checksum'] = checksum(forged['payload'])
        untrusted = forecasts.propose(forged, **self.inputs())
        with self.assertRaisesMessage(ValidationError, 'source evidence changed'):
            self.prepare_forecast(proposals=[untrusted], expected_latest=1)

    def test_shared_sources_cross_entity_caps_and_inventory_are_explicit(self):
        # Detached arithmetic fixtures exercise two entity allocations without
        # claiming a second jointly certified native reporting entity.
        captured = deepcopy(self.captured)
        captured['payload']['scope'].update(entity_key='enterprise', entity_label='Synthetic enterprise')
        captured['checksum'] = checksum(captured['payload'])
        second = forecasts.propose(captured, **self.inputs())
        entities = [dict(key='enterprise', label='Synthetic enterprise'), *self.entities]
        with self.assertRaisesMessage(ValidationError, 'same funding coverage'):
            service.combine([self.forecast, second], entity_inventory=entities, coverage_reference='Explicit synthetic entity coverage')
        args = self.inputs()
        for row in args['half_components']:
            row.update(disposition='exclude', category='', account_id=None, coverage_key='', overlap_of='')
        for row in args['proposed_components']:
            row.update(disposition='exclude', category='', account_id=None, coverage_key='', overlap_of='')
        args['coverage'] = dict(half_estimate=self.coverage(args['half_components']), proposed=self.coverage(args['proposed_components']))
        second = forecasts.propose(captured, **args)
        group = service.combine([self.forecast, second], entity_inventory=entities, coverage_reference='Explicit synthetic entity coverage')
        self.assertEqual(group['controls']['proposed']['diagnostic_total'], '100.00')
        with self.assertRaisesMessage(ValidationError, 'inventory changed'):
            self.prepare_forecast(proposals=[self.forecast, second], entity_inventory=entities)
        args = self.inputs()
        args['half_components'][0]['coverage_key'] = 'different-entity-claim'
        args['proposed_components'][0]['coverage_key'] = 'different-entity-claim'
        args['proposed_components'][1]['coverage_key'] = 'different-entity-claim'
        second = forecasts.propose(captured, **args)
        with self.assertRaisesMessage(ValidationError, 'exceed an original'):
            service.combine([self.forecast, second], entity_inventory=entities, coverage_reference='Explicit synthetic entity coverage')
