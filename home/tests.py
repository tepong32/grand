from django.test import TestCase
from django.urls import reverse


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
