from django.contrib.auth import get_user_model
from django.test import TestCase

from profiles.services.file_service import generate_memo_filename, uploaded_images_directory_path
from departments.models import Department
from profiles.models import EmployeeProfile


class ProfileServiceTests(TestCase):
    def _memo_fixture(self):
        import io
        import tempfile
        from pathlib import Path
        from PIL import Image
        from django.contrib.auth.models import Permission
        from django.test import override_settings

        directory = tempfile.TemporaryDirectory(prefix='grand-memo-tests-')
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.memo_root = Path(directory.name)
        image = io.BytesIO()
        Image.new('RGB', (8, 8), 'navy').save(image, format='PNG')
        self.memo_bytes = image.getvalue()
        User = get_user_model()
        self.owner = User.objects.create_user(username='memo-owner', email='memo-owner@example.test')
        self.coworker = User.objects.create_user(username='memo-peer', email='memo-peer@example.test')
        self.hr = User.objects.create_user(username='memo-hr', email='memo-hr@example.test')
        self.hr_reader = User.objects.create_user(username='memo-hr-reader', email='memo-hr-reader@example.test')
        hr_department = Department.objects.create(name='Human Resources', slug='hr')
        EmployeeProfile.objects.filter(user__in=[self.hr, self.hr_reader]).update(assigned_department=hr_department)
        self.hr.user_permissions.add(Permission.objects.get(content_type__app_label='profiles', codename='change_employeeprofile'))
        self.memo_name = 'users/memo-owner/memos/private-memo.png'
        destination = self.memo_root / self.memo_name
        destination.parent.mkdir(parents=True)
        destination.write_bytes(self.memo_bytes)
        EmployeeProfile.objects.filter(user=self.owner).update(assigned_department_memo=self.memo_name)
        self.memo_url = f'/profiles/{self.owner.username}/memo/'

    def test_memo_upload_path_uses_existing_profile_identity(self):
        from profiles.services.file_service import temp_memo_path
        self._memo_fixture()
        path = temp_memo_path(self.owner.employeeprofile, 'assignment.png')
        self.assertTrue(path.startswith(f'users/{self.owner.pk}/memos/'))
        self.assertEqual(path.count('/memos/'), 1)
        self.assertTrue(path.endswith('.png'))
        self.assertLessEqual(len(path), 100)

    def test_assignment_memo_raw_media_is_denied_but_avatar_is_public(self):
        from django.http import Http404
        from django.test import RequestFactory
        from src.media import serve_development_media
        self._memo_fixture()
        factory = RequestFactory()
        with self.assertRaises(Http404):
            response = serve_development_media(factory.get('/media/' + self.memo_name), self.memo_name)
            response.file_to_stream.close()
        avatar = self.memo_root / 'users/memo-owner/uploads/avatar.png'
        avatar.parent.mkdir(parents=True)
        avatar.write_bytes(self.memo_bytes)
        response = serve_development_media(factory.get('/media/users/memo-owner/uploads/avatar.png'), 'users/memo-owner/uploads/avatar.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response), self.memo_bytes)
        response.file_to_stream.close()
        # A public avatar whose filename is "memos" is not a memo directory.
        avatar_without_extension = avatar.with_name('memos')
        avatar_without_extension.write_bytes(self.memo_bytes)
        response = serve_development_media(factory.get('/media/users/memo-owner/uploads/memos'), 'users/memo-owner/uploads/memos')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response), self.memo_bytes)
        response.file_to_stream.close()

    def test_hr_edit_uses_only_controlled_memo_links(self):
        self._memo_fixture()
        self.client.force_login(self.hr)
        response = self.client.get(f'/profiles/{self.owner.username}/edit/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '/media/' + self.memo_name)
        self.assertContains(response, self.memo_url)
        self.assertContains(response, 'Replace memo')

    def test_memo_download_uses_existing_sensitive_profile_authority(self):
        self._memo_fixture()
        self.assertEqual(self.client.get(self.memo_url).status_code, 302)
        for actor in [self.owner, self.hr]:
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                response = self.client.get(self.memo_url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'image/png')
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                self.assertIn('no-store', response['Cache-Control'])
                self.assertEqual(response['Referrer-Policy'], 'no-referrer')
                self.assertEqual(response['X-GRAND-File-Integrity'], 'not-recorded')
                self.assertEqual(b''.join(response), self.memo_bytes)
        for actor in [self.coworker, self.hr_reader]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.memo_url).status_code, 404)
        self.client.force_login(self.hr)
        self.assertEqual(self.client.post(self.memo_url).status_code, 405)
        self.hr.user_permissions.clear()
        self.assertEqual(self.client.get(self.memo_url).status_code, 404)

    def test_owner_profile_shows_memo_without_exposing_it_to_coworker(self):
        self._memo_fixture()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(f'/profiles/{self.owner.username}/'), self.memo_url)
        self.client.force_login(self.coworker)
        response = self.client.get(f'/profiles/{self.owner.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.memo_url)
        self.assertNotContains(response, 'private-memo.png')

    def test_memo_missing_unsafe_and_redirected_files_fail_closed(self):
        from unittest.mock import patch
        from django.http import Http404
        from django.test import RequestFactory
        from src.media import serve_development_media
        self._memo_fixture()
        self.client.force_login(self.owner)
        for name in ['users/memo-owner/memos/missing.png', '../private.png',
                     '/absolute.png', 'users/memo-owner/uploads/avatar.png',
                     'users/memo-owner/memos/../../private.png',
                     'users\\memo-owner\\memos\\private.png']:
            with self.subTest(name=name):
                EmployeeProfile.objects.filter(user=self.owner).update(assigned_department_memo=name)
                self.assertEqual(self.client.get(self.memo_url).status_code, 404)
        EmployeeProfile.objects.filter(user=self.owner).update(assigned_department_memo='')
        self.assertEqual(self.client.get(self.memo_url).status_code, 404)
        EmployeeProfile.objects.filter(user=self.owner).update(assigned_department_memo=self.memo_name)
        from pathlib import Path
        real_resolve = Path.resolve
        target = self.memo_root.resolve() / self.memo_name
        def redirected(path, *args, **kwargs):
            return self.memo_root / 'elsewhere.png' if path == target else real_resolve(path, *args, **kwargs)
        with patch.object(Path, 'resolve', redirected):
            self.assertEqual(self.client.get(self.memo_url).status_code, 404)
        for path in ['USERS/memo-owner/MEMOS/private.png', 'users/memo-owner/memos/nested/old.png']:
            with self.assertRaises(Http404):
                serve_development_media(RequestFactory().get('/media/' + path), path)

    def test_memo_unknown_content_downloads_as_binary_and_same_handle_streams(self):
        from unittest.mock import patch
        from django.db.models.fields.files import FieldFile
        self._memo_fixture()
        broken_png = bytearray(self.memo_bytes)
        broken_png[broken_png.index(b'IDAT') + 4] ^= 1
        payloads = [b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', bytes(broken_png), b'']
        self.client.force_login(self.owner)
        original_open = FieldFile.open
        for payload in payloads:
            with self.subTest(size=len(payload)):
                (self.memo_root / self.memo_name).write_bytes(payload)
                opened = []
                def capture(field, *args, **kwargs):
                    source = original_open(field, *args, **kwargs)
                    opened.append(source)
                    return source
                with patch.object(FieldFile, 'open', capture):
                    response = self.client.get(self.memo_url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response['Content-Type'], 'application/octet-stream')
                    self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
                    self.assertEqual(len(opened), 1)
                    self.assertEqual(b''.join(response), payload)
                    self.assertTrue(opened[0].closed)

    def test_unrelated_profile_save_preserves_original_memo_path_and_bytes(self):
        self._memo_fixture()
        profile = EmployeeProfile.objects.get(user=self.owner)
        profile.note = 'Updated contact note'
        profile.save(update_fields=['note'])
        profile.refresh_from_db()
        self.assertEqual(profile.assigned_department_memo.name, self.memo_name)
        self.assertEqual((self.memo_root / self.memo_name).read_bytes(), self.memo_bytes)

    def test_hr_memo_upload_replace_and_clear_keep_existing_audit(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from profiles.models import ProfileEditLog
        self._memo_fixture()
        self.client.force_login(self.hr)
        original = self.memo_root / self.memo_name
        payload = {'user-first_name': 'Memo', 'user-last_name': 'Owner',
                   'hr-assigned_department': '', 'hr-plantilla': '',
                   'hr-employment_type': '', 'hr-position_title': '',
                   'hr-step_increment': ''}
        for _ in range(2):
            response = self.client.post(f'/profiles/{self.owner.username}/edit/',
                {**payload, 'hr-assigned_department_memo': SimpleUploadedFile('assignment.png', self.memo_bytes, content_type='image/png')})
            self.assertEqual(response.status_code, 302)
            profile = EmployeeProfile.objects.get(user=self.owner)
            name = profile.assigned_department_memo.name
            self.assertTrue(name.startswith(f'users/{self.owner.pk}/memos/'))
            self.assertEqual(name.count('/memos/'), 1)
            self.assertEqual((self.memo_root / name).read_bytes(), self.memo_bytes)
            self.assertTrue(original.exists())
            original = self.memo_root / name
        response = self.client.post(f'/profiles/{self.owner.username}/edit/',
            {**payload, 'hr-assigned_department_memo-clear': 'on'})
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertFalse(profile.assigned_department_memo)
        self.assertTrue(original.exists())
        self.assertEqual(self.client.get(self.memo_url).status_code, 404)
        self.assertEqual(ProfileEditLog.objects.filter(user=self.owner, edited_by=self.hr, section='HR Fields').count(), 3)

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
