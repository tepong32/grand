from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
import uuid

from django.core.exceptions import ValidationError
from django.db import connections, close_old_connections
from django.test import TransactionTestCase

from . import test_payable_claims
from .claim_groups import reserve
from .models import PayableClaimReservationGroup, PayableClaimReservation
from .payables import _reserve_claim, _capacity


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class ClaimGroupConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = test_payable_claims.PayableClaimTests.setUp
    entry = test_payable_claims.PayableClaimTests.entry
    post = test_payable_claims.PayableClaimTests.post

    def race(self, actions):
        barrier = Barrier(2, timeout=30)
        def run(index):
            close_old_connections()
            try:
                barrier.wait()
                actions[index]()
                return "accepted"
            except ValidationError as error:
                return str(error)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (0, 1)))
        self.assertEqual(results.count("accepted"), 1, results)

    def sources(self):
        return [self.post(self.entry(f"GROUP-{n}", Decimal("1000"), claim=f"INV-{n}")).lines.get(sequence=2) for n in (1, 2)]

    def hold(self, sources, key):
        snapshot = {"department": self.department.pk, "party": "supplier-001", "fund": self.fund.code,
            "claims": [{"source_id": source.pk, "gross": "700.00", "net": "700.00", "deductions": {}} for source in sources]}
        return reserve(key=key, case_public_id=uuid.uuid4(), snapshot=snapshot,
            actor_id=self.poster.pk, as_of=date(2026, 9, 5))

    def test_overlapping_groups_commit_only_one_complete_allocation(self):
        sources = self.sources()
        self.race([lambda: self.hold(sources, "first"), lambda: self.hold(list(reversed(sources)), "second")])
        self.assertEqual(PayableClaimReservationGroup.objects.count(), 1)
        self.assertEqual(PayableClaimReservation.objects.count(), 2)
        self.assertEqual([_capacity(source) for source in sources], [Decimal("300"), Decimal("300")])

    def test_group_and_single_claim_share_capacity_lock(self):
        sources = self.sources()
        def single():
            _reserve_claim(source_id=sources[1].pk, case_public_id=uuid.uuid4(), key="single",
                amount=Decimal("700"), actor_id=self.poster.pk, department_id=self.department.pk,
                fund_code=self.fund.code, party_key="supplier-001", as_of=date(2026, 9, 5))
        self.race([lambda: self.hold(sources, "group"), single])
        count = PayableClaimReservationGroup.objects.count()
        self.assertEqual(PayableClaimReservation.objects.count(), 2 if count else 1)
        self.assertEqual(_capacity(sources[0]), Decimal("300") if count else Decimal("1000"))
