"""Cash-flow purposes retained on cash journal lines and reviewed posting rules.

The direction is the statement row's normal direction, not a constraint on a
journal debit/credit: a reversal must reduce its original receipt/payment row.
"""

# code, statement activity, normal cash direction, operator-facing description
CASH_FLOW_ROWS = (
    ("op_taxes", "operating", "in", "Collections from taxpayers"),
    ("op_transfers", "operating", "in", "National tax allotment / operating transfers received"),
    ("op_services", "operating", "in", "Business and service receipts"),
    ("op_interest_in", "operating", "in", "Interest received - operating"),
    ("op_dividends", "operating", "in", "Dividends received - operating"),
    ("op_other_in", "operating", "in", "Other operating receipts"),
    ("op_expenses", "operating", "out", "Operating expenses paid"),
    ("op_suppliers", "operating", "out", "Operating suppliers and creditors paid"),
    ("op_employees", "operating", "out", "Employees paid"),
    ("op_interest_out", "operating", "out", "Interest paid - operating"),
    ("op_other_out", "operating", "out", "Other operating payments"),
    ("inv_asset_sales", "investing", "in", "Proceeds from sale of long-term assets"),
    ("inv_investments_in", "investing", "in", "Investment disposals / maturities"),
    ("inv_loans_in", "investing", "in", "Collections of loans made"),
    ("inv_other_in", "investing", "in", "Other investing receipts"),
    ("inv_assets", "investing", "out", "Acquisition of long-term assets"),
    ("inv_investments_out", "investing", "out", "Investments purchased"),
    ("inv_loans_out", "investing", "out", "Loans made"),
    ("inv_other_out", "investing", "out", "Other investing payments"),
    ("fin_borrowings", "financing", "in", "Borrowing proceeds"),
    ("fin_other_in", "financing", "in", "Other financing receipts"),
    ("fin_principal", "financing", "out", "Loan principal repayments"),
    ("fin_other_out", "financing", "out", "Other financing payments"),
    ("exchange", "exchange", "in", "Exchange-rate effect on cash / cash equivalents"),
    ("internal", "internal", "in", "Transfer within cash / cash equivalents"),
)
CASH_FLOW_CHOICES = (("", "Not classified / not a cash line"),) + tuple(
    (code, title) for code, _activity, _direction, title in CASH_FLOW_ROWS
)
CASH_FLOW_BY_CODE = {code: (activity, direction, title)
    for code, activity, direction, title in CASH_FLOW_ROWS}
