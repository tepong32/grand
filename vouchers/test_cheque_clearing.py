from datetime import date
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from accounting.models import JournalEntry
from .test_collection_cheques import CollectionChequeTests, CollectionChequeConcurrencyTests
from .models import CollectionChequeClearance as Clearance
from . import cheque_clearing as clearing
from .collection_corrections import propose as correct
from .collection_outputs import generate, content


class ChequeClearingTests(CollectionChequeTests):
    def sources(self):
        receipt = self.cheque_receipt()
        self.post_source(receipt)
        deposit = self.deposit(receipt, '100', 'CLEAR-DEP')
        self.post_source(deposit)
        receipt.refresh_from_db(); deposit.refresh_from_db()
        return receipt, deposit

    def propose_clearing(self, receipt, deposit, **changes):
        values = dict(receipt=receipt, deposit=deposit, actor=self.treasury_user, cleared_on=date(2026,9,13),
            bank_reference='BANK-CLEAR-001', evidence_reference='Synthetic bank confirmation retained')
        values.update(changes)
        return clearing.propose(**values)

    def test_clearing_keeps_journals_and_frozen_outputs_with_reviewed_withdrawal(self):
        receipt, deposit = self.sources()
        before = generate(source=receipt, actor=self.treasury_user)
        old_bytes = content(before, self.treasury_user)
        journal_ids = list(JournalEntry.objects.values_list('pk', flat=True))
        row = self.propose_clearing(receipt, deposit)
        clearing.review(clearance=row, actor=self.validator, approve=True, reason='Bank confirmed full instrument')
        row.refresh_from_db()
        from uuid import uuid4
        row.public_id = uuid4()
        with self.assertRaises(ValidationError): row.save()
        row.refresh_from_db()
        after = generate(source=receipt, actor=self.treasury_user)
        self.assertIn(b'Bank clearing confirmed', content(after, self.treasury_user))
        for source in (receipt, deposit):
            with self.assertRaises(ValidationError):
                correct(original=source, actor=self.treasury_user, corrected_on=date(2026,9,13), reason='Wrong source')
        clearing.withdraw(clearance=row, actor=self.validator, reason='Bank confirmation was attributed to wrong date')
        self.assertEqual(content(before, self.treasury_user), old_bytes)
        self.assertIn(b'Bank clearing confirmed', content(after, self.treasury_user))
        replacement = self.propose_clearing(receipt, deposit, cleared_on=date(2026,9,14))
        self.assertEqual(replacement.version, 2)
        clearing.review(clearance=replacement, actor=self.validator, approve=False, reason='Return for correct bank evidence')
        correction = correct(original=deposit, actor=self.treasury_user, corrected_on=date(2026,9,14), reason='Wrong deposit')
        with self.assertRaises(ValidationError):
            self.propose_clearing(receipt, deposit)
        self.assertEqual(list(JournalEntry.objects.values_list('pk', flat=True)), journal_ids)
        self.assertIsNotNone(correction.pk)

    def test_clearing_rejects_unposted_wrong_dates_duplicate_and_changed_evidence(self):
        receipt = self.cheque_receipt(); self.post_source(receipt); receipt.refresh_from_db()
        deposit = self.deposit(receipt, '100', 'CLEAR-DEP')
        with self.assertRaises(ValidationError): self.propose_clearing(receipt, deposit)
        self.post_source(deposit); deposit.refresh_from_db()
        with self.assertRaises(ValidationError): self.propose_clearing(receipt, deposit, cleared_on=date(2026,9,11))
        with self.assertRaises(ValidationError): self.propose_clearing(receipt, deposit, bank_reference='')
        row = self.propose_clearing(receipt, deposit)
        with self.assertRaises(ValidationError): self.propose_clearing(receipt, deposit)
        with self.assertRaises((PermissionDenied, ValidationError)):
            clearing.review(clearance=row, actor=self.treasury_user, approve=True, reason='Self')
        snapshot = dict(row.snapshot, amount='99.00')
        Clearance.objects.filter(pk=row.pk).update(snapshot=snapshot, checksum=clearing._digest(snapshot))
        with self.assertRaises(ValidationError):
            clearing.review(clearance=row, actor=self.validator, approve=True, reason='Changed source')

    def test_clearing_web_capture_independent_review_and_retained_print(self):
        receipt, deposit = self.sources()
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:cheque_clearing_create', args=[receipt.public_id]), {
            'deposit':deposit.pk, 'cleared_on':'2026-09-13', 'bank_reference':'WEB-CLEAR', 'evidence_reference':'Bank evidence'})
        self.assertEqual(response.status_code, 302)
        row = receipt.cheque_clearances.get()
        url = reverse('vouchers:cheque_clearing_review', args=[receipt.public_id, row.public_id])
        self.assertEqual(self.client.post(url, {'decision':'approve','reason':'Self'}).status_code, 403)
        self.client.force_login(self.validator)
        self.assertContains(self.client.get(response.url), 'WEB-CLEAR')
        response = self.client.post(url, {'decision':'approve','reason':'Independent bank confirmation'})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), 'Bank clearing confirmed')
        self.assertIn(b'WEB-CLEAR', content(generate(source=receipt,actor=self.validator),self.validator))
        self.assertContains(self.client.get(reverse('vouchers:collection_export')), 'WEB-CLEAR')

    def test_uat_and_other_office_cannot_record_or_decide_clearing(self):
        from django.contrib.auth.models import Group
        from .roles import FINANCE_UAT_VIEWER_GROUP
        receipt, deposit = self.sources()
        row = self.propose_clearing(receipt, deposit)
        self.treasury_user.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied): self.propose_clearing(receipt, deposit)
        self.validator.groups.add(Group.objects.get(name=FINANCE_UAT_VIEWER_GROUP))
        with self.assertRaises(PermissionDenied):
            clearing.review(clearance=row, actor=self.validator, approve=True, reason='UAT')
        self.client.force_login(self.validator)
        response = self.client.post(reverse('vouchers:cheque_clearing_review', args=[receipt.public_id,row.public_id]),
            {'decision':'approve','reason':'UAT'})
        self.assertEqual(response.status_code, 403)
        self.assertContains(self.client.get(reverse('vouchers:collection_detail',args=[receipt.public_id])), 'BANK-CLEAR-001')


class ChequeClearingConcurrencyTests(CollectionChequeConcurrencyTests):
    sources = ChequeClearingTests.sources
    propose_clearing = ChequeClearingTests.propose_clearing

    def test_competing_clearing_proposals_keep_one_active_version(self):
        receipt, deposit = self.sources()
        def compete(number):
            self.propose_clearing(receipt, deposit, bank_reference=f'RACE-{number}')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(receipt.cheque_clearances.count(), 1)

    def test_clearing_and_deposit_correction_share_treasury_lock(self):
        receipt, deposit = self.sources()
        def compete(number):
            if number == 1:
                self.propose_clearing(receipt, deposit)
            else:
                correct(original=deposit, actor=self.treasury_user, corrected_on=date(2026,9,13), reason='Wrong deposit')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
