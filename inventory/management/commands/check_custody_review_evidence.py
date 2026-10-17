from .check_receiving_evidence import Command as ReceivingCommand
from inventory.models import EmployeeCustodyReview


class Command(ReceivingCommand):
    help = "Check private HR-reference custody review evidence without changing records or files."
    evidence_model = EmployeeCustodyReview
    namespace_name = "custody-reviews"
