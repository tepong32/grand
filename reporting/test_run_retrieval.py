import csv
import io
import tempfile
import uuid
from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from . import tests as fixtures
from .models import ReportRun


class ReportRunRetrievalTests(TestCase):
    setUpTestData = classmethod(fixtures.ReportingPlatformTests.setUpTestData.__func__)

    def run_row(self, actor=None, output_format='csv'):
        return ReportRun(idempotency_key=str(uuid.uuid4()), definition=self.definition, template_version=self.template,
            output_format=output_format, period_start=date(2026,1,1), period_end=date(2026,12,31),
            status=ReportRun.FAILED, created_by=actor or self.operator,
            error_message='Synthetic retrieval record; no generated output')

    def seed(self):
        ReportRun.objects.bulk_create([self.run_row() for _ in range(110)])
        ReportRun.objects.all().update(created_at=timezone.now())
        self.colleague = self.run_row(self.head); self.colleague.save()
        self.different_format = self.run_row(output_format='pdf'); self.different_format.save()
        self.filters = {'q':'Assistance Volume','status':'failed','output_format':'csv',
            'period_year':'2026','attention':'generation_failed','definition':str(self.definition.pk)}

    def test_all_matching_runs_are_reachable_and_export_remains_complete(self):
        self.seed(); self.client.force_login(self.operator)
        seen=[]
        for number, count in ((1,50),(2,50),(3,10)):
            response=self.client.get(reverse('reporting:workspace'),{**self.filters,'page':number})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['visible_run_count'],110)
            self.assertEqual(len(response.context['recent_runs']),count)
            self.assertContains(response,f'Page {number} of 3')
            self.assertContains(response,'q=Assistance+Volume')
            self.assertContains(response,'attention=generation_failed')
            seen += [row.pk for row in response.context['recent_runs']]
            self.assertNotContains(response,self.colleague.get_absolute_url())
            self.assertNotContains(response,self.different_format.get_absolute_url())
        expected=list(ReportRun.objects.filter(created_by=self.operator,output_format='csv').order_by('-created_at','-pk').values_list('pk',flat=True))
        self.assertEqual(seen,expected)
        self.assertEqual(len(set(seen)),110)
        with tempfile.TemporaryDirectory() as directory, self.settings(GRAND_EXPORT_ROOT=directory):
            response=self.client.get(reverse('reporting:run_register_export'),{**self.filters,'page':3})
        rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows),110)
        self.assertNotIn(str(self.colleague.public_id),{row['run_public_id'] for row in rows})

    def test_empty_invalid_page_and_scope_remain_explicit(self):
        self.seed(); self.client.force_login(self.operator)
        response=self.client.get(reverse('reporting:workspace'),{**self.filters,'page':'invalid'})
        self.assertEqual(response.context['run_page'].number,1)
        response=self.client.get(reverse('reporting:workspace'),{**self.filters,'page':999})
        self.assertEqual(response.context['run_page'].number,3)
        response=self.client.get(reverse('reporting:workspace'),{**self.filters,'q':'absent'})
        self.assertContains(response,'Showing 0–0 of 0 matching runs.')
        self.client.force_login(self.outsider)
        response=self.client.get(reverse('reporting:workspace'),{'page':3})
        self.assertEqual(response.context['visible_run_count'],0)
        self.assertNotContains(response,self.definition.name)

    def test_definition_preview_links_to_complete_scoped_generation_history(self):
        self.seed(); self.client.force_login(self.operator)
        url = reverse('reporting:definition_detail', args=(self.definition.pk,))
        response = self.client.get(url)
        self.assertEqual(len(response.context['runs']),15)
        self.assertContains(response,'Showing 15 of 111 visible runs')
        history_url = reverse('reporting:workspace') + f'?definition={self.definition.pk}'
        self.assertContains(response,f'href="{history_url}#report-runs"')
        self.assertNotContains(response,self.colleague.get_absolute_url())
        history = self.client.get(history_url + '&page=3')
        self.assertEqual(history.context['visible_run_count'],111)
        self.assertEqual(history.context['run_filters']['definition'],str(self.definition.pk))
        self.assertEqual(len(history.context['recent_runs']),11)
        self.assertTrue(all(run.created_by_id==self.operator.pk for run in history.context['recent_runs']))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code,404)
