from datetime import date
import tempfile

from django.test import TestCase, override_settings

from accounting.services import submit_entry, post_entry
from . import tests as fixtures
from .models import TaxFilingEvidence, RemittancePostingRequest
from .remittance_returns import propose_return, review_return
from .remittances import materialize_remittance_journal, reconcile_posted_remittance_entry
from .tax_filings import submit_evidence, review_evidence, create_amendment, export_evidence_csv


class RemittanceReturnFilingTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.VoucherWorkflowTests.setUpTestData.__func__)
    employee = classmethod(fixtures.VoucherWorkflowTests.employee.__func__)
    create_case = fixtures.VoucherWorkflowTests.create_case
    budget_certify = fixtures.VoucherWorkflowTests.budget_certify
    return_signatures = fixtures.VoucherWorkflowTests.return_signatures
    enable_remittance_route = fixtures.VoucherWorkflowTests.enable_remittance_route

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='grand-return-filings-')
        self.addCleanup(temporary.cleanup)
        settings = override_settings(MEDIA_ROOT=temporary.name, GRAND_EXPORT_ROOT=temporary.name)
        settings.enable(); self.addCleanup(settings.disable)

    def test_verified_filing_is_retained_and_amendment_remains_available_after_return(self):
        fixtures.VoucherWorkflowTests.test_governed_tax_remittance_preserves_rule_and_verifies_external_filing_evidence(self)
        filing = TaxFilingEvidence.objects.get(version=2)
        submit_evidence(evidence=filing, actor=self.treasury_user)
        review_evidence(evidence=filing, actor=self.validator, approve=True, reason='Independently verified existing agency evidence')
        filing.refresh_from_db()
        before, _ = export_evidence_csv(evidence=filing, actor=self.treasury_user)
        batch = filing.batch
        source = RemittancePostingRequest.objects.get(batch=batch, status=RemittancePostingRequest.POSTED)
        from accounting.models import JournalEntry
        original = JournalEntry.objects.get(public_id=source.accounting_entry_public_id)
        item = propose_return(batch=batch, actor=self.treasury_user, returned_on=date(2026, 9, 1),
            receipt_reference='Synthetic incoming bank credit', reason='Actual partial return',
            filing_basis='Agency evidence retained; independently review the filing disposition',
            allocations=[{'source_detail': original.subsidiary_lines.get().pk, 'amount': '5.00'}],
            expected_version=batch.state_version)
        review_return(item=item, actor=self.validator, approve=True, reason='Checked actual receipt and retained filing evidence')
        item.refresh_from_db()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        filing.refresh_from_db()
        after, _ = export_evidence_csv(evidence=filing, actor=self.treasury_user)
        self.assertEqual(filing.status, filing.VERIFIED)
        self.assertEqual(before, after)
        amendment = create_amendment(evidence=filing, actor=self.treasury_user,
            reason='Agency accepted a successor filing after the actual return')
        submit_evidence(evidence=amendment, actor=self.treasury_user)
        review_evidence(evidence=amendment, actor=self.validator, approve=True, reason='Independently verified retained agency amendment')
        amendment.refresh_from_db()
        self.assertEqual(amendment.status, amendment.VERIFIED)
        self.assertEqual(amendment.supersedes_id, filing.pk)
