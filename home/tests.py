from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Announcement


class UnauthenticatedHomeTests(TestCase):
    def test_office_portals_dropdown_present(self):
        response = self.client.get(reverse('unauthedhome'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Office Portals", content)
        self.assertIn("Office of the Mayor", content)
        self.assertIn("Treasury", content)
        self.assertIn("Acctg", content)
        self.assertIn("Budget", content)
        self.assertIn("MENRO", content)
        self.assertIn("GSO", content)

    def test_unauthed_home_shows_office_quick_links(self):
        response = self.client.get(reverse('unauthedhome'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Office Portals", content)
        self.assertIn("Explore Services", content)


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
