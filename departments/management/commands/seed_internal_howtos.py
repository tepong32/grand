from django.core.management.base import BaseCommand

from departments.services.internal_howto_seed import seed_finance_internal_howtos


class Command(BaseCommand):
    help = "Create or preserve department- and permission-scoped Finance internal how-to guides."

    def handle(self, *args, **options):
        counts = seed_finance_internal_howtos()
        self.stdout.write(self.style.SUCCESS(
            "Internal How-Tos: "
            f"{counts['departments']} department(s), "
            f"{counts['guides_created']} created, "
            f"{counts['guides_preserved']} published guide(s) preserved."
        ))
