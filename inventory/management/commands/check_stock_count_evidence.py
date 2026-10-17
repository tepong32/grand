from inventory.models import StockCountEvidence
from .check_receiving_evidence import Command as ReceivingEvidenceCommand


class Command(ReceivingEvidenceCommand):
    help = "Check stock-count evidence hashes and report unreferenced files. Never changes data or files."
    evidence_model = StockCountEvidence
    namespace_name = "stock_counts"
