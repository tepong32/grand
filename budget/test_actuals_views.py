from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.core import signing
from unittest.mock import patch
from django.test import Client
from django.urls import reverse

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from .test_actuals_selection import ActualsSelectionTests
from .models import BudgetAuditEvent
from .services import transition_version


class ActualsSourceViewTests(ActualsSelectionTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.preparer)
        self.url = reverse('budget:actuals_sources', args=[self.version.public_id])
        self.scope = f'{self.fund.pk}:{self.center.pk}:half'

    def screen(self):
        return self.client.get(self.url, {'scope': self.scope})

    def token(self, response, kind='native'):
        return next(item for item in response.context['candidates'] if item['kind'] == kind)['form']['preview'].value()

    def post(self, token):
        return self.client.post(self.url, {'preview': token, 'reason': 'Reviewed office coverage'})

    def test_inspect_select_replay_clear_and_get_is_read_only(self):
        before = BudgetAuditEvent.objects.count()
        page = self.screen()
        self.assertContains(page, 'Native certification')
        self.assertContains(page, '100.00')
        self.assertEqual(BudgetAuditEvent.objects.count(), before)
        token = self.token(page)
        self.assertEqual(self.post(token).status_code, 302)
        self.assertEqual(self.post(token).status_code, 409)
        page = self.screen()
        self.assertContains(page, 'Retained explicit choice')
        self.assertEqual(self.post(page.context['clear_form']['preview'].value()).status_code, 302)
        self.version.refresh_from_db()
        self.assertFalse(self.version.actuals_source_selection)

    def test_external_and_native_are_distinct_choices(self):
        self.adopt('140')
        page = self.screen()
        self.assertContains(page, 'Adopted external certificate')
        self.assertEqual(len(page.context['candidates']), 2)
        self.assertEqual(self.post(self.token(page, 'external')).status_code, 302)
        self.version.refresh_from_db()
        self.assertEqual(self.version.actuals_source_selection[self.scope]['kind'], 'external')

    def test_changed_source_and_tampered_preview_reject_without_mutation(self):
        token = self.token(self.screen())
        self.assertEqual(self.post(token + 'tampered').status_code, 409)
        self.journal('POST-AFTER-PREVIEW', date(2026, 6, 30), Decimal('1'))
        self.assertEqual(self.post(token).status_code, 409)
        self.version.refresh_from_db()
        self.assertFalse(self.version.actuals_source_selection)
        self.assertContains(self.screen(), 'fresh certification')

    def test_uat_cannot_select_and_csrf_is_required(self):
        token = self.token(self.screen())
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.preparer)
        self.assertEqual(csrf_client.post(self.url, {'preview': token, 'reason': 'Coverage'}).status_code, 403)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        page = self.screen()
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'Select this source')
        self.assertEqual(self.post(token).status_code, 403)

    def test_submitted_evidence_remains_inspectable_without_new_candidates(self):
        self.choose()
        token = self.token(self.screen())
        self.version = transition_version(self.version, 'submit', self.preparer)
        self.assertEqual(self.post(token).status_code, 409)
        page = self.screen()
        self.assertContains(page, 'Retained explicit choice')
        self.assertFalse(page.context['candidates'])
        self.assertNotContains(page, 'Select this source')

    def test_preview_cannot_be_used_by_another_actor(self):
        token = self.token(self.screen())
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post(token).status_code, 403)
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',
            codename='prepare_budget_proposals'))
        self.assertEqual(self.post(token).status_code, 409)
        self.client.force_login(self.maker)
        self.assertIn(self.screen().status_code, (403, 404))

    def test_expired_preview_preserves_explanation_without_mutation(self):
        token = self.token(self.screen())
        original_loads = signing.loads
        def expired_preview(*args, **kwargs):
            if kwargs.get('salt') == 'budget.actuals-source-preview.v1':
                raise signing.SignatureExpired('Expired')
            return original_loads(*args, **kwargs)
        with patch('budget.actuals_views.signing.loads', side_effect=expired_preview):
            response = self.post(token)
        self.assertContains(response, 'Reviewed office coverage', status_code=409)
        self.version.refresh_from_db()
        self.assertFalse(self.version.actuals_source_selection)

    def test_bad_scope_does_not_expose_candidate_rows(self):
        page = self.client.get(self.url, {'scope': f'{self.fund.pk}:{self.center.pk+1000}:half'})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(page.context['candidates'])

    def test_row_fingerprint_is_rechecked(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.choose(expected_rows_checksum='not-the-preview')
