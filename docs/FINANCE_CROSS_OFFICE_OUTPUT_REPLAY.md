# Ordinary cross-office source-to-output replay

Development checkpoint, 2026-09-21. Extends the existing authoritative Budget to
Treasury replay in `vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay`.
This is synthetic engineering evidence, not witnessed LGU practice or accepted
official form reproduction.

## One transaction, distinct office meanings

The replay uses actual source services: approved appropriation, posted ARO,
certified OBR, source-linked payable with invoice evidence, independent intake
review, DV preparation/signature custody, independent recognition posting,
Treasury instrument issue/advice/acknowledged release, independent payment posting
and bank-statement reconciliation. All physical/authority evidence is explicitly
synthetic. The existing replay retains its role and next-action checks.

| Output/control | Expected result from the same source chain |
| --- | --- |
| Budget accountability | Appropriation 1,000; allotment 1,000; obligation 1,000; unobligated allotment 0 |
| Budget cut-off before OBR date | Obligation 0; later certification does not enter the earlier output |
| Budget versus posted actual | Expense 1,000, mapped exactly; no duplicate expense from payment |
| Payable before payment | 900 outstanding, retained original report bytes/checksum |
| Payable after payment | 0 outstanding, while the earlier report remains 900 |
| Withholding liability | 100 outstanding; payment does not silently remit it |
| Treasury register | 900 issued/released, same case/check and receipt reference |
| Trial balance and general ledger | Three posted sources: opening, recognition and payment; 3,900 debit and credit movement totals |
| Bank position/reconciliation | 2,000 opening less 900 payment = 1,100; trial-balance bank balance agrees with reconciled bank evidence |

The gross claim reconciles as 1,000 expense = 900 released + 100 withholding.
Budget obligation, Accounting expense and Treasury release remain distinct values.
Budget retains the exact OBR identity/date; actual expense retains the recognition
JEV identity/date; ledger reports retain the payment source and date.

Eight workbooks are downloaded through the real permission-checked HTTP route.
Checks compare downloaded bytes with the retained artifact, open each workbook,
and total its visible financial data cells against the declared scenario amounts.
A Budget actor cannot download the Accounting trial balance. All generated
outputs remain working candidates rather than accepted official outputs.

## Scope and remaining proof

No production behavior, models, permissions or posting rules changed in this
checkpoint. Assertions extend one existing end-to-end test rather than creating
another source route or mocking ledger/report amounts.

SQLite source/control replay passed (28.123s); the expanded workbook-cell replay
passed on SQLite (10.268s). The corrected final native MySQL replay passed (14.408s),
including all eight workbook downloads/totals. An initial native failure was caused
by redundant test-response cleanup; the correction removed that extra close and
changed no production logic. Exact commands and scope are in CONTINUE.md. Both SQLite and fresh native
MySQL are used because this evidence crosses the two stores and date-filtered
Treasury reporting, although the checkpoint itself changes no persistence code.

FG-06/FG-07 remain partial. This does not prove every correction, consolidated
claim, tax filing, statutory layout, printer result, realistic-volume performance,
full browser workflow, actual deployment or named-office acceptance. Continue
ordinary screen-level handoffs and the [required-output map](FINANCE_REQUIRED_OUTPUT_MAP.md)
without inferring missing local earmark semantics or expanding the candidate catalog.
