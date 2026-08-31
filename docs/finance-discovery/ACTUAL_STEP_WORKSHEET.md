# Actual-step and GRAND replay worksheet

Create a row for every authority decision, balance movement, calculation, system action, print, wet signature, physical handoff, exception, reconciliation, and period-end proof. Returns and repeated visits receive new sequence rows; do not overwrite the original path.

## Case header

| Field | Record |
|---|---|
| Worksheet/replay ID | `REPLAY-___` |
| Transaction ID | `TX-___` |
| Fiscal year/fund/office scope |  |
| Redacted packet evidence IDs |  |
| Opening control totals | Appropriation / allotment / obligation / payable / ledger / cash |
| Actual-route acceptance | Office/role, result, date, evidence ID |
| GRAND replay build/commit |  |

## Actual route

| Step ID | Seq. | Evidence label | Actor/office | Authority/input | Verification and action | Balance effect | System | Output/number/version | Custody before/after | Next gate | Exception/correction | Evidence IDs |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|
| STEP-TX___-001 | 1 | Unresolved |  |  |  |  |  |  |  |  |  |  |

## GRAND replay comparison

| Step ID | GRAND screen/service | Synthetic role and permission | State/event/version | Balance movement | Output/custody evidence | Result | Severity | Gap/decision ID | Expected correction | Test/UAT evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| STEP-TX___-001 |  |  |  |  |  | Unknown |  | DEC-___ |  |  |

Allowed results are `Exact`, `Equivalent improvement`, `Partial`, `Missing`, `Extra`, and `Unknown`. Assign severity independently as `Critical`, `High`, `Medium`, or `Low`; an attractive interface does not reduce a control gap's severity.

## Control-total reconciliation

| Control | Opening | Authorized increase | Authorized decrease | Expected closing | Actual closing | Difference | Evidence/decision |
|---|---:|---:|---:|---:|---:|---:|---|
| Appropriation |  |  |  |  |  |  |  |
| Released allotment |  |  |  |  |  |  |  |
| Obligation |  |  |  |  |  |  |  |
| Payable |  |  |  |  |  |  |  |
| Ledger/control account |  |  |  |  |  |  |  |
| Cash/payment register |  |  |  |  |  |  |  |

The replay cannot be accepted with an unexplained non-zero difference.
