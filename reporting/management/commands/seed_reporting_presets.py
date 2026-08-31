from django.core.management.base import BaseCommand

from reporting.presets import seed_reporting_presets


class Command(BaseCommand):
    help = "Create or preserve the MSWD and controlled Finance reporting starter presets."

    def handle(self, *args, **options):
        groups = seed_reporting_presets()
        results = groups["mswd"] + groups["finance"]
        if not results:
            self.stdout.write(self.style.WARNING("No matching department and accountable approver were available; no presets were changed."))
            return
        created = sum(1 for _, changed in results if changed)
        self.stdout.write(self.style.SUCCESS(
            f"Reporting starters ready: {len(groups['mswd'])} MSWD and {len(groups['finance'])} Finance; "
            f"{created} newly configured."
        ))
