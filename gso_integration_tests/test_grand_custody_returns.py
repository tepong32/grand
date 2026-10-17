from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from profiles.models import EmployeeProfile
from inventory.models import Asset, AssetReturnEvidence, AssetTransfer
from inventory.services import custody_source, create_asset_transfer, acknowledge_asset_transfer, cancel_asset_transfer, update_asset
from inventory.employee_sources import resolve_employee_custodian
from inventory.custody_returns import record_return, attach_return_evidence, confirm_return, cancel_return
from . import test_grand_employee_custody


class CustodyReturnTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_employee_custody.GrandEmployeeCustodyTests.setUpTestData.__func__(cls)
        source = resolve_employee_custodian(actor=cls.clerk, user_id=cls.outsider.pk)
        handoff = create_asset_transfer(actor=cls.clerk, asset=cls.asset, data={
            "destination_employee_id": cls.outsider.pk, "employee_source_checksum": source["sha256"],
            "transfer_date": timezone.localdate(), "reference": "PAR-RETURN-SOURCE", "reason": "Original custody"})
        acknowledge_asset_transfer(actor=cls.outsider, transfer=handoff)
        cls.asset.refresh_from_db()
        cls.asset.unit_cost = Decimal("123456.78")
        cls.asset.save(update_fields=("unit_cost",))
        EmployeeProfile.objects.filter(user=cls.no_grant).update(assigned_department=cls.gso)
        cls.no_grant.refresh_from_db()
        cls.verifier = cls.no_grant
        permissions = Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("record_asset_return", "verify_asset_return"))
        for actor in (cls.clerk, cls.verifier, cls.outsider, cls.viewer):
            actor.user_permissions.add(*permissions)

    def setUp(self):
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        storage_patch = patch.object(AssetReturnEvidence._meta.get_field("file"), "storage", FileSystemStorage(location=self.storage.name))
        storage_patch.start()
        self.addCleanup(storage_patch.stop)

    def start(self, actor=None, request_id=None):
        return record_return(actor=actor or self.clerk, asset=self.asset, request_id=request_id or uuid4(),
            expected_custody=custody_source(self.asset), data={"transfer_date": timezone.localdate(),
            "reference": "RETURN-SYNTHETIC", "reason": "Received equipment and checked its property tag",
            "return_condition": "damaged", "destination_custodian": "GSO secure storeroom"})

    def evidence(self, transfer, actor=None):
        return attach_return_evidence(actor=actor or self.clerk, transfer=transfer, expected_version=transfer.state_version,
            upload=SimpleUploadedFile("return.pdf", b"%PDF-1.4\nSynthetic witnessed return\n%%EOF", content_type="application/pdf"),
            note="Signed receipt and recorded condition")

    def confirm(self, transfer, actor=None):
        return confirm_return(actor=actor or self.verifier, transfer=transfer,
            expected_version=transfer.state_version, note="Independently checked tag, receipt and receiving location")

    def test_inactive_employee_return_preserves_history_cost_and_status_without_finance(self):
        type(self.outsider).objects.filter(pk=self.outsider.pk).update(is_active=False)
        old_source = self.asset.custodian_snapshot
        with CaptureQueriesContext(connections["finance"]) as finance:
            transfer = self.start()
            self.evidence(transfer)
            transfer.refresh_from_db()
            result = self.confirm(transfer)
        self.assertEqual(len(finance), 0)
        self.assertEqual(result.status, AssetTransfer.ACCEPTED)
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.custodian_user_id)
        self.assertEqual(self.asset.last_custody_return_id, result.pk)
        self.assertEqual(self.asset.assigned_department_id, self.gso.pk)
        self.assertEqual(self.asset.unit_cost, Decimal("123456.78"))
        self.assertEqual(self.asset.status, Asset.ACTIVE)
        self.assertEqual(result.source_employee_snapshot, old_source)
        self.assertEqual(list(result.return_events.values_list("action", flat=True)), ["recorded", "evidence_added", "confirmed"])
        self.assertEqual(self.asset.audit_events.filter(action="returned").count(), 1)
        with self.assertRaises(ValidationError):
            update_asset(actor=self.clerk, asset=self.asset, data={"assigned_office": "Unreviewed custodian"})
        with self.assertRaises(ValidationError):
            create_asset_transfer(actor=self.clerk, asset=self.asset, data={"destination_department": self.other.pk,
                "destination_custodian": "Unlinked person", "reason": "Downgrade", "transfer_date": timezone.localdate()})

    def test_independent_witness_and_verifier_and_explicit_owner_permissions(self):
        for actor in (self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.start(actor=actor)
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=self.gso)
        self.outsider.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            self.start(actor=self.outsider)
        transfer = self.start()
        self.evidence(transfer)
        transfer.refresh_from_db()
        for actor in (self.clerk, self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.confirm(transfer, actor=actor)
        with self.assertRaises(PermissionDenied):
            acknowledge_asset_transfer(actor=self.verifier, transfer=transfer)
        with self.assertRaises(PermissionDenied):
            cancel_asset_transfer(actor=self.clerk, transfer=transfer, reason="Bypass dedicated review")
        self.confirm(transfer)

    def test_missing_changed_and_unsafe_evidence_blocks_confirmation_and_checker_detects_loss(self):
        transfer = self.start()
        with self.assertRaises(ValidationError):
            self.confirm(transfer)
        evidence = self.evidence(transfer)
        transfer.refresh_from_db()
        path = Path(evidence.file.path)
        original = path.read_bytes()
        path.write_bytes(b"changed")
        with self.assertRaises(ValidationError):
            self.confirm(transfer)
        with self.assertRaises(CommandError):
            call_command("check_custody_return_evidence", stdout=StringIO())
        path.write_bytes(original)
        original_name = evidence.file.name
        AssetReturnEvidence.objects.filter(pk=evidence.pk).update(file="../outside.pdf")
        with self.assertRaisesMessage(ValidationError, "unsafe"):
            self.confirm(transfer)
        AssetReturnEvidence.objects.filter(pk=evidence.pk).update(file=original_name)
        call_command("check_custody_return_evidence", stdout=StringIO())
        path.unlink()
        with self.assertRaises(ValidationError):
            self.confirm(transfer)
        path.write_bytes(original)
        self.confirm(transfer)

    def test_stale_versions_custody_and_cancel_keep_original_assignment(self):
        transfer = self.start()
        self.evidence(transfer)
        with self.assertRaises(ValidationError):
            self.confirm(transfer)  # Evidence increased the version.
        transfer.refresh_from_db()
        Asset.objects.filter(pk=self.asset.pk).update(assigned_office="Intervening correction")
        with self.assertRaises(ValidationError):
            self.confirm(transfer)
        cancelled = cancel_return(actor=self.clerk, transfer=transfer, expected_version=transfer.state_version,
                                  note="Reconcile the changed assignment")
        self.assertEqual(cancelled.status, AssetTransfer.CANCELLED)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk)
        self.assertIsNone(self.asset.last_custody_return_id)
        with self.assertRaises(ValidationError):
            self.confirm(cancelled)

    def test_request_retry_is_idempotent_and_evidence_events_cannot_be_replaced(self):
        request_id = uuid4()
        transfer = self.start(request_id=request_id)
        self.assertEqual(self.start(request_id=request_id).pk, transfer.pk)
        evidence = self.evidence(transfer)
        transfer.refresh_from_db()
        self.confirm(transfer)
        self.assertEqual(self.start(request_id=request_id).pk, transfer.pk)
        with self.assertRaises(ValidationError):
            evidence.save()
        with self.assertRaises(ValidationError):
            transfer.return_events.first().delete()
        self.assertEqual(AssetTransfer.objects.filter(kind=AssetTransfer.RETURN).count(), 1)

    def test_return_during_maintenance_preserves_case_and_later_closure_preserves_custody(self):
        from inventory.maintenance import open_maintenance, update_maintenance, close_maintenance
        case = open_maintenance(actor=self.clerk, asset=self.asset,
            data={"reported_date": timezone.localdate(), "problem": "Inspect damaged equipment"})
        self.asset.refresh_from_db()
        maintenance_status = self.asset.status
        transfer = self.start()
        self.evidence(transfer)
        transfer.refresh_from_db()
        self.confirm(transfer)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, maintenance_status)
        case.refresh_from_db()
        self.assertEqual(case.state_version, 1)
        case = update_maintenance(actor=self.clerk, case=case, expected_version=1,
            data={"work_performed": "Inspected casing and verified operation", "documented_cost": "0.00"})
        close_maintenance(actor=self.clerk, case=case, expected_version=2, action="completed",
            finished_date=timezone.localdate(), note="Inspection complete", outcome="active")
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.custodian_user_id)
        self.assertEqual(self.asset.last_custody_return_id, transfer.pk)
        self.assertEqual(self.asset.assigned_office, "GSO secure storeroom")
        self.assertEqual(self.asset.unit_cost, Decimal("123456.78"))
