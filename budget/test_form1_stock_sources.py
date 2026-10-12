from copy import deepcopy

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from accounting import test_budget_cash_certifications as fixtures
from accounting import budget_cash_certifications as joint
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import form1_stock_sources as sources


class Form1StockSourceTests(TestCase):
    databases={'default','finance'}

    def setUp(self):
        super().setUp()
        # Compose the existing genuine source factory without inheriting its tests.
        self.factory=fixtures.NativeCashCertificationTests(
            'test_joint_decisions_reproduce_sources_without_rewriting_preparation')
        self.addCleanup(lambda:self.assertTrue(self.factory.doCleanups()))
        self.factory.setUp()

    def original(self):
        record=self.factory.cash_preparation()
        self.factory.decision(record,'accountant'); self.factory.decision(record,'treasurer')
        return record

    def selected(self,record,route='native',**changes):
        original=record.restriction_source if route=='historical' else record
        expected={key:record.payload['scope'][key] for key in sources.SCOPE_FIELDS}
        return sources.capture(route=route,identity=str(original.public_id),expected_scope=expected,
            actor=self.factory.poster,**changes)

    def test_both_original_alternatives_reproduce_controls_without_posting(self):
        record=self.original(); before=JournalEntry.objects.count(); pinned=deepcopy(record.payload)
        for route in ('historical','native'):
            source=self.selected(record,route); body=sources.require_visible(source,self.factory.poster)
            self.assertEqual((body['gross'],body['restricted'],body['net']),('1000.00','100.00','900.00'))
            self.assertEqual(body['scope']['balance_date'],'2026-09-04')
            self.assertEqual(len(body['restrictions']),1)
            self.assertFalse(body['cash_available']); self.assertFalse(body['form_issued'])
            self.assertFalse(body['source_freshness_certified'])
            self.assertEqual(self.selected(record,route),source)
        self.assertEqual(self.selected(record)['payload']['snapshot'],joint.snapshot(record,self.factory.poster))
        record.refresh_from_db(); self.assertEqual(record.payload,pinned)
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_exact_scope_route_identity_and_pending_certification_fail_closed(self):
        record=self.factory.cash_preparation()
        with self.assertRaises(ValidationError):self.selected(record)
        self.factory.decision(record,'accountant')
        with self.assertRaises(ValidationError):self.selected(record)
        self.factory.decision(record,'treasurer')
        expected={key:record.payload['scope'][key] for key in sources.SCOPE_FIELDS}
        for field in ('department_id','budget_department_id','treasury_department_id','fund_id','entity_key','balance_date','boundary'):
            changed=deepcopy(expected)
            changed[field]=changed[field]+1 if type(changed[field]) is int else (
                'enterprise:other' if field=='entity_key' else '2026-09-03' if field=='balance_date' else 'start_of_day')
            with self.subTest(field=field),self.assertRaises(ValidationError):
                sources.capture(route='native',identity=str(record.public_id),expected_scope=changed,actor=self.factory.poster)
        for route,identity in (('alias',str(record.public_id)),('native',str(record.pk))):
            with self.assertRaises(ValidationError):
                sources.capture(route=route,identity=identity,expected_scope=expected,actor=self.factory.poster)
        for field,value in (('fund_id',True),('balance_date','9999-01-01')):
            changed=deepcopy(expected); changed[field]=value
            with self.assertRaises(ValidationError):sources.scope(changed)

    def test_export_permissions_uat_read_and_original_source_revocation(self):
        record=self.original(); actor=self.factory.poster
        actor.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        for route in ('native','historical'):
            source=self.selected(record,route)
            with self.assertRaises(PermissionDenied):sources.require_visible(source,actor,export=True)
            code='export_native_budget_cash' if route=='native' else 'export_budget_cash_evidence'
            permission=Permission.objects.get(content_type__app_label='accounting',codename=code)
            actor.user_permissions.add(permission)
            self.assertEqual(sources.require_visible(source,actor,export=True),source['payload'])
            actor.user_permissions.remove(permission)
            with self.assertRaises(PermissionDenied):sources.require_visible(source,actor,export=True)
        source=self.selected(record)
        actor.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_cash'))
        with self.assertRaises(PermissionDenied):sources.require_visible(source,actor)

    def test_successors_block_new_selection_but_retain_original_and_reject_rehash(self):
        record=self.original(); actor=self.factory.poster
        original={route:self.selected(record,route) for route in ('historical','native')}
        before=JournalEntry.objects.count()
        self.factory.historical(expected_latest=1)
        for route,source in original.items():
            with self.assertRaises(ValidationError):self.selected(record,route)
            self.assertEqual(sources.require_visible(source,actor),source['payload'])
            changed=deepcopy(source); changed['payload']['net']='999.00'
            changed['checksum']=checksum(changed['payload'])
            with self.assertRaises(ValidationError):sources.require_visible(changed,actor)
        self.assertEqual(JournalEntry.objects.count(),before)
