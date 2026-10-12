from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from . import tests as fixtures
from .models import BudgetCall, BudgetVersion, BudgetAuditEvent
from .services import create_version_draft, consolidate_versions


class VersionIdentityTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.AnnualBudgetPreparationTests.setUpTestData.__func__)
    employee = classmethod(fixtures.AnnualBudgetPreparationTests.employee.__func__)
    make_call = fixtures.AnnualBudgetPreparationTests.make_call
    make_version = fixtures.AnnualBudgetPreparationTests.make_version
    add_line = fixtures.AnnualBudgetPreparationTests.add_line

    def setUp(self):
        self.call = self.make_call(BudgetCall.PUBLISHED)

    def draft(self, number=1, kind=BudgetVersion.EXECUTIVE, office=None):
        return BudgetVersion(department_id=self.budget_office.pk, department_label=self.budget_office.name,
            budget_call=self.call, fiscal_year=self.fiscal_year, kind=kind, version=number,
            requesting_department_id=office, title='Synthetic version identity',
            change_explanation='Retain an explicit version', created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username)

    def test_database_rejects_duplicate_combined_identity_but_keeps_distinct_scopes(self):
        first = self.draft(); first.save()
        with self.assertRaises(IntegrityError), transaction.atomic(using='finance'):
            self.draft().save()
        self.draft(2).save()
        self.draft(kind=BudgetVersion.FINAL).save()
        self.draft(kind=BudgetVersion.DEPARTMENT, office=self.requesting_office.pk).save()
        self.draft(kind=BudgetVersion.DEPARTMENT, office=self.other_office.pk).save()
        self.assertEqual(BudgetVersion.objects.count(), 5)

    def test_manual_creation_and_consolidation_share_sequence(self):
        create_version_draft(self.draft(4), self.preparer)
        source = self.make_version(self.call)
        self.add_line(source)
        source.status = BudgetVersion.APPROVED; source.save(update_fields=['status'])
        target = consolidate_versions(sources=[source], user=self.reviewer, title='Combined', change_explanation='Approved source')
        self.assertEqual(target.version, 5)
        with self.assertRaises(ValidationError):
            create_version_draft(self.draft(5), self.preparer)
        self.assertEqual(BudgetAuditEvent.objects.filter(action='created').count(), 1)

    def test_manual_duplicate_is_a_form_error_not_a_second_write(self):
        create_version_draft(self.draft(), self.preparer)
        self.client.force_login(self.preparer)
        response = self.client.post(reverse('budget:version_create'), {'budget_call': self.call.pk,
            'kind': BudgetVersion.EXECUTIVE, 'version': 1, 'title': 'Duplicate',
            'requesting_department': '', 'change_explanation': 'Must not overwrite the original', 'supersedes': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(BudgetVersion.objects.count(), 1)

    def test_draft_creation_rechecks_call_after_form_selection(self):
        draft = self.draft()
        BudgetCall.objects.filter(pk=self.call.pk).update(status=BudgetCall.CLOSED)
        with self.assertRaisesMessage(ValidationError, 'published budget call'):
            create_version_draft(draft, self.preparer)
        self.assertFalse(BudgetVersion.objects.exists())
