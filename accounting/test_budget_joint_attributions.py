from copy import deepcopy
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import budget_attributions as service
from . import test_budget_component_usage as fixtures
from .budget_reviewed_components import source_components
from .budget_component_usage import component_usage
from .cash_classifications import checksum
from .models import BudgetExpenditureAttribution as Attribution


class JointAttributionTests(TestCase):
    databases = {"default", "finance"}
    setUp = fixtures.ComponentUsageTests.setUp
    entry = fixtures.ComponentUsageTests.entry
    post = fixtures.ComponentUsageTests.post
    rows = fixtures.ComponentUsageTests.rows
    approve = fixtures.ComponentUsageTests.approve
    reference = fixtures.ComponentUsageTests.reference
    payment_rows = fixtures.ComponentUsageTests.payment_rows
    capture = fixtures.ComponentUsageTests.capture
    propose = fixtures.ComponentUsageTests.propose
    reverse_and_review = fixtures.ComponentUsageTests.reverse_and_review

    def joint(self, returned, *, latest=1, extra=None):
        proposals = [dict(entry_id=returned.pk, expected_latest=latest, inherit_from=self.payment.pk),
                     dict(entry_id=self.payment.pk, expected_latest=latest, allocations=self.payment_rows())]
        if extra is not None:
            proposals.insert(0, dict(entry_id=extra.pk, expected_latest=latest, inherit_from=returned.pk))
        return service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=self.original.entry_date.replace(day=1), period_end=self.original.entry_date.replace(day=10),
            expected_source_checksum=self.capture()["checksum"], proposals=proposals,
            reason="Repair dependent classifications together", evidence_reference="SYN-JOINT-REPAIR")

    def stale_pair(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        returned = self.reverse_and_review(self.payment, "RETURN", 5)
        retained = self.capture()
        self.approve(self.propose(version=1))
        self.bound = source_components(self.capture(), self.source.pk)
        return returned, retained

    def test_source_successor_joint_repair_preserves_real_pending_dependencies_and_old_output(self):
        returned, retained = self.stale_pair()
        old = service.reviewed_allocations(retained)
        pending = self.propose(self.payment_rows(), version=1, entry=self.payment)
        with self.assertRaisesMessage(ValidationError, "no longer reproduces"):
            self.approve(pending)
        pending[0].refresh_from_db()
        self.assertEqual(pending[0].status, "submitted")
        with self.assertRaises(ValidationError):
            service.reversal_allocations(self.capture(), returned.pk)
        proposals = [dict(entry_id=self.payment.pk, expected_latest=2, allocations=self.payment_rows()),
                     dict(entry_id=returned.pk, expected_latest=1,
                          allocations=service.reversal_allocations(retained, returned.pk))]
        with self.assertRaisesMessage(ValidationError, "separate batch"):
            service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
                period_start=pending[0].period_start, period_end=pending[0].period_end,
                expected_source_checksum=self.capture()["checksum"], proposals=proposals,
                reason="Repair dependent classifications together", evidence_reference="SYN-JOINT-REPAIR")
        service.review_batch(batch_id=pending[0].batch_id, actor=self.poster, approve=False, note="Replace with explicit joint review")
        proposals[1] = dict(entry_id=returned.pk, expected_latest=1, inherit_from=self.payment.pk)
        records = service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=pending[0].period_start, period_end=pending[0].period_end,
            expected_source_checksum=self.capture()["checksum"], proposals=list(reversed(proposals)),
            reason="Explicit joint repair", evidence_reference="SYN-JOINT-REPAIR")
        parent, child = records
        self.assertTrue(all(record.status == "submitted" and record.reviewed_at is None for record in records))
        self.assertEqual(child.dependencies, {str(parent.entry_id): {
            "public_id": str(parent.public_id), "proposal_checksum": parent.proposal_checksum}})
        self.assertEqual(child.source_snapshot["reversal_attributions"][0]["proposal_dependency"], child.dependencies[str(parent.entry_id)])
        self.assertNotIn("attribution", child.source_snapshot["reversal_attributions"][0])
        self.approve(records)
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            result = component_usage(captured, require_complete=True)
            projected = service.reviewed_allocations(captured)
        self.assertEqual(len(queries), 1)
        self.assertTrue(result["complete"])
        self.assertTrue(all(row["status"] == "reviewed" for row in projected))
        self.assertEqual(service.reviewed_allocations(retained), old)

    def test_joint_reversal_chain_retains_every_pending_predecessor(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        returned = self.reverse_and_review(self.payment, "RETURN", 5)
        restored = self.reverse_and_review(returned, "RESTORED", 6)
        self.approve(self.propose(version=1))
        self.bound = source_components(self.capture(), self.source.pk)
        records = self.joint(returned, extra=restored)
        self.assertEqual(len(records[-1].dependencies), 2)
        self.approve(records)
        key = self.reference("loan_principal")["component_key"]
        self.assertEqual(component_usage(self.capture(), require_complete=True)["components"][key]["applied"], "200.00")

    def test_changed_source_rejects_whole_joint_batch_without_deciding_any_member(self):
        returned, _ = self.stale_pair()
        records = self.joint(returned)
        self.approve(self.propose(version=2))
        with self.assertRaises(ValidationError):
            self.approve(records)
        self.assertEqual(Attribution.objects.filter(batch_id=records[0].batch_id, status="submitted").count(), 2)
        self.assertFalse(Attribution.objects.filter(batch_id=records[0].batch_id, reviewed_at__isnull=False).exists())

    def test_self_review_is_denied_and_return_keeps_the_proposal_chain(self):
        returned, _ = self.stale_pair()
        records = self.joint(returned)
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label="accounting", codename="review_budget_attributions"))
        with self.assertRaises(ValidationError):
            service.review_batch(batch_id=records[0].batch_id, actor=self.maker, approve=True, note="Own joint proposal")
        service.review_batch(batch_id=records[0].batch_id, actor=self.poster, approve=False, note="Return complete group")
        for record in records:
            record.refresh_from_db()
            self.assertEqual(record.status, "returned")
            service.verify(record)
        self.assertTrue(records[-1].dependencies)

    def test_wrong_inheritance_and_altered_parent_are_rejected(self):
        returned, _ = self.stale_pair()
        with self.assertRaises(ValidationError):
            service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
                period_start=self.original.entry_date.replace(day=1), period_end=self.original.entry_date.replace(day=10),
                expected_source_checksum=self.capture()["checksum"],
                proposals=[dict(entry_id=returned.pk, expected_latest=1, inherit_from=self.original.pk)],
                reason="Missing predecessor", evidence_reference="SYN-INVALID")
        records = self.joint(returned)
        changed = deepcopy(records[0].allocations)
        changed[0]["basis"] = "Altered after proposal"
        Attribution.objects.filter(pk=records[0].pk).update(allocations=changed)
        with self.assertRaises(ValidationError):
            self.approve(records)
        self.assertEqual(Attribution.objects.filter(batch_id=records[0].batch_id, status="submitted").count(), 2)

    def test_empty_dependencies_preserve_legacy_projection_and_checksums(self):
        captured = self.capture()
        for entry in captured["payload"]["journals"]:
            if entry["attribution"]:
                self.assertNotIn("dependencies", entry["attribution"])
                self.assertEqual(checksum({key: entry["attribution"][key] for key in service.PROPOSAL_FIELDS}),
                                 entry["attribution"]["proposal_checksum"])
        legacy = deepcopy(captured)
        legacy["payload"]["schema"] = 5
        legacy["checksum"] = checksum(legacy["payload"])
        legacy["evidence_checksum"] = checksum(dict(source_checksum=legacy["checksum"], captured_at=legacy["captured_at"]))
        self.assertEqual(service.reviewed_allocations(legacy), service.reviewed_allocations(captured))
