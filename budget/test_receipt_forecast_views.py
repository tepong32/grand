from copy import deepcopy
import json
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from .test_receipt_forecast_reviews import ReceiptForecastReviewFixture
from .models import BudgetReceiptForecast as Record
from . import receipt_forecast_reviews as service, receipt_forecast_views as views


class ReceiptForecastViewTests(ReceiptForecastReviewFixture):
    def setUp(self):
        super().setUp()
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='export_native_budget_actuals'))

    def url(self, name, *args):
        return reverse('budget:'+name, args=args)

    def payload(self):
        args = self.inputs()
        def components(rows):
            return [dict(id=row['key'], source_id=row['source_id'], amount=row['amount'],
                disposition=row['disposition'], category=row['category'], account_id=str(row['account_id']) if row['account_id'] else '',
                funding_reference=row['coverage_key'], overlap_of=row['overlap_of'], basis=row['basis']) for row in rows]
        return dict(half_sources=args['half_sources'], entities=[dict(entity_key='general',
            half_components=components(args['half_components']), proposed_components=components(args['proposed_components']),
            coverage={column:[{key:row[key] for key in ('category','coverage','basis')} for row in rows]
                for column, rows in args['coverage'].items()})])

    def create_http(self, **changes):
        self.client.force_login(self.preparer)
        url = self.url('receipt_forecast_prepare', self.version.public_id, self.fund.pk)
        get = self.client.get(url); self.assertEqual(get.status_code, 200)
        data = dict(preview=get.context['form']['preview'].value(), allocation=json.dumps(self.payload()),
            coverage_reference='Synthetic complete clerk entity/source declaration', coverage_confirmed='on')
        data.update(changes)
        response = self.client.post(url, data)
        return response, data

    def test_guided_prepare_independent_review_full_export_and_no_posting(self):
        before = JournalEntry.objects.count()
        response, data = self.create_http()
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        record = Record.objects.get()
        detail = self.client.get(response.url)
        self.assertContains(detail, 'Service/user charges')
        self.assertContains(detail, 'Observed as of 2026-09-01')
        self.assertContains(detail, 'Shared source worksheet 0')
        self.assertContains(detail, 'Shared source limits across all entities')
        self.assertNotContains(detail, 'Independent Budget Officer review</h2>')
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(response.url), 'Independent Budget Officer review</h2>')
        review = self.url('receipt_forecast_review', record.public_id)
        self.assertEqual(self.client.post(review, dict(action='approve',authority='Synthetic designated Budget Officer',
            note='Verified dated worksheets, mappings and explicit overlaps')).status_code, 302)
        export = self.url('receipt_forecast_export', record.public_id)
        result = self.client.get(export)
        self.assertEqual(result.status_code, 200)
        retained = json.loads(result.content)
        self.assertEqual(retained['reviewed_totals']['general']['proposed'], '100.00')
        self.assertEqual(len(retained['payload']['group']['members'][0]['forecast']['payload']['columns']['proposed']['components']), 2)
        self.assertEqual(result['X-GRAND-Export-SHA256'], __import__('hashlib').sha256(result.content).hexdigest())
        original = result.content
        self.revenue.title = 'Later account title'; self.revenue.save(update_fields=('title',))
        self.assertEqual(self.client.get(export).content, original)
        self.assertContains(self.client.get(response.url), 'Historical review; current sources or latest package changed')
        self.assertEqual(JournalEntry.objects.count(), before)

    def test_signed_scope_replay_invalid_split_and_bound_rows_survive_errors(self):
        response, data = self.create_http(coverage_confirmed='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['editor']['allocation'], self.payload())
        self.assertFalse(Record.objects.exists())
        bad = deepcopy(self.payload()); bad['entities'][0]['proposed_components'][1]['amount'] = '99'
        response, data = self.create_http(allocation=json.dumps(bad))
        self.assertContains(response, 'Partition every retained source amount exactly')
        self.assertEqual(response.context['editor']['allocation'], bad)
        response, data = self.create_http()
        self.assertEqual(response.status_code, 302)
        url = self.url('receipt_forecast_prepare', self.version.public_id, self.fund.pk)
        self.assertContains(self.client.post(url, data), 'preview changed')
        self.client.force_login(self.reviewer)
        # Another authorized preparer must not use the first actor's signed preview.
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',codename='prepare_budget_receipt_forecasts'))
        self.assertContains(self.client.post(url, data), 'another actor')
        self.assertEqual(Record.objects.count(), 1)

    def test_permissions_uat_mutation_separate_export_and_csrf(self):
        response, data = self.create_http()
        record = Record.objects.get()
        detail = response.url; review = self.url('receipt_forecast_review', record.public_id)
        export = self.url('receipt_forecast_export', record.public_id)
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.assertEqual(self.client.get(export).status_code, 403)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(self.url('receipt_forecast_prepare',self.version.public_id,self.fund.pk),data).status_code, 403)
        self.client.force_login(self.reviewer)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.reviewer)
        self.assertEqual(csrf.post(review,dict(action='approve',authority='Valid designation',note='Valid review')).status_code,403)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',codename='view_budget_receipt_forecasts'))
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals'))
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.assertEqual(self.client.get(export).status_code, 200)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='export_native_budget_actuals'))
        self.assertEqual(self.client.get(export).status_code, 403)

    def test_register_navigation_and_editor_account_scope_without_json_entry(self):
        self.client.force_login(self.preparer)
        register = self.url('receipt_forecasts',self.version.public_id)
        self.assertContains(self.client.get(self.url('version_detail',self.version.public_id)), register)
        self.assertContains(self.client.get(register), '0 retained packages')
        page = self.client.get(self.url('receipt_forecast_prepare',self.version.public_id,self.fund.pk))
        self.assertContains(page, 'forecast-editor-data')
        self.assertContains(page, 'budget-receipt-forecasts.js')
        self.assertNotIn(str(self.account.pk), [row['id'] for row in page.context['editor']['accounts']])
        self.assertIn(str(self.revenue.pk), [row['id'] for row in page.context['editor']['accounts']])
        record = self.prepare_forecast()
        changed = deepcopy(record.payload); changed['group']['controls']['proposed']['diagnostic_total'] = '999.00'
        Record.objects.filter(pk=record.pk).update(payload=changed,payload_checksum=checksum(changed))
        self.assertEqual(self.client.get(self.url('receipt_forecast_detail',record.public_id)).status_code, 409)
        self.assertEqual(self.client.get(self.url('receipt_forecast_export',record.public_id)).status_code, 409)
