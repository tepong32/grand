from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

from inventory.maintenance_notices import case_basis, verify_notice
from inventory.models import MaintenanceCorrectionNotice
from .check_receiving_evidence import Command as EvidenceCommand


class Command(EvidenceCommand):
    help = 'Check correction-notice records, retained files and unreferenced files. Never changes data or files.'
    evidence_model = MaintenanceCorrectionNotice
    namespace_name = 'maintenance_notices'

    def evidence_records(self):
        return self.evidence_model.objects.exclude(file='', sha256='', size=0, original_filename='').order_by('pk').iterator()

    def handle(self, *args, **options):
        bases = {}
        for row in self.evidence_model.objects.select_related('case__asset').order_by('pk').iterator():
            try:
                verify_notice(row)
                if row.case_id not in bases:
                    bases[row.case_id] = case_basis(row.case)
                if row.source_snapshot != bases[row.case_id]:
                    raise ValidationError('The observed original work record changed.')
            except ValidationError as error:
                raise CommandError(f'Notice {row.public_id} requires investigation: {" ".join(error.messages)}') from error
        return super().handle(*args, **options)
