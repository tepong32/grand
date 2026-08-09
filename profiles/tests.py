from django.contrib.auth import get_user_model
from django.test import TestCase

from profiles.services.file_service import generate_memo_filename, uploaded_images_directory_path
from departments.models import Department
from profiles.models import EmployeeProfile


class ProfileServiceTests(TestCase):
    def test_memo_filename_includes_department_slug_and_date(self):
        user = get_user_model().objects.create_user(
            username='profile_user',
            email='profile_user@example.com',
            password='testpass123'
        )
        dept = Department.objects.create(name='Office of the Mayor', slug='office-of-the-mayor')
        profile = EmployeeProfile.objects.get(user=user)
        profile.assigned_department = dept
        profile.save()

        filename = generate_memo_filename(profile, 'memo.png')
        self.assertIn('memo_profile_user_office_of_the_mayor_', filename)
        self.assertTrue(filename.endswith('.png'))

    def test_uploaded_image_path_uses_username(self):
        user = get_user_model().objects.create_user(
            username='john doe',
            email='john@example.com',
            password='testpass123'
        )
        profile = EmployeeProfile.objects.get(user=user)

        path = uploaded_images_directory_path(profile, 'avatar.jpg')
        self.assertEqual(path, 'users/john_doe/uploads/avatar.jpg')
