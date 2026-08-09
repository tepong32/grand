from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile


class UsersServiceTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            is_staff=True,
        )
        self.normal_user = get_user_model().objects.create_user(
            username='normal',
            email='normal@example.com',
            password='testpass123',
        )

        self.admin_profile = EmployeeProfile.objects.get(user=self.admin)
        self.admin_profile.contact_number = '09123456789'
        self.admin_profile.assigned_department, _ = Department.objects.get_or_create(name='HR', slug='hr')
        self.admin_profile.save()

    def test_user_search_view_returns_match(self):
        response = self.client.get(reverse('user-search'), {'q': 'admin'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin')

    def test_export_requires_privileged_user(self):
        response = self.client.get(reverse('export_department_users', kwargs={'department': 'hr', 'format': 'csv'}))
        self.assertEqual(response.status_code, 302)

        self.client.login(username='normal', password='testpass123')
        response = self.client.get(reverse('export_department_users', kwargs={'department': 'hr', 'format': 'csv'}))
        self.assertEqual(response.status_code, 403)

    def test_export_allowed_for_privileged_users(self):
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('export_department_users', kwargs={'department': 'hr', 'format': 'csv'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response["Content-Type"])
