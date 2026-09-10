"""Financial consistency between retained members of one statement package."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation


def package_financial_errors(note_set):
    if not note_set.is_complete_statement_package:
        return []
    runs = dict(note_set.statement_runs)
    errors = []
    journals = {}
    for field, run in runs.items():
        if field in {"position_run", "performance_run"}:
            expected = {line.get("line_code") for line in run.parameters.get("_statement_mapping_snapshot", {}).get("lines", [])}
            expected.discard(None)
            expected.add("unclosed-operating-result" if field == "position_run" else "operating-result")
            rows = run.dataset_snapshot.get("rows", [])
            actual = [row.get("line_code") for row in rows]
            if not expected.issubset(set(actual)) or len(actual) != len(set(actual)) or any("amount" not in row for row in rows):
                errors.append(f"{field}: keep every mapped financial row and the operating-result row in the issued statement.")
        records = {}
        for source in run.source_records.filter(source_model="JournalEntry"):
            snapshot = deepcopy(source.snapshot)
            snapshot.pop("cash_classification", None)
            for line in snapshot.get("lines", []):
                line.pop("cash_flow_allocations", None)
                line.pop("cash_classification_public_id", None)
            records[source.source_public_id] = (source.source_date, snapshot)
        journals[field] = records
    base = journals["position_run"]
    for field in ("net_assets_run", "cash_flow_run"):
        if journals[field] != base:
            errors.append(f"{field}: the retained posted journals differ from Position. Generate matching reports before packaging.")
    current = {key: value for key, value in base.items()
        if note_set.period_start <= value[0] <= note_set.period_end}
    if journals["performance_run"] != current:
        errors.append("Performance does not retain the same period's journals as the other statements.")
    position = runs["position_run"].control_totals
    performance = runs["performance_run"].control_totals
    equity = runs["net_assets_run"].control_totals
    cash = runs["cash_flow_run"].control_totals
    try:
        if Decimal(position["assets"]) - Decimal(position["liabilities"]) != Decimal(equity["closing"]):
            errors.append("Position assets less liabilities do not equal closing Net Assets.")
        if Decimal(performance["operating_result"]) != Decimal(equity["operating_result"]):
            errors.append("Performance surplus does not equal the Net Assets operating movement.")
        if not cash.get("funds") or set(cash["funds"]) != set(equity.get("funds", {})):
            errors.append("Cash Flow and Net Assets must cover the same non-empty fund inventory.")
        codes = set(cash.get("cash_account_codes", []))
        if not codes:
            errors.append("The Cash Flow member lacks its retained cash-account scope.")
        balances = {code: Decimal("0.00") for code in cash.get("funds", {})}
        for _when, snapshot in base.values():
            fund = snapshot["fund"]
            for line in snapshot["lines"]:
                if line["account"] in codes:
                    balances[fund] = balances.get(fund, Decimal("0.00")) + Decimal(line["debit"]) - Decimal(line["credit"])
        for fund, controls in cash.get("funds", {}).items():
            if balances[fund] != Decimal(controls["current"]["closing_cash"]):
                errors.append(f"{fund}: Cash Flow closing cash differs from the retained Position cash ledger.")
    except (KeyError, TypeError, ValueError, InvalidOperation):
        errors.append("The statement members lack valid retained financial controls for package reconciliation.")
    return errors
