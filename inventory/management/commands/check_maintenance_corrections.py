from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

from inventory import maintenance_corrections as service
from inventory.models import MaintenanceCorrection
from .check_receiving_evidence import Command as EvidenceCommand


class Command(EvidenceCommand):
    help = 'Check retained maintenance correction content/history, approved sources, evidence and orphans. Never repairs data.'
    evidence_model = MaintenanceCorrection
    namespace_name = 'maintenance_corrections'

    def handle(self, *args, **options):
        checked_cases = set()
        for row in self.evidence_model.objects.select_related('case__asset').prefetch_related('events'):
            try:
                service.verify(row)
                if row.case_id not in checked_cases:
                    service.basis(row.case)
                    checked_cases.add(row.case_id)
            except (OSError, ValueError, ValidationError) as error:
                raise CommandError(f'Correction {row.public_id} requires investigation; no records or files were changed.') from error
        return super().handle(*args, **options)
