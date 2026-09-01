from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class HealthEndpointTests(SimpleTestCase):
    def test_health_endpoint_is_public_minimal_and_not_cached(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"service": "grand", "status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^healthz/$"],
    )
    def test_container_local_http_probe_is_not_redirected_to_missing_tls(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
