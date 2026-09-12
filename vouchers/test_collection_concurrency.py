from datetime import date
from unittest import skipUnless
import tempfile

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase, override_settings

from . import test_collection_workflow as scenarios
from . import test_deduction_correction_concurrency as concurrent
from .collections import record_deposit
from .collection_corrections import propose
from .collection_posting import review_source, materialize
from .models import TreasuryCollectionSource as Source, CollectionPostingRequest


@skipUnless(connections['finance'].vendor == 'mysql','Requires native MySQL row locks')
class CollectionConcurrencyTests(TransactionTestCase):
    databases={'default','finance'}
    employee=classmethod(scenarios.CollectionWorkflowTests.employee.__func__)
    capture=scenarios.CollectionWorkflowTests.capture
    deposit=scenarios.CollectionWorkflowTests.deposit
    post_source=scenarios.CollectionWorkflowTests.post_source
    race=concurrent.DeductionCorrectionConcurrencyTests.race

    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='grand-collection-race-')
        self.addCleanup(temporary.cleanup)
        settings=override_settings(MEDIA_ROOT=temporary.name,GRAND_EXPORT_ROOT=temporary.name)
        settings.enable();self.addCleanup(settings.disable)
        scenarios.CollectionWorkflowTests.setUpTestData.__func__(type(self))
        scenarios.CollectionWorkflowTests.setUp(self)

    def test_competing_deposits_cannot_consume_the_same_receipt(self):
        receipt=self.capture();self.post_source(receipt)
        def compete(number):
            record_deposit(actor=get_user_model().objects.get(pk=self.treasury_user.pk),variant=self.transaction_variant,
                deposited_on=date(2026,9,12),fund_code='general-fund',deposit_reference=f'RACE-{number}',
                receiving_bank_id=self.bank_item.public_id,allocations=[{'receipt':str(receipt.public_id),'amount':'70'}],
                evidence_reference='Actual synthetic deposit')
            return 'accepted'
        result=self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)
        self.assertEqual(Source.objects.filter(kind=Source.DEPOSIT).count(),1)

    def test_receipt_correction_and_deposit_share_one_source_boundary(self):
        receipt=self.capture();self.post_source(receipt)
        def compete(number):
            actor=get_user_model().objects.get(pk=self.treasury_user.pk)
            if number == 1:
                propose(original=Source.objects.get(pk=receipt.pk),actor=actor,corrected_on=date(2026,9,12),reason='Wrong receipt')
            else:
                record_deposit(actor=actor,variant=self.transaction_variant,deposited_on=date(2026,9,12),
                    fund_code='general-fund',deposit_reference='COMPETING',receiving_bank_id=self.bank_item.public_id,
                    allocations=[{'receipt':str(receipt.public_id),'amount':'100'}],evidence_reference='Actual synthetic slip')
            return 'accepted'
        result=self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)

    def test_duplicate_correction_materialization_recovers_one_reversal(self):
        receipt=self.capture();original=self.post_source(receipt)
        correction=propose(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Wrong receipt')
        review_source(source=correction,actor=self.validator,approve=True,reason='Independent correction review')
        request=correction.posting_requests.get()
        def compete(number):
            entry,created=materialize(CollectionPostingRequest.objects.get(pk=request.pk),
                get_user_model().objects.get(pk=self.preparer.pk))
            return entry.pk,created
        result=self.race(compete)
        self.assertTrue(all(isinstance(row,tuple) for row in result),result)
        self.assertEqual(len({row[0] for row in result}),1)
        self.assertEqual(sorted(row[1] for row in result),[False,True])
        self.assertEqual(original.reversal_entries.count(),1)
