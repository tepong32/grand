from copy import deepcopy
from datetime import date
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from . import test_budget_receipt_partitions as fixtures
from . import budget_receipt_attributions as service
from .cash_classifications import checksum
from .models import (BudgetReceiptAttributionBatch as Batch, BudgetReceiptAttribution as Member,
    BudgetReceiptAttributionHead as Head, AccountingAuditEvent, JournalEntry, Fund)
from vouchers.collection_corrections import propose as propose_correction


class ReceiptAttributionTests(fixtures.ReceiptPartitionTests):
    def setUp(self):
        super().setUp()
        self.configure_receipt_permissions()

    def configure_receipt_permissions(self):
        for actor, actions in ((self.preparer, ('view', 'prepare', 'review', 'export')),
                              (self.validator, ('view', 'review', 'export'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=[a+'_budget_receipt_attributions' for a in actions]))

    def args(self, proposals, **changes):
        inventory = service.capture(actor=self.preparer, fund_id=self.receipt_fund.pk,
            period_start=date(2026,9,1), period_end=date(2026,9,30))
        args = dict(actor=self.preparer, fund_id=self.receipt_fund.pk,
            period_start=date(2026,9,1), period_end=date(2026,9,30),
            expected_source_checksum=inventory['source_checksum'], proposals=proposals,
            reason='Synthetic complete source partition', evidence_reference='Synthetic receipt authority')
        args.update(changes); return args

    def member_args(self, inventory, entry, *, latest=0, receipt=True):
        return dict(entry_id=entry.pk, expected_latest=latest, rows=self.rows(inventory, entry.pk, receipt=receipt))

    def decide(self, batch, **changes):
        args=dict(batch_id=batch.public_id, actor=self.validator, approve=True, note='Independent synthetic receipt review')
        args.update(changes); return service.review_batch(**args)

    def test_whole_batch_independent_review_retained_snapshot_immutability_and_no_posting(self):
        receipt=self.capture(); entry=self.post_source(receipt)
        deposit=self.post_source(self.deposit(receipt,'100','REVIEW-BATCH-DEPOSIT'))
        inventory=self.inventory()
        batch=service.propose_batch(**self.args([self.member_args(inventory,entry),self.member_args(inventory,deposit,receipt=False)]))
        original=deepcopy(service.snapshot(batch,self.preparer))
        with self.assertRaises(ValidationError): self.decide(batch,actor=self.preparer)
        self.assertEqual(Head.objects.count(),0)
        approved=self.decide(batch)
        retained=service.snapshot(approved,self.preparer)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            self.assertEqual(service.verify_snapshot(retained),retained['payload'])
            service.verify_snapshot(original)
        self.assertEqual(retained['payload'],original['payload'])
        self.assertEqual(Head.objects.count(),2)
        self.assertEqual(JournalEntry.objects.count(),2)
        self.assertTrue(service.is_current(approved,self.preparer))
        self.assertEqual(AccountingAuditEvent.objects.filter(action='budget_receipt_approved').count(),1)
        with self.assertRaises(ValidationError): self.decide(batch)
        member=Member.objects.first()
        with self.assertRaises(ValidationError): member.save()
        with self.assertRaises(ValidationError): member.delete()
        with self.assertRaises(ValidationError): approved.delete()
        approved.review_note='Rewrite old review'
        with self.assertRaises(ValidationError): approved.save()

    def test_later_post_stale_batch_return_and_latest_version_preserve_sources(self):
        receipt=self.capture(); entry=self.post_source(receipt); inventory=self.inventory()
        batch=service.propose_batch(**self.args([self.member_args(inventory,entry)]))
        retained=deepcopy(service.snapshot(batch,self.preparer))
        self.post_source(self.deposit(receipt,'100','REVIEW-STALE-DEPOSIT'))
        with self.assertRaisesMessage(ValidationError,'sources changed'): self.decide(batch)
        self.assertFalse(Head.objects.exists())
        returned=self.decide(batch,approve=False,note='Source cohort changed; retained return')
        self.assertEqual(returned.status,Batch.RETURNED)
        fresh=self.inventory()
        second=service.propose_batch(**self.args([self.member_args(fresh,entry,latest=1)]))
        third=service.propose_batch(**self.args([self.member_args(fresh,entry,latest=2)]))
        with self.assertRaisesMessage(ValidationError,'newer receipt'): self.decide(second)
        approved=self.decide(third)
        self.assertTrue(service.is_current(approved,self.preparer))
        self.assertEqual(service.snapshot(returned,self.preparer)['payload'],retained['payload'])
        self.assertEqual(Member.objects.filter(entry=entry).count(),3)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='budget_receipt_returned').count(),1)

    def test_exact_reviewed_correction_pins_decision_and_changed_parent_blocks_new_use(self):
        entry_source=self.capture(); entry=self.post_source(entry_source); inventory=self.inventory()
        original=self.decide(service.propose_batch(**self.args([self.member_args(inventory,entry)])))
        parent=original.members.get()
        fix=propose_correction(original=entry_source,actor=self.treasury_user,corrected_on=date(2026,9,13),reason='Synthetic linked correction')
        child=self.post_source(fix); inventory=self.inventory()
        def inherited(latest,parent_member):
            return dict(entry_id=child.pk,expected_latest=latest,inherit_from=str(parent_member.public_id),
                line_pairs=self.pairs(inventory,child.pk,entry.pk))
        first=service.propose_batch(**self.args([inherited(0,parent)]))
        frozen=deepcopy(service.snapshot(first,self.preparer))
        successor=service.propose_batch(**self.args([self.member_args(inventory,entry,latest=1)]))
        with self.assertRaisesMessage(ValidationError,'predecessor review changed'): self.decide(first)
        self.decide(first,approve=False)
        newer=self.decide(successor).members.get()
        replacement=self.decide(service.propose_batch(**self.args([inherited(1,newer)])))
        retained=service.snapshot(replacement,self.preparer)
        self.assertEqual(retained['payload']['members'][0]['partition']['payload']['controls']['classified_receipts'],'-100.00')
        self.assertEqual(retained['payload']['members'][0]['dependencies'][0]['decision_checksum'],successor.decision_checksum or newer.batch.decision_checksum)
        self.assertTrue(service.is_current(replacement,self.preparer))
        damaged=deepcopy(retained)
        damaged['payload']['members'][0]['dependencies'][0]['member']=str(first.members.get().public_id)
        damaged['checksum']=checksum(damaged['payload'])
        with self.assertRaises(ValidationError): service.verify_snapshot(damaged)
        further=service.propose_batch(**self.args([self.member_args(inventory,entry,latest=2)]))
        self.assertFalse(service.is_current(replacement,self.preparer))
        self.assertEqual(service.snapshot(first,self.preparer)['payload'],frozen['payload'])
        service.verify_snapshot(retained)
        self.assertEqual(further.status,Batch.SUBMITTED)

    def test_exact_permissions_uat_foreign_scope_tamper_and_atomic_invalid_members(self):
        entry=self.post_source(self.capture()); inventory=self.inventory()
        proposal=self.member_args(inventory,entry)
        self.preparer.user_permissions.remove(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=['view_budget_summary_actuals','prepare_budget_summary_actuals','review_budget_summary_actuals','export_budget_summary_actuals']))
        batch=service.propose_batch(**self.args([proposal]))
        with self.assertRaises(PermissionDenied): service.snapshot(batch,self.treasury_user)
        foreign=Fund.objects.create(department_id=self.treasury.pk,department_label=self.treasury.name,code='FOREIGN-REVIEW',name='Foreign')
        with self.assertRaises(PermissionDenied): service.capture(actor=self.preparer,fund_id=foreign.pk,period_start=date(2026,9,1),period_end=date(2026,9,30))
        args=self.args([proposal,{**proposal,'entry_id':999999}],expected_source_checksum=inventory['source_checksum'])
        with self.assertRaises(ValidationError): service.propose_batch(**args)
        self.assertEqual(Batch.objects.count(),1)
        self.assertEqual(Member.objects.count(),1)
        viewer,_=Group.objects.get_or_create(name='Finance UAT Viewer'); self.preparer.groups.add(viewer)
        with self.assertRaises(PermissionDenied): service.propose_batch(**self.args([proposal]))
        with self.assertRaises(PermissionDenied): self.decide(batch,actor=self.preparer)
        self.assertEqual(service.snapshot(batch,self.preparer)['decision'],None)
        self.assertEqual(service.snapshot(batch,self.preparer,action='export')['decision'],None)
        Member.objects.filter(batch=batch).update(base_version=99)
        with self.assertRaises(ValidationError): service.snapshot(batch,self.preparer)

    def test_shared_predecessor_batch_retained_once_for_distinct_corrections(self):
        receipt=self.capture(); original=self.post_source(receipt)
        deposit_source=self.deposit(receipt,'100','SHARED-REVIEWED-SOURCE')
        deposit=self.post_source(deposit_source); inventory=self.inventory()
        approved=self.decide(service.propose_batch(**self.args([self.member_args(inventory,original),
            self.member_args(inventory,deposit,receipt=False)])))
        parents={member.entry_id:member for member in approved.members.all()}
        children=[]
        for source,parent in ((deposit_source,deposit),(receipt,original)):
            correction=propose_correction(original=source,actor=self.treasury_user,
                corrected_on=date(2026,9,13),reason='Synthetic shared-batch correction')
            child=self.post_source(correction); children.append((child,parent))
        inventory=self.inventory()
        proposals=[dict(entry_id=child.pk,expected_latest=0,inherit_from=str(parents[parent.pk].public_id),
            line_pairs=self.pairs(inventory,child.pk,parent.pk)) for child,parent in children]
        reviewed=self.decide(service.propose_batch(**self.args(proposals)))
        retained=service.snapshot(reviewed,self.preparer)
        self.assertEqual(list(retained['payload']['predecessor_snapshots']),[str(approved.public_id)])
        self.assertEqual(len(retained['payload']['members']),2)
        for member in retained['payload']['members']:
            self.assertEqual(member['dependencies'][0]['batch'],str(approved.public_id))
            self.assertNotIn('reviewed_snapshot',member['dependencies'][0])
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            service.verify_snapshot(retained)
        self.assertTrue(service.is_current(reviewed,self.preparer))
        damaged=deepcopy(retained); damaged['payload']['predecessor_snapshots']={}
        damaged['checksum']=checksum(damaged['payload'])
        with self.assertRaises(ValidationError): service.verify_snapshot(damaged)
