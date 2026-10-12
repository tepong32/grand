from copy import deepcopy

from django.core.exceptions import ValidationError
from django.urls import reverse

from accounting.cash_classifications import checksum
from accounting.models import LedgerAccount, ResponsibilityCenter
from .actuals_selection import _source, preview_sources
from .models import BudgetVersion
from .planning_context import build_context, displayed_context
from .services import transition_version
from .test_actuals_selection import ActualsSelectionTests


class CompleteScopeSelectionTests(ActualsSelectionTests):
    def new_proposal_account(self):
        other = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='FUTURE-ONLY',
            title='Synthetic new proposal account', account_type='expense', normal_balance='debit')
        self.line.account = other
        self.line.save(update_fields=('account',))
        return other

    def key(self):
        return f'{self.fund.pk}:{self.center.pk}:half'

    def screen(self):
        self.client.force_login(self.preparer)
        return self.client.get(reverse('budget:actuals_sources', args=[self.version.public_id]),
                               {'scope': self.key()})

    def test_native_history_without_proposal_is_visible_selected_and_retained(self):
        self.new_proposal_account()
        page = self.screen()
        self.assertContains(page, self.account.title)
        self.assertContains(page, 'No proposal line in this scope')
        candidate = next(item for item in page.context['candidates'] if item['kind'] == 'native')
        self.choose(expected_rows_checksum=candidate['rows_checksum'])
        choice = deepcopy(self.version.actuals_source_selection[self.key()])
        self.assertEqual(choice['coverage_mode'], 'complete_scope')
        self.assertEqual([row['account_id'] for row in choice['rows']], [self.account.pk])
        self.assertEqual(choice['rows'][0]['account_title'], self.account.title)
        self.assertEqual(choice['rows'][0]['amount'], '100.00')
        self.assertIsNone(build_context(self.version, self.preparer)['rows'][0]['half_certified'])
        self.version = transition_version(self.version, 'submit', self.preparer)
        frozen = deepcopy(displayed_context(self.version, self.preparer))
        self.assertContains(self.screen(), self.account.title)
        self.version.refresh_from_db()
        self.assertEqual(self.version.actuals_source_selection[self.key()], choice)
        self.assertEqual(displayed_context(self.version, self.preparer), frozen)

    def test_external_only_historical_accounts_are_candidates_with_retained_names(self):
        adopted = self.adopt('140')
        original_title = self.account.title
        self.new_proposal_account()
        self.account.title = 'Later account catalog label'
        self.account.save(update_fields=('title',))
        page = self.screen()
        candidate = next(item for item in page.context['candidates'] if item['kind'] == 'external')
        self.assertEqual(candidate['rows'][0]['account_title'], original_title)
        self.choose(kind='external', source_id=adopted.public_id,
                    expected_rows_checksum=candidate['rows_checksum'])
        self.assertEqual(self.version.actuals_source_selection[self.key()]['rows'][0]['amount'], '140.00')
        self.assertIsNone(build_context(self.version, self.preparer)['rows'][0]['half_certified'])

    def test_legacy_native_choice_reproduces_original_shape(self):
        rows = _source(self.version, self.fund.pk, self.center.pk, 'half', 'native', self.native.public_id)
        self.choose()
        choice = deepcopy(self.version.actuals_source_selection[self.key()])
        choice.pop('coverage_mode')
        choice.update(rows=rows, rows_checksum=checksum(rows))
        BudgetVersion.objects.filter(pk=self.version.pk).update(actuals_source_selection={self.key(): choice})
        self.version.refresh_from_db()
        before = deepcopy(self.version.actuals_source_selection)
        actual = build_context(self.version, self.preparer)['rows'][0]['half_certified']
        self.assertEqual(actual['amount'], '100.00')
        self.assertNotIn('account_title', actual)
        self.version.refresh_from_db()
        self.assertEqual(self.version.actuals_source_selection, before)

    def test_native_scope_does_not_disclose_other_office_rows(self):
        other = ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='PRIVATE-OFFICE',
            name='Other office', office_id=self.budget_office.pk)
        rows = self.rows()
        rows[0]['amount'] = '60'
        rows.append(dict(rows[0], amount='40', center_id=other.pk))
        self.review(self.propose(proposals=[{'entry_id': self.entry.pk, 'expected_latest': 1, 'allocations': rows}]))
        self.native = self.decide(self.native_propose(expected_latest=1))
        self.new_proposal_account()
        self.choose()
        retained = self.version.actuals_source_selection[self.key()]['rows']
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]['amount'], '60.00')
        self.assertEqual(retained[0]['scope']['center_id'], self.center.pk)

    def test_preview_hash_includes_accounts_without_proposals(self):
        legacy = _source(self.version, self.fund.pk, self.center.pk, 'half', 'native', self.native.public_id)
        self.new_proposal_account()
        _, candidates, _ = preview_sources(self.version, self.preparer, self.fund.pk, self.center.pk, 'half')
        native = next(item for item in candidates if item['kind'] == 'native')
        self.assertNotEqual(native['rows_checksum'], checksum(legacy))
        with self.assertRaises(ValidationError):
            self.choose(expected_rows_checksum=checksum([]))
        self.version.refresh_from_db()
        self.assertFalse(self.version.actuals_source_selection)
        self.choose(expected_rows_checksum=native['rows_checksum'])
