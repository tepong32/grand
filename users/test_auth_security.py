from unittest.mock import patch
from datetime import timedelta

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from home.models import Announcement
from profiles.models import CitizenProfile, EmployeeProfile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = get_user_model().objects.create_user(username="employee", password="Valid-Passphrase-2026")
        cls.hr = Department.objects.create(name="Human Resources", slug="hr")
        cls.employee.employeeprofile.assigned_department = cls.hr
        cls.employee.employeeprofile.save()
        cls.citizen = get_user_model().objects.create_user(username="citizen", email="citizen@example.com", password="Valid-Passphrase-2026")
        cls.citizen.employeeprofile.delete()
        CitizenProfile.objects.create(user=cls.citizen, social_auth=False)
        cls.internal = Announcement.objects.create(user=cls.employee, title="Private office memo", slug="private-memo", content="Internal evidence", announcement_type=Announcement.INTERNAL, published=True)
        cls.draft = Announcement.objects.create(user=cls.employee, title="Draft memo", slug="draft-memo", content="Draft evidence", published=False)

    def test_public_signup_alias_uses_verified_citizen_signup(self):
        self.assertRedirects(self.client.get(reverse("register")), reverse("account_signup"))

    def test_public_signup_creates_only_citizen_and_cannot_set_privileges(self):
        response = self.client.post(reverse("account_signup"), {
            "email": "new-citizen@example.com", "password1": "Valid-New-Passphrase-2026", "password2": "Valid-New-Passphrase-2026",
            "is_staff": "true", "is_superuser": "true", "assigned_department": self.hr.pk,
        })
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email="new-citizen@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(EmployeeProfile.objects.filter(user=user).exists())
        self.assertTrue(CitizenProfile.objects.filter(user=user).exists())
        self.assertFalse(EmailAddress.objects.get(user=user).verified)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)

    def test_citizen_cannot_use_password_login_before_email_verification(self):
        EmailAddress.objects.create(user=self.citizen, email=self.citizen.email, verified=False, primary=True)
        self.client.post(reverse("login"), {"username": self.citizen.username, "password": "Valid-Passphrase-2026"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_citizen_cannot_enumerate_internal_announcements(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(self.internal.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("announcements-list")), self.internal.title)
        response = self.client.get(reverse("home"), follow=True)
        self.assertNotContains(response, self.internal.title)
        self.assertNotContains(response, self.draft.title)

    def test_employee_home_does_not_expose_drafts(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("home"), follow=True)
        self.assertNotContains(response, self.draft.title)
        if response.context:
            self.assertNotIn(self.draft, response.context.get("announcements", []))

    def test_citizen_cannot_publish_announcements(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("create-announcement")).status_code, 403)

    def test_staff_flag_alone_does_not_grant_hr_profile_mutation(self):
        self.citizen.is_staff = True
        self.citizen.save()
        self.client.force_login(self.citizen)
        response = self.client.get(reverse("profile-edit", args=[self.employee.username]))
        self.assertEqual(response.status_code, 403)

    def test_hr_profile_permission_cannot_change_another_accounts_recovery_email(self):
        self.employee.user_permissions.add(Permission.objects.get(content_type__app_label="profiles", codename="change_employeeprofile"))
        target = get_user_model().objects.create_user(username="protected-approver", email="approver@example.gov", password="Valid-Passphrase-2026")
        self.client.force_login(self.employee)
        response = self.client.post(reverse("profile-edit", args=[target.username]), {"user-email": "takeover@example.com", "user-first_name": "Updated name"})
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.first_name, "Updated name")
        self.assertEqual(target.email, "approver@example.gov")
        self.client.logout()
        mail.outbox.clear()
        self.client.post(reverse("password_reset"), {"email": "takeover@example.com"})
        self.assertEqual(mail.outbox, [])

    def test_profile_owner_uses_verified_email_management_instead_of_raw_email_update(self):
        self.client.force_login(self.citizen)
        response = self.client.post(reverse("profile-edit", args=[self.citizen.username]), {"user-email": "unverified@example.com", "user-first_name": "Updated citizen", "citizen-contact_number": "09123456789", "citizen-address": "Synthetic citizen address"})
        self.assertEqual(response.status_code, 302)
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.first_name, "Updated citizen")
        self.assertEqual(self.citizen.email, "citizen@example.com")
        self.assertContains(self.client.get(reverse("profile-edit", args=[self.citizen.username])), reverse("account_email"))

    def test_unverified_email_cannot_replace_primary_recovery_address(self):
        EmailAddress.objects.create(user=self.citizen, email=self.citizen.email, verified=True, primary=True)
        candidate = EmailAddress.objects.create(user=self.citizen, email="unverified@example.com", verified=False)
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("account_email")).status_code, 200)
        self.client.post(reverse("account_reauthenticate"), {"password": "Valid-Passphrase-2026"})
        response = self.client.post(reverse("account_email"), {"action_primary": "", "email": candidate.email})
        self.assertRedirects(response, reverse("account_email"))
        self.citizen.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(self.citizen.email, "citizen@example.com")
        self.assertFalse(candidate.primary)

    def test_email_mutation_requires_recent_authentication(self):
        self.client.force_login(self.citizen)
        response = self.client.post(reverse("account_email"), {"action_add": "", "email": "candidate@example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("account_reauthenticate")))
        self.assertFalse(EmailAddress.objects.filter(user=self.citizen, email="candidate@example.com").exists())

    def test_current_password_guesses_share_authenticated_target_counter(self):
        self.client.force_login(self.employee)
        routes = ("password_change", "admin:password_change", "account_change_password", "account_reauthenticate")
        for index in range(11):
            response = self.client.post(reverse(routes[index % len(routes)]), {"username": f"ignored-{index}", "login": f"ignored-{index}", "old_password": "wrong", "oldpassword": "wrong", "password": "wrong", "new_password1": "Valid-New-Passphrase-2026", "new_password2": "Valid-New-Passphrase-2026", "password1": "Valid-New-Passphrase-2026", "password2": "Valid-New-Passphrase-2026"}, REMOTE_ADDR=f"192.0.2.{index}")
        self.assertEqual(response.status_code, 429)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password("Valid-Passphrase-2026"))

    def test_citizen_cannot_enumerate_other_profiles(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("profile", args=[self.employee.username])).status_code, 404)
        self.assertEqual(self.client.get(reverse("profile", args=[self.citizen.username])).status_code, 200)

    def test_citizen_profile_url_uses_username(self):
        self.assertEqual(self.citizen.citizenprofile.get_absolute_url(), reverse("profile", args=[self.citizen.username]))

    def test_owners_can_open_profile_edit_with_correct_authority(self):
        for owner in (self.employee, self.citizen):
            with self.subTest(owner=owner.username):
                self.client.force_login(owner)
                response = self.client.get(reverse("profile-edit", args=[owner.username]))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["is_owner"])
                self.assertFalse(response.context["is_admin"])

    def test_employee_registration_requires_creation_permission(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("employee-register")).status_code, 403)

    def test_guessed_department_dashboard_cannot_select_another_office(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("department_dashboard"), {"department": "mswd", "slug": "mswd"})
        self.assertEqual(response.context["department"], self.hr)

    def test_citizen_dashboard_is_distinct(self):
        self.client.force_login(self.citizen)
        response = self.client.get(reverse("department_dashboard"), follow=True)
        self.assertContains(response, "Your citizen dashboard")
        self.assertNotContains(response, "Internal announcements")

    def test_direct_department_detail_is_public_safe(self):
        response = self.client.get(reverse("departments:detail", args=[self.hr.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Department team")
        self.assertNotContains(response, "Internal announcements")

    def test_login_rejects_external_redirect_and_preserves_safe_next(self):
        for destination in ("https://evil.example/", "//evil.example/", "javascript:alert(1)"):
            with self.subTest(destination=destination):
                self.client.logout()
                response = self.client.post(reverse("login"), {"username": self.employee.username, "password": "Valid-Passphrase-2026", "next": destination})
                self.assertEqual(response.url, reverse("department_dashboard"))
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": self.employee.username, "password": "Valid-Passphrase-2026", "next": "/profiles/employee/"})
        self.assertEqual(response.url, "/profiles/employee/")

    def test_csrf_and_logout_methods(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("login"), {"username": "employee", "password": "Valid-Passphrase-2026"}).status_code, 403)
        client.force_login(self.employee)
        self.assertEqual(client.get(reverse("logout")).status_code, 405)
        self.assertEqual(client.post(reverse("logout")).status_code, 403)

    def test_inactive_account_and_generic_failure(self):
        self.employee.is_active = False
        self.employee.save()
        response = self.client.post(reverse("login"), {"username": self.employee.username, "password": "Valid-Passphrase-2026"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotContains(response, "inactive")

    def test_login_rotates_existing_session_and_post_logout_clears_it(self):
        session = self.client.session
        session["visitor"] = True
        session.save()
        old_key = session.session_key
        self.client.post(reverse("login"), {"username": self.employee.username, "password": "Valid-Passphrase-2026"})
        self.assertNotEqual(self.client.session.session_key, old_key)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_response_does_not_disclose_existing_account(self):
        existing = self.client.post(reverse("password_reset"), {"email": self.citizen.email})
        missing = self.client.post(reverse("password_reset"), {"email": "missing@example.com"})
        self.assertEqual(existing.status_code, missing.status_code)
        self.assertEqual(existing.url, missing.url)

    def test_repeated_login_posts_are_throttled_across_login_routes(self):
        paths = [reverse("login"), reverse("account_login"), reverse("admin:login")]
        responses = [self.client.post(paths[i % 3], {"username": f"missing-{i}", "password": "wrong"}) for i in range(32)]
        self.assertEqual(responses[-1].status_code, 429)
        self.assertIn("Retry-After", responses[-1])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_identity_limit_survives_changing_ip_and_forwarded_headers(self):
        for index in range(11):
            response = self.client.post(reverse("login"), {"username": "target", "password": "wrong"}, REMOTE_ADDR=f"192.0.2.{index}", HTTP_X_FORWARDED_FOR=f"198.51.100.{index}")
        self.assertEqual(response.status_code, 429)

    def test_ignored_login_field_cannot_change_django_target_counter(self):
        for index in range(11):
            response = self.client.post(reverse("login"), {"username": self.employee.username, "login": f"ignored-{index}", "password": "wrong"}, REMOTE_ADDR=f"192.0.2.{index}")
        self.assertEqual(response.status_code, 429)

    def test_login_username_and_email_aliases_share_account_counter(self):
        self.employee.email = "employee@example.com"
        self.employee.save()
        EmailAddress.objects.create(user=self.employee, email=self.employee.email, verified=True)
        for index in range(11):
            path = reverse("login" if index % 2 else "account_login")
            data = {"username": self.employee.username} if index % 2 else {"login": self.employee.email}
            response = self.client.post(path, {**data, "password": "wrong"}, REMOTE_ADDR=f"192.0.2.{index}")
        self.assertEqual(response.status_code, 429)

    def test_unicode_username_normalization_shares_target_counter(self):
        for index in range(11):
            username = "ｅｍｐｌｏｙｅｅ" if index % 2 else self.employee.username
            response = self.client.post(reverse("login"), {"username": username, "password": "wrong"}, REMOTE_ADDR=f"192.0.2.{index}")
        self.assertEqual(response.status_code, 429)

    def test_ignored_email_cannot_change_password_confirmation_target(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        path = reverse("password_reset_confirm", kwargs={"uidb64": urlsafe_base64_encode(force_bytes(self.employee.pk)), "token": "set-password"})
        for index in range(6):
            response = self.client.post(path, {"email": f"ignored-{index}@example.com"}, REMOTE_ADDR=f"192.0.2.{index}")
        self.assertEqual(response.status_code, 429)

    def test_password_reset_delivery_failure_remains_generic(self):
        with patch("django.contrib.auth.forms.PasswordResetForm.send_mail", side_effect=RuntimeError("smtp")):
            existing = self.client.post(reverse("password_reset"), {"email": self.citizen.email})
            missing = self.client.post(reverse("password_reset"), {"email": "missing@example.com"})
        self.assertEqual(existing.url, missing.url)
        self.assertEqual(existing.status_code, 302)

    def test_authorized_hr_can_create_employee_in_explicit_department(self):
        self.employee.user_permissions.add(Permission.objects.get(content_type__app_label="users", codename="add_user"))
        self.client.force_login(self.employee)
        response = self.client.post(reverse("employee-register"), {"username": "new-employee", "email": "staff@example.gov", "password1": "Valid-New-Passphrase-2026", "password2": "Valid-New-Passphrase-2026", "assigned_department": self.hr.pk, "is_superuser": True})
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username="new-employee")
        self.assertEqual(user.employeeprofile.assigned_department, self.hr)
        self.assertFalse(CitizenProfile.objects.filter(user=user).exists())
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_mixed_legacy_identity_is_quarantined_without_deletion(self):
        CitizenProfile.objects.create(user=self.employee)
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("department_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("users-list")).status_code, 403)
        self.assertTrue(EmployeeProfile.objects.filter(user=self.employee).exists())
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)

    def test_new_employee_has_no_implicit_mayor_assignment(self):
        user = get_user_model().objects.create_user(username="unassigned", email="unassigned@example.com")
        self.assertIsNone(user.employeeprofile.assigned_department)

    def test_public_google_identity_exists_before_social_record_is_saved(self):
        from allauth.socialaccount.adapter import get_adapter as get_social_adapter
        from allauth.socialaccount.models import SocialAccount, SocialLogin

        request = RequestFactory().get("/")
        sociallogin = SocialLogin(account=SocialAccount(provider="google", uid="synthetic-google-id"))
        user = get_social_adapter().new_user(request, sociallogin)
        user.username = "social-citizen"
        user.email = "social-citizen@example.com"
        user.save()
        self.assertTrue(CitizenProfile.objects.filter(user=user, social_auth=True).exists())
        self.assertFalse(EmployeeProfile.objects.filter(user=user).exists())

    def test_verified_citizen_can_login(self):
        EmailAddress.objects.create(user=self.citizen, email=self.citizen.email, verified=True, primary=True)
        response = self.client.post(reverse("login"), {"username": self.citizen.username, "password": "Valid-Passphrase-2026"}, follow=True)
        self.assertContains(response, "Your citizen dashboard")

    def test_citizen_cannot_read_leave_data(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("leave_list")).status_code, 403)

    def test_owner_cannot_forge_own_department_or_staff_flags(self):
        self.client.force_login(self.employee)
        other = Department.objects.create(name="Other Office", slug="other-office")
        self.client.post(reverse("profile-edit", args=[self.employee.username]), {"user-email": "employee@example.com", "user-is_staff": "true", "hr-assigned_department": other.pk})
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_staff)
        self.assertEqual(self.employee.employeeprofile.assigned_department, self.hr)

    def test_throttling_also_covers_public_signup_and_password_reset(self):
        for route in ("account_signup", "password_reset"):
            for index in range(11):
                response = self.client.post(reverse(route), {"email": f"probe{index}@example.com"})
            self.assertEqual(response.status_code, 429)

    def test_csrf_required_for_all_public_auth_entrypoints(self):
        client = Client(enforce_csrf_checks=True)
        for route in ("account_signup", "account_login", "password_reset", "register"):
            with self.subTest(route=route):
                self.assertEqual(client.post(reverse(route), {"email": "probe@example.com"}).status_code, 403)

    def test_colleague_profile_hides_contact_address_and_leave_balances(self):
        peer = get_user_model().objects.create_user(username="peer", email="private-peer@example.com")
        peer.employeeprofile.contact_number = "09999999999"
        peer.employeeprofile.address = "Sensitive residential address"
        peer.employeeprofile.save()
        self.client.force_login(self.employee)
        response = self.client.get(reverse("profile", args=[peer.username]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, peer.email)
        self.assertNotContains(response, "09999999999")
        self.assertNotContains(response, "Sensitive residential address")
        self.assertIsNone(response.context["leave_credits"])


class ThrottleStorageTests(TestCase):
    def test_expiry_reopens_counter_and_pruning_retains_active_buckets(self):
        from django.core.management import call_command
        from users.auth_throttle import consume_attempt
        from users.models import AuthAttemptBucket

        self.assertTrue(consume_attempt("test", "identity", limit=1))
        self.assertFalse(consume_attempt("test", "identity", limit=1))
        AuthAttemptBucket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(consume_attempt("test", "identity", limit=1))
        call_command("prune_auth_attempts")
        self.assertEqual(AuthAttemptBucket.objects.count(), 1)

    def test_counter_storage_failure_fails_closed(self):
        from django.db import OperationalError
        with patch("users.auth_throttle.consume_attempt", side_effect=OperationalError("unavailable")):
            response = self.client.post(reverse("login"), {"username": "unknown", "password": "wrong"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("_auth_user_id", self.client.session)


class AuthURLProbeTests(TestCase):
    databases = {"default", "finance"}

    def test_guessed_module_urls_deny_anonymous_and_citizen_access(self):
        user = get_user_model().objects.create_user(username="url-probe-citizen")
        user.employeeprofile.delete()
        CitizenProfile.objects.create(user=user)
        paths = ("/users/", "/users/search/?q=employee", "/users/employee-register/", "/finance/", "/finance/setup/", "/finance/vouchers/", "/finance/accounting/", "/finance/budget/", "/reports/", "/records/", "/tracepoint/", "/social-welfare/", "/assistance/mswd/dashboard/", "/assistance/mswd/citizens/", "/leave-mgt/")
        for actor in (None, user):
            if actor:
                self.client.force_login(actor)
            for path in paths:
                with self.subTest(actor="citizen" if actor else "anonymous", path=path):
                    response = self.client.get(path)
                    self.assertIn(response.status_code, (302, 403, 404))

    def test_guessed_object_and_export_urls_cannot_bypass_office_scope(self):
        user = get_user_model().objects.create_user(username="url-probe-employee")
        user.employeeprofile.assigned_department = Department.objects.create(name="Probe General Services", slug="probe-gso")
        user.employeeprofile.save()
        self.client.force_login(user)
        for path in ("/users/users/export/hr/csv/", "/users/export/all/csv/", "/assistance/mswd/citizens/1/", "/assistance/mswd/request/KNOWN-REF/", "/assistance/mswd/request/KNOWN-REF/print/", "/finance/accounting/", "/finance/setup/"):
            with self.subTest(path=path):
                self.assertIn(self.client.get(path).status_code, (302, 403, 404))
