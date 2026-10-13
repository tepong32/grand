from copy import deepcopy

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_package_reviews as fixtures
from . import form1_treatments as service, form1_philhealth as ph, form1_packages as packages
from .models import Form1TreatmentProposal, Form1TreatmentDecision


class Form1TreatmentTests(fixtures.Form1PackageReviewFixture):
    def retain_original_package(self, claim=False):
        if not claim:
            return self.retain()
        body = ph.verify(self.ph_source)
        parts = [{key: row[key] for key in ph.PART_FIELDS} for row in body['parts']]
        catalog = {row['key']: row for row in body['inventory']['payload']['catalog']}
        receipt = next(row for row in parts if catalog[row['source']]['kind'] == 'receipt'
            and catalog[row['source']]['column'] == 'estimate')
        expense = next(row for row in parts if catalog[row['source']]['kind'] == 'expense'
            and catalog[row['source']]['column'] == 'estimate' and row['amount'] == '40.00')
        expense['treatment'] = 'shf'
        receipt.update(treatment='claimed_overlap', counterpart=expense['source'])
        source, documents = ph.prepare(source=body['inventory'], actor=self.preparer, evidence=self.evidence,
            parts=parts, coverage=body['coverage'], coverage_reference='Synthetic complete source policy',
            authority=SimpleUploadedFile('original-policy.pdf', self.documents['authority']),
            reconciliation=SimpleUploadedFile('original-worksheet.pdf', self.documents['reconciliation']))
        return self.retain(envelope=self.assembled(philhealth_source=source), documents=documents)

    def findings(self, package, claim_finding='confirm_overlap'):
        original = package.payload['assembly']['payload']['philhealth_source']['payload']
        return [dict(part=part['key'], finding=claim_finding if part['treatment'] == 'claimed_overlap'
                else part['treatment'], basis='Synthetic exact signed original-part assessment',
            funding_reference='Synthetic original funding authority; no local applicability claim',
            lineage_reference='Synthetic exact original receipt/restriction/expense linkage')
            for part in original['parts']]

    def prepare_treatment(self, package, **changes):
        args = dict(findings=self.findings(package),
            authority=SimpleUploadedFile('assessment-policy.pdf', b'%PDF-1.4\nSynthetic factual review authority'),
            reconciliation=SimpleUploadedFile('assessment.pdf', b'%PDF-1.4\nSynthetic complete funding reconciliation'),
            reference='Synthetic source-bound factual findings', expected_latest=0)
        args.update(changes)
        return service.prepare(package, self.preparer, **args)

    def decide_treatment(self, record, role='budget', **changes):
        args = dict(actor=self.reviewers[role], role=role, approve=True,
            checks={key: dict(verified=True, basis='Synthetic independent '+key+' inspection')
                for key in service.CHECKS[role]}, authority='Synthetic designated original office reviewer',
            note='Factual finding only; no numeric adjustment or statutory certification')
        args.update(changes)
        return service.review(record, **args)

    def test_confirmed_claim_review_retains_unknown_arithmetic_and_originals(self):
        package = self.retain_original_package(claim=True)
        original = deepcopy(package.payload)
        before = JournalEntry.objects.count()
        proposal = self.prepare_treatment(package)
        for role in ('budget', 'accounting', 'treasury'):
            self.decide_treatment(proposal, role)
        snapshot = service.snapshot(proposal, self.checker, export=True)
        self.assertEqual(snapshot['review']['status'], 'reviewed')
        self.assertTrue(snapshot['review']['factual_review_complete'])
        self.assertIs(snapshot['review']['presentation_recipe'], None)
        for flag in ('numeric_adjustment_approved', 'form_issued', 'cash_available'):
            self.assertIs(snapshot['review'][flag], False)
        self.assertIsNone(original['assembly']['payload']['members'][0]['net_ending']['estimate'])
        self.assertEqual(packages.snapshot(package, self.preparer)['payload'], original)
        self.assertEqual(JournalEntry.objects.count(), before)
        self.assertEqual(len(snapshot['payload']['draft']['payload']['findings']),
            len(original['assembly']['payload']['philhealth_source']['payload']['parts']))

    def test_rejected_claim_is_explicit_and_does_not_resolve_remaining_shf(self):
        package = self.retain_original_package(claim=True)
        proposal = self.prepare_treatment(package, findings=self.findings(package, 'reject_overlap'))
        body = service.verify(proposal)
        claim = next(row for row in body['findings'] if row['finding'] == 'reject_overlap')
        self.assertEqual(claim['original_part']['treatment'], 'claimed_overlap')
        self.assertTrue(claim['original_part']['counterpart'])
        self.assertTrue(any(row['finding'] == 'shf' for row in body['findings']))
        self.assertFalse(body['numeric_adjustment_approved'])
        self.assertIsNone(package.payload['assembly']['payload']['members'][0]['net_ending']['estimate'])

    def test_full_partition_invalid_kind_amount_and_documents_roll_back(self):
        package = self.retain_original_package()
        findings = self.findings(package)
        for inputs in (findings[:-1], findings+[findings[0]],
            [dict(row, amount='999.00') for row in findings],
            [dict(row, finding='invented_offset') for row in findings]):
            with self.assertRaises(ValidationError):
                self.prepare_treatment(package, findings=inputs)
        with self.assertRaises(ValidationError):
            self.prepare_treatment(package, authority=SimpleUploadedFile('not-policy.pdf', b'not a document'))
        self.assertEqual(Form1TreatmentProposal.objects.count(), 0)

    def test_roles_maker_checks_uat_and_export_source_revocation(self):
        package = self.retain_original_package()
        proposal = self.prepare_treatment(package)
        with self.assertRaises(PermissionDenied):
            self.decide_treatment(proposal, actor=self.preparer)
        permission = Permission.objects.get(content_type__app_label='budget', codename='review_form1_package_budget')
        self.preparer.user_permissions.add(permission)
        with self.assertRaises(ValidationError):
            self.decide_treatment(proposal, actor=self.preparer)
        checks = {key: dict(verified=True, basis='Synthetic explicit source inspection')
            for key in service.CHECKS['budget']}
        checks['funding_authority']['verified'] = 'true'
        with self.assertRaises(ValidationError):
            self.decide_treatment(proposal, checks=checks)
        group, _ = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)
        self.reviewer.groups.add(group)
        with self.assertRaises(PermissionDenied):
            self.decide_treatment(proposal)
        self.reviewer.groups.remove(group)
        self.checker.user_permissions.remove(Permission.objects.get(
            content_type__app_label='budget', codename='export_budget_receipt_forecasts'))
        with self.assertRaises(PermissionDenied):
            service.snapshot(proposal, self.checker, export=True)
        self.assertEqual(Form1TreatmentDecision.objects.count(), 0)

    def test_versions_returns_source_successors_preserve_review_history(self):
        package = self.retain_original_package()
        first = self.prepare_treatment(package)
        decision = self.decide_treatment(first)
        second = self.prepare_treatment(package, expected_latest=1)
        self.assertEqual(second.predecessor_id, first.pk)
        with self.assertRaises(ValidationError):
            self.decide_treatment(first, 'accounting')
        returned = self.decide_treatment(first, 'accounting', approve=False)
        history = service.snapshot(first, self.treasurer)
        self.assertEqual(history['review']['status'], 'returned')
        self.assertEqual(history['review']['decisions'][0]['checksum'], decision.payload_checksum)
        with self.assertRaises(ValidationError):
            self.decide_treatment(first, 'treasury')
        self.prepare_forecast(expected_latest=1)
        with self.assertRaises(ValidationError):
            self.decide_treatment(second)
        self.decide_treatment(second, approve=False)
        self.assertEqual(service.snapshot(first, self.treasurer), history)
        with self.assertRaises(ValidationError):
            returned.save()

    def test_immutable_bytes_and_rehashed_source_corruption_fail_closed(self):
        package = self.retain_original_package()
        record = self.prepare_treatment(package)
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()
        attachment = record.attachments.first()
        with self.assertRaises(ValidationError):
            attachment.save()
        old = deepcopy(record.payload)
        record.payload['draft']['payload']['findings'][0]['original_part']['amount'] = '999.00'
        record.payload['draft']['checksum'] = checksum(record.payload['draft']['payload'])
        record.payload_checksum = checksum(record.payload)
        with self.assertRaises(ValidationError):
            service.verify(record)
        record.payload = old
        record.payload_checksum = checksum(old)
        label = record.department_label
        record.department_label = 'Substituted original office'
        with self.assertRaises(ValidationError):
            service.verify(record)
        record.department_label = label
        decision = self.decide_treatment(record)
        decision.payload = {'incomplete': True}
        decision.payload_checksum = checksum(decision.payload)
        with self.assertRaises(ValidationError):
            service._state(record, [decision])
        attachment.data = b'%PDF-1.4\nchanged original'
        with self.assertRaises(ValidationError):
            service.verify(record, attachments=[attachment, *record.attachments.exclude(pk=attachment.pk)])
