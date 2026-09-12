from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission, Group
from django.urls import reverse

from accounting.services import submit_entry, post_entry, discard_draft
from . import test_remittance_returns as fixtures
from .models import RemittanceReturn
from .remittance_return_withdrawal import withdraw_return
from .remittance_returns import review_return
from .remittances import (materialize_remittance_journal, reconcile_posted_remittance_entry,
    supersede_discarded_request, withholding_availability)


class RemittanceReturnWithdrawalTests(fixtures.RemittanceReturnTests):
    def approved_return(self):
        self.remitted = self.posted_remittance(); self.batch = self.remitted_source_batch()
        item = self.propose('100.00')
        review_return(item=item, actor=self.validator, approve=True, reason='Original independent approval')
        item.refresh_from_db()
        return item

    def test_http_withdrawal_retains_approval_and_corrected_receipt_can_post(self):
        item = self.approved_return()
        evidence = (item.proposal, item.proposal_checksum, item.review_reason, item.reviewed_by_id, item.reviewed_at)
        self.validator.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='view_remittance_workbench'))
        self.client.force_login(self.validator)
        url = reverse('vouchers:remittance_return_withdraw', args=[self.batch.public_id, item.public_id])
        group, _ = Group.objects.get_or_create(name='Finance UAT Viewer')
        self.validator.groups.add(group)
        self.assertEqual(self.client.post(url, {'reason': 'Must not mutate from UAT'}).status_code, 403)
        self.validator.groups.remove(group)
        reason = 'Receipt figure did not match actual bank credit'
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'reason': reason}).status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, item.WITHDRAWN)
        self.assertEqual(item.posting_request.status, item.posting_request.CANCELLED)
        self.assertEqual((item.proposal, item.proposal_checksum, item.review_reason, item.reviewed_by_id, item.reviewed_at), evidence)
        self.assertEqual(self.batch.events.filter(action='remittance_return_withdrawn').count(), 1)
        page = self.client.get(reverse('vouchers:remittance_detail', args=[self.batch.public_id]))
        self.assertContains(page, reason)
        corrected = self.propose('60.00', day=2)
        self.post_return(corrected)
        rows = withholding_availability(finance_department_id=self.accounting.pk,
            transaction_type=self.transaction_variant.code, as_of_date=date(2026, 9, 3))
        self.assertEqual(rows[0]['available'], Decimal('60.00'))
        content = self.client.get(reverse('vouchers:remittance_return_export', args=[self.batch.public_id]))
        self.assertContains(content, reason)
        self.assertContains(content, 'Original independent approval')
        self.assertContains(content, 'Withdrawn before posting')

    def test_live_draft_blocks_withdrawal_but_discarded_chain_can_close(self):
        item = self.approved_return()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        with self.assertRaisesMessage(ValidationError, 'Discard the unposted'):
            withdraw_return(item=item, actor=self.validator, reason='Correct receipt')
        discard_draft(entry, self.preparer, 'Incorrect draft')
        supersede_discarded_request(posting_request=item.posting_request, actor=self.preparer, reason='Retain source after discard')
        item.refresh_from_db()
        withdraw_return(item=item, actor=self.validator, reason='Replace approved amount')
        item.refresh_from_db()
        self.assertEqual(item.status, RemittanceReturn.WITHDRAWN)
        self.propose('100.00', day=2)

    def test_posted_finance_receipt_cannot_be_withdrawn_before_or_after_handoff(self):
        item = self.approved_return()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        with self.assertRaises(ValidationError):
            withdraw_return(item=item, actor=self.validator, reason='Must retain actual posted receipt')
        reconcile_posted_remittance_entry(entry, self.validator)
        with self.assertRaises(ValidationError):
            withdraw_return(item=item, actor=self.validator, reason='Must retain completed posting')
        item.refresh_from_db()
        self.assertEqual(item.status, item.POSTED)
