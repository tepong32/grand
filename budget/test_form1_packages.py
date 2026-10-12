from copy import deepcopy

from django.contrib.auth.models import Permission,Group
from django.core.exceptions import ValidationError,PermissionDenied
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_ROLE_PERMISSIONS,FINANCE_UAT_VIEWER_GROUP
from . import test_form1_assembly as fixtures,form1_packages as service,form1_spa_reviews as spa
from .models import Form1Package,Form1PackageAttachment


class Form1PackageFixture(fixtures.Form1AssemblyFixture):
    def setUp(self):
        super().setUp()
        for actor,role in ((self.preparer,'Budget Form 1 Package Preparer'),
            (self.checker,'Accounting Form 1 Package Viewer'),(self.treasurer,'Treasury Form 1 Package Viewer')):
            for permission in FINANCE_ROLE_PERMISSIONS[role]:
                app,code=permission.split('.')
                actor.user_permissions.add(Permission.objects.get(content_type__app_label=app,codename=code))
        self.envelope=self.assembled()

    def retain(self,**changes):
        args=dict(spa_review=self.spa_record,envelope=self.envelope,actor=self.preparer,evidence=self.evidence,
            documents=self.documents,reference='Synthetic complete original package retention',expected_latest=0)
        args.update(changes);return service.prepare(**args)


class Form1PackageTests(Form1PackageFixture):
    def test_currentness_for_all_three_offices_is_separate_from_original_history(self):
        record=self.retain()
        original=service.snapshot(record,self.preparer)
        for actor in (self.preparer,self.checker,self.treasurer):
            self.assertTrue(service.is_current(record,actor))
        self.prepare_forecast(expected_latest=1)
        for actor in (self.preparer,self.checker,self.treasurer):
            self.assertFalse(service.is_current(record,actor))
            self.assertEqual(service.snapshot(record,actor),original)
        self.treasurer.user_permissions.remove(Permission.objects.get(
            content_type__app_label='budget',codename='view_budget_receipt_forecasts'))
        with self.assertRaises(PermissionDenied):service.is_current(record,self.treasurer)

    def test_budget_preparer_role_alone_retains_sources_without_general_editing(self):
        self.preparer.user_permissions.clear()
        self.preparer.groups.clear()
        for permission in FINANCE_ROLE_PERMISSIONS['Budget Form 1 Package Preparer']:
            app,code=permission.split('.')
            self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label=app,codename=code))
        record=self.retain()
        self.assertEqual(service.snapshot(record,self.preparer)['payload']['assembly'],self.envelope)
        self.assertFalse(self.preparer.user_permissions.filter(codename='prepare_budget_proposals').exists())
        self.assertFalse(self.preparer.user_permissions.filter(codename='review_budget_proposals').exists())

    def test_immutable_whole_preparation_attachment_bytes_and_versions_without_posting(self):
        before=JournalEntry.objects.count();record=self.retain()
        attachments=list(record.attachments.all())
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify(record,attachments)
        self.assertEqual(body,self.envelope['payload']);self.assertEqual(len(attachments),4)
        original=deepcopy(record.payload)
        record.payload['reference']='overwrite'
        with self.assertRaises(ValidationError):record.save()
        record.payload=original
        with self.assertRaises(ValidationError):record.delete()
        with self.assertRaises(ValidationError):attachments[0].save()
        with self.assertRaises(ValidationError):attachments[0].delete()
        with self.assertRaisesMessage(ValidationError,'newer'):self.retain()
        second=self.retain(expected_latest=1)
        self.assertEqual(second.version,2)
        self.assertEqual(service.snapshot(record,self.preparer)['payload'],original)
        for row in attachments:
            self.assertEqual(service.attachment_bytes(record,self.preparer,row.key),bytes(row.data))
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_three_office_sources_permissions_export_only_and_uat_mutation_denial(self):
        record=self.retain()
        for actor in (self.preparer,self.checker,self.treasurer):
            result=service.snapshot(record,actor)
            self.assertEqual(result['payload']['assembly'],self.envelope)
            self.assertFalse(result['independently_reviewed']);self.assertFalse(result['form_issued'])
            self.assertEqual(service.snapshot(record,actor,export=True),result)
        with self.assertRaises(PermissionDenied):spa.snapshot(self.spa_record,self.treasurer)
        # Historical source visibility needs the existing read-only Budget audit
        # grant, rather than incidental proposal preparation/review permissions.
        self.preparer.user_permissions.remove(*Permission.objects.filter(content_type__app_label='budget',
            codename__in=('prepare_budget_proposals','review_budget_proposals')))
        service.snapshot(record,self.preparer)
        native_view=Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals')
        self.checker.user_permissions.remove(native_view)
        with self.assertRaises(PermissionDenied):service.snapshot(record,self.checker)
        service.snapshot(record,self.checker,export=True)
        self.treasurer.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',codename='export_budget_receipt_forecasts'))
        with self.assertRaises(PermissionDenied):service.snapshot(record,self.treasurer,export=True)
        service.snapshot(record,self.treasurer)
        with self.assertRaises(PermissionDenied):service.snapshot(record,self.maker)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):self.retain(expected_latest=1)
        self.assertEqual(Form1Package.objects.count(),1)
        self.assertNotIn('budget.prepare_budget_proposals',FINANCE_ROLE_PERMISSIONS['Budget Form 1 Package Preparer'])
        for role in ('Accounting Form 1 Package Viewer','Treasury Form 1 Package Viewer'):
            self.assertNotIn('budget.prepare_budget_proposals',FINANCE_ROLE_PERMISSIONS[role])

    def test_successor_history_rehashed_controls_and_attachment_corruption_fail_closed(self):
        record=self.retain();original=service.snapshot(record,self.preparer)
        self.approved=self.review_forecast(self.prepare_forecast(expected_latest=1))
        with self.assertRaises(ValidationError):self.retain(expected_latest=1)
        self.assertEqual(service.snapshot(record,self.treasurer),original)
        changed=deepcopy(record.payload)
        changed['assembly']['payload']['members'][0]['net_ending']['proposed']='999.00'
        changed['assembly']['checksum']=checksum(changed['assembly']['payload'])
        Form1Package.objects.filter(pk=record.pk).update(payload=changed,payload_checksum=checksum(changed))
        with self.assertRaises(ValidationError):service.snapshot(record,self.preparer)
        Form1Package.objects.filter(pk=record.pk).update(payload=original['payload'],payload_checksum=original['payload_checksum'])
        row=record.attachments.first()
        Form1PackageAttachment.objects.filter(pk=row.pk).update(data=b'changed original')
        with self.assertRaises(ValidationError):service.snapshot(record,self.preparer)
