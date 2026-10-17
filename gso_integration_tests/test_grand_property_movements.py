from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from tempfile import TemporaryDirectory
from . import test_grand_maintenance
User = get_user_model()

from inventory import receiving, services, custody_returns, employee_sources, property_movements
from inventory import property_determinations as properties
service = property_movements
from inventory.models import Asset, AssetTransfer, AssetReturnEvidence, ReceivingEvidence, StockMovement, PropertyMovementRecord
from inventory.models import PropertyDetermination, AssetDisposalAttachment


class PropertyMovementChainTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.actor, self.reviewer = self.clerk, self.no_grant
        grants = Permission.objects.filter(content_type__app_label="inventory", codename__in=(
            "view_asset", "record_property_determination", "review_property_determination",
            "record_property_movement", "review_property_movement"))
        for actor in (self.actor, self.reviewer, self.outsider, self.viewer):
            actor.user_permissions.add(*grants)
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        for model in (PropertyDetermination, PropertyMovementRecord, AssetDisposalAttachment):
            storage = patch.object(model._meta.get_field("file"), "storage", FileSystemStorage(location=root.name))
            storage.start()
            self.addCleanup(storage.stop)

    def determine(self):
        row = properties.record(actor=self.actor, asset=self.asset, request_id=uuid4(),
            expected_source=properties.source_basis(self.asset), expected_predecessor=None,
            data=dict(treatment="semi_expendable", reference="Classification source", source_date=timezone.localdate(),
                source_authority="Supplied determination", property_class="Equipment", fund_label="General fund",
                useful_life=None, life_unit="", life_basis="", life_start=None, expires_on=None, reason="Synthetic packet"),
            upload=self.upload())
        return properties.decide(actor=self.reviewer, row=row, expected_version=1,
            action="verify", note="Independent document check")

    def upload(self):
        return SimpleUploadedFile("source.pdf", b"%PDF-synthetic source")

    def data(self, **changes):
        data = dict(movement_date=timezone.localdate()-timedelta(days=2), within_day_order=0,
            reference="Opening source", item_number="", office_officer_label="GSO stockroom",
            stock_delta=0, opening_quantity=1, unit_cost=None, remarks="Documented end-of-day stock")
        data.update(changes)
        return data

    def record(self, **changes):
        args = dict(actor=self.actor, asset=self.asset, determination_id=self.determination.pk,
            source_kind="opening", source_id=None, request_id=uuid4(), expected_predecessor=None,
            data=self.data(), upload=self.upload())
        args.update(changes)
        if "expected_source" not in args:
            _, args["expected_source"], _ = service.source_basis(asset=args["asset"],
                determination_id=args["determination_id"], source_kind=args["source_kind"], source_id=args["source_id"])
        return service.record(**args)

    def decide(self, row, **changes):
        args = dict(actor=self.reviewer, row=row, expected_version=row.state_version,
                    action="verify", note="Checked source, chronology and stock effect")
        args.update(changes)
        return service.decide(**args)

    def test_real_receipt_issue_return_disposal_sources_project_without_repeating_movements(self):
        for actor in (self.actor, self.reviewer):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory"))
        self.actor, self.reviewer = User.objects.get(pk=self.actor.pk), User.objects.get(pk=self.reviewer.pk)
        borrower = self.outsider
        borrower.user_permissions.add(*Permission.objects.filter(content_type__app_label="inventory",
            codename__in=("view_asset", "acknowledge_asset_transfer")))
        storage = PropertyMovementRecord._meta.get_field("file").storage
        for model in (ReceivingEvidence, AssetReturnEvidence):
            patched = patch.object(model._meta.get_field("file"), "storage", storage)
            patched.start()
            self.addCleanup(patched.stop)
        today = timezone.localdate()
        receipt = receiving.create_receipt(actor=self.actor, data=dict(supplier="Synthetic vendor",
            delivery_reference="DR-CHAIN", delivery_date=today-timedelta(days=4),
            inspection_date=today-timedelta(days=4), inspection_reference="IAR-CHAIN",
            inspector_label="Independent inspector", evidence_reference="Retained delivery and inspection"))
        line = receiving.save_receipt_line(actor=self.actor, receipt=receipt, expected_version=receipt.state_version,
            data=dict(kind="asset", description="Chain equipment", unit="piece", delivered_quantity=1,
                accepted_quantity=1, rejected_quantity=0, unit_cost=Decimal("12500.00"),
                property_tag="MOVEMENT-CHAIN", asset_kind="equipment"))
        for kind in ("delivery", "inspection"):
            receipt.refresh_from_db()
            receiving.attach_receipt_evidence(actor=self.actor, receipt=receipt,
                expected_version=receipt.state_version, kind=kind, upload=self.upload(), note="Synthetic retained source")
        receipt.refresh_from_db()
        receipt = receiving.submit_receipt(actor=self.actor, receipt=receipt, expected_version=receipt.state_version)
        receiving.accept_receipt(actor=self.reviewer, receipt=receipt,
            expected_version=receipt.state_version, note="Independent acceptance")
        line.refresh_from_db()
        self.asset = line.registered_asset
        self.determination = self.determine()
        employee = employee_sources.resolve_employee_custodian(actor=self.actor, user_id=borrower.pk)
        handoff = services.create_asset_transfer(actor=self.actor, asset=self.asset, request_id=uuid4(),
            expected_custody=services.custody_source(self.asset), data=dict(destination_employee_id=borrower.pk,
                employee_source_checksum=employee["sha256"], transfer_date=today-timedelta(days=3),
                reason="Documented issue", reference="ICS-CHAIN"))
        services.acknowledge_asset_transfer(actor=borrower, transfer=handoff)
        self.asset.refresh_from_db()
        returned = custody_returns.record_return(actor=self.actor, asset=self.asset, request_id=uuid4(),
            expected_custody=services.custody_source(self.asset), data=dict(transfer_date=today-timedelta(days=2),
                reference="RETURN-CHAIN", reason="Witnessed physical return", return_condition="serviceable",
                destination_custodian="GSO stockroom"))
        custody_returns.attach_return_evidence(actor=self.actor, transfer=returned, expected_version=returned.state_version,
            upload=self.upload(), note="Witnessed return source")
        returned.refresh_from_db()
        custody_returns.confirm_return(actor=self.reviewer, transfer=returned,
            expected_version=returned.state_version, note="Independently checked return")
        self.asset.refresh_from_db()
        picture = BytesIO()
        Image.new("RGB", (2, 2), "white").save(picture, format="PNG")
        disposal = services.submit_asset_disposal_request(actor=self.actor, asset=self.asset,
            data=dict(reason="Supplied disposal authority", condition_details="Synthetic appraisal",
                photos=[SimpleUploadedFile("condition.png", picture.getvalue(), content_type="image/png")],
                signed_request=self.upload()))
        services.review_asset_disposal_case(actor=self.reviewer, case=disposal, data={"action": "under_review"})
        services.review_asset_disposal_case(actor=self.reviewer, case=disposal,
            data=dict(action="authorized", authority_reference="AUTH-CHAIN", authority_document=self.upload()))
        services.review_asset_disposal_case(actor=self.reviewer, case=disposal,
            data=dict(action="disposed", disposal_method="destruction", disposal_date=today-timedelta(days=1),
                completion_reference="DISPOSAL-CHAIN", completion_document=self.upload()))
        self.asset.refresh_from_db()
        retained_asset = Asset.objects.values().get(pk=self.asset.pk)
        retained_transfers = list(AssetTransfer.objects.filter(asset=self.asset).values())
        audit_count, stock_count = self.asset.audit_events.count(), StockMovement.objects.count()
        self.decide(self.record(data=self.data(movement_date=today-timedelta(days=5), opening_quantity=0)))
        for kind, source, days, effect in (("receipt", line, 4, 1), ("handoff", handoff, 3, -1),
                                          ("return", returned, 2, 1), ("disposal", disposal, 1, -1)):
            self.decide(self.record(source_kind=kind, source_id=source.pk,
                data=self.data(movement_date=today-timedelta(days=days), within_day_order=1,
                    opening_quantity=None, stock_delta=effect, item_number="CHAIN-01", reference=f"SOURCE-{kind}")))
        projection = property_movements.project(actor=self.actor, asset=self.asset, cutoff=today)
        self.assertEqual(projection["issues"], [])
        self.assertEqual(projection["balance"], 0)
        self.assertEqual([row["balance"] for row in projection["rows"]], [1, 0, 1, 0])
        self.assertEqual(Asset.objects.values().get(pk=self.asset.pk), retained_asset)
        self.assertEqual(list(AssetTransfer.objects.filter(asset=self.asset).values()), retained_transfers)
        self.assertEqual(self.asset.audit_events.count(), audit_count)
        self.assertEqual(StockMovement.objects.count(), stock_count)

    def test_native_scope_uat_and_explicit_grants_with_no_finance_access(self):
        self.determination = self.determine()
        for actor in (self.outsider, self.viewer, self.super_no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.record(actor=actor)
        with CaptureQueriesContext(connections["finance"]) as finance:
            row = self.record()
            self.decide(row)
            self.client.force_login(self.actor)
            self.assertContains(self.client.get(reverse("inventory:property-movements", args=[self.asset.pk])), "Opening source")
            self.assertContains(self.client.get(reverse("inventory:property-movement-detail", args=[row.pk])), "Opening source")
        self.assertEqual(len(finance), 0)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("inventory:property-movement-detail", args=[row.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("inventory:property-movement-evidence", args=[row.pk])).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("inventory:property-movement-new", args=[self.asset.pk])).status_code, 403)
        self.assertContains(self.client.get(reverse("inventory:property-movement-detail", args=[row.pk])), "Opening source")
        self.client.force_login(self.super_no_grant)
        self.assertEqual(self.client.get(reverse("inventory:property-movements", args=[self.asset.pk])).status_code, 403)
