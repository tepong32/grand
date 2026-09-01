import json

from django.core.management.base import BaseCommand, CommandError

from src.production_preflight import evaluate_production_preflight


class Command(BaseCommand):
    help = (
        "Evaluate GRAND's production configuration and, by default, live two-store, "
        "migration, and runtime-storage readiness without claiming restore or cutover approval."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--configuration-only",
            action="store_true",
            help="Check static configuration only; do not connect to databases or probe storage.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Print a machine-readable, non-secret preflight receipt.",
        )

    def handle(self, *args, **options):
        result = evaluate_production_preflight(
            configuration_only=options["configuration_only"],
        )
        if options["as_json"]:
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        else:
            for item in result["checks"]:
                marker = {
                    "passed": "PASS",
                    "failed": "FAIL",
                    "not_run": "NOT RUN",
                }[item["status"]]
                self.stdout.write(f"[{marker}] {item['code']}: {item['message']}")
            if options["configuration_only"] and result["selected_scope_passed"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Configuration preflight passed. Live database, migration, and storage checks were not run."
                    )
                )
            elif result["deployment_preflight_passed"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Live environment preflight passed. This is not a restore rehearsal or cutover authorization."
                    )
                )
        if not result["selected_scope_passed"]:
            raise CommandError(
                "GRAND production preflight failed; correct every failed/not-run check before proceeding."
            )
