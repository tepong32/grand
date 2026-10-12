from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test.utils import CaptureQueriesContext

from . import budget_native_actuals as service, budget_attributions as expense_reviews
from . import budget_native_sources as sources
from . import test_budget_receipt_cohorts as fixtures
from .cash_classifications import checksum
from vouchers.collections import record_receipt
from . import budget_actuals_coverage as coverage
from .summary_actuals import RECEIPTS, EXPENDITURES
from .models import LedgerAccount, ResponsibilityCenter, JournalEntry, JournalLine, AccountingPeriod
from .services import submit_entry, post_entry
from . import budget_receipt_partitions as partitions


class NativeActualsPreparationTests(fixtures.ReceiptCohortTests):
    def setUp(self):
        super().setUp()
        self.preparer.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=['view_native_budget_statements', 'prepare_budget_attributions', 'view_budget_attributions']))
        self.validator.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=['review_budget_attributions', 'view_budget_attributions']))

    def actuals(self, **changes):
        args = dict(actor=self.preparer, fund_id=self.receipt_fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
        args.update(changes)
        return service.capture(**args)

    def exclude_collection_expenditures(self, entries, *, included=None):
        captured = sources.capture(actor=self.preparer, fund_id=self.receipt_fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
        selected = {row['id']: row for row in captured['payload']['journals']}
        proposals = []
        for entry in entries:
            rows = [dict(line_id=line['id'], amount=str(Decimal(line['debit']) + Decimal(line['credit'])),
                disposition='exclude', purpose='counterpart', basis='Synthetic collection or bank transfer; no expense recognition')
                for line in selected[entry.pk]['lines']]
            if included and entry.pk == included[0]:
                rows[0].update(disposition='include', purpose='expense_recognition',
                    center_id=included[1], expense_class='Local office MOOE')
            proposals.append(dict(entry_id=entry.pk, expected_latest=0, allocations=rows))
        records = expense_reviews.propose_batch(actor=self.preparer, fund_id=self.receipt_fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
            expected_source_checksum=captured['checksum'], proposals=proposals,
            reason='Synthetic complete expense exclusions', evidence_reference='Synthetic source review')
        expense_reviews.review_batch(batch_id=records[0].batch_id, actor=self.validator,
            approve=True, note='Independent collection and transfer exclusions')

    def test_same_read_full_bridge_and_independent_exclusions_remain_uncertified(self):
        _, original, _, deposit, _ = self.reviewed_originals()
        self.exclude_collection_expenditures([original, deposit])
        with CaptureQueriesContext(connections['finance']) as queries:
            captured = self.actuals()
        self.assertEqual(len([row for row in queries if 'posting_evidence' in row['sql'] and 'accounting_fund' in row['sql']]), 1)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            body = service.verify(captured)
        self.assertTrue(body['classification_complete'])
        self.assertEqual(body['receipts']['payload']['classified_receipts'], '100.00')
        self.assertEqual(body['expenditures']['payload']['total'], '0.00')
        self.assertEqual(len(body['expenditures']['payload']['bridge']), 4)
        self.assertEqual(body['expenditure_source']['payload'], sources.capture(actor=self.preparer,
            fund_id=self.receipt_fund.pk, period_start=date(2026,9,1), period_end=date(2026,9,30))['payload'])
        self.assertIsNone(body['receipt_total']); self.assertIsNone(body['expenditure_total'])
        self.assertEqual(body['certification_status'], 'not_certified')
        self.assertTrue(service.is_current(captured, self.preparer))

    def test_correction_period_excludes_predecessor_activity_and_missing_expense_reviews(self):
        _, children, _ = self.corrected_originals()
        captured = self.actuals(period_start=date(2026,9,13))
        body = service.verify(captured)
        self.assertTrue(body['receipts']['payload']['classification_complete'])
        self.assertFalse(body['classification_complete'])
        self.assertEqual(body['receipts']['payload']['classified_receipts'], '-100.00')
        self.assertEqual(body['expenditure_source']['payload']['controls']['lines'], 4)
        self.assertEqual({row['entry_id'] for row in body['expenditures']['payload']['bridge']}, {child.pk for child,_ in children})
        self.assertIsNone(body['expenditure_total'])

    def test_both_permissions_tamper_and_later_post_preserve_old_preparation(self):
        receipt, original, _, deposit, _ = self.reviewed_originals()
        self.exclude_collection_expenditures([original, deposit])
        captured = self.actuals(); frozen = deepcopy(captured)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',
            codename='view_native_budget_statements'))
        # Discard Django's permission cache after an explicit test authority change.
        for name in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
            self.preparer.__dict__.pop(name, None)
        with self.assertRaises(PermissionDenied): self.actuals()
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='view_native_budget_statements'))
        for name in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
            self.preparer.__dict__.pop(name, None)
        altered = deepcopy(captured); altered['payload']['receipt_total'] = '100.00'
        altered['checksum'] = checksum(altered['payload'])
        with self.assertRaises(ValidationError): service.verify(altered)
        # A later ordinary receipt changes sources; it must not rewrite this artifact.
        later = record_receipt(actor=self.treasury_user, variant=self.transaction_variant,
            received_on=date(2026,9,14), fund_code='general-fund', receipt_book='SYNTHETIC-BOOK',
            receipt_number='002', payer_reference='Synthetic second payer', received_amount='100',
            evidence_reference='Synthetic later collection')
        self.post_source(later)
        self.assertFalse(service.is_current(captured, self.preparer))
        self.assertEqual(captured, frozen)
        self.assertEqual(service.verify(captured), frozen['payload'])

    def coverage_args(self, captured):
        body = service.verify(captured)
        amounts = body['receipts']['payload']['category_totals']
        return dict(entity=dict(key='general', label='Synthetic General Fund', full_fund=True,
            basis='Explicit full Fund boundary for this synthetic entity'), class_mappings=[],
            receipt_rows=[dict(category=key, amount=amounts[key],
                coverage='activity' if key in ('service','regulatory') else 'no_activity',
                basis='Synthetic complete category review') for key in RECEIPTS],
            expenditure_rows=[dict(category=key, amount='0.00', coverage='no_activity',
                basis='Reviewed collection and transfer exclusions') for key in EXPENDITURES])

    def test_real_expense_and_explicit_category_mapping_full_entity_proposal(self):
        _, original, _, deposit, _ = self.reviewed_originals()
        owner = dict(department_id=self.accounting.pk, department_label=self.accounting.name)
        expense = LedgerAccount.objects.create(**owner, code='ACT-EXP', title='Synthetic supplies expense',
            account_type='expense', normal_balance='debit')
        payable = LedgerAccount.objects.create(**owner, code='ACT-PAY', title='Synthetic payable',
            account_type='liability', normal_balance='credit')
        center = ResponsibilityCenter.objects.create(**owner, code='ACT-OFFICE', name='Synthetic office',
            office_id=self.accounting.pk)
        entry = JournalEntry.objects.create(**owner, fund=self.receipt_fund,
            period=AccountingPeriod.objects.get(department_id=self.accounting.pk, fiscal_year=2026, period_number=9),
            reference='ACT-SUPPLIES', entry_date=date(2026,9,14), description='Synthetic accepted supplies accrual',
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=entry, sequence=1, account=expense, responsibility_center=center, debit='75.00')
        JournalLine.objects.create(entry=entry, sequence=2, account=payable, credit='75.00')
        submit_entry(entry,self.preparer); post_entry(entry,self.validator)
        inventory = self.inventory()
        self.decide(fixtures.reviews.propose_batch(**self.args([self.member_args(inventory,entry,receipt=False)])))
        self.exclude_collection_expenditures([original,deposit,entry],included=(entry.pk,center.pk))
        captured = self.actuals(); args = self.coverage_args(captured)
        with self.assertRaises(ValidationError): coverage.propose(captured,**args)
        args['class_mappings']=[dict(expense_class='Local office MOOE', category='mooe',
            basis='Explicit office-approved Form 1 category mapping')]
        next(row for row in args['expenditure_rows'] if row['category']=='mooe').update(amount='75.00',coverage='activity')
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            proposal=coverage.propose(captured,**args)
            body=coverage.verify(proposal)
        self.assertEqual(len(body['receipt_rows']),21); self.assertEqual(len(body['expenditure_rows']),5)
        self.assertEqual(body['review_status'],'not_reviewed'); self.assertIsNone(body['receipt_total'])
        self.assertIsNone(body['expenditure_total']); self.assertEqual(body['certification_status'],'not_certified')

    def test_coverage_rejects_omissions_unknown_entity_wrong_zero_and_rehashed_certification(self):
        _,original,_,deposit,_=self.reviewed_originals()
        self.exclude_collection_expenditures([original,deposit]); captured=self.actuals()
        args=self.coverage_args(captured); proposal=coverage.propose(captured,**args)
        variants=[]
        missing=deepcopy(args); missing['receipt_rows'].pop(); variants.append(missing)
        duplicate=deepcopy(args); duplicate['receipt_rows'][-1]=duplicate['receipt_rows'][0]; variants.append(duplicate)
        subtotal=deepcopy(args); subtotal['receipt_rows'][0]['category']='total'; variants.append(subtotal)
        zero=deepcopy(args); next(row for row in zero['receipt_rows'] if row['category']=='service')['coverage']='no_activity'; variants.append(zero)
        wrong=deepcopy(args); wrong['expenditure_rows'][0]['amount']='0.001'; variants.append(wrong)
        entity=deepcopy(args); entity['entity']['full_fund']=False; variants.append(entity)
        extra=deepcopy(args); extra['entity']['key']='inferred_from_fund'; variants.append(extra)
        for variant in variants:
            with self.assertRaises(ValidationError): coverage.propose(captured,**variant)
        tampered=deepcopy(proposal); tampered['payload']['certification_status']='certified'
        tampered['checksum']=checksum(tampered['payload'])
        with self.assertRaises(ValidationError): coverage.verify(tampered)
        missing=self.actuals(period_start=date(2026,9,15))
        with self.assertRaises(ValidationError): coverage.propose(missing,**args)

    def test_legacy_partition_fingerprint_retained_while_new_schema_ignores_only_expense_head(self):
        _, original, _, deposit, _ = self.reviewed_originals()
        inventory = self.inventory()
        new = partitions.propose(inventory, original.pk, self.rows(inventory, original.pk, receipt=True))
        _, entry, _ = partitions.entry_source(inventory, original.pk)
        legacy = deepcopy(new)
        legacy['payload'].update(schema=1, source_checksum=checksum(entry))
        legacy['checksum']=checksum(legacy['payload'])
        frozen=deepcopy(legacy)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            partitions.verify(inventory,legacy)
        self.exclude_collection_expenditures([original,deposit])
        fresh=self.inventory()
        partitions.verify(fresh,new)
        with self.assertRaises(ValidationError): partitions.verify(fresh,legacy)
        self.assertEqual(legacy,frozen)
        partitions.verify(inventory,legacy)
        altered=deepcopy(fresh)
        # Financial evidence remains part of the new fingerprint.
        altered['payload']['ledger']['payload']['journals'][0]['description']='Changed source'
        with self.assertRaises(ValidationError): partitions.verify(altered,new)
