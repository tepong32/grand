import json

from django.core.management.base import BaseCommand, CommandError

from src.database_backups import BackupError, verify_backup_set


class Command(BaseCommand):
    help = (
        "Read and verify a copied GRAND database backup set, including manifest "
        "identity, both gzip streams, byte lengths, and SHA-256 values."
    )

    def add_arguments(self, parser):
        parser.add_argument("backup_set", help="Path to the dated directory containing manifest.json.")
        parser.add_argument(
            "--allow-partial",
            action="store_true",
            help="Allow an explicitly partial diagnostic set instead of requiring both stores.",
        )
        parser.add_argument(
            "--expect-manifest-sha256",
            help="Compare the manifest with a SHA-256 retained separately from the copied set.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Print a machine-readable verification receipt.",
        )

    def handle(self, *args, **options):
        try:
            result = verify_backup_set(
                options["backup_set"],
                allow_partial=options["allow_partial"],
                expected_manifest_sha256=options["expect_manifest_sha256"],
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        if options["as_json"]:
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Verified {result['scope']} GRAND backup set {result['backup_id']} "
                f"with {len(result['artifacts'])} artifact(s)."
            )
        )
        self.stdout.write(f"Manifest SHA-256: {result['manifest_sha256']}")
        if not result["authenticity_verified"]:
            self.stdout.write(
                self.style.WARNING(
                    "Integrity passed, but manifest authenticity was not compared with a separately retained hash."
                )
            )
        self.stdout.write(
            "Restore status: not tested by this command; retain separate witnessed rehearsal evidence."
        )
