from copy import deepcopy
from datetime import date
from unittest.mock import patch
import time

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_preparation as editor
from . import test_budget_reviewed_components as fixtures
from . import test_budget_joint_attributions as joint
from .models import BudgetExpenditureAttribution as Attribution, ResponsibilityCenter


class PreparationContextTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixtures.ReviewedComponentTests.setUp
    entry = fixtures.ReviewedComponentTests.entry
    post = fixtures.ReviewedComponentTests.post
    capture = fixtures.ReviewedComponentTests.capture
    rows = fixtures.ReviewedComponentTests.rows
    propose = fixtures.ReviewedComponentTests.propose
    approve = fixtures.ReviewedComponentTests.approve

    def prepare(self, ids=None):
        return editor.prepare(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 5),
            entry_ids=ids if ids is not None else [self.original.pk])

    def submit(self, prepared, proposals=None, actor=None):
        return editor.submit(actor=actor or self.maker, token=prepared['token'],
            proposals=proposals if proposals is not None else [dict(entry_id=self.original.pk, allocations=self.rows())],
            reason='Explicit editor source partition', evidence_reference='SYN-EDITOR')

    def test_retained_editor_versions_reject_replay_and_keep_original_split(self):
        prepared = self.prepare()
        self.assertEqual(editor.read(actor=self.maker, token=prepared['token']), prepared['context'])
        records = self.submit(prepared)
        self.assertEqual(records[0].status, 'submitted')
        self.assertEqual(sorted(row['amount'] for row in records[0].allocations), ['1000.00', '400.00', '600.00'])
        with self.assertRaisesMessage(ValidationError, 'newer proposal'):
            self.submit(prepared)
        self.assertEqual(Attribution.objects.count(), 1)

    def test_tampering_expiry_actor_and_revoked_permission(self):
        prepared = self.prepare()
        tampered = dict(prepared, token='x' + prepared['token'])
        with self.assertRaises(ValidationError):
            self.submit(tampered)
        with patch('django.core.signing.time.time', return_value=time.time() + editor.MAX_AGE + 10):
            with self.assertRaisesMessage(ValidationError, 'expired'):
                self.submit(prepared)
        permission = Permission.objects.get(content_type__app_label='accounting', codename='prepare_budget_attributions')
        self.poster.user_permissions.add(permission)
        with self.assertRaises(PermissionDenied):
            self.submit(prepared, actor=self.poster)
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            self.submit(prepared)
        self.assertFalse(Attribution.objects.exists())

    def test_selected_group_and_source_versions_cannot_be_overridden(self):
        prepared = self.prepare()
        for proposals in ([], [dict(entry_id=self.original.pk, expected_latest=7, allocations=self.rows())],
                          [dict(entry_id=self.original.pk + 900, allocations=self.rows())]):
            with self.assertRaises(ValidationError):
                self.submit(prepared, proposals)
        with self.assertRaises(ValidationError):
            self.prepare([self.original.pk, self.original.pk])
        self.assertFalse(Attribution.objects.exists())

    def test_source_and_office_changes_reject_stale_editor_without_writes(self):
        prepared = self.prepare()
        center = ResponsibilityCenter.objects.create(**self.owner, code='EDITOR', name='Visible office',
                                                    office_id=self.department.pk)
        with self.assertRaisesMessage(ValidationError, 'Office choices changed'):
            self.submit(prepared)
        prepared = self.prepare()
        center.name = 'Changed label'; center.save()
        with self.assertRaisesMessage(ValidationError, 'Office choices changed'):
            self.submit(prepared)
        prepared = self.prepare()
        self.approve(self.propose())
        with self.assertRaisesMessage(ValidationError, 'Source coverage'):
            self.submit(prepared)
        self.assertEqual(Attribution.objects.count(), 1)


class PreparationDependencyTests(TestCase):
    databases = {'default', 'finance'}
    setUp = joint.JointAttributionTests.setUp
    entry = joint.JointAttributionTests.entry
    post = joint.JointAttributionTests.post
    rows = joint.JointAttributionTests.rows
    approve = joint.JointAttributionTests.approve
    reference = joint.JointAttributionTests.reference
    payment_rows = joint.JointAttributionTests.payment_rows
    capture = joint.JointAttributionTests.capture
    propose = joint.JointAttributionTests.propose
    reverse_and_review = joint.JointAttributionTests.reverse_and_review
    stale_pair = joint.JointAttributionTests.stale_pair

    def prepare(self, ids):
        return editor.prepare(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 10), entry_ids=ids)

    def test_actual_component_choices_and_explicit_joint_repair(self):
        returned, retained = self.stale_pair()
        prepared = self.prepare([returned.pk, self.payment.pk])
        choices = prepared['context']['components'][str(self.payment.lines.get(sequence=1).pk)]
        self.assertEqual({row['basis'] for row in choices}, {'loan_principal', 'recognized_expenditure'})
        self.assertEqual({row['attribution_id'] for row in choices}, {self.bound.attribution_id})
        self.assertEqual({row['application_share'] for row in choices}, {'600.00'})
        records = editor.submit(actor=self.maker, token=prepared['token'],
            proposals=[dict(entry_id=returned.pk, inherit_from=self.payment.pk),
                       dict(entry_id=self.payment.pk, allocations=self.payment_rows())],
            reason='Repair explicit payment and return together', evidence_reference='SYN-EDITOR-JOINT')
        self.assertTrue(records[1].dependencies)
        self.approve(records)

    def test_missing_source_basis_is_visible_and_forged_component_is_rejected(self):
        prepared = self.prepare([self.payment.pk])
        rows = deepcopy(self.payment_rows())
        rows[0]['claim_component']['component_key'] = 'forged'
        before = Attribution.objects.count()
        with self.assertRaises(ValidationError):
            editor.submit(actor=self.maker, token=prepared['token'],
                proposals=[dict(entry_id=self.payment.pk, allocations=rows)],
                reason='Invalid editor selection', evidence_reference='SYN-BAD')
        self.assertEqual(Attribution.objects.count(), before)
        source_rows = self.rows()
        for row in source_rows:
            row.pop('claim_component_basis', None)
        self.approve(self.propose(source_rows, version=1))
        prepared = self.prepare([self.payment.pk])
        self.assertFalse(prepared['context']['components'])
        self.assertTrue(prepared['context']['warnings'])
