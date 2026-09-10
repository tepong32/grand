from datetime import date
from unittest.mock import patch

from django.test import TestCase

from . import claim_attributions, services, test_claim_attributions
from .claim_attributions import review, current
from .payables import claim_rows
from reporting.datasets import PostedPayableScheduleDataset


class ClaimProjectionTests(TestCase):
    databases = {"default", "finance"}
    setUp = test_claim_attributions.ClaimAttributionTests.setUp
    entry = test_claim_attributions.ClaimAttributionTests.entry
    post = test_claim_attributions.ClaimAttributionTests.post
    legacy = test_claim_attributions.ClaimAttributionTests.legacy
    detail = test_claim_attributions.ClaimAttributionTests.detail
    proposal = test_claim_attributions.ClaimAttributionTests.proposal

    def test_schedule_rows_and_sources_retain_one_attribution_version(self):
        source, applied = self.legacy()
        review(self.proposal(source, [applied]), self.poster, approve=True, note="Original reconciliation")
        successor = self.proposal(source, [applied], party_key="supplier-corrected", expected_version=1)
        reconcile = services.control_reconciliation_snapshot

        def approve_during_generation(*args, **kwargs):
            review(successor, self.poster, approve=True, note="Verified corrected payee identity")
            return reconcile(*args, **kwargs)

        with patch.object(services, "control_reconciliation_snapshot", approve_during_generation):
            payload = PostedPayableScheduleDataset().payload(self.department, date(2026, 9, 1), date(2026, 9, 5), {})
        self.assertEqual(current(source).version, 2)
        self.assertEqual({row["reference_key"] for row in payload.rows}, {"supplier-001"})
        self.assertEqual({row["snapshot"]["reference_key"] for row in payload.sources}, {"supplier-001"})
        self.assertTrue(all(row["snapshot"]["source_snapshot"]["claim_attribution"]["version"] == 1 for row in payload.sources))

    def test_claim_amount_and_export_evidence_use_the_same_reviewed_version(self):
        source, applied = self.legacy()
        review(self.proposal(source, [applied]), self.poster, approve=True, note="Original reconciliation")
        successor = self.proposal(source, [], party_key="supplier-corrected", expected_version=1,
            reason="Correct an application that the supporting evidence assigns elsewhere")
        read = claim_attributions.application_lines
        changed = False

        def approve_after_read(*args, **kwargs):
            nonlocal changed
            result = read(*args, **kwargs)
            if not changed:
                changed = True
                review(successor, self.poster, approve=True, note="Verified corrected schedule")
            return result

        with patch.object(claim_attributions, "application_lines", approve_after_read):
            row = claim_rows(self.department.pk, date(2026, 9, 5))[0]
        self.assertEqual(current(source).version, 2)
        self.assertEqual(row["outstanding"], 600)
        self.assertEqual(row["party_key"], "supplier-001")
        self.assertEqual(row["attribution"]["version"], 1)
