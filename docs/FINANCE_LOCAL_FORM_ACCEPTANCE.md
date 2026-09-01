# Finance local-form inventory and acceptance

Status: **F10.2 implemented synthetic control; actual LGU forms, devices, samples, witnessed trials, and named-office decisions remain field acceptance evidence.**

F10.1 governs how a report layout is previewed, compared, independently promoted, activated, and rolled back. Finance workbook templates separately use macro-free XLSX preflight, controlled named ranges, immutable checksums, and configuration-release activation. F10.2 adds the human and field-evidence layer needed before either technical template is represented as a locally accepted form.

## Plain-language form register

Each department can inventory a familiar form using ordinary fields:

- stable local code, title, and verified form number;
- purpose and current COA, DBM, BIR, bank, ordinance, memorandum, or local-procedure basis;
- accepting office/person and retained decision record;
- exact blank or safely redacted PDF, XLSX, DOCX, or image reference;
- digital, printed, or mixed delivery;
- signatory roles/order and wet/digital treatment;
- usual copies, recipients, acknowledgement, deadline, retention, and custody;
- paper, form stock, printer/tray/scale/duplex instructions;
- pagination, repeating headings, annexes, overflow, and continuation pages; and
- readable/download/accessibility expectations.

An inventory-only record is useful while an office is collecting evidence, but it cannot be submitted for acceptance. Submission requires one exact governed source:

- an active official-ready report template whose live content still matches the snapshot and checksum of its activated F10.1 promotion; or
- an active locally accepted Finance workbook in an active configuration release whose workbook bytes and controlled named-range mapping still pass verification.

No SQL, macro, executable script, credential, arbitrary formula, or production database is accepted by this register.

## Required, optional, conditional, and repeating sections

Authorized preparers describe the sections employees recognize on the actual form. A row is marked required, optional, conditional, or repeating. Optional and conditional sections must say what retained fact makes them apply and who decides. Repeating sections must state row capacity and continuation-page behavior.

This makes the starter human-modifiable without pretending that every form has the same optional blocks. The LGU adds those rules only after the actual reference proves them.

## Independently witnessed practical tests

Every form version needs a current result for seven categories:

1. data and control totals;
2. labels, fields, and visual comparison;
3. signatories, copies, recipients, and custody route;
4. overflow, pagination, and continuation pages;
5. accessibility, download, and readable output;
6. physical printer and form-stock trial; and
7. rollback and recoverable prior-version drill.

The employee performing a test records human-followable steps, expected and observed results, device/file/printer environment, a retained redacted evidence reference, and that evidence file's SHA-256. GRAND also locks the exact form instructions, sections, reference checksum, and governed source checksum exercised by the attempt. A different authorized witness records Pass, Fail, or—only for the printer/form-stock category of a genuinely digital-only form—Not applicable.

A failed result is never overwritten. After correction, the preparer records a reasoned successor attempt linked to the prior attempt. Editing the form, reference, source, or section behavior after a test also makes that result stale and requires a reasoned successor attempt. The latest attempt in every category must pass or be validly not applicable against the current exact basis before form submission.

## Submission, acceptance, and modification

Submission rechecks the exact source template, reference file, source/checksum evidence, readable instructions, form sections, and latest witnessed tests. GRAND freezes one deterministic snapshot and SHA-256.

A different reviewer accepts or returns it with a reason. The preparer or submitter cannot accept the same record. Accepted form instructions, source/template identity, reference, sections, tests, and checksum are immutable.

Changes use a reasoned successor. The familiar form fields and section definitions are copied so staff can edit them without rebuilding the checklist, but test results are not copied: practical tests must be performed and witnessed again. The predecessor remains accepted until the successor is accepted, then becomes historically superseded.

Changing this form evidence does not edit a report run, voucher, obligation, JEV, remittance, check, payment, bank reconciliation, or signed packet. Those records retain their own correction, cancellation, reversal, replacement, or reopen route.

## TraceSync evidence packet

Accepted and historically superseded form versions export a deterministic JSON packet beneath:

`department/user/finance-local-form-acceptance/year/month`

It contains the accepted form contract, exact source snapshot, blank/redacted-reference checksum, current witnessed results, complete failed/superseded test history, workflow actors/times, non-export event history, and source/submission SHA-256 values. Export actions remain append-only audit events but are excluded from the packet body so downloading the same retained record does not change the next packet's bytes. The adjacent export manifest locks the downloaded bytes.

The packet references separately retained blank/redacted samples, test outputs, print samples, screenshots, signed comparison sheets, and promotion receipts; it does not silently duplicate signature images, confidential form bodies, credentials, or TIN-bearing data.

## F11 field-qualification handoff

F11.6 consumes this acceptance record directly. An editable field-qualification plan must select the exact current Accepted form versions used during its consecutive cycles. Plan submission revalidates this protected packet and pins its accepted snapshot plus reference, source, and submission SHA-256 values; every field-cycle submission separately pins the same exact form set. If a selected form is superseded, F11 readiness fails and the changed form must be exercised under a successor cycle and qualification plan. A narrative form-register reference alone cannot satisfy that gate, and the protected blank/redacted reference file is not copied into the cutover export.

## Acceptance still required

Before claiming the parent F10 gate, the LGU must populate this register with its actual enabled forms and retain:

- current authority and named local acceptance;
- exact blank/redacted reference and generated golden outputs;
- proven required/optional/conditional/repeating behavior;
- actual signatory, copy, recipient, deadline, retention, and custody decisions;
- overflow and page-break examples at realistic volume;
- accessibility and supported download checks;
- physical printer, tray, scale, duplex, margin, paper, and form-stock trials where applicable;
- rollback/recovery drills; and
- independent named-office acceptance for each exact form version.

F10.2 provides the governed place and enforcement needed to collect that evidence. It does not fabricate the evidence or declare a starter official.
