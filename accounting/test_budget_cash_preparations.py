from copy import deepcopy
from datetime import date
from decimal import Decimal
import io
from unittest import skipUnless
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TransactionTestCase
from departments.models import Department
from budget.models import BudgetCall
from . import budget_cash, budget_cash_preparations as service
from .models import NativeBudgetCashPreparation as Record, AccountingAuditEvent, JournalEntry
from .test_budget_native_cash import NativeCashTests
from .test_budget_native_cash_concurrency import NativeCashConcurrencyTests
from .test_budget_attribution_concurrency import BudgetAttributionConcurrencyTests


class NativeCashPreparationTests(NativeCashTests):
    def setUp(self):
        super().setUp()
        self.configure_native()

    def configure_native(self):
        self.budget_office = Department.objects.create(name='Synthetic Budget Office', slug='native-cash-budget')
        self.treasury_office = Department.objects.create(name='Synthetic Treasury Office', slug='native-cash-treasury')
        BudgetCall.objects.create(department_id=self.budget_office.pk, department_label=self.budget_office.name,
            fiscal_year=self.batch.fiscal_year, title='Synthetic cash scope call', authority_reference='Synthetic scope',
            instructions='Synthetic fixture', proposal_opens_on=date(2026, 1, 1), proposal_due_on=date(2026, 12, 31),
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        for actor, codes in ((self.maker, ('prepare_native_budget_cash', 'view_native_budget_cash', 'prepare_budget_cash_evidence')),
            (self.poster, ('view_native_budget_cash', 'review_budget_cash_evidence'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting', codename__in=codes))

    def preparation_args(self, **changes):
        result = dict(actor=self.maker, fund_id=self.fund.pk, opening_batch_id=self.batch.pk,
            budget_department_id=self.budget_office.pk, treasury_department_id=self.treasury_office.pk,
            entity_key='general', coverage_authority='Explicit synthetic fund/entity coverage',
            balance_date=date(2026, 9, 4), boundary='end_of_day', expected_latest=0)
        result.update(changes); return result

    def historical(self, **changes):
        from reportlab.pdfgen import canvas
        def document():
            stream = io.BytesIO(); pdf = canvas.Canvas(stream)
            pdf.drawString(40, 800, 'Synthetic gross 1000 / restriction 100 / net 900; not LGU acceptance')
            pdf.save(); return SimpleUploadedFile('synthetic-cash.pdf', stream.getvalue(), content_type='application/pdf')
        args = dict(actor=self.maker, fund_id=self.fund.pk, budget_department_id=self.budget_office.pk,
            treasury_department_id=self.treasury_office.pk, entity_key='general', entity_label='Synthetic General Fund',
            balance_date=date(2026, 9, 4), boundary='end_of_day', gross='1000', restricted='100', net='900',
            rows=[dict(key='R1', reference='Synthetic schedule row 1', purpose='Explicit restriction', coverage='One disjoint source', amount='100')],
            no_restrictions=False, declaration='', overlap_basis='Synthetic complete disjoint schedule',
            certificate=document(), reconciliation=document(), expected_latest=0,
            accountant_certified_on=date(2026, 9, 4), treasurer_certified_on=date(2026, 9, 4))
        for name in ('reference', 'scope_authority', 'gross_basis', 'coverage', 'reconciliation_basis',
            'accountant_authority', 'treasurer_authority', 'reason'):
            args[name] = 'Explicit synthetic ' + name
        args.update(accountant_name='Synthetic Accountant', treasurer_name='Synthetic Treasurer')
        args.update(changes)
        return budget_cash.propose(**args)

    def test_persistence_successors_staleness_and_immutable_history(self):
        count = JournalEntry.objects.count()
        first = service.prepare(**self.preparation_args())
        payload = deepcopy(service.verify(first))
        self.assertEqual(payload['gross'], '1000.00')
        self.assertIsNone(payload['restricted']); self.assertIsNone(payload['net'])
        self.assertEqual(payload['certification_status'], 'not_certified')
        self.assertTrue(service.is_current(first, self.maker))
        self.assertEqual(JournalEntry.objects.count(), count)
        with self.assertRaisesMessage(ValidationError, 'newer'):
            service.prepare(**self.preparation_args())
        self.post(self.entry('PREP-LATER-PAYMENT', Decimal('400'), source=self.source, day=4))
        self.assertFalse(service.is_current(first, self.maker))
        self.assertEqual(service.verify(first), payload)
        second = service.prepare(**self.preparation_args(expected_latest=1))
        self.assertEqual(service.verify(second)['gross'], '600.00')
        self.assertEqual(second.version, 2)
        with self.assertRaises(ValidationError): first.delete()
        first.payload['gross'] = '5.00'
        with self.assertRaises(ValidationError): first.save()
        first.refresh_from_db(); self.assertEqual(service.verify(first), payload)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_cash_prepared').count(), 2)

    def test_exact_restriction_reconciliation_retains_originals_and_decision(self):
        historical = self.historical()
        with self.assertRaisesMessage(ValidationError, 'independently adopted'):
            service.prepare(**self.preparation_args(restriction_source_id=historical.pk))
        historical = budget_cash.review(historical, self.poster, adopt=True, note='Originals checked independently',
            authority='Synthetic independent source designation', verified_documents=True)
        first = service.prepare(**self.preparation_args(restriction_source_id=historical.pk))
        payload = deepcopy(service.verify(first))
        self.assertEqual((payload['gross'], payload['restricted'], payload['net']), ('1000.00', '100.00', '900.00'))
        self.assertEqual(payload['restriction_source']['decision'], budget_cash.decision(historical))
        self.assertEqual(bytes(first.certificate), bytes(historical.certificate))
        self.assertEqual(bytes(first.reconciliation), bytes(historical.reconciliation))
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            self.assertEqual(service.verify(first), payload)
        self.assertTrue(service.is_current(first, self.maker))
        self.historical(expected_latest=1)
        self.assertFalse(service.is_current(first, self.maker))
        self.assertEqual(service.verify(first), payload)
        self.post(self.entry('RESTRICTION-MISMATCH', Decimal('400'), source=self.source, day=4))
        with self.assertRaisesMessage(ValidationError, 'reconcile exactly'):
            service.prepare(**self.preparation_args(expected_latest=1, restriction_source_id=historical.pk))
        self.assertEqual(Record.objects.count(), 1)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_cash_prepared').count(), 1)
        first.payload['net'] = '1000.00'; first.payload_checksum = service.checksum(first.payload)
        with self.assertRaisesMessage(ValidationError, 'reconcile exactly'): service.verify(first)

    def test_permission_uat_scope_and_invalid_inputs(self):
        with self.assertRaises(PermissionDenied): service.prepare(**self.preparation_args(actor=self.poster))
        first = service.prepare(**self.preparation_args())
        with self.assertRaises(ValidationError): service.prepare(**self.preparation_args(expected_latest=1, entity_key='unknown'))
        with self.assertRaises(ValidationError): service.prepare(**self.preparation_args(expected_latest=True))
        with self.assertRaises(ValidationError): service.prepare(**self.preparation_args(balance_date='2026-09-04'))
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied): service.prepare(**self.preparation_args(expected_latest=1))
        self.assertTrue(service.visible(self.maker).filter(pk=first.pk).exists())
        self.poster.employeeprofile.assigned_department = self.treasury_office
        self.poster.employeeprofile.save(update_fields=('assigned_department',))
        self.assertTrue(service.visible(self.poster).filter(pk=first.pk).exists())
        with self.assertRaises(PermissionDenied): service.is_current(first, self.poster)
        self.poster.employeeprofile.assigned_department = self.budget_office
        self.poster.employeeprofile.save(update_fields=('assigned_department',))
        self.assertTrue(service.visible(self.poster).filter(pk=first.pk).exists())


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native preparation Fund lock')
class NativeCashPreparationConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    entry = NativeCashConcurrencyTests.entry
    post = NativeCashConcurrencyTests.post
    configure_cash = NativeCashConcurrencyTests.configure_cash
    configure_native = NativeCashPreparationTests.configure_native
    preparation_args = NativeCashPreparationTests.preparation_args
    race = BudgetAttributionConcurrencyTests.race

    def setUp(self):
        NativeCashConcurrencyTests.setUp(self)
        self.configure_native()

    def test_competing_preparations_keep_one_retained_version(self):
        results = self.race(lambda _: 'prepared' if service.prepare(**self.preparation_args()) else 'missing')
        self.assertEqual(results.count('prepared'), 1, results)
        self.assertTrue(any('newer' in result for result in results), results)
        self.assertEqual(Record.objects.count(), 1)
        record = Record.objects.get()
        self.assertEqual(service.verify(record)['gross'], '1000.00')
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_cash_prepared').count(), 1)
