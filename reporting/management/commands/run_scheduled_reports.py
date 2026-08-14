from django.core.management.base import BaseCommand
from django.utils import timezone

from reporting.models import ReportSchedule
from reporting.services import execute_schedule


class Command(BaseCommand):
    help = "Generate due reports with an idempotent run ledger; safe to invoke repeatedly."

    def handle(self, *args, **options):
        now = timezone.now()
        schedules = ReportSchedule.objects.filter(is_active=True, next_run_at__lte=now).select_related("definition", "template_version", "created_by")
        generated = failures = 0
        for schedule in schedules:
            try:
                execute_schedule(schedule, schedule.next_run_at)
            except Exception as exc:
                failures += 1
                self.stderr.write(f"{schedule.name}: {exc}")
            else:
                generated += 1
        self.stdout.write(f"Processed {generated} due schedule(s); {failures} failure(s) recorded.")
