from django.core.management.base import BaseCommand, CommandError

from src.database_backups import BackupError, create_backup_set


class Command(BaseCommand):
    help = (
        "Create and verify a native logical backup of GRAND's main and Finance "
        "MySQL databases, then atomically publish one portable backup set."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            action="append",
            choices=("default", "finance"),
            dest="databases",
            help="Back up one named store. Omit to back up both stores as a complete set.",
        )
        parser.add_argument(
            "--output-root",
            help="Override GRAND_BACKUP_ROOT for this invocation.",
        )
        parser.add_argument(
            "--retain",
            type=int,
            help="Keep only this many newest completed sets; zero disables deletion.",
        )

    def handle(self, *args, **options):
        retain = options["retain"]
        if retain is not None and retain < 0:
            raise CommandError("--retain must be zero or a positive integer.")
        try:
            result = create_backup_set(
                database_aliases=tuple(options["databases"] or ("default", "finance")),
                backup_root=options["output_root"],
                retention_count=retain,
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        manifest = result["manifest"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Published {manifest['scope']} GRAND backup set {result['backup_id']} "
                f"with {len(manifest['databases'])} database artifact(s): {result['path']}"
            )
        )
        self.stdout.write(f"Manifest SHA-256: {result['manifest_sha256']}")
        if result["removed_by_retention"]:
            self.stdout.write(
                f"Retention removed {len(result['removed_by_retention'])} older completed set(s)."
            )
        if result["retention_warning"]:
            self.stderr.write(self.style.WARNING(result["retention_warning"]))
