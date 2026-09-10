from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from .cash_flow_calculation import cash_flow_period


class CashFlowGrossPresentationTests(SimpleTestCase):
    def source(self, reference, lines, *, opening=False):
        return {"source_model": "JournalEntry", "source_public_id": reference,
            "source_reference": reference, "source_date": date(2027, 1, 1) if opening else date(2027, 2, 1),
            "snapshot": {"statement_source_type": "opening" if opening else "manual",
                "statement_origin_public_id": reference,
                "lines": [{"account": account, "debit": str(debit), "credit": str(credit),
                    "cash_flow_category": purpose} for account, debit, credit, purpose in lines]}}

    def test_a_combined_jev_preserves_gross_receipts_and_payments(self):
        sources = [self.source("OPEN", [("cash", 100, 0, ""), ("equity", 0, 100, "")], opening=True),
            self.source("DAYBOOK", [("cash", 1000, 0, "op_services"), ("revenue", 0, 1000, ""),
                ("expense", 300, 0, ""), ("cash", 0, 300, "op_expenses")])]
        values, controls = cash_flow_period(sources, {"cash"}, date(2027, 1, 1), date(2027, 3, 31))
        self.assertEqual((values["operating_in"], values["operating_out"], values["closing"]),
            (Decimal("1000"), Decimal("300"), Decimal("800")))
        self.assertEqual(controls["reconciliation_difference"], 0)

    def test_unrelated_unclassified_cash_entries_do_not_clear_each_other(self):
        sources = [self.source("RECEIPT", [("cash", 50, 0, ""), ("revenue", 0, 50, "")]),
            self.source("PAYMENT", [("cash", 0, 50, ""), ("expense", 50, 0, "")])]
        _values, controls = cash_flow_period(sources, {"cash"}, date(2027, 1, 1), date(2027, 3, 31))
        self.assertEqual(controls["reconciliation_difference"], 0)
        self.assertEqual(controls["unclassified_entries"], ["PAYMENT", "RECEIPT"])
