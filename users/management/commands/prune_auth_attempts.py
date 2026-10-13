from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import AuthAttemptBucket


class Command(BaseCommand):
    help = "Remove expired authentication attempt counters older than one day."

    def handle(self, *args, **options):
        count, _ = AuthAttemptBucket.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
        self.stdout.write(f"Removed {count} expired counters.")
