import io
import json
import zipfile
from copy import deepcopy
from hashlib import sha256
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from . import test_budget_cash_certifications as fixtures
from . import budget_cash, budget_cash_preparations as preparations
from .models import NativeBudgetCashDecision as Decision, JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class NativeCashCertificationViewTests(fixtures.NativeCashCertificationTests):
    def url(self, name, record, extra=None):
        return reverse('accounting:native_cash_' + name, args=[record.public_id, *([extra] if extra else [])])

    def post_data(self, **changes):
        values = dict(outcome='certify', authority='Synthetic statutory officer designation',
            note='Reviewed all retained source rows and original restriction documents', verified='on')
        values.update(changes); return values

    def test_joint_http_decisions_csrf_confirmation_replay_and_retained_state(self):
        record = self.cash_preparation()
        frozen = deepcopy(record.payload)
        self.client.force_login(self.treasurer)
        page = self.client.get(self.url('detail', record))
        self.assertContains(page, 'Treasurer decision')
        self.assertNotContains(page, 'Accountant decision')
        self.assertEqual(self.client.get(self.url('decide', record, 'treasurer')).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.treasurer)
        self.assertEqual(csrf.post(self.url('decide', record, 'treasurer'), self.post_data()).status_code, 403)
        rejected = self.client.post(self.url('decide', record, 'treasurer'), self.post_data(verified=''))
        self.assertContains(rejected, 'Review the complete evidence', status_code=400)
        self.assertEqual(Decision.objects.count(), 0)
        csrf.get(self.url('detail', record))
        token = csrf.cookies['csrftoken'].value
        self.assertEqual(csrf.post(self.url('decide', record, 'treasurer'), self.post_data(),
            HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertEqual(self.client.post(self.url('decide', record, 'treasurer'), self.post_data()).status_code, 409)
        self.client.force_login(self.poster)
        self.assertContains(self.client.get(self.url('detail', record)), 'Accountant decision')
        self.assertEqual(self.client.post(self.url('decide', record, 'accountant'), self.post_data()).status_code, 302)
        page = self.client.get(self.url('detail', record))
        self.assertContains(page, 'Jointly certified fixed cash snapshot.')
        self.assertEqual(page.context['decision_forms'], [])
        self.assertEqual(Decision.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        record.refresh_from_db(); self.assertEqual(record.payload, frozen)

    def test_full_joint_exports_originals_permission_and_tampered_decision(self):
        rows = [dict(key=f'R{i}', reference=f'Synthetic row {i}', purpose='Explicit restriction',
            coverage=f'Disjoint source {i}', amount='0.99' if i < 100 else '1.00') for i in range(101)]
        historical = self.historical(rows=rows)
        budget_cash.review(historical, self.poster, adopt=True, verified_documents=True,
            authority='Synthetic adopter', note='Complete original documents checked')
        record = preparations.prepare(**self.preparation_args(restriction_source_id=historical.pk))
        self.client.force_login(self.poster)
        self.assertEqual(self.client.get(self.url('export', record, 'joint_snapshot')).status_code, 403)
        self.poster.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='export_native_budget_cash'))
        pending = self.client.get(self.url('export', record, 'joint_snapshot')).content
        self.decision(record); self.decision(record, 'treasurer')
        page = self.client.get(self.url('detail', record), {'row_q': 'row 100'})
        self.assertEqual(page.context['rows'].paginator.count, 1)
        response = self.client.get(self.url('export', record, 'joint_snapshot'), {'row_q': 'no results'})
        self.assertEqual(response.status_code, 200)
        evidence = json.loads(response.content)
        self.assertEqual(evidence['payload']['status'], 'jointly_certified')
        self.assertEqual(len(evidence['payload']['decisions']), 2)
        self.assertEqual(len(evidence['payload']['original_preparation']['restriction_source']['payload']['restrictions']), 101)
        self.assertEqual(response.headers['X-GRAND-Export-SHA256'], sha256(response.content).hexdigest())
        self.assertNotEqual(pending, response.content)
        self.assertEqual(json.loads(pending)['payload']['status'], 'awaiting_joint_certification')
        self.assertEqual(self.client.get(self.url('export', record, 'joint_package')).status_code, 403)
        self.poster.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='export_budget_cash_evidence'))
        package = self.client.get(self.url('export', record, 'joint_package'))
        self.assertEqual(package.status_code, 200)
        self.assertEqual(package.content, self.client.get(self.url('export', record, 'joint_package')).content)
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            self.assertEqual(set(archive.namelist()), {'joint-evidence.json', 'certificate.pdf', 'reconciliation.pdf'})
            self.assertEqual(archive.read('joint-evidence.json'), response.content)
            self.assertEqual(archive.read('certificate.pdf'), bytes(historical.certificate))
            self.assertEqual(archive.read('reconciliation.pdf'), bytes(historical.reconciliation))
        decision = Decision.objects.first()
        Decision.objects.filter(pk=decision.pk).update(payload_checksum='tampered')
        self.assertEqual(self.client.get(self.url('detail', record)).status_code, 409)
        self.assertEqual(self.client.get(self.url('export', record, 'joint_snapshot')).status_code, 409)
        self.assertEqual(self.client.get(self.url('export', record, 'joint_package')).status_code, 409)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_configured_certifier_roles_scope_uat_unknown_and_return(self):
        record = preparations.prepare(**self.preparation_args())
        call_command('configure_finance_roles', stdout=io.StringIO())
        for actor, group_name in ((self.poster, 'Budget Cash Accountant Certifier'),
                                  (self.treasurer, 'Budget Cash Treasurer Certifier')):
            actor.user_permissions.clear()
            actor.groups.add(Group.objects.get(name=group_name))
        for name in ('Accounting Reviewer', 'Treasury Collection Officer', 'Treasury Disbursement Officer'):
            self.assertFalse(Group.objects.get(name=name).permissions.filter(
                codename__in=('certify_accountant_native_budget_cash', 'certify_treasurer_native_budget_cash')).exists())
        self.client.force_login(self.treasurer)
        self.assertEqual(self.client.get(reverse('accounting:workspace')).status_code, 200)
        self.assertContains(self.client.get(self.url('detail', record)), 'Restrictions and net cash are unknown')
        self.assertEqual(self.client.post(self.url('decide', record, 'treasurer'), self.post_data()).status_code, 409)
        self.assertEqual(self.client.post(self.url('decide', record, 'accountant'), self.post_data()).status_code, 403)
        self.treasurer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.post(self.url('decide', record, 'treasurer'), self.post_data(outcome='return')).status_code, 403)
        self.assertEqual(self.client.get(self.url('export', record, 'joint_snapshot')).status_code, 200)
        self.treasurer.groups.remove(Group.objects.get(name=FINANCE_UAT_VIEWER_GROUP))
        self.assertEqual(self.client.post(self.url('decide', record, 'treasurer'),
            self.post_data(outcome='return', verified='')).status_code, 302)
        self.assertContains(self.client.get(self.url('detail', record)), 'Returned preparation.')
        self.client.force_login(self.poster)
        self.assertEqual(self.client.post(self.url('decide', record, 'accountant'), self.post_data()).status_code, 409)
        self.assertEqual(Decision.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
