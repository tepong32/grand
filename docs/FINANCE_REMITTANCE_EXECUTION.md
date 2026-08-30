# Finance deduction and withholding remittance execution

Status: **F8.1 implemented synthetic control; local acceptance remains required**.

This slice turns posted GRAND withholding subsidiary balances into a controlled, cross-voucher Treasury remittance. It does not initiate a bank transaction, import eGAPS history, or claim that a generic export is an accepted COA, BIR, GSIS, PhilHealth, Pag-IBIG, or local form.

## Operating route

1. Accounting first posts governed voucher recognition JEVs with immutable withholding subsidiary detail and the transaction-variant identity.
2. Treasury opens **Deduction and withholding remittances** and creates a one-fund batch under the active Accounting-approved Finance Setup release.
3. GRAND offers only positive posted balances for the selected transaction group and subtracts allocations reserved by every live remittance batch.
4. Treasury selects the receiving government agency, fund, payment account, method, date, reviewed authority/applicability reference, and source-schedule evidence.
5. A draft or Accounting-returned batch permits reasoned allocation revision or removal. Every prior allocation version remains retained. Submission closes ordinary editing.
6. A different authorized Accounting reviewer approves the exact checksum-pinned schedule or returns it with correction instructions.
7. Treasury records actual bank/payment release and optional acknowledgement/official-receipt evidence once. GRAND then creates an immutable posting request with a controlled JEV number.
8. Accounting materializes the JEV from the pinned rule. The supported starter debits each actual withholding liability account and credits the mapped bank account for the exact control total.
9. A separate poster submits/posts under the normal journal control. Only successful posting completes the remittance and reduces the subsidiary balance.

## Modification and correction boundaries

- Allocation amounts may change, or be removed with zero, only while the batch is **Draft** or **Returned for correction**. A reason and immutable successor version are mandatory.
- Accounting approval makes the schedule read-only. Actual release is a harder boundary: it cannot be repeated to repair a draft JEV.
- Discarding a generated pre-posting JEV retains the voided draft and reserves a new controlled JEV number for the same released payment snapshot.
- After posting, use a linked Accounting reversal or adjustment. Never rewrite the batch, posted journal lines, or subsidiary detail.
- One batch deliberately covers one fund and one bank/payment account. Prepare another batch when fund or account differs.

## Posting and setup contract

The selected transaction variant must have one active remittance posting rule whose event is `remittance`, recognition point is `deduction_remittance`, and Accounting effect is a journal entry. F8.1 accepts the conservative starter pattern:

- debit `deduction_mappings` using `each_deduction`; and
- credit `bank_mapping` using `event_amount` or `total_deductions`.

Materialization stops when a current deduction mapping no longer matches the account that carries the posted liability. This is an intervention signal, not permission to substitute another account. Finance Setup also needs active `deduction-remittance` and `journal-entry` sequences, active agency parties, fund/bank items, ledger mappings, and an open Accounting period.

## Roles, guidance, and evidence

- **Treasury Disbursement Officer** prepares/releases batches and exports the register.
- **Accounting Reviewer** independently approves/returns the Treasury schedule and posts the resulting submitted JEV.
- **Accounting DV Preparer** materializes and submits the checksummed JEV.
- Department-specific floating `?` guides explain preparation, modification, review, release, posting, recovery, and post-posting correction. Tutorial progress is private learning state and is not workflow evidence.
- The CSV register includes every allocation version, release/acknowledgement references, source-balance checksum, JEV number, and posting status. The same bytes are retained beneath `department/user/finance-remittances/year/month` in the single TraceSync-ready export root beside a SHA-256 manifest.

## Acceptance still required

Before official use, named local process owners must confirm recipient-agency handling, deadlines, forms/returns, authority references, fund/account separation, payment and acknowledgement evidence, exact account mappings, printed or electronic layouts, exception handling, and redacted end-to-end replay. F8.2 now supplies synthetic bank-statement intake/reconciliation; cash-position control, stale/unclaimed instruments, and consolidated statutory reporting remain later F8/F9 work.
