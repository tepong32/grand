# Finance statement notes and signed-reference comparison

Status: **F9.4 implemented synthetic controls; exact current disclosures, tax/BIR outputs, form geometry, and named-office acceptance remain controlled local work**.

F9.4 closes two software gaps left by the governed F9.3 statements:

- Accounting can prepare a versioned explanatory-note package against one exact-period, control-reconciled Statement of Financial Position run and one Statement of Financial Performance run.
- Accounting or the Finance template team can compare a retained signed/redacted reference copy with the exact control totals of one governed statement run.

Neither feature promotes public guidance into local authority. A technically reconciled note or reference comparison remains a controlled candidate until the LGU retains the applicable authority, approved wording/form, and named-office acceptance.

## Official-reference context

The public [COA Circular No. 2016-004](https://www.coa.gov.ph/wpfd_file/coa-circular-no-2016-004-september-30-2016/) package for the LGU chart conversion includes statements and an Annex G for Notes to Financial Statements. This is useful evidence that notes belong with the financial-statement package, but the circular's year-specific conversion context is not treated as proof of the municipality's current exact disclosure wording.

The COA Government Accounting Manual material also identifies notes as a component of a complete general-purpose financial-statement set. Because that public GAM page is framed for national government agencies, GRAND records it only as contextual guidance—not as automatic LGU applicability.

BIR's official electronic forms currently expose government-withholding-agent routes for forms such as [0619-E](https://efps.bir.gov.ph/efps-war/EFPSWeb_war/forms2018Version/0619E/0619e_01.xhtml) and [1601-EQ](https://efps.bir.gov.ph/efps-war/EFPSWeb_war/forms2018Version/1601EQ/1601eq_guidelines.html). Tax rules and electronic filing channels can change, so F9.4 does **not** generate, file, or label a working withholding schedule as a BIR return. Current registration, tax types, ATCs, rates, forms, attachments, deadlines, authorized officer, and filing channel require confirmation with the LGU's responsible officers and current BIR issuances before a later tax-output slice is enabled.

## Statement-note workflow

1. Open `Reports → Statement notes` and choose reconciled position and performance runs for the exact same period.
2. GRAND creates eleven plain-language candidate topics. Staff may edit or remove them; nothing is silently declared mandatory.
3. For each retained topic, write the disclosure from retained schedules and authority, or mark it not applicable with a specific reason.
4. Optionally link the disclosure to line codes pinned inside either statement run.
5. Submit the package. GRAND pins the note text, applicability position, selected runs, mapping snapshots, output/dataset/control checksums, reproduction keys, and package checksum.
6. A different authorized reviewer may:
   - return it with a correction;
   - accept it as immutable controlled working notes; or
   - approve it as locally accepted notes only when both source runs are approved official outputs and authority/local acceptance evidence is recorded.
7. Locked topics and evidence cannot be silently rewritten. Changed requirements use a successor package.

The broad starter topics include reporting entity/scope, preparation basis, significant accounting policies, cash, receivables, property/plant/equipment, payables/withholdings, revenue, expenses, commitments/contingencies, and events after the reporting date. They are review prompts, not a substitute for the current locally applicable disclosure checklist.

## Signed-reference comparison

From a governed statement run, an authorized preparer can upload a PDF, macro-free XLSX, PNG, or JPEG comparison copy after confirming that it is signed and redacted. GRAND never executes uploaded content.

The preparer enters each defined control total shown by the retained copy. On submission GRAND pins:

- the report run, period, status, statement mapping, output/data/control checksums, and reproduction key;
- the reference values and corresponding generated values;
- every exact difference;
- the reference-file SHA-256; and
- the whole comparison SHA-256.

A different reviewer can reconcile only a zero-difference comparison whose report evidence, reference file, and comparison snapshot have not drifted. A non-zero comparison remains visible and can be returned with the difference rather than overwritten.

Zero difference proves only that the entered control totals agree with the retained copy. It does not automatically prove labels, notes, signatories, page geometry, pagination, form stock, printer alignment, or current official acceptance; those remain F10 fidelity decisions.

## Guidance, roles, and exports

- Accounting DV Preparer prepares note packages and reference comparisons.
- Accounting Reviewer independently reviews both and may export retained evidence.
- Finance Configuration Manager/Approver may prepare/review reference comparisons used for later template promotion, but do not gain Accounting note-approval authority.
- Department and permission checks apply to every page and download.
- The Accounting Internal How-To is version 4 and adds note preparation and signed-reference steps to the floating, non-blocking `?` guidance.

Statement-note CSVs and reference-comparison JSON receipts are atomically archived in the single TraceSync-ready export root under department/user/category/year/month folders with adjacent checksum manifests. The retained redacted reference remains permission-checked in GRAND; copying an evidence receipt does not disclose or recreate the source file.

## Remaining F9/F10 acceptance work

- confirm the current LGU financial-statement set, exact note topics, wording, fund treatment, comparative columns, responsible preparers/reviewers, signatories, deadlines, recipients, and retention class;
- reproduce a complete redacted signed package from accepted opening balances and pilot transactions;
- confirm current BIR registration and applicable withholding/remittance/certificate/alphalist outputs before implementing exact tax artifacts;
- complete visual template mapping, page geometry, pagination, form-stock/printer tests, and independently approved promotion under F10; and
- record named Accounting, Treasury, Budget, management, records, IT, and audit-coordination acceptance before the parent F9/F11 gates can close.
