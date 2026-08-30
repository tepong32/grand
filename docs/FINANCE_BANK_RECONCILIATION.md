# Finance bank-statement intake and reconciliation

Status: **F8.2 implemented synthetic control; local BRS/template acceptance remains required**.

This slice provides a familiar monthly Accounting workflow for one bank account and fund at a time. It does not connect directly to a bank, replace authorized JEV preparation, or claim that GRAND's controlled CSV is the locally accepted official Bank Reconciliation Statement (BRS).

## Control basis

The public COA Government Accounting Manual Chapter 21 describes bank reconciliation as settlement of differences between the bank statement and the cash account, calls for a monthly BRS per bank account using the adjusted-balance method, and requires JEVs for reconciling items that need book adjustment. The DBM PFM Assessment Tool for LGUs also treats regular, timely bank reconciliation as an Accounting control. These are **official references**, but the LGU must still confirm their applicability, current local deadlines, account coverage, signatories, copies, attachments, and accepted BRS layout.

- COA GAM Chapter 21, scope and definitions: <https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/br1.1.htm>
- COA GAM Chapter 21, objectives/method/preparation/reporting: <https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/br1.2.htm>
- COA GAM Chapter 21, adjusted-balance procedure and JEV treatment: <https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/br1.4.htm>
- DBM PFM Assessment Tool for LGUs: <https://www.dbm.gov.ph/wp-content/uploads/DBM%20Publications/PFMAT%20Book.pdf>

## Guided workflow

1. An Accounting preparer creates one monthly batch using the active Finance Setup bank-account code, fund, bank/statement identity, safe masked account value, statement dates, receipt date, and independently checked control totals.
2. The preparer uploads the [human-editable starter CSV](finance-starters/BANK_STATEMENT_IMPORT.csv). GRAND records its SHA-256, keeps each source version, validates dates, one-sided amounts, row totals, optional running balances, and the opening-plus-deposits-less-withdrawals closing equation.
3. Unique exact matching requires the same date, reference, amount, and debit/credit direction. Ambiguous same-amount candidates remain visible for a human evidence-based choice.
4. A statement transaction without a posted matching book line cannot close. Bank charges, credit/debit memoranda, direct credits, or book errors must follow the authorized JEV/correction route, then be matched.
5. Posted ledger bank lines absent from the statement may be classified as deposits in transit or outstanding checks/withdrawals only with explanation, supporting reference, and expected clearance date.
6. GRAND computes `statement closing + deposits in transit - outstanding checks = adjusted bank balance` and compares that to the posted GL cash balance through the statement end.
7. Submission requires every statement row matched, every ledger-only line classified, valid statement controls, and exactly zero unexplained difference.
8. A different Accounting reviewer approves with the reviewed BRS/evidence reference or returns a specific correction instruction.

## Modification allowance and history

Until submission, and again after a return, the preparer may correct declared controls, replace the staged CSV, change a match, or replace timing-item evidence. Every replacement requires a reason where applicable; source versions, prior matches/classifications, checksums, actors, and events remain retained. Under review and after reconciliation, controls are read-only. A later discovered book error uses an adjusting/reversing JEV and, where required, a successor BRS rather than rewriting the closed record.

## Starter CSV

The CSV is deliberately plain and macro-free:

```text
transaction_date,bank_reference,description,withdrawal,deposit,running_balance
```

- Dates use `YYYY-MM-DD`.
- Use either withdrawal or deposit on each row, never both.
- `running_balance` may be blank when the bank does not provide it.
- Replace/remove the two example rows before use.
- The batch screen carries the bank/fund/month and independent totals, so users do not repeat those values on every row.

## Export and safekeeping

The controlled evidence export contains current statement rows, matches, outstanding items, adjusted-balance controls, source/version checksums, and reconciliation checksum. The same bytes are archived atomically below `department/user/finance-bank-reconciliation/year/month` inside `GRAND_EXPORT_ROOT`, beside a manifest suitable for whole-folder TraceSync copying.

The export is controlled working/evidence data, not automatically an official BRS. Keep the approved signed BRS and attachments under the locally accepted records procedure.

## Acceptance still required

Before official use, named Accounting, Treasury, management, and audit-coordination owners must confirm the actual bank statement formats, bank-account/fund scope, prior-month outstanding-item carry-forward and ageing, bank debit/credit memo route, book-adjustment route, local review/signature matrix, deadlines/copies/recipients, official BRS layout, and at least one redacted month replayed to zero.
