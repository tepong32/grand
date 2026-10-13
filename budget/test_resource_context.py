from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from accounting.models import FundingSource
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_planning_context as fixtures
from .models import BudgetResourceEstimate, BudgetVersion, BudgetAuditEvent
from .resource_context import capture, save_estimate
from .planning_context import build_context
from .services import transition_version, consolidate_versions


class ResourceContextTests(fixtures.PlanningContextTests):
    def setUp(self):
        super().setUp()
        self.source = FundingSource.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, fiscal_year=self.fiscal_year, fund=self.fund,
            code='SOURCE-TEST', name='Synthetic financing source', kind='local',
            authority_reference='Synthetic source authority', effective_from=date(2027, 1, 1))

    def resource(self, **changes):
        self.version.refresh_from_db()
        args = dict(version=self.version, actor=self.preparer, funding_source=self.source,
            description='Synthetic proposed financing', amount=Decimal('500'), basis='Synthetic projected collection worksheet',
            expected_state_version=self.version.state_version, reason='Record proposed financing basis')
        args.update(changes)
        return save_estimate(**args)

    def approve(self):
        self.version = transition_version(self.version, 'submit', self.preparer)
        self.version = transition_version(self.version, 'approve', self.reviewer, 'Independent proposal/resource review')

    def test_submission_and_export_retain_resources_after_setup_changes(self):
        item = self.resource()
        self.approve()
        frozen = deepcopy(self.version.planning_context_snapshot['resources'])
        self.assertEqual(frozen['rows'][0]['amount'], '500.00')
        self.assertFalse(frozen['cash_available'])
        self.client.force_login(self.preparer)
        url = reverse('budget:resource_export', args=[self.version.public_id])
        before = self.client.get(url)
        self.source.code = 'LATER-SOURCE'; self.source.save(update_fields=('code',))
        self.assertEqual(self.client.get(url).content, before.content)
        detail = self.client.get(reverse('budget:version_detail', args=[self.version.public_id]))
        self.assertContains(detail, 'SOURCE-TEST')
        self.assertNotContains(detail, 'LATER-SOURCE')
        item.amount = Decimal('900')
        with self.assertRaisesMessage(ValidationError, 'editable only'):
            item.save()
        with self.assertRaises(ValidationError):
            item.delete()

    def test_audited_revision_zero_missing_fund_and_replay(self):
        self.source.fund = None; self.source.save(update_fields=('fund',))
        item = self.resource(amount=Decimal('0'))
        snapshot = capture(self.version)
        self.assertIsNone(snapshot['rows'][0]['funding_source']['fund_id'])
        self.assertEqual(snapshot['rows'][0]['amount'], '0.00')
        state = self.version.state_version
        item = self.resource(item_id=item.pk, amount=Decimal('20'), reason='Revise collectible projection')
        self.assertEqual(BudgetAuditEvent.objects.get(action='resource_estimate_changed').snapshot['before']['amount'], '0.00')
        with self.assertRaisesMessage(ValidationError, 'proposal changed'):
            self.resource(item_id=item.pk, expected_state_version=state)
        self.assertNotIn('total', capture(self.version))

    def test_source_change_or_row_tamper_before_approval_is_rejected(self):
        item = self.resource()
        self.version = transition_version(self.version, 'submit', self.preparer)
        BudgetResourceEstimate.objects.filter(pk=item.pk).update(amount='600')
        with self.assertRaisesMessage(ValidationError, 'changed after submission'):
            transition_version(self.version, 'approve', self.reviewer, 'Cannot approve changed resource')

    def test_owner_year_uat_and_reparent_controls(self):
        with self.assertRaises(PermissionDenied):
            self.resource(actor=self.maker)
        item = self.resource()
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            self.resource()
        other = self.make_version(self.call, 2)
        item.version = other
        with self.assertRaisesMessage(ValidationError, 'cannot be moved'):
            item.save()
        self.source.department_id = self.budget_office.pk
        self.source.save(update_fields=('department_id',))
        with self.assertRaisesMessage(ValidationError, 'Finance ledger'):
            capture(self.version)

    def test_consolidation_retains_exact_description_and_resource_origins(self):
        self.resource(description='X' * 220)
        self.approve()
        target = consolidate_versions(sources=[self.version], user=self.reviewer,
            title='Combined resource evidence', change_explanation='Retain exact proposed financing')
        snapshot = capture(target)
        self.assertEqual(snapshot['rows'][0]['description'], 'X' * 220)
        self.assertEqual(snapshot['origins'][0]['source_proposal'], str(self.version.public_id))
        self.assertEqual(snapshot['origins'][0]['target_resource_id'], snapshot['rows'][0]['id'])
        self.assertEqual(snapshot['origins'][0]['source_resource']['amount'], '500.00')
        self.assertEqual(build_context(target, self.preparer)['resources'], snapshot)

    def test_legacy_resources_are_not_backfilled_by_consolidation_or_export(self):
        self.resource()
        self.version.status = BudgetVersion.APPROVED
        self.version.save(update_fields=('status',))
        with self.assertRaisesMessage(ValidationError, 'no submitted snapshot'):
            consolidate_versions(sources=[self.version], user=self.reviewer,
                title='Cannot infer old approval', change_explanation='Reject missing resource evidence')
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(reverse('budget:resource_export', args=[self.version.public_id])).status_code, 409)

    def test_http_create_and_revision_capture_model_owner_and_hidden_state(self):
        self.client.force_login(self.preparer)
        create = reverse('budget:resource_create', args=[self.version.public_id])
        form = self.client.get(create).context['form']
        data = dict(funding_source=self.source.pk, description='HTTP proposed resource', amount='75.00',
            basis='Synthetic HTTP worksheet', reason='Initial proposal source',
            expected_state_version=form['expected_state_version'].value())
        response = self.client.post(create, data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        item = self.version.resource_estimates.get()
        edit = reverse('budget:resource_edit', args=[self.version.public_id, item.pk])
        data.update(amount='80.00', reason='Updated projection',
            expected_state_version=self.client.get(edit).context['form']['expected_state_version'].value())
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        item.refresh_from_db(); self.assertEqual(item.amount, Decimal('80'))
        replay = self.client.post(edit, data)
        self.assertContains(replay, 'proposal changed')
