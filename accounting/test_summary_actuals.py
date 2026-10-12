from copy import deepcopy
from datetime import date
import io

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from . import test_budget_actuals as fixtures
from . import summary_actuals as services
from .models import BudgetSummaryActual as Actual, BudgetSummaryScope as Scope, JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class SummaryActualTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = fixtures.BudgetActualAdoptionTests.__dict__['setUpTestData']
    employee = fixtures.BudgetActualAdoptionTests.__dict__['employee']
    make_call = fixtures.BudgetActualAdoptionTests.make_call
    make_version = fixtures.BudgetActualAdoptionTests.make_version
    add_line = fixtures.BudgetActualAdoptionTests.add_line
    add_ceiling = fixtures.BudgetActualAdoptionTests.add_ceiling
    grant = fixtures.BudgetActualAdoptionTests.grant

    def setUp(self):
        fixtures.BudgetActualAdoptionTests.setUp(self)
        from departments.models import Department
        self.operating_office = Department.objects.create(name='Synthetic Treasury Office', slug='summary-treasury')
        from .models import LedgerAccount
        self.receipt_account = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='SYN-SERVICE', title='Synthetic service receipts',
            account_type='revenue', normal_balance='credit')
        self.grant_summary(self.maker, 'view', 'prepare', 'export', 'review')
        self.grant_summary(self.checker, 'view', 'review', 'export')

    def grant_summary(self, actor, *actions):
        actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=[f'{action}_budget_summary_actuals' for action in actions]))

    def document(self):
        from reportlab.pdfgen import canvas
        stream = io.BytesIO(); page = canvas.Canvas(stream)
        for number, line in enumerate(('SYNTHETIC TEST ONLY - Joint historical actuals and trial balance',
            'General Fund / January-June 2026 / receipts 200 / expenditures 140',
            'Original Treasurer: Synthetic Treasurer / July 1, 2026 / designation T',
            'Original Accountant: Synthetic Accountant / July 2, 2026 / designation A',
            'R1: Service charges 200; E1: MOOE 140; synthetic reconciliation only')):
            page.drawString(30, 790-number*25, line)
        page.save()
        return SimpleUploadedFile('synthetic-joint-evidence.pdf', stream.getvalue(), content_type='application/pdf')

    def arguments(self, **changes):
        values = dict(actor=self.maker, fund_id=self.fund.pk, budget_department_id=self.budget_office.pk,
            treasury_department_id=self.operating_office.pk, entity_key='general', entity_label='Synthetic General Fund',
            period_start=date(2026, 1, 1), period_end=date(2026, 6, 30), evidence=self.document(), trial_balance=self.document(),
            rows=[{'kind': 'receipt', 'category': 'service', 'account_id': self.receipt_account.pk, 'amount': '200', 'source_row': 'p1 R1'},
                {'kind': 'expenditure', 'category': 'mooe', 'account_id': self.account.pk, 'amount': '140', 'source_row': 'p1 E1'}],
            expected_latest=0, receipt_total='200', expenditure_total='140', reference='SYN-JOINT-1', issuer='Synthetic LGU',
            scope_authority='Synthetic explicit fund and partner designation', coverage='All covered source leaf rows; no omitted activity',
            trial_balance_reference='Synthetic TB and reconciliation p1', reconciliation_basis='Retained synthetic source reconciliation',
            accountant_name='Synthetic Accountant', accountant_authority='Designation A', accountant_certified_on=date(2026, 7, 2),
            treasurer_name='Synthetic Treasurer', treasurer_authority='Designation T', treasurer_certified_on=date(2026, 7, 1),
            reason='Retain historical joint evidence')
        values.update(changes)
        return values

    def adopt(self, record=None):
        return services.review(record or services.propose(**self.arguments()), self.checker, approve=True,
            note='Verified original certifications and reconciliation', authority='Independent adoption designation', verified_documents=True)

    def test_adoption_retains_original_dates_and_does_not_post(self):
        before = JournalEntry.objects.count()
        record = self.adopt()
        self.assertEqual(record.payload['accountant_certified_on'], '2026-07-02')
        self.assertEqual(record.payload['treasurer_certified_on'], '2026-07-01')
        self.assertEqual(record.scope.current_version_id, record.pk)
        self.assertEqual(services.verify(record)['totals'], {'receipt': '200.00', 'expenditure': '140.00'})
        self.assertEqual(JournalEntry.objects.count(), before)
        self.assertEqual(services.visible(self.preparer).get().pk, record.pk)
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(reverse('accounting:summary_detail', args=[record.public_id])), 'Synthetic Treasurer')
        self.assertEqual(self.client.get(reverse('accounting:summary_export', args=[record.public_id, 'evidence'])).status_code, 403)

    def test_independent_review_confirmation_uat_and_latest(self):
        first = services.propose(**self.arguments())
        with self.assertRaisesMessage(ValidationError, 'independent'):
            services.review(first, self.maker, approve=True, note='x', authority='x', verified_documents=True)
        with self.assertRaisesMessage(ValidationError, 'Verify both'):
            services.review(first, self.checker, approve=True, note='x', authority='x')
        newer = services.propose(**self.arguments(expected_latest=1))
        with self.assertRaisesMessage(ValidationError, 'newer'):
            self.adopt(first)
        self.adopt(newer)
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            services.propose(**self.arguments(expected_latest=2))

    def test_document_and_totals_missing_roles_duplicate_rows_and_period(self):
        cases = [{'treasurer_name': ''}, {'treasurer_name': 'Synthetic Accountant'}, {'receipt_total': '201'},
            {'period_end': date(2026, 5, 31)}, {'trial_balance': None}, {'accountant_certified_on': date(2026, 6, 1)}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                services.propose(**self.arguments(**change))
        args = self.arguments(); args['rows'][1]['source_row'] = 'p1 R1'
        with self.assertRaisesMessage(ValidationError, 'same source row'):
            services.propose(**args)
        self.assertEqual(Scope.objects.count(), 0)

    def test_zero_missing_and_explicit_owner(self):
        args = self.arguments(receipt_total='0')
        args['rows'][0].update(account_id=None, amount='0')
        record = services.propose(**args)
        self.assertIsNone(record.payload['rows'][0]['account_id'])
        with self.assertRaises(ValidationError):
            services.propose(**self.arguments(budget_department_id=self.operating_office.pk, expected_latest=1))
        with self.assertRaises(ValidationError):
            services.propose(**self.arguments(entity_key='made-up', expected_latest=1))
        self.client.force_login(self.checker)
        self.assertContains(self.client.get(reverse('accounting:summary_detail', args=[record.public_id])), 'Explicit certified zero')

    def test_immutable_records_files_old_exports_after_successor_and_setup_rename(self):
        record = self.adopt()
        self.client.force_login(self.checker)
        url = reverse('accounting:summary_export', args=[record.public_id, 'evidence'])
        content = self.client.get(url).content
        self.adopt(services.propose(**self.arguments(expected_latest=1)))
        self.fund.code = 'RENAMED'; self.fund.save(update_fields=['code'])
        record.refresh_from_db()
        self.assertEqual(self.client.get(url).content, content)
        self.assertEqual(services.verify(record)['scope']['fund_code'], 'GF')
        for obj in (record, record.scope):
            with self.assertRaises(ValidationError): obj.delete()
        record.review_note = 'overwrite'
        with self.assertRaises(ValidationError): record.save()
        record.refresh_from_db(); record.payload = deepcopy(record.payload); record.payload['reference'] = 'overwrite'
        with self.assertRaises(ValidationError): record.save()
        Actual.objects.filter(pk=record.pk).update(trial_balance=b'changed')
        self.assertEqual(self.client.get(url).status_code, 409)

    def test_setup_change_blocks_new_adoption_and_scope_redirect(self):
        record = services.propose(**self.arguments())
        self.account.title = 'Changed'; self.account.save(update_fields=['title'])
        with self.assertRaisesMessage(ValidationError, 'classifications changed'): self.adopt(record)
        with self.assertRaisesMessage(ValidationError, 'original offices'):
            services.propose(**self.arguments(expected_latest=1, treasury_department_id=self.budget_office.pk))

    def test_http_create_review_and_successor(self):
        args = self.arguments()
        data = {k: v for k, v in args.items() if k not in ('actor', 'rows', 'fund_id', 'budget_department_id', 'treasury_department_id')}
        data.update(fund=self.fund.pk, budget_department=self.budget_office.pk, treasury_department=self.operating_office.pk,
            **{'form-TOTAL_FORMS': '2', 'form-INITIAL_FORMS': '0'})
        for i, row in enumerate(args['rows']):
            for key, value in row.items(): data[f'form-{i}-' + ('account' if key == 'account_id' else key)] = value
        self.client.force_login(self.maker)
        response = self.client.post(reverse('accounting:summary_create'), data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        record = Actual.objects.get()
        self.client.force_login(self.checker)
        response = self.client.post(reverse('accounting:summary_decide', args=[record.public_id]),
            {'decision': 'approve', 'note': 'Checked original evidence', 'authority': 'Synthetic reviewer', 'verified_documents': 'yes'})
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db(); self.assertEqual(record.status, Actual.APPROVED)
        self.client.force_login(self.maker)
        response = self.client.get(reverse('accounting:summary_successor', args=[record.public_id]))
        self.assertEqual(response.context['form']['expected_latest'].value(), 1)
        self.assertContains(response, 'Leave blank to retain')

    def test_register_pagination_preserves_complete_history(self):
        for number in range(51):
            services.propose(**self.arguments(expected_latest=number, reference=f'SYN-{number}'))
        self.client.force_login(self.maker)
        response = self.client.get(reverse('accounting:summary_register'), {'q': 'SYN-', 'page': 2})
        self.assertEqual(response.context['page'].paginator.count, 51)
        self.assertContains(response, 'SYN-0')

    def test_treasury_and_outsider_visibility_and_uat_export(self):
        treasury = self.employee(self.operating_office, 'summary.treasury')
        self.grant_summary(treasury, 'view', 'export', 'review')
        self.grant_summary(self.outsider, 'view', 'export', 'review')
        record = services.propose(**self.arguments())
        self.assertFalse(services.visible(treasury).exists())
        self.adopt(record)
        self.assertEqual(services.visible(treasury).get().pk, record.pk)
        self.assertFalse(services.visible(self.outsider).exists())
        with self.assertRaises(PermissionDenied):
            services.review(record, treasury, approve=False, note='Cannot decide another ledger', authority='Treasury')
        treasury.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(treasury)
        response = self.client.get(reverse('accounting:summary_export', args=[record.public_id, 'trial_balance']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content, bytes(record.trial_balance))
        with self.assertRaises(PermissionDenied):
            services.review(record, treasury, approve=False, note='UAT cannot mutate', authority='Treasury')
