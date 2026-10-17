from .check_receiving_evidence import Command as ReceivingCommand
from inventory.models import PropertyDetermination


class Command(ReceivingCommand):
    help = "Check private property determination evidence without changing records or files."
    evidence_model = PropertyDetermination
    namespace_name = "property-determinations"
