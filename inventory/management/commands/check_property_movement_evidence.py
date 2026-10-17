from inventory.models import PropertyMovementRecord
from .check_receiving_evidence import Command as ReceivingEvidenceCommand


class Command(ReceivingEvidenceCommand):
    help = "Check property movement evidence and unreferenced files without modifying data or files."
    evidence_model = PropertyMovementRecord
    namespace_name = "property-movements"
