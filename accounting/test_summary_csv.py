import csv
import io
import zipfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from . import test_summary_actuals as fixtures
from . import summary_csv, summary_actuals
from .models import BudgetSummaryActual as Actual, BudgetSummaryScope as Scope


class SummaryCSVTests(fixtures.SummaryActualTests):
    def upload(self, count=1001, *, last_account=None):
        stream = io.StringIO(newline=''); writer = csv.writer(stream)
        writer.writerow(summary_csv.COLUMNS)
        for number in range(count - 1):
            writer.writerow(('receipt', 'service', last_account if number == count - 2 and last_account else self.receipt_account.code,
                '1.00', f'p1 R{number+1}'))
        writer.writerow(('expenditure', 'mooe', self.account.code, '140.00', 'p2 E1'))
        return SimpleUploadedFile('rows.csv', stream.getvalue().encode('utf-8-sig'), content_type='text/csv')

    def post_data(self, count=1001):
        data = self.arguments(receipt_total=str(count-1))
        for name in ('actor', 'rows'): data.pop(name)
        for name in ('fund', 'budget_department', 'treasury_department'): data[name] = data.pop(name+'_id')
        data.update(row_input='csv', row_csv=self.upload(count))
        return data

    def test_large_http_import_review_and_successor_retain_all_rows(self):
        self.client.force_login(self.maker)
        data = self.post_data()
        # Keep the normal parser limit: CSV file content must not become form fields.
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=1000):
            response = self.client.post(reverse('accounting:summary_create'), data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        first = Actual.objects.get()
        self.assertEqual(len(first.payload['rows']), 1001)
        self.assertEqual(first.payload['rows'][-2]['source_row'], 'p1 R1000')
        self.assertEqual(first.payload['totals']['receipt'], '1000.00')
        self.adopt(first)
        successor_url = reverse('accounting:summary_successor', args=[first.public_id])
        form = self.client.get(successor_url)
        self.assertEqual(form.context['form']['row_input'].value(), 'retain')
        self.assertEqual(len(form.context['formset'].forms), 2)
        follow = self.post_data(); follow.pop('evidence'); follow.pop('trial_balance'); follow.pop('row_csv')
        follow.update(row_input='retain', expected_latest=1, reason='Retain full historical schedule')
        response = self.client.post(successor_url, follow)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        last = Actual.objects.get(version=2)
        self.assertEqual(last.payload['rows'], first.payload['rows'])
        self.assertEqual(bytes(last.evidence), bytes(first.evidence))
        self.adopt(last)
        self.client.force_login(self.checker)
        exported = self.client.get(reverse('accounting:summary_export', args=[last.public_id, 'snapshot']))
        import json
        self.assertEqual(len(json.loads(exported.content)['payload']['rows']), 1001)
        package_url = reverse('accounting:summary_export', args=[last.public_id, 'package'])
        package = self.client.get(package_url)
        self.assertEqual(package.status_code, 200)
        self.assertEqual(package.content, self.client.get(package_url).content)
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            self.assertEqual(set(archive.namelist()), {'certificate.pdf', 'trial-balance.pdf', 'evidence.json'})
            self.assertEqual(archive.read('certificate.pdf'), bytes(last.evidence))
            self.assertEqual(archive.read('trial-balance.pdf'), bytes(last.trial_balance))
            self.assertEqual(archive.read('evidence.json'), exported.content)
        detail_url = reverse('accounting:summary_detail', args=[last.public_id])
        tail = self.client.get(detail_url, {'rows_page': 11})
        self.assertEqual(tail.context['row_page'].paginator.count, 1001)
        self.assertEqual(tail.context['row_page'][0]['source_row'], 'p2 E1')
        found = self.client.get(detail_url, {'row_q': 'p1 R1000'})
        self.assertEqual(found.context['row_page'].paginator.count, 1)
        self.assertContains(found, '1000.00')
        self.assertContains(found, 'do not change the signed totals')

    def test_last_invalid_row_rejects_entire_import_and_mapping_changes_fail(self):
        self.client.force_login(self.maker)
        data = self.post_data(); data['row_csv'] = self.upload(last_account='NOT-IN-THIS-LEDGER')
        response = self.client.post(reverse('accounting:summary_create'), data)
        self.assertContains(response, 'CSV row 1001')
        self.assertEqual(Actual.objects.count(), 0); self.assertEqual(Scope.objects.count(), 0)
        parsed = summary_csv.parse(self.upload(3), self.accounting_office.pk)
        self.receipt_account.code = 'CHANGED'; self.receipt_account.save(update_fields=['code'])
        with self.assertRaisesMessage(ValidationError, 'CSV account changed'):
            summary_actuals.propose(**self.arguments(rows=parsed, receipt_total='2'))

    def test_csv_shape_encoding_limits_and_zero(self):
        invalid = [b'kind,kind\n', b'\xff\xfe\n', b'kind,category,account_code,amount,source_row\n',
            b'kind,category,account_code,amount,source_row\nreceipt,service,,,\n',
            b'kind,category,account_code,amount,source_row\nreceipt,service,,0,x,extra\n',
            b'kind,category,account_code,amount,source_row\n"unterminated']
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                summary_csv.parse(SimpleUploadedFile('bad.csv', data), self.accounting_office.pk)
        with patch.object(summary_csv, 'MAX_ROWS', 2), self.assertRaisesMessage(ValidationError, 'exceeds'):
            summary_csv.parse(self.upload(3), self.accounting_office.pk)
        with patch.object(summary_csv, 'MAX_BYTES', 10), self.assertRaisesMessage(ValidationError, 'exceeds'):
            summary_csv.parse(self.upload(3), self.accounting_office.pk)
        raw = b'kind,category,account_code,amount,source_row\nreceipt,service,,0,"p1, zero"\nexpenditure,mooe,,0,p2\n'
        parsed = summary_csv.parse(SimpleUploadedFile('zero.csv', raw), self.accounting_office.pk)
        self.assertIsNone(parsed[0]['account_id'])
        self.assertEqual(summary_actuals.normalize(self.accounting_office.pk, parsed)[0]['amount'], '0.00')

    def test_explicit_csv_mode_and_template_permission(self):
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(reverse('accounting:summary_csv_template')).content.decode().strip(), ','.join(summary_csv.COLUMNS))
        data = self.post_data(3); data['row_input'] = 'manual'
        response = self.client.post(reverse('accounting:summary_create'), data)
        self.assertContains(response, 'will not be silently ignored')
        self.assertFalse(Actual.objects.exists())
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(reverse('accounting:summary_csv_template')).status_code, 403)
