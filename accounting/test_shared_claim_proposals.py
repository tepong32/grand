from copy import deepcopy
from decimal import Decimal
from uuid import UUID
from unittest import skipUnless

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase, TransactionTestCase

from . import test_shared_claim_allocations as fixture_module
from .claim_attributions import review
from .models import SharedPayableClaimProposal, PayableClaimAttributionHead, PayableClaimReservation
from .shared_claim_proposals import propose, verify


class SharedClaimProposalTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixture_module.SharedHistoricalPostedSourceTests.setUp
    entry = fixture_module.SharedHistoricalPostedSourceTests.entry
    post = fixture_module.SharedHistoricalPostedSourceTests.post
    legacy = fixture_module.SharedHistoricalPostedSourceTests.legacy
    detail = fixture_module.SharedHistoricalPostedSourceTests.detail
    proposal = fixture_module.SharedHistoricalPostedSourceTests.proposal
    sources_and_payment = fixture_module.SharedHistoricalPostedSourceTests.sources_and_payment

    def schedule(self):
        first, second, payment = self.sources_and_payment()
        rows = [{'source_id': source.pk, 'invoices': [{'key': str(UUID(int=index)),
            'party_key': 'supplier-001', 'claim_reference': f'SHARED-{index}', 'recognized': amount,
            'applications': {str(payment.pk): paid}}]}
            for index, (source, amount, paid) in enumerate([(first, '1000', '300'), (second, '800', '200')], 1)]
        args = dict(actor=self.maker, source_ids=[first.pk, second.pk], application_ids=[payment.pk],
            rows=rows, expected_approvals={str(first.pk): 0, str(second.pk): 0}, expected_version=0,
            evidence_reference='Synthetic shared payment schedule', reason='Identify both original credits')
        return first, second, payment, args

    def test_independent_return_is_retained_without_heads_and_cannot_be_decided_again(self):
        from .shared_claim_proposals import review as decide
        first, second, payment, args = self.schedule()
        proposal = propose(**args)
        with self.assertRaisesMessage(ValidationError, 'different authorized reviewer'):
            decide(proposal, self.maker, approve=True, note='Own proposal')
        with self.assertRaisesMessage(ValidationError, 'different authorized reviewer'):
            decide(proposal, self.poster, approve=True, note='')
        self.poster.is_active = False
        with self.assertRaises(PermissionDenied):
            decide(proposal, self.poster, approve=True, note='Inactive reviewer')
        self.poster.is_active = True
        self.assertFalse(proposal.attributions.exists())
        returned = decide(proposal, self.poster, approve=False, note='Reconcile omitted documentary evidence')
        self.assertEqual({record.status for record in returned}, {'returned'})
        self.assertFalse(PayableClaimAttributionHead.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'undecided shared proposal'):
            decide(proposal, self.poster, approve=True, note='Cannot replace return')

    def test_old_version_and_changed_base_are_rejected_without_partial_members(self):
        from .shared_claim_proposals import review as decide
        first, second, payment, args = self.schedule()
        old = propose(**args)
        newer = propose(**dict(args, expected_version=1))
        with self.assertRaisesMessage(ValidationError, 'latest shared proposal'):
            decide(old, self.poster, approve=True, note='Stale')
        self.assertFalse(old.attributions.exists())
        standalone = self.proposal(first, [], claim_reference='CURRENT-FIRST')
        review(standalone, self.poster, approve=True, note='Independent first claim approval')
        with self.assertRaisesMessage(ValidationError, 'approved attribution changed'):
            decide(newer, self.poster, approve=True, note='Stale base')
        self.assertFalse(newer.attributions.exists())
        self.assertEqual(PayableClaimAttributionHead.objects.count(), 1)

    def test_duplicate_invoice_failure_rolls_back_the_entire_group(self):
        from .shared_claim_proposals import review as decide
        from .models import PayableClaimSlice
        first, second, payment, args = self.schedule()
        proposal = propose(**args)
        other = self.entry('SHARED-DUPLICATE-CLAIM', Decimal('50'))
        line = other.lines.get(sequence=2)
        line.payable_claim_reference = 'SHARED-2'
        line.save()
        self.post(other)
        with self.assertRaisesMessage(ValidationError, 'already recognized'):
            decide(proposal, self.poster, approve=True, note='Duplicate discovered under lock')
        self.assertFalse(proposal.attributions.exists())
        self.assertFalse(PayableClaimAttributionHead.objects.exists())
        self.assertFalse(PayableClaimSlice.objects.exists())

    def test_sealed_versions_preserve_sources_and_do_not_approve_or_reserve(self):
        first, second, payment, args = self.schedule()
        record = propose(**args)
        self.assertEqual(verify(record).pk, record.pk)
        self.assertEqual([row['applications'][str(payment.pk)] for row in record.allocations], ['300.00', '200.00'])
        self.assertFalse(PayableClaimAttributionHead.objects.exists())
        self.assertFalse(PayableClaimReservation.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'shared proposal changed'):
            propose(**args)
        successor = propose(**dict(args, expected_version=1, reason='Rechecked original evidence'))
        self.assertEqual(successor.version, 2)
        self.assertEqual(verify(record).reason, 'Identify both original credits')
        record.reason = 'Overwrite attempted'
        with self.assertRaisesMessage(ValidationError, 'new version'):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()

    def test_changed_approval_requires_reloaded_coordinated_schedule(self):
        first, second, payment, args = self.schedule()
        ordinary = self.proposal(first, [payment], claim_reference='OLD-FIRST')
        review(ordinary, self.poster, approve=True, note='Existing complete-line attribution')
        with self.assertRaisesMessage(ValidationError, 'approved attribution changed'):
            propose(**args)
        args['expected_approvals'][str(first.pk)] = ordinary.version
        record = propose(**args)
        self.assertEqual(record.base_approvals[str(first.pk)]['public_id'], str(ordinary.public_id))
        self.assertEqual(PayableClaimAttributionHead.objects.get(source=first).attribution_id, ordinary.pk)
        self.assertFalse(PayableClaimAttributionHead.objects.filter(source=second).exists())

    def test_other_credit_ownership_cannot_be_bypassed(self):
        first, second, payment, args = self.schedule()
        third_entry = self.entry('THIRD-CREDIT', Decimal('1000'))
        third = third_entry.lines.get(sequence=2)
        third.payable_party_key = third.payable_claim_reference = ''
        third.save()
        self.post(third_entry)
        ordinary = self.proposal(third, [payment], claim_reference='THIRD-OWNER')
        review(ordinary, self.poster, approve=True, note='Owns original application')
        with self.assertRaisesMessage(ValidationError, 'already belongs to another approved claim'):
            propose(**args)
        self.assertFalse(SharedPayableClaimProposal.objects.exists())

    def test_incomplete_schedule_and_inactive_actor_write_nothing(self):
        first, second, payment, args = self.schedule()
        invalid = deepcopy(args['rows'])
        invalid[1]['invoices'][0]['applications'][str(payment.pk)] = '199.99'
        with self.assertRaisesMessage(ValidationError, 'application in full'):
            propose(**dict(args, rows=invalid))
        self.maker.is_active = False
        with self.assertRaises(PermissionDenied):
            propose(**args)
        self.assertFalse(SharedPayableClaimProposal.objects.exists())

    def test_tampered_retained_schedule_is_detected(self):
        first, second, payment, args = self.schedule()
        record = propose(**args)
        SharedPayableClaimProposal.objects.filter(pk=record.pk).update(reason='Bypassed editor')
        record.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'retained source evidence'):
            verify(record)


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native MySQL row locks')
class SharedProposalConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    from . import test_claim_attribution_concurrency as concurrency_module
    setUp = SharedClaimProposalTests.setUp
    entry = SharedClaimProposalTests.entry
    post = SharedClaimProposalTests.post
    legacy = SharedClaimProposalTests.legacy
    detail = SharedClaimProposalTests.detail
    proposal = SharedClaimProposalTests.proposal
    sources_and_payment = SharedClaimProposalTests.sources_and_payment
    schedule = SharedClaimProposalTests.schedule
    race = concurrency_module.ClaimAttributionConcurrencyTests.race

    def test_two_reviewers_cannot_decide_the_same_group_twice(self):
        from .shared_claim_proposals import review as decide
        first, second, payment, args = self.schedule()
        proposal = propose(**args)
        results = self.race([lambda actor: decide(proposal, actor, approve=True, note='Independent complete review'),
            lambda actor: decide(proposal, actor, approve=True, note='Competing complete review')])
        self.assertTrue(any('undecided shared proposal' in result for result in results), results)
        self.assertEqual(proposal.attributions.count(), 2)
        self.assertEqual(PayableClaimAttributionHead.objects.count(), 2)

    def test_shared_and_standalone_approval_cannot_partially_replace_each_other(self):
        from .shared_claim_proposals import review as decide
        first, second, payment, args = self.schedule()
        proposal = propose(**args)
        standalone = self.proposal(first, [payment])
        self.race([lambda actor: decide(proposal, actor, approve=True, note='Complete shared approval'),
            lambda actor: review(standalone, actor, approve=True, note='Standalone approval')])
        group_count = proposal.attributions.count()
        self.assertIn(group_count, [0, 2])
        self.assertEqual(PayableClaimAttributionHead.objects.count(), 2 if group_count else 1)

    def test_concurrent_first_versions_cannot_mix_two_schedules(self):
        first, second, payment, args = self.schedule()
        other = deepcopy(args['rows'])
        other[0]['invoices'][0]['applications'][str(payment.pk)] = '200'
        other[1]['invoices'][0]['applications'][str(payment.pk)] = '300'
        results = self.race([lambda actor: propose(**dict(args, actor=actor)),
            lambda actor: propose(**dict(args, actor=actor, rows=other))])
        self.assertTrue(any('shared proposal changed' in result for result in results), results)
        record = SharedPayableClaimProposal.objects.get()
        self.assertEqual(verify(record).version, 1)
        self.assertIn([row['applications'][str(payment.pk)] for row in record.allocations],
            [['300.00', '200.00'], ['200.00', '300.00']])
        self.assertFalse(PayableClaimAttributionHead.objects.exists())
