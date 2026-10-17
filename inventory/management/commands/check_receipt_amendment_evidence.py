from .check_receiving_evidence import Command as ReceivingCommand
from inventory.models import ReceiptCostAmendment


class Command(ReceivingCommand):
    help = "Check private receipt cost-amendment evidence without changing records or files."
    evidence_model = ReceiptCostAmendment
    namespace_name = "receipt-amendments"
