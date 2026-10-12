import csv
import io
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from .test_budget_cash import BudgetCashTests
from . import budget_cash as service
from . import budget_cash_forms as forms
from .models import BudgetCashEvidence as Record


class BudgetCashFormTests(BudgetCashTests):
    def upload(self, count=1001, last_amount='1'):
        stream = io.StringIO(newline=''); writer = csv.writer(stream)
        writer.writerow(forms.COLUMNS)
        for i in range(count): writer.writerow((f'r{i}', f'p{i}', f'Purpose {i}', f'Unique scope {i}', last_amount if i == count-1 else '1'))
        return SimpleUploadedFile('restrictions.csv', stream.getvalue().encode('utf-8-sig'))

    def post_data(self, **changes):
        data = self.cash_args(gross='2000', restricted='1001', net='999')
        for key in ('actor', 'rows'): data.pop(key)
        for key in ('fund', 'budget_department', 'treasury_department'): data[key] = data.pop(key+'_id')
        data.update(row_input='csv', row_csv=self.upload()); data.update(changes)
        return data

    def test_large_submission_retains_full_successor_scope_documents_and_stale_guard(self):
        self.cash_args()  # authorize the initial GET before constructing POST data
        self.client.force_login(self.maker)
        create = reverse('accounting:budget_cash_create')
        self.assertContains(self.client.get(create), 'Original cash certificate')
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=1000): response = self.client.post(create, self.post_data())
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        first = Record.objects.get()
        self.assertEqual(len(first.payload['restrictions']), 1001)
        self.assertEqual(first.payload['restrictions'][-1]['reference'], 'p1000')
        service.review(first, self.checker, adopt=True, note='Verified originals', authority='Designation', verified_documents=True)
        url = reverse('accounting:budget_cash_successor', args=[first.public_id])
        response = self.client.get(url)
        self.assertEqual(response.context['form']['row_input'].value(), 'retain')
        self.assertEqual(len(response.context['formset'].forms), 1)
        data = self.post_data(row_input='retain', expected_latest=1, fund=self.fund.pk+999,
            entity_key='enterprise:tampered', balance_date='2020-01-01')
        for key in ('certificate', 'reconciliation', 'row_csv'): data.pop(key)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        second = Record.objects.get(version=2)
        self.assertEqual(second.payload['restrictions'], first.payload['restrictions'])
        self.assertEqual(bytes(second.certificate), bytes(first.certificate))
        self.assertEqual(bytes(second.reconciliation), bytes(first.reconciliation))
        self.assertEqual(second.entity_key, first.entity_key)
        self.assertEqual(second.balance_date, first.balance_date)
        self.assertEqual(second.fund_id, first.fund_id)
        data['expected_latest'] = 2
        self.assertContains(self.client.post(url, data), 'displayed predecessor')
        data['expected_latest'] = 1
        self.assertContains(self.client.post(url, data), 'newer cash submission')
        self.assertEqual(Record.objects.count(), 2)
        self.assertEqual(service.verify(first)['net'], '999.00')

    def test_csv_failure_atomicity_no_restriction_and_manual_submission(self):
        self.client.force_login(self.maker); url = reverse('accounting:budget_cash_create')
        data = self.post_data(row_csv=self.upload(last_amount='not-money'))
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(Record.objects.count(), 0)
        data = self.post_data(row_input='manual')
        self.assertContains(self.client.post(url, data), 'will not be silently ignored')
        self.assertEqual(Record.objects.count(), 0)
        data = self.post_data(row_input='manual', gross='0', restricted='0', net='0', no_restrictions=True,
            declaration='Synthetic signed zero and no restrictions', **{'form-TOTAL_FORMS': '0', 'form-INITIAL_FORMS': '0'})
        data.pop('row_csv')
        self.assertEqual(self.client.post(url, data).status_code, 302)
        first = Record.objects.get(); self.assertEqual(first.payload['restrictions'], [])
        self.assertEqual(service.verify(first)['net'], '0.00')
        data = self.post_data(row_input='manual', expected_latest=1, gross='100', restricted='25', net='75',
            **{'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '0', 'form-0-key': 'r1', 'form-0-reference': 'p1',
            'form-0-purpose': 'Continuing', 'form-0-coverage': 'Unique source', 'form-0-amount': '25'})
        data.pop('row_csv')
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(Record.objects.count(), 2)
        self.assertEqual(Record.objects.get(version=2).payload['restricted'], '25.00')
        self.client.force_login(self.checker)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_csv_bounds_and_malformed_structure(self):
        for raw in (b'wrong\n', b'key,reference,purpose,coverage,amount\n', b'\xff', b'\x00',
            b'key,reference,purpose,coverage,amount\nr,p,purpose,coverage\n'):
            with self.subTest(raw=raw), self.assertRaises(ValidationError): forms.parse_csv(io.BytesIO(raw))
        with patch.object(forms, 'MAX_ROWS', 1), self.assertRaises(ValidationError): forms.parse_csv(self.upload(2))
        with patch.object(forms, 'MAX_BYTES', 3), self.assertRaises(ValidationError): forms.parse_csv(self.upload(1))
        with self.assertRaises(ValidationError):
            service.restrictions(['bad'], no_restrictions=False, declaration='', overlap_basis='Explicit coverage')

    def test_configured_office_roles_and_uat_boundaries(self):
        from django.core.management import call_command
        from django.contrib.auth.models import Group
        from django.core.exceptions import PermissionDenied
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        call_command('configure_finance_roles', stdout=io.StringIO())
        maker = self.employee(self.accounting_office, 'cash.role.maker')
        checker = self.employee(self.accounting_office, 'cash.role.checker')
        treasury = self.employee(self.operating_office, 'cash.role.treasury')
        maker.groups.add(Group.objects.get(name='Accounting DV Preparer'))
        checker.groups.add(Group.objects.get(name='Accounting Reviewer'))
        treasury.groups.add(Group.objects.get(name='Treasury Collection Officer'))
        record = service.propose(**self.cash_args(actor=maker))
        self.assertFalse(service.visible(treasury).exists())
        with self.assertRaises(PermissionDenied):
            service.review(record, maker, adopt=True, note='x', authority='x', verified_documents=True)
        service.review(record, checker, adopt=True, note='Verified originals', authority='Designation', verified_documents=True)
        self.assertEqual(service.visible(treasury).get().pk, record.pk)
        self.client.force_login(treasury)
        self.assertEqual(self.client.get(reverse('accounting:budget_cash_export', args=[record.public_id, 'certificate'])).content, bytes(record.certificate))
        self.assertEqual(self.client.get(reverse('accounting:budget_cash_create')).status_code, 403)
        maker.groups.add(Group.objects.get(name=FINANCE_UAT_VIEWER_GROUP))
        with self.assertRaises(PermissionDenied): service.propose(**self.cash_args(actor=maker, expected_latest=1))
        checker.groups.add(Group.objects.get(name=FINANCE_UAT_VIEWER_GROUP))
        pending = service.propose(**self.cash_args(expected_latest=1))
        with self.assertRaises(PermissionDenied): service.review(pending, checker, adopt=False, note='x', authority='x')
        self.client.force_login(checker)
        self.assertEqual(self.client.get(reverse('accounting:budget_cash_export', args=[record.public_id, 'certificate'])).status_code, 200)
