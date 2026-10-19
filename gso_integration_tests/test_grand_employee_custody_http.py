from time import time
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from profiles.models import EmployeeProfile

from inventory.models import Asset, AssetTransfer
from inventory.services import cancel_asset_transfer
from . import test_grand_employee_custody


class EmployeeCustodyHttpTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        test_grand_employee_custody.GrandEmployeeCustodyTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.clerk)
        self.url = reverse("inventory:employee-handoff", args=[self.asset.pk])

    def csrf(self):
        return self.client.cookies["csrftoken"].value

    def search_people(self, total=53):
        from django.contrib.auth import get_user_model
        people = []
        for number in range(total):
            person = get_user_model().objects.create_user(username=f'page-search-{number:03}',
                email=f'page-search-{number:03}@example.test', first_name='Repeated', last_name=f'Directory{number:03}')
            EmployeeProfile.objects.filter(user=person).update(assigned_department=self.other)
            people.append(person)
        return people

    def search_preview(self, person, *, page=2, **changes):
        from django.utils import timezone
        self.client.get(self.url, {'q': 'page-search', 'employee_page': page})
        values = {'action': 'preview', 'query': 'page-search', 'employee_page': str(page),
            'employee_id': person.pk, 'transfer_date': timezone.localdate().isoformat(),
            'reference': 'PAR-PAGED-01', 'reason': 'Documented receiving employee', 'csrfmiddlewaretoken': self.csrf()}
        values.update(changes)
        return self.client.post(self.url, values)

    def test_employee_search_reaches_every_match_with_bounded_pages(self):
        people = self.search_people()
        found = []
        for number, size in ((1, 25), (2, 25), (3, 3)):
            response = self.client.get(self.url, {'q': 'page-search', 'employee_page': number})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['employees']), size)
            found.extend(person.pk for person in response.context['employees'])
        self.assertEqual(found, [person.pk for person in people])
        self.assertEqual(len(set(found)), 53)

    def test_employee_search_page_survives_invalid_handoff_details(self):
        people = self.search_people()
        response = self.search_preview(people[30], reference='')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="employee_page"')
        self.assertEqual(response.context['form']['employee_id'].value(), str(people[30].pk))
        self.assertEqual(response.context['form']['reason'].value(), 'Documented receiving employee')
        self.assertEqual(response.context['employee_page'].number, 2)
        self.assertIsNone(response.context['preview'])
        self.assertFalse(AssetTransfer.objects.exists())

    def test_employee_search_applies_profile_visibility_before_page_counts(self):
        people = self.search_people()
        allowed = {person.pk for person in people[25:]}
        with patch('profiles.services.profile_service.can_view_profile',
                   side_effect=lambda actor, target: target.pk in allowed):
            response = self.client.get(self.url, {'q': 'page-search'})
        self.assertEqual([person.pk for person in response.context['employees']], [person.pk for person in people[25:50]])
        self.assertEqual(response.context['employee_page'].paginator.count, 28)

    def test_employee_search_later_page_completes_one_signed_handoff_and_acknowledgment(self):
        from django.contrib.auth.models import Permission
        people = self.search_people()
        target = people[30]
        target.user_permissions.add(*Permission.objects.filter(content_type__app_label='inventory',
            codename__in=('view_asset', 'acknowledge_asset_transfer')))
        response = self.search_preview(target)
        self.assertIsNotNone(response.context['preview'])
        token = response.context['confirmation'].initial['handoff_token']
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(self.confirm(token).status_code, 302)
        transfer = AssetTransfer.objects.get()
        self.assertEqual(transfer.destination_custodian_user_id, target.pk)
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.custodian_user_id)
        self.client.force_login(target)
        self.client.get(reverse('inventory:asset-transfer-list'))
        response = self.client.post(reverse('inventory:asset-transfer-acknowledge', args=[transfer.pk]),
            {'csrfmiddlewaretoken': self.csrf()})
        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, target.pk)
        self.assertEqual(self.asset.audit_events.count(), 1)
        self.assertEqual(AssetTransfer.objects.count(), 1)

    def test_employee_search_rejects_an_id_outside_the_posted_page(self):
        people = self.search_people()
        response = self.search_preview(people[0], page=2)
        self.assertIsNone(response.context['preview'])
        self.assertIn('employee_id', response.context['form'].errors)
        self.assertFalse(AssetTransfer.objects.exists())

    def test_employee_search_keeps_eligibility_authority_and_finance_boundaries(self):
        from django.db import connections
        from django.test.utils import CaptureQueriesContext
        people = self.search_people(28)
        people[0].is_active = False; people[0].save(update_fields=['is_active'])
        EmployeeProfile.objects.filter(user=people[1]).update(assigned_department=None)
        before = list(Asset.objects.values())
        with CaptureQueriesContext(connections['finance']) as finance:
            responses = [self.client.get(self.url, {'q': 'page-search', 'employee_page': page}) for page in (1, 2)]
        ids = [person.pk for response in responses for person in response.context['employees']]
        self.assertEqual(ids, [person.pk for person in people[2:]])
        self.assertEqual(len(finance), 0)
        self.assertEqual(list(Asset.objects.values()), before)
        for actor in (self.viewer, self.super_no_grant):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.url, {'q': 'page-search', 'employee_page': '2'}).status_code, 403)

    def test_employee_search_later_page_still_rejects_a_changed_identity(self):
        people = self.search_people()
        response = self.search_preview(people[30])
        self.assertIsNotNone(response.context['preview'])
        token = response.context['confirmation'].initial['handoff_token']
        EmployeeProfile.objects.filter(user=people[30]).update(assigned_department=self.gso)
        self.assertEqual(self.confirm(token).status_code, 200)
        self.assertFalse(AssetTransfer.objects.exists())
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.custodian_user_id)

    def preview(self):
        response = self.client.get(self.url, {"q": "repair-out"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        response = self.client.post(self.url, {"action": "preview", "query": "repair-out",
            "employee_id": self.outsider.pk, "transfer_date": "2026-10-17",
            "reference": "PAR-HTTP-01", "reason": "Documented receipt",
            "csrfmiddlewaretoken": self.csrf()})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["preview"], response.content.decode())
        return response.context["confirmation"].initial["handoff_token"]

    def confirm(self, token):
        return self.client.post(self.url, {"action": "confirm", "handoff_token": token,
            "csrfmiddlewaretoken": self.csrf()})

    def test_preview_retry_and_named_recipient_in_another_gso_office(self):
        self.assertContains(self.client.get(reverse("inventory:asset-detail", args=[self.asset.pk])),
                            "Hand over to employee")
        token = self.preview()
        self.assertFalse(AssetTransfer.objects.exists())
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(self.confirm(token).status_code, 302)
        transfer = AssetTransfer.objects.get()
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("inventory:asset-transfer-list"))
        self.assertContains(response, "PAR-HTTP-01")
        self.assertContains(response, "Acknowledge receipt")
        self.assertNotContains(response, "Cancel handoff")
        self.assertEqual(self.client.post(reverse("inventory:asset-transfer-acknowledge", args=[transfer.pk]),
            {"csrfmiddlewaretoken": self.csrf()}).status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.custodian_user_id, self.outsider.pk)
        self.client.force_login(self.clerk)
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(AssetTransfer.objects.count(), 1)
        self.assertEqual(self.asset.audit_events.count(), 1)
        self.assertRedirects(self.client.get(reverse("inventory:asset-transfer-create", args=[self.asset.pk])),
                             self.url, fetch_redirect_response=False)

    def test_csrf_tampering_expiry_and_actor_binding(self):
        token = self.preview()
        self.assertEqual(self.client.post(self.url, {"action": "confirm", "handoff_token": token}).status_code, 403)
        self.assertContains(self.confirm(token + "changed"), "expired or changed")
        with patch("django.core.signing.time.time", return_value=time() + 1900):
            self.assertContains(self.confirm(token), "expired or changed")
        other_asset = Asset.objects.create(asset_name="Other asset", department_id=self.gso.pk)
        self.assertEqual(self.client.post(reverse("inventory:employee-handoff", args=[other_asset.pk]), {
            "action": "confirm", "handoff_token": token, "csrfmiddlewaretoken": self.csrf()}).status_code, 403)
        EmployeeProfile.objects.filter(user=self.no_grant).update(assigned_department=self.gso)
        self.client.force_login(self.no_grant)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.client.force_login(self.super_no_grant)
        self.assertEqual(self.confirm(token).status_code, 403)
        self.assertFalse(AssetTransfer.objects.exists())

    def test_changed_asset_preview_and_cancelled_retry_do_not_create_new_handoff(self):
        token = self.preview()
        Asset.objects.filter(pk=self.asset.pk).update(assigned_office="Reconciled legacy custodian")
        self.assertEqual(self.confirm(token).status_code, 200)
        self.assertFalse(AssetTransfer.objects.exists())
        token = self.preview()
        self.assertEqual(self.confirm(token).status_code, 302)
        transfer = AssetTransfer.objects.get()
        cancel_asset_transfer(actor=self.clerk, transfer=transfer, reason="Review request")
        self.assertEqual(self.confirm(token).status_code, 302)
        self.assertEqual(AssetTransfer.objects.count(), 1)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, AssetTransfer.CANCELLED)
