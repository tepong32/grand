"""Run explicitly with scripts/run_grand_source_tests.py, not standalone discovery."""
from datetime import date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, connection, transaction, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from finance.models import FinanceConfigurationRelease, FinanceParty
from vouchers.models import VoucherCase, DisbursementVoucher, VoucherLineItem
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from inventory.finance_sources import resolve_claim_line
from inventory.models import ReceivingReceipt, ReceivingEvent
from inventory.receiving import create_receipt


class GrandClaimSourceTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.gso = Department.objects.create(name="Synthetic GSO", slug="gso-source-test")
        cls.other = Department.objects.create(name="Synthetic other office", slug="other-source-test")
        cls.finance = Department.objects.create(name="Synthetic Accounting", slug="acctg-source-test")
        def actor(name, department, permissions=()):
            user = get_user_model().objects.create_user(username=name, email=f"{name}@example.test",
                                                        first_name="Synthetic", last_name=name)
            EmployeeProfile.objects.update_or_create(user=user, defaults={"assigned_department": department})
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="vouchers", codename__in=permissions))
            # The creation signal cached the initial unassigned reverse relation.
            # Real requests load a fresh user after employee provisioning.
            user.refresh_from_db()
            assert user.employeeprofile.assigned_department_id == department.pk
            return user
        cls.clerk = actor("source-clerk", cls.gso, ("view_voucher_workbench", "initiate_payable_case"))
        cls.outsider = actor("source-outsider", cls.other, ("view_voucher_workbench", "initiate_payable_case"))
        cls.no_grant = actor("source-no-grant", cls.gso)
        cls.viewer = actor("source-viewer", cls.finance)
        cls.viewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        release = FinanceConfigurationRelease.objects.create(department=cls.finance, code="source-test",
            title="Synthetic release", fiscal_year=2026, effective_from=date(2026, 1, 1), created_by=cls.clerk)
        party = FinanceParty.objects.create(department=cls.finance, release=release, code="source-vendor",
            display_name="Synthetic supplier", effective_from=date(2026, 1, 1), created_by=cls.clerk,
            tax_identifier="MUST-NOT-EXPORT")
        cls.case = VoucherCase.objects.create(reference_code="GSO-SOURCE-TEST", requesting_department=cls.gso,
            current_department=cls.finance, configuration_release=release, payee=party,
            payee_name=party.display_name, particulars="Synthetic source", created_by=cls.clerk,
            current_stage=VoucherCase.ACCOUNTING_PREPARATION)
        cls.voucher = DisbursementVoucher.objects.create(case=cls.case, dv_number="GSO-SOURCE-DV",
            voucher_date=date(2026, 10, 17), gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"),
            prepared_by=cls.clerk, prepared_at=timezone.now())
        cls.line = VoucherLineItem.objects.create(voucher=cls.voucher, description="Supplies", amount=Decimal("100.00"))

    def resolve(self, actor=None, line_id=None):
        return resolve_claim_line(actor=actor or self.clerk, case_public_id=self.case.public_id,
                                  line_id=self.line.pk if line_id is None else line_id)

    def test_real_source_scope_owner_and_read_only_router(self):
        with CaptureQueriesContext(connections["default"]) as default, CaptureQueriesContext(connections["finance"]) as finance:
            result = self.resolve()
        self.assertEqual(result["source"]["finance_department_id"], self.finance.pk)
        self.assertEqual(result["source"]["requesting_department_id"], self.gso.pk)
        self.assertEqual(result["source"]["line_amount"], "100.00")
        self.assertNotIn("MUST-NOT-EXPORT", str(result))
        self.assertEqual(len(finance), 0)
        for query in default:
            self.assertFalse(query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")), query["sql"])

    def test_other_requesting_office_and_ungranted_staff_cannot_resolve(self):
        for actor in (self.outsider, self.no_grant):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                self.resolve(actor=actor)

    def test_uat_viewer_reads_only_through_existing_finance_visibility(self):
        result = self.resolve(actor=self.viewer)
        self.assertEqual(result["source"]["case_public_id"], str(self.case.public_id))
        self.case.refresh_from_db()
        self.assertEqual(self.case.state_version, 0)

    def test_replaced_line_is_not_silently_retargeted(self):
        original = self.resolve()
        old_id = self.line.pk
        # This is the actual line replacement used by GRAND prepare_voucher.
        self.voucher.line_items.all().delete()
        replacement = VoucherLineItem.objects.create(voucher=self.voucher, description="Supplies", amount=Decimal("100.00"))
        with self.assertRaisesMessage(ValidationError, "replaced"):
            self.resolve(line_id=old_id)
        self.assertNotEqual(original["sha256"], self.resolve(line_id=replacement.pk)["sha256"])

    def test_case_version_changes_invalidate_reviewed_snapshot(self):
        original = self.resolve()
        VoucherCase.objects.filter(pk=self.case.pk).update(state_version=1)
        self.assertNotEqual(original["sha256"], self.resolve()["sha256"])

    def test_inventory_schema_and_receiving_use_grand_identity_in_default_only(self):
        self.gso.name = "General Services Office"
        self.gso.save(update_fields=("name",))
        self.clerk.refresh_from_db()
        self.clerk.user_permissions.add(Permission.objects.get(
            content_type__app_label="inventory", codename="add_receivingreceipt"))
        data = dict(supplier="Synthetic supplier", delivery_reference="DELIVERY-TEST",
                    delivery_date=date(2026, 10, 16), inspection_reference="INSPECTION-TEST",
                    inspection_date=date(2026, 10, 16), inspector_label="Synthetic inspector",
                    evidence_reference="Synthetic evidence reference")
        with CaptureQueriesContext(connections["finance"]) as finance_queries:
            receipt = create_receipt(actor=self.clerk, data=data)
        self.assertEqual(len(finance_queries), 0)
        self.assertEqual(receipt._state.db, "default")
        self.assertEqual(receipt.department_id, self.gso.pk)
        self.assertEqual(receipt.created_by, self.clerk)
        self.assertEqual(receipt.created_by._meta.label, "users.User")
        self.assertTrue(ReceivingEvent.objects.filter(receipt=receipt, actor=self.clerk,
                                                      action="created").exists())
        self.assertIn(ReceivingReceipt._meta.db_table, connections["default"].introspection.table_names())
        self.assertNotIn(ReceivingReceipt._meta.db_table, connections["finance"].introspection.table_names())
        with self.assertRaises(PermissionDenied):
            create_receipt(actor=self.outsider, data=data)


@skipUnless(connection.vendor == "mysql", "Requires native MySQL row locks and separate connections")
class GrandClaimSourceConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}

    def setUp(self):
        GrandClaimSourceTests.setUpTestData.__func__(type(self))

    def test_source_reader_does_not_resolve_a_replaced_line_during_preparation(self):
        started = Event()
        reader_connection = []

        def read_source():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.clerk.pk)
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
                    cursor.execute("SELECT CONNECTION_ID()")
                    reader_connection.append(cursor.fetchone()[0])
                started.set()
                try:
                    resolve_claim_line(actor=actor, case_public_id=self.case.public_id, line_id=self.line.pk)
                except ValidationError as exc:
                    return str(exc)
                return "unexpectedly resolved a replaced line"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            # Mirrors prepare_voucher's case lock and replacement transaction.
            # This tests source synchronization, not the entire preparation workflow.
            with transaction.atomic(using="default"):
                VoucherCase.objects.select_for_update().get(pk=self.case.pk)
                self.voucher.line_items.all().delete()
                VoucherLineItem.objects.create(voucher=self.voucher, description="Replacement", amount=Decimal("100.00"))
                future = executor.submit(read_source)
                self.assertTrue(started.wait(3), "Reader did not establish its independent connection")
                deadline = monotonic() + 3
                blocked = False
                while monotonic() < deadline:
                    with connections["default"].cursor() as cursor:
                        cursor.execute("""SELECT 1 FROM performance_schema.data_lock_waits w
                            JOIN performance_schema.threads t ON t.THREAD_ID = w.REQUESTING_THREAD_ID
                            WHERE t.PROCESSLIST_ID = %s""", [reader_connection[0]])
                        blocked = cursor.fetchone() is not None
                    if blocked or future.done():
                        break
                    sleep(0.02)
                self.assertTrue(blocked, "MySQL did not observe the source reader waiting on preparation")
            self.assertIn("replaced", future.result(timeout=10))
