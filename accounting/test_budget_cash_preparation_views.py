import io
import json
import zipfile
from hashlib import sha256
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .test_budget_cash_preparations import NativeCashPreparationTests
from . import budget_cash_preparations as service, budget_cash
from .models import NativeBudgetCashPreparation as Record, JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class NativeCashPreparationViewTests(NativeCashPreparationTests):
    def url(self, name, record=None, kind=None):
        args = [record.public_id] if record else []
        if kind: args.append(kind)
        return reverse('accounting:native_cash_' + name, args=args)

    def form_data(self, **changes):
        data = dict(fund=self.fund.pk, opening_batch=self.batch.pk, budget_department=self.budget_office.pk,
            treasury_department=self.treasury_office.pk, entity_key='general', coverage_authority='Explicit synthetic coverage',
            balance_date='2026-09-04', boundary='end_of_day', expected_latest=0, restriction_source='')
        data.update(changes); return data

    def export_grant(self):
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='export_native_budget_cash'))

    def test_form_submission_successor_csrf_scope_and_unknown_restrictions(self):
        self.client.force_login(self.maker)
        self.assertContains(self.client.get(self.url('create')), 'Reconciled opening source')
        self.assertEqual(Record.objects.count(), 0)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.maker)
        self.assertEqual(csrf.post(self.url('create'), self.form_data()).status_code, 403)
        response = self.client.post(self.url('create'), self.form_data())
        self.assertEqual(response.status_code, 302)
        first = Record.objects.get()
        self.assertContains(self.client.get(self.url('detail', first)), 'Unknown')
        self.assertContains(self.client.get(self.url('register'), {'q': str(first.public_id)}), str(first.public_id))
        self.assertContains(self.client.get(self.url('register'), {'q': self.fund.code}), str(first.public_id))
        self.assertEqual(self.client.post(self.url('detail', first)).status_code, 405)
        self.assertEqual(self.client.get(self.url('export', first, 'snapshot')).status_code, 403)
        self.export_grant()
        self.assertEqual(self.client.get(self.url('export', first, 'certificate')).status_code, 404)
        successor = self.client.get(self.url('successor', first))
        self.assertTrue(successor.context['form'].fields['fund'].disabled)
        self.assertContains(self.client.post(self.url('successor', first), self.form_data(expected_latest=2)), 'displayed predecessor')
        self.assertEqual(Record.objects.count(), 1)
        self.assertEqual(self.client.post(self.url('successor', first), self.form_data(expected_latest=1, entity_key='forged')).status_code, 302)
        self.assertEqual(Record.objects.get(version=2).entity_key, 'general')
        self.assertContains(self.client.post(self.url('successor', first), self.form_data(expected_latest=1)), 'newer native cash')
        self.assertEqual(Record.objects.count(), 2)
        original = first.payload_checksum
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.get(self.url('create')).status_code, 403)
        self.assertEqual(self.client.post(self.url('successor', first), self.form_data(expected_latest=1)).status_code, 403)
        self.assertEqual(self.client.get(self.url('export', first, 'snapshot')).status_code, 200)
        first.refresh_from_db(); self.assertEqual(first.payload_checksum, original)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_full_restriction_schedule_originals_exports_and_source_visibility(self):
        rows = [dict(key=f'R{number}', reference=f'Synthetic restriction {number}', purpose='Explicit item',
            coverage=f'Only item {number}', amount='0.01') for number in range(101)]
        from reportlab.pdfgen import canvas
        def doc():
            stream = io.BytesIO(); pdf = canvas.Canvas(stream)
            pdf.drawString(30, 800, 'Synthetic gross 1000 / restrictions 1.01 / net 998.99')
            pdf.save(); return SimpleUploadedFile('source.pdf', stream.getvalue(), content_type='application/pdf')
        historical = self.historical(rows=rows, restricted='1.01', net='998.99', certificate=doc(), reconciliation=doc())
        budget_cash.review(historical, self.poster, adopt=True, note='Exact synthetic source checked',
            authority='Independent designation', verified_documents=True)
        record = service.prepare(**self.preparation_args(restriction_source_id=historical.pk))
        self.client.force_login(self.maker); self.export_grant()
        detail = self.client.get(self.url('detail', record), {'rows_page': 2})
        self.assertContains(detail, 'Synthetic restriction 100')
        self.assertEqual(detail.context['rows'].paginator.count, 101)
        self.assertEqual(len(detail.context['rows']), 1)
        filtered = self.client.get(self.url('detail', record), {'row_q': 'restriction 100', 'line_q': 'cash'})
        self.assertEqual(filtered.context['rows'].paginator.count, 1)
        self.assertEqual(filtered.context['lines'].paginator.count, 1)
        self.assertContains(filtered, '998.99')
        self.assertEqual(self.client.get(self.url('export', record, 'package')).status_code, 403)
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='export_budget_cash_evidence'))
        response = self.client.get(self.url('export', record, 'package'), {'row_q': 'restriction 100', 'lines_page': 9})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-GRAND-Export-SHA256'], sha256(response.content).hexdigest())
        with zipfile.ZipFile(io.BytesIO(response.content)) as package:
            self.assertCountEqual(package.namelist(), ['evidence.json', 'certificate.pdf', 'reconciliation.pdf'])
            self.assertEqual(package.read('certificate.pdf'), bytes(record.certificate))
            self.assertEqual(package.read('reconciliation.pdf'), bytes(record.reconciliation))
            exported = json.loads(package.read('evidence.json'))
            self.assertEqual(exported['payload'], record.payload)
            self.assertEqual(len(exported['payload']['restriction_source']['payload']['restrictions']), 101)
        self.assertEqual(self.client.get(self.url('export', record, 'package')).content, response.content)
        self.assertEqual(self.client.get(self.url('export', record, 'certificate')).content, bytes(record.certificate))
        old_permissions = Permission.objects.filter(content_type__app_label='accounting', codename__in=(
            'view_budget_cash_evidence', 'prepare_budget_cash_evidence', 'review_budget_cash_evidence', 'export_budget_cash_evidence'))
        self.maker.user_permissions.remove(*old_permissions)
        self.assertEqual(self.client.get(self.url('detail', record)).status_code, 404)
        self.assertEqual(self.client.get(self.url('export', record, 'snapshot')).status_code, 404)
        self.assertEqual(self.client.get(self.url('register')).context['page'].paginator.count, 0)
        self.assertEqual(self.client.get(self.url('create')).status_code, 200)  # native gross only
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_configured_native_roles_and_tamper_denial(self):
        call_command('configure_finance_roles', stdout=io.StringIO())
        self.maker.user_permissions.clear()
        self.maker.groups.add(Group.objects.get(name='Accounting DV Preparer'))
        self.poster.user_permissions.clear()
        self.poster.groups.add(Group.objects.get(name='Accounting Reviewer'))
        self.assertTrue(service.permitted(self.maker, 'prepare'))
        self.assertTrue(service.permitted(self.maker, 'export'))
        self.assertFalse(service.permitted(self.poster, 'prepare'))
        self.assertTrue(service.permitted(self.poster, 'view'))
        record = service.prepare(**self.preparation_args())
        self.client.force_login(self.maker)
        self.assertContains(self.client.get(reverse('accounting:workspace')), 'Native cash preparations')
        self.fund.code = 'RENAMED'; self.fund.save()
        self.assertEqual(self.client.get(self.url('register'), {'q': 'GF'}).context['page'].paginator.count, 1)
        self.assertContains(self.client.get(self.url('detail', record)), 'GF / general')
        Record.objects.filter(pk=record.pk).update(payload_checksum='0' * 64)
        self.assertEqual(self.client.get(self.url('detail', record)).status_code, 409)
        self.assertEqual(self.client.get(self.url('export', record, 'snapshot')).status_code, 409)
        self.maker.groups.add(Group.objects.get(name=FINANCE_UAT_VIEWER_GROUP))
        self.assertFalse(service.permitted(self.maker, 'prepare'))
        self.assertTrue(service.permitted(self.maker, 'export'))
