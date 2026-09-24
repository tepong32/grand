"""Historical observation probe, not an application-correctness regression.

Use only a fresh two-store Django test runner and the exact test label documented
in docs/FINANCE_BUDGET_NATIVE_SOURCE_AUDIT.md. The expected missing attribution
describes v0.7.151; future repairs should not preserve it to keep this probe green.
"""
import json
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.utils import timezone
from accounting.models import FiscalYear, JournalEntry, JournalLine, LedgerAccount
from accounting.services import submit_entry, post_entry
from budget.models import BudgetCall, BudgetVersion, BudgetProposalLine
from budget.planning_context import build_context
from finance.models import FinanceConfigurationItem
from vouchers.test_advance_refunds import AdvanceRefundTests
from vouchers.advance_applications import prepare, materialize, reconcile
from vouchers.collections import record_deposit


class NativeActualSourceProbe(AdvanceRefundTests):
    @classmethod
    def setUpClass(cls):
        clock = patch('django.utils.timezone.now', return_value=datetime(2026,9,25,3,tzinfo=dt_timezone.utc))
        clock.start()
        cls.addClassCleanup(clock.stop)
        super().setUpClass()

    def test_posted_sources_and_missing_office_context(self):
        self.accounting_center.office_id = self.requesting.pk
        self.accounting_center.save(update_fields=['office_id'])
        detail, cash = self.refund_setup()
        request = prepare(detail=detail, actor=self.preparer, rule=self.liquidation_rule(), day=timezone.localdate(),
            expenses=[{'account_code': self.expense_account.code, 'amount': '200', 'document_reference': 'SYN-EXPENSE'}],
            evidence_reference='SYN-LIQUIDATION', key='native-actual-audit')
        expense, _ = materialize(request, self.preparer)
        submit_entry(expense, self.preparer)
        post_entry(expense, self.validator)
        expense.refresh_from_db()
        reconcile(expense, self.validator)
        receipt = self.capture_refund(detail, amount='100')
        self.post_refund_source(receipt)
        bank = FinanceConfigurationItem.objects.get(release=self.release, category='bank_account', code='gf-lbp')
        deposit = record_deposit(actor=self.treasury_user, variant=self.transaction_variant, deposited_on=timezone.localdate(),
            fund_code='general-fund', deposit_reference='SYN-REFUND-DEPOSIT', receiving_bank_id=bank.public_id,
            allocations=[{'receipt': str(receipt.public_id), 'amount': '100'}], evidence_reference='SYN-BANK-RECEIPT')
        self.post_refund_source(deposit)
        owner = {'department_id': self.accounting.pk, 'department_label': self.accounting.name}
        capital = LedgerAccount.objects.create(**owner, code='SYN-PPE', title='Synthetic equipment',
            account_type='asset', normal_balance='debit')
        equipment = JournalEntry.objects.create(**owner, fund=self.accounting_fund, period=self.accounting_period,
            reference='SYN-CAPITAL', entry_date=date(2026, 8, 25), description='Synthetic equipment recognition',
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username)
        JournalLine.objects.create(entry=equipment, sequence=1, account=capital, responsibility_center=self.accounting_center, debit=500)
        JournalLine.objects.create(entry=equipment, sequence=2, account=self.payable_account, credit=500)
        submit_entry(equipment, self.preparer)
        post_entry(equipment, self.validator)
        year = FiscalYear.objects.create(**owner, year=2028, label='Synthetic 2028 planning',
            starts_on=date(2028,1,1), ends_on=date(2028,12,31), business_date=date(2028,1,1))
        budget_owner = {'department_id': self.budget.pk, 'department_label': self.budget.name}
        call = BudgetCall.objects.create(**budget_owner, fiscal_year=year, title='Synthetic native audit',
            authority_reference='SYNTHETIC ONLY', instructions='Source audit only',
            proposal_opens_on=date(2027,8,1), proposal_due_on=date(2027,9,30),
            created_by_id=self.budget_user.pk, created_by_label=self.budget_user.username)
        version = BudgetVersion.objects.create(**budget_owner, budget_call=call, fiscal_year=year,
            title='Synthetic source audit', requesting_department_id=self.requesting.pk,
            requesting_department_label=self.requesting.name, change_explanation='Synthetic audit',
            created_by_id=self.budget_user.pk, created_by_label=self.budget_user.username)
        for account, expense_class in [(self.expense_account, 'MOOE'), (capital, 'CO')]:
            BudgetProposalLine.objects.create(**budget_owner, version=version, fund=self.accounting_fund,
                responsibility_center=self.accounting_center, account=account, expense_class=expense_class,
                particulars='Synthetic proposal', amount=1000)
        self.budget_user.user_permissions.add(Permission.objects.get(content_type__app_label='budget', codename='prepare_budget_proposals'))
        with patch('django.utils.timezone.localdate', return_value=date(2027,8,1)):
            context = build_context(version, self.budget_user)
        lines = list(JournalLine.objects.filter(entry__department_id=self.accounting.pk, entry__status='posted')
            .select_related('entry', 'account').order_by('entry_id', 'sequence'))
        source_rows = [{'journal': str(row.entry.public_id), 'reference': row.entry.reference,
            'date': row.entry.entry_date.isoformat(), 'source_type': row.entry.source_type,
            'source_keys': sorted(row.entry.source_snapshot), 'line': row.pk, 'account': row.account.code,
            'account_type': row.account.account_type, 'center_id': row.responsibility_center_id,
            'debit': str(row.debit), 'credit': str(row.credit)} for row in lines]
        expense_sum = sum((row.debit-row.credit for row in lines if row.account.account_type == 'expense'), Decimal('0'))
        naive_sum = sum((row.debit for row in lines if row.account.account_type in ('expense', 'asset')), Decimal('0'))
        self.assertEqual(expense_sum, Decimal('200'))
        self.assertEqual(naive_sum, Decimal('1900'))
        self.assertIsNone(expense.lines.get(account=self.expense_account).responsibility_center_id)
        self.assertTrue(all(row['prior_amount'] is None for row in context['rows']))
        observation = {'basis_commit': '1d289b58b070a21e044c5249a2820131a1172c60',
            'meaning': 'Observed source coverage gaps; passing probe is not application correctness or certification',
            'actual_expense_debit': str(expense_sum), 'naive_expense_plus_asset_debits': str(naive_sum),
            'advance_original_debit': str(detail.debit), 'accepted_expense': '200.00',
            'refund': '100.00', 'deposit': '100.00', 'capital_candidate_debit': '500.00',
            'proposal_context': context, 'posted_source_lines': source_rows}
        target = Path(__file__).resolve().parents[2] / '.tmp/native-budget-source-audit.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(observation, indent=2), encoding='utf-8')
        print('SOURCE AUDIT:', target, 'expense=200.00; naive=1900.00; office comparison=missing', flush=True)
