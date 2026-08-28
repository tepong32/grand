# eGAPS-to-GRAND finance modernization plan

Status: planning and prototype blueprint only. The current eGAPS installation remains untouched and authoritative until a separately approved cutover.

## Purpose

Reproduce the useful financial controls and outputs of eGAPS in GRAND, then improve them with clearer workflows, safer CRUD behavior, stronger auditability, a dedicated finance database, and no-code Excel template maintenance.

This plan is based on read-only inspection of the installed client, its launch/configuration topology, exposed navigation, and GRAND's existing Finance Setup, Voucher Workbench, Reporting, Records, and TracePoint contracts. It intentionally contains no credentials, production record values, personal identifiers, server addresses, or proprietary eGAPS source artifacts.

## Non-negotiable safety boundary

- Do not create, edit, delete, save, post, approve, cancel, release, print, export, import, or otherwise mutate eGAPS records during discovery.
- Do not connect GRAND with an account that can write to an eGAPS database.
- Do not use desktop UI automation as a production integration mechanism.
- Do not copy production records, screenshots containing PII, credentials, or proprietary compiled artifacts into the repository or test fixtures.
- Prefer vendor/DBA-approved read-only exports or a read-only OpenEdge SQL service. If neither is approved, use redacted manual exports for the prototype.
- Every imported source row must retain its source system, source key, extraction time, source checksum, and reconciliation status.
- GRAND must use a separate finance database. It must never share or attach to eGAPS database files.

## What was observed

### Deployment shape

- eGAPS is a native Progress OpenEdge 11.7 client, not a web application.
- Client code and parameter files are installed locally; business databases are reached over TCP on a remote OpenEdge server.
- The launch configuration separates logical databases for global/security data, audit data, accounting/eNGAS, budget monitoring, cash disbursement, and cash collection. A small client-local system/reporting database also exists.
- The observed client makes multiple broker/server connections after module launch. Host and service values are intentionally excluded from this repository.
- This is a tightly coupled legacy client/server design. GRAND should not reproduce its workstation-local database and many-direct-database-connection pattern.

### Functional shape

The enabled installation exposes eNGAS, Budget Monitoring and Management, and Cash Disbursement from the main menu. The accounting module includes:

- master data for funds/special accounts, chart of accounts, account-code setup, offices/responsibility centers, subsidiary-ledger references, LGU bank accounts, DV transaction types, deductions/taxes, and JEV types;
- collection/deposit and disbursement/liquidation paths;
- disbursement vouchers, report of checks issued, report of check disbursements, and liquidation reports;
- accountant's advice;
- JEV entry plus separate approval/unapproval/cancellation views;
- journal/recapitulation setup and output;
- general and subsidiary ledgers, payable/tax schedules, and BIR outputs;
- trial balance and core financial statements, including budget-versus-actual reporting.

The legacy UI is organized around maintenance “files,” modal windows, and generic Add/Edit/Delete buttons. GRAND should preserve the domain coverage while replacing this with role-based tasks and explicit record states.

## Target architecture

### Databases

Use three bounded stores in development and production:

1. `grand_core` — existing GRAND identity, departments, public services, records metadata, and non-finance modules.
2. `grand_finance` — finance configuration, budgets, obligations, vouchers, JEVs, posting batches, ledger entries, bank advice, payment instruments, template bindings, output metadata, and finance audit events.
3. `grand_finance_stage` — immutable eGAPS extracts, source schemas, import runs, row hashes, validation results, mapping decisions, and reconciliation issues.

The prototype may use separate SQLite files with wholly synthetic data. Production should use separately backed-up MySQL/PostgreSQL databases and least-privilege service accounts.

Do not create cross-database foreign keys. Finance records should carry stable GRAND UUIDs/IDs plus immutable display snapshots for the actor, department, payee, office, signatory, and other historically significant references. Cross-database work uses an outbox/inbox pattern and idempotency keys, not one transaction spanning databases.

### Integration boundary

Implement an `egaps_bridge` adapter boundary with interchangeable readers:

- `RedactedFileAdapter` for CSV/XLSX exports during prototype and UAT;
- `OpenEdgeReadOnlyAdapter` only after vendor/DBA approval, using a dedicated read-only account and allowlisted views;
- optional `ScheduledExportAdapter` when eGAPS can produce controlled server-side extracts without granting query access.

All adapters write only to `grand_finance_stage`. A separate promotion service validates, maps, and copies approved records into `grand_finance`. No adapter may write to eGAPS. UI automation is excluded from this boundary.

### Source-of-truth progression

- Discovery: eGAPS is authoritative; GRAND contains synthetic or redacted samples only.
- Shadow pilot: eGAPS remains authoritative; GRAND imports snapshots and compares results.
- Controlled parallel run: both systems process approved pilot cases, with documented reconciliation and no automatic outbound synchronization.
- Cutover: GRAND becomes authoritative only for an explicitly approved scope and date. Historical eGAPS records remain read-only evidence.

## User experience and navigation

Replace module/file menus with a task-first finance workspace:

- **My work** — drafts, returned items, due reviews, and blocking issues.
- **Budget** — appropriations, allotments, obligations/OBRs, balances, and budget-versus-actual.
- **Payables** — voucher preparation, supporting documents, deductions, and signatories.
- **Accounting** — JEV preparation/review/posting, journals, ledgers, closing periods, and statements.
- **Treasury** — payment instruments, bank advice, release, cancellation/replacement, and reconciliation.
- **Reports and templates** — approved outputs, schedules, template versions, and validation evidence.
- **Setup** — governed master data and effective-dated releases.
- **Reconciliation** — eGAPS import status, mismatches, exceptions, and sign-off.

Every transaction detail page should show:

- a plain-language title and stable reference number;
- breadcrumbs and a visible stage stepper;
- current owner/office, next required action, due date, and blockers;
- amounts and accounting balance checks in one summary;
- supporting documents and TracePoint custody without duplicating their authoritative content;
- comments/return reasons and a chronological, immutable audit history;
- only actions permitted in the current state and for the signed-in role.

Accessibility and usability requirements include keyboard navigation, strong focus states, responsive layouts, readable contrast, consistent terminology, saved searches, pagination, column customization, explainable validation messages, and confirmation screens for consequential actions.

## CRUD and workflow contract

### Master data

`Draft → Submitted → Approved → Scheduled/Active → Superseded/Retired`

- Create and edit only in Draft.
- A different authorized user approves.
- Active values are never edited in place; create a successor version.
- Delete is allowed only for an unused draft. Otherwise retire/supersede.
- Import candidates require mapping and reconciliation before promotion.

### Budget and obligation

`Draft budget → Review → Approved budget → Allotment → Obligation/OBR → Adjusted/Closed`

- Maintain fiscal-year versions and period locks.
- Prevent negative or over-obligated balances unless a separately approved statutory override exists.
- Adjust approved entries with append-only adjustment documents, never silent edits.

### Voucher/payable

`Draft → Budget certified → Accounting preparation → Awaiting signatures → Validated → Payment preparation → Advised → Released → Completed`

- Drafts may be edited by their preparer.
- Submission freezes the source snapshot and increments a state version.
- Returns reopen a controlled correction round and preserve prior values.
- Numbered/submitted vouchers cannot be deleted.
- Cancellation/replacement is a business event with reason, authority, and retained lineage.

### JEV and posting

`Draft → Balanced → Submitted → Approved → Posted → Reversed`

- Debit and credit totals must balance before submission.
- The preparer cannot approve/post the same JEV.
- Posted entries are immutable. Corrections use reversal and replacement JEVs.
- Period close blocks posting unless an explicitly approved reopening event exists.

### Advice and payment release

`Draft batch → Reconciled → Finalized → Released/Partially released → Closed`

- Finalization requires exact reconciliation to eligible payment instruments.
- Finalized advice is immutable; corrections use a new superseding batch.
- Check numbers and other instrument identifiers are never silently reused.
- Release records the authorized claimant and evidence without collecting unnecessary PII.

### Consistent mutation safeguards

- database transactions and row locks for consequential actions;
- expected state-version checks to reject stale pages;
- idempotency keys for every submit/approve/post/finalize/release action;
- server-side permission and segregation-of-duties checks;
- before/after snapshots in an append-only audit event;
- neutral Cancel for abandoning an unsaved form, clearly distinguished from the business action Cancel transaction;
- explicit validation summary before commit and a success receipt afterward.

## No-code Excel Template Studio

Build on GRAND's existing macro-free XLSX preflight, checksum, named-range, and controlled-mapping engines. Add a visual workflow for non-technical template managers:

1. **Upload or clone** — upload `.xlsx` or clone the last approved version. Reject `.xls`, `.xlsm`, macros, external links, embedded queries, and risky formulas.
2. **Inspect** — show worksheets, print areas, merged cells, formulas, named ranges, protected cells, and a rendered preview.
3. **Map fields visually** — select a cell/range, then choose a plain-language GRAND field such as “DV number,” “payee,” or “net amount.” Named ranges remain an optional advanced shortcut.
4. **Map repeating rows** — mark the first/last template row, choose line-item columns, define overflow behavior, and preview page breaks.
5. **Configure format rules** — dates, currency, zero display, text wrapping, signatory blocks, totals, and allowed formulas.
6. **Validate** — check required bindings, overlapping mappings, merged-cell safety, line capacity, formula dependencies, print geometry, and mapping checksum.
7. **Preview with synthetic data** — render/download a conspicuously synthetic workbook and compare it side by side with the blank template.
8. **Review change impact** — show a workbook diff, retained/lost mappings, moved cells, and fields needing remap. Auto-suggest bindings but require human confirmation.
9. **Submit and approve** — a separate authorized reviewer approves the immutable template version and its mapping checksum.
10. **Publish and roll back** — activate by effective date; existing outputs keep their pinned version. Rollback activates a prior approved version without rewriting history.

Template mapping modes should include single cell, merged range, repeating table, totals area, optional block, fixed label, image/logo anchor, and signatory block. The UI must use business labels rather than spreadsheet coordinates wherever possible, while still showing coordinates for verification.

## Phased delivery

### Phase 0 — Governance and safety gate

Deliverables:

- written read-only discovery authorization and named system/database owners;
- data classification, retention, backup, recovery, and incident procedure;
- approved list of redacted templates/exports and prohibited data;
- vendor/DBA decision on read-only OpenEdge export or SQL access;
- signed rule that no integration account can write to eGAPS.

Exit: owners approve the discovery boundary and rollback/escalation procedure.

### Phase 1 — Detailed process and data contract

Deliverables:

- workshops with Budget, Accounting, Treasury, IT, and COA Audit Team;
- page/process inventory for BMS, eNGAS, and cash disbursement;
- data dictionary for funds, accounts, offices, SL references, banks, deductions, DV/JEV, advice, payments, journals, ledgers, and periods;
- stable identifier and status mapping to GRAND;
- blank/redacted forms and expected totals/rounding/numbering rules;
- current exception, correction, cancellation, and approval paths.

Exit: every planned field and state has an owner, definition, source, sensitivity, and acceptance example.

### Phase 2 — Separate finance database and bridge skeleton

Deliverables:

- Django multi-database configuration and finance database router;
- finance-domain repository/service boundary with no cross-database foreign keys;
- `egaps_bridge` staging models, import-run ledger, row hashes, validation errors, and reconciliation issues;
- synthetic `RedactedFileAdapter` and repeatable fixtures;
- database backup/restore rehearsal and permission tests.

Exit: synthetic imports are idempotent, isolated, auditable, and cannot reach eGAPS.

### Phase 3 — Master data and setup modernization

Deliverables:

- extend Finance Setup for the observed eGAPS master-data coverage;
- import/mapping review queues with duplicate detection and effective dates;
- no-code forms, guided validation, separate approval, activation, retirement, and lineage;
- role-specific Setup dashboard and readiness blockers.

Exit: approved synthetic master data can drive downstream forms without free-text re-entry.

### Phase 4 — Excel Template Studio

Deliverables:

- visual mapping wizard and workbook preview;
- repeating-row and formula-safe mappings;
- synthetic preview, workbook/mapping diffs, review, approval, and activation;
- golden-workbook regression suite for DV, advice, check registers, JEV, ledgers, and financial statements.

Exit: an authorized non-developer can revise a blank template, remap it, validate it, and publish a new approved version without code changes.

### Phase 5 — Budget and obligation control

Deliverables:

- appropriations/allotments, obligation/OBR workflow, adjustments, period controls, and balance projections;
- Budget queues, certification, returns, approvals, and budget-versus-actual views;
- immutable movement ledger and reconciliation-ready source references.

Exit: synthetic budget cases reconcile from approved budget through obligation without negative-balance defects.

### Phase 6 — Voucher and payables completion

Deliverables:

- extend the existing Voucher Workbench for all locally validated DV categories, deductions, documents, signatories, corrections, and outputs;
- guided data entry with reusable payee/office/account selectors;
- TracePoint and Records links that preserve source ownership;
- controlled DV/register/transmittal outputs using approved templates.

Exit: ordinary-supplier and assistance scenarios pass role, amount, numbering, correction, and output acceptance tests in shadow mode.

### Phase 7 — JEV, journals, and posting engine

Deliverables:

- balanced JEV header/line model, review, approval, posting, reversal, and period locks;
- posting batches and immutable double-entry ledger;
- cash receipt, check disbursement, and general journal routes;
- preparer/approver separation and complete audit evidence.

Exit: every posted synthetic transaction balances, traces to its source case, and reverses without rewriting history.

### Phase 8 — Treasury, advice, and release

Deliverables:

- bank/payment-account controls, instrument issuance, cancellation/replacement, advice batching, reconciliation, and claimant release;
- Treasury work queues and Accounting finalization boundary;
- RCI, RCD/RD, liquidation, tax, and bank-advice outputs.

Exit: issued, advised, released, cancelled, and replacement instruments reconcile exactly and retain lineage.

### Phase 9 — Ledgers and financial reporting

Deliverables:

- general/subsidiary ledgers, AP and withholding schedules, trial balance, and period close;
- statement of financial position, financial performance, cash flows, changes in net assets/equity, and budget-versus-actual;
- controlled report definitions, mappings, review, approval, archive, and supersession.

Exit: approved synthetic opening balances plus transactions reproduce signed test statements and ledger schedules.

### Phase 10 — Read-only eGAPS shadow integration

Deliverables:

- approved read-only adapter or scheduled export ingestion;
- incremental watermarking, immutable snapshots, schema-drift detection, and source checksums;
- field-, record-, batch-, and control-total reconciliation dashboards;
- mismatch assignment, explanation, resolution evidence, and sign-off.

Exit: several consecutive periods reconcile within documented tolerances with zero unexplained control-total differences.

### Phase 11 — Parallel pilot and controlled cutover

Deliverables:

- limited office/transaction pilot, training, runbooks, support rota, and rollback plan;
- parallel processing with daily reconciliation and formal acceptance;
- production-readiness review covering security, performance, backups, recovery, printing, and statutory outputs;
- explicit scope/date decision for GRAND authority and eGAPS read-only retention.

Exit: Budget, Accounting, Treasury, IT, management, and the COA Audit Team sign the acceptance and cutover record. No implicit cutover occurs.

## Verification strategy

- permission and object-boundary tests for every role/action;
- accounting invariants and property-based tests for balanced postings and reconciliations;
- concurrency, stale-page, duplicate-submit, and idempotency tests;
- migration and schema-drift tests using synthetic source versions;
- golden XLSX/PDF comparisons for layout, formulas, totals, print areas, and page breaks;
- append-only audit and immutable-posting tests;
- backup/restore and disaster-recovery exercises;
- accessibility, keyboard, responsive, and plain-language usability tests;
- role-based UAT scripts using synthetic/redacted cases only.

## First prototype increments on this branch

1. Add architecture decision records for the separate finance and staging databases.
2. Add empty multi-database settings contracts driven by environment variables; no production endpoints.
3. Add an `egaps_bridge` app with synthetic import-run, source-record, and reconciliation models.
4. Add a redacted CSV/XLSX adapter interface and synthetic fixtures.
5. Add a read-only reconciliation workspace with no promotion action initially.
6. Add the visual Template Studio prototype over existing Finance/Reporting preflight services.
7. Add role-based finance navigation and task queues before expanding transaction CRUD.

Implementation must remain synthetic until Phase 0 and Phase 1 approvals are complete.
