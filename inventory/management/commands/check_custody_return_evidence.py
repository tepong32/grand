from inventory.models import AssetReturnEvidence
from .check_receiving_evidence import Command as ReceivingEvidenceCommand


class Command(ReceivingEvidenceCommand):
    help = "Check custody-return evidence hashes and report unreferenced files. Never changes data or files."
    evidence_model = AssetReturnEvidence
    namespace_name = "custody_returns"
