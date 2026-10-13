from django.core.management.base import BaseCommand

from users.models import User


class Command(BaseCommand):
    help = "Read-only identity review: report account IDs with conflicting public/employee profiles or missing assignment."

    def handle(self, *args, **options):
        conflicts = User.objects.filter(employeeprofile__isnull=False, citizenprofile__isnull=False).values_list("pk", flat=True)
        unassigned = User.objects.filter(employeeprofile__isnull=False, employeeprofile__assigned_department__isnull=True).values_list("pk", flat=True)
        self.stdout.write(f"Conflicting profile account IDs (quarantined): {list(conflicts)}")
        self.stdout.write(f"Unassigned employee account IDs: {list(unassigned)}")
        self.stdout.write("Review actual HR authority before any correction. No account or profile was changed.")
