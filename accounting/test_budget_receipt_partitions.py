from copy import deepcopy
from datetime import date
from django.core.exceptions import ValidationError
from . import test_budget_receipt_sources as fixtures
from . import budget_receipt_partitions as service
from .cash_classifications import checksum
from vouchers.collection_corrections import propose as propose_correction


class ReceiptPartitionTests(fixtures.ReceiptSourceInventoryTests):
    def rows(self, inventory, entry_id, *, receipt=False):
        _, entry, _ = service.entry_source(inventory, entry_id)
        rows = []
        for line in entry['lines']:
            value = line['debit'] if line['debit'] != '0.00' else line['credit']
            if receipt and line['account_id'] == self.collection_cash.pk:
                for amount, category in (('60.00', 'service'), ('40.00', 'regulatory')):
                    rows.append(dict(line_id=line['id'], amount=amount, disposition='include',
                        purpose='receipt', category=category, basis='Synthetic explicit charge allocation'))
            else:
                rows.append(dict(line_id=line['id'], amount=value, disposition='exclude',
                    purpose='transfer' if entry['source_type'] == 'deposit' else 'counterpart',
                    category='', basis='Synthetic explicit source disposition'))
        return rows

    def pairs(self, inventory, child_id, parent_id):
        _, child, _ = service.entry_source(inventory, child_id)
        _, parent, _ = service.entry_source(inventory, parent_id)
        return {str(row['id']): next(line['id'] for line in parent['lines']
            if line['account_id'] == row['account_id']) for row in child['lines']}

    def test_complete_explicit_splits_and_deposit_exclusions_stay_uncertified(self):
        receipt = self.capture(); entry = self.post_source(receipt)
        deposit = self.post_source(self.deposit(receipt, '100', 'PARTITION-DEPOSIT'))
        inventory = self.inventory()
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            partition = service.propose(inventory, entry.pk, self.rows(inventory, entry.pk, receipt=True))
            self.assertEqual(service.verify(inventory, partition)['controls']['classified_receipts'], '100.00')
        self.assertIsNone(partition['payload']['receipt_total'])
        self.assertEqual(partition['payload']['review_status'], 'not_reviewed')
        transfer_rows = self.rows(inventory, deposit.pk)
        excluded = service.propose(inventory, deposit.pk, transfer_rows)
        self.assertEqual(service.verify(inventory, excluded)['controls']['classified_receipts'], '0.00')
        bank = next(row for row in transfer_rows if row['line_id'] == next(
            line['id'] for line in service.entry_source(inventory, deposit.pk)[1]['lines']
            if line['account_id'] == self.deposit_bank.pk))
        bank.update(disposition='include', purpose='receipt', category='service')
        with self.assertRaisesMessage(ValidationError, 'deposits'):
            service.propose(inventory, deposit.pk, transfer_rows)

    def test_exact_source_corrections_inherit_splits_and_prior_period_dependencies(self):
        receipt = self.capture(); original = self.post_source(receipt)
        deposit_source = self.deposit(receipt, '100', 'PARTITION-REVERSE-DEPOSIT')
        deposit = self.post_source(deposit_source)
        children = []
        for source in (deposit_source, receipt):
            fix = propose_correction(original=source, actor=self.treasury_user,
                corrected_on=date(2026, 9, 13), reason='Synthetic linked partition correction')
            children.append(self.post_source(fix))
        inventory = self.inventory(period_start=date(2026, 9, 13))
        self.assertEqual(inventory['payload']['controls']['journals'], 2)
        parent = service.propose(inventory, original.pk, self.rows(inventory, original.pk, receipt=True))
        original_pairs = self.pairs(inventory, children[1].pk, original.pk)
        reverse = service.inherit(inventory, children[1].pk, parent, pairs=original_pairs)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            self.assertEqual(service.verify(inventory, reverse)['controls']['classified_receipts'], '-100.00')
        self.assertEqual(reverse['payload']['dependency'], parent)
        self.assertEqual([row['signed_amount'] for row in reverse['payload']['allocations'] if row['disposition']=='include'],
            ['-60.00', '-40.00'])
        transfer = service.propose(inventory, deposit.pk, self.rows(inventory, deposit.pk))
        reversed_transfer = service.inherit(inventory, children[0].pk, transfer,
            pairs=self.pairs(inventory, children[0].pk, deposit.pk))
        self.assertEqual(service.verify(inventory, reversed_transfer)['controls']['classified_receipts'], '0.00')
        with self.assertRaises(ValidationError):
            service.propose(inventory, children[1].pk, service._input_rows(reverse))
        with self.assertRaises(ValidationError):
            service.inherit(inventory, children[1].pk, transfer, pairs=original_pairs)
        bad = deepcopy(reverse); bad['payload']['allocations'][0]['category'] = 'business_tax'
        bad['checksum'] = checksum(bad['payload'])
        with self.assertRaises(ValidationError): service.verify(inventory, bad)
        with self.assertRaises(ValidationError):
            service.inherit(inventory, children[1].pk, parent, pairs={key: next(iter(original_pairs.values())) for key in original_pairs})

    def test_omission_overallocation_fractional_amount_unknown_category_and_rehashed_tamper(self):
        entry = self.post_source(self.capture()); inventory = self.inventory()
        rows = self.rows(inventory, entry.pk, receipt=True)
        for changed in (rows[:-1], [{**row, 'amount':'101.00'} for row in rows],
            [{**row, 'amount':'0.001'} for row in rows],
            [{**row, 'category':'guessed'} if row['disposition']=='include' else row for row in rows],
            [{**row, 'basis':''} for row in rows], [{**row, 'extra':'ignored?'} for row in rows]):
            with self.assertRaises(ValidationError): service.propose(inventory, entry.pk, changed)
        unknown = [{**row, 'disposition':'unresolved', 'purpose':'unresolved', 'category':''} for row in rows]
        proposed = service.propose(inventory, entry.pk, unknown)
        self.assertEqual(service.verify(inventory, proposed)['controls']['unresolved_amount'], '200.00')
        self.assertIsNone(proposed['payload']['receipt_total'])
        damaged = deepcopy(proposed); damaged['payload']['receipt_total']='0.00'
        damaged['checksum']=checksum(damaged['payload'])
        with self.assertRaises(ValidationError): service.verify(inventory, damaged)
