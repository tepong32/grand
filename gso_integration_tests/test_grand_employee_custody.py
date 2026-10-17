from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from profiles.models import EmployeeProfile
from inventory.employee_sources import resolve_employee_custodian
from inventory.models import Asset
from inventory.services import create_asset_transfer, acknowledge_asset_transfer, cancel_asset_transfer, update_asset
from . import test_grand_maintenance


class GrandEmployeeCustodyTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        permissions = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "transfer_asset", "acknowledge_asset_transfer", "view_asset", "change_asset"))
        for actor in (cls.clerk, cls.outsider, cls.no_grant, cls.viewer):
            actor.user_permissions.add(*permissions)
        EmployeeProfile.objects.filter(user=cls.no_grant).update(assigned_department=cls.other)
        cls.no_grant.refresh_from_db()

    def start(self, target=None, **changes):
        target = target or self.outsider
        source = resolve_employee_custodian(actor=self.clerk, user_id=target.pk)
        data = {"destination_employee_id": target.pk, "employee_source_checksum": source["sha256"],
                "transfer_date": timezone.localdate(), "reason": "Documented custody", "reference": "PAR-SYNTHETIC-01"}
        data.update(changes)
        return create_asset_transfer(actor=self.clerk, asset=self.asset, data=data)

    def accept(self):
        return acknowledge_asset_transfer(actor=self.outsider, transfer=self.start())

    def test_named_acknowledgment_preserves_legacy_then_retains_link_and_source_history(self):
        with CaptureQueriesContext(connections["finance"]) as finance:
            transfer = self.start()
            self.asset.refresh_from_db()
            self.assertIsNone(self.asset.custodian_user_id)
            self.assertEqual(self.asset.assigned_office, "Original custodian")
            acknowledge_asset_transfer(actor=self.outsider, transfer=transfer)
        self.assertEqual(len(finance), 0)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk)
        self.assertEqual(self.asset.custodian_snapshot, transfer.destination_employee_snapshot)
        self.assertEqual(self.asset.audit_events.get().snapshot["custodian_user_local_id"], self.outsider.pk)
        next_transfer = self.start(self.no_grant)
        self.assertEqual(next_transfer.source_custodian_user_id, self.outsider.pk)
        self.assertEqual(next_transfer.source_employee_snapshot, self.asset.custodian_snapshot)
        acknowledge_asset_transfer(actor=self.no_grant, transfer=next_transfer)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.no_grant.pk)
        self.assertEqual(self.asset.transfers.filter(status="accepted").count(), 2)

    def test_same_office_delegate_and_self_requested_acknowledgment_are_denied(self):
        transfer = self.start()
        with self.assertRaises(PermissionDenied):
            acknowledge_asset_transfer(actor=self.no_grant, transfer=transfer)
        cancel_asset_transfer(actor=self.clerk, transfer=transfer, reason="Replace selection")
        own = self.start(self.clerk)
        with self.assertRaises(PermissionDenied):
            acknowledge_asset_transfer(actor=self.clerk, transfer=own)

    def test_changed_employee_snapshot_needs_new_review_and_can_be_cancelled(self):
        with self.assertRaises(ValidationError):
            self.start(employee_source_checksum="0" * 64)
        with self.assertRaises(ValidationError):
            self.start(reference="")
        transfer = self.start()
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=self.gso)
        self.outsider.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            acknowledge_asset_transfer(actor=self.outsider, transfer=transfer)
        EmployeeProfile.objects.filter(user=self.outsider).update(assigned_department=self.other)
        self.outsider.refresh_from_db()
        type(self.outsider).objects.filter(pk=self.outsider.pk).update(first_name="Reviewed new name")
        with self.assertRaises(ValidationError):
            acknowledge_asset_transfer(actor=self.outsider, transfer=transfer)
        self.outsider.is_active = False
        self.outsider.save(update_fields=("is_active",))
        cancel_asset_transfer(actor=self.clerk, transfer=transfer, reason="HR assignment changed; recheck documents")
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.custodian_user_id)

    def test_named_custody_cannot_be_erased_by_register_edit_or_legacy_handoff(self):
        self.accept()
        for data in ({"assigned_office": "Changed"}, {"assigned_department": self.gso.pk},
                     {"custodian_user_id": None}, {"custodian_snapshot": {}}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                update_asset(actor=self.clerk, asset=self.asset, data=data)
        update_asset(actor=self.clerk, asset=self.asset, data={"notes": "Equipment inspected"})
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_department_id, self.other.pk)
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk)
        with self.assertRaises(ValidationError):
            create_asset_transfer(actor=self.clerk, asset=self.asset, data={
                "destination_department": self.gso.pk, "destination_custodian": "Free text",
                "transfer_date": timezone.localdate(), "reason": "Attempted downgrade"})
        with self.assertRaises(ProtectedError):
            self.outsider.delete()

    def test_uat_cannot_cancel_named_handoff_even_with_transfer_permission(self):
        transfer = self.start()
        with self.assertRaises(PermissionDenied):
            cancel_asset_transfer(actor=self.viewer, transfer=transfer, reason="Not authorized")
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, transfer.PENDING)

    def test_stale_source_identity_does_not_overwrite_intervening_custody(self):
        transfer = self.start()
        Asset.objects.filter(pk=self.asset.pk).update(custodian_user=self.no_grant)
        with self.assertRaises(ValidationError):
            acknowledge_asset_transfer(actor=self.outsider, transfer=transfer)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.no_grant.pk)
