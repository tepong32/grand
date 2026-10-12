from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounting import test_budget_native_certifications as fixtures
from accounting import test_budget_actuals as external_fixtures
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from .actuals_selection import select_source
from .planning_context import build_context, displayed_context
from .services import transition_version
from .models import BudgetVersion, BudgetAuditEvent


class ActualsSelectionTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.NativeCertificationTests.setUpTestData.__func__)
    employee = classmethod(fixtures.NativeCertificationTests.employee.__func__)
    make_call = fixtures.NativeCertificationTests.make_call
    make_version = fixtures.NativeCertificationTests.make_version
    add_line = fixtures.NativeCertificationTests.add_line
    add_ceiling = fixtures.NativeCertificationTests.add_ceiling
    grant = fixtures.NativeCertificationTests.grant
    attribute_grant = fixtures.NativeCertificationTests.attribute_grant
    journal = fixtures.NativeCertificationTests.journal
    capture = fixtures.NativeCertificationTests.capture
    rows = fixtures.NativeCertificationTests.rows
    propose = fixtures.NativeCertificationTests.propose
    review = fixtures.NativeCertificationTests.review
    native_grant = fixtures.NativeCertificationTests.native_grant
    native_propose = fixtures.NativeCertificationTests.native_propose
    decide = fixtures.NativeCertificationTests.decide
    document = external_fixtures.BudgetActualAdoptionTests.document
    arguments = external_fixtures.BudgetActualAdoptionTests.arguments
    adopt = external_fixtures.BudgetActualAdoptionTests.adopt

    def setUp(self):
        fixtures.NativeCertificationTests.setUp(self)
        self.native = self.decide(self.native_propose())

    def choose(self, **changes):
        args = dict(version=self.version, actor=self.preparer, fund_id=self.fund.pk, center_id=self.center.pk,
            prefix='half', kind='native', source_id=self.native.public_id,
            expected_state_version=self.version.state_version, reason='Reviewed actual source for this office')
        args.update(changes)
        self.version = select_source(**args)
        return self.version

    def test_native_external_overlap_is_explicit_replacement_and_audited_clear(self):
        adopted = self.adopt('140')
        self.assertEqual(build_context(self.version, self.preparer)['rows'][0]['half_certified']['amount'], '140.00')
        self.choose()
        native = build_context(self.version, self.preparer)
        self.assertEqual(native['schema'], 7)
        self.assertEqual(native['rows'][0]['half_certified']['amount'], '100.00')
        self.assertEqual(native['rows'][0]['half_certified']['source_kind'], 'native')
        self.choose(kind='external', source_id=adopted.public_id)
        self.assertEqual(build_context(self.version, self.preparer)['rows'][0]['half_certified']['amount'], '140.00')
        self.choose(kind='clear', source_id='')
        self.assertFalse(self.version.actuals_source_selection)
        self.assertEqual(build_context(self.version, self.preparer)['schema'], 2)
        self.assertEqual(BudgetAuditEvent.objects.filter(action='actuals_source_selected').count(), 2)
        self.assertTrue(BudgetAuditEvent.objects.filter(action='actuals_source_cleared').exists())

    def test_submission_freezes_selected_native_evidence_and_csv(self):
        self.choose()
        self.version = transition_version(self.version, 'submit', self.preparer)
        frozen = deepcopy(self.version.planning_context_snapshot)
        self.client.force_login(self.preparer)
        url = reverse('budget:planning_context_export', args=[self.version.public_id])
        before = self.client.get(url)
        self.assertEqual(before.status_code, 200)
        self.assertContains(before, 'Prior certified actual')
        self.journal('AFTER-BUDGET-SUBMISSION', date(2026, 6, 30), Decimal('8'))
        self.assertEqual(displayed_context(self.version, self.preparer), frozen)
        self.assertEqual(self.client.get(url).content, before.content)
        with self.assertRaises(ValidationError):
            self.choose(kind='clear', source_id='')
        self.version = transition_version(self.version, 'approve', self.reviewer, 'Reviewed retained actual source')
        self.assertEqual(displayed_context(self.version, self.reviewer), frozen)

    def test_new_post_blocks_new_submission_without_erasing_selection(self):
        self.choose()
        retained = deepcopy(self.version.actuals_source_selection)
        self.journal('BEFORE-BUDGET-SUBMISSION', date(2026, 6, 30), Decimal('3'))
        with self.assertRaises(ValidationError):
            transition_version(self.version, 'submit', self.preparer)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, BudgetVersion.DRAFT)
        self.assertEqual(self.version.actuals_source_selection, retained)
        self.choose(kind='clear', source_id='')
        self.assertIsNone(build_context(self.version, self.preparer)['rows'][0]['half_certified'])

    def test_superseded_certification_requires_new_choice_and_guards_replay_uat(self):
        self.choose()
        successor = self.decide(self.native_propose(expected_latest=1))
        with self.assertRaises(ValidationError):
            build_context(self.version, self.preparer)
        with self.assertRaises(ValidationError):
            self.choose(source_id=successor.public_id, expected_state_version=0)
        self.choose(source_id=successor.public_id)
        self.assertEqual(build_context(self.version, self.preparer)['rows'][0]['half_certified']['certificate'], str(successor.public_id))
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            self.choose(kind='clear', source_id='')

    def test_wrong_scope_and_missing_period_do_not_become_zero(self):
        with self.assertRaises(ValidationError):
            self.choose(prefix='prior')
        with self.assertRaises(ValidationError):
            self.choose(center_id=self.center.pk + 10000)
        with self.assertRaises(PermissionDenied):
            self.choose(actor=self.maker)
        self.choose()
        context = build_context(self.version, self.preparer)
        self.assertIsNone(context['rows'][0]['prior_certified'])
        self.assertEqual(context['rows'][0]['half_certified']['amount'], '100.00')
