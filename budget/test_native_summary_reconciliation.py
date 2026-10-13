"""Real native approvals and issued office forms across both database aliases."""
from copy import copy, deepcopy
from datetime import date
from decimal import Decimal
import json
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.test import TestCase
from accounting import budget_actuals_preparations as preparations
from accounting import budget_actuals_certifications as certifications
from accounting import budget_native_actuals as actuals
from accounting import budget_receipt_sources as receipts
from accounting import budget_receipt_attributions as receipt_reviews
from accounting import budget_attributions as expense_reviews, budget_native_sources as ledger
from accounting import summary_actuals
from accounting.cash_classifications import checksum
from accounting.summary_actuals import RECEIPTS, EXPENDITURES
from accounting.models import LedgerAccount, JournalEntry, JournalLine, AccountingPeriod
from accounting.services import submit_entry, post_entry
from accounting.test_summary_actuals import SummaryActualTests
from reporting.models import FinanceStatementMapping as Mapping, FinanceStatementLine as MappingLine
from reporting.statement_services import submit_statement_mapping, review_statement_mapping
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from .test_office_forms import OfficeFormTests
from .test_actuals_selection import ActualsSelectionTests
from . import office_forms, summary_reconciliations as service, summary_sources
from .form1_integrity import _scope


class NativeSummaryReconciliationFixture(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(OfficeFormTests.setUpTestData.__func__)
    employee = classmethod(OfficeFormTests.employee.__func__)
    for name in ('make_call', 'make_version', 'add_line', 'add_ceiling', 'grant', 'attribute_grant',
        'journal', 'capture', 'rows', 'propose', 'review', 'native_grant', 'native_propose',
        'decide', 'choose', 'document', 'arguments', 'adopt'):
        locals()[name] = getattr(ActualsSelectionTests, name)
    complete_proposal = OfficeFormTests.complete_proposal
    form_args = OfficeFormTests.form_args

    def setUp(self):
        super().setUp()
        ActualsSelectionTests.setUp(self)
        self.prepare_resources()
        self.version.refresh_from_db()
        self.complete_proposal()
        self.form = office_forms.decide(item=office_forms.prepare(**self.form_args()),
            actor=self.reviewer, issue=True, note='Independent complete synthetic office issue')
        self.configure_sources()

    def prepare_resources(self):
        """Optional planning-source setup before the proposal is frozen."""
        pass

    def configure_sources(self):
        from departments.models import Department
        self.treasury = Department.objects.create(name='Synthetic joint Treasury', slug='native-joint-treasury')
        self.treasurer = self.employee(self.treasury, 'native.joint.treasurer')
        for actor, codes in ((self.maker, ['prepare_native_budget_actuals', 'view_native_budget_actuals',
            'prepare_budget_receipt_attributions', 'view_budget_receipt_attributions', 'view_budget_summary_actuals',
            'prepare_budget_summary_actuals']), (self.checker, ['review_native_budget_actuals',
            'view_native_budget_actuals', 'certify_accountant_native_budget_actuals',
            'review_budget_receipt_attributions', 'view_budget_receipt_attributions', 'view_budget_summary_actuals',
            'review_budget_summary_actuals']), (self.preparer, ['view_native_budget_actuals', 'export_native_budget_actuals', 'view_budget_summary_actuals']),
            (self.reviewer, ['view_native_budget_actuals', 'view_budget_summary_actuals']),
            (self.treasurer, ['view_native_budget_actuals', 'certify_treasurer_native_budget_actuals'])):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting', codename__in=codes))
        for actor, code in ((self.maker, 'manage_report_definitions'), (self.checker, 'approve_reports')):
            actor.user_permissions.add(Permission.objects.get(content_type__app_label='reporting', codename=code))
        cash = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='NATIVE-SYN-CASH', title='Synthetic reviewed cash scope',
            account_type='asset', normal_balance='debit')
        mapping = Mapping.objects.create(department=self.accounting_office, statement_type=Mapping.CASH_FLOW,
            version=1, title='Synthetic whole Fund cash inventory', authority_reference='Synthetic cash authority',
            local_acceptance_note='Synthetic reviewed source scope', created_by=self.maker)
        MappingLine.objects.create(mapping=mapping, position=1, section_code='cash', section_title='Cash',
            line_code='cash', line_title='Cash', selector_type=MappingLine.ACCOUNT_CODES, account_codes=[cash.code])
        submit_statement_mapping(mapping, self.maker)
        review_statement_mapping(mapping, self.checker, approve=True, note='Independent reviewed cash scope')
        owner = dict(department_id=self.accounting_office.pk, department_label=self.accounting_office.name)
        period = AccountingPeriod.objects.create(**owner, fiscal_year=2025, period_number=1,
            label='Synthetic opening period', starts_on=date(2025,1,1), ends_on=date(2025,1,31))
        opening = JournalEntry.objects.create(**owner, period=period, fund=self.fund,
            reference='SYN-OPENING-STOCK', entry_date=date(2025,1,1), description='Synthetic original opening cash stock',
            source_type='opening', created_by_id=self.maker.pk, created_by_label=self.maker.username)
        JournalLine.objects.create(entry=opening, sequence=1, account=cash, debit='50.00')
        JournalLine.objects.create(entry=opening, sequence=2, account=self.offset, credit='50.00')
        submit_entry(opening, self.maker); post_entry(opening, self.checker)
        prior_inventory = receipts.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2025,1,1), period_end=date(2025,12,31))
        prior_rows = [dict(line_id=line.pk, amount=str(line.debit+line.credit), disposition='exclude',
            purpose='opening', category='', basis='Retained original opening stock, not period receipts or expenses')
            for line in opening.lines.order_by('sequence')]
        batch = receipt_reviews.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2025,1,1), period_end=date(2025,12,31),
            expected_source_checksum=prior_inventory['source_checksum'],
            proposals=[dict(entry_id=opening.pk, expected_latest=0, rows=prior_rows)],
            reason='Explicit original opening exclusions', evidence_reference='Synthetic complete opening source review')
        receipt_reviews.review_batch(batch_id=batch.public_id, actor=self.checker, approve=True,
            note='Independent original opening stock verification')
        prior_ledger = ledger.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2025,1,1), period_end=date(2025,12,31))
        members = expense_reviews.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2025,1,1), period_end=date(2025,12,31), expected_source_checksum=prior_ledger['checksum'],
            proposals=[dict(entry_id=opening.pk, expected_latest=0,
                allocations=[{key:value for key,value in row.items() if key!='category'} for row in prior_rows])],
            reason='Opening stock is not expense activity', evidence_reference='Synthetic full opening expense exclusions')
        expense_reviews.review_batch(batch_id=members[0].batch_id, actor=self.checker, approve=True,
            note='Independent stock versus activity verification')
        inventory = receipts.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026,1,1), period_end=date(2026,6,30))
        batch = receipt_reviews.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026,1,1), period_end=date(2026,6,30), expected_source_checksum=inventory['source_checksum'],
            proposals=[dict(entry_id=self.entry.pk, expected_latest=0, rows=[dict(line_id=line.pk,
                amount=str(line.debit+line.credit), disposition='exclude', purpose='counterpart', category='',
                basis='Accepted supplies expense/equity counterpart is not a receipt')
                for line in self.entry.lines.order_by('sequence')])],
            reason='Explicit whole journal receipt exclusions', evidence_reference='Synthetic independent receipt coverage')
        receipt_reviews.review_batch(batch_id=batch.public_id, actor=self.checker, approve=True,
            note='Verified original expense source exclusion')
        self.prior = self.make_actuals(2025, 12)
        self.half = self.make_actuals(2026, 6)

    def make_actuals(self, year, month, *, certify=True, expected_latest=0,
                     entity_key='general', entity_label='Synthetic General Fund'):
        start, end = date(year,1,1), date(year,month,30 if month==6 else 31)
        captured = actuals.capture(actor=self.maker, fund_id=self.fund.pk, period_start=start, period_end=end)
        body = actuals.verify(captured)
        active_receipts = {row['allocation']['category'] for row in body['receipts']['payload']['bridge']
            if row['allocation']['disposition']=='include'}
        expense_total = sum((Decimal(row['amount']) for row in body['expenditures']['payload']['rows']), Decimal('0.00'))
        record = preparations.prepare(actor=self.maker, fund_id=self.fund.pk,
            budget_department_id=self.budget_office.pk, treasury_department_id=self.treasury.pk,
            period_start=start, period_end=end, expected_latest=expected_latest,
            expected_source_checksum=captured['source_checksum'], reference=f'Synthetic native {year}-{month}',
            authority='Synthetic complete Fund reporting designation', reason='Retain exact complete category coverage',
            entity=dict(key=entity_key, label=entity_label, full_fund=True,
                basis='Synthetic complete Fund/entity and explicit zero-activity verification'),
            class_mappings=[dict(expense_class=row['expense_class'], category='mooe', basis='Explicit MOOE designation')
                for row in body['expenditures']['payload']['rows']],
            receipt_rows=[dict(category=key, amount=body['receipts']['payload']['category_totals'][key],
                coverage='activity' if key in active_receipts else 'no_activity', basis='Verified complete source inventory')
                for key in RECEIPTS],
            expenditure_rows=[dict(category=key, amount=str(expense_total) if key=='mooe' else '0.00',
                coverage='activity' if key=='mooe' and body['expenditures']['payload']['rows'] else 'no_activity',
                basis='Verified original reviewed expenses and explicit no-activity leaves') for key in EXPENDITURES])
        if certify:
            record = preparations.review(preparation_id=record.pk, actor=self.checker, approve=True,
                authority='Independent category designation', note='Verified complete entity and category coverage')
            for role, actor in (('accountant', self.checker), ('treasurer', self.treasurer)):
                certifications.decide(preparation_id=record.pk, actor=actor, role=role, certify=True,
                    authority='Synthetic designated '+role, note='Verified full source cohort and Fund trial balance')
        return record

    def args(self, **changes):
        args = dict(proposal=self.version, actor=self.preparer, prior_id=self.prior.public_id,
            half_id=self.half.public_id, prior_route='native', half_route='native',
            form_ids=[self.form.public_id], expected_offices=[self.form.office_id], entity_key='general',
            coverage_reference='Synthetic complete entity/office designation', expected_latest=0)
        args.update(changes)
        return args

    def accept(self, record, **changes):
        args = dict(actor=self.reviewer, accept=True, note='Verified both periods and complete source versions',
            authority='Independent Budget reconciliation designation')
        args.update(changes)
        return service.review(record, **args)

class NativeSummaryReconciliationTests(NativeSummaryReconciliationFixture):
    def test_native_both_periods_pure_retention_http_and_no_duplicate_posting(self):
        before = JournalEntry.objects.count()
        record = service.prepare(**self.args())
        self.assertEqual(record.payload['schema'], 3)
        self.assertEqual(record.payload['comparisons']['half']['difference'], '0.00')
        self.assertEqual(len(record.payload['actuals']['half']['payload']['rows']), 26)
        with self.assertNumQueries(0, using='finance'), self.assertNumQueries(0, using='default'):
            service.verify(record)
        self.accept(record)
        self.client.force_login(self.preparer)
        detail = self.client.get(reverse('budget:summary_reconciliation_detail', args=[record.public_id]))
        self.assertContains(detail, reverse('accounting:native_actuals_detail', args=[self.half.public_id]))
        url = reverse('budget:summary_reconciliation_prepare', args=[self.version.public_id])
        page = self.client.get(url)
        response = self.client.post(url, dict(preview=page.context['form']['preview'].value(),
            prior='native:'+str(self.prior.public_id), half='native:'+str(self.half.public_id),
            office_forms=[self.form.pk], expected_offices=[self.form.office_id], complete='on',
            coverage_reference='Synthetic complete office inventory'))
        self.assertEqual(response.status_code, 302)
        exported = self.client.get(reverse('budget:summary_reconciliation_export', args=[record.public_id]))
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(json.loads(exported.content)['payload']['actuals']['half']['snapshot'],
            record.payload['actuals']['half']['snapshot'])
        self.assertEqual(JournalEntry.objects.count(), before)

    def test_stale_native_source_blocks_new_use_and_acceptance_but_retains_return(self):
        record = service.prepare(**self.args())
        original = deepcopy(record.payload)
        self.journal('NATIVE-RECON-LATER', date(2026,6,30), Decimal('5'))
        with self.assertRaisesMessage(ValidationError, 'stale'): self.accept(record)
        with self.assertRaisesMessage(ValidationError, 'stale'):
            service.prepare(**self.args(expected_latest=1))
        returned = self.accept(record, accept=False, note='Actual new posting requires a complete successor')
        self.assertEqual(service.verify(returned), original)

    def test_source_read_export_authority_is_rechecked_for_retained_native_evidence(self):
        record = service.prepare(**self.args())
        self.client.force_login(self.preparer)
        detail = reverse('budget:summary_reconciliation_detail', args=[record.public_id])
        export = reverse('budget:summary_reconciliation_export', args=[record.public_id])
        read_permission = Permission.objects.get(content_type__app_label='accounting', codename='view_native_budget_actuals')
        export_permission = Permission.objects.get(content_type__app_label='accounting', codename='export_native_budget_actuals')
        self.preparer.user_permissions.remove(read_permission)
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.assertEqual(self.client.get(export).status_code, 200)
        self.preparer.user_permissions.remove(export_permission)
        self.assertEqual(self.client.get(export).status_code, 403)
        self.preparer.user_permissions.add(read_permission)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.get(export).status_code, 403)
        self.reviewer.user_permissions.remove(read_permission)
        with self.assertRaises(PermissionDenied): self.accept(record, accept=False)
        record.refresh_from_db(); self.assertEqual(record.status, 'prepared')

    def test_latest_preparation_office_scope_uat_and_rehashed_tamper_guards(self):
        record = service.prepare(**self.args())
        for mutation in ('amount', 'role', 'route', 'id'):
            shadow = copy(record); shadow.payload = deepcopy(record.payload)
            source = shadow.payload['actuals']['half']
            if mutation=='amount': source['payload']['rows'][0]['amount']='200.00'
            elif mutation=='role': source['snapshot']['payload']['decisions'][0]['payload']['identity']['actor_id']=self.maker.pk
            elif mutation=='route': source['route']='combined'
            else: source['id']=str(self.prior.public_id)
            source['payload_checksum']=checksum(source['payload'])
            shadow.payload_checksum=checksum(shadow.payload)
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError): service.verify(shadow)
        with self.assertRaises(ValidationError): service.prepare(**self.args(half_route='guessed'))
        with self.assertRaises(ValidationError): service.prepare(**self.args(half_id=self.prior.public_id))
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied): self.accept(record)
        self.reviewer.groups.clear()
        pending = self.make_actuals(2026,6,certify=False,expected_latest=1)
        with self.assertRaisesMessage(ValidationError, 'jointly certified'):
            summary_sources.capture(actor=self.preparer, budget_department_id=self.budget_office.pk,
                identity=pending.public_id, route='native')
        with self.assertRaisesMessage(ValidationError, 'stale'): self.accept(record)
        self.accept(record, accept=False)
        with self.assertRaises(ValidationError): summary_sources.capture(actor=self.preparer,
            budget_department_id=self.requesting_office.pk, identity=self.half.public_id, route='native')

    def test_newer_office_version_requires_new_issued_selection_and_mixed_routes(self):
        record = service.prepare(**self.args())
        newer = office_forms.prepare(**self.form_args(expected_latest=1))
        with self.assertRaisesMessage(ValidationError, 'newer office'): self.accept(record)
        self.accept(record, accept=False)
        newer = office_forms.decide(item=newer, actor=self.reviewer, issue=True, note='Independent successor issue')
        receipt = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='SYN-NATIVE-EXTERNAL', title='Synthetic historical receipt',
            account_type='revenue', normal_balance='credit')
        from types import SimpleNamespace
        fixture = SimpleNamespace(maker=self.maker, fund=self.fund, budget_office=self.budget_office,
            operating_office=self.treasury, receipt_account=receipt, account=self.account,
            document=SummaryActualTests().document)
        args = SummaryActualTests.arguments(fixture, period_start=date(2025,1,1), period_end=date(2025,12,31),
            receipt_total='0', expenditure_total='0', rows=[
                dict(kind='receipt', category='service', account_id=None, amount='0', source_row='explicit zero R'),
                dict(kind='expenditure', category='mooe', account_id=None, amount='0', source_row='explicit zero E')])
        historical = summary_actuals.review(summary_actuals.propose(**args), self.checker, approve=True,
            note='Verified original synthetic certificate', authority='Independent adoption designation', verified_documents=True)
        mixed = service.prepare(**self.args(prior_id=historical.public_id, prior_route='historical',
            expected_latest=1, form_ids=[newer.public_id]))
        self.assertEqual(mixed.payload['actuals']['prior']['route'], 'historical')
        self.assertEqual(mixed.payload['actuals']['half']['route'], 'native')
        self.assertEqual(self.accept(mixed).status, 'accepted')

    def test_native_source_projection_retains_exact_verified_scope_rows_and_totals(self):
        source = summary_sources.capture(actor=self.preparer,
            budget_department_id=self.budget_office.pk, identity=self.half.public_id, route='native')
        original = deepcopy(source)
        with _scope(), self.assertNumQueries(0, using='finance'), self.assertNumQueries(0, using='default'):
            self.assertEqual(summary_sources.verify(source), source['payload'])
            self.assertEqual(summary_sources.project_native(source['snapshot']), source['payload'])
            same = deepcopy(source)
            self.assertIs(summary_sources.verify(same), same['payload'])
            for mutation in ('scope', 'rows', 'totals', 'snapshot', 'tuple_rows'):
                shadow = deepcopy(source)
                if mutation == 'scope':
                    shadow['payload']['scope']['treasury_department_id'] = self.budget_office.pk
                elif mutation == 'rows':
                    shadow['payload']['rows'].reverse()
                elif mutation == 'totals':
                    shadow['payload']['totals']['receipt'] = '123.00'
                elif mutation == 'snapshot':
                    shadow['snapshot']['payload']['original_preparation']['identity']['entity_label'] = 'Changed retained entity'
                else:
                    shadow['payload']['rows'] = tuple(shadow['payload']['rows'])
                shadow['payload_checksum'] = checksum(shadow['payload'])
                with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                    summary_sources.verify(shadow)
            same['payload']['scope']['entity_label'] = 'Changed caller copy'
        self.assertEqual(source, original)

    def test_native_projection_and_source_reject_genuine_pending_successor(self):
        source = summary_sources.capture(actor=self.preparer,
            budget_department_id=self.budget_office.pk, identity=self.half.public_id, route='native')
        pending = self.make_actuals(2026, 6, certify=False, expected_latest=1)
        captured = certifications.snapshot(pending, self.preparer)
        shadow = deepcopy(source)
        shadow.update(id=str(pending.public_id), snapshot=captured)
        for operation in (lambda: summary_sources.project_native(captured),
                          lambda: summary_sources.verify(shadow)):
            with self.assertRaisesMessage(ValidationError, 'jointly certified'):
                operation()
        self.assertEqual(summary_sources.verify(source), source['payload'])
