from .check_receiving_evidence import Command as ReceivingCommand
from inventory.models import ReceiptQuantityCorrection


class Command(ReceivingCommand):
    help = "Check retained receipt quantity-correction files without changing data or files."
    evidence_model = ReceiptQuantityCorrection
    namespace_name = "receipt-quantity-corrections"
