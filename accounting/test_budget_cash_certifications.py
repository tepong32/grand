from copy import deepcopy
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from . import budget_cash, budget_cash_preparations as preparations
from . import budget_cash_certifications as service
from .cash_classifications import checksum
from .models import NativeBudgetCashDecision as Decision, JournalEntry
from . import test_budget_cash_preparations as fixtures
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class NativeCashCertificationTests(fixtures.NativeCashPreparationTests):
    def setUp(self):
        super().setUp()
        self.configure_certifiers()

    def grant_certifier(self, actor, *roles):
        actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=['view_native_budget_cash', 'view_budget_cash_evidence',
                *[f'certify_{role}_native_budget_cash' for role in roles]]))

    def configure_certifiers(self):
        self.treasurer = get_user_model().objects.create_user(username='native.cash.treasurer',
            email='native-cash-treasurer@example.test')
        self.treasurer.employeeprofile.assigned_department = self.treasury_office
        self.treasurer.employeeprofile.save(update_fields=('assigned_department',))
        self.grant_certifier(self.poster, 'accountant')
        self.grant_certifier(self.treasurer, 'treasurer')

    def cash_preparation(self, **changes):
        historical = self.historical()
        budget_cash.review(historical, self.poster, adopt=True, verified_documents=True,
            authority='Synthetic historical adoption authority', note='Checked complete original cash restrictions')
        return preparations.prepare(**self.preparation_args(restriction_source_id=historical.pk, **changes))

    def decision(self, record, role='accountant', **changes):
        args = dict(preparation_id=record.pk, actor=self.poster if role == 'accountant' else self.treasurer,
            role=role, certify=True, authority='Synthetic designated ' + role,
            note='Independently verified complete source and restriction reconciliation')
        args.update(changes)
        return service.decide(**args)

    def test_joint_decisions_reproduce_sources_without_rewriting_preparation(self):
        record = self.cash_preparation()
        frozen = deepcopy(record.payload)
        journals = JournalEntry.objects.count()
        first = self.decision(record, 'treasurer')
        self.assertEqual(service.snapshot(record, self.poster)['payload']['status'], 'awaiting_joint_certification')
        self.assertFalse(service.is_current(record, self.poster))
        second = self.decision(record)
        result = service.snapshot(record, self.treasurer)
        self.assertEqual(result['payload']['status'], 'jointly_certified')
        self.assertEqual(result['payload']['original_preparation']['net'], '900.00')
        self.assertTrue(service.is_current(record, self.treasurer))
        with self.assertNumQueries(0, using='finance'), self.assertNumQueries(0, using='default'):
            service.verify_decision(record, first)
            service.verify_decision(record, second)
        record.refresh_from_db()
        self.assertEqual(record.payload, frozen)
        self.assertEqual(record.payload['certification_status'], 'not_certified')
        self.assertEqual(JournalEntry.objects.count(), journals)
        with self.assertRaises(ValidationError):
            self.decision(record)
        with self.assertRaises(ValidationError):
            second.delete()
        second.actor_label = 'Rewritten authority'
        with self.assertRaises(ValidationError):
            second.save()

    def test_unknown_restrictions_and_return_preserve_evidence(self):
        record = preparations.prepare(**self.preparation_args())
        with self.assertRaisesMessage(ValidationError, 'restrictions'):
            self.decision(record)
        returned = self.decision(record, 'treasurer', certify=False)
        self.assertIsNone(returned.payload['observation'])
        self.assertEqual(service.snapshot(record, self.poster)['payload']['status'], 'returned')
        with self.assertRaises(ValidationError):
            self.decision(record)
        self.assertEqual(Decision.objects.count(), 1)

    def test_office_role_independence_uat_and_source_visibility(self):
        record = self.cash_preparation()
        self.grant_certifier(self.maker, 'accountant')
        with self.assertRaises(ValidationError):
            self.decision(record, actor=self.maker)
        self.grant_certifier(self.poster, 'treasurer')
        with self.assertRaises(PermissionDenied):
            self.decision(record, 'treasurer', actor=self.poster)
        with self.assertRaises(PermissionDenied):
            self.decision(record, actor=self.treasurer)
        self.poster.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            self.decision(record)
        self.assertEqual(service.snapshot(record, self.poster)['payload']['status'], 'awaiting_joint_certification')
        self.poster.groups.clear()
        self.treasurer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',
            codename='view_budget_cash_evidence'))
        with self.assertRaises(PermissionDenied):
            self.decision(record, 'treasurer')
        self.assertEqual(Decision.objects.count(), 0)

    def test_source_and_successor_changes_reject_new_use_keep_old_decisions(self):
        record = self.cash_preparation()
        first = self.decision(record)
        frozen = deepcopy(first.payload)
        self.post(self.entry('JOINT-CASH-LATER-PAYMENT', Decimal('400'), source=self.source, day=4))
        with self.assertRaisesMessage(ValidationError, 'sources changed'):
            self.decision(record, 'treasurer')
        self.assertEqual(service.verify_decision(record, first), frozen)
        self.decision(record, 'treasurer', certify=False)
        self.assertEqual(service.snapshot(record, self.poster)['payload']['status'], 'returned')
        self.assertEqual(first.payload, frozen)

    def test_new_preparation_and_restriction_versions_block_older_certification(self):
        record = self.cash_preparation()
        self.decision(record)
        successor = preparations.prepare(**self.preparation_args(expected_latest=1,
            restriction_source_id=record.restriction_source_id))
        with self.assertRaisesMessage(ValidationError, 'newer preparation'):
            self.decision(record, 'treasurer')
        self.historical(expected_latest=1)
        with self.assertRaisesMessage(ValidationError, 'Restriction source changed'):
            self.decision(successor)
        self.assertEqual(Decision.objects.count(), 1)

    def test_decision_tampering_and_joint_actor_reuse_fail(self):
        record = self.cash_preparation()
        first = self.decision(record)
        damaged = deepcopy(first.payload)
        damaged['observation']['payload']['gross'] = '1001.00'
        first.payload = damaged; first.payload_checksum = checksum(damaged)
        with self.assertRaises(ValidationError):
            service.verify_decision(record, first)
        first.refresh_from_db()
        # A mistaken designation of the same user into both offices cannot
        # manufacture the second independent officer.
        self.grant_certifier(self.poster, 'treasurer')
        self.poster.employeeprofile.assigned_department = self.treasury_office
        self.poster.employeeprofile.save(update_fields=('assigned_department',))
        with self.assertRaises(ValidationError):
            self.decision(record, 'treasurer', actor=self.poster)
        first.refresh_from_db()
        service.verify_decision(record, first)
