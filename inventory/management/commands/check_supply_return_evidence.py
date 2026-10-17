from .check_receiving_evidence import Command as ReceivingCommand
from inventory.models import SupplyReturn


class Command(ReceivingCommand):
    help = "Check private supply return evidence without changing records or files."
    evidence_model = SupplyReturn
    namespace_name = "supply-returns"
