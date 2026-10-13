from decimal import Decimal
from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_budget_native_certifications as fixtures
from .models import NativeBudgetStatement as Statement


class NativeStatementViewsTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.NativeCertificationTests.setUpTestData.__func__)
    employee = classmethod(fixtures.NativeCertificationTests.employee.__func__)
    setUp = fixtures.NativeCertificationTests.setUp
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

    def preview(self):
        self.client.force_login(self.maker)
        response = self.client.get(reverse('accounting:budget_native_prepare'),
            {'fund': self.fund.pk, 'start': '2026-01-01', 'end': '2026-06-30'})
        self.assertEqual(response.status_code, 200)
        return {'fund': self.fund.pk, 'start': '2026-01-01', 'end': '2026-06-30',
            'context': response.context['preparation'].initial['context'],
            'reason': 'Actual HTTP preparation', 'coverage': 'Complete source and supporting schedule checked',
            'evidence_reference': 'SYN-HTTP-NATIVE'}

    def test_preparation_independent_certification_and_retained_export(self):
        result = self.client.post(reverse('accounting:budget_native_prepare'), self.preview())
        self.assertEqual(result.status_code, 302)
        record = Statement.objects.get()
        detail = reverse('accounting:budget_native_detail', args=[record.public_id])
        self.assertContains(self.client.get(detail), '100.00')
        self.assertFalse(self.client.get(detail).context['can_decide'])
        self.client.force_login(self.checker)
        decided = self.client.post(reverse('accounting:budget_native_decide', args=[record.public_id]),
            {'decision': 'certify', 'authority': 'Synthetic Accountant designation', 'note': 'Independent complete-source check'})
        self.assertEqual(decided.status_code, 302)
        self.assertTrue(self.client.get(detail).context['current'])
        export = reverse('accounting:budget_native_export', args=[record.public_id])
        self.assertEqual(self.client.get(export).status_code, 403)
        self.native_grant(self.checker, 'export')
        before = self.client.get(export)
        self.assertEqual(before.status_code, 200)
        self.journal('AFTER-NATIVE-CERT', date(2026, 6, 30), Decimal('5'))
        self.assertContains(self.client.get(detail), 'source coverage has changed')
        after = self.client.get(export)
        self.assertEqual(before.content, after.content)
        self.assertEqual(before['X-GRAND-Export-SHA256'], after['X-GRAND-Export-SHA256'])

    def test_preview_actor_period_tamper_staleness_and_uat(self):
        args = self.preview()
        self.assertEqual(self.client.post(reverse('accounting:budget_native_prepare'), dict(args, context='broken')).status_code, 409)
        self.assertEqual(self.client.post(reverse('accounting:budget_native_prepare'), dict(args, end='2026-12-31')).status_code, 409)
        self.native_grant(self.checker, 'prepare')
        self.client.force_login(self.checker)
        self.assertEqual(self.client.post(reverse('accounting:budget_native_prepare'), args).status_code, 409)
        self.client.force_login(self.maker)
        self.journal('PREVIEW-BACKDATE', date(2026, 6, 30), Decimal('3'))
        stale = self.client.post(reverse('accounting:budget_native_prepare'), args)
        self.assertEqual(stale.status_code, 409)
        self.assertContains(stale, 'Actual HTTP preparation', status_code=409)
        self.assertFalse(Statement.objects.exists())
        self.maker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.get(reverse('accounting:budget_native_register')).status_code, 200)
        self.assertEqual(self.client.post(reverse('accounting:budget_native_prepare'), args).status_code, 403)

    def test_all_versions_paged_search_foreign_scope_and_post_csrf(self):
        for number in range(51):
            self.native_propose(expected_latest=number, evidence_reference=f'SYN-HISTORY-{number:03}')
        self.client.force_login(self.maker)
        register = reverse('accounting:budget_native_register')
        page = self.client.get(register, {'page': 2})
        self.assertEqual(page.context['page'].paginator.count, 51)
        self.assertEqual(len(page.context['page']), 1)
        self.assertEqual(self.client.get(register, {'q': 'SYN-HISTORY-000'}).context['page'].paginator.count, 1)
        record = Statement.objects.first()
        url = reverse('accounting:budget_native_decide', args=[record.public_id])
        self.assertEqual(self.client.get(url).status_code, 405)
        guarded = Client(enforce_csrf_checks=True); guarded.force_login(self.checker)
        self.assertEqual(guarded.post(url, {'decision': 'certify'}).status_code, 403)
        self.native_grant(self.preparer, 'view')
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(reverse('accounting:budget_native_detail', args=[record.public_id])).status_code, 404)
