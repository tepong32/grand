# Finance operational report catalog

Status: **F9.2 implemented synthetic controls; exact local forms, tax outputs, signed-reference reproduction, and parent-F9 acceptance remain required**.

This slice uses the immutable evidence and reproduction foundation from F9.1 to add working operational reports for Budget, Accounting, and Treasury. Each starter is intentionally plain and editable through the governed report/template administration. None is represented as an accepted COA, DBM, BIR, or local form until its definition is locally confirmed and its exact template passes fidelity review.

## Catalog added

### Budget versus Posted Actual Schedule

The report begins with the authorized Budget schedule and cumulative allotment/obligation controls, then reads fiscal-year-to-date posted Accounting expense lines through the selected period end. An actual amount maps only when **fiscal year + fund + responsibility center + account** identifies exactly one Budget line.

- One exact Budget line receives the posted net expense.
- Several Budget lines sharing the same key remain ambiguous; GRAND does not spread the amount among PPAs.
- An Accounting expense key with no Budget counterpart remains unmatched.
- Ambiguous, unmatched, missing, or multiple Accounting-department conditions create a control exception that blocks review.

The report therefore exposes classification-bridge work instead of inventing program allocation. Local owners must decide and evidence any additional project/PPA/allocation dimension before GRAND may automate it.

### Posted General Ledger

The covered-period register contains every line of every posted JEV for the Accounting department, including date, JEV/source reference, fund, responsibility center, account, memo, debit, and credit. Debit and credit totals must agree exactly. Each retained source snapshot contains the complete included line set and links to the permission-checked JEV.

### Posted Accounts Payable Subsidiary Schedule

The as-of schedule aggregates immutable posted payable subsidiary movements by fund, mapped control account, governed payee identity, and source code. Review is allowed only when the subsidiary credit balance agrees exactly with the mapped general-ledger payable balance. Missing control-account setup is an exception, not a zero-balance approval.

### Posted Withholding Liability Schedule

The as-of schedule applies the same posted subsidiary-to-GL control to deduction/withholding liabilities by agency or deduction identity. It is working Accounting evidence only. It is not a BIR return, attachment, alphalist, certificate, filing confirmation, or automatic assertion of tax applicability.

### Payment Instrument and Disbursement Register

The Treasury register includes an instrument when issue, release, or cancellation activity falls inside the covered period. It retains the voucher, payee, fund, bank-account code, controlled instrument number, amount, current status, advice, claimant/receipt, cancellation, and replacement lineage.

Control exceptions identify missing DV, issue identity, advice link, release/receipt, or cancellation evidence. Incomplete historical data still produces a retained exception run for repair and explanation instead of crashing or disappearing from the report.

## Reporting workflow

1. The department chooses the controlled starter and covered period/end date.
2. GRAND pins the candidate applicability position, definition, selected fields, template, parameters, and format.
3. The dataset reads only authoritative posted/authorized sources and retains the data, control, source, freshness, and checksum snapshots.
4. The preparer investigates every control exception using source drill-through.
5. Corrections occur through the source transaction's governed draft/return/successor/adjustment/reversal route; report evidence is never edited to force agreement.
6. A different authorized reviewer reviews the new run. Candidate applicability or pilot template fidelity still blocks official approval.
7. Output, control/source CSV, and JSON reproduction receipt are stored in the existing TraceSync-ready department/user/category/year/month export hierarchy with checksum manifests.

## Modification allowance

F9.2 does not widen the transaction-editing window. Voucher, obligation, payable, and payment corrections remain allowed only at the stages already defined by their governing workflow—particularly before DV/check issuance where applicable. Once a posted JEV, certified movement, issued instrument, or approved report snapshot is locked, use its reasoned successor, adjustment, reversal, cancellation, replacement, or supersession route. Regenerate the report afterward so the prior run and corrected successor remain reproducible.

## Acceptance still required

Named Budget, Accounting, Treasury, management, records, IT, and audit-coordination owners must still confirm:

- exact report names, legal/administrative bases, period versus as-of semantics, funds, transaction/status scope, and cut-offs;
- the accepted Budget-to-actual classification bridge, including treatment of PPAs, projects, shared accounts, responsibility centers, reversals, prior-period adjustments, and year-end entries;
- control-account mappings, ageing/grouping rules, debit balances, payee/agency identities, tax types, remittances, and exception treatment;
- instrument/register scope, advice and bank-return presentation, claimant/receipt evidence, cancelled/replaced rows, signatories, copies, recipients, deadlines, and retention class;
- current BIR forms, certificates, attachments, filing channels, deadlines, validation rules, and proof of filing—implemented later only from accepted evidence; and
- redacted signed reference packages whose row populations, totals, layouts, and reproduction receipts agree exactly.

F9 remains open for financial statements and notes, current locally accepted BIR outputs, management dashboard definitions, report supersession/catalog controls, and signed-reference reproduction. F10 remains responsible for exact official-form mapping and non-developer template promotion.
