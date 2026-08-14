from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Announcement, ServiceShortcut, SiteConfiguration


class UnauthenticatedHomeTests(TestCase):
    def test_public_navigation_uses_real_plain_language_destinations(self):
        response = self.client.get(reverse('unauthedhome'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Municipal services", content)
        self.assertIn("Employee sign in", content)
        self.assertIn("Office contacts", content)
        self.assertNotIn("Office Portals", content)
        self.assertNotIn("Coming soon", content)

    def test_public_home_uses_seeded_service_shortcuts_and_neutral_media_default(self):
        response = self.client.get(reverse('unauthedhome'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Request Assistance", content)
        self.assertIn("Track a Request", content)
        self.assertIn("Organization Directory", content)
        self.assertNotIn("Tambalang Jonjon", content)
        self.assertNotIn("youtube.com/embed/T-msx__xlXY", content)


class ConfigurableSiteUITests(TestCase):
    def test_branding_colors_and_optional_media_are_admin_configurable(self):
        config = SiteConfiguration.objects.first()
        config.brand_name = "CivicLink"
        config.institution_name = "Sample Municipality"
        config.hero_heading = "Choose a public service"
        config.primary_color = "#234567"
        config.featured_media_url = "https://www.youtube.com/embed/example"
        config.featured_media_title = "Official municipal briefing"
        config.save()

        response = self.client.get(reverse("unauthedhome"))

        self.assertContains(response, "CivicLink")
        self.assertContains(response, "Sample Municipality")
        self.assertContains(response, "Choose a public service")
        self.assertContains(response, "--gov-primary: #234567")
        self.assertContains(response, "Official municipal briefing")

    def test_service_shortcut_controls_icon_copy_destination_and_order(self):
        shortcut = ServiceShortcut.objects.create(
            title="Book an Appointment",
            description="Choose an office and an available service schedule.",
            icon_class="fas fa-calendar-check",
            link_url="/appointments/",
            link_label="Choose a schedule",
            display_order=1,
        )

        response = self.client.get(reverse("unauthedhome"))

        self.assertContains(response, shortcut.title)
        self.assertContains(response, shortcut.icon_class)
        self.assertContains(response, shortcut.link_url)
        self.assertContains(response, shortcut.link_label)

    def test_shortcuts_reject_unsafe_or_malformed_configuration(self):
        unsafe = ServiceShortcut(
            title="Unsafe",
            description="Unsafe link",
            icon_class="javascript:alert(1)",
            link_url="javascript:alert(1)",
        )

        with self.assertRaises(ValidationError):
            unsafe.full_clean()

    def test_site_configuration_remains_single_record(self):
        existing = SiteConfiguration.objects.first()
        replacement = SiteConfiguration(brand_name="Updated GRAND")
        replacement.save()

        self.assertEqual(SiteConfiguration.objects.count(), 1)
        self.assertEqual(SiteConfiguration.objects.get().pk, existing.pk)
        self.assertEqual(SiteConfiguration.objects.get().brand_name, "Updated GRAND")


class PublicAnnouncementPrivacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(
            username="announcement-author",
            email="announcements@example.gov",
            password="test-password",
        )
        cls.public = Announcement.objects.create(
            user=cls.author,
            title="Public service advisory",
            slug="public-service-advisory",
            announcement_type=Announcement.PUBLIC,
            published=True,
            is_pinned=True,
            content="Public information.",
        )
        cls.internal = Announcement.objects.create(
            user=cls.author,
            title="Internal personnel memo",
            slug="internal-personnel-memo",
            announcement_type=Announcement.INTERNAL,
            published=True,
            is_pinned=True,
            content="Employees only.",
        )

    def test_public_home_never_shows_internal_pinned_announcement(self):
        response = self.client.get(reverse("unauthedhome"))

        self.assertContains(response, self.public.title)
        self.assertNotContains(response, self.internal.title)

    def test_public_announcement_list_hides_internal_items(self):
        response = self.client.get(reverse("announcements-list"))

        self.assertIn(self.public, response.context["announcements"])
        self.assertNotIn(self.internal, response.context["announcements"])

    def test_anonymous_user_cannot_open_internal_announcement_directly(self):
        response = self.client.get(
            reverse("announcement-detail", kwargs={"slug": self.internal.slug})
        )

        self.assertEqual(response.status_code, 404)

    def test_authenticated_employee_can_open_internal_announcement(self):
        self.client.force_login(self.author)

        response = self.client.get(
            reverse("announcement-detail", kwargs={"slug": self.internal.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["announcement"], self.internal)
