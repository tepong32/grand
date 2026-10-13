from copy import deepcopy

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Permission
from django.test import TestCase
from accounting import test_budget_cash_certifications as fixtures
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from . import form1_stock_sources as stocks, form1_cash_forecasts as forecasts


class Form1CashForecastTests(TestCase):
    databases={'default','finance'}

    def setUp(self):
        super().setUp()
        self.factory=fixtures.NativeCashCertificationTests(
            'test_joint_decisions_reproduce_sources_without_rewriting_preparation')
        self.addCleanup(lambda:self.assertTrue(self.factory.doCleanups()))
        self.factory.setUp()
        self.record=self.factory.cash_preparation()
        self.factory.decision(self.record,'accountant'); self.factory.decision(self.record,'treasurer')
        self.source=stocks.capture(route='native',identity=str(self.record.public_id),actor=self.factory.poster,
            expected_scope={key:self.record.payload['scope'][key] for key in stocks.SCOPE_FIELDS})
        self.key=self.source['payload']['restrictions'][0]['key']

    def inputs(self):
        return dict(target_date='2027-01-01',target_boundary='start_of_day',
            cash_changes=[dict(key='receipt',source_row='worksheet 1',effective_date='2026-12-01',
                direction='in',amount='200.00',basis='Expected receipt date from retained worksheet'),
                dict(key='payment',source_row='worksheet 2',effective_date='2026-12-02',
                direction='out',amount='50.00',basis='Expected payment date from retained worksheet')],
            proposed_restrictions=[dict(key='new',reference='new reserve',purpose='Forecast reserve',coverage='Full target scope')],
            restriction_changes=[dict(key='release',source_row='worksheet 3',effective_date='2026-12-01',
                restriction=self.key,action='remove',amount='20.00',basis='Expected release'),
                dict(key='reserve',source_row='worksheet 4',effective_date='2026-12-02',
                restriction='new',action='add',amount='30.00',basis='Expected reserve')],
            cash_coverage='complete',cash_basis='Whole original worksheet cash timing reconciled',
            no_cash_changes=False,cash_declaration='',restriction_coverage='complete',
            restriction_basis='Whole target restriction inventory, including overlap',
            no_restrictions=False,restriction_declaration='')

    def proposal(self,source=None,**changes):
        inputs=dict(self.inputs(),**changes)
        return forecasts.propose(source=source or self.source,actor=self.factory.poster,
            evidence=SimpleUploadedFile('forecast.pdf',b'%PDF-1.4\noriginal synthetic forecast worksheet'),**inputs)

    def test_cash_and_restriction_rollforward_retain_sources_without_posting(self):
        before=JournalEntry.objects.count(); original=deepcopy(self.record.payload)
        envelope,data=self.proposal(); body=forecasts.reproduce(envelope,self.factory.poster,evidence=data)
        self.assertEqual((body['gross'],body['restricted'],body['net']),('1150.00','110.00','1040.00'))
        self.assertEqual(body['source'],self.source)
        self.assertEqual(sorted(row['amount'] for row in body['restriction_positions']),['30.00','80.00'])
        self.assertTrue(body['coverage_complete'])
        for field in ('independently_reviewed','actual_cash','cash_available','source_freshness_certified','form_issued'):
            self.assertFalse(body[field])
        self.record.refresh_from_db(); self.assertEqual(self.record.payload,original)
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_missing_is_unknown_and_zero_requires_its_own_evidence(self):
        envelope,data=self.proposal(cash_changes=[],cash_coverage='missing')
        body=forecasts.reproduce(envelope,self.factory.poster,evidence=data)
        self.assertIsNone(body['gross']); self.assertIsNone(body['net'])
        self.assertEqual(body['diagnostic_gross'],'1000.00')
        with self.assertRaises(ValidationError):self.proposal(cash_changes=[])
        envelope,_=self.proposal(cash_changes=[],no_cash_changes=True,cash_declaration='No projected cash movements')
        self.assertEqual(envelope['payload']['gross'],'1000.00')
        removal=dict(key='all',source_row='worksheet 5',effective_date='2026-12-01',restriction=self.key,
            action='remove',amount='100.00',basis='Full release of original restrictions')
        with self.assertRaises(ValidationError):self.proposal(proposed_restrictions=[],restriction_changes=[removal])
        envelope,_=self.proposal(proposed_restrictions=[],restriction_changes=[removal],
            no_restrictions=True,restriction_declaration='Complete inventory confirms no target restrictions')
        self.assertEqual(envelope['payload']['restricted'],'0.00')
        for field in ('cash_declaration','restriction_declaration'):
            with self.subTest(field=field),self.assertRaises(ValidationError):self.proposal(**{field:None})

    def test_boundary_duplicates_and_later_additions_fail_closed(self):
        for day in ('2026-09-04','2027-01-01'):
            inputs=self.inputs(); inputs['cash_changes'][0]['effective_date']=day
            with self.subTest(day=day),self.assertRaises(ValidationError):self.proposal(**inputs)
        for boundary in ('start_of_day','end_of_day'):
            with self.assertRaises(ValidationError):self.proposal(target_date='2026-09-04',target_boundary=boundary)
        inputs=self.inputs(); inputs['cash_changes'].append(deepcopy(inputs['cash_changes'][0]))
        with self.assertRaises(ValidationError):self.proposal(**inputs)
        inputs=self.inputs(); inputs['restriction_changes']=[
            dict(key='early',source_row='early',effective_date='2026-10-01',restriction=self.key,
                action='remove',amount='101.00',basis='Early removal'),
            dict(key='late',source_row='late',effective_date='2026-11-01',restriction=self.key,
                action='add',amount='2.00',basis='Later addition')]
        inputs['proposed_restrictions']=[]
        with self.assertRaises(ValidationError):self.proposal(**inputs)
        # A target end boundary includes its actual date; start excludes it.
        inputs=self.inputs(); inputs['cash_changes'][0]['effective_date']='2027-01-01'
        inputs['target_boundary']='end_of_day'
        self.assertEqual(self.proposal(**inputs)[0]['payload']['gross'],'1150.00')

    def test_retained_history_export_authority_and_rehashed_controls(self):
        envelope,data=self.proposal(); actor=self.factory.poster
        with self.assertRaises(PermissionDenied):forecasts.reproduce(envelope,actor,evidence=data,export=True)
        permission=Permission.objects.get(content_type__app_label='accounting',codename='export_native_budget_cash')
        actor.user_permissions.add(permission)
        self.assertEqual(forecasts.reproduce(envelope,actor,evidence=data,export=True),envelope['payload'])
        actor.user_permissions.remove(permission)
        with self.assertRaises(ValidationError):forecasts.reproduce(envelope,actor,evidence=data+b'changed')
        for field in ('net','source'):
            changed=deepcopy(envelope)
            if field=='net':changed['payload']['net']='1041.00'
            else:
                changed['payload']['source']['payload']['gross']='1001.00'
                changed['payload']['source']['checksum']=checksum(changed['payload']['source']['payload'])
            changed['checksum']=checksum(changed['payload'])
            with self.subTest(field=field),self.assertRaises(ValidationError):forecasts.reproduce(changed,actor,evidence=data)
        self.factory.historical(expected_latest=1)
        with self.assertRaises(ValidationError):self.proposal()
        self.assertEqual(forecasts.reproduce(envelope,actor,evidence=data),envelope['payload'])
