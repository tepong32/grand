from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from . import test_deduction_corrections as fixtures
from .models import TreasuryCollectionSource
from .remittances import _digest


class CollectionSourceStorageTests(TestCase):
    """Storage contracts only; these do not prove receipt/deposit workflow coverage."""
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.DeductionCorrectionTests.setUpTestData.__func__)
    employee = classmethod(fixtures.DeductionCorrectionTests.employee.__func__)

    def receipt(self, **changes):
        proposal = {'receipt_book':'SYNTHETIC-BOOK', 'receipt_number':'001', 'amount':'100.00',
            'payer_reference':'Synthetic payer only', 'evidence_reference':'Synthetic collection evidence'}
        values = dict(treasury_department=self.treasury, configuration_release=self.release,
            transaction_variant=self.transaction_variant, finance_department_id=self.accounting.pk,
            finance_department_label=self.accounting.name, kind=TreasuryCollectionSource.RECEIPT,
            book_reference='SYNTHETIC-BOOK', document_reference='001', source_date=date(2026,9,12),
            fund_code='general-fund', amount=Decimal('100'), proposal=proposal,
            proposal_checksum=_digest(proposal), prepared_by=self.treasury_user)
        values.update(changes)
        return TreasuryCollectionSource.objects.create(**values)

    def test_source_and_independent_decision_evidence_are_retained(self):
        source = self.receipt()
        source.amount = Decimal('90')
        with self.assertRaisesMessage(ValidationError, 'immutable'):
            source.save()
        source.refresh_from_db()
        source.status = source.APPROVED
        source.reviewed_by, source.reviewed_at, source.review_reason = self.validator, timezone.now(), 'Synthetic independent review'
        source.save()
        source.review_reason = 'Overwritten decision'
        with self.assertRaisesMessage(ValidationError, 'independent'):
            source.save()
        with self.assertRaisesMessage(ValidationError, 'cannot be deleted'):
            source.delete()

    def test_document_version_and_positive_amount_have_database_constraints(self):
        self.receipt()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.receipt()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.receipt(document_reference='002', amount=Decimal('0'))
        self.assertEqual(TreasuryCollectionSource.objects.count(),1)
