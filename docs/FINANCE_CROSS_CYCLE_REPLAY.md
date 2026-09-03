# Finance cross-cycle synthetic replay

## Purpose

GRAND now keeps one automated synthetic replay across the implemented fiscal-foundation, opening-balance, Budget, Accounting, Treasury, vouchering, bank-reconciliation, and reporting boundaries. The replay closes an assurance gap that module-level tests could not close on their own: it proves that one governed fiscal foundation and authoritative obligation can remain connected through final payment reporting.

This is an integration checkpoint, not evidence that an LGU has accepted GRAND for official use.

## Replayed control path

The replay in `VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay` performs the following sequence:

1. Creates a draft synthetic fiscal year with governed fund, responsibility-center, funding-source, program, and account dimensions.
2. Stages a checksummed opening-balance CSV, obtains independent approval, posts the per-fund opening JEV, and reconciles its row/debit/credit controls exactly.
3. Records all five readiness-layer decisions and activates the fiscal year only after the structural checks pass.
4. Creates a final approved budget version and independently authorizes its appropriation evidence.
5. Releases and independently posts an allotment against the authorized appropriation.
6. Lets a requesting office submit an obligation and lets Budget independently certify it against executable allotment.
7. Opens the payable directly from that authoritative F4 obligation, records a pinned required invoice rule, submits the checklist, and obtains independent Accounting acceptance.
8. Prepares the DV, completes its returned-signature gates, validates it, and posts and reconciles the recognition JEV.
9. Issues one check, submits and independently reviews the bank advice, retains the bank acknowledgement, and records claimant release evidence.
10. Posts and reconciles the payment-event JEV before allowing the case to complete.
11. Stages a checksummed bank-statement CSV, treats the governed opening JEV as the book baseline rather than a bank transaction, uniquely matches the exact payment bank line, proves a zero difference, and obtains independent bank-reconciliation approval.
12. Generates the Treasury Payment Instrument and Disbursement Register and proves that its control totals, case reference, check, and receipt trace back to the same case.

## Principal assertions

- The fiscal year cannot activate until the reconciled opening batch and all five readiness layers pass.
- The `2,000.00` governed bank opening contributes to book balance but cannot be falsely matched to a bank transaction row.
- The payable retains the authoritative certified-obligation public identity.
- The certified obligation is backed by an authorized appropriation and a posted allotment movement.
- Gross amount is `1,000.00`, governed withholding is `100.00`, and the DV/check/released/report amount is `900.00`.
- Recognition and payment use separate, rule-pinned, balanced, independently posted JEVs.
- The case does not reach `Completed` until the payment JEV is posted and reconciled to its source event.
- The staged statement matches the exact posted bank line and reaches a zero-difference independent reconciliation.
- The Treasury report reaches its control-reconciled state and retains the case, instrument, and receipt evidence.

## Deliberate boundary

The replay uses synthetic users, authority references, amounts, dates, configuration, and evidence. It does not establish:

- current local COA, DBM, BIR, bank, ordinance, or memorandum applicability;
- acceptance of any exact form, workbook, report layout, signature route, numbering rule, or documentary threshold;
- witnessed printer, paper, scanner, bank-file, accessibility, performance, continuity, or recovery results;
- consecutive redacted parallel cycles against the incumbent process;
- signed acceptance or cutover authority from the requesting offices, Budget, Accounting, Treasury, administration, audit/review, or executive owner.

Those remain field work under F10.2 and F11. The in-app local-form register and the Finance field-acceptance starter pack should be used to record that evidence without converting a candidate into policy automatically.

## Operator check

Run the focused replay from the repository root:

```powershell
.\.venv\Scripts\python.exe manage.py test vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay --verbosity 2
```

Run the complete regression suite before merging or releasing:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

The test databases and generated report artifacts are isolated from the working `db.sqlite3` and normal export storage.
