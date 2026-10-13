from datetime import date
import io
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from .test_summary_actuals import SummaryActualTests
from . import budget_cash as service
from .models import JournalEntry


class BudgetCashTests(SummaryActualTests):
    def cash_args(self,**changes):
        for actor,actions in ((self.maker,('prepare','view')),(self.checker,('review','view'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=[f'{action}_budget_cash_evidence' for action in actions]))
        original=self.arguments()
        for key in ('period_start','period_end','evidence','trial_balance','receipt_total','expenditure_total','rows'):
            original.pop(key)
        from reportlab.pdfgen import canvas
        def doc():
            stream=io.BytesIO();pdf=canvas.Canvas(stream)
            for index,line in enumerate(('SYNTHETIC CASH TEST ONLY / General Fund / start of January 1, 2026',
                'Gross cash 100; continuing-appropriation restriction R1 25; net cash 75',
                'Treasurer: Synthetic Treasurer / designation T / July 1, 2026',
                'Accountant: Synthetic Accountant / designation A / July 2, 2026',
                'R1 unique source, no overlap; synthetic gross/source reconciliation; no municipal cash claim')):
                pdf.drawString(25,790-index*28,line)
            pdf.save();return SimpleUploadedFile('synthetic-cash.pdf',stream.getvalue(),content_type='application/pdf')
        original.update(balance_date=date(2026,1,1),boundary='start_of_day',gross='100',restricted='25',net='75',
            rows=[{'key':'continuing-1','reference':'p1 R1','amount':'25','purpose':'Synthetic continuing appropriation',
                   'coverage':'Only R1; no overlap with other restriction sources'}],no_restrictions=False,declaration='',
            overlap_basis='Synthetic full restriction schedule checked for overlaps',gross_basis='Synthetic gross cash/source reconciliation',
            certificate=doc(),reconciliation=doc())
        original.update(changes);return original

    def test_historical_cash_retention_controls_and_independent_adoption(self):
        before=JournalEntry.objects.count()
        record=service.propose(**self.cash_args())
        self.assertEqual(service.verify(record)['net'],'75.00')
        with self.assertRaises(PermissionDenied):service.review(record,self.maker,adopt=True,note='x',authority='x',verified_documents=True)
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',codename='review_budget_cash_evidence'))
        with self.assertRaisesMessage(ValidationError,'independent'):
            service.review(record,self.maker,adopt=True,note='x',authority='x',verified_documents=True)
        with self.assertRaises(ValidationError):service.review(record,self.checker,adopt=True,note='x',authority='x')
        adopted=service.review(record,self.checker,adopt=True,note='Verified original gross/restriction sources and certifications',authority='Independent cash adoption designation',verified_documents=True)
        self.assertEqual(adopted.status,'adopted')
        with self.assertRaises(ValidationError):adopted.delete()
        adopted.payload['net']='100'
        with self.assertRaises(ValidationError):adopted.save()
        adopted.refresh_from_db()
        self.assertEqual(service.verify(adopted)['net'],'75.00')
        self.assertEqual(JournalEntry.objects.count(),before)
        for changes in ({'restricted':'24'},{'net':'100'},{'rows':[]},{'no_restrictions':True},
                        {'rows':self.cash_args()['rows']*2},{'overlap_basis':''}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                service.propose(**self.cash_args(expected_latest=1,**changes))
        next_record=service.propose(**self.cash_args(expected_latest=1))
        with self.assertRaises(ValidationError):service.propose(**self.cash_args(expected_latest=1))
        self.assertEqual(service.verify(adopted)['version'],1)
        returned=service.review(next_record,self.checker,adopt=False,note='Synthetic return',authority='Independent designation')
        self.assertEqual(returned.status,'returned')
        zero=service.propose(**self.cash_args(expected_latest=2,gross='0',restricted='0',net='0',rows=[],
            no_restrictions=True,declaration='Synthetic explicit zero cash and no-restriction source declaration'))
        self.assertEqual(service.verify(zero)['net'],'0.00')
        from django.contrib.auth.models import Group
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        self.checker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):service.review(zero,self.checker,adopt=True,note='x',authority='x',verified_documents=True)
        self.assertTrue(service.permitted(self.checker,'view'))
        self.checker.groups.remove(Group.objects.get(name=FINANCE_UAT_VIEWER_GROUP))
        type(self.fund).objects.filter(pk=self.fund.pk).update(department_id=self.budget_office.pk)
        with self.assertRaisesMessage(ValidationError,'no longer belongs'):
            service.review(zero,self.checker,adopt=True,note='x',authority='x',verified_documents=True)
        self.assertEqual(service.review(zero,self.checker,adopt=False,note='Resolve changed fund setup',authority='Designation').status,'returned')
        self.assertEqual(service.verify(adopted)['net'],'75.00')
