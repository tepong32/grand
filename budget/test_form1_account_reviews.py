from copy import deepcopy
from io import BytesIO
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Permission, Group
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_account_proposals as fixtures
from . import form1_account_reviews as service, receipt_forecasts, form1_flows, form1_components
from . import test_form1_components as component_fixtures
from .models import Form1AccountReview as Record


class Form1AccountReviewFixture(fixtures.Form1AccountProposalFixture):
    def setUp(self):
        super().setUp()
        self.setup_account_review()

    def setup_account_review(self):
        self.approved_forecast = self.version.receipt_forecasts.get(status='approved')
        for actor, actions in ((self.preparer, ('prepare', 'view', 'export')), (self.checker, ('review', 'view', 'export'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget',
                codename__in=[action+'_form1_account_reviews' for action in actions]))
        self.checker.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='export_native_budget_actuals'))

    def code_document(self):
        from reportlab.pdfgen import canvas
        stream=BytesIO(); page=canvas.Canvas(stream)
        page.drawString(30, 790, 'SYNTHETIC TEST ONLY: reporting code selection evidence; not official LGU authority')
        page.save()
        return SimpleUploadedFile('synthetic-code-authority.pdf', stream.getvalue(), content_type='application/pdf')

    def prepare_accounts(self, **changes):
        args=dict(forecast=self.approved_forecast, actor=self.preparer,
            allocations=self.account_allocations(self.targets['valid']),
            coverage_reference='Synthetic full original component partition',
            code_reference='Synthetic reviewed code applicability fixture only',
            evidence=self.code_document(), expected_latest=0)
        args.update(changes)
        return service.prepare(**args)

    def review_accounts(self, record, **changes):
        args=dict(actor=self.checker, approve=True, note='Synthetic independent account/date and code evidence review',
            authority='Synthetic designated Accountant', codes_verified=True)
        args.update(changes)
        return service.review(record, **args)


class Form1AccountReviewTests(Form1AccountReviewFixture):
    def test_real_historical_zero_selections_preserve_missing_coverage_and_source_export(self):
        component_fixtures.Form1ComponentTests.test_real_historical_zero_rows_preserve_missing_categories_and_null_source_accounts(self)
        self.approved_forecast=self.version.receipt_forecasts.filter(status='approved').order_by('-version').first()
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=self.approved_forecast,actor=self.preparer))
        rows=self.account_allocations(self.targets['valid'])
        components={row['key']:row for row in self.inventory['payload']['components']}
        for row in rows:
            if components[row['component']]['source_account'] is None:
                row['account_id']=None
        record=self.review_accounts(self.prepare_accounts(allocations=rows))
        self.assertFalse(record.payload['draft']['payload']['source_coverage_complete'])
        self.assertTrue(service.is_current(record,self.checker))
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker,export=True)
        permission=Permission.objects.get(content_type__app_label='accounting',codename='export_budget_summary_actuals')
        self.checker.user_permissions.add(permission)
        self.assertFalse(service.snapshot(record,self.checker,export=True)['form_issued'])
        view=Permission.objects.get(content_type__app_label='accounting',codename='view_budget_summary_actuals')
        self.checker.user_permissions.remove(view)
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker)

    def test_retained_accounting_review_pure_reproduction_and_no_ledger_changes(self):
        before=JournalEntry.objects.count()
        record=self.prepare_accounts()
        original=deepcopy(record.payload)
        with self.assertNumQueries(0,using='default'), self.assertNumQueries(0,using='finance'):
            service.verify(record)
        self.assertFalse(service.snapshot(record,self.preparer)['independently_reviewed'])
        with self.assertRaises(ValidationError): self.review_accounts(record,codes_verified=False)
        record=self.review_accounts(record)
        snap=service.snapshot(record,self.checker,export=True)
        self.assertTrue(snap['independently_reviewed']); self.assertTrue(snap['code_authority_approved'])
        self.assertFalse(snap['form_issued']); self.assertTrue(service.is_current(record,self.checker))
        self.assertEqual(service.evidence_bytes(record,self.checker),bytes(record.evidence))
        self.assertEqual(record.payload,original); self.assertEqual(JournalEntry.objects.count(),before)
        with self.assertRaises(ValidationError): self.review_accounts(record)
        record.payload['code_reference']='Rewrite original'
        with self.assertRaises(ValidationError): record.save()
        with self.assertRaises(ValidationError): record.delete()

    def test_explicit_office_roles_source_access_uat_and_no_general_budget_access(self):
        record=self.prepare_accounts()
        with self.assertRaises(PermissionDenied): self.review_accounts(record,actor=self.preparer)
        with self.assertRaises(PermissionDenied): self.prepare_accounts(actor=self.checker)
        with self.assertRaises(PermissionDenied): receipt_forecasts.capture(reconciliation=self.reconciliation,actor=self.checker)
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.maker)
        permission=Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals')
        self.checker.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker)
        self.checker.user_permissions.add(permission)
        group,_=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)
        self.checker.groups.add(group)
        service.snapshot(record,self.checker)
        with self.assertRaises(PermissionDenied): self.review_accounts(record)
        self.checker.groups.remove(group)
        export=Permission.objects.get(content_type__app_label='accounting',codename='export_native_budget_actuals')
        self.checker.user_permissions.remove(export)
        with self.assertRaises(PermissionDenied): service.snapshot(record,self.checker,export=True)
        service.snapshot(record,self.checker)

    def test_pending_successor_stale_chart_returns_and_retained_old_approval(self):
        first=self.review_accounts(self.prepare_accounts())
        retained=service.snapshot(first,self.checker)
        pending=self.prepare_accounts(expected_latest=1)
        self.assertFalse(service.is_current(first,self.checker))
        self.assertEqual(service.snapshot(first,self.checker),retained)
        self.targets['valid'].title='Changed unused reporting account'; self.targets['valid'].save(update_fields=('title',))
        with self.assertRaises(ValidationError): self.review_accounts(pending)
        returned=self.review_accounts(pending,approve=False,codes_verified=False)
        service.verify(returned); self.assertEqual(returned.status,'returned')
        with self.assertRaises(ValidationError): self.prepare_accounts(expected_latest=2)

    def test_unresolved_return_and_rehashed_evidence_identity_decision_tamper(self):
        record=self.prepare_accounts(allocations=self.account_allocations())
        with self.assertRaises(ValidationError): self.review_accounts(record)
        record=self.review_accounts(record,approve=False,codes_verified=False)
        for field in ('identity','evidence','decision'):
            changed=Record.objects.select_related('proposal__fiscal_year','fund','forecast').get(pk=record.pk)
            if field=='identity': changed.payload['identity']['accounting_department_id']+=1
            elif field=='evidence': changed.evidence=b'changed original authority'
            else: changed.reviewed_by_id=changed.prepared_by_id; changed.decision_checksum=checksum(service.decision(changed))
            changed.payload_checksum=checksum(changed.payload)
            with self.subTest(field=field):
                with self.assertRaises(ValidationError): service.verify(changed)
