from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_unsigned_copies as fixtures
from . import form1_signed_copies as signed, form1_final_issues as final, form1_unsigned_copies as unsigned
from .models import Form1SignedReceipt as Receipt, Form1SignedReview as Review, Form1FinalIssue as Issue


class Form1SignedFixture(fixtures.Form1UnsignedFixture):
    def setUp(self):
        super().setUp()
        for actor in (self.preparer, self.reviewer, self.checker):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget', codename__in=[
                *(action+'_form1_signed_copies' for action in ('record','verify','view','export')),
                *(action+'_form1_signed_packages' for action in ('issue','view','export'))]))

    def signed_upload(self, copy, *, pages=None):
        writer = PdfWriter()
        original = PdfReader(BytesIO(bytes(copy.document)))
        for page in list(original.pages)[:pages]:
            writer.add_page(page)
        writer.add_metadata({'/Title': 'SYNTHETIC declared returned-copy fixture; NO REAL SIGNATURES'})
        buffer = BytesIO(); writer.write(buffer)
        return SimpleUploadedFile('synthetic-return.pdf', buffer.getvalue(), content_type='application/pdf')

    def receipt_dates(self, copy):
        return {entity: {role: timezone.localtime().date() for role in signed.signing.ROLES}
                for entity in signed.entities(copy)}

    def capture_return(self, copy, **changes):
        args = dict(copy=copy, actor=self.preparer, upload=self.signed_upload(copy), signed_dates=self.receipt_dates(copy),
            received_on=timezone.localtime().date(), received_by='Synthetic on-site recipient',
            custody_reference='TEST physical handover reference', custody_location='TEST Budget paper file',
            correction_reason='Synthetic physical return declaration, not an actual signature', expected_latest=0)
        args.update(changes)
        return signed.record(**args)

    def inspection_checks(self, copy):
        keys = [*signed.CHECKS, *(entity+':'+role for entity in signed.entities(copy) for role in signed.signing.ROLES)]
        return {key: dict(verified=True, basis='Synthetic independently witnessed fixture finding: '+key) for key in keys}

    def inspect_return(self, receipt, **changes):
        args = dict(receipt=receipt, actor=self.reviewer, approve=True, checks=self.inspection_checks(receipt.copy),
                    note='Synthetic independent physical/source inspection, no actual LGU acceptance')
        args.update(changes)
        return signed.review(**args)

    def issue_return(self, receipt, **changes):
        args = dict(receipt=receipt, actor=self.reviewer, reference='Synthetic final Form 1 issued-package reference')
        args.update(changes)
        return final.issue(**args)


class Form1SignedCopyTests(Form1SignedFixture):
    def test_corrupt_predecessor_row_cannot_seed_a_successor(self):
        copy = self.release_copy(self.unsigned_preparation())
        receipt = self.capture_return(copy)
        self.inspect_return(receipt)
        issued = self.issue_return(receipt)
        original = final.document(issued,self.checker)
        version = issued.version
        journals = JournalEntry.objects.count()
        # Simulate an out-of-band row error; normal model saves remain forbidden.
        Issue.objects.filter(pk=issued.pk).update(version=version+1)
        issued.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.capture_return(copy,expected_latest=1,predecessor=issued)
        self.assertEqual(Receipt.objects.count(),1)
        self.assertEqual(Review.objects.count(),1)
        self.assertEqual(Issue.objects.count(),1)
        self.assertEqual(JournalEntry.objects.count(),journals)
        Issue.objects.filter(pk=issued.pk).update(version=version)
        issued.refresh_from_db()
        self.assertEqual(final.document(issued,self.checker),original)

    def test_complete_return_independent_verification_and_original_issued_bundle_are_separate(self):
        copy = self.release_copy(self.unsigned_preparation())
        original = unsigned.document(copy, self.checker)
        journal_count = JournalEntry.objects.count()
        receipt = self.capture_return(copy)
        pending = signed.snapshot(receipt, self.checker)
        self.assertEqual(pending['status'], 'unverified')
        for flag in ('statutorily_certified','chief_executive_approved','form_issued','cash_available'):
            self.assertIs(pending[flag], False)
        with self.assertRaises(ValidationError): self.issue_return(receipt)
        self.inspect_return(receipt)
        self.assertEqual(signed.snapshot(receipt,self.checker)['status'], 'verified')
        issued = self.issue_return(receipt)
        content, retained = final.document(issued, self.checker)
        self.assertTrue(retained['form_issued']); self.assertIs(retained['cash_available'],False)
        self.assertEqual(set(receipt.payload['physical_return']['signed_dates']),set(signed.entities(copy)))
        with ZipFile(BytesIO(content)) as archive:
            self.assertEqual(set(archive.namelist()), {'issuance.json','unsigned-copy.json','signed-evidence.json',
                                                      'unsigned-form1.pdf','signed-form1.pdf'})
            self.assertEqual(archive.read('unsigned-form1.pdf'),original[0])
            self.assertEqual(archive.read('signed-form1.pdf'),bytes(receipt.document))
        self.assertEqual(unsigned.document(copy,self.checker), original)
        self.assertEqual(JournalEntry.objects.count(),journal_count)
        for model in (Receipt, Review, Issue):
            self.assertIn(model._meta.db_table, connections['finance'].introspection.table_names())
            self.assertNotIn(model._meta.db_table, connections['default'].introspection.table_names())
        for record in (receipt, Review.objects.get(receipt=receipt), issued):
            with self.assertRaises(ValidationError): record.save()
            with self.assertRaises(ValidationError): record.delete()
        with self.assertRaises(ValidationError): self.inspect_return(receipt)
        with self.assertRaises(ValidationError): self.issue_return(receipt)
        # Later source changes do not rewrite history or require rerendering/repacking.
        self.prepare_forecast(expected_latest=1)
        with patch.object(final, 'ZipFile', wraps=ZipFile) as zip_class:
            self.assertEqual(final.document(issued,self.checker), (content,retained))
            self.assertTrue(all((call.args[1] if len(call.args)>1 else call.kwargs.get('mode','r')) == 'r'
                                for call in zip_class.call_args_list))

    def test_dates_complete_pages_designations_and_independence_fail_closed(self):
        copy = self.release_copy(self.unsigned_preparation())
        with self.assertRaises(ValidationError): self.capture_return(copy,signed_dates={})
        with self.assertRaises(ValidationError): self.capture_return(copy,upload=self.signed_upload(copy,pages=1))
        with self.assertRaises(ValidationError):
            self.capture_return(copy,upload=SimpleUploadedFile('broken.pdf',b'%PDF-broken'))
        dates = self.receipt_dates(copy)
        entity = next(iter(dates)); dates[entity]['treasurer'] += timedelta(days=1)
        with self.assertRaises(ValidationError): self.capture_return(copy,signed_dates=dates)
        dates = self.receipt_dates(copy); dates[entity]['chief_executive'] -= timedelta(days=1)
        with self.assertRaises(ValidationError): self.capture_return(copy,signed_dates=dates)
        # The pure validator checks authority on the actual signing date, not
        # merely the preparation's intended date.
        original_to = copy.preparation.payload['signatories']['treasurer']['valid_to']
        copy.preparation.payload['signatories']['treasurer']['valid_to'] = (timezone.localtime().date()-timedelta(days=1)).isoformat()
        with self.assertRaises(ValidationError):
            signed._facts(copy,self.receipt_dates(copy),timezone.localtime().date(),'Person','Reference','Location',timezone.localtime().date())
        copy.preparation.payload['signatories']['treasurer']['valid_to'] = original_to
        with self.assertRaises(PermissionDenied): self.capture_return(copy,actor=self.checker)
        self.assertFalse(Receipt.objects.exists())
        incomplete = self.receipt_dates(copy); incomplete[entity]['treasurer'] = None
        partial = self.capture_return(copy,signed_dates=incomplete)
        self.assertIs(signed.snapshot(partial,self.checker)['payload']['physical_return']['signed_dates'][entity]['treasurer'],None)
        with self.assertRaises(ValidationError): self.inspect_return(partial)
        checks = self.inspection_checks(copy); checks[entity+':treasurer']['verified'] = False
        self.inspect_return(partial,approve=False,checks=checks)
        with self.assertRaises(ValidationError): self.issue_return(partial)
        receipt = self.capture_return(copy,expected_latest=1)
        with self.assertRaises(ValidationError): self.inspect_return(receipt,actor=self.preparer)
        with self.assertRaises(PermissionDenied): self.inspect_return(receipt,actor=self.checker)
        group = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0]
        self.reviewer.groups.add(group)
        with self.assertRaises(PermissionDenied): self.inspect_return(receipt)
        self.reviewer.groups.remove(group)
        checks = self.inspection_checks(copy); checks.pop(next(iter(checks)))
        with self.assertRaises(ValidationError): self.inspect_return(receipt,checks=checks)
        checks = self.inspection_checks(copy); checks['complete_pages']['verified'] = False
        with self.assertRaises(ValidationError): self.inspect_return(receipt,checks=checks)
        self.inspect_return(receipt,approve=False,checks=checks)
        self.assertEqual(signed.snapshot(receipt,self.checker)['status'],'returned')
        with self.assertRaises(ValidationError): self.issue_return(receipt)

    def test_successor_scan_issuance_lineage_and_atomic_combined_action(self):
        copy = self.release_copy(self.unsigned_preparation())
        first = self.capture_return(copy)
        second = self.capture_return(copy,expected_latest=1)
        with self.assertRaises(ValidationError): self.inspect_return(first)
        with self.assertRaises(ValidationError):
            final.verify_and_issue(receipt=second,actor=self.reviewer,checks=self.inspection_checks(copy),
                                   note='Synthetic complete inspection',reference='')
        self.assertFalse(Review.objects.filter(receipt=second).exists())
        issued = final.verify_and_issue(receipt=second,actor=self.reviewer,checks=self.inspection_checks(copy),
            note='Synthetic complete independent inspection',reference='Synthetic first issue')
        original = final.document(issued,self.checker)
        with self.assertRaises(ValidationError): self.capture_return(copy,expected_latest=2)
        third = self.capture_return(copy,expected_latest=2,predecessor=issued,
                                    correction_reason='Synthetic replacement scan; original issue retained')
        self.inspect_return(third)
        successor = self.issue_return(third)
        self.assertEqual(successor.predecessor_id,issued.pk)
        self.assertEqual(successor.version,2)
        self.assertEqual(final.document(issued,self.checker),original)
        with self.assertRaises(ValidationError): self.capture_return(copy,expected_latest=3,predecessor=issued)
        # Source staleness blocks new verification but not evidence retrieval.
        fourth = self.capture_return(copy,expected_latest=3,predecessor=successor)
        self.prepare_forecast(expected_latest=1)
        with self.assertRaises(ValidationError): self.inspect_return(fourth)
        self.assertEqual(final.document(issued,self.checker),original)

    def test_source_permissions_and_rehashed_corruption_cannot_fabricate_approval_or_archive(self):
        copy = self.release_copy(self.unsigned_preparation())
        receipt = self.capture_return(copy)
        original_data = deepcopy(receipt.payload)
        corrupt = deepcopy(original_data); corrupt['form_issued'] = True
        Receipt.objects.filter(pk=receipt.pk).update(payload=corrupt,payload_checksum=checksum(corrupt))
        with self.assertRaises(ValidationError): signed.snapshot(receipt,self.checker)
        Receipt.objects.filter(pk=receipt.pk).update(payload=original_data,payload_checksum=checksum(original_data))
        self.inspect_return(receipt); issued = self.issue_return(receipt)
        original = final.document(issued,self.checker)
        # A correction must refuse a predecessor whose original archive is
        # missing/corrupt, even when its metadata checksum still matches.
        Issue.objects.filter(pk=issued.pk).update(archive=b'changed predecessor bytes')
        with self.assertRaises(ValidationError):
            self.capture_return(copy,expected_latest=1,predecessor=issued)
        self.assertEqual(Receipt.objects.filter(copy=copy).count(),1)
        Issue.objects.filter(pk=issued.pk).update(archive=bytes(issued.archive))
        self.assertEqual(signed._previous(issued,copy)['archive_sha256'],issued.archive_checksum)
        permission = Permission.objects.get(content_type__app_label='budget',codename='export_budget_receipt_forecasts')
        self.checker.user_permissions.remove(permission)
        self.assertTrue(final.snapshot(issued,self.checker)['form_issued'])
        with self.assertRaises(PermissionDenied): final.document(issued,self.checker)
        self.checker.user_permissions.add(permission)
        data = bytes(issued.archive)
        # Even a matching archive checksum cannot excuse changed member bytes.
        buffer = BytesIO()
        with ZipFile(BytesIO(data)) as source, ZipFile(buffer,'w') as target:
            for name in source.namelist():
                target.writestr(name,b'changed' if name=='signed-form1.pdf' else source.read(name))
        corrupt = buffer.getvalue()
        Issue.objects.filter(pk=issued.pk).update(archive=corrupt,archive_checksum=sha256(corrupt).hexdigest())
        with self.assertRaises(ValidationError): final.snapshot(issued,self.checker)
        Issue.objects.filter(pk=issued.pk).update(archive=data,archive_checksum=issued.archive_checksum)
        self.assertEqual(final.document(issued,self.checker),original)
