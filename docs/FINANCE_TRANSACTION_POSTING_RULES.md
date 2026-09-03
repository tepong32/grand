# Finance transaction posting rules and governed JEV handoff

## Status and purpose

F7.1 is an implemented synthetic control slice. It replaces the Voucher Workbench's single hard-coded recognition recipe with human-readable, versioned posting rules inside Finance Setup. It does not claim that GRAND's starter entry, a public source, or a generated CSV is already the municipality's accepted policy or official form.

The slice covers:

- editable transaction/event rules and ordered debit/credit instructions;
- an ordinary recognition starter that must be reviewed before submission;
- explicit recognition-point control;
- immutable rule and voucher snapshots at Accounting validation;
- balanced, idempotent JEV materialization using the snapshot rather than later mutable setup;
- independent submit/post, return, reversal, and source-handoff recovery already present in standalone Accounting;
- posted general-ledger and trial-balance CSV exports retained in the TraceSync-ready export tree.

Payment, remittance, cancellation, replacement, cash-receipt, subsidiary-ledger, closing, and period-reopen orchestration remain later F7/F8 work even though the event vocabulary is reserved now.

## What a non-technical setup reviewer changes

For each enabled transaction variant, open its draft Finance Setup release and describe each accounting event in ordinary office language:

1. Choose the event, such as recognition, liquidation, payment, remittance, adjustment, cancellation, reversal, or replacement.
2. Choose the exact recognition point, such as delivery acceptance, billing validation, DV validation, payment issuance/release, liquidation acceptance, or period end.
3. Add ordered debit and credit instructions. Accounts can come from voucher allocations, deduction mappings, the transaction payable mapping, a payment-account mapping, or one locally confirmed fixed account code. Amounts can come from each allocation, each deduction, gross, net, or total deductions.
4. Record the reviewed accounting authority and its local applicability or acceptance basis.
5. Submit only after every configured rule has at least one debit and one credit instruction.

The recognition starter creates the familiar shape “debit reviewed allocations; credit deductions; credit net payable.” Its authority begins with `EDIT BEFORE SUBMISSION`, and GRAND blocks release submission until that warning is replaced with the reviewed local basis. The starter is a convenience, not policy acceptance.

## Recognition decision and timing controls

The payable-readiness decision determines which event is eligible later:

- `Recognize through the governed DV/JEV route` selects the configured recognition rule, and the current F7.1 route requires its recognition point to be DV validation.
- `Liquidation / non-payment recognition decision` selects a separate liquidation rule when locally configured.
- `Accrue payable before settlement` is not silently converted to DV recognition. GRAND stops and requires the earlier accrual JEV to be linked by a future control.
- `Settle a previously recognized payable` is not silently recognized again. GRAND stops and requires the earlier posted payable to be linked by a future control.

Legacy voucher cases created before payable-intake records remain operable through the pinned F7 recognition rule and are visibly labelled as legacy intake cases. Historical posting requests created before F7 also remain reproducible through an explicit `legacy_pre_f7` recipe; new requests always pin a governed rule.

## Immutable evidence and correction boundary

At DV Accounting validation, GRAND pins:

- release, transaction variant, event, recognition point, title, description, and authority;
- every ordered account/amount instruction;
- the posting-rule UUID and SHA-256 checksum;
- the recognition decision and basis;
- voucher, allocation, deduction, gross, net, and source identifiers plus their separate payload checksum.

Draft JEV creation reads that snapshot. A later setup release cannot change an already requested entry. Before posting, an incorrect generated draft is discarded and the same voucher is returned and revalidated into a new request version. After posting, lines are immutable and correction uses a linked reversing or adjusting JEV with a reason.

This complements the wider modification allowance: draft setup changes stay inside a draft release; pre-DV claim and obligation relationship corrections remain versioned; once a DV, JEV, or check crosses its issuance/posting boundary, the relevant successor, reversal, cancellation, or replacement workflow applies instead of silent editing.

## Accounting exports and TraceSync

Authorized ledger users can export:

- the filtered Accounting journal control register, one row per JEV, with the same status/source/period/fund/next-action/search scope shown on screen, numeric balance controls, source and rule checksums, maker-checker actors, latest audit reason, and reversal/replacement lineage;
- the posted general ledger for all accounts or one selected account, including JEV/source lineage and any posting-rule checksum; and
- the posted trial balance with debit, credit, and net columns plus a balance indicator in its manifest.

The Accounting workspace keeps the existing JEV states intact and adds plain operational views for drafts needing lines, drafts whose debit and credit differ, returned corrections, independent posting, posted evidence, discarded drafts, and correction lineage. Invalid controlled filter values fail closed. The downloaded control register is generated from the exact same department-bounded query as the screen and records an append-only export receipt even when no JEV matches.

The browser download bytes are atomically retained under:

`department/user/category/year/month/artifact.csv`

Each artifact has an adjacent `.manifest.json` containing its SHA-256, byte length, time, department, user, parameters, and official-status boundary. Copy or synchronize the entire configured `GRAND_EXPORT_ROOT`; do not separate an artifact from its manifest.

## Official-source evidence and acceptance boundary

The design uses official COA material as review evidence, not automatic local acceptance:

- [COA Circular No. 2002-003](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2002-003-june-20-2002/) prescribes the New Government Accounting System manuals for LGUs.
- [COA illustrative barangay journal entries](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/Financial_Management_Brgy/d1.3.htm) demonstrate that check disbursement, cash advance, and liquidation are distinct accounting events rather than one universal voucher entry.
- [COA Government Accounting Manual disbursement guidance](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/GAM_A/g5.htm) provides useful JEV/source-document and unreleased-check/reversal evidence, but its exact LGU applicability must be confirmed.
- [COA liquidation workflow guidance](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/GAM_A/g21.htm) supports separate liquidation evidence and review, again subject to confirmed LGU/local applicability.

Before official use, Accounting must compare each enabled variant and event with current COA issuances, the locally adopted chart/mappings, completed redacted cases, accepted JEVs/schedules, and named-office practice. Exact official JEV, journal, ledger, and trial-balance templates remain acceptance-gated under F9/F10.

## Synthetic verification checklist

- Create a draft transaction variant and evidence rules.
- Build or enter its recognition rule, then verify submission is blocked while the starter warning remains.
- Replace the warning only after local review; confirm the rule has debit and credit instructions.
- Validate a synthetic payable decision and verify the request contains both payload and rule checksums.
- Materialize twice and verify only one draft JEV exists.
- Confirm the JEV is balanced, carries the pinned event/rule lineage, and requires independent posting.
- Confirm an earlier-accrual decision cannot generate a duplicate DV-recognition request.
- Export the ledger and trial balance; verify the downloaded bytes, archived bytes, checksum headers, manifests, and department/user folder boundaries agree.
- Filter the Accounting journal queue by source, period, fund, and next action; export the synchronized register and verify numeric totals, formula-safe text, source checksums, audit receipt, and reversal lineage.
