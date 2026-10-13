from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from users.auth_throttle import consume_attempt
from users.models import AuthAttemptBucket


@skipUnless(connection.vendor == "mysql", "Authentication aliases require native MySQL collation")
class AuthThrottleCollationTests(TestCase):
    def test_collation_aliases_resolve_to_same_account(self):
        from django.contrib.auth import get_user_model
        from users.auth_throttle import attempt_identities

        user = get_user_model().objects.create_user(username="collation-employee", email="collation@example.com")
        # The native fixture uses an accent-insensitive collation, as ordinary
        # MySQL deployments do. Match the database's actual authentication key.
        self.assertTrue(get_user_model().objects.filter(username__iexact="collation-émployee").exists())
        for value in (user.username, "collation-émployee", "COLLATION-EMPLOYEE"):
            self.assertEqual(attempt_identities("login", {"username": value}, {}), [f"account:{user.pk}"])


@skipUnless(connection.vendor == "mysql", "Concurrent row updates require native MySQL")
class AuthThrottleConcurrencyTests(TransactionTestCase):
    def test_first_concurrent_attempts_cannot_exceed_limit(self):
        barrier = Barrier(12)

        def attempt(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return consume_attempt("concurrent", "same-identity", limit=5)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(attempt, range(12)))
        self.assertEqual(sum(results), 5)
        self.assertEqual(AuthAttemptBucket.objects.get().attempts, 5)

    def test_expired_concurrent_counter_resets_once(self):
        from datetime import timedelta
        from django.utils import timezone

        consume_attempt("expired", "same-identity", limit=1)
        AuthAttemptBucket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        barrier = Barrier(8)

        def attempt(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return consume_attempt("expired", "same-identity", limit=3)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(AuthAttemptBucket.objects.get().attempts, 3)
