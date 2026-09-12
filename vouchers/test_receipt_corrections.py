from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission, Group
from django.urls import reverse

from accounting.services import submit_entry, post_entry, discard_draft
from . import test_remittance_returns as fixtures
from .receipt_corrections import propose_correction, review_correction
from .remittances import materialize_remittance_journal, reconcile_posted_remittance_entry, withholding_availability
from .models import RemittancePostingRequest


class ReceiptCorrectionTests(fixtures.RemittanceReturnTests):
    def posted_receipt(self):
        self.remitted = self.posted_remittance(); self.batch = self.remitted_source_batch()
        self.receipt = self.propose('100.00', day=1)
        self.incoming = self.post_return(self.receipt)
        self.receipt.refresh_from_db()

    def correction(self):
        self.batch.refresh_from_db()
        return propose_correction(receipt=self.receipt, actor=self.treasury_user,
            correction_date=date(2026, 9, 2), reason='Receipt amount was encoded incorrectly',
            evidence_reference='Synthetic bank credit correction', filing_basis='Synthetic reviewed agency disposition',
            expected_version=self.batch.state_version)

    def available_after(self):
        return withholding_availability(finance_department_id=self.accounting.pk,
            transaction_type=self.transaction_variant.code, as_of_date=date(2026, 9, 30), include_nonpositive=True)[0]['available']

    def test_http_exact_correction_and_replacement_retains_receipt_and_outputs(self):
        self.posted_receipt()
        original = list(self.incoming.lines.values('account_id', 'debit', 'credit'))
        approval = (self.receipt.reviewed_by_id, self.receipt.reviewed_at, self.receipt.review_reason, self.receipt.proposal)
        for user in (self.treasury_user, self.validator):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='view_remittance_workbench'))
        self.batch.refresh_from_db()
        url = reverse('vouchers:receipt_correct', args=[self.batch.public_id, self.receipt.public_id])
        data = {'correction_date': '2026-09-02', 'reason': 'Receipt encoded incorrectly',
            'evidence_reference': 'Synthetic bank correction', 'filing_basis': 'Synthetic retained agency basis',
            'expected_version': self.batch.state_version}
        self.client.force_login(self.treasury_user)
        group, _ = Group.objects.get_or_create(name='Finance UAT Viewer')
        self.treasury_user.groups.add(group)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.treasury_user.groups.remove(group)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        item = self.receipt.corrections.get()
        self.assertEqual(self.available_after(), Decimal('0'))
        with self.assertRaises(ValidationError): self.request(correction_date=date(2026, 9, 3))
        self.client.force_login(self.validator)
        self.assertContains(self.client.get(reverse('finance_operations:my_work')), 'Posted receipt corrections for review')
        review_url = reverse('vouchers:receipt_correction_review', args=[self.batch.public_id, self.receipt.public_id, item.public_id])
        self.assertEqual(self.client.post(review_url, {'decision':'approve', 'reason':'Independent receipt correction review'}).status_code, 302)
        item.refresh_from_db()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        self.assertEqual(entry.reversal_of_id, self.incoming.pk)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        with self.assertRaises(ValidationError): self.propose('60', day=3)
        reconcile_posted_remittance_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        reconcile_posted_remittance_entry(self.incoming, self.validator)
        self.assertEqual(self.available_after(), Decimal('0'))
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, self.receipt.CORRECTED)
        self.assertEqual((self.receipt.reviewed_by_id, self.receipt.reviewed_at, self.receipt.review_reason, self.receipt.proposal), approval)
        self.assertEqual(list(self.incoming.lines.values('account_id', 'debit', 'credit')), original)
        with self.assertRaises(ValidationError): self.propose('60', day=1)
        replacement = self.propose('60.00', day=3)
        self.post_return(replacement)
        self.assertEqual(self.available_after(), Decimal('60'))
        exported = self.client.get(reverse('vouchers:receipt_correction_export', args=[self.batch.public_id]))
        self.assertContains(exported, self.incoming.reference); self.assertContains(exported, entry.reference)
        self.assertContains(exported, 'Correction posted')
        detail = self.client.get(reverse('vouchers:remittance_detail', args=[self.batch.public_id]))
        self.assertContains(detail, 'Receipt reversed by posted correction')

    def test_consumed_withholding_blocks_correction_and_rejection_releases_hold(self):
        self.posted_receipt()
        self.request(correction_date=date(2026, 9, 2))
        with self.assertRaisesMessage(ValidationError, 'already used'):
            self.correction()
        self.post_request(self.case.posting_requests.get(kind='reversal'))
        with self.assertRaisesMessage(ValidationError, 'already used'):
            self.correction()

    def test_rejection_retains_proposal_and_releases_hold(self):
        self.posted_receipt(); item = self.correction()
        review_correction(item=item, actor=self.validator, approve=False, reason='Receipt evidence requires correction')
        self.assertEqual(self.available_after(), Decimal('100'))
        successor = self.correction()
        self.assertEqual(successor.version, 2)

    def test_discard_and_interrupted_materialization_recover_exact_correction(self):
        self.posted_receipt(); item = self.correction()
        review_correction(item=item, actor=self.validator, approve=True, reason='Independent receipt correction review')
        item.refresh_from_db()
        save = RemittancePostingRequest.save
        def interrupt(source, *args, **kwargs):
            if source.status == source.MATERIALIZED: raise RuntimeError('Interrupted correction handoff')
            return save(source, *args, **kwargs)
        with patch.object(RemittancePostingRequest, 'save', interrupt), self.assertRaises(RuntimeError):
            materialize_remittance_journal(item.posting_request, self.preparer)
        entry, created = materialize_remittance_journal(item.posting_request, self.preparer)
        self.assertFalse(created)
        discard_draft(entry, self.preparer, 'Discard incorrect draft reference')
        from .remittances import supersede_discarded_request
        successor = supersede_discarded_request(posting_request=item.posting_request, actor=self.preparer, reason='Retain exact approval')
        item.refresh_from_db(); self.assertEqual(item.posting_request_id, successor.pk)
        entry, _ = materialize_remittance_journal(successor, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)

    def test_nonmirrored_financial_lines_cannot_submit(self):
        self.posted_receipt(); item = self.correction()
        review_correction(item=item, actor=self.validator, approve=True, reason='Independent receipt correction review')
        item.refresh_from_db(); entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        line = entry.lines.filter(debit__gt=0).get()
        type(line).objects.filter(pk=line.pk).update(debit=Decimal('99'))
        with self.assertRaisesMessage(ValidationError, 'exactly reverse'):
            submit_entry(entry, self.preparer)

    def test_unposted_withdrawal_preserves_review_and_releases_hold(self):
        from .receipt_corrections import withdraw_correction
        self.posted_receipt(); item = self.correction()
        review_correction(item=item, actor=self.validator, approve=True, reason='Original independent correction decision')
        item.refresh_from_db(); approved = (item.reviewed_by_id, item.reviewed_at, item.review_reason)
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        with self.assertRaisesMessage(ValidationError, 'Discard'):
            withdraw_correction(item=item, actor=self.validator, reason='Withdraw mistaken correction')
        discard_draft(entry, self.preparer, 'Retain unused correction draft')
        self.validator.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='view_remittance_workbench'))
        self.client.force_login(self.validator)
        url = reverse('vouchers:receipt_correction_withdraw', args=[self.batch.public_id, self.receipt.public_id, item.public_id])
        self.assertEqual(self.client.post(url, {'reason':'Withdraw mistaken correction'}).status_code, 302)
        self.assertEqual(self.client.post(url, {'reason':'Repeated withdrawal'}).status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, item.WITHDRAWN)
        self.assertEqual((item.reviewed_by_id, item.reviewed_at, item.review_reason), approved)
        self.assertEqual(self.available_after(), Decimal('100'))
        self.assertEqual(self.batch.events.filter(action='receipt_correction_withdrawn').count(), 1)
        exported = self.client.get(reverse('vouchers:receipt_correction_export', args=[self.batch.public_id]))
        self.assertContains(exported, 'Withdraw mistaken correction')
        self.assertContains(exported, 'Original independent correction decision')
        self.assertEqual(self.correction().version, 2)
