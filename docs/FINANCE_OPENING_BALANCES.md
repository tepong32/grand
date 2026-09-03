# Finance opening balances and control-total intake

Status: GRAND-implemented F2.2 control foundation. This workflow is ready for synthetic acceptance; it is not authority to import production balances or replace the LGU's accepted opening schedules.

## Purpose and evidence boundary

Opening balances are brought into the isolated Finance store through a controlled staging, approval, posting, and reconciliation route. GRAND retains the source filename and SHA-256 checksum, declared controls, normalized rows, validation results, decisions, generated JEV lineage, and append-only events.

The intake is deliberately generic. It does not claim that its CSV is a prescribed COA schedule. Before production use, Accounting and the assigned COA auditor must confirm the controlling chart, subsidiary detail, fund treatment, opening/conversion schedules, fiscal cutover date, and accepted signed evidence. Any official or locally approved layout must be versioned and mapped separately.

## Roles

- `prepare_opening_balances` creates a batch, stages or corrects its rows and declared controls, validates it, and submits it.
- `approve_opening_balances` independently approves or returns the batch. The approver cannot be its preparer or submitter.
- `post_opening_balances` creates and posts the opening JEVs, then runs the separate reconciliation gate. The preparer cannot post the same batch.
- `view_accounting_workspace` can inspect and export opening evidence for the user's currently assigned department.

Permissions never cross the current department boundary.

## Guided action queue and oversight register

The Opening balances workspace remains the single operating register. Fiscal-year, workflow-status, and plain-language next-action filters divide the same governed records into needs staging/correction, ready for submission, awaiting independent review, awaiting posting, awaiting reconciliation, and reconciled/complete work. The four summary cards remain explicitly department-wide while the table and its visible count follow the selected filters.

`Export visible register` uses the exact same filters. Its spreadsheet-safe CSV contains one control row per visible batch: declared and staged totals, validation exceptions, source checksum, maker/reviewer/poster/reconciler lineage, state version, and the next action. It intentionally does not repeat normalized source rows; those remain available in the controlled per-batch export. The exact register bytes and manifest are retained in the TraceSync-ready `department/user/finance-opening-register/year/month` tree and an append-only Accounting audit event retains their SHA-256 and filter scope.

All users with Accounting workspace access may inspect and export the department-bounded register, matching the existing opening-evidence access rule. Exporting is a read-only evidence action: it does not approve, post, reconcile, or establish official-form status.

## Controlled CSV

The UTF-8 source is limited to 5 MB and uses these columns:

```text
fund_code,account_code,responsibility_center_code,debit,credit,subsidiary_reference,memo
```

`fund_code`, `account_code`, `debit`, and `credit` are required columns. Every populated row must resolve to active governed codes, contain a positive debit or credit but not both, and use a non-negative amount with no more than two decimal places. GRAND checks row count, declared debit and credit, batch balance, and balance within each fund. A genuinely new year with no brought-forward balances uses an explicit zero-balance declaration rather than invented rows.

## Starter CSV

To make onboarding easier for clerks and new processors, GRAND provides a plain starter template at

```text
docs/finance-starters/OPENING_BALANCE_IMPORT.csv
```

and an in-app download:

* `/accounting/opening/starter.csv`

The CSV is deliberately familiar and editable:

```text
fund_code,account_code,responsibility_center_code,debit,credit,subsidiary_reference,memo
```

- Opening rows do not carry a transaction-date column; controls are enforced per declared period and header.
- Keep one positive debit or one positive credit per row; do not mix both.
- Replace or remove the sample rows before uploading.
- Keep codes in your local COA/ledger format so GRAND can map governed master data.

## Operator sequence

1. Create the batch for one typed fiscal year and its opening period. Record the reviewed source reference and independent row/debit/credit controls.
2. Stage the CSV. GRAND replaces only the pre-approval staging rows, records the checksum, maps controlled codes, and immediately validates.
3. Correct a flagged row or declared control with a mandatory reason. The prior and corrected values remain in append-only evidence. Revalidate until every difference is zero.
4. Submit the validated batch for independent review.
5. The approver records the schedule/control evidence and approves, or returns it for correction. An approved but unposted batch may still be returned.
6. A separate poster posts one immutable opening JEV per fund. The typed year must be approved or active and its selected period must be open.
7. Run reconciliation. GRAND compares staged controls with the generated posted JEV lineage. Only zero row, debit, and credit differences move the batch to `Reconciled` and satisfy the Accounting structural-readiness check.
8. Use the workspace filters to isolate the next authorized action. Export the visible register when a supervisor or reviewer needs one retained oversight list.
9. Export an individual batch's controlled CSV when row-level operational review needs it. The export carries the department, fiscal year, period, source reference/status/checksum, declared controls, normalized rows, validation state, and stable codes. Both exports are downloaded and retained in the [portable GRAND export archive](EXPORT_ARCHIVE.md), but remain evidence/data interchange rather than automatically official forms.

## Modification allowance

Draft and returned staging may be corrected with a stated reason, before/after evidence, revalidation, and another approval cycle. An approved batch can be returned only before posting. Once opening JEVs are posted, neither the source rows nor the generated entries are silently rewritten; a governed adjusting/reversing route in the applicable open period must carry the original lineage and new approval evidence.

This is stricter than the broader voucher/check issuance boundary because ledger posting is itself an authoritative accounting event. Later Finance phases must coordinate any opening adjustment with period close, subsidiary reconciliation, statements, and downstream reports.

## Synthetic acceptance

Acceptance requires tests showing department isolation, permission gates, rejected unknown codes, reasoned correction, exact row and control totals, per-fund balance, independent approval, immutable posted JEVs, explicit zero declaration, reconciliation to zero difference, synchronized action filtering, and scoped control/row exports. Production migration, historical conversion, and official-form fidelity remain outside this slice.
