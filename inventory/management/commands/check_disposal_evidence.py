from inventory.models import AssetDisposalAttachment
from .check_receiving_evidence import Command as ReceivingEvidenceCommand


class Command(ReceivingEvidenceCommand):
    help = "Check disposal evidence; report legacy unknowns, missing, changed and unreferenced files without modifying them."
    evidence_model = AssetDisposalAttachment
    namespace_name = "disposal"
    report_unknown_hashes = True
