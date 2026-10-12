import io
import json
import zipfile
from hashlib import sha256

from django.contrib.auth.models import Group, Permission
from django.test import Client
from django.urls import reverse

from .test_budget_cash import BudgetCashTests
from . import budget_cash as service
from .models import BudgetCashEvidence as Record
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class BudgetCashViewTests(BudgetCashTests):
    def url(self, name, record=None, kind=None):
        args = [record.public_id] if record else []
        if kind: args.append(kind)
        return reverse('accounting:budget_cash_' + name, args=args)

    def test_scoped_review_documents_complete_exports_and_tamper_denial(self):
        record = service.propose(**self.cash_args())
        self.client.force_login(self.preparer)  # assigned Budget office
        self.assertEqual(self.client.get(self.url('detail', record)).status_code, 404)
        self.client.force_login(self.checker)
        self.assertContains(self.client.get(self.url('detail', record)), '75.00')
        self.assertEqual(self.client.get(self.url('decide', record)).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.checker)
        self.assertEqual(csrf.post(self.url('decide', record), {'decision': 'adopt'}).status_code, 403)
        self.client.post(self.url('decide', record), {'decision': 'adopt', 'note': 'Verified originals', 'authority': 'Designation'})
        record.refresh_from_db(); self.assertEqual(record.status, 'submitted')
        self.assertEqual(self.client.post(self.url('decide', record), {'decision': 'other'}).status_code, 400)
        self.client.post(self.url('decide', record), {'decision': 'adopt', 'verified_documents': 'yes',
            'note': 'Verified originals', 'authority': 'Designation'})
        record.refresh_from_db(); self.assertEqual(record.status, 'adopted')
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(self.url('detail', record)), 'Synthetic Treasurer')
        self.assertEqual(self.client.get(self.url('export', record, 'snapshot')).status_code, 403)
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='export_budget_cash_evidence'))
        response = self.client.get(self.url('export', record, 'package'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-GRAND-Export-SHA256'], sha256(response.content).hexdigest())
        with zipfile.ZipFile(io.BytesIO(response.content)) as package:
            self.assertCountEqual(package.namelist(), ['evidence.json', 'certificate.pdf', 'reconciliation.pdf'])
            self.assertEqual(package.read('certificate.pdf'), bytes(record.certificate))
            self.assertEqual(package.read('reconciliation.pdf'), bytes(record.reconciliation))
            evidence = json.loads(package.read('evidence.json'))
            self.assertEqual(evidence['payload'], record.payload)
            self.assertEqual(evidence['decision'], service.decision(record))
        self.assertEqual(self.client.get(self.url('export', record, 'package')).content, response.content)
        self.assertEqual(self.client.get(self.url('export', record, 'certificate')).content, bytes(record.certificate))
        self.client.force_login(self.outsider)
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='export_budget_cash_evidence'))
        self.assertEqual(self.client.get(self.url('export', record, 'snapshot')).status_code, 404)
        self.client.force_login(self.checker)
        self.checker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        pending = service.propose(**self.cash_args(expected_latest=1))
        self.assertEqual(self.client.post(self.url('decide', pending), {'decision': 'return', 'note': 'x', 'authority': 'x'}).status_code, 403)
        self.assertContains(self.client.get(self.url('detail', record)), '75.00')
        Record.objects.filter(pk=record.pk).update(certificate=b'corrupt')
        self.assertEqual(self.client.get(self.url('detail', record)).status_code, 409)
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(self.url('export', record, 'package')).status_code, 409)

    def test_complete_row_and_history_pagination_preserves_controls(self):
        rows = [{'key': f'r{i}', 'reference': f'p{i}', 'purpose': f'Purpose {i}',
            'coverage': f'Unique source {i}', 'amount': '1'} for i in range(101)]
        record = service.propose(**self.cash_args(rows=rows, gross='200', restricted='101', net='99'))
        self.client.force_login(self.checker)
        response = self.client.get(self.url('detail', record), {'rows_page': 2})
        self.assertContains(response, 'Purpose 100')
        self.assertContains(response, '99.00')
        self.assertEqual(len(response.context['row_page']), 1)
        self.assertEqual(response.context['row_count'], 101)
        response = self.client.get(self.url('detail', record), {'row_q': 'Purpose 100'})
        self.assertEqual(response.context['row_page'].paginator.count, 1)
        for latest in range(1, 26):
            service.propose(**self.cash_args(expected_latest=latest))
        response = self.client.get(self.url('detail', record), {'page': 2})
        self.assertEqual(response.context['history'].paginator.count, 26)
        self.assertEqual(len(response.context['history']), 1)
        self.assertContains(response, 'Version 1')
        response = self.client.get(self.url('register'), {'q': 'Synthetic General', 'status': 'submitted'})
        self.assertEqual(response.context['page'].paginator.count, 26)
        self.assertEqual(service.verify(record)['restricted'], '101.00')
