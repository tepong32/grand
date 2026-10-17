from .check_receiving_evidence import Command as ReceivingCommand
from inventory.models import SupplyRequisition


class Command(ReceivingCommand):
    help = "Check private supplied requisition evidence without changing records or files."
    evidence_model = SupplyRequisition
    namespace_name = "requisitions"
