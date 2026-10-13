from decimal import Decimal

from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import TestCase

from . import test_budget_preparation as fixtures
from .models import BudgetExpenditureAttribution as Attribution


class PreparationSelectionTests(TestCase):
    databases = {'default', 'finance'}
    entry = fixtures.PreparationContextTests.entry
    post = fixtures.PreparationContextTests.post

    def setUp(self):
        fixtures.PreparationContextTests.setUp(self)
        self.client.force_login(self.maker)
        self.url = reverse('accounting:budget_preparation_select')
        self.scope = {'fund': self.fund.pk, 'start': '2026-09-01', 'end': '2026-09-05', 'q': ''}

    def populate(self, count):
        return [self.post(self.entry(f'PAGED-{number:03}', Decimal('1'), claim=f'PAGE-{number}'))
                for number in range(count)]

    def move(self, page, *, entries=(), action='save', **changes):
        return self.client.post(self.url, {**self.scope, 'basket': page.context['basket'],
            'page': page.context['page'].number, 'entries': list(entries), 'action': action, **changes})

    def test_selection_survives_pages_search_empty_results_and_prepares_whole_group(self):
        added = self.populate(101)
        first = self.client.get(self.url, self.scope)
        self.assertEqual(first.context['page'].paginator.count, 102)
        self.assertEqual(len(first.context['page']), 50)
        second = self.move(first, entries=[self.original.pk], action='page:2')
        self.assertEqual(second.context['page'].number, 2)
        self.assertEqual([entry.pk for entry in second.context['selected_rows']], [self.original.pk])
        chosen = list(second.context['page'])[0]
        last = self.move(second, entries=[chosen.pk], action='page:3')
        self.assertEqual(len(last.context['page']), 2)
        self.assertEqual(len(last.context['selected_rows']), 2)
        empty = self.move(last, action='search', q='NOT-A-MATCH')
        self.assertEqual(empty.context['page'].paginator.count, 0)
        self.assertEqual(len(empty.context['selected_rows']), 2)
        self.assertContains(empty, 'Search and keep selection')
        self.assertContains(empty, 'Prepare selected journals')
        editor = self.move(empty, action='prepare', q='NOT-A-MATCH')
        self.assertContains(editor, 'Prepare expenditure allocations')
        self.assertEqual({entry['id'] for entry in editor.context['context']['entries']}, {self.original.pk, chosen.pk})
        self.assertFalse(Attribution.objects.exists())

    def test_unchecking_and_removal_do_not_drop_other_pages(self):
        self.populate(51)
        first = self.client.get(self.url, self.scope)
        second = self.move(first, entries=[self.original.pk], action='page:2')
        other = list(second.context['page'])[0]
        first_again = self.move(second, entries=[other.pk], action='page:1')
        unchecked = self.move(first_again, entries=[])
        self.assertEqual([entry.pk for entry in unchecked.context['selected_rows']], [other.pk])
        removed = self.move(unchecked, remove=str(other.pk))
        self.assertFalse(removed.context['selected_rows'])
        empty = self.move(removed, action='prepare')
        self.assertContains(empty, 'Select between one and 250', status_code=400)
        self.assertFalse(Attribution.objects.exists())

    def test_signed_selection_cannot_cross_actor_period_or_page(self):
        added = self.populate(51)
        first = self.client.get(self.url, self.scope)
        forged = self.move(first, entries=[added[-1].pk])
        self.assertContains(forged, 'no longer available on this page', status_code=400)
        tampered = self.move(first, basket='x' + first.context['basket'], action='prepare')
        self.assertEqual(tampered.status_code, 400)
        changed_period = self.move(first, end='2026-09-04')
        self.assertEqual(changed_period.status_code, 403)
        self.poster.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
                                                                codename='prepare_budget_attributions'))
        self.client.force_login(self.poster)
        wrong_actor = self.move(first, entries=[self.original.pk], action='prepare')
        self.assertEqual(wrong_actor.status_code, 403)
        self.assertFalse(Attribution.objects.exists())
