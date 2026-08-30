# Finance payment-event posting and register

F7.3 extends the same GRAND voucher case and immutable Accounting handoff from initial recognition into the physical payment cycle. It does not create a separate Treasury ledger and it does not claim that a starter rule is locally accepted.

## Governed event decisions

Each transaction variant must now contain reviewed decisions for initial recognition or liquidation, payment, deduction remittance, cancellation, and replacement. A decision can either create a governed JEV or explicitly record that no JEV is required. `Build editable payment-cycle starters` creates plain-language starting points inside a draft Finance Setup release:

- payment on actual release: debit the transaction payable and credit the mapped bank/cash account for the current instrument amount;
- cancellation before release: explicit no-entry starter;
- replacement before release: explicit no-entry starter; and
- deduction/withholding remittance: debit the remitted deduction payable lines and credit the mapped bank/cash account.

Every starter begins with `EDIT BEFORE SUBMISSION`. Accounting must compare it with the locally accepted COA/local treatment, update its authority basis, and retain maker-checker release approval. GRAND blocks submission when an unresolved starter remains or a typed variant lacks complete lifecycle decisions.

## Release-to-posting route

When a pinned payment rule applies at actual release, GRAND records the authorized claimant, receipt, physical instrument, bank-account code, date, and exact event amount in one checksum-backed posting request. The case temporarily moves from Treasury to **Accounting payment-event JEV posting**.

Accounting uses its familiar source-generated JEV queue. GRAND interprets the pinned rule snapshot, creates payable subsidiary detail, and keeps independent prepare/post roles. Posting returns the case to the exact recorded stage:

- a partial or split payment returns to Treasury release for the remaining advised instrument; and
- the final payment completes the shared case.

The release action must not be repeated while Accounting is posting. Idempotent instrument triggers and controlled JEV numbering prevent duplicate requests.

## Cancellation, replacement, and modification boundary

Voucher convenience edits remain available only before payment-instrument issuance. Once a check exists, the user does not overwrite it or reuse its number. Treasury cancels or spoils it with a reason and creates a linked replacement.

The pinned local event rule determines the Accounting effect. An explicit no-entry decision is retained as evidence and continues the Treasury route immediately; it is not displayed as missing work. If local policy requires a JEV instead, the case uses the same recoverable Accounting event-posting stage.

If a generated payment-event draft is discarded before posting, GRAND retains the voided draft and reason, reserves a new controlled JEV number, and creates a successor request. The physical check release is not repeated. After posting, corrections use linked reversal/adjustment entries rather than rewriting the posted JEV or voucher history.

## Portable payment register

Authorized users can export a case payment register from the Voucher Workbench. The CSV includes instrument identity, bank/check number, amount and status, issue operator/time, cancellation reason, replacement lineage, advice, claimant/release/receipt evidence, and payment/cancellation/replacement accounting decisions and JEV statuses.

The downloaded bytes are also archived below the one configured TraceSync-ready root using `department/user/category/year/month/artifact`, beside a SHA-256 manifest. Copy or synchronize the complete root for safekeeping. The CSV is controlled data interchange and is not automatically an accepted official COA or local register form.

## Internal How-Tos

The floating `?` window now explains the payment-event queue to Accounting preparers/posters and the cancellation, replacement, release, resume, and export steps to Treasury. Visibility follows the employee's current department and permission. Private tutorial checkmarks do not approve a transaction, prove job completion, measure performance, or transfer to a successor.

## Remaining parent-phase acceptance

This is an implemented synthetic control. Official use still requires locally accepted per-variant entries/no-entry decisions, redacted complete-case replay, account mapping and segregation review, named Accounting/Treasury acceptance, and comparison of the payment register with the exact approved local form. F8.1 now covers runtime remittance batches, F8.2 covers synthetic bank-statement reconciliation, and F8.3 covers synthetic cash position/reservation plus unclaimed/stale/returned classification. Broader payment methods/printing/custody, accepted thresholds/forms, advice acknowledgement, returned-item Accounting treatment, and named-office replay remain F8 acceptance work.
