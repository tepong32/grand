from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission, Group
from django.urls import reverse

from accounting.services import submit_entry, post_entry, create_reversal, discard_draft
from . import test_dated_withholding_corrections as fixtures
from .models import RemittanceReturn
from .remittance_returns import propose_return, review_return
from .remittances import materialize_remittance_journal, reconcile_posted_remittance_entry, withholding_availability


class RemittanceReturnTests(fixtures.DatedWithholdingCorrectionTests):
    def propose(self, amount, day=1):
        self.batch.refresh_from_db()
        return propose_return(batch=self.batch, actor=self.treasury_user,
            returned_on=date(2026, 9, day), receipt_reference=f'Synthetic bank receipt {day}',
            reason='Actual remittance amount returned', filing_basis='Synthetic agency disposition retained for independent review',
            allocations=[{'source_detail': self.remitted.subsidiary_lines.get().pk, 'amount': amount}],
            expected_version=self.batch.state_version)

    def post_return(self, item):
        review_return(item=item, actor=self.validator, approve=True, reason='Independently matched actual bank credit and agency evidence')
        item.refresh_from_db()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        return entry

    def test_partial_returns_restore_only_allocated_withholding_then_allow_correction(self):
        self.remitted = self.posted_remittance()
        self.batch = self.remitted_source_batch()
        original_rows = list(self.remitted.lines.values('account_id', 'debit', 'credit'))
        first = self.propose('40.00')
        with self.assertRaises(ValidationError):
            self.propose('60.01')
        first_entry = self.post_return(first)
        with self.assertRaises(ValidationError):
            self.request(correction_date=date(2026, 9, 2))
        with self.assertRaisesMessage(ValidationError, 'detached reversal'):
            create_reversal(self.remitted, self.preparer, reference='INVALID-DETACHED',
                entry_date=self.remitted.entry_date, period=self.remitted.period, reason='Must retain actual incoming receipt')
        second = self.propose('60.00', day=2)
        second_entry = self.post_return(second)
        self.assertEqual(first_entry.totals, (Decimal('40'), Decimal('40')))
        self.assertEqual(second_entry.totals, (Decimal('60'), Decimal('60')))
        self.assertEqual(list(self.remitted.lines.values('account_id', 'debit', 'credit')), original_rows)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, self.batch.COMPLETED)
        self.assertEqual(self.batch.total_amount, Decimal('100'))
        self.request(correction_date=date(2026, 9, 3))

    def remitted_source_batch(self):
        from .models import RemittancePostingRequest
        return RemittancePostingRequest.objects.get(public_id=self.remitted.source_reference).batch

    def test_interrupted_return_materialization_reuses_exact_journal(self):
        self.remitted = self.posted_remittance(); self.batch = self.remitted_source_batch()
        item = self.propose('100')
        review_return(item=item, actor=self.validator, approve=True, reason='Independent actual receipt review')
        item.refresh_from_db()
        from .models import RemittancePostingRequest
        save = RemittancePostingRequest.save
        def interrupt(request, *args, **kwargs):
            if request.status == request.MATERIALIZED:
                raise RuntimeError('Interrupted default link')
            return save(request, *args, **kwargs)
        with patch.object(RemittancePostingRequest, 'save', interrupt), self.assertRaises(RuntimeError):
            materialize_remittance_journal(item.posting_request, self.preparer)
        entry, created = materialize_remittance_journal(item.posting_request, self.preparer)
        self.assertFalse(created)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        item.refresh_from_db()
        self.assertEqual(item.status, RemittanceReturn.POSTED)

    def test_http_entry_independent_review_and_retained_exports(self):
        self.remitted = self.posted_remittance(); self.batch = self.remitted_source_batch()
        for user in (self.treasury_user, self.validator):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='view_remittance_workbench'))
        self.client.force_login(self.treasury_user)
        url = reverse('vouchers:remittance_return_prepare', args=[self.batch.public_id])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        data = {'returned_on': '2026-09-01', 'receipt_reference': 'HTTP bank receipt',
            'reason': 'Actual returned funds', 'filing_basis': 'Retained agency disposition',
            'expected_version': self.batch.state_version,
            f'amount_{self.remitted.subsidiary_lines.get().pk}': '100.00'}
        group, _ = Group.objects.get_or_create(name='Finance UAT Viewer')
        self.treasury_user.groups.add(group)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.treasury_user.groups.remove(group)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        item = self.batch.returns.get()
        review_url = reverse('vouchers:remittance_return_review', args=[self.batch.public_id, item.public_id])
        self.client.force_login(self.validator)
        work = self.client.get(reverse('finance_operations:my_work'))
        self.assertContains(work, 'Actual remittance returns for review')
        self.assertEqual(self.client.post(review_url, {'decision': 'approve', 'reason': 'Independent bank and filing review'}).status_code, 302)
        item.refresh_from_db()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        with self.assertRaises(ValidationError):
            self.request(correction_date=date(2026, 9, 2))
        reconcile_posted_remittance_entry(entry, self.validator)
        detail = self.client.get(reverse('vouchers:remittance_detail', args=[self.batch.public_id]))
        self.assertContains(detail, 'Return posted')
        original_csv = self.client.get(reverse('vouchers:remittance_export', args=[self.batch.public_id]))
        self.assertContains(original_csv, self.remitted.reference)
        self.assertNotContains(original_csv, entry.reference)
        returned_csv = self.client.get(reverse('vouchers:remittance_return_export', args=[self.batch.public_id]))
        self.assertContains(returned_csv, entry.reference)
        self.assertContains(returned_csv, '100.00,100.00')

    def test_discarded_return_draft_preserves_approval_and_allocation(self):
        self.remitted = self.posted_remittance(); self.batch = self.remitted_source_batch()
        item = self.propose('100.00')
        review_return(item=item, actor=self.validator, approve=True, reason='Independent incoming evidence')
        item.refresh_from_db(); original_request = item.posting_request
        entry, _ = materialize_remittance_journal(original_request, self.preparer)
        discard_draft(entry, self.preparer, 'Discard unposted draft')
        from .remittances import supersede_discarded_request
        successor = supersede_discarded_request(posting_request=original_request, actor=self.preparer, reason='Retain approved return in successor')
        item.refresh_from_db()
        self.assertEqual(item.posting_request_id, successor.pk)
        self.assertEqual(successor.payload, original_request.payload)
        replacement, _ = materialize_remittance_journal(successor, self.preparer)
        submit_entry(replacement, self.preparer); post_entry(replacement, self.validator)
        reconcile_posted_remittance_entry(replacement, self.validator)
