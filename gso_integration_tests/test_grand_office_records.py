"""The GSO entry uses the native Records registry and its authority."""
from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from profiles.models import EmployeeProfile
from records.models import DepartmentRecord, RecordAssociation
from inventory.models import Asset, StockMovement
from inventory.office_records import workspace_url
from . import test_grand_maintenance


class GrandOfficeRecordsTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_maintenance.GrandMaintenanceTests.setUpTestData.__func__(cls)
        grant = Permission.objects.get(content_type__app_label="inventory", codename="view_asset")
        for actor in (cls.clerk, cls.no_grant, cls.outsider):
            actor.user_permissions.add(grant)
        cls.clerk.user_permissions.add(*Permission.objects.filter(content_type__app_label="records",
            codename__in=("view_records_workspace", "manage_department_records")))

    def test_entry_uses_native_grant_and_fails_closed_when_route_absent(self):
        self.client.force_login(self.no_grant)
        self.assertNotContains(self.client.get(reverse("inventory:dashboard")), "Open office records")
        self.assertIsNone(workspace_url(self.no_grant))
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertContains(response, 'href="'+reverse("records:workspace")+'"')
        with override_settings(ROOT_URLCONF="inventory.urls"):
            self.assertIsNone(workspace_url(self.clerk))
        self.clerk.user_permissions.remove(Permission.objects.get(content_type__app_label="records", codename="view_records_workspace"))
        self.client.force_login(type(self.clerk).objects.get(pk=self.clerk.pk))
        self.assertNotContains(self.client.get(reverse("inventory:dashboard")), "Open office records")

    def test_native_filing_is_scoped_and_creates_no_inventory_or_finance_records(self):
        self.client.force_login(self.clerk)
        inventory_before = (Asset.objects.count(), StockMovement.objects.count())
        with CaptureQueriesContext(connections["finance"]) as finance:
            self.assertEqual(self.client.get(workspace_url(self.clerk)).status_code, 200)
            response = self.client.post(reverse("records:record_create"), dict(
                title="Synthetic GSO correspondence", description="Office filing through native Records",
                classification="general", confidentiality="internal", custodian=self.clerk.pk,
                retention_years="", retention_notes="Await the approved retention schedule"))
        self.assertEqual(response.status_code, 302)
        row = DepartmentRecord.objects.get(title="Synthetic GSO correspondence")
        self.assertEqual(row.department_id, self.gso.pk)
        self.assertEqual(row.created_by_id, self.clerk.pk)
        self.assertEqual(row.status, "draft")
        self.assertEqual(row.events.get().action, "created")
        self.assertFalse(RecordAssociation.objects.filter(record=row).exists())
        self.assertEqual((Asset.objects.count(), StockMovement.objects.count()), inventory_before)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")) for q in finance))
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label="records", codename="view_records_workspace"))
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse("records:workspace")), row.title)
        self.assertEqual(self.client.get(row.get_absolute_url()).status_code, 404)

    def test_native_restricted_visibility_and_actual_assigned_department(self):
        row = DepartmentRecord.objects.create(department=self.gso,record_number="PRIVATE-GSO",
            title="Restricted synthetic record",confidentiality="confidential",created_by=self.clerk)
        self.client.force_login(self.clerk)
        self.assertNotContains(self.client.get(reverse("records:workspace")), row.title)
        self.assertEqual(self.client.get(row.get_absolute_url()).status_code, 404)
        # Superuser fallback inventory scope must not advertise another office's registry as GSO.
        self.other.name, self.other.slug = "Engineering", "engineering"
        self.other.save(update_fields=("name", "slug"))
        EmployeeProfile.objects.filter(user=self.super_no_grant).update(assigned_department=self.other)
        self.assertIsNone(workspace_url(type(self.super_no_grant).objects.get(pk=self.super_no_grant.pk)))
