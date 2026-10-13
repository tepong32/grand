from copy import deepcopy
from datetime import date
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test.utils import CaptureQueriesContext
from . import test_budget_receipt_attributions as fixtures
from . import budget_receipt_attributions as reviews, budget_receipt_cohorts as service
from .cash_classifications import checksum
from vouchers.collection_corrections import propose as propose_correction


class ReceiptCohortTests(fixtures.ReceiptAttributionTests):
    def cohort(self, **changes):
        args=dict(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=date(2026,9,1),period_end=date(2026,9,30))
        args.update(changes); return service.capture(**args)

    def reviewed_originals(self):
        receipt=self.capture(); original=self.post_source(receipt)
        deposit_source=self.deposit(receipt,'100','COHORT-ORIGINAL-DEPOSIT')
        deposit=self.post_source(deposit_source); inventory=self.inventory()
        approved=self.decide(reviews.propose_batch(**self.args([self.member_args(inventory,original),
            self.member_args(inventory,deposit,receipt=False)])))
        return receipt,original,deposit_source,deposit,approved

    def corrected_originals(self):
        receipt,original,deposit_source,deposit,approved=self.reviewed_originals()
        parents={member.entry_id:member for member in approved.members.all()}
        children=[]
        for source,parent in ((deposit_source,deposit),(receipt,original)):
            fix=propose_correction(original=source,actor=self.treasury_user,corrected_on=date(2026,9,13),reason='Synthetic complete cohort correction')
            children.append((self.post_source(fix),parent))
        inventory=self.inventory()
        proposed=[dict(entry_id=child.pk,expected_latest=0,inherit_from=str(parents[parent.pk].public_id),
            line_pairs=self.pairs(inventory,child.pk,parent.pk)) for child,parent in children]
        corrected=self.decide(reviews.propose_batch(**self.args(proposed)))
        return original,children,corrected

    def test_complete_reviewed_receipt_and_deposit_bridge_unknown_certification_and_exact_corrections(self):
        self.corrected_originals()
        with CaptureQueriesContext(connections['finance']) as queries:
            captured=self.cohort()
        self.assertEqual(len([q for q in queries if 'posting_evidence' in q['sql'] and 'accounting_fund' in q['sql']]),1)
        payload=service.verify(captured)
        self.assertTrue(payload['classification_complete'])
        self.assertEqual(payload['classified_receipts'],'0.00')
        self.assertIsNone(payload['receipt_total'])
        self.assertEqual(payload['category_coverage'],'not_declared')
        self.assertEqual(payload['entity_coverage'],'not_declared')
        self.assertEqual(len(payload['bridge']),10) # two split cash sides plus four counterparts/deposit sides
        self.assertEqual(len(payload['batches']),2)
        self.assertEqual(payload['coverage_controls']['include'],dict(debit='100.00',credit='100.00',cash_movement='0.00'))
        self.assertEqual(payload['coverage_controls']['exclude']['cash_movement'],'0.00')
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            self.assertEqual(service.verify(captured),payload)
        self.assertTrue(service.is_current(captured,self.preparer))

    def test_empty_missing_unresolved_and_newer_versions_never_supply_receipt_zero(self):
        empty=service.verify(self.cohort())
        self.assertFalse(empty['classification_complete']); self.assertIsNone(empty['receipt_total'])
        self.assertIn({'kind':'empty_period_requires_evidence'},empty['issues'])
        entry=self.post_source(self.capture()); inventory=self.inventory()
        missing=service.verify(self.cohort())
        self.assertEqual(missing['coverage_controls']['unresolved']['cash_movement'],'100.00')
        self.assertIn({'entry_id':entry.pk,'kind':'missing_review'},missing['issues'])
        rows=[{**row,'disposition':'unresolved','purpose':'unresolved','category':''}
            for row in self.rows(inventory,entry.pk,receipt=True)]
        self.decide(reviews.propose_batch(**self.args([dict(entry_id=entry.pk,expected_latest=0,rows=rows)])))
        unresolved=service.verify(self.cohort())
        self.assertFalse(unresolved['classification_complete']); self.assertIsNone(unresolved['receipt_total'])
        reviews.propose_batch(**self.args([self.member_args(inventory,entry,latest=1)]))
        newer=service.verify(self.cohort())
        self.assertIn({'entry_id':entry.pk,'kind':'newer_proposal'},newer['issues'])
        self.assertEqual(newer['classified_receipts'],'0.00')

    def test_prior_period_predecessors_do_not_add_activity_and_changed_parent_blocks_descendants(self):
        original,children,_=self.corrected_originals()
        captured=self.cohort(period_start=date(2026,9,13))
        payload=service.verify(captured)
        self.assertTrue(payload['classification_complete'])
        self.assertEqual(payload['classified_receipts'],'-100.00')
        self.assertEqual(payload['category_totals']['service'],'-60.00')
        self.assertEqual(payload['category_totals']['regulatory'],'-40.00')
        self.assertEqual(len(payload['heads']),4)
        self.assertEqual({row['entry_id'] for row in payload['bridge']},{child.pk for child,_ in children})
        inventory=self.inventory()
        reviews.propose_batch(**self.args([self.member_args(inventory,original,latest=1)]))
        changed=service.verify(self.cohort(period_start=date(2026,9,13)))
        self.assertFalse(changed['classification_complete'])
        self.assertIn({'entry_id':children[1][0].pk,'kind':'changed_predecessor'},changed['issues'])
        self.assertEqual(changed['classified_receipts'],'0.00')
        self.assertEqual(service.verify(captured),payload)
        self.assertFalse(service.is_current(captured,self.preparer))

    def test_full_head_manifest_rehashed_tamper_scope_and_later_post_freshness(self):
        receipt=self.capture(); original=self.post_source(receipt); inventory=self.inventory()
        self.decide(reviews.propose_batch(**self.args([self.member_args(inventory,original)])))
        captured=self.cohort(); frozen=deepcopy(captured)
        self.assertEqual(service.verify(captured)['classified_receipts'],'100.00')
        with self.assertRaises(PermissionDenied): self.cohort(actor=self.treasury_user)
        for field,value in (('classified_receipts','100000.00'),('receipt_total','100.00'),('heads',[])):
            damaged=deepcopy(captured); damaged['payload'][field]=value
            damaged['checksum']=checksum(damaged['payload']); damaged['source_checksum']=service.source_checksum(damaged['payload'])
            with self.assertRaises(ValidationError): service.verify(damaged)
        self.post_source(self.deposit(receipt,'100','COHORT-LATER-POST'))
        self.assertFalse(service.is_current(captured,self.preparer))
        self.assertEqual(service.verify(captured)['classified_receipts'],'100.00')
        self.assertEqual(captured,frozen)
