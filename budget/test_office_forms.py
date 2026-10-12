from copy import deepcopy
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from pypdf import PdfReader

from accounting.cash_classifications import checksum
from departments.models import Department
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import office_forms as service
from . import test_actuals_selection as fixtures
from .models import BudgetOfficeForm, BudgetVersion
from .planning_context import set_estimate
from .services import transition_version


class OfficeFormTests(fixtures.ActualsSelectionTests):
    def complete_proposal(self):
        # The retained synthetic external document explicitly supplies the prior row.
        from reportlab.pdfgen import canvas
        file = BytesIO()
        page = canvas.Canvas(file)
        page.drawString(40, 790, 'SYNTHETIC TEST ONLY - Full-year 2025 office actuals certificate')
        page.drawString(40, 770, 'Office supplies, MOOE: explicit certified zero; GF / GSO; January-December 2025')
        page.drawString(40, 750, 'Synthetic original Accountant - synthetic designation evidence')
        page.save()
        prior = self.adopt('0', period_start=date(2025, 1, 1), period_end=date(2025, 12, 31),
            document=SimpleUploadedFile('synthetic-prior-actuals.pdf', file.getvalue(), content_type='application/pdf'))
        self.choose(prefix='prior', kind='external', source_id=prior.public_id)
        self.choose()
        from decimal import Decimal
        set_estimate(version=self.version, line_id=self.line.pk, actor=self.preparer,
            amount=Decimal('40'), as_of=date(2026, 8, 1), basis='Synthetic department forecast worksheet')
        self.version = transition_version(self.version, 'submit', self.preparer)
        self.version = transition_version(self.version, 'approve', self.reviewer, 'Independent complete proposal review')

    def arguments(self, amount='140', **changes):
        # Preserve the inherited external-adoption fixture API.
        return super().arguments(amount, **changes)

    def form_args(self, **changes):
        args = dict(version=self.version, actor=self.preparer, office_id=self.requesting_office.pk,
            fund_id=self.fund.pk, expected_latest=0, expected_context_checksum=checksum(self.version.planning_context_snapshot),
            lgu='SYNTHETIC TEST MUNICIPALITY - Peña', fund_scope='Synthetic General Fund scope, peso (₱) reporting and retained fund designation',
            coverage='Synthetic complete office worksheet covers all centers and objects, both historical periods and dated forecasts.',
            coverage_confirmed=True, signatories={role: {'name': 'Synthetic ' + label,
                'authority': 'Synthetic designation record for ' + label} for role, label in service.ROLES.items()})
        args.update(changes)
        return args

    def test_issue_retain_unsigned_pdf_and_download_after_sources_change(self):
        self.complete_proposal()
        item = service.prepare(**self.form_args())
        self.assertEqual(item.payload['schedule']['totals'], {'prior_amount': '0.00', 'half_amount': '100.00',
            'estimate': '40.00', 'current_total': '140.00', 'proposed': '1000.00'})
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget', codename='review_budget_proposals'))
        with self.assertRaisesMessage(ValidationError, 'different reviewer'):
            service.decide(item=item, actor=self.preparer, issue=True, note='Cannot self issue')
        item = service.decide(item=item, actor=self.reviewer, issue=True, note='Checked complete coverage and all three designations')
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(bytes(item.document))).pages)
        self.assertIn('UNSIGNED COPY FOR PHYSICAL SIGNING', text)
        self.assertIn('140.00', text)
        self.assertIn('Local Chief Executive', text)
        self.assertIn('Peña', text)
        self.assertIn('₱', text)
        original = bytes(item.document)
        Department.objects.filter(pk=self.requesting_office.pk).update(name='Later office name')
        self.client.force_login(self.preparer)
        with patch('budget.office_form_pdf.render_document', side_effect=AssertionError('Never re-render a download')):
            response = self.client.get(reverse('budget:office_form_download', args=[item.public_id]))
        self.assertEqual(response.content, original)
        self.assertEqual(response['X-GRAND-Export-SHA256'], item.document_checksum)
        self.assertEqual(service.verify(item)['schedule']['office_label'], self.requesting_office.name)
        with self.assertRaises(ValidationError):
            item.save()

    def test_missing_actual_and_forecast_are_not_zero(self):
        self.choose()
        self.version = transition_version(self.version, 'submit', self.preparer)
        self.version = transition_version(self.version, 'approve', self.reviewer, 'Review incomplete planning context')
        with self.assertRaises(ValidationError) as result:
            service.prepare(**self.form_args())
        self.assertIn('prior amount is missing', str(result.exception))
        self.assertIn('estimate is missing', str(result.exception))
        self.assertFalse(BudgetOfficeForm.objects.exists())

    def test_scope_coverage_designation_and_preview_guards(self):
        self.complete_proposal()
        for changes in ({'office_id': self.budget_office.pk}, {'fund_id': self.fund.pk + 1000},
                        {'coverage_confirmed': False}, {'coverage': ''}, {'signatories': {}},
                        {'expected_context_checksum': 'stale'}, {'expected_latest': 9}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                service.prepare(**self.form_args(**changes))
        item = service.prepare(**self.form_args())
        with self.assertRaises(ValidationError):
            service.prepare(**self.form_args())
        newer = service.prepare(**self.form_args(expected_latest=1))
        with self.assertRaisesMessage(ValidationError, 'newer preparation'):
            service.decide(item=item, actor=self.reviewer, issue=True, note='Old preview')
        returned = service.decide(item=item, actor=self.reviewer, issue=False, note='Retain superseded preparation')
        self.assertEqual(returned.status, BudgetOfficeForm.RETURNED)
        self.assertFalse(returned.document)
        self.assertEqual(newer.version, 2)

    def test_source_changed_after_preparation_blocks_issue_but_allows_return(self):
        self.complete_proposal()
        item = service.prepare(**self.form_args())
        self.native = self.decide(self.native_propose(expected_latest=1))
        with self.assertRaises(ValidationError):
            service.decide(item=item, actor=self.reviewer, issue=True, note='Source superseded')
        item.refresh_from_db()
        self.assertEqual(item.status, BudgetOfficeForm.PREPARED)
        self.assertFalse(item.document)
        service.decide(item=item, actor=self.reviewer, issue=False, note='Return stale source for a successor')

    def test_integrity_and_owner_uat_controls(self):
        self.complete_proposal()
        with self.assertRaises(PermissionDenied):
            service.prepare(**self.form_args(actor=self.maker))
        item = service.prepare(**self.form_args())
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            service.prepare(**self.form_args(expected_latest=1))
        self.client.force_login(self.maker)
        self.assertIn(self.client.get(reverse('budget:office_form_detail', args=[item.public_id])).status_code, (403, 404))
        item = service.decide(item=item, actor=self.reviewer, issue=True, note='Independent coverage review')
        BudgetOfficeForm.objects.filter(pk=item.pk).update(document=b'altered bytes')
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(reverse('budget:office_form_download', args=[item.public_id])).status_code, 409)

    def test_legacy_snapshot_and_tampered_submission_not_reconstructed(self):
        self.complete_proposal()
        data = deepcopy(self.version.planning_context_snapshot)
        data['schema'] = 6
        BudgetVersion.objects.filter(pk=self.version.pk).update(planning_context_snapshot=data)
        self.version.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'submitted planning evidence'):
            service.prepare(**self.form_args())

    def test_http_flow_signed_preview_csrf_and_pagination(self):
        self.complete_proposal()
        self.client.force_login(self.preparer)
        url = reverse('budget:office_form_prepare', args=[self.version.public_id, self.requesting_office.pk, self.fund.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Prepare office Form 2')
        data = {key: value for key, value in self.form_args().items() if key in ('lgu', 'fund_scope', 'coverage', 'coverage_confirmed')}
        data['preview'] = page.context['form']['preview'].value()
        for role, values in self.form_args()['signatories'].items():
            data.update({role + '_' + key: value for key, value in values.items()})
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.preparer)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.assertEqual(self.client.post(url, {**data, 'preview': data['preview'] + 'changed'}).status_code, 409)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        item = BudgetOfficeForm.objects.get()
        self.assertEqual(self.client.get(reverse('budget:office_form_download', args=[item.public_id])).status_code, 409)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(reverse('budget:office_form_action', args=[item.public_id]),
            {'action': 'issue', 'note': 'Independent full coverage and authority review'}).status_code, 302)
        self.assertContains(self.client.get(reverse('budget:office_form_detail', args=[item.public_id])), 'Download retained unsigned PDF')
        self.assertContains(self.client.get(reverse('budget:office_forms', args=[self.version.public_id])), 'Issued unsigned copy')

    def test_known_unselected_scope_blocks_new_form(self):
        self.complete_proposal()
        with patch('budget.actuals_scopes.available_scopes', return_value=({'missing': {
            'fund_id': self.fund.pk, 'center_id': self.center.pk, 'label': 'Known additional history'}}, [])):
            with self.assertRaisesMessage(ValidationError, 'Additional known office history'):
                service.prepare(**self.form_args())

    def test_object_totals_span_centers_without_borrowing_other_office_or_fund(self):
        self.complete_proposal()
        context = deepcopy(self.version.planning_context_snapshot)
        original = context['certified_schedule'][0]
        extra = deepcopy(original)
        extra['center_id'] += 1000
        extra['center_code'] = 'SECOND-CENTER'
        for prefix in ('prior', 'half'):
            for evidence in extra[prefix + '_rows']:
                evidence['scope']['center_id'] = extra['center_id']
        other_office, other_fund = deepcopy(original), deepcopy(original)
        other_office['office_id'] = self.budget_office.pk
        other_fund['fund_id'] += 1000
        context['certified_schedule'].extend([extra, other_office, other_fund])
        result = service.project(context, self.requesting_office.pk, self.fund.pk)
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(len(result['rows'][0]['sources']), 2)
        self.assertEqual(result['totals']['current_total'], '280.00')
        self.assertEqual(result['totals']['proposed'], '2000.00')

    def test_unsupported_glyph_rolls_back_issuance_without_missing_character_boxes(self):
        self.complete_proposal()
        args = self.form_args(lgu='Synthetic unsupported glyph \U0001f600')
        item = service.prepare(**args)
        with self.assertRaisesMessage(ValidationError, 'font cannot render'):
            service.decide(item=item, actor=self.reviewer, issue=True, note='Test print-font rejection')
        item.refresh_from_db()
        self.assertEqual(item.status, BudgetOfficeForm.PREPARED)
        self.assertFalse(item.document)
        self.assertIsNone(item.decided_at)
