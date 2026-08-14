from django.core.management.base import BaseCommand

from reporting.presets import seed_mswd_presets


class Command(BaseCommand):
    help = "Create or preserve the approved MSWD reporting pilot presets."

    def handle(self, *args, **options):
        results = seed_mswd_presets()
        if not results:
            self.stdout.write(self.style.WARNING("No MSWD department and accountable approver were available; no presets were changed."))
            return
        created = sum(1 for _, changed in results if changed)
        self.stdout.write(self.style.SUCCESS(f"MSWD reporting presets ready: {len(results)} total, {created} newly configured."))

