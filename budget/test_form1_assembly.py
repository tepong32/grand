from copy import deepcopy
from datetime import date

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from . import test_form1_spa_reviews as spa_fixtures,test_form1_stocks as stock_fixtures
from . import test_form1_philhealth as ph_fixtures
from . import form1_stocks,form1_philhealth as ph,form1_spa_output as spa_output
from . import form1_spa_reviews as spa_reviews,form1_flows,form1_assembly as service


class Form1AssemblyFixture(spa_fixtures.Form1SPAReviewFixture):
    inputs=ph_fixtures.Form1PhilHealthTests.inputs
    cash=stock_fixtures.Form1StockCalendarTests.cash
    bridge=stock_fixtures.Form1StockCalendarTests.bridge
    capture_stock=stock_fixtures.Form1StockCalendarTests.capture_stock

    def setUp(self):
        super().setUp()
        self.spa_record=self.approve_spa(self.prepare_spa())
        self.approved=self.approved_forecast
        self.scope=form1_flows.capture(forecast=self.approved,actor=self.preparer)['payload']['members'][0]['scope']
        for actor,codes in ((self.maker,('prepare_budget_cash_evidence','view_budget_cash_evidence')),
            (self.checker,('review_budget_cash_evidence','view_budget_cash_evidence')),
            (self.preparer,('view_budget_cash_evidence','export_budget_cash_evidence'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',codename__in=codes))
        self.prior=self.cash(date(2025,1,1));self.half=self.cash(date(2026,1,1))
        self.estimate,self.estimate_bytes=self.bridge('2026-07-01','100.00')
        self.proposed,self.proposed_bytes=self.bridge('2027-01-01','200.00')
        self.selections=[dict(entity_key=self.scope['entity_key'],opening=dict(prior_amount=dict(kind='actual',source=self.prior),
            half_amount=dict(kind='actual',source=self.half),estimate=dict(kind='forecast',source=self.estimate),
            proposed=dict(kind='forecast',source=self.proposed)))]
        self.evidence={self.estimate['checksum']:self.estimate_bytes,self.proposed['checksum']:self.proposed_bytes}
        self.ph_source,self.documents=self.ph_draft()

    def ph_draft(self,*,attach=True,selections=None):
        stock=self.capture_stock(**(dict(selections=selections) if selections is not None else {}))
        source=ph.capture(stock=stock,actor=self.preparer,evidence=self.evidence)
        parts=[dict(key='part-'+str(index),source=row['key'],amount=row['amount'],counterpart='',
            treatment='deduct' if row['kind']=='receipt' else 'other',basis='Synthetic explicit original funding treatment')
            for index,row in enumerate(source['payload']['catalog'])]
        coverage=[dict(entity=self.scope['entity_key'],column=column,kind=kind,coverage='complete',
            basis='Synthetic whole original source inventory') for column in ph.components.SOURCE_COLUMNS for kind in ph.KINDS]
        args=dict(source=source,actor=self.preparer,evidence=self.evidence,parts=parts,coverage=coverage,
            coverage_reference='Synthetic whole-form reconciliation')
        if attach:args.update(authority=SimpleUploadedFile('policy.pdf',b'%PDF-1.4\nSynthetic policy'),
            reconciliation=SimpleUploadedFile('overlap.pdf',b'%PDF-1.4\nSynthetic worksheet'))
        return ph.prepare(**args)

    def assembled(self,**changes):
        args=dict(spa_review=self.spa_record,philhealth_source=self.ph_source,actor=self.preparer,
            evidence=self.evidence,documents=self.documents)
        args.update(changes);return service.capture(**args)

class Form1AssemblyTests(Form1AssemblyFixture):
    def test_genuine_whole_source_all_rows_columns_controls_and_no_authority(self):
        before=JournalEntry.objects.count();original=deepcopy(self.ph_source)
        envelope=self.assembled()
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify(envelope)
        member=body['members'][0]
        self.assertEqual(len(member['receipt']['rows']),21);self.assertEqual(len(member['expenditure']['rows']),5)
        self.assertEqual(len(member['spa']['rows']),6)
        self.assertEqual(member['philhealth']['deduction']['estimate'],'30.00')
        self.assertEqual(member['net_ending']['current_total'],'760.00')
        self.assertEqual(member['opening']['current_total']['net'],member['opening']['half_amount']['net'])
        self.assertTrue(body['calculation_coverage_complete'])
        for flag in ('independently_reviewed','stock_complete','philhealth_deduction_complete',
            'form_issued','cash_available','source_freshness_certified'):self.assertIs(body[flag],False)
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=self.documents),body)
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=self.documents,export=True),body)
        self.assertEqual(original,self.ph_source);self.assertEqual(JournalEntry.objects.count(),before)

    def test_missing_documents_and_rehashed_rows_keep_unknown_and_fail_closed(self):
        source,documents=self.ph_draft(attach=False)
        envelope=self.assembled(philhealth_source=source,documents=documents)
        body=envelope['payload'];self.assertFalse(body['calculation_coverage_complete'])
        self.assertTrue(all(value is None for value in body['members'][0]['net_ending'].values()))
        for key in ('net_ending','resource_ending'):
            changed=deepcopy(envelope);changed['payload']['members'][0][key]['proposed']='999.00'
            changed['checksum']=checksum(changed['payload'])
            with self.subTest(key=key),self.assertRaises(ValidationError):service.verify(changed)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='export_budget_cash_evidence'))
        with self.assertRaises(PermissionDenied):service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=documents,export=True)
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=documents),body)

    def test_exact_flow_pair_successors_original_history_and_document_bytes(self):
        envelope=self.assembled();snapshot=spa_reviews.snapshot(self.spa_record,self.preparer)
        self.approved=self.review_forecast(self.prepare_forecast(expected_latest=1))
        replacement,replacement_docs=self.ph_draft()
        with self.assertRaisesMessage(ValidationError,'same whole flow'):service.compose(spa_output.package(snapshot),replacement)
        with self.assertRaises(ValidationError):self.assembled(philhealth_source=replacement,documents=replacement_docs)
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=self.documents),envelope['payload'])
        bad=dict(self.documents);bad['authority']+=b'changed'
        with self.assertRaises(ValidationError):service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=bad)
