from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.models import LedgerAccount, JournalEntry
from accounting.cash_classifications import checksum
from . import test_receipt_forecast_reviews as fixtures
from . import form1_flows, form1_components, form1_account_proposals as service


class Form1AccountProposalFixture(fixtures.ReceiptForecastReviewFixture):
    def prepare_resources(self):
        fixtures.ReceiptForecastReviewFixture.prepare_resources(self)
        self.targets = {}
        for name, changes in (
            ('valid', {}), ('retired', dict(is_active=False, allow_posting=False)),
            ('late', dict(effective_from=date(2027, 7, 1))),
            ('expired', dict(effective_to=date(2025, 12, 31))),
        ):
            self.targets[name] = LedgerAccount.objects.create(
                department_id=self.accounting_office.pk, department_label=self.accounting_office.name,
                code='SYN-REPORT-'+name, title='Synthetic reporting target '+name,
                government_account_code='SYNTHETIC-'+name,
                account_type='revenue', normal_balance='credit', **changes)

    def setUp(self):
        super().setUp()
        approved = self.review_forecast(self.prepare_forecast())
        self.inventory = form1_components.inventory(form1_flows.capture(forecast=approved, actor=self.preparer))

    def account_allocations(self, target=None):
        return [dict(key='part-'+str(index), component=row['key'], amount=row['amount'],
            disposition='mapped' if target else 'unresolved', account_id=target.pk if target else None,
            basis='Synthetic selection only; no official code authority')
            for index, row in enumerate(self.inventory['payload']['components'])]

    def propose_accounts(self, rows):
        return service.propose(self.inventory, rows, coverage_reference='Synthetic draft coverage, pending Accounting authority')


class Form1AccountProposalTests(Form1AccountProposalFixture):
    def test_pure_complete_partitions_retain_original_accounts_without_approval_or_posting(self):
        before = JournalEntry.objects.count()
        original = deepcopy(self.inventory)
        rows = self.account_allocations(self.targets['valid'])
        first = rows.pop(0)
        value = Decimal(first['amount'])
        rows.extend([dict(first, key='split-a', amount=str(value/2)), dict(first, key='split-b', amount=str(value/2))])
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            body = service.verify(self.propose_accounts(rows))
        self.assertTrue(body['selection_complete'])
        for flag in ('independently_reviewed', 'code_authority_approved', 'form_issued'):
            self.assertFalse(body[flag])
        self.assertEqual(self.inventory, original)
        self.assertEqual(body['inventory'], original)
        self.assertTrue(all(row['account']['government_account_code']=='SYNTHETIC-valid' for row in body['allocations']))
        self.assertEqual(JournalEntry.objects.count(), before)
        self.assertFalse(service.verify(self.propose_accounts(self.account_allocations()))['selection_complete'])

    def test_exact_coverage_identity_sign_and_no_local_code_fallback(self):
        rows = self.account_allocations()
        malformed = [rows[:-1], rows+[deepcopy(rows[0])],
            [dict(rows[0], amount='-1')]+rows[1:],
            [dict(rows[0], amount='0')]+rows[1:],
            [dict(rows[0], component='invented')]+rows[1:],
            [dict(rows[0], disposition='mapped', account_id=self.revenue.pk)]+rows[1:],
            [dict(rows[0], disposition='mapped', account_id=987654321)]+rows[1:],
            [dict(rows[0], disposition='mapped', account_id=None)]+rows[1:],
            [dict(rows[0], account_id=self.targets['valid'].pk)]+rows[1:]]
        for candidate in malformed:
            with self.subTest(candidate=candidate[0]):
                with self.assertRaises(ValidationError): self.propose_accounts(candidate)

    def test_original_date_and_whole_forecast_interval_retirement_boundaries(self):
        rows = self.account_allocations()
        components = {row['key']:row for row in self.inventory['payload']['components']}
        actual = next(index for index,row in enumerate(rows) if components[row['component']]['identity']['source']['route']=='native')
        forecast = next(index for index,row in enumerate(rows) if components[row['component']]['identity']['column']=='proposed')
        historical = deepcopy(rows)
        historical[actual] = dict(rows[actual], disposition='mapped', account_id=self.targets['retired'].pk)
        self.propose_accounts(historical)
        for index,target in ((forecast,'retired'), (forecast,'late'), (actual,'expired')):
            changed = deepcopy(rows)
            changed[index] = dict(rows[index], disposition='mapped', account_id=self.targets[target].pk)
            with self.subTest(index=index,target=target):
                with self.assertRaises(ValidationError): self.propose_accounts(changed)

    def test_rehashed_account_amount_and_authority_tamper_fail_reproduction(self):
        proposal = self.propose_accounts(self.account_allocations(self.targets['valid']))
        for field in ('account', 'amount', 'independently_reviewed', 'code_authority_approved'):
            changed = deepcopy(proposal)
            if field == 'account': changed['payload']['allocations'][0]['account']['government_account_code']='invented'
            elif field == 'amount': changed['payload']['allocations'][0]['amount']='999.00'
            else: changed['payload'][field]=True
            changed['checksum']=checksum(changed['payload'])
            with self.subTest(field=field):
                with self.assertRaises(ValidationError): service.verify(changed)
