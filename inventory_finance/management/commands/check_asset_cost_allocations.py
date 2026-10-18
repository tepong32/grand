from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from inventory.management.commands.check_receiving_evidence import Command as EvidenceCommand
from inventory_finance import asset_cost_allocations as service
from inventory_finance.models import AssetCostAllocation


class Command(EvidenceCommand):
    help = 'Read-only documentary allocation history/source/file/orphan check. Never repairs or revalues.'
    evidence_model = AssetCostAllocation
    namespace_name = 'asset-cost-allocations'

    def handle(self, *args, **options):
        checked = set()
        for row in self.evidence_model.objects.select_related('line__receipt', 'line__registered_asset').prefetch_related('events'):
            try:
                service.verify(row)
                if row.line_id not in checked:
                    snapshot, head = service.basis(row.line)
                    if head and head.source_snapshot['source'] != snapshot['source']:
                        raise ValidationError('Current documentary worksheet has stale sources.')
                    checked.add(row.line_id)
            except (OSError, ValueError, ValidationError) as error:
                raise CommandError(f'Allocation {row.public_id} requires investigation. No records or files changed.') from error
        return super().handle(*args, **options)
