from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase

from . import claim_attributions as history
from . import test_shared_claim_projection as fixture_module
from .shared_claim_proposals import propose, review
from .payables import _reserve_claim, _capacity, verify_reservation


class SharedClaimReservationReviewTests(TestCase):
    databases = {'default', 'finance'}
    setUp = fixture_module.SharedClaimProjectionTests.setUp
    entry = fixture_module.SharedClaimProjectionTests.entry
    post = fixture_module.SharedClaimProjectionTests.post
    legacy = fixture_module.SharedClaimProjectionTests.legacy
    detail = fixture_module.SharedClaimProjectionTests.detail
    proposal = fixture_module.SharedClaimProjectionTests.proposal
    sources_and_payment = fixture_module.SharedClaimProjectionTests.sources_and_payment
    schedule = fixture_module.SharedClaimProjectionTests.schedule
    reviewed_fixture = fixture_module.SharedClaimProjectionTests.reviewed_fixture

    def test_reserved_invoice_rejects_changed_shares_and_retains_compatible_successor(self):
        first, second, payment, records = self.reviewed_fixture()
        invoice = history.allocation_rows(records[0])[0]
        hold = _reserve_claim(source_id=first.pk, case_public_id=uuid4(), key='shared-review-hold',
            amount=Decimal('100'), actor_id=self.maker.pk, department_id=self.department.pk,
            fund_code=first.entry.fund.code, party_key=invoice['party_key'], as_of=date(2026, 9, 5),
            invoice_key=invoice['key'])
        rows = [{'source_id': record.source_id, 'invoices': history.allocation_rows(record)} for record in records]
        args = dict(actor=self.maker, source_ids=[first.pk, second.pk], application_ids=[payment.pk],
            rows=rows, expected_approvals={str(record.source_id): record.version for record in records},
            expected_version=1, evidence_reference='Reconciled invoice schedule', reason='Review updated evidence')
        changed = deepcopy(rows)
        changed[0]['invoices'][0]['applications'][str(payment.pk)] = '299.00'
        changed[1]['invoices'][0]['applications'][str(payment.pk)] = '201.00'
        incompatible = propose(**dict(args, rows=changed))
        with self.assertRaisesMessage(ValidationError, 'already used by applications or reservations'):
            review(incompatible, self.poster, approve=True, note='Cannot change the retained DV invoice')
        self.assertFalse(incompatible.attributions.exists())
        self.assertEqual(history.current(first).pk, records[0].pk)
        successor = propose(**dict(args, expected_version=2))
        approved = review(successor, self.poster, approve=True, note='Same exact invoice allocations')
        self.assertNotEqual(approved[0].pk, records[0].pk)
        hold.refresh_from_db()
        self.assertEqual(verify_reservation(hold).pk, hold.pk)
        self.assertEqual(_capacity(first), Decimal('600'))
        self.assertEqual(_capacity(first, invoice_key=invoice['key']), Decimal('600'))
        self.assertEqual(_capacity(second), Decimal('600'))
