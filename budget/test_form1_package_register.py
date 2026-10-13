from copy import deepcopy
from importlib import import_module
from uuid import uuid4
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connections
from django.urls import reverse
from accounting.cash_classifications import checksum
from .test_form1_packages import Form1PackageFixture
from .models import Form1Package,Form1PackageOffice,Form1PackageAttachment
from . import form1_packages as packages


class Form1PackageRegisterTests(Form1PackageFixture):
    def test_complete_three_office_history_paging_revocation_projection_and_backfill(self):
        original=self.retain();root=deepcopy(original.payload)
        before=root.copy()
        offices=packages.offices(original,root['assembly']['payload'])
        self.assertEqual(set(original.office_index.values_list('department_id',flat=True)),offices)
        row=original.office_index.first()
        with self.assertRaisesMessage(ValidationError,'original package office'):row.save()
        copies=[]
        for version in range(2,106):
            fields={field.attname:getattr(original,field.attname) for field in original._meta.concrete_fields if not field.primary_key}
            fields.update(public_id=uuid4(),version=version,payload=deepcopy(root))
            fields['payload']['identity'].update(public_id=str(fields['public_id']),version=version)
            fields['payload_checksum']=checksum(fields['payload'])
            copies.append(Form1Package(**fields))
        # Whole roots include complete nested original source evidence. Keep
        # inserts bounded rather than combining 104 large roots in one packet.
        Form1Package.objects.bulk_create(copies,batch_size=1)
        # MySQL does not populate primary keys on bulk-created model instances.
        # Fetch saved identities before retaining dependent bytes/index rows.
        copies=list(Form1Package.objects.exclude(pk=original.pk).only('pk','public_id'))
        attachments=list(original.attachments.all())
        Form1PackageAttachment.objects.bulk_create([Form1PackageAttachment(package=record,key=row.key,data=bytes(row.data))
            for record in copies for row in attachments])
        Form1PackageOffice.objects.bulk_create([Form1PackageOffice(package=record,department_id=office)
            for record in copies for office in offices])
        url=reverse('budget:form1_packages')
        for actor in (self.preparer,self.checker,self.treasurer):
            self.client.force_login(actor)
            response=self.client.get(url,{'page':3})
            self.assertEqual(response.status_code,200,response.content.decode())
            self.assertEqual(response.context['page'].paginator.count,105)
            self.assertEqual(len(response.context['page']),5)
            self.assertContains(response,'version 1')
        response=self.client.get(url,{'q':str(original.public_id),'status':'prepared'})
        self.assertEqual(response.context['page'].paginator.count,1)
        self.assertEqual(self.client.get(url,{'status':'issued'}).status_code,400)
        detail=reverse('budget:form1_package_detail',args=[original.public_id])
        response=self.client.get(detail)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Net ending balance')
        self.assertContains(response,'Download complete draft PDF')
        self.assertContains(response,'designated office')
        self.assertEqual(self.client.post(url).status_code,405)
        self.assertEqual(self.client.post(detail).status_code,405)
        native=Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals')
        self.checker.user_permissions.remove(native)
        self.client.force_login(self.checker)
        response=self.client.get(url)
        self.assertEqual(response.context['page'].paginator.count,0)
        self.assertEqual(self.client.get(detail).status_code,403)
        self.checker.user_permissions.add(native)
        export=Permission.objects.get(content_type__app_label='budget',codename='export_budget_receipt_forecasts')
        self.treasurer.user_permissions.remove(export)
        self.client.force_login(self.treasurer)
        response=self.client.get(detail)
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'Download complete draft PDF')
        # A forged candidate index cannot authorize a different office.
        permission=Permission.objects.get(content_type__app_label='budget',codename='view_form1_packages')
        self.outsider.user_permissions.add(permission)
        from .access import department_for_user
        alien=department_for_user(self.outsider)
        self.assertNotIn(alien.pk,offices)
        Form1PackageOffice.objects.create(package=original,department_id=alien.pk)
        self.client.force_login(self.outsider)
        response=self.client.get(url)
        self.assertEqual(response.context['page'].paginator.count,0)
        self.assertEqual(self.client.get(detail).status_code,403)
        self.client.force_login(self.treasurer)
        self.assertEqual(self.client.get(url).status_code,409)
        Form1PackageOffice.objects.filter(package=original,department_id=alien.pk).delete()
        # The earlier 104 rows populate request-local assembly/source caches.
        # Rehashed altered controls in the last root must still be rejected.
        changed=deepcopy(root)
        changed['assembly']['payload']['members'][0]['net_ending']['proposed']='999.00'
        changed['assembly']['checksum']=checksum(changed['assembly']['payload'])
        Form1Package.objects.filter(pk=original.pk).update(payload=changed,payload_checksum=checksum(changed))
        self.assertEqual(self.client.get(url).status_code,409)
        Form1Package.objects.filter(pk=original.pk).update(payload=root,payload_checksum=checksum(root))
        # Backfill reads original roots and leaves their payloads unchanged.
        Form1PackageOffice.objects.all().delete()
        migration=import_module('budget.migrations.0022_form1_package_offices')
        editor=SimpleNamespace(connection=connections['finance'])
        migration.backfill(apps,editor)
        self.assertEqual(Form1PackageOffice.objects.count(),105*len(offices))
        original.refresh_from_db();self.assertEqual(original.payload,before)
        Form1PackageOffice.objects.all().delete()
        Form1Package.objects.filter(pk=original.pk).update(payload_checksum='0'*64)
        with self.assertRaisesMessage(RuntimeError,'Inspect original'):migration.backfill(apps,editor)
        self.assertEqual(Form1PackageOffice.objects.count(),0)
